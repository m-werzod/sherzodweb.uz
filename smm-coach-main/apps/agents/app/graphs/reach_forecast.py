"""Stage 5 — deterministic per-post reach forecast from script-quality signals.

The scriptwriter only emits numeric reach (P10/P50/P90) when a cross-tenant
exemplar happens to be retrieved; otherwise it falls back to a bare qualitative
`impactBand` and the script-quality signals (hook A/B retention, viral/fit
scores) never touch the prediction. This module closes that gap with a pure,
deterministic formula:

    reach ≈ account_baseline × quality_multiplier  (blended with exemplar)

`account_baseline` is the user's OWN median post reach (or a follower-derived
estimate for new accounts), so the forecast is grounded in their real audience
rather than an LLM guess. The function is pure (no I/O, no randomness) so it is
unit-testable; the caller supplies the baseline + quality signals.
"""
from __future__ import annotations

import math

# Typical reach-as-fraction-of-followers for a small account with no post
# history yet. Engagement rate falls as accounts grow, so this is a single
# conservative tier — refined the moment real post medians exist.
_FOLLOWER_REACH_RATE = 0.30
_DEFAULT_BASELINE = 300.0  # cold start: no posts AND no followers known

# Qualitative band → multiplier when no numeric quality score is available.
_BAND_MULT = {"low": 0.7, "medium": 1.0, "high": 1.45, "setup": 0.0, "action": 0.0}

# Follower-conversion: a fraction of reach that turns into new followers.
_FOLLOWER_CONV = 0.008


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _round_nice(x: float) -> int:
    """Round to a human-readable precision so the UI shows 1,200 not 1,237."""
    if x <= 0:
        return 0
    if x < 100:
        return int(round(x / 10.0) * 10)
    if x < 1000:
        return int(round(x / 50.0) * 50)
    if x < 10_000:
        return int(round(x / 100.0) * 100)
    return int(round(x / 500.0) * 500)


def _quality_multiplier(
    viral_potential: float | None,
    audience_fit: float | None,
    hook_score: float | None,
    impact_band: str | None,
) -> tuple[float, int]:
    """Combine whatever quality signals are present into a single multiplier
    centered near 1.0. Returns (multiplier, n_signals_used)."""
    factors: list[float] = []

    # viral_potential / audience_fit are 1-10 (Haiku scorer). Map to a band
    # centered at the 5-6 midpoint = ~1.0; 10 ≈ 1.5, 1 ≈ 0.65.
    if isinstance(viral_potential, (int, float)) and viral_potential > 0:
        factors.append(_clamp(0.6 + (float(viral_potential) / 10.0) * 0.9, 0.6, 1.55))
    if isinstance(audience_fit, (int, float)) and audience_fit > 0:
        # Audience fit moves reach less than raw virality.
        factors.append(_clamp(0.75 + (float(audience_fit) / 10.0) * 0.5, 0.75, 1.3))

    # hook_score is 0..1 (B-variant strength); 0.5 = the A/B are a tie. We treat
    # the CHOSEN hook's strength as max(0.5, score) so a tie is neutral (1.0), a
    # strong B lifts reach, and a weak B never drags the (kept) A below neutral.
    if isinstance(hook_score, (int, float)):
        eff = max(0.5, float(hook_score))
        factors.append(_clamp(1.0 + (eff - 0.5) * 0.3, 1.0, 1.15))

    if not factors:
        band = _BAND_MULT.get((impact_band or "medium").lower(), 1.0)
        return (band if band > 0 else 1.0, 0)

    # Geometric mean keeps the combined multiplier balanced (one huge signal
    # can't blow it out) and stays at 1.0 when every factor is neutral.
    prod = 1.0
    for f in factors:
        prod *= f
    geo = prod ** (1.0 / len(factors))
    return (_clamp(geo, 0.5, 2.0), len(factors))


def calibration_from_ratios(ratios: list[float], *, min_samples: int = 3) -> float:
    """Stage 5 feedback loop: derive a per-tenant correction factor from past
    actual/predicted reach ratios. If we've systematically over/under-predicted
    (median ratio ≠ 1), future forecasts are scaled to match reality. Returns 1.0
    (no correction) below min_samples; clamped to [0.5, 2.0] so a few outliers
    can't wildly swing it. Pure → unit-testable."""
    vals = sorted(r for r in ratios if isinstance(r, (int, float)) and r > 0)
    if len(vals) < min_samples:
        return 1.0
    mid = len(vals) // 2
    median = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0
    return _clamp(median, 0.5, 2.0)


def forecast_reach(
    *,
    median_reach: float = 0.0,
    followers: int = 0,
    viral_potential: float | None = None,
    audience_fit: float | None = None,
    hook_score: float | None = None,
    exemplar_reach: float | None = None,
    impact_band: str | None = None,
    calibration: float = 1.0,
) -> dict:
    """Compute a deterministic reach diapazon + follower estimate.

    Returns a dict mergeable into `predict_evidence`:
      reachLow / reachMid / reachHigh (ints), predictedFollowers (int),
      confidence ('low'|'medium'|'high'), _source ('model_forecast'), note (uz).
    """
    # 1) Baseline: own post median > follower-derived > cold-start default.
    if median_reach and median_reach > 0:
        baseline = float(median_reach)
        base_conf = "high"
    elif followers and followers > 0:
        baseline = max(float(followers) * _FOLLOWER_REACH_RATE, 50.0)
        base_conf = "medium"
    else:
        baseline = _DEFAULT_BASELINE
        base_conf = "low"

    # 2) Quality multiplier from available signals.
    mult, n_signals = _quality_multiplier(viral_potential, audience_fit, hook_score, impact_band)

    p50 = baseline * mult

    # 3) Blend with the cross-tenant exemplar when present. Exemplars are often
    # from bigger accounts, so cap their pull at 4× the user's baseline and take
    # a geometric mean — the exemplar informs the ceiling, doesn't replace it.
    blended = False
    if exemplar_reach and exemplar_reach > 0 and baseline > 0:
        capped = min(float(exemplar_reach), baseline * 4.0)
        p50 = math.sqrt(p50 * capped)
        blended = True

    # 3b) Calibration: correct our systematic bias from resolved past predictions
    # (Stage 5 feedback loop). 1.0 = no correction (default / too few samples).
    p50 *= _clamp(calibration, 0.5, 2.0)

    # 4) Spread: tighter when we have real history + a quality signal, wider on
    # cold start. Reach is right-skewed (a few posts pop), hence asymmetric.
    if base_conf == "high" and (n_signals > 0 or blended):
        lo_f, hi_f, confidence = 0.55, 1.9, "high"
    elif base_conf == "low" and n_signals == 0:
        lo_f, hi_f, confidence = 0.35, 2.8, "low"
    else:
        lo_f, hi_f, confidence = 0.45, 2.3, "medium"

    reach_mid = _round_nice(p50)
    reach_low = _round_nice(p50 * lo_f)
    reach_high = _round_nice(p50 * hi_f)

    # 5) Follower estimate: a small fraction of reach, scaled by quality. Kept
    # deliberately conservative — over-promising followers erodes trust.
    pred_followers = _round_nice(p50 * _FOLLOWER_CONV * mult)

    if base_conf == "high":
        note = f"Prognoz sizning {int(baseline):,} o'rtacha qamroyingiz + ssenariy sifatidan hisoblandi."
    elif base_conf == "medium":
        note = "Prognoz obunachilar soni + ssenariy sifatidan taxminiy hisoblandi (post tarixi kam)."
    else:
        note = "Boshlang'ich taxmin — aniq post tarixi yig'ilgach prognoz aniqlashadi."

    return {
        "reachLow": reach_low,
        "reachMid": reach_mid,
        "reachHigh": reach_high,
        "predictedFollowers": pred_followers,
        "confidence": confidence,
        "_source": "model_forecast",
        "note": note,
    }

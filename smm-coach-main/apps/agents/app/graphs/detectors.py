"""Deterministic performance detectors (Stage 13) — pure functions, no DB/LLM.

account_tracker computes per-post rates against a rolling baseline and classifies
a verdict (underperform / watch / norm / breakout); comment_sentinel flags a
negative-comment wave. These feed the alert + self-correction loop
(performance_review). Thresholds are module constants so they can be tuned in one
place against real production output.

Mirrors the goal_profiles.py style: stdlib only, trivially unit-testable.
"""
from __future__ import annotations

import statistics
from typing import Literal

Verdict = Literal["underperform", "watch", "norm", "breakout"]

# A post must clear this much reach before we judge it — tiny-sample noise → norm.
_MIN_REACH = 50
# Underperformance bands: rate as a fraction of the rolling-median baseline.
_WATCH_MULT = 0.6   # <= median * 0.6 → soft "watch"
_RED_MULT = 0.4     # <= median * 0.4 → "underperform"
_BREAKOUT_MULT = 3.0  # >= median * 3 on a core signal → "breakout"
# Need at least this many metrics agreeing before calling under/watch (anti-noise).
_MIN_SIGNALS = 2
# Negative-comment wave.
_NEG_WAVE_FRAC = 0.30
_NEG_WAVE_MIN_COMMENTS = 10

_RATE_KEYS = ("reach_rate", "er_reach", "save_rate", "send_rate")


def compute_rates(metrics: dict | None, followers: int) -> dict[str, float]:
    """Normalised engagement rates from a post's raw metrics. Only emits a rate
    when its denominator is known (>0). `_reach` is carried for the volume gate.

    `metrics` is the actualMetrics jsonb shape ({likes, comments, views, plays})
    and tolerates richer keys (reach/saves/shares/sends) when present.
    """
    m = metrics or {}
    reach = float(m.get("reach") or m.get("views") or m.get("plays") or 0)
    likes = float(m.get("likes") or 0)
    comments = float(m.get("comments") or 0)
    saves = float(m.get("saves") or 0)
    shares = float(m.get("shares") or m.get("sends") or 0)

    rates: dict[str, float] = {"_reach": reach}
    f = float(followers or 0)
    if f > 0:
        rates["reach_rate"] = reach / f
    if reach > 0:
        rates["er_reach"] = (likes + comments + saves + shares) / reach
        if saves:
            rates["save_rate"] = saves / reach
        if shares:
            rates["send_rate"] = shares / reach
    return rates


def rolling_baseline(history: list[dict]) -> dict[str, float]:
    """Median of each rate across past posts (history = list of compute_rates
    dicts). Empty when there's no usable history yet."""
    out: dict[str, float] = {}
    for k in _RATE_KEYS:
        vals = [
            float(h[k]) for h in history
            if isinstance(h, dict) and h.get(k) is not None
        ]
        if vals:
            out[k] = statistics.median(vals)
    return out


def classify_verdict(rates: dict, baseline: dict, total_comments: int = 0) -> Verdict:
    """Classify a post vs its rolling baseline. Returns 'norm' when there's no
    baseline yet or the post's reach is too small to judge (anti-noise)."""
    if not baseline:
        return "norm"
    if float(rates.get("_reach") or 0) < _MIN_REACH:
        return "norm"

    # Breakout: a CORE signal (reach or engagement) ≥ 3× its median.
    for key in ("reach_rate", "er_reach"):
        base = baseline.get(key)
        val = rates.get(key)
        if base and val is not None and val >= base * _BREAKOUT_MULT:
            return "breakout"

    watch = red = 0
    for key, base in baseline.items():
        if not base or base <= 0:
            continue
        val = rates.get(key)
        if val is None:
            continue
        if val <= base * _RED_MULT:
            red += 1
            watch += 1
        elif val <= base * _WATCH_MULT:
            watch += 1

    if red >= _MIN_SIGNALS:
        return "underperform"
    if watch >= _MIN_SIGNALS:
        return "watch"
    return "norm"


def _neg_fraction(sentiment: dict, total_comments: int) -> float:
    """Negative share of (positive+negative+neutral) — scale-agnostic (works
    whether the buckets are fractions, percentages, or raw counts)."""
    neg = sentiment.get("negative")
    if neg is None:
        return 0.0
    neg = float(neg)
    pos = float(sentiment.get("positive") or 0)
    neu = float(sentiment.get("neutral") or 0)
    total = neg + pos + neu
    if total <= 0:
        # fall back to share of total comments when only a negative count is given
        return neg / float(total_comments) if total_comments else 0.0
    return neg / total


def detect_negative_wave(sentiment: dict | None, total_comments: int = 0) -> bool:
    """True when a post has a meaningful negative-comment spike (gated by a
    minimum comment volume so a single grumpy reply doesn't trip it)."""
    if not sentiment or (total_comments or 0) < _NEG_WAVE_MIN_COMMENTS:
        return False
    return _neg_fraction(sentiment, total_comments) > _NEG_WAVE_FRAC

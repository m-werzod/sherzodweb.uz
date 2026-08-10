"""Stage 5 — deterministic reach forecast. Pins: baseline selection, that
quality signals move the forecast monotonically, exemplar blending stays
bounded, ordering (low<mid<high), and the cold-start path."""
from __future__ import annotations

from app.graphs.reach_forecast import forecast_reach


def test_history_baseline_drives_midpoint():
    r = forecast_reach(median_reach=2000, hook_score=0.5)
    # Neutral quality (hook 0.5, no scores) → mid ≈ baseline.
    assert 1800 <= r["reachMid"] <= 2200
    assert r["confidence"] == "high"
    assert r["_source"] == "model_forecast"


def test_low_high_bracket_mid():
    r = forecast_reach(median_reach=5000, viral_potential=7, hook_score=0.7)
    assert r["reachLow"] < r["reachMid"] < r["reachHigh"]
    assert r["reachLow"] > 0


def test_higher_quality_predicts_more_reach():
    low = forecast_reach(median_reach=1000, viral_potential=2, audience_fit=3, hook_score=0.4)
    high = forecast_reach(median_reach=1000, viral_potential=10, audience_fit=9, hook_score=0.95)
    assert high["reachMid"] > low["reachMid"]


def test_follower_fallback_when_no_history():
    r = forecast_reach(median_reach=0, followers=10_000, hook_score=0.5)
    # 10k followers * 0.30 reach-rate ≈ 3000 baseline.
    assert 2400 <= r["reachMid"] <= 3600
    assert r["confidence"] in {"medium", "low"}


def test_cold_start_widest_spread_low_confidence():
    r = forecast_reach(median_reach=0, followers=0)
    assert r["confidence"] == "low"
    assert r["reachMid"] > 0
    # Cold-start spread is the widest band.
    assert r["reachHigh"] / max(1, r["reachMid"]) >= 2.5


def test_exemplar_blend_is_bounded():
    # A giant exemplar (100k) must not blow the forecast past the 4x cap blend.
    base = forecast_reach(median_reach=1000, hook_score=0.5)
    withex = forecast_reach(median_reach=1000, hook_score=0.5, exemplar_reach=100_000)
    assert withex["reachMid"] > base["reachMid"]  # exemplar lifts it
    # Capped at sqrt(baseline_p50 * min(exemplar, baseline*4)) = sqrt(1000*4000) ≈ 2000.
    assert withex["reachMid"] <= 2600


def test_predicted_followers_conservative_and_present():
    r = forecast_reach(median_reach=5000, viral_potential=8, hook_score=0.8)
    assert r["predictedFollowers"] >= 0
    # Followers should be a small fraction of reach, never exceed it.
    assert r["predictedFollowers"] < r["reachMid"]


def test_impact_band_used_when_no_numeric_signals():
    high = forecast_reach(median_reach=1000, impact_band="high")
    low = forecast_reach(median_reach=1000, impact_band="low")
    assert high["reachMid"] > low["reachMid"]


def test_calibration_below_min_samples_is_neutral():
    from app.graphs.reach_forecast import calibration_from_ratios
    assert calibration_from_ratios([0.5, 0.6]) == 1.0  # < 3 samples
    assert calibration_from_ratios([]) == 1.0


def test_calibration_median_ratio():
    from app.graphs.reach_forecast import calibration_from_ratios
    # We consistently over-predict (actual ~0.6× predicted) → factor ~0.6.
    assert calibration_from_ratios([0.6, 0.6, 0.6, 0.6]) == 0.6


def test_calibration_clamped():
    from app.graphs.reach_forecast import calibration_from_ratios
    assert calibration_from_ratios([5, 5, 5]) == 2.0   # clamp high
    assert calibration_from_ratios([0.1, 0.1, 0.1]) == 0.5  # clamp low
    # negatives/zero ignored
    assert calibration_from_ratios([-1, 0, 0.6, 0.6, 0.6]) == 0.6


def test_calibration_applied_to_forecast():
    base = forecast_reach(median_reach=2000, hook_score=0.5)
    cal = forecast_reach(median_reach=2000, hook_score=0.5, calibration=0.5)
    assert cal["reachMid"] < base["reachMid"]

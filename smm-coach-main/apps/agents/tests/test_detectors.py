from __future__ import annotations

from app.graphs import detectors as d

# ── compute_rates ──

def test_compute_rates_basic():
    r = d.compute_rates({"views": 1000, "likes": 80, "comments": 20}, followers=500)
    assert r["reach_rate"] == 2.0  # 1000 / 500
    assert r["er_reach"] == 0.1  # (80+20) / 1000
    assert r["_reach"] == 1000.0


def test_compute_rates_zero_denominators_omit_keys():
    r = d.compute_rates({"views": 0, "likes": 5}, followers=0)
    assert "reach_rate" not in r  # followers 0
    assert "er_reach" not in r  # reach 0
    assert r["_reach"] == 0.0


def test_compute_rates_uses_richer_keys_when_present():
    r = d.compute_rates({"reach": 200, "saves": 20, "shares": 10, "likes": 0, "comments": 0}, 100)
    assert r["save_rate"] == 0.1
    assert r["send_rate"] == 0.05


# ── rolling_baseline ──

def test_rolling_baseline_median():
    hist = [{"reach_rate": 1.0}, {"reach_rate": 2.0}, {"reach_rate": 3.0}]
    assert d.rolling_baseline(hist) == {"reach_rate": 2.0}


def test_rolling_baseline_empty():
    assert d.rolling_baseline([]) == {}


# ── classify_verdict ──

def test_verdict_norm_without_baseline():
    assert d.classify_verdict({"reach_rate": 1.0, "_reach": 1000}, {}) == "norm"


def test_verdict_norm_when_reach_too_small():
    # below _MIN_REACH → don't judge
    assert d.classify_verdict({"reach_rate": 0.01, "_reach": 10}, {"reach_rate": 1.0}) == "norm"


def test_verdict_underperform_two_red_signals():
    rates = {"_reach": 1000, "reach_rate": 0.3, "er_reach": 0.3}  # both ≤ 0.4× base
    base = {"reach_rate": 1.0, "er_reach": 1.0}
    assert d.classify_verdict(rates, base) == "underperform"


def test_verdict_watch_two_soft_signals():
    rates = {"_reach": 1000, "reach_rate": 0.55, "er_reach": 0.55}  # ≤ 0.6× base, > 0.4×
    base = {"reach_rate": 1.0, "er_reach": 1.0}
    assert d.classify_verdict(rates, base) == "watch"


def test_verdict_breakout_on_core_signal():
    rates = {"_reach": 5000, "reach_rate": 4.0}  # ≥ 3× base reach_rate
    base = {"reach_rate": 1.0}
    assert d.classify_verdict(rates, base) == "breakout"


def test_verdict_norm_when_on_target():
    rates = {"_reach": 1000, "reach_rate": 1.0, "er_reach": 1.0}
    base = {"reach_rate": 1.0, "er_reach": 1.0}
    assert d.classify_verdict(rates, base) == "norm"


# ── detect_negative_wave ──

def test_negative_wave_needs_min_comments():
    assert d.detect_negative_wave({"negative": 0.9}, total_comments=3) is False


def test_negative_wave_triggers_on_high_share():
    assert d.detect_negative_wave({"negative": 6, "positive": 2, "neutral": 2}, total_comments=10) is True


def test_negative_wave_low_share_false():
    assert d.detect_negative_wave({"negative": 1, "positive": 7, "neutral": 5}, total_comments=13) is False

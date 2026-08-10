from __future__ import annotations

import math

from app.workers.prediction_resolver import _as_dict, _metric_actual, compute_accuracy_pct


def test_accuracy_none_when_empty():
    assert compute_accuracy_pct([]) is None
    assert compute_accuracy_pct([None, None]) is None


def test_accuracy_perfect_predictions():
    # zero error → 100%
    assert compute_accuracy_pct([0.0, 0.0, 0.0]) == 100.0


def test_accuracy_half_off():
    # mean |error| = 0.5 → (1 - 0.5) * 100 = 50
    assert compute_accuracy_pct([0.5, -0.5]) == 50.0


def test_accuracy_clamps_to_zero_when_way_off():
    # mean |error| = 2.0 → (1 - 2) * 100 = -100 → clamped to 0
    assert compute_accuracy_pct([2.0, 2.0]) == 0.0


def test_accuracy_uses_absolute_error():
    # under- and over-prediction of equal magnitude average to the same |error|
    assert compute_accuracy_pct([-0.2, 0.2]) == compute_accuracy_pct([0.2, 0.2])


def test_accuracy_skips_none_entries():
    # None mixed in is ignored, not treated as 0
    assert compute_accuracy_pct([0.4, None]) == compute_accuracy_pct([0.4])


# ── _metric_actual: raw vs rate resolution (Stage 5 PR-2) ──

def test_metric_actual_raw_key():
    assert _metric_actual("reach", {"reach": 1000}, 0) == 1000.0
    assert _metric_actual("saves", {"saves": 42}, 0) == 42.0


def test_metric_actual_save_rate():
    # saves / reach = 30 / 1000
    assert _metric_actual("save_rate", {"reach": 1000, "saves": 30}, 500) == 0.03


def test_metric_actual_er_reach():
    # (likes + comments) / reach = (80 + 20) / 1000
    assert _metric_actual("er_reach", {"views": 1000, "likes": 80, "comments": 20}, 500) == 0.1


def test_metric_actual_rate_none_when_no_reach():
    # rate denominator (reach) still 0 → unresolved, retried tomorrow
    assert _metric_actual("save_rate", {"reach": 0, "saves": 5}, 500) is None


def test_metric_actual_reach_falls_back_to_views():
    # 'reach' isn't a raw instagrapi key — resolve via views|plays so scraped
    # metrics still close the loop.
    assert _metric_actual("reach", {"views": 1500}, 0) == 1500.0
    assert _metric_actual("reach", {"plays": 900}, 0) == 900.0


def test_metric_actual_reach_none_when_no_signal():
    # photo post: no reach/views/plays → unresolved (retried, then aged out)
    assert _metric_actual("reach", {"likes": 10}, 0) is None
    assert _metric_actual("reach", {}, 0) is None


# ── _as_dict: jsonb string vs dict coercion ──

def test_as_dict_passes_dict():
    assert _as_dict({"reach": 5}) == {"reach": 5}


def test_as_dict_parses_json_string():
    assert _as_dict('{"reach": 5}') == {"reach": 5}


def test_as_dict_bad_input_is_empty():
    assert _as_dict(None) == {}
    assert _as_dict("not json") == {}
    assert _as_dict(42) == {}


# ── compute_accuracy_pct: NaN / inf are filtered ──

def test_accuracy_filters_nan_and_inf():
    # a corrupt NaN error must not silently clamp accuracy to 100
    assert compute_accuracy_pct([float("nan"), float("inf")]) is None
    assert compute_accuracy_pct([0.0, float("nan")]) == 100.0
    assert math.isfinite(compute_accuracy_pct([0.2, float("inf")]) or 0.0)

"""Stage 13 — breakout follow-up: pins the pure ranking of which breakout the
autopilot continues (the DB-bound insert is integration-tested in staging)."""
from __future__ import annotations

from app.graphs.nodes.performance_review import _removal_pivot, _top_breakout


def test_none_when_empty():
    assert _top_breakout([]) is None


def test_skips_entries_without_task_id():
    assert _top_breakout([{"metrics": {"reach": 9999}}]) is None


def test_picks_highest_reach():
    out = _top_breakout(
        [
            {"task_id": "a", "metrics": {"reach": 1000}},
            {"task_id": "b", "metrics": {"reach": 8000}},
            {"task_id": "c", "metrics": {"reach": 3000}},
        ]
    )
    assert out is not None
    assert out["task_id"] == "b"


def test_falls_back_to_views_then_likes():
    out = _top_breakout(
        [
            {"task_id": "a", "metrics": {"likes": 50}},
            {"task_id": "b", "metrics": {"views": 7000}},
        ]
    )
    assert out is not None
    assert out["task_id"] == "b"


def test_removal_pivot_none_when_no_negative():
    under = [{"task_id": "a"}, {"task_id": "b"}]
    assert _removal_pivot(under, {"a": 20, "b": 10}) is None


def test_removal_pivot_fires_on_negative_underperformer():
    under = [{"task_id": "a"}, {"task_id": "b"}]
    out = _removal_pivot(under, {"a": 20, "b": 70})
    assert out is not None
    assert "o'chirish" in out


def test_removal_pivot_threshold_boundary():
    assert _removal_pivot([{"task_id": "a"}], {"a": 54}) is None
    assert _removal_pivot([{"task_id": "a"}], {"a": 55}) is not None


def test_removal_pivot_ignores_non_underperformer_sentiment():
    # Only task_ids in the underperformers list count.
    assert _removal_pivot([{"task_id": "a"}], {"b": 90}) is None

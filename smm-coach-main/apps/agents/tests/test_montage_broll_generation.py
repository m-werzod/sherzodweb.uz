"""Faza B cinematic-trigger — broll_curator.mark_generation: opt-in generate marking (pure)."""
from __future__ import annotations

from app.graphs.nodes.broll_curator import mark_generation


def test_disabled_is_passthrough() -> None:
    plan = [{"shot_index": 1, "query": "hands counting cash"}]
    assert mark_generation(plan, False) == plan


def test_enabled_marks_generate_and_keeps_stock_fallback() -> None:
    plan = [
        {"shot_index": 1, "query": "hands counting cash"},
        {"shot_index": 2, "query": "city skyline"},
    ]
    out = mark_generation(plan, True)
    assert out[0]["source"] == "generate"
    assert out[0]["prompt"] == "hands counting cash"
    assert out[0]["query"] == "hands counting cash"  # stock fallback saqlanadi
    assert out[1]["source"] == "generate"
    assert out[1]["prompt"] == "city skyline"


def test_enabled_empty_plan() -> None:
    assert mark_generation([], True) == []

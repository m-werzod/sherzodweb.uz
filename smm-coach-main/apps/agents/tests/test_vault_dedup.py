"""Stage 6 — vault lesson dedup: pins which notes collapse vs stay distinct.
Auto-generated lessons (one per run) must fold into a near-identical existing
lesson; the user's real qa/insight notes must never merge."""
from __future__ import annotations

from app.memory.knowledge_vault import _DEDUP_THRESHOLD, _dedup_target


def test_no_related_returns_none():
    assert _dedup_target([], "lessons_learned") is None


def test_non_lesson_kind_never_dedups():
    related = [{"id": "a", "kind": "qa", "similarity": 0.99}]
    assert _dedup_target(related, "qa") is None


def test_near_identical_lesson_folds():
    related = [{"id": "lesson1", "kind": "lessons_learned", "similarity": 0.96}]
    assert _dedup_target(related, "lessons_learned") == "lesson1"


def test_below_threshold_stays_distinct():
    related = [{"id": "lesson1", "kind": "lessons_learned", "similarity": 0.80}]
    assert _dedup_target(related, "lessons_learned") is None


def test_threshold_boundary_inclusive():
    related = [{"id": "x", "kind": "lessons_learned", "similarity": _DEDUP_THRESHOLD}]
    assert _dedup_target(related, "lessons_learned") == "x"


def test_top_must_match_kind():
    # Most-similar note is a different kind → don't merge a lesson into a qa note.
    related = [{"id": "qa1", "kind": "qa", "similarity": 0.99}]
    assert _dedup_target(related, "lessons_learned") is None


def test_missing_similarity_is_safe():
    related = [{"id": "x", "kind": "lessons_learned"}]
    assert _dedup_target(related, "lessons_learned") is None

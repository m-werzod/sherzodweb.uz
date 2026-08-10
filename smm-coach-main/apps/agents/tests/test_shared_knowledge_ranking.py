"""Cross-cutting — weighted trend signal ('vaznlangan signal'): the effective score
weights raw score by source-confidence (web > llm_seed) and recency (trends decay)."""
from __future__ import annotations

from app.memory.shared_knowledge import _effective_signal_score


def test_fresh_beats_stale_at_equal_score():
    fresh = _effective_signal_score(0.7, "llm_seed", age_days=1)
    stale = _effective_signal_score(0.7, "llm_seed", age_days=40)
    assert fresh > stale


def test_web_source_outranks_seed_at_equal_score_and_age():
    web = _effective_signal_score(0.7, "web_search", age_days=2)
    seed = _effective_signal_score(0.7, "llm_seed", age_days=2)
    assert web > seed


def test_fresh_real_signal_beats_stale_high_seed():
    # A 0.6 web signal from today should beat a 0.8 LLM seed from 40 days ago —
    # the exact inversion raw `score DESC` produced.
    fresh_real = _effective_signal_score(0.6, "web_search", age_days=1)
    stale_seed = _effective_signal_score(0.8, "llm_seed", age_days=40)
    assert fresh_real > stale_seed


def test_decay_has_a_floor():
    # Neutral source isolates the DECAY floor (llm_seed now also carries a source
    # down-weight, which would conflate the two).
    very_old = _effective_signal_score(1.0, None, age_days=999)
    # Floor keeps a strong-but-old signal from collapsing to zero.
    assert very_old >= 0.4


def test_official_graph_outranks_web_and_seed():
    # Official measured Instagram data is the strongest evidence tier.
    graph = _effective_signal_score(0.7, "graph_api", age_days=2)
    web = _effective_signal_score(0.7, "web_search", age_days=2)
    seed = _effective_signal_score(0.7, "llm_seed", age_days=2)
    assert graph > web > seed


def test_fresh_seed_does_not_beat_real_trend():
    # An invented "trend" from today must not outrank a real one a few days old.
    real = _effective_signal_score(0.6, "graph_api", age_days=4)
    invented = _effective_signal_score(0.8, "llm_seed", age_days=0)
    assert real > invented


def test_null_score_uses_neutral_base():
    v = _effective_signal_score(None, "web_search", age_days=0)
    assert v > 0  # neutral 0.5 base × web boost, no crash on NULL

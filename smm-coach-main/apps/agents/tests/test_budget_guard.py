"""Budget guard + pricing: the cost-control safety net. Locks in the two fixes
that make it actually protect spend — (1) a model id missing from PRICES must
NOT cost $0 (that blinded every cap), and (2) EMERGENCY_DISABLE_LLM is a real
hard stop at the client layer (stub, no spend), not just a soft degrade.
"""
from __future__ import annotations

import pytest

from app.integrations.llm.pricing import _FALLBACK_PRICE, cost_usd


def test_cost_usd_known_model() -> None:
    # claude-haiku-4-5 = $1/1M in, $5/1M out.
    assert cost_usd("claude-haiku-4-5", 1_000_000, 1_000_000) == pytest.approx(1.0 + 5.0)


def test_cost_usd_unknown_model_fails_closed_nonzero() -> None:
    # An unconfigured / drifted model id (e.g. a CEREBRAS_MODEL override) MUST be
    # charged the non-zero fallback — a $0 cost makes that spend invisible to the
    # budget caps and the guard never trips on it.
    c = cost_usd("zai-glm-4.7-some-future-tag", 1_000_000, 1_000_000)
    assert c > 0
    assert c == pytest.approx(_FALLBACK_PRICE.input_per_1m + _FALLBACK_PRICE.output_per_1m)


def test_cost_usd_zero_tokens_is_zero() -> None:
    assert cost_usd("claude-haiku-4-5", 0, 0) == 0.0


def test_kill_switch_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.budget import guard

    monkeypatch.delenv("EMERGENCY_DISABLE_LLM", raising=False)
    assert guard.kill_switch_on() is False
    for on in ("1", "true", "yes", "on", "ON", "True"):
        monkeypatch.setenv("EMERGENCY_DISABLE_LLM", on)
        assert guard.kill_switch_on() is True
    for off in ("0", "false", "", "no"):
        monkeypatch.setenv("EMERGENCY_DISABLE_LLM", off)
        assert guard.kill_switch_on() is False


def test_degrade_map_premium_to_cheap_and_passthrough() -> None:
    from app.budget import guard

    assert guard.degrade("claude-opus-4-7") == "claude-haiku-4-5"
    assert guard.degrade("claude-sonnet-4-6") == "claude-haiku-4-5"
    # A model not in the map passes through unchanged (no crash, no loop).
    assert guard.degrade("gpt-oss-120b") == "gpt-oss-120b"


@pytest.mark.asyncio
async def test_call_claude_kill_switch_returns_stub_no_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """EMERGENCY_DISABLE_LLM=1 → call_claude short-circuits to a stub with a
    zero-cost ledger BEFORE any provider call (the real hard stop, regardless of
    which premium model was requested)."""
    monkeypatch.setenv("EMERGENCY_DISABLE_LLM", "1")
    from app.integrations.llm import anthropic_client

    resp, ledger = await anthropic_client.call_claude(
        model="claude-opus-4-7",
        system="x",
        messages=[{"role": "user", "content": "hi"}],
        agent_name="test",
    )
    assert ledger["cost_usd"] == 0.0  # CostLedger is a TypedDict
    assert ledger["input_tokens"] == 0
    assert ledger["output_tokens"] == 0
    assert "stub" in str(resp).lower()


def test_configured_fast_models_are_priced() -> None:
    """The fast path is the highest-volume spend; its CONFIGURED model ids —
    including env overrides like OpenRouter's ':free' tier — MUST be in PRICES,
    else cost_usd hits the fallback and mis-counts every fast call. This is the
    exact invariant the ':free' over-charge regression violated."""
    from app.config import get_settings
    from app.integrations.llm.pricing import PRICES

    s = get_settings()
    assert s.model_fast in PRICES, f"CEREBRAS_MODEL {s.model_fast!r} missing from PRICES"
    assert s.model_fast_openrouter in PRICES, (
        f"OPENROUTER_MODEL {s.model_fast_openrouter!r} missing from PRICES"
    )


@pytest.mark.asyncio
async def test_fast_chat_kill_switch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """fast_chat raises under the kill switch (mirrors no-provider) so its caller
    falls back to the also-stubbed call_claude — net: no spend on the fast path."""
    monkeypatch.setenv("EMERGENCY_DISABLE_LLM", "1")
    from app.integrations.llm import fast_llm

    with pytest.raises(RuntimeError, match="EMERGENCY_DISABLE_LLM"):
        await fast_llm.fast_chat(system="x", user="hi")

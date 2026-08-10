"""Centralized model pricing — USD per 1M tokens."""
from __future__ import annotations

from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Price:
    input_per_1m: float
    output_per_1m: float
    cached_per_1m: float = 0.0


# Pricing snapshot as of 2026-05. Update centrally when providers change.
PRICES: dict[str, Price] = {
    # Anthropic
    "claude-opus-4-7": Price(input_per_1m=5.0, output_per_1m=25.0, cached_per_1m=0.5),
    "claude-sonnet-4-6": Price(input_per_1m=3.0, output_per_1m=15.0, cached_per_1m=0.3),
    "claude-haiku-4-5": Price(input_per_1m=1.0, output_per_1m=5.0, cached_per_1m=0.1),
    # Google
    "gemini-2.5-flash": Price(input_per_1m=0.30, output_per_1m=2.50),
    "gemini-3.1-pro": Price(input_per_1m=2.0, output_per_1m=12.0),
    # OpenAI (gpt-4o-mini priced here so the openai_critic shows real cost)
    "gpt-4o-mini": Price(input_per_1m=0.15, output_per_1m=0.60),
    # Fast LLM (Cerebras + OpenRouter) — these high-volume models were recorded at $0.00,
    # so the AI-spend panel under-reported the bulk of the spend. Approximate public rates.
    "gpt-oss-120b": Price(input_per_1m=0.25, output_per_1m=0.69),
    "meta-llama/llama-3.3-70b-instruct": Price(input_per_1m=0.13, output_per_1m=0.40),
    # The deployed OPENROUTER_MODEL is the ":free" tier (genuinely $0). Listed
    # explicitly so the fail-closed fallback below doesn't over-charge it — a
    # ":free" model is a KNOWN-zero rate, not an unknown id.
    "meta-llama/llama-3.3-70b-instruct:free": Price(input_per_1m=0.0, output_per_1m=0.0),
    "llama-3.3-70b": Price(input_per_1m=0.13, output_per_1m=0.40),
    "zai-glm-4.7": Price(input_per_1m=0.20, output_per_1m=0.60),
    # Embeddings (voyage-3 native 1024-dim)
    "voyage-3": Price(input_per_1m=0.12, output_per_1m=0.0),
    "text-embedding-3-small": Price(input_per_1m=0.02, output_per_1m=0.0),
}


# Fallback rate for a model id NOT in PRICES. MUST be non-zero: a $0 fallback
# made unconfigured / drifted model ids (e.g. a CEREBRAS_MODEL / OPENROUTER_MODEL
# override, or a version-tagged id) record costUsd=0, so that spend was invisible
# to every budget cap and the guard never tripped on it. Deliberately on the high
# side (~Haiku-tier) so an unknown model degrades EARLY rather than spending
# unbounded — set the real rate in PRICES to replace it.
_FALLBACK_PRICE = Price(input_per_1m=1.0, output_per_1m=3.0)
_warned_unknown: set[str] = set()


def cost_usd(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    p = PRICES.get(model)
    if p is None:
        # Fail-CLOSED on cost: a missing rate must not zero out the spend (that
        # blinds the budget guard). Warn once per unknown id, then charge the
        # conservative fallback so the caps still see the spend.
        if model not in _warned_unknown:
            _warned_unknown.add(model)
            log.warning(
                "pricing.unknown_model_fallback",
                model=model,
                fallback_input_per_1m=_FALLBACK_PRICE.input_per_1m,
                fallback_output_per_1m=_FALLBACK_PRICE.output_per_1m,
            )
        p = _FALLBACK_PRICE
    return (
        input_tokens * p.input_per_1m / 1_000_000
        + output_tokens * p.output_per_1m / 1_000_000
        + cached_tokens * p.cached_per_1m / 1_000_000
    )

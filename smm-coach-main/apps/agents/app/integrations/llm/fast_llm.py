"""Fast OpenAI-compatible LLM — Cerebras (primary) / OpenRouter (alternate).

Cerebras serves Llama 3.3 70B / Qwen at very high speed and low cost — ideal for
the high-volume agent tasks (task scoring, enrichment, market/industry synthesis,
account-tracker root-cause). OpenRouter (one key, many models) is the alternate.

Both speak the OpenAI chat-completions API, so this is a thin wrapper. Every call
is persisted to the AI Inspector via record_llm_call (CLAUDE.md rule). Raises on
error so callers can fall back to Claude Haiku.
"""
from __future__ import annotations

import contextlib
import os
import time
from typing import Any

import httpx
import structlog

from app.budget.guard import kill_switch_on
from app.config import get_settings
from app.graphs.state import CostLedger
from app.integrations.llm.pricing import cost_usd
from app.runs.context import current as current_run
from app.runs.llm_inspector import record_llm_call
from app.runs.repository import record_token_usage

log = structlog.get_logger(__name__)

CEREBRAS_API = "https://api.cerebras.ai/v1"
OPENROUTER_API = "https://openrouter.ai/api/v1"

# One provider: (base_url, api_key, default_model, provider_name).
_Provider = tuple[str, str, str, str]


def _providers() -> list[_Provider]:
    """All configured fast providers, in the order we should try them.

    Both speak the OpenAI chat-completions API. We try each in turn and fall
    through to the next on ANY error (billing cap, rate limit, 5xx) — so a dead
    Cerebras key no longer drops us straight to expensive Haiku while a working
    OpenRouter key sits unused. Order is overridable via LLM_FAST_PROVIDER
    (`openrouter` or `cerebras`); default is Cerebras → OpenRouter.
    """
    s = get_settings()
    ck = getattr(s, "cerebras_api_key", None)
    ok = getattr(s, "openrouter_api_key", None)
    cerebras: _Provider | None = (
        (CEREBRAS_API, ck.get_secret_value(), s.model_fast, "cerebras") if ck is not None else None
    )
    openrouter: _Provider | None = (
        (OPENROUTER_API, ok.get_secret_value(), s.model_fast_openrouter, "openrouter")
        if ok is not None
        else None
    )

    pref = os.getenv("LLM_FAST_PROVIDER", "").strip().lower()
    ordered = [openrouter, cerebras] if pref == "openrouter" else [cerebras, openrouter]
    return [p for p in ordered if p is not None]


def is_configured() -> bool:
    return len(_providers()) > 0


async def fast_chat(
    *,
    system: str,
    user: str,
    json: bool = False,
    max_tokens: int = 800,
    temperature: float = 0.3,
    model: str = "",
    agent_name: str = "fast_llm",
) -> str:
    """Chat completion via the fast OpenAI-compatible providers, tried in order.

    Returns the text. Raises only if EVERY configured provider failed — the
    caller (groq_client) then falls back to Claude Haiku.
    """
    # HARD kill switch: raise like a no-provider failure so the caller falls back
    # to call_claude (which is also kill-switch-stubbed) — net: no spend anywhere.
    if kill_switch_on():
        raise RuntimeError("fast_llm: EMERGENCY_DISABLE_LLM")
    provs = _providers()
    if not provs:
        raise RuntimeError("fast_llm: no provider (set CEREBRAS_API_KEY or OPENROUTER_API_KEY)")

    last_exc: Exception | None = None
    for base, key, default_model, pname in provs:
        try:
            return await _call_one(
                base=base,
                key=key,
                # A caller-supplied `model` is usually a provider-specific id
                # (e.g. Groq's "llama-3.3-70b-versatile") that won't resolve on
                # Cerebras/OpenRouter — prefer each provider's own default.
                use_model=default_model,
                pname=pname,
                system=system,
                user=user,
                json=json,
                max_tokens=max_tokens,
                temperature=temperature,
                agent_name=agent_name,
            )
        except Exception as exc:  # noqa: BLE001 — try the next provider
            last_exc = exc
            log.warning("fast_llm.provider_failed", provider=pname, error=str(exc)[:200])

    assert last_exc is not None
    raise last_exc


async def _call_one(
    *,
    base: str,
    key: str,
    use_model: str,
    pname: str,
    system: str,
    user: str,
    json: bool,
    max_tokens: int,
    temperature: float,
    agent_name: str,
) -> str:
    body: dict[str, Any] = {
        "model": use_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json:
        body["response_format"] = {"type": "json_object"}

    started = time.monotonic()
    text, in_tok, out_tok = "", 0, 0
    status, err = "ok", None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
        if resp.status_code >= 400:
            status, err = "error", f"{resp.status_code}: {resp.text[:300]}"
            raise RuntimeError(f"fast_llm {pname} {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        return text
    except Exception as exc:  # noqa: BLE001
        if status == "ok":
            status, err = "error", str(exc)[:300]
        raise
    finally:
        # Was always 0 → the AI-spend panel + budget guard under-reported the high-volume fast calls.
        _cost = cost_usd(use_model, in_tok, out_tok)
        with contextlib.suppress(Exception):
            await record_llm_call(
                agent=agent_name,
                provider=pname,
                model=use_model,
                system_prompt=system,
                user_message=user,
                response_text=text,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=_cost,
                latency_ms=int((time.monotonic() - started) * 1000),
                status=status,
                error_message=err,
            )
        # record_llm_call writes ONLY llm_calls (the Inspector); the spend panel + budget guard read
        # token_usage. The anthropic/openai clients write both — fast_llm only wrote llm_calls, so the
        # cerebras/openrouter spend was invisible. Mirror it into token_usage too.
        _ctx = current_run()
        if _ctx is not None:
            with contextlib.suppress(Exception):
                await record_token_usage(
                    tenant_id=_ctx.tenant_id,
                    run_id=_ctx.run_id,
                    agent=agent_name,
                    provider=pname,
                    model=use_model,
                    cost=CostLedger(
                        input_tokens=in_tok, output_tokens=out_tok, cached_tokens=0, cost_usd=_cost
                    ),
                )

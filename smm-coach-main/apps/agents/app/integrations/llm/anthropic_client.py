"""Thin Anthropic wrapper that:
- emits a unified (response, cost) tuple
- supports prompt caching declaratively
- enforces JSON output when asked
- writes a TokenUsage row per call (attributed via RunContext)
- retries on transient errors with exponential backoff
- automatically degrades to Haiku when the tenant's monthly budget is exhausted
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

import structlog
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    BadRequestError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.budget.guard import DEGRADE_MAP, degrade as degrade_model, kill_switch_on, over_cap
from app.config import get_settings
from app.graphs.state import CostLedger
from app.integrations.llm.pricing import cost_usd
from app.runs.context import current as current_run
from app.runs.llm_inspector import record_llm_call
from app.runs.repository import record_token_usage
from app.streams.bus import publish

log = structlog.get_logger(__name__)

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        key = get_settings().anthropic_api_key
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        # 60s isn't enough for Opus generating a multi-thousand-token JSON
        # roadmap. The SDK then exponentially retries on APITimeoutError,
        # which compounds the latency rather than helping. Bump to 4 minutes;
        # that's long enough for Opus 4.7's longest typical output and well
        # under any reasonable user patience for a one-shot onboarding call.
        _client = AsyncAnthropic(api_key=key.get_secret_value(), timeout=240.0)
    return _client


def _should_retry(exc: BaseException) -> bool:
    """Retry transient errors only. Skip 400 BadRequest (quota / invalid
    request) because retrying won't change the outcome and just delays the
    Gemini fallback."""
    if isinstance(exc, BadRequestError):
        return False
    return isinstance(
        exc, (RateLimitError, APIConnectionError, APITimeoutError, APIStatusError)
    )


@retry(
    retry=retry_if_exception(_should_retry),
    wait=wait_exponential_jitter(initial=2, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _create_message(**kwargs: Any) -> Any:
    return await _get_client().messages.create(**kwargs)


async def call_claude(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 2000,
    response_format: Literal["text", "json"] = "text",
    prompt_cache: dict[str, Any] | None = None,
    agent_name: str = "unknown",
) -> tuple[dict[str, Any], CostLedger]:
    """Returns (response_dict, cost_ledger). Stub mode when no key configured.

    Provider routing:
      1. If `ANTHROPIC_API_KEY` is set → try Claude.
      2. On account-level usage-limit error (e.g. monthly spend cap), fall
         back to Gemini 2.5 Flash transparently — same prompt, same shape.
      3. If Anthropic key is missing AND Gemini key is set → go straight
         to Gemini.
      4. If both are missing → stub.
    Lets the agent loop keep running when one provider is throttled. The
    UI sees a normal response; only the `model` field of the response
    changes (e.g. `gemini-2.5-flash` instead of the requested Claude model).
    """
    settings = get_settings()
    # HARD kill switch (EMERGENCY_DISABLE_LLM): short-circuit to a stub BEFORE any
    # provider call — NO spend on any model/provider. Distinct from over_cap's
    # soft degrade (which still runs a cheaper model). Reuses the no-key stub path.
    if kill_switch_on():
        log.warning("anthropic.kill_switch — EMERGENCY_DISABLE_LLM on, stub (no spend)", agent=agent_name)
        return _stub_response(response_format), CostLedger(
            input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0
        )
    if not settings.anthropic_api_key:
        if settings.gemini_api_key:
            log.info("anthropic.no_key → falling back to Gemini", agent=agent_name)
            return await _via_gemini(system, messages, response_format, agent_name)
        log.warning("anthropic.no_key — returning stub response")
        return _stub_response(response_format), CostLedger(
            input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0
        )

    ctx = current_run()
    # Budget guard: if tenant is over the monthly cap and we were about to use
    # a premium model, swap to Haiku and notify the UI.
    effective_model = model
    if ctx and model in DEGRADE_MAP and await over_cap(ctx.tenant_id):
        effective_model = degrade_model(model)
        log.warning(
            "anthropic.budget_degrade",
            tenant_id=ctx.tenant_id,
            from_model=model,
            to_model=effective_model,
        )
        try:
            await publish(
                ctx.user_id or "system",
                {
                    "type": "budget.exceeded",
                    "runId": ctx.run_id,
                    "spentUsd": settings.tenant_monthly_budget_usd,
                    "capUsd": settings.tenant_monthly_budget_usd,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:  # noqa: BLE001
            log.exception("anthropic.budget_publish_failed")

    system_blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": system,
            **(
                {"cache_control": {"type": "ephemeral"}}
                if prompt_cache and prompt_cache.get("system")
                else {}
            ),
        }
    ]

    # Claude 4.x rejects assistant-message prefill ("the conversation must
    # end with a user message"). We force JSON output by injecting an
    # explicit instruction in the LAST user message instead — works across
    # all model versions.
    formatted_messages = list(messages)
    if response_format == "json" and formatted_messages:
        last = formatted_messages[-1]
        if last.get("role") == "user":
            extra = (
                "\n\nFAQAT VA FAQAT yagona JSON ob'ekt qaytar. "
                "Markdown ```json ``` bloklarisiz, izohlarsiz, prefixsiz. "
                "Birinchi belgi '{' bo'lsin, oxirgisi '}'."
            )
            existing = last.get("content")
            if isinstance(existing, str):
                last["content"] = existing + extra
            elif isinstance(existing, list):
                last["content"] = existing + [{"type": "text", "text": extra}]

    import time as _t
    started_at = _t.monotonic()
    try:
        resp = await _create_message(
            model=effective_model,
            system=system_blocks,
            messages=formatted_messages,
            max_tokens=max_tokens,
        )
    except BadRequestError as exc:
        # Workspace-level monthly spend cap reached → reroute to Gemini Flash
        # so the agent loop doesn't stall. The fallback uses the same prompt
        # text and emits a single token-usage row attributed to "gemini".
        if "usage limits" in str(exc).lower() and settings.gemini_api_key:
            log.warning(
                "anthropic.usage_limit — falling back to Gemini",
                agent=agent_name,
                from_model=effective_model,
            )
            await record_llm_call(
                agent=agent_name, provider="anthropic", model=effective_model,
                system_prompt=system, user_message=formatted_messages, response_text="",
                latency_ms=int((_t.monotonic() - started_at) * 1000),
                status="degraded", error_message="usage_limit → fallback gemini",
            )
            return await _via_gemini(system, formatted_messages, response_format, agent_name)
        await record_llm_call(
            agent=agent_name, provider="anthropic", model=effective_model,
            system_prompt=system, user_message=formatted_messages, response_text="",
            latency_ms=int((_t.monotonic() - started_at) * 1000),
            status="error", error_message=str(exc)[:500],
        )
        raise
    text_out = "".join(b.text for b in resp.content if hasattr(b, "text"))
    if response_format == "json":
        text_out = _extract_json(text_out)

    usage = resp.usage
    in_tok = getattr(usage, "input_tokens", 0)
    out_tok = getattr(usage, "output_tokens", 0)
    cache_tok = getattr(usage, "cache_read_input_tokens", 0) or 0
    cost = cost_usd(effective_model, in_tok, out_tok, cache_tok)
    latency_ms = int((_t.monotonic() - started_at) * 1000)

    ledger = CostLedger(
        input_tokens=in_tok,
        output_tokens=out_tok,
        cached_tokens=cache_tok,
        cost_usd=cost,
    )

    if ctx is not None:
        try:
            await record_token_usage(
                tenant_id=ctx.tenant_id,
                run_id=ctx.run_id,
                agent=agent_name,
                provider="anthropic",
                model=effective_model,
                cost=ledger,
            )
        except Exception:  # noqa: BLE001
            log.exception("anthropic.token_usage_write_failed")

    # AI Inspector — persist full prompt + response for the in-app drawer.
    await record_llm_call(
        agent=agent_name,
        provider="anthropic",
        model=effective_model,
        system_prompt=system,
        user_message=formatted_messages,
        response_text=text_out,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cached_tokens=cache_tok,
        cost_usd=cost,
        latency_ms=latency_ms,
        status="ok" if effective_model == model else "degraded",
    )

    return ({"text": text_out, "raw": resp.model_dump(), "model": effective_model}, ledger)


def _stub_response(fmt: Literal["text", "json"]) -> dict[str, Any]:
    if fmt == "json":
        return {"text": json.dumps({"stub": True, "tasks": []}), "raw": {}}
    return {"text": "[stub response — set ANTHROPIC_API_KEY]", "raw": {}}


async def _via_gemini(
    system: str,
    messages: list[dict],
    response_format: Literal["text", "json"],
    agent_name: str,
) -> tuple[dict[str, Any], CostLedger]:
    """Fallback path: re-shape a Claude-style (system + messages) call into
    Gemini's flatter API. We concatenate every user/assistant message into a
    single user_text and pass `system` as Gemini's system_instruction.
    """
    # Import lazily so anthropic_client.py doesn't always pay the SDK cost.
    from app.integrations.llm.gemini_client import call_gemini

    # Flatten the conversation into a single user-role prompt. Assistant turns
    # become "(Previously you said: ...)" so context isn't lost.
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict) and "text" in p
            )
        content = content or ""
        if role == "assistant":
            parts.append(f"(Previously: {content})")
        else:
            parts.append(content)
    user_text = "\n\n".join(parts).strip()

    # Force JSON if the original call requested it.
    if response_format == "json":
        user_text += (
            "\n\nFAQAT VA FAQAT yagona JSON ob'ekt qaytar. Markdown bloklarsiz, "
            "izohlarsiz, prefixsiz. Birinchi belgi '{' bo'lsin, oxirgisi '}'."
        )

    text_out, ledger = await call_gemini(
        model=get_settings().model_market_analyst,  # gemini-2.5-flash
        system=system,
        user_text=user_text,
        # Flash supports 64k output. We bump well past 8k because Gemini
        # counts hidden "thinking" tokens against this budget — at 8k it
        # routinely truncates a 12-task roadmap mid-object.
        max_output_tokens=32768,
        agent_name=agent_name,
        response_format=response_format,
    )
    if response_format == "json":
        text_out = _extract_json(text_out)
    return (
        {
            "text": text_out,
            "raw": {"provider": "gemini-fallback", "model": "gemini-2.5-flash"},
            "model": "gemini-2.5-flash",
        },
        ledger,
    )


def _extract_json(text: str) -> str:
    """Pull a single JSON object out of model output.

    Claude sometimes wraps JSON in ```json ... ``` blocks or prefixes it
    with explanation prose, even with strict instructions. We accept either
    and return only the `{...}` substring so `json.loads` succeeds.
    """
    s = text.strip()
    # Strip code fences
    if s.startswith("```"):
        # ```json\n{...}\n``` or ```\n{...}\n```
        end = s.find("```", 3)
        if end > 0:
            inner = s[3:end]
            # Drop the first line which is usually `json` or empty
            nl = inner.find("\n")
            if nl >= 0:
                inner = inner[nl + 1 :]
            s = inner.strip()
    # If there's still prose before the JSON, slice from first `{` to last `}`
    open_idx = s.find("{")
    close_idx = s.rfind("}")
    if open_idx >= 0 and close_idx > open_idx:
        return s[open_idx : close_idx + 1]
    return s

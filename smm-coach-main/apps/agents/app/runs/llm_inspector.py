"""Persists every LLM call (prompt + response + tokens + latency) so the
in-app AI Inspector UI can show users exactly what each model received and
returned. Separate from TokenUsage (aggregates) — this table stores raw
payloads.

Single entry point: ``record_llm_call(...)`` is invoked by every LLM client
(anthropic, openai, groq, gemini) at the end of a successful (or failed)
call. Fire-and-forget — never blocks the agent if persistence trips.

The runs.context.current() helper provides the tenant_id / run_id /
task_id automatically, so callers only need to pass the per-call fields.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.memory.db import get_sessionmaker
from app.runs.context import current as current_run

log = structlog.get_logger(__name__)

# Soft cap on text fields. Postgres TEXT has no hard limit, but a runaway
# prompt (e.g. 1M-token Gemini call) would bloat the table. 100K chars is
# plenty for our use cases — long roadmap_generator system prompts are
# ~5K, full responses ~20K.
_MAX_TEXT = 100_000


def _truncate(s: str | None) -> str:
    if not s:
        return ""
    if len(s) > _MAX_TEXT:
        return s[: _MAX_TEXT - 200] + f"\n\n... [truncated · original {len(s)} chars]"
    return s


async def record_llm_call(
    *,
    agent: str,
    provider: str,
    model: str,
    system_prompt: str,
    user_message: Any,
    response_text: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    status: str = "ok",
    error_message: str | None = None,
) -> None:
    """Persist a single LLM call. Never raises — fire-and-forget."""
    # Live Telegram feed: the real Q&A — which agent, what was asked, and how
    # the model answered (truncated to fit Telegram's 4096-char limit).
    try:
        if isinstance(user_message, (list, dict)):
            _ask = json.dumps(user_message, ensure_ascii=False)
        else:
            _ask = str(user_message or "")
        _ask = " ".join(_ask.split())[:700]
        _ans = " ".join((response_text or "").split())[:2200]
        if status == "ok":
            telegram.send(
                f"🧠 {agent} · {provider}/{model} · "
                f"{int(input_tokens or 0)}+{int(output_tokens or 0)} tok · ${float(cost_usd or 0.0):.4f}\n"
                f"❓ SO'ROV: {_ask}\n"
                f"💬 JAVOB: {_ans}"
            )
        else:
            telegram.send(
                f"⚠️ {agent} · {provider}/{model} — XATO\n"
                f"❓ SO'ROV: {_ask}\n"
                f"❌ {(error_message or '')[:500]}"
            )
    except Exception:  # noqa: BLE001
        pass
    ctx = current_run()
    if ctx is None:
        # No run context (e.g. background script) — skip persistence.
        return
    # Stringify user_message — it's usually a list of {role, content} dicts.
    if isinstance(user_message, (list, dict)):
        user_text = json.dumps(user_message, ensure_ascii=False)
    else:
        user_text = str(user_message) if user_message is not None else ""

    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO llm_calls
                      (id, "tenantId", "runId", "taskId", agent, provider, model,
                       "systemPrompt", "userMessage", "responseText",
                       "inputTokens", "outputTokens", "cachedTokens",
                       "costUsd", "latencyMs", status, "errorMessage", "createdAt")
                    VALUES
                      (:id, :tid, :rid, :task_id, :agent, :provider, :model,
                       :sys, :usr, :resp,
                       :in_tok, :out_tok, :cache_tok,
                       :cost, :latency, :status, :err, NOW())
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "tid": ctx.tenant_id,
                    "rid": ctx.run_id,
                    "task_id": getattr(ctx, "task_id", None),
                    "agent": agent[:80],
                    "provider": provider[:40],
                    "model": model[:80],
                    "sys": _truncate(system_prompt),
                    "usr": _truncate(user_text),
                    "resp": _truncate(response_text),
                    "in_tok": int(input_tokens or 0),
                    "out_tok": int(output_tokens or 0),
                    "cache_tok": int(cached_tokens or 0),
                    "cost": float(cost_usd or 0.0),
                    "latency": int(latency_ms or 0),
                    "status": status,
                    "err": _truncate(error_message) if error_message else None,
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        # Inspector persistence MUST NOT break the agent loop. If the DB is
        # down or the row trips a constraint, log + swallow.
        log.exception("llm_inspector.persist_failed", agent=agent, provider=provider)

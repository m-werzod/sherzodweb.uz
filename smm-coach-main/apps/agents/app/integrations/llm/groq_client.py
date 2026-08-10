"""Fast JSON / text LLM helper.

Routes the high-volume agent tasks (task scorer, enricher, knowledge seeder,
account tracker, market/industry synthesis) to the fastest available provider:
**Cerebras** (Llama 3.3 70B, very high tok/s) or **OpenRouter** when set, with
**Claude Haiku** as the reliability fallback (no fast provider, or a transient
error / unparseable JSON). The module + function names are kept so the many call
sites don't need to change.

Every call is persisted to llm_calls for the AI Inspector + Telegram (both
fast_llm and call_claude record).
"""
from __future__ import annotations

import json
import os
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# Fast, cheap, reliable model for these strategy-grader / fill tasks.
_FAST_MODEL = "claude-haiku-4-5"


def _model() -> str:
    """Model for the fast JSON/text tasks (override via env)."""
    return os.getenv("CHAT_JSON_MODEL") or _FAST_MODEL


def is_configured() -> bool:
    from app.config import get_settings

    s = get_settings()
    # Usable as long as EITHER provider is set — call_claude falls back to
    # Gemini when no Anthropic key is present.
    return getattr(s, "anthropic_api_key", None) is not None or s.gemini_api_key is not None


def _parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Strip stray markdown fences if the model added them.
        return json.loads(text.strip().lstrip("`").lstrip("json").rstrip("`").strip())


async def chat_json(
    *,
    model: str = "",  # accepted for call-site compatibility; ignored
    system: str,
    user: str,
    max_tokens: int = 800,
    temperature: float = 0.2,  # noqa: ARG001 — kept for call-site compatibility
    agent_name: str = "unknown",
) -> dict[str, Any]:
    """Forced-JSON completion. Prefers Cerebras/OpenRouter (fast + cheap); falls
    back to Claude Haiku for reliability if no fast provider is set or it errors."""
    from app.integrations.llm import fast_llm

    if fast_llm.is_configured():
        try:
            text = await fast_llm.fast_chat(
                system=system, user=user, json=True, max_tokens=max_tokens, agent_name=agent_name
            )
            return _parse_json(text or "{}")
        except Exception as exc:  # noqa: BLE001
            log.warning("fast_llm.json_failed_fallback_haiku", error=repr(exc))

    from app.integrations.llm.anthropic_client import call_claude

    resp, _ledger = await call_claude(
        model=_model(),
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
        response_format="json",
        agent_name=agent_name,
    )
    return _parse_json(resp.get("text") or "{}")


async def chat_text(
    *,
    model: str = "",  # accepted for compatibility; ignored
    system: str,
    user: str,
    max_tokens: int = 800,
    temperature: float = 0.4,  # noqa: ARG001 — kept for call-site compatibility
) -> str:
    """Plain-text completion. Prefers Cerebras/OpenRouter; falls back to Haiku."""
    from app.integrations.llm import fast_llm

    if fast_llm.is_configured():
        try:
            return await fast_llm.fast_chat(
                system=system, user=user, max_tokens=max_tokens, agent_name="chat_text"
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("fast_llm.text_failed_fallback_haiku", error=repr(exc))

    from app.integrations.llm.anthropic_client import call_claude

    resp, _ledger = await call_claude(
        model=_model(),
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
        response_format="text",
        agent_name="chat_text",
    )
    return resp.get("text") or ""

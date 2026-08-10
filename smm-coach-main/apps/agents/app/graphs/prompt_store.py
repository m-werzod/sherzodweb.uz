"""Runtime prompt overrides.

Each agent's system prompt is a module-level constant (the code default).
The admin panel can override any of them at runtime: the override lives in
the `prompt_overrides` table (written by the web app behind the admin guard).

`resolve_prompt(key, default)` returns the enabled override when present, else
the code default. Results are TTL-cached so the hot LLM path doesn't hit the DB
on every call. The web app calls the agents' `/v1/admin/prompt-cache` purge
endpoint after an edit so changes take effect within the TTL at worst.
"""
from __future__ import annotations

import asyncio
import time

import structlog
from sqlalchemy import text

from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

_TTL_SEC = 30.0
# key -> (expiry_ts, override_content_or_None)
_cache: dict[str, tuple[float, str | None]] = {}
_lock = asyncio.Lock()


async def resolve_prompt(agent_key: str, default: str) -> str:
    """Return the active system prompt for `agent_key` — override if one is
    enabled, otherwise `default`. Never raises: a DB hiccup falls back to the
    code default so generation never breaks because of the admin layer.
    """
    now = time.time()
    async with _lock:
        hit = _cache.get(agent_key)
        if hit and now < hit[0]:
            return hit[1] or default

    content: str | None = None
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = (
                await session.execute(
                    text(
                        'SELECT content FROM prompt_overrides '
                        'WHERE "agentKey" = :k AND enabled = true'
                    ),
                    {"k": agent_key},
                )
            ).first()
            if row and row[0]:
                content = str(row[0])
    except Exception:  # noqa: BLE001
        log.exception("prompt_store.lookup_failed", agent_key=agent_key)
        content = None

    async with _lock:
        _cache[agent_key] = (now + _TTL_SEC, content)
    return content or default


def invalidate(agent_key: str | None = None) -> None:
    """Drop cached override(s). Called after an admin edit."""
    if agent_key is None:
        _cache.clear()
    else:
        _cache.pop(agent_key, None)

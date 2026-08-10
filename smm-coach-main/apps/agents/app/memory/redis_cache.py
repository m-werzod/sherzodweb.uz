"""Tiny JSON cache over Redis — fail-soft on every path.

Used for expensive scrape results (Virale competitor grids) that must NOT be
recomputed on every page view. Redis down / unset → cache misses and the
caller recomputes; a cache failure must never take a request down with it.
Kept separate from streams.bus (pub/sub) so cache TTL semantics don't leak
into the SSE fan-out client.
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis_async
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_pool: redis_async.Redis | None = None


def _client() -> redis_async.Redis:
    global _pool
    if _pool is None:
        _pool = redis_async.from_url(
            get_settings().redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _pool


async def get_json(key: str) -> Any | None:
    try:
        raw = await _client().get(key)
    except Exception as exc:  # noqa: BLE001 — cache miss on any Redis failure
        log.warning("redis_cache.get_failed", key=key, error=repr(exc)[:120])
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("redis_cache.bad_payload", key=key)
        return None


async def set_json(key: str, value: Any, *, ttl_seconds: int) -> None:
    try:
        payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        await _client().set(key, payload, ex=ttl_seconds)
    except Exception as exc:  # noqa: BLE001 — best-effort write
        log.warning("redis_cache.set_failed", key=key, error=repr(exc)[:120])


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None

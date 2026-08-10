"""Redis pub/sub fan-out for SSE."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

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


def _channel(user_id: str) -> str:
    return f"user:{user_id}:agent-events"


async def publish(user_id: str, event: dict[str, Any]) -> None:
    """Fire-and-forget SSE publish. Logs and swallows failures — SSE is a
    nice-to-have signal, never a critical path. The agent workflow must keep
    running if Redis blips or isn't available (dev / tests)."""
    payload = json.dumps(event, separators=(",", ":"))
    try:
        await _client().publish(_channel(user_id), payload)
    except Exception as exc:  # noqa: BLE001
        log.warning("bus.publish_failed", error=repr(exc), event_type=event.get("type"))


async def subscribe(user_id: str) -> AsyncIterator[dict[str, Any]]:
    pubsub = _client().pubsub()
    await pubsub.subscribe(_channel(user_id))
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
            if msg is None:
                # Keep the connection alive — browsers/proxies drop idle SSE
                yield {"type": "ping", "at": _now()}
                continue
            try:
                yield json.loads(msg["data"])
            except json.JSONDecodeError:
                log.warning("sse.bad_payload", raw=msg.get("data"))
    finally:
        await pubsub.unsubscribe(_channel(user_id))
        await pubsub.close()


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None

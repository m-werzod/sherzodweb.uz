"""Postgres advisory-lock gate so a periodic cron worker runs on at most ONE
replica per tick — the piece the agents.Dockerfile comment promised ("Scale out
later via an advisory-lock gate"). Without it, a second brain replica (or a
rolling-deploy overlap of old+new containers) re-runs every tenant's pulse /
snapshot → doubled LLM spend + duplicate rows.

`pg_try_advisory_lock` is non-blocking and session-scoped: the lock auto-releases
when this connection drops, so a dead leader frees it for another replica's next
tick. We hold it on a dedicated connection for the duration of `work`.
"""
from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text

from app.memory.db import get_sessionmaker

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = structlog.get_logger(__name__)


def lock_key(name: str) -> int:
    """Stable 32-bit signed int key for pg_try_advisory_lock(bigint)."""
    return zlib.crc32(name.encode()) - 2**31


async def run_as_singleton(name: str, work: Callable[[], Awaitable[None]]) -> bool:
    """Run ``work()`` only if this replica can acquire the advisory lock ``name``
    (i.e. no other replica is running this job right now). Returns True if it ran,
    False if another replica holds the lock and it was skipped."""
    key = lock_key(name)
    sm = get_sessionmaker()
    async with sm() as session:
        got = (await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})).scalar()
        if not got:
            log.info("singleton.skip", job=name)
            return False
        try:
            await work()
        finally:
            await session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
            await session.commit()
        return True

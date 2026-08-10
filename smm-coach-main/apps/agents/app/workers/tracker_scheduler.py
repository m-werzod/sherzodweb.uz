"""Periodic worker: every 6 hours, runs the `tracker_pulse` workflow for each
active tenant. The Account Tracker agent then refreshes metrics for tasks
that have been published in the last 14 days.

Started by the FastAPI app on boot (in production) or run standalone:
    uv run python -m app.workers.tracker_scheduler
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from app.graphs.dispatcher import dispatch_workflow
from app.integrations import telegram
from app.memory.db import get_sessionmaker
from app.workers._singleton import run_as_singleton

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours


async def _enqueue_pulses() -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT DISTINCT t.id AS tenant_id, u.id AS user_id
                FROM tenants t
                JOIN users u ON u."tenantId" = t.id
                WHERE EXISTS (
                  SELECT 1 FROM content_tasks ct
                  WHERE ct."tenantId" = t.id
                    AND ct.status = 'published'
                    AND ct."publishedAt" > NOW() - INTERVAL '14 days'
                )
                """
            )
        )
        tenants = rows.mappings().all()

    log.info("tracker.pulse_batch", count=len(tenants))
    if tenants:
        telegram.send(f"⏰ Tracker scheduler · {len(tenants)} tenant uchun tracker_pulse ishga tushirildi")
    # Deterministic idempotency key per tenant per 6h grid window: two agents
    # replicas — or a rolling-deploy overlap of the old + new container — ticking
    # in the same window produce the SAME run id, so the dispatcher short-circuits
    # the duplicate (fetch_run by id) instead of double-running every tenant's
    # pulse and doubling the LLM spend.
    window = int(datetime.now(UTC).timestamp() // INTERVAL_SECONDS)
    for row in tenants:
        await dispatch_workflow(
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            workflow="tracker_pulse",
            thread_id=None,
            payload={"triggeredAt": datetime.now(UTC).isoformat()},
            idempotency_key=f"tracker-pulse:{row['tenant_id']}:{window}",
        )


async def loop_forever() -> None:
    log.info("tracker.scheduler.start", interval_seconds=INTERVAL_SECONDS)
    while True:
        try:
            # Singleton gate: only one replica enqueues the batch per tick (the
            # deterministic idempotency key already dedups dispatch, but this
            # avoids the wasted fan-out entirely).
            await run_as_singleton("tracker_scheduler", _enqueue_pulses)
        except Exception:  # noqa: BLE001
            log.exception("tracker.pulse_batch_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

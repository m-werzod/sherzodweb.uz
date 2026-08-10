"""Periodic worker: once a day, runs the `comment_sentinel_pulse` workflow for
each tenant with recently-published posts. The Comment Sentinel agent then
re-reads each post's comments → refreshes sentiment, raises negative-wave
alerts, AND (Stage 12) detects sales-intent leads with drafted replies.

Without this, comment sentiment + lead detection only ever fired off the IG
webhook (~24h post-publish). A daily sweep means leads/sentiment stay fresh
even when the webhook is absent or a comment lands days later — and the
lead/alert upserts dedupe, so the overlap with the webhook path is harmless.

Daily cadence (not the tracker's 6h) because re-running the LLM over a 14-day
window of posts every 6h is wasteful; comments accrue slowly.

Started by the FastAPI app on boot when RUN_WORKERS=1 (brain plane), or:
    uv run python -m app.workers.comment_sentinel_scheduler
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

INTERVAL_SECONDS = 24 * 60 * 60  # daily


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
                    AND ct."instagramPostId" IS NOT NULL
                    AND ct."instagramPostId" <> ''
                    AND ct."publishedAt" > NOW() - INTERVAL '14 days'
                )
                """
            )
        )
        tenants = rows.mappings().all()

    log.info("comment_sentinel.pulse_batch", count=len(tenants))
    if tenants:
        telegram.send(
            f"💬 Comment scheduler · {len(tenants)} tenant uchun comment_sentinel_pulse ishga tushirildi"
        )
    # Deterministic per-tenant idempotency key on a daily grid window — replica
    # overlap / rolling-deploy double-tick produces the SAME run id, so the
    # dispatcher short-circuits the duplicate instead of double-spending LLM.
    window = int(datetime.now(UTC).timestamp() // INTERVAL_SECONDS)
    for row in tenants:
        await dispatch_workflow(
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            workflow="comment_sentinel_pulse",
            thread_id=None,
            payload={"triggeredAt": datetime.now(UTC).isoformat()},
            idempotency_key=f"comment-sentinel-pulse:{row['tenant_id']}:{window}",
        )


async def loop_forever() -> None:
    log.info("comment_sentinel.scheduler.start", interval_seconds=INTERVAL_SECONDS)
    while True:
        try:
            await run_as_singleton("comment_sentinel_scheduler", _enqueue_pulses)
        except Exception:  # noqa: BLE001
            log.exception("comment_sentinel.pulse_batch_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

"""autoqueue_scheduler — Stage 11 cadence auto-queue trigger.

The auto-queue logic lives in the web service (best-time + ScheduledPost), so
this worker is a thin trigger: hourly it POSTs the web's /api/cron/autoqueue,
which (for tenants that opted into autoSchedule) tops up scheduled posts toward
their cadence using finalized tasks + AI best-time slots. Needs WEB_URL +
CRON_SECRET env; a no-op (logs once) when unconfigured. Opt-in via RUN_WORKERS=1.

Hourly (not 60s like publish_scheduler) because cadence is weekly — an hourly
top-up is plenty and keeps the cost trivial. Standalone:
    uv run python -m app.workers.autoqueue_scheduler
"""
from __future__ import annotations

import asyncio
import os

import httpx
import structlog

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 60 * 60  # hourly


async def _tick() -> None:
    web = (os.getenv("WEB_URL") or "").rstrip("/")
    secret = os.getenv("CRON_SECRET") or os.getenv("AGENTS_HMAC_SECRET") or ""
    if not web or not secret:
        return  # scheduling not configured on this deployment
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{web}/api/cron/autoqueue", headers={"x-cron-secret": secret}
        )
        if r.status_code != 200:
            log.warning("autoqueue_scheduler.http", status=r.status_code)
            return
        data = r.json()
        if data.get("scheduled"):
            log.info(
                "autoqueue_scheduler.tick",
                scheduled=data.get("scheduled"),
                tenants_touched=data.get("tenantsTouched"),
            )


async def loop_forever() -> None:
    log.info("autoqueue_scheduler.start", interval_seconds=INTERVAL_SECONDS)
    await asyncio.sleep(120)  # let the app + web boot
    _warned = False
    while True:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            if not _warned:
                log.warning("autoqueue_scheduler.tick_failed")
                _warned = True
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

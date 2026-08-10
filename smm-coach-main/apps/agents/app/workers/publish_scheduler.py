"""publish_scheduler — fires due scheduled Instagram posts.

The publish logic lives in the web service (TS Graph API client), so this worker
is a thin trigger: every 60s it POSTs the web's /api/cron/publish-due endpoint,
which claims + publishes any ScheduledPost whose time has come. Needs WEB_URL +
CRON_SECRET env; a no-op (logs once) when unconfigured. Opt-in via RUN_WORKERS=1.

Standalone:  uv run python -m app.workers.publish_scheduler
"""
from __future__ import annotations

import asyncio
import os

import httpx
import structlog

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 60


async def _tick() -> None:
    web = (os.getenv("WEB_URL") or "").rstrip("/")
    secret = os.getenv("CRON_SECRET") or os.getenv("AGENTS_HMAC_SECRET") or ""
    if not web or not secret:
        return  # scheduling not configured on this deployment
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{web}/api/cron/publish-due", headers={"x-cron-secret": secret}
        )
        if r.status_code != 200:
            log.warning("publish_scheduler.http", status=r.status_code)
            return
        data = r.json()
        if data.get("published") or data.get("failed") or data.get("requeued"):
            log.info(
                "publish_scheduler.tick",
                published=data.get("published"),
                requeued=data.get("requeued"),
                failed=data.get("failed"),
            )


async def loop_forever() -> None:
    log.info("publish_scheduler.start", interval_seconds=INTERVAL_SECONDS)
    await asyncio.sleep(90)  # let the app + web boot
    _warned = False
    while True:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            if not _warned:
                log.warning("publish_scheduler.tick_failed")
                _warned = True
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

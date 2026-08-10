"""insights_scheduler — refreshes OFFICIAL per-post metrics every 6h.

The Graph insights fetch lives in the web service (it holds the per-account OAuth
token + uses graph.instagram.com), so this worker is a thin trigger: it POSTs the
web's /api/cron/refresh-insights endpoint, which reads recently-published tasks'
numeric media ids and writes reach/views/saves/shares/likes/comments to
ContentTask.actualMetrics. account_tracker (tracker_pulse) then reads those official
metrics instead of the datacenter-IP-blocked scraper.

Needs WEB_URL + CRON_SECRET; a no-op (logs once) when unconfigured. Opt-in via
RUN_WORKERS=1 (brain plane). Standalone: uv run python -m app.workers.insights_scheduler
"""
from __future__ import annotations

import asyncio
import os

import httpx
import structlog

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 6 * 60 * 60  # every 6h, ahead of the tracker_pulse cadence


async def _tick() -> None:
    web = (os.getenv("WEB_URL") or "").rstrip("/")
    secret = os.getenv("CRON_SECRET") or os.getenv("AGENTS_HMAC_SECRET") or ""
    if not web or not secret:
        return  # insights refresh not configured on this deployment
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{web}/api/cron/refresh-insights", headers={"x-cron-secret": secret}
        )
        if r.status_code != 200:
            log.warning("insights_scheduler.http", status=r.status_code)
            return
        data = r.json()
        if data.get("refreshed"):
            log.info(
                "insights_scheduler.tick",
                scanned=data.get("scanned"),
                refreshed=data.get("refreshed"),
                skipped=data.get("skipped"),
            )


async def loop_forever() -> None:
    log.info("insights_scheduler.start", interval_seconds=INTERVAL_SECONDS)
    await asyncio.sleep(120)  # let the app + web boot
    _warned = False
    while True:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            if not _warned:
                log.warning("insights_scheduler.tick_failed")
                _warned = True
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

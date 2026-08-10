"""post_sync_scheduler — keeps each user's OWN Instagram posts in sync.

The initial sync runs once at OAuth connect (web syncInstagramAccount). A post
published DIRECTLY on Instagram afterwards would otherwise never appear in the
dashboard. This thin trigger POSTs the web's /api/cron/sync-posts every 30 min,
which pulls each connected account's recent media and stores anything new
(new-posts-only, cheap). So "I posted on IG but it's not in the app" self-heals.

Needs WEB_URL + CRON_SECRET; a no-op (logs once) when unconfigured. Opt-in via
RUN_WORKERS=1 (brain plane). Standalone: uv run python -m app.workers.post_sync_scheduler
"""
from __future__ import annotations

import asyncio
import os

import httpx
import structlog

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 30 * 60  # every 30 min — new IG posts appear without a reconnect


async def _tick() -> None:
    web = (os.getenv("WEB_URL") or "").rstrip("/")
    secret = os.getenv("CRON_SECRET") or os.getenv("AGENTS_HMAC_SECRET") or ""
    if not web or not secret:
        return  # post re-sync not configured on this deployment
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{web}/api/cron/sync-posts", headers={"x-cron-secret": secret}
        )
        if r.status_code != 200:
            log.warning("post_sync_scheduler.http", status=r.status_code)
            return
        data = r.json()
        if data.get("newPosts"):
            log.info(
                "post_sync_scheduler.tick",
                scanned=data.get("scanned"),
                new_posts=data.get("newPosts"),
                skipped=data.get("skipped"),
            )


async def loop_forever() -> None:
    log.info("post_sync_scheduler.start", interval_seconds=INTERVAL_SECONDS)
    await asyncio.sleep(140)  # let the app + web boot
    _warned = False
    while True:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            if not _warned:
                log.warning("post_sync_scheduler.tick_failed")
                _warned = True
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

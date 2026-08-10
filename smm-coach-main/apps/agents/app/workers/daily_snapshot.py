"""Daily snapshot worker.

Once per day (00:05 Asia/Tashkent), walks every active tenant and writes
two rows: `FollowerSnapshot` (current IG follower count + 24h delta) and
`DailyActivity` (intensity 0-4 derived from posts+tasks+agent runs in the
last 24h). These rows feed the dashboard sparkline, KPI deltas, streak
heatmap, and the forecast worker.

In dev: skip IG scraping when `IG_SCRAPER_ACCOUNTS` is unset — just refresh
the `delta24h` field from the existing `followerCount` so the row is honest.

Start:
    RUN_WORKERS=1 uv run uvicorn app.main:app
    # or standalone:
    uv run python -m app.workers.daily_snapshot
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.integrations.instagram import graph_api, instagrapi_client
from app.memory.db import get_sessionmaker
from app.workers._singleton import run_as_singleton

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 24 * 60 * 60  # 24h


async def _fetch_follower_count(handle: str) -> int | None:
    """Current follower count via the OFFICIAL business_discovery edge (scrape-free,
    works for any public PROFESSIONAL account incl. the owner's own), with instagrapi
    as a degraded fallback, else None (keep the cached value — never fabricate).

    business_discovery uses the shared service token + the handle, NOT a per-account
    OAuth token, so it works uniformly for OAuth'd AND manually-added own accounts —
    and it doesn't hit the datacenter-IP block the scraper does."""
    h = (handle or "").lstrip("@").strip()
    if not h:
        return None
    token = os.getenv("IG_GRAPH_SERVICE_TOKEN")
    ig_user_id = os.getenv("IG_GRAPH_SERVICE_USER_ID")
    if token and ig_user_id:
        snap = await graph_api.fetch_competitor_snapshot(h, ig_user_id=ig_user_id, access_token=token)
        fc = int(snap.get("follower_count", 0)) if snap else 0
        if fc > 0:
            return fc
        # fc<=0 = personal/private/unreadable, NOT a real 0 — fall through.
    if os.getenv("IG_SCRAPER_ACCOUNTS"):
        try:
            snap2 = await instagrapi_client.fetch_profile(h)
            fc2 = int(snap2.get("follower_count", 0))
            return fc2 if fc2 > 0 else None
        except Exception as exc:  # noqa: BLE001
            log.warning("daily_snapshot.scrape_failed", handle=h, error=repr(exc))
            return None
    return None


async def _active_tenants() -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT t.id AS tenant_id, ig.id AS ig_id, ig.handle, ig."followerCount" AS follower_count
                FROM tenants t
                JOIN instagram_accounts ig ON ig."tenantId" = t.id
                WHERE EXISTS (SELECT 1 FROM users u WHERE u."tenantId" = t.id)
                """
            )
        )
        return [dict(r) for r in rows.mappings().all()]


async def _snapshot_one(t: dict) -> None:
    sm = get_sessionmaker()
    handle = t["handle"]
    cached = int(t["follower_count"] or 0)
    fresh = cached

    got = await _fetch_follower_count(handle)
    if got and got > 0:
        fresh = got

    async with sm() as session:
        # Only record a follower snapshot when we have a REAL count. A 0 here means
        # "unknown" (personal/private/unreadable/fetch-failed), not zero followers —
        # writing it created artifact 0-rows that later made delta24h a false
        # +followers spike (real − 0) the first time a genuine count arrived.
        if fresh > 0:
            # Yesterday's count for delta24h — the last NON-ZERO snapshot, so a
            # legacy artifact 0-row can never poison the delta.
            yest = await session.execute(
                text(
                    """
                    SELECT count FROM follower_snapshots
                    WHERE "instagramAccountId" = :ig AND count > 0
                    ORDER BY "takenAt" DESC LIMIT 1
                    """
                ),
                {"ig": t["ig_id"]},
            )
            prev = yest.scalar() or fresh
            delta = fresh - int(prev)

            await session.execute(
                text(
                    """
                    INSERT INTO follower_snapshots
                      (id, "tenantId", "instagramAccountId", count, "delta24h", "takenAt")
                    VALUES (:id, :tenant_id, :ig, :count, :delta, NOW())
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "tenant_id": t["tenant_id"],
                    "ig": t["ig_id"],
                    "count": fresh,
                    "delta": delta,
                },
            )

        # Daily activity intensity 0-4 based on activity in last 24h
        activity = await session.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM content_tasks
                     WHERE "tenantId" = :tenant_id AND status IN ('complete','published')
                     AND "updatedAt" > NOW() - INTERVAL '24 hours') AS tasks_done,
                  (SELECT count(*) FROM instagram_posts ip
                     JOIN instagram_accounts ia ON ia.id = ip."instagramAccountId"
                     WHERE ia."tenantId" = :tenant_id AND ip."postedAt" > NOW() - INTERVAL '24 hours') AS posts_count,
                  (SELECT count(*) FROM agent_runs
                     WHERE "tenantId" = :tenant_id AND "createdAt" > NOW() - INTERVAL '24 hours') AS runs_count
                """
            ),
            {"tenant_id": t["tenant_id"]},
        )
        row = activity.mappings().first() or {}
        posts = int(row.get("posts_count", 0))
        tasks = int(row.get("tasks_done", 0))
        runs = int(row.get("runs_count", 0))

        # Intensity scale:
        # 0 — nothing; 1 — only agents ran; 2 — 1 task or post;
        # 3 — multiple tasks; 4 — published + multiple tasks
        if posts >= 1 and tasks >= 2:
            intensity = 4
        elif tasks >= 2:
            intensity = 3
        elif posts >= 1 or tasks >= 1:
            intensity = 2
        elif runs >= 1:
            intensity = 1
        else:
            intensity = 0

        today = datetime.now(UTC).date()
        await session.execute(
            text(
                """
                INSERT INTO daily_activity
                  (id, "tenantId", date, intensity, "postsCount", "tasksDone", "agentRunsCount", meta)
                VALUES (:id, :tenant_id, :date, :intensity, :posts, :tasks, :runs, '{}'::jsonb)
                ON CONFLICT ("tenantId", date) DO UPDATE
                SET intensity = EXCLUDED.intensity,
                    "postsCount" = EXCLUDED."postsCount",
                    "tasksDone" = EXCLUDED."tasksDone",
                    "agentRunsCount" = EXCLUDED."agentRunsCount"
                """
            ),
            {
                "id": uuid.uuid4().hex,
                "tenant_id": t["tenant_id"],
                "date": today,
                "intensity": intensity,
                "posts": posts,
                "tasks": tasks,
                "runs": runs,
            },
        )

        # Keep InstagramAccount.followerCount in sync
        await session.execute(
            text(
                'UPDATE instagram_accounts SET "followerCount" = :c, "lastSyncedAt" = NOW() WHERE id = :id'
            ),
            {"c": fresh, "id": t["ig_id"]},
        )
        await session.commit()


async def snapshot_all() -> None:
    tenants = await _active_tenants()
    log.info("daily_snapshot.batch", count=len(tenants))
    if tenants:
        telegram.send(f"📸 Kunlik snapshot · {len(tenants)} akkaunt follower count yangilanmoqda")
    for t in tenants:
        try:
            await _snapshot_one(t)
        except Exception:  # noqa: BLE001
            log.exception("daily_snapshot.failed", handle=t.get("handle"))


async def _seconds_until_next_run() -> float:
    """Schedule for 00:05 Asia/Tashkent (= 19:05 UTC previous day)."""
    now = datetime.now(UTC)
    # 19:05 UTC = 00:05 Tashkent
    target = now.replace(hour=19, minute=5, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def loop_forever() -> None:
    log.info("daily_snapshot.start")
    # First run after a short delay so other services have time to boot.
    await asyncio.sleep(30)
    while True:
        try:
            # Singleton gate: only one replica writes the day's snapshots (a plain
            # follower_snapshots INSERT would otherwise duplicate per replica).
            await run_as_singleton("daily_snapshot", snapshot_all)
        except Exception:  # noqa: BLE001
            log.exception("daily_snapshot.batch_failed")
        await asyncio.sleep(await _seconds_until_next_run())


if __name__ == "__main__":
    asyncio.run(snapshot_all())

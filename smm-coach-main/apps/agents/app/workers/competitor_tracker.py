"""Competitor tracker worker.

Every 12 hours, walks every `CompetitorTrack` row and refreshes:
- `followers` (current count via instagrapi public profile)
- `growthRate` (% per week vs row a week ago — best effort if no history)
- `lastScrapedAt`

`overlapPct` (audience overlap with the tenant's own followers) is left as
a periodic-best-effort field: it's expensive to compute and would require
fetching follower lists. For MVP we keep whatever was set at onboarding.
"""
from __future__ import annotations

import asyncio
import os
import random

import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.integrations.instagram import graph_api, instagrapi_client
from app.memory import redis_cache
from app.memory.db import get_sessionmaker
from app.memory.shared_knowledge import save_competitor_posts

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 12 * 60 * 60
# Cross-process/replica "ran recently" marker (TTL = the interval). Gates the
# boot run so a crash/restart loop can't re-fire the full business_discovery
# batch ~90s after every reboot and deepen the code-4 rate limit.
_LAST_RUN_KEY = "competitor_tracker:last_run"


async def _all_competitors() -> list[dict]:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT ct.id, ct."tenantId", ct.handle, ct.followers,
                       (SELECT op.niche FROM onboarding_profiles op
                        WHERE op."tenantId" = ct."tenantId"
                        ORDER BY op."createdAt" DESC LIMIT 1) AS niche
                FROM competitor_tracks ct
                """
            )
        )
        return [dict(r) for r in rows.mappings().all()]


async def _fetch_follower_count(handle: str) -> int | None:
    """Current follower count for a competitor, preferring the OFFICIAL
    business_discovery edge (scrape-free, scalable, no ban risk) when a FB-Login
    service token is configured; falling back to instagrapi only if a scraper
    account is set. Returns None when nothing can fetch it — the caller then
    leaves the row UNTOUCHED (stale real data beats fabricated growth)."""
    h = handle.lstrip("@").strip()
    if not h:
        return None

    # 1) Official path — one configured FB-Login account's token reads ANY public
    #    business/creator via business_discovery. Preferred at scale.
    token = os.getenv("IG_GRAPH_SERVICE_TOKEN")
    ig_user_id = os.getenv("IG_GRAPH_SERVICE_USER_ID")
    if token and ig_user_id:
        snap = await graph_api.fetch_competitor_snapshot(h, ig_user_id=ig_user_id, access_token=token)
        fc = int(snap.get("follower_count", 0)) if snap else 0
        if fc > 0:
            return fc
        # fc<=0 means parse glitch / empty payload, NOT a real count — fall through
        # rather than clobber every tracking row to 0 / -100% growth.

    # 2) Fallback — instagrapi, only if a scraper account is configured.
    if os.getenv("IG_SCRAPER_ACCOUNTS"):
        try:
            # Bound it: instagrapi.fetch_profile carries an @retry backoff (30–600s ×3)
            # that, on this datacenter IP (IG-blocked), can stall the ENTIRE tracker
            # tick for minutes PER handle. business_discovery is the real path now; this
            # fallback is best-effort and must never hang the loop — cap at 25s.
            snap2 = await asyncio.wait_for(instagrapi_client.fetch_profile(h), timeout=25)
            fc2 = int(snap2.get("follower_count", 0))
            # instagrapi returns a follower_count=0 STUB when the session can't be
            # acquired / both fetch paths fail — treat that as no-data, not a real 0
            # (else the dedup fan-out would zero out the handle for every tenant).
            return fc2 if fc2 > 0 else None
        except Exception as exc:  # noqa: BLE001 — incl. TimeoutError; degraded fallback
            log.warning("competitor_tracker.scrape_failed", handle=h, error=repr(exc)[:160])
            return None

    # 3) Nothing configured — do NOT fabricate (the old code random-walked a fake
    #    count and compounded it every 12h).
    return None


async def _fetch_recent_posts(handle: str) -> list[dict]:
    """A competitor's recent posts via the OFFICIAL business_discovery media edge —
    only when a FB-Login service token is configured (no instagrapi posts path).
    Returns [] otherwise so the caller simply skips content caching."""
    h = handle.lstrip("@").strip()
    token = os.getenv("IG_GRAPH_SERVICE_TOKEN")
    ig_user_id = os.getenv("IG_GRAPH_SERVICE_USER_ID")
    if not h or not token or not ig_user_id:
        return []
    try:
        return await graph_api.fetch_competitor_recent_posts(h, ig_user_id=ig_user_id, access_token=token)
    except graph_api.GraphRateLimited:
        return []  # throttled → skip this handle's content caching this tick


def _group_by_handle(rows: list[dict]) -> dict[str, list[dict]]:
    """Dedup: many tenants can track the SAME competitor. Fetch each unique handle
    ONCE and apply to every tracking row — not one API call per (tenant, handle).
    Critical at scale given business_discovery's ~200-calls/hr limit."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        key = (r.get("handle") or "").lstrip("@").strip().lower()
        if key:
            groups.setdefault(key, []).append(r)
    return groups


async def _apply(rows: list[dict], fresh: int) -> None:
    """Write one fetched follower count to every row tracking that handle (each
    row keeps its OWN prior count for the per-tenant growth %)."""
    sm = get_sessionmaker()
    async with sm() as session:
        for r in rows:
            prev = int(r["followers"] or 0)
            growth = ((fresh - prev) / prev * 100.0) if prev > 0 else 0.0
            await session.execute(
                text(
                    """
                    UPDATE competitor_tracks
                    SET followers = :fresh, "growthRate" = :growth,
                        "lastScrapedAt" = NOW(), "updatedAt" = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": r["id"], "fresh": fresh, "growth": growth},
            )
        await session.commit()


async def refresh_all() -> None:
    competitors = await _all_competitors()
    groups = _group_by_handle(competitors)
    log.info("competitor_tracker.batch", rows=len(competitors), unique=len(groups))
    if groups:
        telegram.send(f"🔭 Raqobat kuzatuvchisi · {len(groups)} ta noyob raqobatchi yangilanmoqda")
    for handle, rows in groups.items():
        try:
            fresh = await _fetch_follower_count(handle)
            if fresh is not None:  # None → nothing fetched, leave rows untouched (no fabrication)
                await _apply(rows, fresh)
            # Cache the competitor's top posts per niche ("what's working") so the
            # competitor_intel node + dashboard surface real content, not just a
            # follower number. One fetch per handle, saved under each niche that
            # tracks it (the row's niche came from the tenant's onboarding profile).
            posts = await _fetch_recent_posts(handle)
            if posts:
                niches = {(r.get("niche") or "").strip() for r in rows if r.get("niche")}
                for niche in niches:
                    await save_competitor_posts(handle=handle, niche=niche, posts=posts)
        except Exception:  # noqa: BLE001
            log.exception("competitor_tracker.handle_failed", handle=handle)
        # 0.5-2s jitter between handles so we don't burst the rate limit — runs on
        # EVERY handle incl. the unreadable ones (each still cost a business_discovery
        # call), so the pacing actually protects the ~200/hr quota.
        await asyncio.sleep(random.uniform(0.5, 2.0))  # noqa: S311 — jitter, not crypto


async def loop_forever() -> None:
    log.info("competitor_tracker.start")
    await asyncio.sleep(90)
    while True:
        # Skip the batch when a run already happened within the interval — this
        # replica, another replica, OR a prior process before a restart. Without
        # this, a restart loop re-runs the full business_discovery batch ~90s
        # after every reboot (the code-4 amplifier the founder hit). redis_cache
        # is fail-soft (None on any error) → degrades to always-run if Redis is
        # down, never blocks the tracker.
        if await redis_cache.get_json(_LAST_RUN_KEY):
            log.info("competitor_tracker.skip_recent_run")
        else:
            # Mark BEFORE the batch, not after: a process-kill mid-run (the OOM /
            # restart case) must still suppress the re-run on the next boot.
            await redis_cache.set_json(_LAST_RUN_KEY, {"ran": True}, ttl_seconds=INTERVAL_SECONDS)
            try:
                await refresh_all()
            except Exception:  # noqa: BLE001
                log.exception("competitor_tracker.batch_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(refresh_all())

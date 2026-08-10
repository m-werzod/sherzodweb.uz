"""Virale grid pre-warm worker.

Twice a day — at 07:00 and 19:00 Asia/Tashkent — recomputes the Virale
competitor grids and writes them into the Redis cache that
/v1/scrape/competitor-media serves from, so a page view is a Redis GET, never a
live 60-90s scrape fan-out. Sends exactly ONE Telegram summary per refresh (the
per-compute chatter was removed). Entry kinds:

- ONE region grid per region (today: "uz") — cross-tenant top accounts, shared
  by every tenant on the region filter.
- ONE global grid — the worldwide anchors behind the "Global" tab (the "Top
  layk" tab re-ranks region+global at request time, no entry of its own).
- One niche grid per tenant — the same inputs the web's getViraleData sends
  (tracked competitor handles + onboarding niche), so the worker-warmed entry
  is exactly what the lazy path would compute (per_handle defaults to the API
  max in CompetitorMediaRequest — both paths MUST agree, they share cache keys).

Runs with force_refresh=True: bypasses the cache read AND gets the roomier
view-enrichment timeouts (nobody is waiting on a background pass).

Started by the FastAPI app on boot (RUN_WORKERS=1) or run standalone:
    uv run python -m app.workers.virale_refresher
"""
from __future__ import annotations

import asyncio
import datetime
import os
import random

import structlog
from sqlalchemy import text

from app.api.scrape import (
    CompetitorMediaRequest,
    _virale_cache_key,
    start_or_join_accounts,
    start_or_join_compute,
)
from app.integrations import telegram
from app.memory import redis_cache
from app.memory.db import get_sessionmaker
from app.workers._singleton import run_as_singleton

log = structlog.get_logger(__name__)

# Fixed daily refresh times, 07:00 and 19:00 Asia/Tashkent (UTC+5, no DST) →
# 02:00 and 14:00 UTC. Twice a day is enough; the user wants the "kesh
# yangilandi" ping to land at exactly these times, not "12h since boot".
_REFRESH_HOURS_UTC = (2, 14)
# Regions with tenants. Single-region product today; the region isn't stored
# per tenant anywhere yet, so this list IS the source of truth.
REGIONS = ["uz"]

# When a shared grid comes back with 0 reels, the compute tags WHY (scrape.py
# _empty_grid_reason). Surface it in the one daily summary so an empty grid names
# its cause instead of a silent "0 ta reel" the founder can't act on.
_EMPTY_REASON_UZ = {
    "no_candidates": "akkaunt topilmadi (web qidiruv sozlanmagan yoki seed bo'sh)",
    "rate_limited": "Instagram vaqtincha limitladi (rate limit) — o'zi tiklanadi",
    "some_rate_limited": "qisman rate limit, qolgan akkauntlar o'qilmadi",
    "all_unreadable": (
        "hech bir akkaunt o'qilmadi — IG_GRAPH_SERVICE_TOKEN yaroqsiz yoki "
        "business_discovery ruxsati yo'q"
    ),
    "exception": "ichki xato — loglarni tekshiring",
}


def _grid_summary_line(label: str, count: int, reason: str, unit: str = "reel") -> str:
    """One Telegram bullet per shared grid: the count, or — when empty — WHY."""
    if count > 0:
        return f"• {label}: {count} ta {unit}"
    hint = _EMPTY_REASON_UZ.get(reason, "sabab noma'lum — loglarni tekshiring")
    return f"• {label}: 0 ta {unit} ⚠️ {hint}"


def _seconds_until_next_refresh(now: datetime.datetime) -> float:
    """Seconds from `now` (UTC-aware) to the next 07:00/19:00 Tashkent tick."""
    upcoming = [
        (now + datetime.timedelta(days=d)).replace(
            hour=h, minute=0, second=0, microsecond=0
        )
        for d in (0, 1)
        for h in _REFRESH_HOURS_UTC
    ]
    return min((t - now).total_seconds() for t in upcoming if t > now)


async def _shared_cache_cold() -> bool:
    """True ONLY when a shared grid was never computed under the current cache
    version — a genuinely fresh deploy (the vN key bump invalidates old entries)
    or an expired TTL. Drives a one-off boot warm so users don't wait until
    07:00/19:00 to see the new grids.

    Deliberately NOT true for a recently-computed-but-EMPTY grid: an empty grid
    (e.g. a transient Graph rate limit) still carries `generated_at`, so a
    restart / crash-loop can't re-trigger a full boot-warm refresh on every reboot
    and deepen the rate limit — the code-4 loop. The scheduled 07:00/19:00 tick +
    TTL expiry recompute it on a healthy cadence instead."""
    for req in (
        CompetitorMediaRequest(mode="region", region="uz"),
        CompetitorMediaRequest(mode="global"),
    ):
        cached = await redis_cache.get_json(_virale_cache_key(req))
        if not (isinstance(cached, dict) and cached.get("generated_at")):
            return True
    return False


async def _tenants_with_virale() -> list[dict]:
    """Tenants that can render a Virale grid: an onboarding niche to discover
    from and/or tracked competitor handles. Mirrors getViraleData's inputs."""
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT t.id AS tenant_id,
                       (SELECT op.niche FROM onboarding_profiles op
                        WHERE op."tenantId" = t.id
                        ORDER BY op."createdAt" DESC LIMIT 1) AS niche,
                       (SELECT op."nicheDetail" FROM onboarding_profiles op
                        WHERE op."tenantId" = t.id
                        ORDER BY op."createdAt" DESC LIMIT 1) AS niche_detail
                FROM tenants t
                WHERE EXISTS (SELECT 1 FROM users u WHERE u."tenantId" = t.id)
                """
            )
        )
        return [dict(r) for r in rows.mappings().all()]


async def _tenant_handles(tenant_id: str) -> list[str]:
    """Same pool the web sends: the tenant's tracked competitors, top-15 by
    follower count (getViraleData's competitorTrack.findMany take:15)."""
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT handle FROM competitor_tracks
                WHERE "tenantId" = :t
                ORDER BY followers DESC NULLS LAST
                LIMIT 15
                """
            ),
            {"t": tenant_id},
        )
        return [str(r["handle"]) for r in rows.mappings().all()]


async def refresh_all() -> None:
    if not os.getenv("IG_GRAPH_SERVICE_TOKEN") or not os.getenv("IG_GRAPH_SERVICE_USER_ID"):
        log.info("virale_refresher.skipped", reason="no_service_token")
        return

    # Shared grids first — one compute each serves every tenant: per-region
    # grids (region filter) + the single worldwide grid (Global tab; the "Top
    # layk" tab is a request-time re-rank of these two, no compute of its own).
    # A healthy tick costs 12 business_discovery calls per grid; a thin anchor
    # spine triggers the top-up wave (up to 12 more + web discovery on region).
    region_posts = 0
    global_posts = 0
    region_reason = ""
    global_reason = ""
    shared: list[CompetitorMediaRequest] = [
        CompetitorMediaRequest(mode="region", region=region, force_refresh=True)
        for region in REGIONS
    ]
    shared.append(CompetitorMediaRequest(mode="global", force_refresh=True))
    for req in shared:
        try:
            result = await asyncio.shield(start_or_join_compute(req, _virale_cache_key(req)))
            n = len(result.get("posts") or [])
            reason = str(result.get("reason") or "")
            if req.mode == "global":
                global_posts, global_reason = n, reason
            else:
                region_posts, region_reason = n, reason
            log.info(
                "virale_refresher.shared_done",
                mode=req.mode,
                region=req.region if req.mode == "region" else None,
                posts=n,
                reason=reason or None,
            )
        except Exception:  # noqa: BLE001
            log.exception("virale_refresher.shared_failed", mode=req.mode, region=req.region)
            if req.mode == "global":
                global_reason = "exception"
            else:
                region_reason = "exception"
        # Space shared grids ~30s apart, NOT 3-8s: business_discovery is
        # PLATFORM (per-app) rate-limited on burst load (X-App-Usage total_time/
        # cputime), so region's 12 heavy nested-media calls can throttle global's
        # batch fired seconds later — the "all 20 global anchors dead" symptom.
        # A wider gap lets the burst counters recover between grids.
        await asyncio.sleep(random.uniform(25.0, 40.0))  # noqa: S311 — anti-burst pacing

    # Top-accounts grid (profile cards ranked by follower count) — one shared
    # region compute, warmed alongside the reels grids. Cheaper than a reels grid
    # (one profile GET per handle, no media edge).
    accounts_count = 0
    accounts_reason = ""
    acc_req = CompetitorMediaRequest(mode="accounts", region="uz", force_refresh=True)
    try:
        acc = await asyncio.shield(start_or_join_accounts(acc_req, _virale_cache_key(acc_req)))
        accounts_count = len(acc.get("accounts") or [])
        accounts_reason = str(acc.get("reason") or "")
        log.info("virale_refresher.accounts_done", accounts=accounts_count, reason=accounts_reason or None)
    except Exception:  # noqa: BLE001
        log.exception("virale_refresher.accounts_failed")
        accounts_reason = "exception"
    await asyncio.sleep(random.uniform(25.0, 40.0))  # noqa: S311 — anti-burst pacing

    tenants = await _tenants_with_virale()
    log.info("virale_refresher.batch", tenants=len(tenants))
    tenant_ok = 0
    for t in tenants:
        tenant_id = str(t["tenant_id"])
        niche = (t.get("niche") or t.get("niche_detail") or "").strip()
        try:
            handles = await _tenant_handles(tenant_id)
            if not handles and not niche:
                continue  # nothing to show and nothing to discover from
            req = CompetitorMediaRequest(
                handles=handles,
                niche=niche or None,
                region="uz",
                tenant_id=tenant_id,
                force_refresh=True,
            )
            result = await asyncio.shield(start_or_join_compute(req, _virale_cache_key(req)))
            if result.get("posts"):
                tenant_ok += 1
            log.info(
                "virale_refresher.tenant_done",
                tenant_id=tenant_id,
                posts=len(result.get("posts") or []),
            )
        except Exception:  # noqa: BLE001
            log.exception("virale_refresher.tenant_failed", tenant_id=tenant_id)
        # Each tenant costs up to 8 business_discovery calls (+ enrichment) —
        # pace the walk so the batch stays inside the ~200/hr Meta quota that
        # competitor_tracker shares.
        await asyncio.sleep(random.uniform(3.0, 8.0))  # noqa: S311 — jitter, not crypto

    # The ONE Telegram message per refresh (the user asked for just this): what
    # got refreshed, ranked by views/likes — and, for any empty grid, WHY (so a
    # dead token / rate limit is visible, not a silent "0 ta reel"). All the
    # per-compute chatter was removed from scrape.py.
    from app.integrations.search import web_search_enabled

    # Dynamic discovery (the primary source for region/global) needs a search
    # provider. Without one the grids fall back to the curated seed floor only —
    # tell the founder so "o'zi qidirish" not working is diagnosable.
    search_note = (
        ""
        if web_search_enabled()
        else "\n⚠️ Web qidiruv (Tavily yoki Gemini) sozlanmagan — grid faqat zaxira "
        "ro'yxatdan to'ladi, avtomatik 'o'zi qidirish' ishlamaydi."
    )
    telegram.send(
        "✅ Virale keshi yangilandi — eng ko'p ko'rilgan/layk olganlar bo'yicha\n"
        + _grid_summary_line("O'zbekiston (region)", region_posts, region_reason) + "\n"
        + _grid_summary_line("Global (dunyo)", global_posts, global_reason) + "\n"
        + "• Top layk: region + global reels'lari layk soni bo'yicha qayta saralandi\n"
        + _grid_summary_line("Top akkountlar", accounts_count, accounts_reason, unit="akkaunt") + "\n"
        + f"• Soha (niche): {tenant_ok} ta tenant yangilandi"
        + search_note
    )


async def loop_forever() -> None:
    log.info("virale_refresher.start", refresh_hours_utc=_REFRESH_HOURS_UTC)
    # Let the app (and competitor_tracker's 90s head start) boot first.
    await asyncio.sleep(180)
    # One-off boot warm ONLY when the shared grids are cold (fresh deploy — the
    # v2 key bump invalidates old entries — or expired TTL). Steady-state
    # restarts with a warm cache skip this, so it doesn't ping on every restart.
    try:
        if await _shared_cache_cold():
            await run_as_singleton("virale_refresher", refresh_all)
    except Exception:  # noqa: BLE001
        log.exception("virale_refresher.boot_warm_failed")
    while True:
        now = datetime.datetime.now(datetime.UTC)
        await asyncio.sleep(_seconds_until_next_refresh(now))
        try:
            await run_as_singleton("virale_refresher", refresh_all)
        except Exception:  # noqa: BLE001
            log.exception("virale_refresher.batch_failed")


if __name__ == "__main__":
    asyncio.run(refresh_all())

"""Periodic worker: keep cross-tenant `shared_knowledge` FRESH for every active
niche using real web search (Stage 6 "bilim doimiy o'sadi").

knowledge_seeder populates a niche ONCE on first encounter (LLM-invented +
45-day TTL). This refresher runs daily and, for each niche an active tenant
actually uses, pulls LIVE web results into shared_knowledge (kind=niche_news,
source=web_search, 7-day TTL) via the same save_web_results path industry_news
uses — so the shared cache reflects the present, not a stale one-shot seed, and
new tenants in that niche start warm.

No-op when no web-search provider is configured. Opt-in via RUN_WORKERS=1
(brain plane). Standalone:  uv run python -m app.workers.knowledge_refresher
"""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import text

from app.integrations.search import web_search, web_search_enabled
from app.memory.db import get_sessionmaker
from app.memory.shared_knowledge import save_web_results
from app.workers._singleton import run_as_singleton

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 24 * 60 * 60  # daily
_MAX_NICHES = 20  # cap per tick — protects the search quota
_REGION = "uz"


async def _active_niches() -> list[str]:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT DISTINCT LOWER(TRIM(niche)) AS niche
                FROM onboarding_profiles
                WHERE niche IS NOT NULL AND TRIM(niche) <> ''
                LIMIT :lim
                """
            ),
            {"lim": _MAX_NICHES},
        )
        return [str(r[0]) for r in rows.all() if r[0]]


async def _fresh_niches() -> set[str]:
    """Niches whose web_search cache was refreshed in the last day — skip them so
    we don't re-embed identical snippets daily (embeddings cost tokens)."""
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT DISTINCT "nicheTag"
                FROM shared_knowledge
                WHERE source = 'web_search' AND region = :region
                  AND "createdAt" > NOW() - INTERVAL '1 day'
                """
            ),
            {"region": _REGION},
        )
        return {str(r[0]).lower() for r in rows.all() if r[0]}


async def _refresh_once() -> None:
    if not web_search_enabled():
        return  # no provider → nothing to refresh with
    niches = await _active_niches()
    if not niches:
        return
    fresh = await _fresh_niches()  # already refreshed <1 day ago → skip (save embed cost)
    stale = [n for n in niches if n not in fresh]
    refreshed = 0
    for niche in stale:
        try:
            hits = await web_search(
                f"{niche} Instagram trend yangiliklari {_REGION} 2026", limit=6
            )
            if hits:
                n = await save_web_results(niche, _REGION, hits)
                refreshed += int(bool(n))
        except Exception as exc:  # noqa: BLE001 — one niche failing must not stop the rest
            log.warning("knowledge_refresher.niche_failed", niche=niche, error=str(exc)[:120])
    log.info(
        "knowledge_refresher.done",
        niches=len(niches), stale=len(stale), skipped_fresh=len(niches) - len(stale), refreshed=refreshed,
    )


async def loop_forever() -> None:
    log.info("knowledge_refresher.start", interval_seconds=INTERVAL_SECONDS)
    await asyncio.sleep(150)  # let the app boot
    while True:
        try:
            await run_as_singleton("knowledge_refresher", _refresh_once)
        except Exception:  # noqa: BLE001
            log.exception("knowledge_refresher.tick_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

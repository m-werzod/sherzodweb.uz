"""Periodic worker: pull OFFICIAL Instagram hashtag trends into shared_knowledge
(kind=hashtag_trend, source=graph_api, 7-day TTL) for every active niche + the UZ
region, via the Graph API Hashtag Search `top_media` edge. Feeds
top_signals_for_region → competitor_intel → roadmap ("nima trendda + mahalliy
trendlar"), scrape-free and ban-safe so it scales to many tenants.

Meta limits Hashtag Search to ~30 UNIQUE hashtags / 7 days / querying account
(Platform rate limiting), so we (a) cache cross-tenant — one fetch per hashtag,
shared by region; (b) SKIP hashtags whose trend row is still live (<7-day TTL) so we
never burn the quota re-querying; (c) hard-cap the per-tick batch.

No-op unless IG_GRAPH_SERVICE_TOKEN + IG_GRAPH_SERVICE_USER_ID are set. Opt-in via
RUN_WORKERS=1 (brain plane). Standalone: uv run python -m app.workers.hashtag_trend_refresher
"""
from __future__ import annotations

import asyncio
import os
import random
import re

import structlog
from sqlalchemy import text

from app.integrations.instagram import graph_api
from app.memory.db import get_sessionmaker
from app.memory.shared_knowledge import save_hashtag_trends
from app.workers._singleton import run_as_singleton

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 24 * 60 * 60  # daily
_REGION = "uz"
_MAX_NICHES = 10  # cap niches read per tick
_MAX_HASHTAGS_PER_TICK = 20  # stay well under the 30/7-day quota (regional set + niche tags)

# Always-on UZ-regional hashtags — the "mahalliy trend" signal, independent of niche.
_REGIONAL_TAGS = ["uzbekistan", "toshkent", "ozbekiston", "tashkent", "uzbekblogger"]


def _niche_tag(niche: str) -> str:
    """Derive a single clean hashtag candidate from a niche (first word, alnum only)."""
    parts = (niche or "").strip().split()
    first = parts[0] if parts else ""
    return re.sub(r"[^a-z0-9]", "", first.lower())


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


async def _fresh_hashtags() -> set[str]:
    """Hashtags whose trend row is still live (<7-day TTL) — skip them so we never
    burn the 30/7-day quota re-querying a hashtag we already cached."""
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT DISTINCT metadata->>'hashtag' AS tag
                FROM shared_knowledge
                WHERE kind = 'hashtag_trend' AND region = :region
                  AND ("expiresAt" IS NULL OR "expiresAt" > NOW())
                """
            ),
            {"region": _REGION},
        )
        return {str(r[0]).lower() for r in rows.all() if r[0]}


def _candidate_hashtags(niches: list[str]) -> list[tuple[str, str | None]]:
    """(hashtag, niche) candidates: fixed UZ regional set + one tag per active niche,
    de-duped (preserving order, regional first)."""
    out: list[tuple[str, str | None]] = [(t, None) for t in _REGIONAL_TAGS]
    for n in niches:
        tag = _niche_tag(n)
        if len(tag) >= 3:
            out.append((tag, n))
    seen: set[str] = set()
    uniq: list[tuple[str, str | None]] = []
    for tag, niche in out:
        if tag and tag not in seen:
            seen.add(tag)
            uniq.append((tag, niche))
    return uniq


async def _refresh_once() -> None:
    token = os.getenv("IG_GRAPH_SERVICE_TOKEN")
    ig_user_id = os.getenv("IG_GRAPH_SERVICE_USER_ID")
    if not token or not ig_user_id:
        return  # no FB-Login service account configured → nothing to fetch with
    niches = await _active_niches()
    candidates = _candidate_hashtags(niches)
    fresh = await _fresh_hashtags()  # already cached <7 days ago → skip (quota guard)
    stale = [(t, n) for (t, n) in candidates if t not in fresh][:_MAX_HASHTAGS_PER_TICK]
    refreshed = 0
    for tag, niche in stale:
        try:
            posts = await graph_api.fetch_hashtag_top_media(tag, ig_user_id=ig_user_id, access_token=token)
            if posts:
                # ONE row per hashtag (the top post): a hashtag is a SINGLE "this tag
                # trends here" signal. Storing all N posts floods top_signals_for_region
                # with duplicate "#tag" labels and crowds out the other trend kinds
                # (trending_hook/audio/format), hurting signal diversity into the roadmap.
                n = await save_hashtag_trends(
                    hashtag=tag, region=_REGION, posts=posts, niche=niche, keep_top=1
                )
                refreshed += int(bool(n))
        except Exception as exc:  # noqa: BLE001 — one hashtag failing must not stop the rest
            log.warning("hashtag_trend_refresher.tag_failed", hashtag=tag, error=str(exc)[:120])
        # Pace the platform quota; runs on EVERY tag (even empty) so we never burst.
        await asyncio.sleep(random.uniform(0.5, 2.0))  # noqa: S311 — jitter, not crypto
    log.info(
        "hashtag_trend_refresher.done",
        candidates=len(candidates), queried=len(stale),
        skipped_fresh=len(candidates) - len(stale), refreshed=refreshed,
    )


async def loop_forever() -> None:
    log.info("hashtag_trend_refresher.start", interval_seconds=INTERVAL_SECONDS)
    await asyncio.sleep(160)  # let the app boot
    while True:
        try:
            await run_as_singleton("hashtag_trend_refresher", _refresh_once)
        except Exception:  # noqa: BLE001
            log.exception("hashtag_trend_refresher.tick_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

"""Chooses the best Instagram data source per request.

Priority (MVP):
1. Meta Graph API — when the user has OAuth'd and we have Advanced Access
2. instagrapi — primary scraping path (private mobile API, fast)
3. Playwright — fallback for things instagrapi can't reach (Reels Explore,
   hashtag pages without login)

The graph API path will become the primary source once Advanced Access is
granted; until then we lean on instagrapi for both self-data and competitor
data.
"""
from __future__ import annotations

import structlog

from app.graphs.state import AccountSnapshot
from app.integrations.instagram import graph_api, instagrapi_client, playwright_scraper

log = structlog.get_logger(__name__)


async def fetch_account_snapshot(handle: str, *, oauth_token: str | None = None) -> AccountSnapshot:
    if oauth_token:
        try:
            return await graph_api.fetch_self_snapshot(oauth_token)
        except Exception as exc:  # noqa: BLE001
            log.warning("graph_api.fallback_to_scrape", error=repr(exc))

    return await instagrapi_client.fetch_profile(handle)


async def fetch_post_metrics(post_id: str, *, oauth_token: str | None = None) -> dict:
    if oauth_token:
        try:
            return await graph_api.fetch_insights(post_id, oauth_token)
        except Exception as exc:  # noqa: BLE001
            log.warning("graph_api.fallback_to_scrape", error=repr(exc))

    return await instagrapi_client.fetch_post_metrics(post_id)


async def fetch_recent_posts(handle: str, *, limit: int = 24) -> list[dict]:
    return await instagrapi_client.fetch_recent_posts(handle, limit=limit)


async def fetch_recent_comments(post_id: str, *, limit: int = 50) -> list[dict]:
    return await instagrapi_client.fetch_recent_comments(post_id, limit=limit)


async def fetch_hashtag_top_posts(hashtag: str, *, limit: int = 20) -> list[dict]:
    """Hashtag exploration — Playwright path since instagrapi rate-limits faster on tags."""
    return await playwright_scraper.fetch_hashtag_top_posts(hashtag, limit=limit)


async def fetch_reels_explore(region_locale: str = "uz-UZ", *, limit: int = 20) -> list[dict]:
    return await playwright_scraper.fetch_reels_explore(region_locale, limit=limit)

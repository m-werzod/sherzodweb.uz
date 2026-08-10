"""Hashtag Search trend client — the OFFICIAL two-step (ig_hashtag_search -> top_media)
scrape-free trend signal. Locks in fail-soft (None, never raises), the no-step-2-on-
empty short-circuit, and the input sanitization that keeps the hashtag from corrupting
the query."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations.instagram import graph_api


@pytest.mark.asyncio
async def test_hashtag_top_media_success() -> None:
    with respx.mock:
        respx.route(method="GET", url__regex=r".*ig_hashtag_search.*").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "17999"}]})
        )
        respx.route(method="GET", url__regex=r".*top_media.*").mock(
            return_value=httpx.Response(
                200,
                json={"data": [
                    {"id": "m1", "media_type": "VIDEO", "like_count": 500, "comments_count": 20, "caption": "A"},
                    {"id": "m2", "media_type": "IMAGE", "like_count": 100, "comments_count": 3},
                ]},
            )
        )
        posts = await graph_api.fetch_hashtag_top_media(
            "#uzbekistan", ig_user_id="self123", access_token="tok"
        )
    assert posts is not None
    assert len(posts) == 2
    assert posts[0]["id"] == "m1"
    assert posts[0]["like_count"] == 500
    assert posts[0]["media_type"] == "VIDEO"


@pytest.mark.asyncio
async def test_hashtag_top_media_not_found_returns_none() -> None:
    # ig_hashtag_search returns empty data (typo'd / unknown hashtag) → None, and
    # step 2 (top_media) is NEVER reached. We define ONLY the search route, so if the
    # code wrongly proceeded to top_media, respx would raise (unmatched) and fail.
    with respx.mock:
        search = respx.route(method="GET", url__regex=r".*ig_hashtag_search.*").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        res = await graph_api.fetch_hashtag_top_media("nope", ig_user_id="self123", access_token="tok")
    assert res is None
    assert search.called


@pytest.mark.asyncio
async def test_hashtag_top_media_failsoft_on_error() -> None:
    with respx.mock:
        respx.route(method="GET", url__regex=r".*ig_hashtag_search.*").mock(
            return_value=httpx.Response(400, json={"error": {"message": "rate limited"}})
        )
        res = await graph_api.fetch_hashtag_top_media("uzbekistan", ig_user_id="self123", access_token="tok")
    assert res is None


@pytest.mark.asyncio
async def test_hashtag_top_media_empty_inputs() -> None:
    # No HTTP call should happen for empty hashtag / missing querying id.
    assert await graph_api.fetch_hashtag_top_media("  ", ig_user_id="self123", access_token="t") is None
    assert await graph_api.fetch_hashtag_top_media("uzbekistan", ig_user_id="", access_token="t") is None


@pytest.mark.asyncio
async def test_hashtag_top_media_sanitizes_query() -> None:
    captured: dict = {}

    def _cap(request: httpx.Request) -> httpx.Response:
        if "ig_hashtag_search" in str(request.url):
            captured["q"] = request.url.params.get("q")
            return httpx.Response(200, json={"data": [{"id": "17999"}]})
        return httpx.Response(200, json={"data": []})

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(side_effect=_cap)
        await graph_api.fetch_hashtag_top_media("#tosh! kent$", ig_user_id="self123", access_token="tok")
    # '#', '!', ' ', '$' stripped → alnum/underscore only, so the query can't corrupt
    # the request or inject extra params.
    assert captured["q"] == "toshkent"

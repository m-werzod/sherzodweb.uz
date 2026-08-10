"""business_discovery client — the OFFICIAL, scrape-free competitor-data path that
scales to many tenants. Locks in fail-soft behaviour (None, never raises) for the
many handles that can't be read (personal/private/typo), so callers degrade
gracefully instead of crashing a run."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations.instagram import graph_api


@pytest.mark.asyncio
async def test_competitor_snapshot_success() -> None:
    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                200,
                json={
                    "business_discovery": {
                        "id": "999",
                        "username": "natgeo",
                        "name": "National Geographic",
                        "biography": "Nature.",
                        "followers_count": 280_000_000,
                        "follows_count": 132,
                        "media_count": 30_000,
                    },
                    "id": "self123",
                },
            )
        )
        snap = await graph_api.fetch_competitor_snapshot(
            "@natgeo", ig_user_id="self123", access_token="tok"
        )
    assert snap is not None
    assert snap["handle"] == "natgeo"  # leading @ stripped
    assert snap["instagram_user_id"] == "999"
    assert snap["follower_count"] == 280_000_000
    assert snap["posts_count"] == 30_000
    assert snap["account_type"] == "business"


@pytest.mark.asyncio
async def test_competitor_snapshot_non_professional_returns_none() -> None:
    # business_discovery 400s when the target isn't a Professional account / doesn't exist.
    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                400, json={"error": {"message": "Cannot find user", "code": 110}}
            )
        )
        snap = await graph_api.fetch_competitor_snapshot(
            "some_personal_acct", ig_user_id="self123", access_token="tok"
        )
    assert snap is None


@pytest.mark.asyncio
async def test_competitor_snapshot_empty_inputs_short_circuit() -> None:
    # No HTTP call should happen for empty handle / missing querying id.
    with respx.mock:
        route = respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(200, json={})
        )
        assert await graph_api.fetch_competitor_snapshot("  ", ig_user_id="self123", access_token="t") is None
        assert await graph_api.fetch_competitor_snapshot("natgeo", ig_user_id="", access_token="t") is None
        assert route.call_count == 0


@pytest.mark.asyncio
async def test_competitor_snapshot_missing_bd_key_returns_none() -> None:
    # A 200 with no business_discovery payload (edge case) → None, not a crash.
    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(200, json={"id": "self123"})
        )
        snap = await graph_api.fetch_competitor_snapshot(
            "natgeo", ig_user_id="self123", access_token="tok"
        )
    assert snap is None


@pytest.mark.asyncio
async def test_competitor_snapshot_null_numeric_failsoft() -> None:
    # Meta can return a numeric field present-but-JSON-null for restricted/
    # transitional professional accounts. `.get(key, 0)` would NOT default (the
    # key exists) → int(None) raises, breaking the never-raises contract and
    # skipping the instagrapi fallback. Must coerce null → 0.
    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                200,
                json={
                    "business_discovery": {
                        "id": "999",
                        "username": "natgeo",
                        "followers_count": None,  # present-but-null
                        "follows_count": None,
                        "media_count": None,
                    },
                    "id": "self123",
                },
            )
        )
        snap = await graph_api.fetch_competitor_snapshot(
            "natgeo", ig_user_id="self123", access_token="tok"
        )
    assert snap is not None  # did not raise
    assert snap["follower_count"] == 0
    assert snap["following_count"] == 0
    assert snap["posts_count"] == 0


@pytest.mark.asyncio
async def test_competitor_snapshot_sanitizes_handle() -> None:
    # A handle carrying field-spec grammar chars ')' / '{' must be whitelisted to
    # the IG-username charset BEFORE interpolation, so it can't corrupt/inject the
    # business_discovery query.
    captured: dict = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["fields"] = request.url.params.get("fields", "")
        return httpx.Response(200, json={"business_discovery": {"id": "1", "username": "natgeo"}, "id": "self123"})

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(side_effect=_capture)
        await graph_api.fetch_competitor_snapshot(
            "@nat)geo{evil}", ig_user_id="self123", access_token="tok"
        )
    assert "business_discovery.username(natgeoevil)" in captured["fields"]
    assert ")" not in captured["fields"].split("username(")[1].split(")")[0]


@pytest.mark.asyncio
async def test_competitor_recent_posts_success() -> None:
    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                200,
                json={
                    "business_discovery": {
                        "media": {
                            "data": [
                                {"id": "p1", "caption": "Reel A", "media_type": "VIDEO",
                                 "media_product_type": "REELS", "view_count": 7757,
                                 "like_count": 100, "comments_count": 5, "permalink": "https://ig/p1"},
                                {"id": "p2", "caption": "Photo B", "media_type": "IMAGE",
                                 "like_count": 40, "comments_count": 2},
                            ]
                        }
                    },
                    "id": "self123",
                },
            )
        )
        posts = await graph_api.fetch_competitor_recent_posts(
            "@natgeo", ig_user_id="self123", access_token="tok", limit=12
        )
    assert len(posts) == 2
    assert posts[0]["id"] == "p1"
    assert posts[0]["like_count"] == 100
    assert posts[0]["media_type"] == "VIDEO"
    # Official Reels views land as int; photos (no view_count key) coerce to 0.
    assert posts[0]["view_count"] == 7757
    assert posts[1]["view_count"] == 0


@pytest.mark.asyncio
async def test_competitor_recent_posts_retries_without_view_count() -> None:
    # A Graph deployment that rejects the view_count field (error #100 names the
    # offending field) must not lose the whole grid — one retry WITHOUT it.
    seen_fields: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        fields = request.url.params.get("fields", "")
        seen_fields.append(fields)
        if "view_count" in fields:
            return httpx.Response(
                400,
                json={"error": {"message": "(#100) Tried accessing nonexisting field (view_count)", "code": 100}},
            )
        return httpx.Response(
            200,
            json={
                "business_discovery": {
                    "media": {"data": [{"id": "p1", "media_type": "VIDEO", "like_count": 9, "comments_count": 1}]}
                },
                "id": "self123",
            },
        )

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(side_effect=_handler)
        posts = await graph_api.fetch_competitor_recent_posts(
            "natgeo", ig_user_id="self123", access_token="tok"
        )
    assert len(seen_fields) == 2
    assert "view_count" in seen_fields[0]
    assert "view_count" not in seen_fields[1]
    assert len(posts) == 1
    assert posts[0]["view_count"] == 0  # field absent → coerced, not KeyError


@pytest.mark.asyncio
async def test_competitor_recent_posts_failsoft_on_error() -> None:
    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(400, json={"error": {"message": "nope"}})
        )
        assert await graph_api.fetch_competitor_recent_posts(
            "x", ig_user_id="self123", access_token="tok"
        ) == []


@pytest.mark.asyncio
async def test_competitor_recent_posts_empty_inputs() -> None:
    assert await graph_api.fetch_competitor_recent_posts("  ", ig_user_id="self123", access_token="t") == []
    assert await graph_api.fetch_competitor_recent_posts("natgeo", ig_user_id="", access_token="t") == []


def test_graph_error_classification() -> None:
    # Rate-limit codes are distinguished from a genuinely unreadable handle so
    # callers don't advise "fix your seed list" for throttling.
    assert graph_api._is_rate_limited('{"error":{"code":4,"message":"limit"}}')
    assert graph_api._is_rate_limited('{"error":{"code":80004}}')
    assert not graph_api._is_rate_limited('{"error":{"code":110,"message":"not found"}}')
    assert not graph_api._is_rate_limited("not json at all")
    code, sub, msg = graph_api._graph_error('{"error":{"code":110,"error_subcode":2207013,"message":"gone"}}')
    assert code == 110 and sub == 2207013 and msg == "gone"


@pytest.mark.asyncio
async def test_competitor_recent_posts_raises_on_rate_limit(monkeypatch) -> None:
    # A throttled call (code 4) must raise GraphRateLimited, NOT fail-soft to [],
    # so curated-anchor callers can tell "Meta throttled us" from "dead handle".
    monkeypatch.setattr(graph_api.telegram, "send", lambda *_a, **_k: None)
    monkeypatch.setattr(graph_api, "_RATE_LIMIT_ALERT_AT", 0.0)
    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                400, json={"error": {"code": 4, "message": "Application request limit reached"}}
            )
        )
        with pytest.raises(graph_api.GraphRateLimited):
            await graph_api.fetch_competitor_recent_posts(
                "cristiano", ig_user_id="self123", access_token="tok"
            )

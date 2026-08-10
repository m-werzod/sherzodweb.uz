"""Competitor tracker: source preference + dedup. The follower count must come
from the OFFICIAL business_discovery edge first (scrape-free, scalable), fall back
to instagrapi only if configured, and NEVER be fabricated when nothing is set.
Many tenants tracking one handle must cost ONE fetch, not N (rate-limit safety)."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.workers import competitor_tracker as ct

# ── _group_by_handle (pure dedup) ───────────────────────────────────────────


def test_group_by_handle_dedups_case_and_at_sign() -> None:
    rows = [
        {"id": "1", "handle": "@natgeo", "followers": 10},
        {"id": "2", "handle": "natgeo", "followers": 20},
        {"id": "3", "handle": "NATGEO", "followers": 30},
        {"id": "4", "handle": "nasa", "followers": 5},
        {"id": "5", "handle": "  ", "followers": 0},  # blank → skipped
    ]
    groups = ct._group_by_handle(rows)
    assert set(groups.keys()) == {"natgeo", "nasa"}
    assert len(groups["natgeo"]) == 3  # all three variants collapse to one fetch
    assert len(groups["nasa"]) == 1


# ── _fetch_follower_count (source preference) ───────────────────────────────


@pytest.mark.asyncio
async def test_prefers_business_discovery_over_instagrapi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IG_GRAPH_SERVICE_TOKEN", "tok")
    monkeypatch.setenv("IG_GRAPH_SERVICE_USER_ID", "self123")
    monkeypatch.setenv("IG_SCRAPER_ACCOUNTS", '[{"username":"x"}]')  # also set, must NOT be used
    bd = AsyncMock(return_value={"follower_count": 4242})
    insta = AsyncMock(return_value={"follower_count": 9999})
    monkeypatch.setattr(ct.graph_api, "fetch_competitor_snapshot", bd)
    monkeypatch.setattr(ct.instagrapi_client, "fetch_profile", insta)

    assert await ct._fetch_follower_count("@natgeo") == 4242
    bd.assert_awaited_once()
    insta.assert_not_awaited()  # official path won → no scrape


@pytest.mark.asyncio
async def test_falls_back_to_instagrapi_when_bd_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IG_GRAPH_SERVICE_TOKEN", "tok")
    monkeypatch.setenv("IG_GRAPH_SERVICE_USER_ID", "self123")
    monkeypatch.setenv("IG_SCRAPER_ACCOUNTS", '[{"username":"x"}]')
    monkeypatch.setattr(ct.graph_api, "fetch_competitor_snapshot", AsyncMock(return_value=None))
    monkeypatch.setattr(ct.instagrapi_client, "fetch_profile", AsyncMock(return_value={"follower_count": 777}))

    assert await ct._fetch_follower_count("natgeo") == 777


@pytest.mark.asyncio
async def test_instagrapi_only_when_no_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IG_GRAPH_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("IG_GRAPH_SERVICE_USER_ID", raising=False)
    monkeypatch.setenv("IG_SCRAPER_ACCOUNTS", '[{"username":"x"}]')
    bd = AsyncMock(return_value={"follower_count": 1})
    monkeypatch.setattr(ct.graph_api, "fetch_competitor_snapshot", bd)
    monkeypatch.setattr(ct.instagrapi_client, "fetch_profile", AsyncMock(return_value={"follower_count": 555}))

    assert await ct._fetch_follower_count("natgeo") == 555
    bd.assert_not_awaited()  # no service token → business_discovery skipped


@pytest.mark.asyncio
async def test_returns_none_when_nothing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # No fabrication: neither source configured → None (caller leaves row untouched).
    monkeypatch.delenv("IG_GRAPH_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("IG_GRAPH_SERVICE_USER_ID", raising=False)
    monkeypatch.delenv("IG_SCRAPER_ACCOUNTS", raising=False)
    assert await ct._fetch_follower_count("natgeo") is None


@pytest.mark.asyncio
async def test_empty_handle_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IG_GRAPH_SERVICE_TOKEN", "tok")
    monkeypatch.setenv("IG_GRAPH_SERVICE_USER_ID", "self123")
    assert await ct._fetch_follower_count("  ") is None


@pytest.mark.asyncio
async def test_bd_zero_count_falls_through_not_clobber(monkeypatch: pytest.MonkeyPatch) -> None:
    # business_discovery returning 0 (parse glitch / empty) must NOT be written —
    # fall through to instagrapi rather than zero the row.
    monkeypatch.setenv("IG_GRAPH_SERVICE_TOKEN", "tok")
    monkeypatch.setenv("IG_GRAPH_SERVICE_USER_ID", "self123")
    monkeypatch.setenv("IG_SCRAPER_ACCOUNTS", '[{"username":"x"}]')
    monkeypatch.setattr(ct.graph_api, "fetch_competitor_snapshot", AsyncMock(return_value={"follower_count": 0}))
    monkeypatch.setattr(ct.instagrapi_client, "fetch_profile", AsyncMock(return_value={"follower_count": 888}))
    assert await ct._fetch_follower_count("natgeo") == 888


@pytest.mark.asyncio
async def test_instagrapi_zero_stub_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # instagrapi's follower_count=0 STUB (session unavailable) is no-data, not a real
    # 0 — must return None so the dedup fan-out can't zero a handle for every tenant.
    monkeypatch.delenv("IG_GRAPH_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("IG_GRAPH_SERVICE_USER_ID", raising=False)
    monkeypatch.setenv("IG_SCRAPER_ACCOUNTS", '[{"username":"x"}]')
    monkeypatch.setattr(ct.instagrapi_client, "fetch_profile", AsyncMock(return_value={"follower_count": 0}))
    assert await ct._fetch_follower_count("natgeo") is None


@pytest.mark.asyncio
async def test_refresh_all_paces_every_handle_even_on_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # The rate-limit jitter must run on EVERY handle — including the unreadable ones
    # (each still cost a business_discovery call). Regression guard: a `continue`
    # used to skip the sleep on the (common) None path → unpaced burst.
    monkeypatch.setattr(
        ct, "_all_competitors",
        AsyncMock(return_value=[
            {"id": "1", "handle": "a", "followers": 0},
            {"id": "2", "handle": "b", "followers": 0},
        ]),
    )
    monkeypatch.setattr(ct, "_fetch_follower_count", AsyncMock(return_value=None))  # all unreadable
    apply_mock = AsyncMock()
    monkeypatch.setattr(ct, "_apply", apply_mock)
    monkeypatch.setattr(ct.telegram, "send", lambda *a, **k: None)
    sleep_mock = AsyncMock()
    monkeypatch.setattr(ct.asyncio, "sleep", sleep_mock)

    await ct.refresh_all()

    assert apply_mock.await_count == 0  # nothing fetched → no writes (no fabrication)
    assert sleep_mock.await_count == 2  # but BOTH handles were paced

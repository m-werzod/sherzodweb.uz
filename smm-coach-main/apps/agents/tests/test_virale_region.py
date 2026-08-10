"""Virale region grid — the "O'zbekiston bo'yicha top" tab must stay
niche-AGNOSTIC. business_discovery drops dead/personal handles SILENTLY, so a
rotted anchor list used to collapse the region grid into the cross-tenant pool
(= one tenant's competitors on a young deployment) and both Virale tabs
rendered identical content. These tests lock in the post-fetch top-up wave
that prevents that collapse."""
from __future__ import annotations

import re

import httpx
import pytest
import respx

from app.api import scrape
from app.api.scrape import (
    CompetitorMediaRequest,
    _compute_competitor_media,
    _virale_cache_key,
    competitor_media,
)


def _handle_from_fields(request: httpx.Request) -> str:
    m = re.search(r"business_discovery\.username\(([^)]*)\)", request.url.params.get("fields", ""))
    return m.group(1) if m else ""


def _reel(handle: str, idx: int, views: int) -> dict:
    return {
        "id": f"{handle}-{idx}",
        "caption": f"reel {idx}",
        "media_type": "VIDEO",
        "media_product_type": "REELS",
        "like_count": 10,
        "comments_count": 1,
        "view_count": views,  # official views present → playwright gap-fill skipped
        "permalink": f"https://www.instagram.com/reel/{handle}{idx}/",
    }


def _bd_response(handle: str, alive: set[str], views: dict[str, int]) -> httpx.Response:
    if handle not in alive:
        # business_discovery 400s for non-professional/nonexistent handles.
        return httpx.Response(400, json={"error": {"message": "Cannot find user", "code": 110}})
    v = views.get(handle, 1000)
    return httpx.Response(
        200,
        json={
            "business_discovery": {"media": {"data": [_reel(handle, i, v - i) for i in range(3)]}},
            "id": "self123",
        },
    )


@pytest.fixture()
def _service_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IG_GRAPH_SERVICE_TOKEN", "tok")
    monkeypatch.setenv("IG_GRAPH_SERVICE_USER_ID", "self123")
    monkeypatch.delenv("IG_SCRAPER_ACCOUNTS", raising=False)
    monkeypatch.delenv("VIRALE_REGION_SEED_HANDLES", raising=False)
    monkeypatch.setattr(scrape.telegram, "send", lambda *_a, **_k: None)
    # The dead-anchor alert is throttled via module state — reset per test.
    monkeypatch.setattr(scrape, "_DEAD_SEED_ALERT_AT", {})


@pytest.mark.asyncio
async def test_region_dead_anchors_trigger_discovery_topup(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """Every curated anchor dead + only the tenant pool resolving → the top-up
    wave must fetch web-discovered region accounts instead of silently shipping
    a pool-only (= niche-identical) grid, and the dead anchors must be alerted."""
    seeds = [f"deadseed{i}" for i in range(8)]
    pool = ["tenant_comp1", "tenant_comp2"]
    alive = {*pool, "megablogger"}
    views = {"megablogger": 1_000_000, "tenant_comp1": 500_000, "tenant_comp2": 100_000}

    monkeypatch.setattr(scrape, "_region_seed_handles", lambda: list(seeds))

    async def _pool(_limit: int) -> list[str]:
        return list(pool)

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    alerts: list[str] = []
    monkeypatch.setattr(scrape.telegram, "send", lambda msg, *_a, **_k: alerts.append(msg))

    async def _discover(niche: str, region: str, *, limit: int = 8) -> list[dict]:
        return [{"handle": "megablogger", "source_url": "", "discovered": True}]

    from app.graphs.nodes import competitor_intel

    monkeypatch.setattr(competitor_intel, "_discover_competitors_web", _discover)

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _bd_response(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="region", region="uz", force_refresh=True),
            prev_views={},
        )

    grid_handles = {p["handle"] for p in result["posts"]}
    assert "megablogger" in grid_handles  # discovery content made the grid
    assert result["posts"][0]["handle"] == "megablogger"  # ranked by views, region top leads
    assert any("anchor" in a for a in alerts)  # dead-anchor rot is operator-visible


@pytest.mark.asyncio
async def test_region_healthy_anchors_dominate_and_skip_discovery(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """All anchors resolving → no discovery wave, and the grid is the TRUE
    top-N by views: low-view tenant-pool posts get NO slot (the old round-robin
    guaranteed every handle a card, pushing 50K-view posts into a grid that had
    million-view candidates sitting cut)."""
    seeds = [f"anchor{i}" for i in range(10)]
    pool = ["tenant_comp1", "tenant_comp2", "tenant_comp3"]
    alive = set(seeds) | set(pool)
    views = {h: 2_000_000 - i * 10_000 for i, h in enumerate(seeds)}
    views |= {h: 50_000 for h in pool}  # realistic: tenant competitors are small

    monkeypatch.setattr(scrape, "_region_seed_handles", lambda: list(seeds))

    async def _pool(_limit: int) -> list[str]:
        return list(pool)

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    discovery_calls: list[str] = []

    async def _discover(niche: str, region: str, *, limit: int = 8) -> list[dict]:
        discovery_calls.append(niche)
        return []

    from app.graphs.nodes import competitor_intel

    monkeypatch.setattr(competitor_intel, "_discover_competitors_web", _discover)

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _bd_response(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="region", region="uz"), prev_views={}
        )

    assert discovery_calls == []  # healthy first wave → no top-up
    grid_views = [p["views"] for p in result["posts"]]
    assert grid_views == sorted(grid_views, reverse=True)  # strictly most-viewed first
    # Million-view anchor posts fill the grid; 50K pool posts are pushed out.
    assert all(not p["handle"].startswith("tenant_comp") for p in result["posts"])
    assert len(result["posts"]) == 15


@pytest.mark.asyncio
async def test_region_partial_anchor_rot_still_tops_up_and_alerts(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """Half-dead anchor spine + fully-alive tenant pool → a TOTAL-count gate
    would pass silently while half the shared grid is one tenant's niche. The
    anchor-count gate must still trigger the top-up, and the dead anchors must
    be alerted even though the grid isn't empty."""
    seeds = [f"anchor{i}" for i in range(8)]
    pool = [f"tenant_comp{i}" for i in range(4)]
    alive = set(seeds[:4]) | set(pool) | {"megablogger"}
    views = {"megablogger": 1_000_000}

    monkeypatch.setattr(scrape, "_region_seed_handles", lambda: list(seeds))

    async def _pool(_limit: int) -> list[str]:
        return list(pool)

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    alerts: list[str] = []
    monkeypatch.setattr(scrape.telegram, "send", lambda msg, *_a, **_k: alerts.append(msg))

    discovery_calls: list[str] = []

    async def _discover(niche: str, region: str, *, limit: int = 8) -> list[dict]:
        discovery_calls.append(niche)
        return [{"handle": "megablogger", "source_url": "", "discovered": True}]

    from app.graphs.nodes import competitor_intel

    monkeypatch.setattr(competitor_intel, "_discover_competitors_web", _discover)

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _bd_response(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="region", region="uz", force_refresh=True),
            prev_views={},
        )

    assert len(discovery_calls) == 1  # 4 alive anchors < gate → top-up ran
    assert "megablogger" in {p["handle"] for p in result["posts"]}
    assert any("anchor4" in a for a in alerts)  # partial rot is operator-visible


@pytest.mark.asyncio
async def test_region_default_seed_list_leaves_room_for_discovery(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """REGRESSION (found in review): with the real 20-entry default seed list all
    dead, the 12 leftover backup anchors used to fill wave2 completely and every
    discovered handle was silently dropped — the grid collapsed back into the
    tenant pool. Wave2 must reserve slots so discovery content reaches the grid."""
    pool = ["tenant_comp1", "tenant_comp2"]
    alive = {*pool, "megablogger"}
    views = {"megablogger": 2_000_000, "tenant_comp1": 500_000, "tenant_comp2": 100_000}

    # NO _region_seed_handles monkeypatch — the shipped _DEFAULT_REGION_SEED runs.
    async def _pool(_limit: int) -> list[str]:
        return list(pool)

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    async def _discover(niche: str, region: str, *, limit: int = 8) -> list[dict]:
        return [{"handle": "megablogger", "source_url": "", "discovered": True}]

    from app.graphs.nodes import competitor_intel

    monkeypatch.setattr(competitor_intel, "_discover_competitors_web", _discover)

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _bd_response(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="region", region="uz", force_refresh=True),
            prev_views={},
        )

    grid_handles = {p["handle"] for p in result["posts"]}
    assert "megablogger" in grid_handles  # discovery survived the 20-seed wave2
    assert grid_handles != set(pool)  # NOT the pool-only (niche-identical) grid


@pytest.mark.asyncio
async def test_region_interactive_cold_miss_skips_discovery(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """A user-facing cold miss (force_refresh=False) runs under the web-side 90s
    ceiling — the top-up wave still fetches the verified backup anchors but must
    NOT spend up to 60s on web discovery (that's the worker's job)."""
    seeds = [f"anchor{i}" for i in range(10)]
    pool = ["tenant_comp1"]
    alive = {"anchor8", "anchor9", "tenant_comp1"}  # spine dead, backups alive
    views = {"anchor8": 800_000, "anchor9": 700_000, "tenant_comp1": 100_000}

    monkeypatch.setattr(scrape, "_region_seed_handles", lambda: list(seeds))

    async def _pool(_limit: int) -> list[str]:
        return list(pool)

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    discovery_calls: list[str] = []

    async def _discover(niche: str, region: str, *, limit: int = 8) -> list[dict]:
        discovery_calls.append(niche)
        return []

    from app.graphs.nodes import competitor_intel

    monkeypatch.setattr(competitor_intel, "_discover_competitors_web", _discover)

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _bd_response(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="region", region="uz"), prev_views={}
        )

    assert discovery_calls == []  # interactive path never burns discovery time
    grid_handles = {p["handle"] for p in result["posts"]}
    assert {"anchor8", "anchor9"} <= grid_handles  # backup anchors still rescued


@pytest.mark.asyncio
async def test_region_worker_discovery_is_primary_even_when_anchors_healthy(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """Discovery is now the PRIMARY source: the twice-daily worker (force_refresh
    =True) must ALWAYS discover fresh accounts — not only when the curated anchors
    rot — so the grid reflects who is viral NOW, not a static list. A discovered
    account with the highest views must outrank the healthy seed anchors."""
    seeds = [f"anchor{i}" for i in range(8)]
    alive = {*seeds, "freshviral"}
    views = {h: 100_000 for h in seeds}
    views["freshviral"] = 5_000_000  # the discovered account is the real top

    monkeypatch.setattr(scrape, "_region_seed_handles", lambda: list(seeds))

    async def _pool(_limit: int) -> list[str]:
        return []

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    discovery_calls: list[str] = []

    async def _discover(niche: str, region: str, *, limit: int = 8) -> list[dict]:
        discovery_calls.append(niche)
        return [{"handle": "freshviral", "source_url": "", "discovered": True}]

    from app.graphs.nodes import competitor_intel

    monkeypatch.setattr(competitor_intel, "_discover_competitors_web", _discover)

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _bd_response(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="region", region="uz", force_refresh=True),
            prev_views={},
        )

    assert len(discovery_calls) == 1  # discovery ran despite fully-healthy anchors
    # The discovered account is the region's real top — it must lead the grid.
    assert result["posts"][0]["handle"] == "freshviral"
    grid_views = [p["views"] for p in result["posts"]]
    assert grid_views == sorted(grid_views, reverse=True)  # still most-viewed first


@pytest.mark.asyncio
async def test_empty_grid_reports_unreadable_reason(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """When every business_discovery call fails (dead/invalid token or missing
    access), the empty grid must carry reason='all_unreadable' so the worker's
    twice-daily summary names the cause instead of a bare '0 ta reel'."""
    gseeds = [f"star{i}" for i in range(12)]
    monkeypatch.setattr(scrape, "_global_seed_handles", lambda: list(gseeds))

    with respx.mock:
        # Every call 400s with code 110 (unreadable) — the token/access signature.
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                400, json={"error": {"message": "Cannot find user", "code": 110}}
            )
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="global"), prev_views={}
        )

    assert result["posts"] == []
    assert result.get("reason") == "all_unreadable"


@pytest.mark.asyncio
async def test_top_accounts_ranks_by_followers(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """The 'Top accounts' grid returns profile cards (name/@handle/followers/
    posts/avatar) ranked by follower count desc — built from business_discovery
    profile reads, one GET per handle."""
    seeds = [f"acc{i}" for i in range(6)]
    monkeypatch.setattr(scrape, "_region_seed_handles", lambda: list(seeds))

    async def _pool(_limit: int) -> list[str]:
        return []

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    followers = {
        "acc0": 100, "acc1": 9_000_000, "acc2": 500,
        "acc3": 3_000_000, "acc4": 50, "acc5": 7_000_000,
    }

    def _profile_response(request: httpx.Request) -> httpx.Response:
        h = _handle_from_fields(request)
        if h not in followers:
            return httpx.Response(400, json={"error": {"code": 110, "message": "no"}})
        return httpx.Response(
            200,
            json={
                "business_discovery": {
                    "id": h,
                    "username": h,
                    "name": h.upper(),
                    "followers_count": followers[h],
                    "media_count": 42,
                    "profile_picture_url": f"https://cdn/{h}.jpg",
                }
            },
        )

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(side_effect=_profile_response)
        result = await scrape._compute_top_accounts(
            CompetitorMediaRequest(mode="accounts", region="uz")
        )

    assert result["mode"] == "accounts"
    handles = [a["handle"] for a in result["accounts"]]
    assert handles[:3] == ["acc1", "acc5", "acc3"]  # strictly by followers desc
    top = result["accounts"][0]
    assert top["followers"] == 9_000_000
    assert top["name"] == "ACC1"
    assert top["posts"] == 42
    assert top["avatar_url"] == "https://cdn/acc1.jpg"
    assert top["profile_url"] == "https://instagram.com/acc1"


@pytest.mark.asyncio
async def test_global_mode_uses_global_anchors_only(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """The Global tab is ONE worldwide grid: global anchors only — the region
    pool (tenant competitors) must never be queried, let alone leak in."""
    gseeds = [f"star{i}" for i in range(12)]
    monkeypatch.setattr(scrape, "_global_seed_handles", lambda: list(gseeds))

    async def _pool(_limit: int) -> list[str]:
        raise AssertionError("region pool must not be queried in global mode")

    monkeypatch.setattr(scrape, "_region_handle_pool", _pool)

    alive = set(gseeds)
    views = {h: 10_000_000 - i * 1000 for i, h in enumerate(gseeds)}

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _bd_response(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="global"), prev_views={}
        )

    assert result["mode"] == "global"
    grid_handles = {p["handle"] for p in result["posts"]}
    assert grid_handles and grid_handles <= set(gseeds)
    grid_views = [p["views"] for p in result["posts"]]
    assert grid_views == sorted(grid_views, reverse=True)


@pytest.mark.asyncio
async def test_one_account_cannot_dominate_the_grid(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """REGRESSION (user: 'bir xil odam' — same person repeated): one prolific
    account holding the globally-highest views must NOT fill the grid. With a
    healthy pool each account contributes at most 2 posts."""
    gseeds = [f"star{i}" for i in range(12)]
    monkeypatch.setattr(scrape, "_global_seed_handles", lambda: list(gseeds))

    alive = set(gseeds)
    # star0 owns the 5 highest view counts by far; the rest are far smaller.
    views = {h: 10_000 for h in gseeds}
    views["star0"] = 9_000_000

    def _many_reels(handle: str, alive: set, views: dict) -> httpx.Response:
        if handle not in alive:
            return httpx.Response(400, json={"error": {"message": "no", "code": 110}})
        base = views.get(handle, 1000)
        # star0's posts are ALL higher than everyone else's — a flat sort would
        # let it take many slots.
        data = [_reel(handle, i, base - i) for i in range(6)]
        return httpx.Response(
            200, json={"business_discovery": {"media": {"data": data}}, "id": "self123"}
        )

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            side_effect=lambda r: _many_reels(_handle_from_fields(r), alive, views)
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="global"), prev_views={}
        )

    star0_slots = sum(1 for p in result["posts"] if p["handle"] == "star0")
    assert star0_slots <= 2  # capped — no longer "same person" spam
    grid_views = [p["views"] for p in result["posts"]]
    assert grid_views == sorted(grid_views, reverse=True)  # still most-viewed first


@pytest.mark.asyncio
async def test_rate_limited_anchors_not_reported_as_dead(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """When Graph THROTTLES us (code 4), the anchors aren't dead — the
    dead-anchor 'update your seed list' alert must NOT fire (the graph layer
    fires its own rate-limit alert instead)."""
    gseeds = [f"star{i}" for i in range(12)]
    monkeypatch.setattr(scrape, "_global_seed_handles", lambda: list(gseeds))

    from app.integrations.instagram import graph_api

    monkeypatch.setattr(graph_api, "_RATE_LIMIT_ALERT_AT", 0.0)

    alerts: list[str] = []
    monkeypatch.setattr(scrape.telegram, "send", lambda msg, *_a, **_k: alerts.append(msg))
    monkeypatch.setattr(graph_api.telegram, "send", lambda msg, *_a, **_k: alerts.append(msg))

    with respx.mock:
        # Every business_discovery call is throttled with code 4.
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                400, json={"error": {"code": 4, "message": "Application request limit reached"}}
            )
        )
        result = await _compute_competitor_media(
            CompetitorMediaRequest(mode="global"), prev_views={}
        )

    assert result["posts"] == []  # nothing fetched (all throttled)
    # The misleading "o'lik akkauntlarni yangilang" alert must NOT be sent.
    assert not any("yangilang" in a for a in alerts)
    # The correct rate-limit alert IS sent.
    assert any("rate limit" in a.lower() for a in alerts)


@pytest.mark.asyncio
async def test_rate_limited_empty_grid_backs_off_longer(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """A grid emptied by Graph rate-limiting (code 4) must be cached with the
    long ~3h backoff, NOT the 30-min empty TTL — otherwise the retry loop
    re-trips the same app-level quota every half hour (the code-4 loop)."""
    from app.integrations.instagram import graph_api

    monkeypatch.setattr(graph_api, "_RATE_LIMIT_ALERT_AT", 0.0)
    monkeypatch.setattr(graph_api.telegram, "send", lambda *_a, **_k: None)

    gseeds = [f"star{i}" for i in range(12)]
    monkeypatch.setattr(scrape, "_global_seed_handles", lambda: list(gseeds))

    captured: dict[str, object] = {}

    async def _get(_key: str) -> None:
        return None  # no previous grid cached — the empty-with-no-prev branch

    async def _set(key: str, val: dict, *, ttl_seconds: int) -> None:
        captured["ttl"] = ttl_seconds
        captured["reason"] = val.get("reason")

    monkeypatch.setattr(scrape.redis_cache, "get_json", _get)
    monkeypatch.setattr(scrape.redis_cache, "set_json", _set)

    with respx.mock:
        respx.route(method="GET", host="graph.facebook.com").mock(
            return_value=httpx.Response(
                400, json={"error": {"code": 4, "message": "Application request limit reached"}}
            )
        )
        req = CompetitorMediaRequest(mode="global")
        result = await scrape._compute_and_cache(req, _virale_cache_key(req))

    assert result["posts"] == []
    assert captured["reason"] == "rate_limited"
    assert captured["ttl"] == scrape._VIRALE_RATE_LIMIT_TTL_SEC  # ~3h, not 30 min


@pytest.mark.asyncio
async def test_boot_warm_skips_recently_computed_empty_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restart must NOT re-trigger the boot-warm refresh for a grid already
    computed (even an EMPTY one from a transient rate limit) — that's the
    crash-loop → rate-limit amplifier. _shared_cache_cold is True only when a
    grid was never computed under this cache version."""
    from app.workers import virale_refresher

    # Both shared grids present WITH a compute timestamp but empty (rate-limited).
    warmed = {
        "ok": True,
        "posts": [],
        "generated_at": "2026-07-03T14:00:00+00:00",
        "reason": "rate_limited",
    }

    async def _get_warm(_key: str) -> dict:
        return dict(warmed)

    monkeypatch.setattr(virale_refresher.redis_cache, "get_json", _get_warm)
    assert await virale_refresher._shared_cache_cold() is False  # no re-warm on restart

    # A grid never computed under this cache version (missing) → cold, warm once.
    async def _get_none(_key: str) -> None:
        return None

    monkeypatch.setattr(virale_refresher.redis_cache, "get_json", _get_none)
    assert await virale_refresher._shared_cache_cold() is True


@pytest.mark.asyncio
async def test_likes_endpoint_reranks_cached_grids(
    monkeypatch: pytest.MonkeyPatch, _service_env: None
) -> None:
    """'Top layk' = re-rank of the cached region + global grids by like count,
    deduped by post id — no third scrape fan-out, no Graph calls at all."""

    def _post(pid: str, handle: str, likes: int, views: int) -> dict:
        return {"id": pid, "handle": handle, "like_count": likes, "views": views, "engagement": likes}

    region_grid = {
        "ok": True,
        "posts": [_post("r1", "uzblogger", 500, 100_000), _post("x", "shared", 900, 50_000)],
        "generated_at": "2026-07-03T05:00:00+00:00",
    }
    global_grid = {
        "ok": True,
        "posts": [_post("g1", "cristiano", 9000, 1_000_000), _post("x", "shared", 900, 50_000)],
        "generated_at": "2026-07-03T06:00:00+00:00",
    }
    grids = {
        _virale_cache_key(CompetitorMediaRequest(mode="region", region="uz")): region_grid,
        _virale_cache_key(CompetitorMediaRequest(mode="global")): global_grid,
    }

    async def _fake_get(key: str) -> dict | None:
        return grids.get(key)

    monkeypatch.setattr(scrape.redis_cache, "get_json", _fake_get)

    with respx.mock:  # any Graph call would error — none must happen
        result = await competitor_media(CompetitorMediaRequest(mode="likes", region="uz"))

    assert [p["id"] for p in result["posts"]] == ["g1", "x", "r1"]  # by likes, deduped
    assert result["generated_at"] == "2026-07-03T06:00:00+00:00"
    assert result["mode"] == "likes"


def test_refresh_schedule_hits_0700_and_1900_tashkent() -> None:
    """The worker must tick at 07:00 and 19:00 Asia/Tashkent (02:00 / 14:00
    UTC), not "12h since boot"."""
    import datetime

    from app.workers.virale_refresher import _seconds_until_next_refresh

    def _next(hh: int, mm: int) -> datetime.datetime:
        now = datetime.datetime(2026, 7, 3, hh, mm, tzinfo=datetime.UTC)
        return now + datetime.timedelta(seconds=_seconds_until_next_refresh(now))

    # 00:30 UTC → next tick 02:00 UTC (07:00 Tashkent).
    assert _next(0, 30).hour == 2 and _next(0, 30).minute == 0
    # 09:00 UTC → next tick 14:00 UTC (19:00 Tashkent).
    assert _next(9, 0).hour == 14
    # 15:00 UTC (after both) → wraps to tomorrow 02:00 UTC.
    nxt = _next(15, 0)
    assert nxt.hour == 2 and nxt.day == 4

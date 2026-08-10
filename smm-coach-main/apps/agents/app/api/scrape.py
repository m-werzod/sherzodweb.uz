"""Public scraping endpoints — login-less profile lookups used by the web
service during signup, PLUS the voice-coach "super tools" that let the AI
coach explore any account, read any post, and analyse content via instagrapi
(+ Gemini vision). All HMAC-protected by the global middleware."""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.integrations import telegram
from app.integrations.instagram import graph_api, instagrapi_client, playwright_scraper
from app.integrations.llm import gemini_client
from app.memory import redis_cache

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = structlog.get_logger(__name__)

router = APIRouter()


class ProfileProbeRequest(BaseModel):
    handle: str = Field(..., min_length=1, max_length=60)


class RecentPost(BaseModel):
    shortcode: str
    taken_at: int = Field(alias="takenAt")  # epoch seconds

    model_config = {"populate_by_name": True}


class ProfileProbeResponse(BaseModel):
    handle: str
    followers: int = 0
    following: int = 0
    posts: int = 0
    bio: str | None = None
    avatar_url: str | None = Field(default=None, alias="avatarUrl")
    is_private: bool = Field(default=False, alias="isPrivate")
    recent_posts: list[RecentPost] = Field(default_factory=list, alias="recentPosts")
    ok: bool = False

    model_config = {"populate_by_name": True}


@router.post("/profile", response_model=ProfileProbeResponse)
async def probe_profile(req: ProfileProbeRequest) -> ProfileProbeResponse:
    """Anonymous public profile probe. Best-effort — returns ok=False when
    Instagram blocks the scrape or the profile can't be parsed; the web
    wizard then prompts the user for follower count manually.

    `recent_posts` carries (shortcode, taken_at_timestamp) pairs for the
    most recent ~30 posts (when IG embeds them in the profile HTML). The
    onboarding flow writes these as InstagramPost rows so the dashboard
    streak heatmap shows real activity immediately.
    """
    telegram.send(f"🔍 Profil tekshirilmoqda · @{req.handle.lstrip('@')}")
    result = await playwright_scraper.fetch_public_profile(req.handle)
    telegram.send(
        f"✅ Profil topildi · @{result.get('handle', req.handle)} → "
        f"{int(result.get('follower_count') or 0)} obunachi"
        if result.get("ok")
        else f"⚠️ Profilni ololmadim · @{req.handle.lstrip('@')} (IG bloklashi mumkin)"
    )
    raw_posts = result.get("recent_posts") or []
    recent = [
        RecentPost(shortcode=p["shortcode"], takenAt=int(p["taken_at"]))
        for p in raw_posts
        if isinstance(p, dict) and p.get("shortcode") and p.get("taken_at")
    ]
    return ProfileProbeResponse(
        handle=result.get("handle", req.handle),
        followers=int(result.get("follower_count") or 0),
        following=int(result.get("following_count") or 0),
        posts=int(result.get("posts_count") or 0),
        bio=result.get("bio"),
        avatarUrl=result.get("avatar_url"),
        isPrivate=bool(result.get("is_private")),
        recentPosts=recent,
        ok=bool(result.get("ok")),
    )


# ── Voice-coach super tools (instagrapi-backed) ──────────────────────────


class AccountRequest(BaseModel):
    handle: str = Field(..., min_length=1, max_length=60)
    limit: int = Field(default=12, ge=1, le=24)


class PostRequest(BaseModel):
    ref: str = Field(..., min_length=1, max_length=300)  # shortcode or URL
    comments_limit: int = Field(default=15, ge=0, le=50)


class HashtagRequest(BaseModel):
    tag: str = Field(..., min_length=1, max_length=80)
    limit: int = Field(default=12, ge=1, le=24)


class AnalyzeMediaRequest(BaseModel):
    image_url: str = Field(..., min_length=8, max_length=1000)
    question: str = Field(default="Bu post/video nima haqida? Mavzu, uslub va asosiy g'oyani qisqacha tushuntir.")


@router.post("/account")
async def scrape_account(req: AccountRequest) -> dict[str, Any]:
    """Profile + recent posts for ANY public account (voice: 'look at @x')."""
    telegram.send(f"👀 Akkaunt ko'rilmoqda · @{req.handle.lstrip('@')} · oxirgi {req.limit} post")
    return await instagrapi_client.fetch_account_overview(req.handle, limit=req.limit)


@router.post("/post")
async def scrape_post(req: PostRequest) -> dict[str, Any]:
    """One post in full — caption, metrics, video/cover url, top comments.
    When a cover image is present we also run a quick Gemini-vision summary so
    the coach can "understand" the content, not just read the caption."""
    telegram.send(f"🎬 Post ochilmoqda · {req.ref[:60]}")
    detail = await instagrapi_client.fetch_post_detail(req.ref, comments_limit=req.comments_limit)
    cover = detail.get("thumbnail_url")
    if detail.get("ok") and cover:
        vision = await gemini_client.analyze_media(
            image_url=cover,
            question=(
                "Bu Instagram post/video muqovasi. Nima ko'rsatilgan, mavzusi nima, "
                "qanday uslub (vlog, mahsulot, ta'lim, hazil...)? 2-3 jumla o'zbekcha."
            ),
        )
        if vision:
            detail["vision_summary"] = vision
    return detail


@router.post("/hashtag")
async def scrape_hashtag(req: HashtagRequest) -> dict[str, Any]:
    """Top posts for a hashtag (voice: 'what's trending in #x')."""
    telegram.send(f"#️⃣ Hashtag qidirilmoqda · #{req.tag.lstrip('#')}")
    return await instagrapi_client.fetch_hashtag_posts(req.tag, limit=req.limit)


@router.post("/analyze-media")
async def analyze_media(req: AnalyzeMediaRequest) -> dict[str, Any]:
    """Standalone Gemini-vision call over an image URL (cover/thumbnail)."""
    telegram.send("🖼 Rasm AI ko'zi bilan tahlil qilinmoqda")
    summary = await gemini_client.analyze_media(image_url=req.image_url, question=req.question)
    return {"ok": bool(summary), "summary": summary}


# ── Virale — top competitor content: business_discovery base + instagrapi views ──


class CompetitorMediaRequest(BaseModel):
    handles: list[str] = Field(default_factory=list)
    # When no handles are tracked yet, discover top accounts for this niche on
    # the fly (web_search: Tavily or Gemini grounding) and seed them.
    niche: str | None = None
    region: str = "uz"
    tenant_id: str | None = None
    # Sampling depth PER handle before ranking; the grid shows the global top.
    # Default = the API max: "eng ko'p ko'rilgan" must sample deep enough per
    # account to catch viral outliers, and the worker + web write the SAME
    # cache key — a lower default on one path would silently overwrite the
    # other's deeper grid every 12h (business_discovery is one GET per handle
    # regardless of media.limit, so depth is quota-free).
    per_handle: int = Field(default=25, ge=1, le=25)
    # Total posts returned (global top across all handles) — NOT per handle.
    top: int = Field(default=15, ge=1, le=150)
    # 'niche' → the tenant's own competitor pool (+ niche web-discovery).
    # 'region' → cross-tenant top accounts of the region, reels preferred; the
    # grid is IDENTICAL for every tenant in the region (shared cache entry).
    # 'global' → the world's biggest reels accounts, no region/tenant coloring.
    # 'likes' → re-rank of the region+global grids by like count (no scraping).
    # 'accounts' → top region ACCOUNTS ranked by follower count (profile cards:
    #   avatar/name/@handle/followers/posts), NOT posts. Shared per region.
    mode: Literal["niche", "region", "global", "likes", "accounts"] = "niche"
    # Worker pre-warm: recompute even when a cached grid exists (still rewrites
    # the cache, and gets more generous scrape timeouts — nobody is waiting).
    # No-op for mode='likes' (a cache-less re-rank of the region+global grids).
    force_refresh: bool = False


# The virale_refresher worker rewrites entries every 12h ("twice a day"); the TTL
# only exists so a dead worker can't serve week-old grids forever — 26h leaves a
# 2h grace past one missed tick before a user request recomputes on demand.
_VIRALE_CACHE_TTL_SEC = 26 * 60 * 60
# Empty grids (discovery misfired / thin pool) retry sooner instead of pinning a
# blank page for a whole day.
_VIRALE_EMPTY_TTL_SEC = 30 * 60
# A rate-limited (Graph code 4) empty grid must back off MUCH longer than a
# genuinely-empty one: retrying in 30 min just re-trips the same app-level quota
# — the code-4 loop. ~3h lets the quota recover while interactive misses serve
# the cached empty grid instead of recomputing (matches graph_api's 3h alert
# throttle).
_VIRALE_RATE_LIMIT_TTL_SEC = 3 * 60 * 60
# Dead-anchor Telegram nudges are throttled PER MODE (region rot must not
# starve the global-rot alert that names a different env var): the 30-min
# empty-TTL retry loop would otherwise re-alert on every user page view
# (~48/day) for the same rot. The structlog warning still fires every compute.
_DEAD_SEED_ALERT_AT: dict[str, float] = {}  # mode → monotonic secs of last alert
_DEAD_SEED_ALERT_THROTTLE_S = 24 * 3600
# Concurrent cache misses for the same key share ONE compute (page refresh spam
# during a cold 60-90s scrape must not fan out into parallel scrapes).
_inflight: dict[str, asyncio.Task[dict[str, Any]]] = {}


def _virale_cache_key(req: CompetitorMediaRequest) -> str:
    if req.mode == "likes":
        # Deliberately cache-less: likes is a re-rank of the region+global
        # grids (_likes_grid). Falling through would return the tenant's NICHE
        # key and a compute under it would poison that cache entry.
        raise ValueError("mode='likes' has no cache key — served by _likes_grid")
    region = (req.region or "uz").strip().lower()
    # v3: bumped when the ranking/anchor logic changes so a deploy invalidates
    # every stale grid at once (the boot warm then rewrites them) instead of
    # serving the old shape until the 26h TTL lapses. v3 = region/global grids
    # are now discovery-driven (dynamic web discovery is the primary candidate
    # source; the curated seed lists are only a reliability floor).
    if req.mode == "global":
        return "virale:v3:global"  # one worldwide grid, no region/tenant coloring
    if req.mode == "region":
        return f"virale:v3:region:{region}"
    if req.mode == "accounts":
        return f"virale:v3:accounts:{region}"  # top region accounts by followers
    if req.tenant_id:
        return f"virale:v3:niche:{req.tenant_id}:{region}"
    # No tenant (ad-hoc caller) — key by the request shape itself.
    basis = "|".join(sorted(h.lower() for h in req.handles)) + ":" + (req.niche or "")
    # sha1 is a cache-key digest here, not a security primitive.
    return f"virale:v3:niche:{hashlib.sha1(basis.encode()).hexdigest()[:16]}:{region}"  # noqa: S324


# Niche-AGNOSTIC anchor for the region grid — well-known large Uzbek
# business/creator accounts that post reels. This is what makes the "O'zbekiston
# bo'yicha top" tab genuinely region-wide, DISTINCT from the niche tab (which is
# colored by the tenant's own niche + competitors). business_discovery silently
# drops any handle that isn't a resolvable business/creator account, so a stale
# entry just contributes nothing — the post-fetch top-up wave fills the gap and
# alerts on dead anchors.
_DEFAULT_REGION_SEED = [
    # Every username individually WEB-VERIFIED against the live account
    # (2026-07-03) — the previous list was guessed and only 1 of its 10 handles
    # survived verification, which silently collapsed the region grid into one
    # tenant's competitor pool (the "both tabs identical" bug). Ordered mega-creators
    # first (the region's actual most-VIEWED reels) and CROSS-CATEGORY (music /
    # comedy / lifestyle / food / sport) — the first 8 are the wave-1 spine, so
    # a single-category run would make the region tab mirror that category.
    "munisarizaeva",           # music · 7.9M
    "jahongir_xojayev",        # comedy (SARIQ BOLA) · 6.3M
    "shaxzoda__muxammedova",   # lifestyle · 6.5M
    "jamshid_jamshidd",        # comedy/prank · 6M
    "asalshodieva",            # actress/lifestyle · 5.6M
    "dadosh_bro",              # comedy/business · 5.3M
    "tass_cooking",            # food · 2.3M
    "abdukodir_khusanov_",     # football (Man City) · 2.3M
    # Wave-2 backups — fetched only when the spine comes back thin.
    "obidjon_nasriddinov",     # comedy · 5.7M
    "luiza_rasulova",          # actress · 5.3M
    "rayhonganieva",           # music · 5.1M
    "mitti.me",                # comedy · 4.6M
    "ziyodamusic",             # music · 4.4M
    "bek_vines",               # comedy · 3.8M
    "shukurullohdomla",        # education/religion · 3.1M
    "jaloliddin_ahmadaliyev",  # music · 1M
    "uzum.market",             # marketplace · 528K
    "artel_official",          # electronics · 870K
    "korzinkauz",              # grocery retail · 328K
    "bellissimouz",            # fast food · 256K
]


def _region_seed_handles() -> list[str]:
    """Curated top-UZ anchor handles. Operator-editable via
    VIRALE_REGION_SEED_HANDLES (comma-separated) so the real top accounts can be
    tuned per deployment without a code change."""
    env = os.getenv("VIRALE_REGION_SEED_HANDLES", "")
    if env.strip():
        return [h.strip().lstrip("@") for h in env.split(",") if h.strip()]
    return list(_DEFAULT_REGION_SEED)


# The "Global" tab's anchor — the world's biggest reels accounts. Every
# username individually WEB-VERIFIED (2026-07-03), same discipline as the
# region list (business_discovery silently drops bad handles). Viral-reels
# heavyweights first and CROSS-CATEGORY; the first 12 are the wave-1 spine.
_DEFAULT_GLOBAL_SEED = [
    "cristiano",       # football · 670M
    "khaby00",         # comedy (Khaby Lame) · 80M
    "leomessi",        # football · 511M
    "zachking",        # magic/entertainment · 30M
    "mrbeast",         # entertainment · 88M
    "therock",         # entertainment · 382M
    "cznburak",        # food (CZN Burak) · 51M
    "selenagomez",     # music/lifestyle · 405M
    "neymarjr",        # football · 230M
    "nusr_et",         # food (Salt Bae) · 50M
    "kyliejenner",     # lifestyle · 382M
    "virat.kohli",     # cricket · 273M
    # Wave-2 backups — fetched only when the spine comes back thin.
    "kimkardashian",   # lifestyle · 344M
    "arianagrande",    # music · 363M
    "kevinhart4real",  # comedy · 172M
    "kingjames",       # basketball · 154M
    "shakira",         # music · 99M
    "taylorswift",     # music · 273M
    "gordongram",      # food (Gordon Ramsay) · 19M
    "nasa",            # science · 104M
]


def _global_seed_handles() -> list[str]:
    """Curated worldwide anchor handles for the Global tab. Operator-editable
    via VIRALE_GLOBAL_SEED_HANDLES (comma-separated)."""
    env = os.getenv("VIRALE_GLOBAL_SEED_HANDLES", "")
    if env.strip():
        return [h.strip().lstrip("@") for h in env.split(",") if h.strip()]
    return list(_DEFAULT_GLOBAL_SEED)


async def _region_handle_pool(limit: int) -> list[str]:
    """Cross-tenant pool of REAL Uzbekistan accounts, ranked by follower count:
    the UNION of every tenant's tracked competitors AND the platform's own
    connected Instagram accounts (public, established). This is the most authentic
    "accounts in this region" signal — on a young single-niche deployment the
    curated anchors carry the breadth, but as tenants spread across niches this
    pool becomes the region's real top. Best-effort → [] on any error."""
    try:
        from sqlalchemy import text

        from app.memory.db import get_sessionmaker

        sm = get_sessionmaker()
        async with sm() as session:
            rows = await session.execute(
                text(
                    """
                    SELECT handle, MAX(followers) AS followers
                    FROM (
                        SELECT handle, followers FROM competitor_tracks
                        UNION ALL
                        SELECT handle, "followerCount" AS followers
                        FROM instagram_accounts
                        WHERE "isPrivate" = false AND "followerCount" >= 10000
                    ) region_pool
                    GROUP BY handle
                    ORDER BY MAX(followers) DESC NULLS LAST
                    LIMIT :lim
                    """
                ),
                {"lim": limit},
            )
            return [str(r["handle"]) for r in rows.mappings().all()]
    except Exception as exc:  # noqa: BLE001 — pool is best-effort
        log.warning("competitor_media.region_pool_failed", error=repr(exc)[:120])
        return []


async def _discover_anchor_handles(req: CompetitorMediaRequest) -> list[str]:
    """Dynamic region/global discovery — the PRIMARY candidate source for the
    shared grids on the twice-daily worker refresh. web_search (Tavily/Gemini
    grounding) surfaces the accounts trending NOW, so the grid isn't pinned to a
    hand-maintained seed list (the owner's ask: discover accounts on the fly,
    don't hardcode them). Region uses a geo-scoped Uzbek query; global uses a
    niche-agnostic worldwide query with an EMPTY region so no "Toshkent" geo
    terms leak onto a worldwide search. Returns the discovered handles, [] when
    no search provider is configured or on any error (the curated seed floor then
    carries the grid). Called worker-side only (force_refresh): the ~60s search
    doesn't fit the interactive 90s ceiling."""
    query, disc_region = (
        ("eng mashhur va ko'p obunachili instagram bloggerlari", req.region or "uz")
        if req.mode in ("region", "accounts")
        else ("most followed instagram accounts reels creators", "")
    )
    try:
        from app.graphs.nodes.competitor_intel import _discover_competitors_web

        discovered = await asyncio.wait_for(
            _discover_competitors_web(query, disc_region, limit=20), timeout=60
        )
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort
        log.warning("competitor_media.discovery_failed", mode=req.mode, error=type(exc).__name__)
        return []
    return [str(d.get("handle") or "") for d in discovered if d.get("handle")]


def _empty_grid_reason(tried: list[str], rate_limited: set[str]) -> str:
    """Coarse WHY a grid came back empty, so the worker's twice-daily Telegram
    summary can name the cause instead of a bare "0 ta reel". Ops-facing (not
    shown to end users). 'all_unreadable' is the dead-token / missing-access
    signature: every business_discovery call 400'd."""
    tried_lc = {h.lower() for h in tried}
    if not tried_lc:
        return "no_candidates"        # couldn't build a handle list at all
    if tried_lc <= rate_limited:
        return "rate_limited"         # every attempted handle was throttled
    if rate_limited:
        return "some_rate_limited"    # a mix of throttled + unreadable
    return "all_unreadable"           # every handle 400'd — dead token / no access


@router.post("/competitor-media")
async def competitor_media(req: CompetitorMediaRequest) -> dict[str, Any]:
    """Top competitor posts for the Virale grid, served from a Redis cache that
    the virale_refresher worker rewrites every 12h — a page view costs one Redis
    GET, not a 60-90s scrape fan-out. Cold misses compute once (concurrent misses
    coalesce) and write the cache. See _compute_competitor_media for how the grid
    itself is built."""
    token = os.getenv("IG_GRAPH_SERVICE_TOKEN")
    ig_uid = os.getenv("IG_GRAPH_SERVICE_USER_ID")
    if not token or not ig_uid:
        # No official token → nothing reliable to fetch. Signal the web layer so it
        # shows a truthful "configure the token" state instead of a silent blank.
        return {"ok": False, "error": "no_service_token", "posts": [], "discovered": []}

    if req.mode == "likes":
        return await _likes_grid(req)

    key = _virale_cache_key(req)
    if not req.force_refresh:
        cached = await redis_cache.get_json(key)
        if isinstance(cached, dict) and cached.get("ok"):
            cached["cached"] = True
            return cached

    # shield: a browser abort must not cancel the shared compute mid-scrape —
    # the cache write is the whole point.
    if req.mode == "accounts":
        return await asyncio.shield(start_or_join_accounts(req, key))
    return await asyncio.shield(start_or_join_compute(req, key))


async def _likes_grid(req: CompetitorMediaRequest) -> dict[str, Any]:
    """"Top layk" tab — a RE-RANK of the region + global grids by like count.
    Zero extra Graph quota and no third cache to keep warm: likes ride on the
    two anchor grids the worker already refreshes twice a day. Cold caches fall
    back to the shared computes (coalesced, shielded) like any other tab."""

    async def _grid(mode: Literal["region", "global"]) -> dict[str, Any]:
        sub = CompetitorMediaRequest(
            mode=mode, region=req.region, per_handle=req.per_handle, top=req.top
        )
        key = _virale_cache_key(sub)
        cached = await redis_cache.get_json(key)
        if isinstance(cached, dict) and cached.get("ok"):
            cached["cached"] = True
            return cached
        return await asyncio.shield(start_or_join_compute(sub, key))

    grids = await asyncio.gather(_grid("region"), _grid("global"), return_exceptions=True)
    posts: list[dict[str, Any]] = []
    generated: list[str] = []
    all_cached = True
    for sub_mode, g in zip(("region", "global"), grids, strict=True):
        if not (isinstance(g, dict) and g.get("ok")):
            # A dead sub-grid must be distinguishable from a not-yet-warm cache.
            log.warning(
                "competitor_media.likes_grid_failed", grid=sub_mode, error=repr(g)[:120]
            )
            continue
        posts.extend(g.get("posts") or [])
        if g.get("generated_at"):
            generated.append(str(g["generated_at"]))
        if not g.get("cached"):
            all_cached = False
    posts.sort(
        key=lambda p: (int(p.get("like_count") or 0), int(p.get("views") or 0)),
        reverse=True,
    )
    seen_ids: set[str] = set()
    top: list[dict[str, Any]] = []
    for p in posts:
        pid = str(p.get("id") or "")
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        top.append(p)
        if len(top) >= req.top:
            break
    return {
        "ok": True,
        "posts": top,
        "discovered": [],
        "mode": "likes",
        "generated_at": max(generated) if generated else None,
        "cached": all_cached,
    }


def _coalesce(
    key: str, factory: Callable[[], Awaitable[dict[str, Any]]]
) -> asyncio.Task[dict[str, Any]]:
    """One live compute per cache key: concurrent misses share ONE task instead
    of each firing its own scrape/Graph fan-out."""
    task = _inflight.get(key)
    if task is None:
        task = asyncio.create_task(factory())
        _inflight[key] = task
        task.add_done_callback(lambda _t, k=key: _inflight.pop(k, None))
    return task


def start_or_join_compute(
    req: CompetitorMediaRequest, key: str
) -> asyncio.Task[dict[str, Any]]:
    """One live POSTS compute per cache key, shared by the endpoint AND the
    virale_refresher worker — a user cold miss landing mid-refresh joins the
    worker's task instead of racing it with a second scrape fan-out."""
    return _coalesce(key, lambda: _compute_and_cache(req, key))


def start_or_join_accounts(
    req: CompetitorMediaRequest, key: str
) -> asyncio.Task[dict[str, Any]]:
    """Same coalescing for the 'Top accounts' grid (profile cards ranked by
    followers) — worker warm + endpoint share one compute per region key."""
    return _coalesce(key, lambda: _compute_and_cache_accounts(req, key))


async def _compute_and_cache(req: CompetitorMediaRequest, key: str) -> dict[str, Any]:
    # Carry forward last-known view counts: the view enrichment is best-effort
    # (IG blocks datacenter IPs), so a failed pass must degrade to yesterday's
    # real number, not zero the whole grid out.
    prev = await redis_cache.get_json(key)
    prev_views: dict[str, int] = {}
    if isinstance(prev, dict):
        for p in prev.get("posts") or []:
            if p.get("id") and int(p.get("views") or 0) > 0:
                prev_views[str(p["id"])] = int(p["views"])

    result = await _compute_competitor_media(req, prev_views)
    prev_had_posts = isinstance(prev, dict) and bool(prev.get("posts"))
    mode_label = {"region": "region", "global": "global"}.get(req.mode, "soha")
    if result.get("ok") and result.get("posts"):
        # No per-grid Telegram ping — the worker sends one summary per refresh.
        result["generated_at"] = datetime.now(UTC).isoformat()
        await redis_cache.set_json(key, result, ttl_seconds=_VIRALE_CACHE_TTL_SEC)
    elif result.get("ok") and not prev_had_posts:
        # Genuinely nothing to show (and nothing better cached) — cache the empty
        # grid so retries are throttled without pinning a blank page. A
        # rate-limited empty grid backs off ~3h (not 30 min) so we stop hammering
        # a throttled API every half hour; a plain-empty grid retries sooner.
        result["generated_at"] = datetime.now(UTC).isoformat()
        empty_ttl = (
            _VIRALE_RATE_LIMIT_TTL_SEC
            if result.get("reason") in ("rate_limited", "some_rate_limited")
            else _VIRALE_EMPTY_TTL_SEC
        )
        await redis_cache.set_json(key, result, ttl_seconds=empty_ttl)
    elif result.get("ok"):
        # Every handle failed (or the pool resolved empty) while a full grid sits
        # in cache — that's a transient Meta/API failure, not "no content". Keep
        # serving yesterday's grid; overwriting it would also destroy the
        # prev_views carry-forward chain for good.
        log.warning("competitor_media.empty_recompute_kept_previous", key=key)
        telegram.send(
            f"⚠️ Virale · {mode_label} · "
            "yangilanmadi (vaqtinchalik xato) — oldingi natija saqlandi"
        )
        prev["cached"] = True
        return prev
    result["cached"] = False
    return result


async def _compute_competitor_media(
    req: CompetitorMediaRequest, prev_views: dict[str, int]
) -> dict[str, Any]:
    """Build the Virale grid. The base comes from the OFFICIAL Graph API
    business_discovery edge (gated only by the service token that prod already
    plumbs) so the grid is never empty when the token is valid — including REAL
    Reels view counts via its view_count field (business_discovery-only, Meta
    changelog 2025-06-16). Two BEST-EFFORT scrape tiers gap-fill what that
    leaves at 0 (joined on shortcode): tier 1 is login-less web_profile_info (no
    scraper accounts), tier 2 is instagrapi ONLY when IG_SCRAPER_ACCOUNTS is
    configured. When no source yields a view, posts keep views=0 and rank by
    engagement. In 'niche' mode a thin handle pool is topped up by niche
    web-discovery and validated handles get seeded into competitor_tracks; in
    'region' mode the pool is the cross-tenant top of the region and the grid
    prefers reels. Diversified so one account can't fill it."""
    token = os.getenv("IG_GRAPH_SERVICE_TOKEN")
    ig_uid = os.getenv("IG_GRAPH_SERVICE_USER_ID")

    # No per-compute Telegram chatter here — the worker sends ONE summary per
    # refresh (twice a day); interactive cold misses stay silent.

    # Region probes MORE candidates: its pool handles are unvalidated for
    # business_discovery (personal accounts resolve to []) so some slots are
    # expected to die — the extra GETs are cheap (one httpx call each) and the
    # shared region grid only recomputes twice a day.
    MAX_HANDLES = 12 if req.mode in ("region", "global") else 8
    # Anchor quality gate (region/global): with fewer VALID (post-fetch) ANCHOR
    # handles than this the grid degenerates into whatever the cross-tenant pool
    # holds — on a young deployment that's ONE tenant's competitors, i.e. the
    # niche tab (the exact "both tabs identical" bug). Counting anchors, not all
    # valid handles, matters: a half-dead anchor spine plus a fully-alive tenant
    # pool would pass a total-count gate while half the shared grid is one
    # tenant's niche.
    MIN_ANCHORS = 6
    seen: set[str] = set()
    handles: list[str] = []
    handle_src: dict[str, str] = {}
    wave2: list[str] = []                    # region/global seed-floor backfill (empty otherwise)
    discovered_anchor_lc: set[str] = set()   # dynamically discovered handles (region/global)

    def _add(
        raw: str, src: str = "", *, into: list[str] | None = None, cap: int | None = None
    ) -> None:
        batch = handles if into is None else into
        limit = MAX_HANDLES if cap is None else cap
        clean = (raw or "").lstrip("@").strip()
        key = clean.lower()
        if clean and key not in seen and len(batch) < limit:
            seen.add(key)
            batch.append(clean)
            if src:
                handle_src[clean] = src

    anchor_seeds: list[str] = []
    anchor_pool: list[str] = []
    if req.mode in ("region", "global"):
        # The region/global grids are SHARED across tenants and niche-AGNOSTIC —
        # ignore req.handles. Candidate sources, in PRIORITY order:
        #   1. DYNAMIC DISCOVERY (primary) — on the twice-daily worker refresh we
        #      web-search the accounts actually trending NOW and add them FIRST,
        #      so the grid isn't pinned to a hand-maintained list (the owner's
        #      request: "o'zi qidirib chiqsin, tayyor ro'yxatdan emas"). Capped so
        #      a few curated slots always remain as a floor. Interactive cold
        #      misses (force_refresh=False) skip discovery — the ~60s search
        #      doesn't fit the web-side 90s ceiling; they lean on the
        #      worker-warmed cache + the seed floor.
        #   2. CURATED SEED FLOOR — verified anchors backfill the slots discovery
        #      left, so a noisy/empty web search can never blank the grid.
        #   3. (region only) the cross-tenant pool of REAL Uzbekistan accounts.
        #   4. a post-fetch top-up wave (below) rescues a thin grid from the seed
        #      floor — business_discovery drops dead handles SILENTLY, so seed
        #      health is only knowable after the fetch, never at build time.
        if req.mode == "region":
            anchor_seeds = _region_seed_handles()
            anchor_pool = await _region_handle_pool(MAX_HANDLES * 3)
        else:
            anchor_seeds = _global_seed_handles()
        if req.force_refresh:
            # Leave >=4 slots for the curated floor so discovery quality can't
            # blank the grid on a bad search day.
            disc_cap = max(1, MAX_HANDLES - 4)
            for h in await _discover_anchor_handles(req):
                _add(h, "discovered", cap=disc_cap)
                discovered_anchor_lc.add(h.lstrip("@").strip().lower())
        spine = anchor_seeds[:8] if req.mode == "region" else anchor_seeds[:MAX_HANDLES]
        for h in spine:
            _add(h)
        for h in anchor_pool:  # empty for global (no cross-tenant pool)
            _add(h)
    else:
        for h in req.handles:
            _add(h)

    # Thin NICHE pool → discover accounts on the fly (web_search: Tavily or
    # Gemini grounding) and add them as CANDIDATES. Time-bounded so the slow
    # sequential web_search fan-out can't push the request past the web-side 90s
    # ceiling; only accounts that actually return posts get persisted (below).
    # (Region/global already discovered up front — worker-side, force_refresh —
    # and top up from the seed floor after the fetch; see the block above.)
    if req.mode == "niche" and len(handles) < MAX_HANDLES and req.niche:
        try:
            from app.graphs.nodes.competitor_intel import _discover_competitors_web

            discovered = await asyncio.wait_for(
                _discover_competitors_web(req.niche, req.region or "uz", limit=20),
                timeout=20,
            )
            for d in discovered:
                _add(d.get("handle") or "", d.get("source_url") or "")
        except Exception as exc:  # noqa: BLE001 — discovery is best-effort
            log.warning("competitor_media.discovery_failed", error=type(exc).__name__)

    if not handles:
        return {"ok": True, "posts": [], "discovered": [], "mode": req.mode, "reason": "no_candidates"}

    # business_discovery is one cheap async httpx GET per handle (no pool lock).
    sem = asyncio.Semaphore(4)
    # Handles that failed because Graph THROTTLED us (not because they're dead) —
    # excluded from the dead-anchor classification so a rate limit never reads as
    # "these world-famous accounts don't exist, update the list".
    rate_limited: set[str] = set()

    async def one(handle: str) -> tuple[str, list[dict]]:
        # Base grid via official business_discovery (fail-soft → [] on any error).
        try:
            async with sem:
                posts = await asyncio.wait_for(
                    graph_api.fetch_competitor_recent_posts(
                        handle, ig_user_id=ig_uid, access_token=token, limit=req.per_handle
                    ),
                    timeout=20,
                )
        except graph_api.GraphRateLimited:
            rate_limited.add(handle.lower())
            return handle, []
        except Exception:  # noqa: BLE001 — timeout / transport error → skip handle
            return handle, []
        out: list[dict] = []
        for m in posts:
            likes = int(m.get("like_count") or 0)
            comments = int(m.get("comments_count") or 0)
            permalink = m.get("permalink")
            out.append(
                {
                    "id": str(m.get("id") or ""),
                    "handle": handle,
                    "caption": (m.get("caption") or "")[:2000],
                    "media_type": m.get("media_type"),
                    "media_product_type": m.get("media_product_type"),
                    "like_count": likes,
                    "comments_count": comments,
                    # OFFICIAL Reels views from business_discovery's view_count
                    # (Meta changelog 2025-06-16) — the scrape tiers below only
                    # gap-fill posts this leaves at 0 (feed videos, old API).
                    "views": int(m.get("view_count") or 0),
                    "engagement": likes + comments,
                    "permalink": permalink,
                    "thumbnail_url": m.get("thumbnail_url"),
                    "timestamp": m.get("timestamp"),
                    # Join key for optional view enrichment; stripped before return.
                    "_shortcode": instagrapi_client._shortcode_from_ref(permalink) if permalink else "",
                }
            )
        return handle, out

    async def _fetch_batch(batch: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        results = await asyncio.gather(*(one(h) for h in batch), return_exceptions=True)
        merged_batch: list[dict[str, Any]] = []
        valid_batch: list[str] = []  # handles that returned real posts
        for r in results:
            if isinstance(r, tuple):
                handle, posts = r
                if posts:
                    valid_batch.append(handle)
                    merged_batch.extend(posts)
        return merged_batch, valid_batch

    merged, valid = await _fetch_batch(handles)

    # ── Region/global top-up wave — runs when discovery + anchors came back thin ─
    # business_discovery drops wrong/personal handles SILENTLY, so a rotted
    # anchor list (and a bad-search-day discovery) are invisible until after the
    # fetch. Left alone, the grid then collapses into the cross-tenant pool (= one
    # tenant's competitors on a young deployment) and the region tab renders the
    # niche tab's content. Top up from the untried curated seed floor, then any
    # leftover pool. (Dynamic discovery already ran up front — force_refresh only.)
    if req.mode in ("region", "global"):
        anchor_lc = {s.lower() for s in anchor_seeds}
        wave1_slots = 8 if req.mode == "region" else MAX_HANDLES
        # An operator-trimmed seed env shorter than the gate must not make it
        # permanently unsatisfiable (top-up on every compute).
        min_anchors = min(MIN_ANCHORS, len(anchor_seeds[:wave1_slots]))
        # Discovery is the PRIMARY source now (added up front on the worker
        # path), so a discovered handle that RESOLVED counts toward grid health
        # exactly like a curated anchor: only fall back to the seed floor when
        # discovery AND the anchors together came back thin — the case where the
        # grid would otherwise collapse into the tenant pool (= one tenant's
        # niche, the bug this gate exists to prevent).
        valid_reps = sum(
            1 for v in valid if v.lower() in anchor_lc or v.lower() in discovered_anchor_lc
        )
        # Don't pour a SECOND wave of calls into a throttled API: when much of
        # wave 1 came back rate-limited (Graph code 4 — NOT dead handles), a
        # top-up only deepens the app-level quota hit. Skip it; the empty result
        # backs off ~3h (see _compute_and_cache) so the quota recovers.
        rate_limited_wave1 = len(rate_limited) >= max(2, len(handles) // 2)
        if valid_reps < min_anchors and not rate_limited_wave1:
            # Rescue the thin grid from the untried curated seed floor, then any
            # leftover cross-tenant pool. Discovery already ran up front, so the
            # verified anchors are the only reliable signal left to add.
            for h in anchor_seeds:
                _add(h, into=wave2)
            for h in anchor_pool:  # empty for global (no cross-tenant pool)
                _add(h, into=wave2)
            if wave2:
                more_merged, more_valid = await _fetch_batch(wave2)
                merged.extend(more_merged)
                valid.extend(more_valid)

        # Dead-anchor visibility — checked AFTER all waves so partial rot is
        # reported too, not only the catastrophic all-dead case. Dead anchors
        # mean the curated list needs updating (the seed env var) — exactly the
        # silent rot that made the region tab mirror the niche tab.
        valid_lc = {v.lower() for v in valid}
        tried_lc = {h.lower() for h in handles} | {h.lower() for h in wave2}
        # A throttled handle is NOT dead — the graph layer already fired the
        # rate-limit alert; don't also tell the operator to fix the seed list.
        dead_seeds = [
            s
            for s in anchor_seeds
            if s.lower() in tried_lc
            and s.lower() not in valid_lc
            and s.lower() not in rate_limited
        ]
        if dead_seeds:
            log.warning(
                "competitor_media.anchor_seeds_dead", mode=req.mode, dead=dead_seeds
            )
            seed_env = (
                "VIRALE_REGION_SEED_HANDLES"
                if req.mode == "region"
                else "VIRALE_GLOBAL_SEED_HANDLES"
            )
            # Global mega-accounts (Ronaldo, MrBeast…) are commonly age-gated
            # (18+), and Meta's business_discovery explicitly refuses age-gated
            # accounts — so on the global tab "not found" usually means age-gated,
            # NOT a typo. Say so, and point at accounts that DO resolve.
            hint = (
                " (ko'pi 18+ yosh cheklovli — Meta bunday akkauntlarni bermaydi; "
                "yosh cheklovsiz yirik akkauntlarni tanlang)"
                if req.mode == "global"
                else ""
            )
            now = time.monotonic()
            if now - _DEAD_SEED_ALERT_AT.get(req.mode, 0.0) >= _DEAD_SEED_ALERT_THROTTLE_S:
                _DEAD_SEED_ALERT_AT[req.mode] = now
                telegram.send(
                    f"⚠️ Virale {req.mode} · {len(dead_seeds)} ta anchor akkaunt "
                    f"business_discovery'da topilmadi{hint}: "
                    f"{', '.join(dead_seeds[:6])} — {seed_env} orqali yangilang"
                )

    # ── View gap-fill — best-effort, NEVER gates the grid ────────────────────
    # The OFFICIAL business_discovery view_count above already covers Reels (the
    # bulk of the grid). Two scrape tiers fill only what it leaves at 0 (feed
    # videos, deployments where the field errored), both fail-soft under time
    # caps (any failure keeps views as-is and the grid still renders). They run
    # CONCURRENTLY per handle so a wide pool can't silently truncate later
    # handles to zero:
    #   Tier 1 — playwright web_profile_info (LOGIN-LESS, no scraper accounts):
    #            the anonymous JSON carries video_view_count on reel/video nodes.
    #   Tier 2 — instagrapi (also covers feed videos), only when
    #            IG_SCRAPER_ACCOUNTS is configured.
    # Both are FILL-ONLY: the official Graph number is authoritative and must not
    # be overwritten by a scraped one. Handles whose video posts all carry
    # official views are skipped — no anonymous scraping when there is nothing to
    # fill (IG 429s datacenter IPs; don't burn quota for zero gain).
    # Worker pre-warms (force_refresh) get roomier caps: nobody is waiting on the
    # request, and views are exactly what the lazy path keeps missing under the
    # tight interactive budget.
    per_handle_timeout = 30 if req.force_refresh else 15
    tier_timeout = 150 if req.force_refresh else 40

    def _needs_views(p: dict) -> bool:
        # Only videos can ever have views; photos/carousels stay 0 everywhere.
        return (p.get("media_type") or "").upper() == "VIDEO" and not p.get("views")

    need_views = [
        h for h in valid
        if any(p["handle"].lower() == h.lower() and _needs_views(p) for p in merged)
    ]
    if need_views:
        from app.integrations.instagram import playwright_scraper

        def _apply(handle: str, view_by_code: dict[str, int]) -> None:
            for p in merged:
                if p["handle"].lower() == handle.lower() and not p.get("views"):
                    code = p.get("_shortcode")
                    if code and view_by_code.get(code):
                        p["views"] = view_by_code[code]

        async def _enrich_playwright(h: str) -> None:
            try:
                media = await asyncio.wait_for(
                    playwright_scraper.fetch_public_recent_media(h, limit=req.per_handle),
                    timeout=per_handle_timeout,
                )
            except Exception:  # noqa: BLE001 — best-effort per handle
                return
            vbc: dict[str, int] = {}
            for m in media:
                code = instagrapi_client._shortcode_from_ref(m.get("shortcode") or "")
                v = m.get("view_count")
                if code and v:  # skip None/0 — photos & stripped payloads stay unknown
                    vbc[code] = int(v)
            _apply(h, vbc)

        try:
            await asyncio.wait_for(
                asyncio.gather(*(_enrich_playwright(h) for h in need_views), return_exceptions=True),
                timeout=tier_timeout,
            )
        except Exception:  # noqa: BLE001 — enrichment must never fail the grid
            log.warning("competitor_media.enrich_playwright_failed")

        # Tier 1 just mutated `merged` — recompute the gap list so the logged-in
        # scraper accounts (ban-prone, quota-bound) aren't spent on handles whose
        # gaps tier 1 already filled (fill-only _apply would discard the result).
        still_need = [
            h for h in need_views
            if any(p["handle"].lower() == h.lower() and _needs_views(p) for p in merged)
        ]
        if still_need and os.getenv("IG_SCRAPER_ACCOUNTS"):

            async def _enrich_instagrapi(h: str) -> None:
                try:
                    ov = await asyncio.wait_for(
                        instagrapi_client.fetch_account_overview(h, limit=req.per_handle),
                        timeout=per_handle_timeout,
                    )
                except Exception:  # noqa: BLE001 — best-effort per handle
                    return
                if not ov.get("ok"):
                    return
                vbc: dict[str, int] = {}
                for m in ov.get("posts") or []:
                    code = instagrapi_client._shortcode_from_ref(
                        m.get("permalink") or m.get("shortcode") or ""
                    )
                    if code:
                        # Reels report play_count; feed videos report view_count.
                        val = int(m.get("play_count") or 0) or int(m.get("view_count") or 0)
                        if val:
                            vbc[code] = val
                _apply(h, vbc)  # fill remaining gaps tier 1 also missed

            try:
                await asyncio.wait_for(
                    asyncio.gather(*(_enrich_instagrapi(h) for h in still_need), return_exceptions=True),
                    timeout=tier_timeout,
                )
            except Exception:  # noqa: BLE001 — enrichment must never fail the grid
                log.warning("competitor_media.enrich_instagrapi_failed")

    # Every view source is best-effort — when all of them come back empty for a
    # post that HAD a real view count in the previous cache generation, keep the
    # old number (stale truth beats a "—" flapping in and out every refresh).
    if prev_views:
        for p in merged:
            if not p.get("views") and prev_views.get(str(p.get("id"))):
                p["views"] = prev_views[str(p["id"])]

    # Region/global promise "top reels" — keep true Reels
    # (media_product_type == REELS) when the edge tagged them, fall back to any
    # VIDEO where it didn't, and to the mixed set when a thin pool can't fill a
    # reel-only grid (degrade to real content, not an empty page).
    if req.mode in ("region", "global"):

        def _is_reel(p: dict) -> bool:
            mpt = (p.get("media_product_type") or "").upper()
            return mpt == "REELS" if mpt else (p.get("media_type") or "").upper() == "VIDEO"

        reels = [p for p in merged if _is_reel(p)]
        if len(reels) >= min(6, req.top):
            merged = reels

    # ── Rank: strictly most-viewed, under a tight per-handle cap ─────────────
    # The product promise on EVERY tab is "eng ko'p ko'rilgan": the grid is the
    # global top-N by (views, engagement). But a FLAT most-viewed sort lets one
    # prolific account (e.g. Ronaldo on the global tab) take many slots — the
    # user's "bir xil odam" (same person repeated) complaint. So each account
    # contributes at most _DIVERSITY_CAP posts; within that the grid is still
    # strictly most-viewed. When the pool is too thin to fill top-N under the
    # cap (few anchors resolved), the cap is relaxed ONE step at a time so a
    # short grid fills with the next-most-viewed posts rather than staying
    # under-filled — a thin pool is the only case one account can repeat 3+.
    _DIVERSITY_CAP = 2

    def _rank_key(p: dict[str, Any]) -> tuple[int, int]:
        return (int(p.get("views") or 0), int(p.get("engagement") or 0))

    by_handle: dict[str, list[dict]] = defaultdict(list)
    for p in merged:
        p.pop("_shortcode", None)
        by_handle[p["handle"]].append(p)
    for posts in by_handle.values():
        posts.sort(key=_rank_key, reverse=True)

    def _pick(cap: int) -> list[dict]:
        chosen = [p for posts in by_handle.values() for p in posts[:cap]]
        chosen.sort(key=_rank_key, reverse=True)
        return chosen[: req.top]

    # Smallest cap that fills the grid wins (maximizes diversity); the deepest
    # any account can have is its post count, so that's the ceiling.
    max_depth = max((len(posts) for posts in by_handle.values()), default=0)
    result: list[dict] = []
    for cap in range(_DIVERSITY_CAP, max(max_depth, _DIVERSITY_CAP) + 1):
        result = _pick(cap)
        if len(result) >= req.top:
            break

    # Seed ONLY the validated accounts into competitor_tracks so the tenant's pool
    # + the competitor_tracker fill with good handles rather than discovery misfires.
    # Niche mode only: region-mode handles are cross-niche celebrities of the whole
    # region — writing them into ONE tenant's competitor list would poison it.
    if req.mode == "niche" and req.tenant_id and valid:
        try:
            from app.graphs.nodes.competitor_intel import _persist_discovered

            await _persist_discovered(
                req.tenant_id,
                [{"handle": h, "source_url": handle_src.get(h, ""), "discovered": True} for h in valid],
                limit=MAX_HANDLES,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("competitor_media.persist_failed", error=type(exc).__name__)

    posts_out = result[: req.top]
    out: dict[str, Any] = {"ok": True, "posts": posts_out, "discovered": valid, "mode": req.mode}
    if not posts_out:
        # Ops-facing WHY, surfaced in the worker's twice-daily Telegram summary so
        # an empty grid names its cause (dead token / rate limit / …) instead of
        # a bare "0 ta reel". Ignored by the web (it reads posts/views only).
        out["reason"] = _empty_grid_reason(handles + wave2, rate_limited)
    return out


# ── Virale "Top accounts" — profile cards ranked by follower count ───────────
# A DIFFERENT shape from the reels grids: one card per ACCOUNT (avatar, display
# name, @handle, followers, posts) instead of per post. Shared per region, warmed
# twice a day. "Reach/qamrov" is an owner-only insights metric (unavailable for
# OTHER accounts), so follower_count is the ranking proxy for "profile coverage".


async def _account_candidates(req: CompetitorMediaRequest, *, limit: int) -> list[str]:
    """Region account pool for the Top-accounts grid: dynamic discovery (worker
    path) FIRST, then the verified UZ seed floor, then the cross-tenant pool — the
    same niche-agnostic sources as the region reels grid, deduped and capped."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        clean = (raw or "").lstrip("@").strip()
        key = clean.lower()
        if clean and key not in seen and len(out) < limit:
            seen.add(key)
            out.append(clean)

    if req.force_refresh:
        for h in await _discover_anchor_handles(req):
            _add(h)
    for h in _region_seed_handles():
        _add(h)
    for h in await _region_handle_pool(limit * 2):
        _add(h)
    return out


async def _compute_top_accounts(req: CompetitorMediaRequest) -> dict[str, Any]:
    """Top region accounts by follower count via business_discovery PROFILE reads
    (one cheap GET per handle — no media edge). Fail-soft per handle; ranked desc,
    deduped by handle."""
    token = os.getenv("IG_GRAPH_SERVICE_TOKEN")
    ig_uid = os.getenv("IG_GRAPH_SERVICE_USER_ID")
    # Probe more than we show so ranking has depth after dead/thin handles drop.
    candidates = await _account_candidates(req, limit=max(req.top * 2, 24))
    if not candidates:
        return {"ok": True, "accounts": [], "mode": "accounts", "reason": "no_candidates"}

    sem = asyncio.Semaphore(4)
    rate_limited: set[str] = set()

    async def one(handle: str) -> dict[str, Any] | None:
        try:
            async with sem:
                return await asyncio.wait_for(
                    graph_api.fetch_competitor_profile(
                        handle, ig_user_id=ig_uid or "", access_token=token or ""
                    ),
                    timeout=20,
                )
        except graph_api.GraphRateLimited:
            rate_limited.add(handle.lower())
            return None
        except Exception:  # noqa: BLE001 — timeout / transport error → skip handle
            return None

    results = await asyncio.gather(*(one(h) for h in candidates), return_exceptions=True)
    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in results:
        if isinstance(r, dict) and r.get("handle"):
            k = str(r["handle"]).lower()
            if k not in seen:
                seen.add(k)
                accounts.append(r)
    accounts.sort(key=lambda a: int(a.get("followers") or 0), reverse=True)
    top = accounts[: req.top]
    out: dict[str, Any] = {"ok": True, "accounts": top, "mode": "accounts"}
    if not top:
        out["reason"] = _empty_grid_reason(candidates, rate_limited)
    return out


async def _compute_and_cache_accounts(req: CompetitorMediaRequest, key: str) -> dict[str, Any]:
    """Cache wrapper for the Top-accounts grid — mirrors _compute_and_cache: keep
    yesterday's cards on a transient empty recompute, back off ~3h on a rate limit,
    short-TTL a genuinely-empty grid."""
    prev = await redis_cache.get_json(key)
    result = await _compute_top_accounts(req)
    prev_had = isinstance(prev, dict) and bool(prev.get("accounts"))
    if result.get("ok") and result.get("accounts"):
        result["generated_at"] = datetime.now(UTC).isoformat()
        await redis_cache.set_json(key, result, ttl_seconds=_VIRALE_CACHE_TTL_SEC)
    elif result.get("ok") and not prev_had:
        result["generated_at"] = datetime.now(UTC).isoformat()
        empty_ttl = (
            _VIRALE_RATE_LIMIT_TTL_SEC
            if result.get("reason") in ("rate_limited", "some_rate_limited")
            else _VIRALE_EMPTY_TTL_SEC
        )
        await redis_cache.set_json(key, result, ttl_seconds=empty_ttl)
    elif result.get("ok") and isinstance(prev, dict):
        # Transient failure while a full grid sits in cache — keep serving it.
        log.warning("competitor_media.accounts_empty_recompute_kept_previous", key=key)
        prev["cached"] = True
        return prev
    result["cached"] = False
    return result

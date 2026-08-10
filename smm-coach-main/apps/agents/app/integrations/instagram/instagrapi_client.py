"""instagrapi-based scraper — primary IG data source for MVP.

Uses Instagram's private mobile API (the same one the official app uses)
through pre-authenticated sessions. Much faster than headless browsers and
returns richer payloads, but requires throwaway accounts and careful
rate-limit handling.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.graphs.state import AccountSnapshot
from app.integrations import telegram
from app.integrations.instagram.session_pool import get_pool

log = structlog.get_logger(__name__)


def _is_session_dead(exc: Exception) -> bool:
    """True when the error means the cached IG session is no longer usable
    (logged out / needs re-auth) — so the pool should drop it and the next
    acquire re-logins instead of re-handing-out the same broken client."""
    return (
        "loginrequired" in type(exc).__name__.lower()
        or "login_required" in str(exc).lower()
    )


class IgRateLimited(Exception):
    """Raised when Instagram returns a feedback-required / 429-style error."""


@retry(
    retry=retry_if_exception_type(IgRateLimited),
    wait=wait_exponential(min=30, max=600),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def fetch_profile(handle: str) -> AccountSnapshot:
    pool = get_pool()
    try:
        client = await pool.acquire()
    except RuntimeError as exc:
        # No scraper accounts configured (dev / unconfigured env). Return a
        # neutral stub so the workflow can still run end-to-end against the
        # demo dataset — the user will see "data sync coming soon" in the UI.
        log.warning("instagrapi.no_scrapers — returning stub profile", handle=handle, error=str(exc))
        return AccountSnapshot(
            handle=handle,
            instagram_user_id="",
            follower_count=0,
            following_count=0,
            posts_count=0,
            bio=None,
            profile_url=f"https://instagram.com/{handle}",
            avatar_url=None,
            is_private=False,
            account_type="unknown",
        )

    try:
        user = await asyncio.to_thread(client.user_info_by_username, handle)
    except Exception as exc:  # noqa: BLE001
        # Degraded fallback now (business_discovery via the service token is the
        # primary follower source). This server's datacenter IP is blocked by IG so
        # this path fails routinely — log it, don't telegram-spam the owner with an
        # unactionable "IG scraper xato" alert on every snapshot/tracker tick.
        log.warning("instagrapi.fetch_profile_failed", handle=handle, error=str(exc)[:160])
        if _is_session_dead(exc):
            pool.evict_client(client)
        if "feedback_required" in str(exc) or "challenge_required" in str(exc):
            raise IgRateLimited(str(exc)) from exc
        # instagrapi login/proxy is dead — do NOT kill the whole workflow (this
        # used to bubble up through fetch_account_snapshot → initial_analysis and
        # fail the entire roadmap run). Fall back to the login-less
        # web_profile_info path (works through the home-IP proxy — the same route
        # onboarding used to fetch 177 followers), then to a neutral stub.
        log.warning("instagrapi.profile_failed_fallback_web", handle=handle, error=str(exc)[:160])
        from app.integrations.instagram import playwright_scraper

        try:
            prof = await playwright_scraper.fetch_public_profile(handle)
        except Exception:  # noqa: BLE001
            prof = {}
        return AccountSnapshot(
            handle=prof.get("handle") or handle,
            instagram_user_id="",
            follower_count=int(prof.get("follower_count") or 0),
            following_count=int(prof.get("following_count") or 0),
            posts_count=int(prof.get("posts_count") or 0),
            bio=prof.get("bio"),
            profile_url=f"https://instagram.com/{handle}",
            avatar_url=prof.get("avatar_url"),
            is_private=bool(prof.get("is_private")),
            account_type="unknown",
        )
    finally:
        await pool.release(client)

    telegram.send(
        f"📷 IG scraper · @{user.username} → {int(user.follower_count or 0)} obunachi · "
        f"{int(user.media_count or 0)} post"
    )
    return AccountSnapshot(
        handle=user.username,
        instagram_user_id=str(user.pk),
        follower_count=int(user.follower_count or 0),
        following_count=int(user.following_count or 0),
        posts_count=int(user.media_count or 0),
        bio=user.biography,
        profile_url=f"https://instagram.com/{user.username}",
        avatar_url=str(user.profile_pic_url) if user.profile_pic_url else None,
        is_private=bool(user.is_private),
        account_type=_map_account_type(user),
    )


def _map_account_type(user: Any) -> str:
    if getattr(user, "is_business", False):
        return "business"
    if getattr(user, "category", None):
        return "creator"
    return "personal"


@retry(
    retry=retry_if_exception_type(IgRateLimited),
    wait=wait_exponential(min=30, max=600),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def fetch_recent_posts(handle: str, *, limit: int = 24) -> list[dict[str, Any]]:
    pool = get_pool()
    client = await pool.acquire()
    try:
        user_id = await asyncio.to_thread(client.user_id_from_username, handle)
        medias = await asyncio.to_thread(client.user_medias, user_id, limit)
    except Exception as exc:  # noqa: BLE001
        if _is_session_dead(exc):
            pool.evict_client(client)
        if "feedback_required" in str(exc):
            raise IgRateLimited(str(exc)) from exc
        raise
    finally:
        await pool.release(client)

    return [_media_to_dict(m) for m in medias]


def _media_to_dict(m: Any) -> dict[str, Any]:
    """Normalize an instagrapi Media object to our post dict. Includes
    `video_url` (present on reels/videos) so downstream callers can hand the
    thumbnail/cover to Gemini vision for content understanding."""
    return {
        "post_id": str(m.pk),
        "shortcode": m.code,
        "media_type": str(m.media_type),
        "caption": m.caption_text,
        "like_count": int(m.like_count or 0),
        "comment_count": int(m.comment_count or 0),
        "view_count": int(getattr(m, "view_count", 0) or 0),
        "play_count": int(getattr(m, "play_count", 0) or 0),
        "permalink": f"https://instagram.com/p/{m.code}/",
        "taken_at": m.taken_at.isoformat() if m.taken_at else None,
        "thumbnail_url": str(m.thumbnail_url) if m.thumbnail_url else None,
        "video_url": str(m.video_url) if getattr(m, "video_url", None) else None,
    }


def _shortcode_from_ref(ref: str) -> str:
    """Accept a bare shortcode OR a full instagram.com/p|reel|tv/<code>/ URL."""
    ref = ref.strip()
    if "instagram.com" in ref:
        import re

        m = re.search(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", ref)
        if m:
            return m.group(1)
    return ref.strip("/").split("/")[-1]


@retry(
    retry=retry_if_exception_type(IgRateLimited),
    wait=wait_exponential(min=30, max=600),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def fetch_account_overview(handle: str, *, limit: int = 12) -> dict[str, Any]:
    """Profile + recent posts in one call — what the voice coach hands the
    user when they say "look at @competitor". Best-effort: returns ok=False
    with a reason when scrapers aren't configured / the account is blocked."""
    handle = handle.lstrip("@").strip()
    pool = get_pool()
    try:
        client = await pool.acquire()
    except RuntimeError as exc:
        log.warning("instagrapi.no_scrapers — account_overview", handle=handle, error=str(exc))
        return {"ok": False, "handle": handle, "reason": "no_scrapers", "posts": []}

    try:
        user = await asyncio.to_thread(client.user_info_by_username, handle)
        medias = await asyncio.to_thread(client.user_medias, str(user.pk), limit)
    except Exception as exc:  # noqa: BLE001
        if _is_session_dead(exc):
            pool.evict_client(client)
        if "feedback_required" in str(exc) or "challenge_required" in str(exc):
            raise IgRateLimited(str(exc)) from exc
        telegram.send(f"⚠️ IG overview xato · @{handle}\n{str(exc)[:200]}")
        return {"ok": False, "handle": handle, "reason": str(exc)[:160], "posts": []}
    finally:
        await pool.release(client)

    telegram.send(f"🔎 IG overview · @{user.username} → {int(user.follower_count or 0)} obunachi")
    return {
        "ok": True,
        "handle": user.username,
        "full_name": user.full_name,
        "followers": int(user.follower_count or 0),
        "following": int(user.following_count or 0),
        "posts_count": int(user.media_count or 0),
        "bio": user.biography,
        "is_private": bool(user.is_private),
        "account_type": _map_account_type(user),
        "avatar_url": str(user.profile_pic_url) if user.profile_pic_url else None,
        "posts": [_media_to_dict(m) for m in medias],
    }


@retry(
    retry=retry_if_exception_type(IgRateLimited),
    wait=wait_exponential(min=30, max=600),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def fetch_post_detail(ref: str, *, comments_limit: int = 15) -> dict[str, Any]:
    """One post in full — caption, metrics, media/video url, cover image, and
    the top comments. `ref` is a shortcode or an instagram.com/p|reel URL.
    This is what the voice coach uses to "watch + understand" a video."""
    shortcode = _shortcode_from_ref(ref)
    pool = get_pool()
    try:
        client = await pool.acquire()
    except RuntimeError as exc:
        log.warning("instagrapi.no_scrapers — post_detail", ref=ref, error=str(exc))
        return {"ok": False, "shortcode": shortcode, "reason": "no_scrapers", "comments": []}

    try:
        pk = await asyncio.to_thread(client.media_pk_from_code, shortcode)
        media = await asyncio.to_thread(client.media_info, pk)
        try:
            comments = await asyncio.to_thread(client.media_comments, pk, comments_limit)
        except Exception:  # noqa: BLE001 — comments are optional; metrics still useful
            comments = []
    except Exception as exc:  # noqa: BLE001
        if _is_session_dead(exc):
            pool.evict_client(client)
        if "feedback_required" in str(exc) or "challenge_required" in str(exc):
            raise IgRateLimited(str(exc)) from exc
        telegram.send(f"⚠️ IG post detail xato · {shortcode}\n{str(exc)[:200]}")
        return {"ok": False, "shortcode": shortcode, "reason": str(exc)[:160], "comments": []}
    finally:
        await pool.release(client)

    detail = _media_to_dict(media)
    detail["ok"] = True
    detail["author"] = media.user.username if media.user else None
    detail["comments"] = [
        {
            "text": c.text,
            "user": c.user.username if c.user else None,
            "like_count": int(c.like_count or 0),
        }
        for c in comments
        if getattr(c, "text", None)
    ]
    telegram.send(f"🎬 IG post detail · {shortcode} · {detail.get('view_count') or detail.get('like_count')} ko'rish/like")
    return detail


@retry(
    retry=retry_if_exception_type(IgRateLimited),
    wait=wait_exponential(min=30, max=600),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def fetch_hashtag_posts(tag: str, *, limit: int = 12) -> dict[str, Any]:
    """Top posts for a hashtag — lets the coach + market analyst see what's
    winning in a niche right now. Uses instagrapi's hashtag_medias_top."""
    tag = tag.lstrip("#").strip()
    pool = get_pool()
    try:
        client = await pool.acquire()
    except RuntimeError as exc:
        log.warning("instagrapi.no_scrapers — hashtag", tag=tag, error=str(exc))
        return {"ok": False, "tag": tag, "reason": "no_scrapers", "posts": []}

    try:
        medias = await asyncio.to_thread(client.hashtag_medias_top, tag, limit)
    except Exception as exc:  # noqa: BLE001
        if _is_session_dead(exc):
            pool.evict_client(client)
        if "feedback_required" in str(exc) or "challenge_required" in str(exc):
            raise IgRateLimited(str(exc)) from exc
        telegram.send(f"⚠️ IG hashtag xato · #{tag}\n{str(exc)[:200]}")
        return {"ok": False, "tag": tag, "reason": str(exc)[:160], "posts": []}
    finally:
        await pool.release(client)

    telegram.send(f"#️⃣ IG hashtag · #{tag} → {len(medias)} top post")
    return {"ok": True, "tag": tag, "posts": [_media_to_dict(m) for m in medias]}


async def fetch_post_metrics(post_id: str) -> dict[str, Any]:
    """Refresh metrics for one post (called by Account Tracker).

    Accepts either a numeric media_pk OR an alphanumeric shortcode (e.g.
    ``CqGmL_5pBb1``). The publish endpoint stores the shortcode in
    ContentTask.instagramPostId because that's what's parseable from the
    pasted Instagram URL — but instagrapi's media_info needs the numeric
    pk, so we resolve via media_pk_from_code first when needed. Without
    that branch, every tracker_pulse hit a ``ValueError`` on int()
    conversion and the actualMetrics column never filled in.
    """
    pool = get_pool()
    client = await pool.acquire()
    try:
        if post_id.isdigit():
            pk = int(post_id)
        else:
            pk = await asyncio.to_thread(client.media_pk_from_code, post_id)
        media = await asyncio.to_thread(client.media_info, pk)
    except Exception as exc:  # noqa: BLE001
        if _is_session_dead(exc):
            pool.evict_client(client)
        raise
    finally:
        await pool.release(client)

    return {
        "likes": int(media.like_count or 0),
        "comments": int(media.comment_count or 0),
        "views": int(getattr(media, "view_count", 0) or 0),
        "plays": int(getattr(media, "play_count", 0) or 0),
    }


def _media_pk(client: Any, post_id: str) -> int:
    """Coerce a stored post identifier into the numeric media pk instagrapi needs.

    Graph stores the SHORTCODE in instagram_post_id (e.g. 'Cabc123'); media_comments()
    needs the numeric pk. Passing the shortcode to int() raised ValueError and silently
    killed the whole lead/comment pulse (leads stayed at 0). media_pk_from_code is a pure
    local base64 decode — no network. Accepts numeric pk, 'pk_userid' media-id, or shortcode.
    """
    s = str(post_id).strip()
    if "_" in s:  # 'pk_userid' media-id form → keep the pk part
        s = s.split("_", 1)[0]
    if s.isdigit():
        return int(s)
    return int(client.media_pk_from_code(s))  # shortcode → pk


async def fetch_recent_comments(post_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    pool = get_pool()
    client = await pool.acquire()
    try:
        comments = await asyncio.to_thread(client.media_comments, _media_pk(client, post_id), limit)
    except Exception as exc:  # noqa: BLE001
        if _is_session_dead(exc):
            pool.evict_client(client)
        raise
    finally:
        await pool.release(client)

    return [
        {
            "pk": str(c.pk) if getattr(c, "pk", None) else None,
            "text": c.text,
            "user": c.user.username if c.user else None,
            "created_at": c.created_at_utc.isoformat() if c.created_at_utc else None,
            "like_count": int(c.like_count or 0),
        }
        for c in comments
    ]

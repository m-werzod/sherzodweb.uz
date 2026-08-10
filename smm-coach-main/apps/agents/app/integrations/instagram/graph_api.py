"""Meta Graph API client — Business/Creator accounts only (after Advanced Access)."""
from __future__ import annotations

import contextlib
import json
import re
import time

import httpx
import structlog

from app.graphs.state import AccountSnapshot
from app.integrations import telegram

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v25.0"


class GraphRateLimited(Exception):
    """Raised when business_discovery is throttled (a rate-limit error code),
    so callers can tell a transient block apart from a genuinely dead handle."""

    def __init__(self, handle: str, code: int | None) -> None:
        super().__init__(f"business_discovery rate-limited on @{handle} (code {code})")
        self.handle = handle
        self.code = code

# The single shared IG_GRAPH_SERVICE_TOKEN drives ALL competitor/hashtag intel.
# When it expires (Meta error code 190) every business_discovery + Hashtag Search
# call fail-softs to None/[] and the intel tables silently go stale — which is
# exactly how the founder got blindsided twice. Detect the expiry and fire ONE
# throttled Telegram alert so a dead token is visible instead of silent.
_TOKEN_ALERT_AT = 0.0  # monotonic seconds of the last alert
_TOKEN_ALERT_THROTTLE_S = 6 * 3600
_RATE_LIMIT_ALERT_AT = 0.0
_RATE_LIMIT_ALERT_THROTTLE_S = 3 * 3600


def _graph_error(body: str) -> tuple[int | None, int | None, str]:
    """Parse a Graph error body into (code, error_subcode, message). Best-effort:
    returns (None, None, "") when the body isn't the expected error JSON."""
    try:
        err = (json.loads(body) or {}).get("error") or {}
    except Exception:  # noqa: BLE001 — non-JSON body (HTML error page, empty, …)
        return None, None, ""
    code = err.get("code")
    sub = err.get("error_subcode")
    return (
        int(code) if isinstance(code, int) else None,
        int(sub) if isinstance(sub, int) else None,
        str(err.get("message") or "")[:200],
    )


# Graph throttling codes: 4 = app-level rate limit, 17 = user-level, 32 = page,
# 613 = custom-rate-limit, 80004 = IG business-use-case limit. A throttled
# business_discovery call looks EXACTLY like a "handle not found" ([]/None) to
# callers, so callers that curate anchor lists must distinguish the two — a
# rate-limit is NOT a dead handle and must not trigger "update your seed list".
_RATE_LIMIT_CODES = {4, 17, 32, 613, 80004}


def _is_rate_limited(body: str) -> bool:
    code, _sub, _msg = _graph_error(body)
    return code in _RATE_LIMIT_CODES


def _is_token_expired(body: str) -> bool:
    """True when a non-200 body signals an expired/invalid OAuth token (code 190),
    NOT the ordinary 400s business_discovery returns for a personal/typo'd handle."""
    b = (body or "").lower()
    return (
        '"code":190' in b.replace(" ", "")
        or "session has expired" in b
        or "access token" in b and "expired" in b
    )


def _maybe_alert_token_expired(body: str) -> None:
    """Throttled Telegram nudge when the service token is dead. Fail-soft."""
    global _TOKEN_ALERT_AT
    if not _is_token_expired(body):
        return
    now = time.monotonic()
    if now - _TOKEN_ALERT_AT < _TOKEN_ALERT_THROTTLE_S:
        return
    _TOKEN_ALERT_AT = now
    log.error("graph_api.service_token_expired")  # visible in logs regardless of Telegram
    # never let alerting break a fetch
    with contextlib.suppress(Exception):
        telegram.send(
            "⚠️ IG_GRAPH_SERVICE_TOKEN yaroqsiz (code 190 / muddati tugagan). "
            "Raqobatchi va trend ma'lumotlari (business_discovery, Hashtag Search) "
            "hozir ishlamayapti. Coolify'da yangi MUDDATSIZ Page token o'rnating."
        )


def _maybe_alert_rate_limited(body: str) -> bool:
    """Throttled nudge when Graph is THROTTLING us (not dead accounts). Returns
    True when the body is a rate-limit error so callers can classify the failure
    correctly. Fail-soft."""
    global _RATE_LIMIT_ALERT_AT
    if not _is_rate_limited(body):
        return False
    now = time.monotonic()
    if now - _RATE_LIMIT_ALERT_AT >= _RATE_LIMIT_ALERT_THROTTLE_S:
        _RATE_LIMIT_ALERT_AT = now
        code, sub, msg = _graph_error(body)
        log.warning("graph_api.rate_limited", code=code, subcode=sub, message=msg)
        with contextlib.suppress(Exception):
            telegram.send(
                "⏳ Instagram Graph API vaqtincha limitladi (rate limit, "
                f"code {code}). Bu akkauntlar o'lik EMAS — biroz kutilsa o'zi "
                "tiklanadi. Kesh eski natijani saqlab turadi."
            )
    return True


async def fetch_self_snapshot(access_token: str) -> AccountSnapshot:
    """Pulls /me?fields=… for the connected Instagram business account."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            f"{GRAPH_BASE}/me",
            params={
                "fields": "id,username,name,biography,profile_picture_url,followers_count,follows_count,media_count",
                "access_token": access_token,
            },
        )
        r.raise_for_status()
        data = r.json()

    return AccountSnapshot(
        handle=data.get("username", ""),
        instagram_user_id=data.get("id"),
        # `... or 0`, not `.get(key, 0)`: Graph can return the key present-but-null
        # for transitional/restricted accounts, and int(None) raises.
        follower_count=int(data.get("followers_count") or 0),
        following_count=int(data.get("follows_count") or 0),
        posts_count=int(data.get("media_count") or 0),
        bio=data.get("biography"),
        profile_url=f"https://instagram.com/{data.get('username', '')}",
        is_private=False,
        account_type="business",
    )


async def fetch_competitor_snapshot(
    handle: str, *, ig_user_id: str, access_token: str
) -> AccountSnapshot | None:
    """Public profile of ANOTHER business/creator via the `business_discovery` edge.

    This is the OFFICIAL, ToS-compliant, scrape-free way to read a competitor —
    the path that actually scales to many tenants (no proxy, no scraper account,
    no ban risk). Requires the Facebook-Login variant (the querying IG account
    must be linked to a Facebook Page); `ig_user_id` is the QUERYING account's IG
    Business Account id and `access_token` its token.

    Returns None (never raises) when the target can't be read — personal/private
    account, a typo'd handle, or a token without the Page link — so callers fall
    back gracefully (web-search / cache). Meta rate-limits this (~200 calls/user/
    hr), so results MUST be cached cross-tenant (fetch a competitor once per niche,
    share to every tenant) rather than re-fetched per tenant.
    """
    # Whitelist to the IG-username charset before interpolating into the
    # business_discovery field-spec grammar — a stray ')' or '{' in `handle`
    # would otherwise corrupt the query (defense-in-depth; handles are
    # admin-curated today but this keeps the edge injection-proof).
    target = re.sub(r"[^A-Za-z0-9._]", "", (handle or "").lstrip("@").strip())
    if not target or not ig_user_id:
        return None
    fields = (
        f"business_discovery.username({target})"
        "{id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url}"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{GRAPH_BASE}/{ig_user_id}",
                params={"fields": fields, "access_token": access_token},
            )
        if r.status_code != 200:
            # business_discovery 400s for a non-professional/non-existent target or a
            # token missing the Page link. Expected for many handles → fail-soft.
            log.warning(
                "graph_api.business_discovery_unavailable",
                handle=target, status=r.status_code, body=r.text[:200],
            )
            _maybe_alert_token_expired(r.text)
            return None
        bd = (r.json().get("business_discovery") or {})
    except Exception as exc:  # noqa: BLE001 — never break the caller on a competitor fetch
        # error= class name only, NOT exc_info: structlog renders frame locals,
        # and the httpx Request repr embeds access_token=<token> in the URL — a
        # full traceback would leak the shared service token into logs.
        log.warning("graph_api.business_discovery_error", handle=target, error=type(exc).__name__)
        return None

    if not bd.get("username"):
        return None
    return AccountSnapshot(
        handle=bd.get("username", target),
        instagram_user_id=str(bd["id"]) if bd.get("id") else None,
        # `... or 0` (not `.get(key, 0)`): a present-but-null numeric → int(None) raises,
        # which would skip the instagrapi fallback and abort the handle's refresh.
        follower_count=int(bd.get("followers_count") or 0),
        following_count=int(bd.get("follows_count") or 0),
        posts_count=int(bd.get("media_count") or 0),
        bio=bd.get("biography"),
        profile_url=f"https://instagram.com/{bd.get('username', target)}",
        is_private=False,
        account_type="business",
    )


async def fetch_competitor_profile(
    handle: str, *, ig_user_id: str, access_token: str
) -> dict | None:
    """Public PROFILE card for a business/creator via business_discovery — the
    fields the Virale "Top accounts" tab renders: display name, @handle, follower
    count, post count, avatar. Same Facebook-Login requirement + fail-soft contract
    as fetch_competitor_snapshot, but RAISES GraphRateLimited on a throttle (codes
    4/17/…) so the accounts grid can tell a rate limit apart from a dead handle
    (like fetch_competitor_recent_posts). Returns None on any other error."""
    target = re.sub(r"[^A-Za-z0-9._]", "", (handle or "").lstrip("@").strip())
    if not target or not ig_user_id:
        return None
    fields = (
        f"business_discovery.username({target})"
        "{id,username,name,followers_count,media_count,profile_picture_url}"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{GRAPH_BASE}/{ig_user_id}",
                params={"fields": fields, "access_token": access_token},
            )
        if r.status_code != 200:
            code, sub, msg = _graph_error(r.text)
            log.warning(
                "graph_api.business_discovery_profile_unavailable",
                handle=target, status=r.status_code, code=code, subcode=sub, message=msg,
            )
            _maybe_alert_token_expired(r.text)
            if _maybe_alert_rate_limited(r.text):
                raise GraphRateLimited(target, code)
            return None
        bd = r.json().get("business_discovery") or {}
    except GraphRateLimited:
        raise
    except Exception as exc:  # noqa: BLE001 — never break the caller on a profile fetch
        log.warning("graph_api.business_discovery_profile_error", handle=target, error=type(exc).__name__)
        return None
    if not bd.get("username"):
        return None
    username = bd.get("username", target)
    return {
        "handle": username,
        "name": bd.get("name") or username,
        # `... or 0` (not .get(key, 0)): a present-but-null numeric → int(None) raises.
        "followers": int(bd.get("followers_count") or 0),
        "posts": int(bd.get("media_count") or 0),
        "avatar_url": bd.get("profile_picture_url"),
        "profile_url": f"https://instagram.com/{username}",
    }


async def fetch_competitor_recent_posts(
    handle: str, *, ig_user_id: str, access_token: str, limit: int = 12
) -> list[dict]:
    """A competitor's recent PUBLIC posts via business_discovery's media edge — the
    engagement signal ("what's working in this niche") that feeds the roadmap. Same
    Facebook-Login requirement + fail-soft contract as fetch_competitor_snapshot
    (returns [] on any error). Each item: id, caption, media_type, like_count,
    comments_count, timestamp, permalink, view_count (official Reels views;
    0 for photos/carousels — Meta only counts views on Reels here)."""
    target = re.sub(r"[^A-Za-z0-9._]", "", (handle or "").lstrip("@").strip())
    if not target or not ig_user_id:
        return []
    n = max(1, min(int(limit), 25))

    def _fields(with_views: bool) -> str:
        media_fields = (
            "id,caption,media_type,media_product_type,"
            "like_count,comments_count,timestamp,permalink,media_url,thumbnail_url"
        )
        if with_views:
            # view_count is a business_discovery-ONLY field (Meta changelog
            # 2025-06-16): official competitor Reels view counts, no scraping.
            media_fields += ",view_count"
        return (
            f"business_discovery.username({target})"
            "{media.limit(" + str(n) + "){" + media_fields + "}}"
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{GRAPH_BASE}/{ig_user_id}",
                params={"fields": _fields(True), "access_token": access_token},
            )
            # Graph rejects UNKNOWN fields with error #100 for the WHOLE query —
            # if a deployment/version ever refuses view_count, retry without it:
            # losing views must not lose the entire grid (likes/comments too).
            if r.status_code != 200 and "view_count" in (r.text or ""):
                # LOUD: a persistent rejection silently doubles every call AND
                # zeroes official views (this codebase got blindsided by silent
                # Graph degrades twice before — see the token-expiry alert above).
                log.warning(
                    "graph_api.view_count_rejected_retrying_without",
                    handle=target,
                    status=r.status_code,
                    body=(r.text or "")[:200],
                )
                r = await client.get(
                    f"{GRAPH_BASE}/{ig_user_id}",
                    params={"fields": _fields(False), "access_token": access_token},
                )
        if r.status_code != 200:
            code, sub, msg = _graph_error(r.text)
            # Log the ACTUAL Graph error (code + message), not just the HTTP
            # status — a bare "status=400" hides whether the handle is genuinely
            # unreadable (110), throttled (rate-limit codes), or the token died
            # (190). This module got blindsided by silent Graph degrades before.
            log.warning(
                "graph_api.business_discovery_media_unavailable",
                handle=target,
                status=r.status_code,
                code=code,
                subcode=sub,
                message=msg,
            )
            _maybe_alert_token_expired(r.text)
            if _maybe_alert_rate_limited(r.text):
                # Distinguish throttling from a dead handle so curated-list
                # callers don't advise "update your seed list" for a rate limit.
                raise GraphRateLimited(target, code)
            return []
        media = (((r.json().get("business_discovery") or {}).get("media") or {}).get("data") or [])
    except GraphRateLimited:
        raise  # let callers classify throttling separately from a dead handle
    except Exception as exc:  # noqa: BLE001 — never break the caller on a competitor fetch
        # No exc_info: see fetch_competitor_snapshot — avoids leaking the token-bearing URL.
        log.warning("graph_api.business_discovery_media_error", handle=target, error=type(exc).__name__)
        return []
    out: list[dict] = []
    for m in media:
        if isinstance(m, dict) and m.get("id"):
            out.append(
                {
                    "id": m.get("id"),
                    "caption": (m.get("caption") or "")[:2000],
                    "media_type": m.get("media_type"),
                    "like_count": int(m.get("like_count") or 0),
                    "comments_count": int(m.get("comments_count") or 0),
                    "view_count": int(m.get("view_count") or 0),
                    "timestamp": m.get("timestamp"),
                    "permalink": m.get("permalink"),
                    "media_product_type": m.get("media_product_type"),
                    # Reels expose thumbnail_url; images expose media_url. The
                    # Virale grid uses whichever is present for the card image.
                    "thumbnail_url": m.get("thumbnail_url") or m.get("media_url"),
                    "media_url": m.get("media_url"),
                }
            )
    return out


async def fetch_hashtag_top_media(
    hashtag: str, *, ig_user_id: str, access_token: str, limit: int = 15
) -> list[dict] | None:
    """Top public posts for a hashtag via the OFFICIAL two-step Hashtag Search API —
    the scrape-free "what's trending in this niche/region" signal that scales to many
    tenants. Step 1 resolves the hashtag name to its node id (`ig_hashtag_search`),
    step 2 reads that node's `top_media`. Same Facebook-Login requirement as
    business_discovery (`ig_user_id` = the QUERYING IG Business account id, required on
    BOTH calls). Fail-soft: returns None on any error so the caller skips this hashtag.
    Each item: id, caption, media_type, like_count, comments_count, timestamp, permalink.

    Meta rate-limits this to ~30 UNIQUE hashtags / 7 days / querying account (Platform
    rate limiting, not the per-call Business quota), so callers MUST cache cross-tenant
    (one fetch per hashtag, shared per region) — see hashtag_trend_refresher.
    """
    tag = re.sub(r"[^A-Za-z0-9_]", "", (hashtag or "").lstrip("#").strip())
    if not tag or not ig_user_id:
        return None
    n = max(1, min(int(limit), 50))
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Step 1 — resolve the hashtag name to its node id.
            r1 = await client.get(
                f"{GRAPH_BASE}/ig_hashtag_search",
                params={"user_id": ig_user_id, "q": tag, "access_token": access_token},
            )
            if r1.status_code != 200:
                log.warning("graph_api.hashtag_search_unavailable", hashtag=tag, status=r1.status_code)
                _maybe_alert_token_expired(r1.text)
                return None
            data = r1.json().get("data") or []
            if not data or not data[0].get("id"):
                return None
            hashtag_id = data[0]["id"]
            # Step 2 — the hashtag's top (most-engaged) recent public posts.
            r2 = await client.get(
                f"{GRAPH_BASE}/{hashtag_id}/top_media",
                params={
                    "user_id": ig_user_id,
                    "fields": "id,caption,media_type,like_count,comments_count,timestamp,permalink",
                    "limit": n,
                    "access_token": access_token,
                },
            )
        if r2.status_code != 200:
            log.warning("graph_api.hashtag_top_media_unavailable", hashtag=tag, status=r2.status_code)
            return None
        media = r2.json().get("data") or []
    except Exception as exc:  # noqa: BLE001 — never break the caller on a trend fetch
        # No exc_info: the request URL carries access_token; see fetch_competitor_snapshot.
        log.warning("graph_api.hashtag_search_error", hashtag=tag, error=type(exc).__name__)
        return None
    out: list[dict] = []
    for m in media:
        if isinstance(m, dict) and m.get("id"):
            out.append(
                {
                    "id": m.get("id"),
                    "caption": (m.get("caption") or "")[:2000],
                    "media_type": m.get("media_type"),
                    "like_count": int(m.get("like_count") or 0),
                    "comments_count": int(m.get("comments_count") or 0),
                    "timestamp": m.get("timestamp"),
                    "permalink": m.get("permalink"),
                }
            )
    return out


async def fetch_insights(post_id: str, access_token: str) -> dict:
    """Per-media insights. Metric names migrated in Apr 2025 — see plan."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            f"{GRAPH_BASE}/{post_id}/insights",
            params={
                "metric": "media_views,media_viewers,saved,shares,likes,comments",
                "access_token": access_token,
            },
        )
        r.raise_for_status()
        return r.json()

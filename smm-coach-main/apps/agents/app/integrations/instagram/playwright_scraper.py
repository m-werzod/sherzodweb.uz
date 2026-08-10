"""Playwright fallback for things instagrapi can't reach cleanly: Discovery /
Reels Explore feed, region-trending audio shelves, hashtag pages without
login.

Stealth plugin masks navigator.webdriver and the common Playwright
fingerprints. Still detectable by sophisticated heuristics — keep volume
low and rotate User-Agents.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import random
from typing import Any
from urllib.parse import urlparse

import structlog
from fake_useragent import UserAgent  # type: ignore[import-untyped]
from playwright.async_api import Browser, async_playwright
from playwright_stealth import Stealth  # type: ignore[import-untyped]

log = structlog.get_logger(__name__)

_ua = UserAgent()
_stealth = Stealth()


def _proxy_url() -> str | None:
    """Residential/ISP proxy for login-less IG calls. Instagram returns 429 to
    datacenter IPs, so the public JSON endpoint + Playwright must egress through
    the same clean proxy the instagrapi session pool uses."""
    return os.getenv("IG_SCRAPER_PROXY_URL") or None


def _playwright_proxy(proxy_url: str) -> dict[str, str]:
    """Split a `http://user:pass@host:port` URL into Playwright's proxy dict."""
    u = urlparse(proxy_url)
    host = u.hostname or ""
    server = f"{u.scheme}://{host}:{u.port}" if u.port else f"{u.scheme}://{host}"
    out: dict[str, str] = {"server": server}
    if u.username:
        out["username"] = u.username
    if u.password:
        out["password"] = u.password
    return out


class _BrowserHolder:
    """Single browser instance reused across calls — launching Chromium
    every request is too slow and looks suspicious."""

    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> Browser:
        async with self._lock:
            if self._browser is None:
                pw = await async_playwright().start()
                launch_kw: dict[str, Any] = {
                    "headless": True,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                }
                # Launch-level proxy (most reliable for Chromium) so all
                # login-less IG page loads egress through the clean ISP IP.
                proxy = _proxy_url()
                if proxy:
                    launch_kw["proxy"] = _playwright_proxy(proxy)
                self._browser = await pw.chromium.launch(**launch_kw)
            return self._browser


_holder = _BrowserHolder()


async def _new_page():
    browser = await _holder.get()
    ctx = await browser.new_context(
        user_agent=_ua.chrome,
        locale="uz-UZ",
        timezone_id="Asia/Tashkent",
        viewport={"width": 390, "height": 844},  # mobile viewport
    )
    page = await ctx.new_page()
    await _stealth.apply_stealth_async(page)
    return ctx, page


async def _ig_json_get(
    url: str, headers: dict[str, str], proxy: str | None
) -> tuple[int, dict[str, Any] | None]:
    """GET a JSON endpoint as (status_code, parsed_json|None).

    Prefers curl_cffi with a real Chrome TLS/JA3 fingerprint — Instagram flags
    naked Python (httpx/requests) TLS handshakes as bot traffic and 403s them.
    Falls back to httpx when curl_cffi isn't installed, so it degrades cleanly.
    """
    try:
        from curl_cffi.requests import AsyncSession  # type: ignore[import-untyped]

        kw: dict[str, Any] = {"timeout": 12, "impersonate": "chrome124"}
        if proxy:
            kw["proxies"] = {"http": proxy, "https": proxy}
        async with AsyncSession() as s:
            r = await s.get(url, headers=headers, **kw)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001 — non-JSON body (e.g. a block page)
            return r.status_code, None
    except ImportError:
        import httpx

        ckw: dict[str, Any] = {"timeout": 10.0, "follow_redirects": True}
        if proxy:
            ckw["proxy"] = proxy
        async with httpx.AsyncClient(**ckw) as c:
            r = await c.get(url, headers=headers)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, None


async def _fetch_via_json_api(handle_clean: str) -> dict[str, Any] | None:
    """Try IG's web_profile_info JSON endpoint — much more reliable than
    HTML scraping. Returns None on failure so caller falls back to HTML.

    The endpoint requires the X-IG-App-ID header (a known web client ID).
    It's the same call IG's own frontend makes when you visit a profile,
    so it doesn't require login and works for public accounts.
    """

    from app.integrations.instagram import rate_limiter

    # Global pacer — skip the call (not crash) when the hourly cap is hit or a
    # cooldown from a prior 429 is still active.
    try:
        await rate_limiter.acquire()
    except rate_limiter.IGRateLimited as exc:
        log.info("ig_json_api.rate_limited", handle=handle_clean, reason=str(exc))
        return None

    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={handle_clean}"
    headers = {
        "X-IG-App-ID": "936619743392459",
        "User-Agent": _ua.chrome,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.instagram.com/{handle_clean}/",
    }
    proxy = _proxy_url()
    try:
        status_code, body = await _ig_json_get(url, headers, proxy)
        if status_code == 429:
            rate_limiter.trip_cooldown()  # hard block → pause ALL IG traffic for hours
            log.warning("ig_json_api.429_cooldown", handle=handle_clean)
            return None
        if status_code != 200 or body is None:
            log.info("ig_json_api.non_200", handle=handle_clean, status=status_code)
            return None
        user = (body.get("data") or {}).get("user") or body.get("user") or {}
        if not user:
            return None
        followers = int(((user.get("edge_followed_by") or {}).get("count")) or 0)
        following = int(((user.get("edge_follow") or {}).get("count")) or 0)
        posts = int(((user.get("edge_owner_to_timeline_media") or {}).get("count")) or 0)
        # Pull recent post (shortcode, timestamp) pairs for the dashboard
        # streak heatmap — the timeline node has up to 12 most recent posts.
        recent_posts: list[dict[str, Any]] = []
        timeline = (user.get("edge_owner_to_timeline_media") or {}).get("edges") or []
        for edge in timeline[:30]:
            node = edge.get("node") or {}
            shortcode = node.get("shortcode")
            taken_at = node.get("taken_at_timestamp")
            if shortcode and taken_at:
                # web_profile_info carries per-post engagement + (for videos/reels)
                # video_view_count on the SAME payload we already fetched. Harvest
                # it so callers get competitor VIEW counts login-lessly (no scraper
                # accounts). view_count is None for photos (and can be absent when
                # IG strips it for anonymous callers) — leave None, do NOT coerce to
                # 0, so photos rank by engagement rather than a fake zero.
                vv = node.get("video_view_count")
                recent_posts.append(
                    {
                        "shortcode": shortcode,
                        "taken_at": int(taken_at),
                        "view_count": int(vv) if vv is not None else None,
                        "like_count": int((node.get("edge_media_preview_like") or {}).get("count") or 0),
                        "comment_count": int((node.get("edge_media_to_comment") or {}).get("count") or 0),
                        "is_video": bool(node.get("is_video")),
                    }
                )
        return {
            "handle": user.get("username") or handle_clean,
            "follower_count": followers,
            "following_count": following,
            "posts_count": posts,
            "bio": user.get("biography"),
            "avatar_url": user.get("profile_pic_url_hd") or user.get("profile_pic_url"),
            "is_private": bool(user.get("is_private")),
            "recent_posts": recent_posts,
            "ok": followers > 0 or posts > 0 or bool(user.get("biography")),
        }
    except Exception as exc:  # noqa: BLE001
        log.info("ig_json_api.exception", handle=handle_clean, error=repr(exc)[:200])
        return None


async def fetch_public_recent_media(handle: str, *, limit: int = 12) -> list[dict[str, Any]]:
    """Login-less per-post views + engagement for a public account, via the same
    web_profile_info call fetch_public_profile uses — NO scraper accounts, no
    extra request. Each item: {shortcode, taken_at, view_count, like_count,
    comment_count, is_video}. `view_count` is None for photos (and may be absent
    when IG strips it from the anonymous payload) — callers MUST treat None as
    'unknown', never 0. Returns [] on any block/failure so callers degrade
    cleanly (grid keeps views=0, ranks by engagement)."""
    handle_clean = handle.lstrip("@").strip()
    if not handle_clean:
        return []
    res = await _fetch_via_json_api(handle_clean)
    if not res:
        return []
    return (res.get("recent_posts") or [])[: max(1, limit)]


async def fetch_public_profile(handle: str) -> dict[str, Any]:
    """Best-effort public scrape of a profile page without login.

    Strategy:
      1. Try IG's web_profile_info JSON endpoint — fastest, most reliable.
         Just needs the X-IG-App-ID header (a known constant).
      2. If that fails (rate-limit / IG blocks), fall back to Playwright
         HTML scraping of the profile page (og:description meta tag).

    Returns a partial snapshot — some fields may be 0/None when scraping
    fails (very private accounts, rate limits, ToS challenges). The caller
    falls back to a manual input field in the wizard.
    """
    import re

    handle_clean = handle.lstrip("@").strip()
    if not handle_clean:
        return {"handle": "", "follower_count": 0, "is_private": False, "ok": False}

    # Strategy 1: JSON API (cheap, fast, reliable when not blocked).
    json_result = await _fetch_via_json_api(handle_clean)
    if json_result and json_result.get("ok"):
        log.info("public_profile.via_json_api",
                 handle=handle_clean,
                 followers=json_result.get("follower_count"))
        return json_result

    ctx, page = await _new_page()
    out: dict[str, Any] = {
        "handle": handle_clean,
        "follower_count": 0,
        "following_count": 0,
        "posts_count": 0,
        "bio": None,
        "avatar_url": None,
        "is_private": False,
        "ok": False,
    }
    # Capture JSON responses Instagram fetches client-side. The profile
    # page's post grid loads via GraphQL after JS hydrates — so we listen
    # for response bodies that smell like the timeline payload and harvest
    # (taken_at_timestamp, shortcode) pairs from them.
    captured_posts: list[dict[str, Any]] = []
    captured_codes: set[str] = set()

    async def _on_response(resp) -> None:
        url = resp.url
        if "instagram.com" not in url:
            return
        # GraphQL and the /api/v1/feed/user_timeline_graphql_connection/
        # endpoint both deliver post data. We grep the body text rather
        # than parse — the JSON structures change too often.
        if "graphql" not in url and "timeline" not in url and "/api/v1/" not in url:
            return
        try:
            text = await resp.text()
        except Exception:  # noqa: BLE001
            return
        if "taken_at_timestamp" not in text and '"taken_at":' not in text:
            return
        # Try the GraphQL pattern first ("taken_at_timestamp"), then the
        # mobile-API pattern ("taken_at"). Both pair with "code" or
        # "shortcode" depending on endpoint.
        for pat in (
            r'"shortcode":"([^"]+)"[^{}]{0,500}?"taken_at_timestamp":(\d+)',
            r'"taken_at_timestamp":(\d+)[^{}]{0,500}?"shortcode":"([^"]+)"',
            r'"code":"([^"]+)"[^{}]{0,500}?"taken_at":(\d+)',
            r'"taken_at":(\d+)[^{}]{0,500}?"code":"([^"]+)"',
        ):
            for m in re.finditer(pat, text):
                # First two patterns: group1=shortcode, group2=timestamp.
                # Last two: reversed. Detect by which group is numeric.
                a, b = m.group(1), m.group(2)
                code = b if a.isdigit() else a
                ts = a if a.isdigit() else b
                if code in captured_codes or len(captured_posts) >= 30:
                    continue
                captured_codes.add(code)
                captured_posts.append({"shortcode": code, "taken_at": int(ts)})

    page.on("response", lambda r: asyncio.create_task(_on_response(r)))
    try:
        # Instagram aggressively blocks headless browsers. Use a two-step
        # load: domcontentloaded first (fast), then networkidle with a
        # generous timeout so the meta tags hydrate. Fallback to load state
        # if networkidle never fires.
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        await page.goto(
            f"https://www.instagram.com/{handle_clean}/",
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        try:
            await page.wait_for_load_state("networkidle", timeout=12_000)
        except Exception:  # noqa: BLE001
            try:
                await page.wait_for_load_state("load", timeout=8_000)
            except Exception:  # noqa: BLE001
                pass
        # Give JS hydration extra time — IG's meta tags sometimes appear
        # only after the deferred script bundle runs.
        await asyncio.sleep(random.uniform(2.0, 3.5))
        html = await page.content()

        # 1) og:description meta tag — most reliable signal for public profiles
        og = re.search(
            r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.IGNORECASE
        )
        if og:
            txt = og.group(1)
            # Examples seen in the wild:
            #   "123K Followers, 456 Following, 789 Posts - See ..."
            #   "1,234 Followers, 56 Following, 7 Posts ..."
            m = re.search(
                r"([\d,\.]+[KMB]?)\s*Followers?,\s*([\d,\.]+[KMB]?)\s*Following,\s*([\d,\.]+[KMB]?)\s*Posts?",
                txt,
                re.IGNORECASE,
            )
            if m:
                out["follower_count"] = _parse_compact(m.group(1))
                out["following_count"] = _parse_compact(m.group(2))
                out["posts_count"] = _parse_compact(m.group(3))
                # Instagram's anti-scraping sometimes returns "0 Followers" even
                # for active accounts. Treat that as a failed scrape so the wizard
                # falls back to manual input.
                out["ok"] = out["follower_count"] > 0

        # 2) Fallback: full-name + bio via additional meta tags
        title = re.search(
            r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.IGNORECASE
        )
        if title:
            out["full_name"] = title.group(1).split("(@")[0].strip()

        img = re.search(
            r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.IGNORECASE
        )
        if img:
            out["avatar_url"] = img.group(1)

        # 3) Private profile detection
        if "This Account is Private" in html or '"is_private":true' in html:
            out["is_private"] = True

        # 4) Last-resort: structured data embedded in the page
        if not out["ok"]:
            for blob in re.findall(
                r'"edge_followed_by":\{"count":(\d+)\}', html
            ):
                out["follower_count"] = int(blob)
                out["ok"] = True
                break
            for blob in re.findall(r'"edge_follow":\{"count":(\d+)\}', html):
                out["following_count"] = int(blob)
            for blob in re.findall(r'"edge_owner_to_timeline_media":\{"count":(\d+)\}', html):
                out["posts_count"] = int(blob)

        # 5) Recent post timestamps — first merge any captured from network
        # responses (most reliable), then fall back to HTML regex for old-
        # style profile pages that embed the data inline.
        recent_posts: list[dict[str, Any]] = list(captured_posts)
        seen_codes: set[str] = set(captured_codes)
        for m in re.finditer(
            r'"shortcode":"([^"]+)"[^{}]{0,400}?"taken_at_timestamp":(\d+)',
            html,
        ):
            code = m.group(1)
            if code in seen_codes:
                continue
            seen_codes.add(code)
            recent_posts.append({"shortcode": code, "taken_at": int(m.group(2))})
            if len(recent_posts) >= 30:
                break
        for m in re.finditer(
            r'"taken_at_timestamp":(\d+)[^{}]{0,400}?"shortcode":"([^"]+)"',
            html,
        ):
            code = m.group(2)
            if code in seen_codes:
                continue
            seen_codes.add(code)
            recent_posts.append({"shortcode": code, "taken_at": int(m.group(1))})
            if len(recent_posts) >= 30:
                break
        out["recent_posts"] = recent_posts

        log.info(
            "playwright.public_profile",
            handle=handle_clean,
            ok=out["ok"],
            followers=out["follower_count"],
        )
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("playwright.public_profile_failed", handle=handle_clean, error=repr(exc))
        return out
    finally:
        try:
            await ctx.close()
        except Exception:  # noqa: BLE001
            pass


def _parse_compact(s: str) -> int:
    """`'1.2K'` → 1200, `'123,456'` → 123456, `'1.5M'` → 1500000."""
    s = s.strip().replace(",", "")
    if not s:
        return 0
    mult = 1
    last = s[-1].upper()
    if last in {"K", "M", "B"}:
        mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[last]
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


async def fetch_hashtag_top_posts(hashtag: str, *, limit: int = 20) -> list[dict[str, Any]]:
    ctx, page = await _new_page()
    try:
        await page.goto(
            f"https://www.instagram.com/explore/tags/{hashtag.lstrip('#')}/",
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        await asyncio.sleep(random.uniform(2.0, 4.0))
        # Pull the shared __NEXT_DATA__ blob if available; fallback to DOM scrape.
        html = await page.content()
        items: list[dict[str, Any]] = _extract_posts_from_html(html, limit=limit)
        return items
    finally:
        await ctx.close()


async def fetch_reels_explore(region_locale: str = "uz-UZ", *, limit: int = 20) -> list[dict[str, Any]]:
    ctx, page = await _new_page()
    try:
        await ctx.set_extra_http_headers({"Accept-Language": region_locale})
        await page.goto("https://www.instagram.com/reels/", wait_until="domcontentloaded", timeout=20_000)
        # Scroll a few times to populate the feed
        for _ in range(3):
            await page.mouse.wheel(0, 1500)
            await asyncio.sleep(random.uniform(1.5, 3.0))
        html = await page.content()
        return _extract_posts_from_html(html, limit=limit)
    finally:
        await ctx.close()


def _extract_posts_from_html(html: str, *, limit: int) -> list[dict[str, Any]]:
    """Best-effort regex extraction of shortcode + thumbnail from server-rendered HTML.
    Real impl should use Instagram's GraphQL responses captured via page.on('response')
    — that gives us caption, like count, audio, etc. Stub here keeps the scaffold tight.
    """
    import re

    codes = re.findall(r'"shortcode":"([^"]+)"', html)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for c in codes:
        if c in seen:
            continue
        seen.add(c)
        out.append({"shortcode": c, "permalink": f"https://instagram.com/p/{c}/"})
        if len(out) >= limit:
            break
    return out


async def shutdown() -> None:
    if _holder._browser is not None:
        await _holder._browser.close()
        _holder._browser = None


# ── Browser-based login (Bloks/checkpoint bypass) ────────────────────────
# Empirically: Instagram serves a real browser (Playwright) over a DATACENTER
# IP just fine (HTTP 200), while it 429s the private mobile API (instagrapi)
# from the same IP. A browser login also lands on the simple email/SMS code
# page (`auth_platform/codeentry`) instead of the Bloks checkpoint that the
# API hits — and that code page is something we CAN solve via the interactive
# Telegram flow. So we drive a headless browser to log in, ask the operator
# for the code over Telegram, and extract the resulting sessionid.

# Code-entry input candidates (IG changes these; try in order, then fall back
# to the first visible text/tel input).
_CODE_SELECTORS = (
    "input[name='verificationCode']",
    "input[autocomplete='one-time-code']",
    "input[name='security_code']",
    "input[aria-label*='code' i]",
    "input[type='tel']",
)
_DISMISS_TEXTS = ("Not now", "Not Now", "Continue", "Dismiss", "Save info")


async def login_via_browser(username: str, password: str) -> tuple[str | None, str | None]:
    """Log in to Instagram through a headless browser and return its sessionid.

    Returns (sessionid, None) on success, or (None, reason) on failure. The
    code step DMs the operator over Telegram (session_pool helpers) and waits
    ~3 min for their reply. Runs WITHOUT a proxy on purpose — a real browser
    clears IG's datacenter-IP block that the mobile API can't.
    """
    # Lazy import to avoid a circular import at module load.
    from app.integrations.instagram.session_pool import (
        SESSIONS_DIR,
        _tg_poll_code,
        _tg_send_dm,
    )

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    try:
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        with contextlib.suppress(Exception):
            await _stealth.apply_stealth_async(page)

        await page.goto(
            "https://www.instagram.com/accounts/login/",
            timeout=40000,
            wait_until="networkidle",
        )
        await page.wait_for_timeout(3000)
        await page.fill("input[name='email']", username, timeout=15000)
        await page.fill("input[name='pass']", password, timeout=15000)
        await page.press("input[name='pass']", "Enter")
        await page.wait_for_timeout(9000)

        url = page.url
        body = (await page.content()).lower()
        if "incorrect" in body or "password was incorrect" in body:
            return None, "parol noto'g'ri"

        # Code step — email/SMS code, 2FA, or a challenge that asks for a code.
        if any(k in url for k in ("codeentry", "two_factor", "challenge")):
            _tg_send_dm(
                f"🔐 IG Playwright login · {username}\n"
                f"Instagram email/SMS kod so'radi. Botga kodni yuboring (faqat raqam). 3 daqiqa vaqt bor."
            )
            code = await asyncio.to_thread(_tg_poll_code, 180)
            if not code:
                _tg_send_dm(f"⌛ IG login · {username} · kod kelmadi, bekor qilindi.")
                return None, "kod kelmadi (timeout)"

            filled = False
            for sel in _CODE_SELECTORS:
                try:
                    await page.fill(sel, code, timeout=4000)
                    filled = True
                    break
                except Exception:  # noqa: BLE001, S112 — try the next selector
                    continue
            if not filled:
                # Last resort: first visible text/tel input on the page.
                for inp in await page.query_selector_all("input"):
                    t = await inp.get_attribute("type")
                    if t in ("text", "tel", None) and await inp.is_visible():
                        await inp.fill(code)
                        filled = True
                        break
            if not filled:
                return None, "kod input topilmadi"
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(8000)

        # "Save your login info?" interstitial — dismiss it.
        for txt in _DISMISS_TEXTS:
            try:
                await page.click(f"text={txt}", timeout=2500)
                break
            except Exception:  # noqa: BLE001, S112 — interstitial may be absent
                continue
        await page.wait_for_timeout(2000)

        cookies = await ctx.cookies()
        sid = next(
            (c["value"] for c in cookies if c["name"] == "sessionid" and c.get("value")),
            None,
        )
        if not sid:
            return None, f"sessionid yo'q (url={page.url[:60]})"

        # Persist the full browser session so a later resume skips the login.
        with contextlib.suppress(Exception):
            await ctx.storage_state(path=str(SESSIONS_DIR / f"{username}_browser.json"))
        _tg_send_dm(f"✅ IG Playwright login muvaffaqiyatli · {username} · sessionid olindi")
        log.info("playwright.login_success", username=username)
        return sid, None
    except Exception as exc:  # noqa: BLE001
        log.warning("playwright.login_failed", username=username, error=str(exc)[:160])
        return None, str(exc)[:160]
    finally:
        with contextlib.suppress(Exception):
            await browser.close()
        with contextlib.suppress(Exception):
            await pw.stop()


def _parse_profile_html(html: str, handle: str) -> dict[str, Any]:
    """Pull follower/post counts out of a logged-in profile page's HTML.

    Tries several shapes because IG's markup shifts. Returns ok=False when the
    page is the login wall (no counts present) — the caller treats that as a
    normal best-effort miss, not an error.
    """
    import re

    out: dict[str, Any] = {"handle": handle, "follower_count": 0, "posts_count": 0, "ok": False}
    m_f = re.search(r'"edge_followed_by":\{"count":(\d+)', html) or re.search(
        r'"follower_count":(\d+)', html
    )
    m_p = re.search(r'"edge_owner_to_timeline_media":\{"count":(\d+)', html) or re.search(
        r'"media_count":(\d+)', html
    )
    if m_f:
        out["follower_count"] = int(m_f.group(1))
        out["posts_count"] = int(m_p.group(1)) if m_p else 0
        out["ok"] = True
        return out
    m_og = re.search(r'og:description" content="([\d.,KMB]+)\s+[Ff]ollowers', html)
    if m_og:
        out["follower_count"] = _parse_compact(m_og.group(1))
        out["ok"] = True
    return out


async def fetch_account_via_browser(handle: str, *, max_retries: int = 3) -> dict[str, Any]:
    """Best-effort logged-in profile scrape through a real browser.

    Reuses the stored browser session (storage_state from login_via_browser) and,
    when IG_SCRAPER_PROXY_URL is set, egresses through it. WITHOUT a residential
    proxy this is unreliable on purpose: Instagram quickly walls automated
    requests from a datacenter IP (serves the login wall after a few hits). So
    we retry a few times with progressive waits and give up — callers MUST treat
    {"ok": False} as a normal outcome, not an error. With a clean residential
    proxy the same code path becomes reliable.
    """
    import json

    raw = os.getenv("IG_SCRAPER_ACCOUNTS") or "[]"
    try:
        accounts = json.loads(raw)
    except Exception:  # noqa: BLE001
        accounts = []
    if not accounts:
        return {"ok": False, "reason": "no_scraper_accounts", "handle": handle}

    # Lazy import — session_pool imports heavy IG deps; keep module load cheap.
    from app.integrations.instagram.session_pool import SESSIONS_DIR

    username = (accounts[0] or {}).get("username", "")
    state_path = SESSIONS_DIR / f"{username}_browser.json"
    if not state_path.exists():
        return {"ok": False, "reason": "no_browser_session", "handle": handle}

    handle_clean = handle.lstrip("@").strip()
    pw = await async_playwright().start()
    launch_kw: dict[str, Any] = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
    }
    proxy = _proxy_url()
    if proxy:
        launch_kw["proxy"] = _playwright_proxy(proxy)
    browser = await pw.chromium.launch(**launch_kw)
    try:
        for attempt in range(max_retries):
            ctx = await browser.new_context(
                storage_state=str(state_path),
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1280, "height": 800},
            )
            page = await ctx.new_page()
            with contextlib.suppress(Exception):
                await _stealth.apply_stealth_async(page)
            try:
                await page.goto(
                    f"https://www.instagram.com/{handle_clean}/",
                    wait_until="domcontentloaded",
                    timeout=35000,
                )
                await page.wait_for_timeout(3500 + attempt * 2500)  # progressive backoff
                data = _parse_profile_html(await page.content(), handle_clean)
                if data.get("ok"):
                    log.info("browser_scrape.ok", handle=handle_clean, attempt=attempt)
                    return data
            except Exception as exc:  # noqa: BLE001
                log.info(
                    "browser_scrape.attempt_failed",
                    handle=handle_clean,
                    attempt=attempt,
                    error=str(exc)[:80],
                )
            finally:
                with contextlib.suppress(Exception):
                    await ctx.close()
        # A sustained login wall means IG is actively blocking this IP — back the
        # whole service off so we stop hammering and getting flagged further.
        from app.integrations.instagram import rate_limiter

        rate_limiter.trip_cooldown(2)  # 2h — softer than the 8h a hard 429 triggers
        log.warning("browser_scrape.login_wall", handle=handle_clean, attempts=max_retries)
        return {"ok": False, "reason": "login_wall", "handle": handle_clean}
    finally:
        with contextlib.suppress(Exception):
            await browser.close()
        with contextlib.suppress(Exception):
            await pw.stop()

"""Pool of pre-authenticated instagrapi sessions.

We rotate across 2-3 throwaway Instagram accounts to spread the per-account
rate-limit (~200 req/hour). Each session is pickled to disk so we don't have
to re-login on every restart (Instagram flags fresh logins more often than
returning sessions).

NEVER use the founder's personal account here — ban risk is real.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import random
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import structlog
from instagrapi import Client  # type: ignore[import-untyped]

from app.integrations import telegram

log = structlog.get_logger(__name__)


def _stable_uuids(username: str) -> dict[str, str]:
    """Deterministic device identity for an account, derived from its username.

    Instagram ties a session to the device that created it. instagrapi
    otherwise randomises the device UUIDs on every fresh login, so each deploy
    (or each sessionid bootstrap) looked like a NEW device → Instagram flagged
    it as a suspicious login and killed the session. Seeding the UUIDs from the
    username makes the device identical across deploys, so a session — once
    established — survives far longer.
    """
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"smm-ig-device:{username}")
    return {
        "phone_id": str(uuid.uuid5(ns, "phone_id")),
        "uuid": str(uuid.uuid5(ns, "uuid")),
        "client_session_id": str(uuid.uuid5(ns, "client_session_id")),
        "advertising_id": str(uuid.uuid5(ns, "advertising_id")),
        "device_id": "android-" + uuid.uuid5(ns, "device_id").hex[:16],
    }


def _is_dead_session_error(exc: Exception) -> bool:
    """A redirect storm / login-required during sessionid bootstrap means the
    sessionid is dead (Instagram bounces it to the login page). Treat it as a
    signal to fall back to a password login rather than benching the account."""
    name = type(exc).__name__.lower()
    s = str(exc).lower()
    return (
        "redirect" in name
        or "redirect" in s
        or "loginrequired" in name
        or "login_required" in s
    )

# Allow override via IG_SESSIONS_DIR; default to `./.smm-sessions` on dev and
# `/tmp/.smm-sessions` in container (pwuser can't write to /app).
def _resolve_sessions_dir() -> Path:
    """First *writable* dir among: $IG_SESSIONS_DIR (persistent Docker volume in
    prod), ./.smm-sessions (dev), /tmp/.smm-sessions (ephemeral last resort).

    The explicit path is a mounted volume in production so a once-trusted IG
    session survives redeploys. Without persistence every deploy forces a fresh
    login, which re-triggers Instagram's suspicious-login challenge.
    """
    candidates: list[Path] = []
    explicit = os.getenv("IG_SESSIONS_DIR")
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path(".smm-sessions"))
    fallback = Path("/tmp/.smm-sessions")  # noqa: S108 — last-resort ephemeral dir
    candidates.append(fallback)

    for cand in candidates:
        try:
            cand.mkdir(parents=True, exist_ok=True)
            probe = cand / ".write_test"
            probe.write_text("ok")
            probe.unlink()
            if cand != candidates[0]:
                log.info("session_pool.sessions_dir_fallback", path=str(cand))
            return cand
        except (PermissionError, OSError):
            continue
    return fallback

SESSIONS_DIR = _resolve_sessions_dir()


def _read_challenge_code() -> str | None:
    """A one-time IG verification code an operator drops into the
    IG_CHALLENGE_CODE env var or {SESSIONS_DIR}/challenge_code.txt."""
    env_code = os.getenv("IG_CHALLENGE_CODE")
    if env_code and env_code.strip():
        return env_code.strip()
    try:
        p = SESSIONS_DIR / "challenge_code.txt"
        if p.exists():
            return p.read_text().strip() or None
    except OSError:
        pass
    return None


# ── Interactive Telegram challenge flow ──────────────────────────────────
# When IG demands a verification code, the bot DMs the operator and then polls
# getUpdates for their reply, so the whole login self-heals over Telegram with
# no shell access. SYNC (httpx) because instagrapi calls the handler inside a
# worker thread — the async telegram.send() queue has no event loop there.


def _tg_token() -> str | None:
    return os.getenv("TELEGRAM_BOT_TOKEN") or None


def _challenge_chat_id() -> str | None:
    """Who to DM for the code. Personal Telegram user id preferred so the code
    isn't posted to the shared log channel. The user must have pressed /start
    on the bot first (Telegram only lets bots DM users who started them)."""
    return (
        os.getenv("IG_CHALLENGE_TELEGRAM_ID")
        or os.getenv("TELEGRAM_LOG_CHANNEL_ID")
        or None
    )


def _tg_send_dm(text: str) -> None:
    token, chat = _tg_token(), _challenge_chat_id()
    if not (token and chat):
        return
    with contextlib.suppress(Exception):
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "disable_web_page_preview": True},
            timeout=10.0,
        )


def _extract_code(text: str) -> str | None:
    """Pull a 4-8 digit IG code out of a Telegram message ('kod 123456' → 123456)."""
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits if 4 <= len(digits) <= 8 else None


def _tg_poll_code(timeout_s: int = 180) -> str | None:
    """Long-poll getUpdates for a code DM'd by the authorised operator.

    Only accepts a reply from IG_CHALLENGE_TELEGRAM_ID (so a random chat member
    can't inject a code). Drains existing updates first so a stale message
    doesn't count. Returns None on timeout."""
    token = _tg_token()
    authorised = str(_challenge_chat_id() or "")
    if not token:
        return None

    base = f"https://api.telegram.org/bot{token}/getUpdates"
    offset: int | None = None
    deadline = time.time() + timeout_s
    with httpx.Client(timeout=35.0) as c:
        # Drain backlog → set offset past the last existing update.
        with contextlib.suppress(Exception):
            r = c.get(base, params={"timeout": 0})
            ups = r.json().get("result", [])
            if ups:
                offset = ups[-1]["update_id"] + 1
        while time.time() < deadline:
            try:
                r = c.get(base, params={"timeout": 25, "offset": offset})
                for u in r.json().get("result", []):
                    offset = u["update_id"] + 1
                    msg = u.get("message") or u.get("channel_post") or {}
                    frm = str((msg.get("from") or {}).get("id") or msg.get("chat", {}).get("id") or "")
                    # Accept only the authorised operator (or, if no specific id
                    # was set, anyone — single-operator deployments).
                    if authorised and frm and frm != authorised:
                        continue
                    code = _extract_code(msg.get("text") or "")
                    if code:
                        log.info("session_pool.challenge_code_via_telegram")
                        return code
            except Exception:  # noqa: BLE001 — keep polling until the deadline
                time.sleep(2)
    return None


def _challenge_code_handler(username: str, choice: Any) -> str:
    """instagrapi calls this when IG demands an email/SMS code during login.

    Active ONLY when IG_CHALLENGE_INTERACTIVE=1 — a deliberate, operator-
    supervised login. Flow: the bot DMs the operator (IG_CHALLENGE_TELEGRAM_ID),
    then polls getUpdates ~3 min for their reply. Falls back to the
    IG_CHALLENGE_CODE env / challenge_code.txt file. In normal unattended
    operation the flag is unset and we raise immediately so a background worker
    never hangs waiting on a human.
    """
    if os.getenv("IG_CHALLENGE_INTERACTIVE") != "1":
        _tg_send_dm(
            f"🔐 IG tasdiqlash · {username} · kod so'ralyapti, lekin interaktiv handler o'chiq. "
            f"IG_CHALLENGE_INTERACTIVE=1 qo'ying."
        )
        raise RuntimeError("IG challenge required but interactive handler disabled")

    _tg_send_dm(
        f"🔐 IG tasdiqlash · {username}\n"
        f"Instagram email/SMS kod so'radi. Shu yerga kodni yuboring (faqat raqam, masalan 123456). "
        f"3 daqiqa vaqt bor."
    )

    # 1) Wait for the operator's Telegram reply.
    code = _tg_poll_code(timeout_s=180)
    if code:
        _tg_send_dm(f"✅ Kod qabul qilindi ({code}) · {username} · kirishga urinilyapti…")
        log.info("session_pool.challenge_code_used", username=username, via="telegram")
        return code

    # 2) Fallback — env var / file (manual drop).
    for _ in range(20):  # ~60s extra grace
        code = _read_challenge_code()
        if code:
            with contextlib.suppress(OSError):
                (SESSIONS_DIR / "challenge_code.txt").unlink(missing_ok=True)
            log.info("session_pool.challenge_code_used", username=username, via="file")
            return code
        time.sleep(3)

    _tg_send_dm(f"⌛ IG tasdiqlash · {username} · kod kelmadi, urinish bekor qilindi.")
    raise RuntimeError("IG challenge code not supplied within timeout")


@dataclass
class IgAccount:
    username: str
    password: str
    proxy: str | None = None
    # Optional browser-exported sessionid — bootstraps the session WITHOUT a
    # username/password login (which Instagram challenges for fresh accounts on
    # new IPs). Decoded form: "<user_id>:<...>:<...>:<...>".
    sessionid: str | None = None


def _load_accounts() -> list[IgAccount]:
    """Reads `IG_SCRAPER_ACCOUNTS` env JSON: '[{"username":"...","password":"...","proxy":"..."}]'."""
    import os

    raw = os.getenv("IG_SCRAPER_ACCOUNTS")
    if not raw:
        log.warning("session_pool.no_accounts — scrapers will return empty data")
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        log.error("session_pool.bad_json", raw_len=len(raw))
        return []
    return [IgAccount(**it) for it in items]


# How long to bench an IG scraper account after a login/resume failure so a
# flagged or dead session isn't re-login-stormed every cycle — the root cause
# of the prod login_required -> "Exceeded 30 redirects" loop. Override via env.
_COOLDOWN_SECONDS = int(os.getenv("IG_LOGIN_COOLDOWN_S", "3600"))
# Cap for the exponential backoff applied on repeated login failures.
_MAX_COOLDOWN_SECONDS = int(os.getenv("IG_LOGIN_COOLDOWN_MAX_S", str(24 * 3600)))


class SessionPool:
    def __init__(self) -> None:
        self._accounts = _load_accounts()
        self._clients: dict[str, Client] = {}
        self._lock = asyncio.Lock()
        self._last_used: dict[str, float] = {}
        # username -> monotonic ts until which the account is benched after a
        # login failure. Stops the retry-storm on a dead/flagged session.
        self._cooldown_until: dict[str, float] = {}
        # Alert-once-per-episode + exponential backoff so a flagged scraper
        # account doesn't storm Telegram with an hourly "IG login xato".
        self._notified_down: set[str] = set()
        self._fail_count: dict[str, int] = {}

    async def acquire(self) -> Client:
        if not self._accounts:
            raise RuntimeError("No IG scraper accounts configured (set IG_SCRAPER_ACCOUNTS)")

        async with self._lock:
            now = time.monotonic()
            # Skip accounts still in post-failure cooldown. With a single
            # account this makes acquire() fail fast (the caller then degrades
            # to its last cached value) instead of re-attempting a doomed login
            # every cycle — the login_required -> TooManyRedirects storm.
            available = [
                a
                for a in self._accounts
                if self._cooldown_until.get(a.username, 0.0) <= now
            ]
            if not available:
                wait = int(min(self._cooldown_until.values()) - now)
                raise RuntimeError(f"All IG scraper accounts in login cooldown (~{wait}s left)")

            # Round-robin among least-recently-used available accounts.
            acct = sorted(available, key=lambda a: self._last_used.get(a.username, 0.0))[0]
            self._last_used[acct.username] = now

            client = self._clients.get(acct.username)
            if client is None:
                try:
                    client = await asyncio.to_thread(_login_or_resume, acct)
                except Exception as exc:  # noqa: BLE001
                    # Bench the account so the next acquire() skips it rather
                    # than re-storming the same failing login. Back off
                    # exponentially on repeated failures (1h -> 2h -> ... -> 24h).
                    self._fail_count[acct.username] = self._fail_count.get(acct.username, 0) + 1
                    fails = self._fail_count[acct.username]
                    cooldown = min(_COOLDOWN_SECONDS * (2 ** (fails - 1)), _MAX_COOLDOWN_SECONDS)
                    self._cooldown_until[acct.username] = now + cooldown
                    log.warning(
                        "session_pool.login_failed_cooldown",
                        username=acct.username,
                        error=repr(exc),
                        cooldown_s=cooldown,
                        fails=fails,
                    )
                    # Alert ONCE when an account goes down (cleared on recovery
                    # below) — not on every hourly retry. Scraper login failures
                    # don't affect the core product, so keep the Telegram noise low.
                    if acct.username not in self._notified_down:
                        self._notified_down.add(acct.username)
                        name = type(exc).__name__
                        # A Bloks checkpoint / challenge can't be cleared by code —
                        # IG deliberately wants a human to confirm on a trusted
                        # device. Give the exact recovery steps instead of a vague
                        # "session dead". A plain redirect/login-required usually
                        # means the sessionid is dead → just refresh it.
                        if "Challenge" in name or "Checkpoint" in name:
                            hint = (
                                f" — IG checkpoint. Telefon IG ilovasida yoki brauzerda "
                                f"(proxy IP {os.getenv('IG_SCRAPER_PROXY_URL','')[:40]}…) @{acct.username} "
                                f"akkauntiga kirib LOGIN'ni qo'lda tasdiqlang ('Bu men edim'), "
                                f"1-2 kun ishlating, keyin yangi sessionid'ni IG_SCRAPER_ACCOUNTS'ga qo'ying"
                            )
                        elif "Redirect" in name or "LoginRequired" in name:
                            hint = " — sessionid o'lgan, yangi sessionid kerak (residential proxy IP'dan)"
                        else:
                            hint = ""
                        telegram.send(
                            f"📷 IG login xato · {acct.username} · {name}{hint} · "
                            f"~{cooldown // 60}daq cooldown (scraper akkaunt — asosiy ish ta'sirlanmaydi)"
                        )
                    raise
                self._clients[acct.username] = client
                recovered = acct.username in self._notified_down
                self._notified_down.discard(acct.username)
                self._fail_count.pop(acct.username, None)
                telegram.send(
                    f"📷 IG akkaunt {'tiklandi' if recovered else 'ulandi'} · {acct.username}"
                )

            # Random delay so we don't look like a bot
            await asyncio.sleep(random.uniform(0.5, 2.0))  # noqa: S311 — anti-bot jitter, not crypto
            return client

    async def release(self, _client: Client) -> None:
        # The lock is per-acquire; nothing to do on release. Keeping the API
        # symmetric so we can add per-account semaphore later if rate-limits
        # tighten.
        return None

    def evict(self, username: str, *, cooldown: bool = True) -> None:
        """Drop a cached client whose session died mid-use and (optionally) bench
        the account. A caller that hits LoginRequired on a handed-out client
        should call this so the next acquire() re-logins or skips it, instead of
        being handed the same broken client again."""
        self._clients.pop(username, None)
        if cooldown:
            self._cooldown_until[username] = time.monotonic() + _COOLDOWN_SECONDS
        log.warning("session_pool.evicted", username=username, cooldown=cooldown)

    def evict_client(self, client: Client, *, cooldown: bool = True) -> None:
        """Evict by client object — for callers (the IG fetch helpers) that
        hold the Client but not the username. Matches by identity; no-op if the
        client isn't (or is no longer) pooled."""
        for username, cached in list(self._clients.items()):
            if cached is client:
                self.evict(username, cooldown=cooldown)
                return


def _login_or_resume(acct: IgAccount) -> Client:
    session_path = SESSIONS_DIR / f"{acct.username}.json"
    client = Client()
    client.challenge_code_handler = _challenge_code_handler
    # Cap redirects so a flagged account/IP fails fast instead of spinning into
    # the "Exceeded 30 redirects" storm seen in prod. instagrapi's private
    # transport is a requests.Session; guard the set in case internals differ.
    with contextlib.suppress(Exception):
        client.private.max_redirects = 5
    if acct.proxy:
        client.set_proxy(acct.proxy)
    # Stable device identity so a re-login looks like the SAME device to
    # Instagram (otherwise every bootstrap = a new device = flagged session).
    with contextlib.suppress(Exception):
        client.set_uuids(_stable_uuids(acct.username))

    # 1) Resume a persisted session if we have one (survives redeploys via the
    #    mounted volume). Validate cheaply; drop it if dead.
    if session_path.exists():
        try:
            client.load_settings(session_path)
            # load_settings can restore an older proxy/device — re-apply ours.
            if acct.proxy:
                client.set_proxy(acct.proxy)
            with contextlib.suppress(Exception):
                client.set_uuids(_stable_uuids(acct.username))
            client.get_timeline_feed()
            log.info("session_pool.resumed", username=acct.username)
            return client
        except Exception as exc:  # noqa: BLE001
            log.warning("session_pool.resume_failed", username=acct.username, error=repr(exc))
            with contextlib.suppress(Exception):
                session_path.unlink(missing_ok=True)

    # 2) Bootstrap fresh. Prefer a browser-exported sessionid (skips the login
    #    challenge), but SELF-HEAL: if the sessionid is dead (redirect storm /
    #    login-required), fall through to a username+password login instead of
    #    benching the account on a stale cookie.
    if acct.sessionid:
        try:
            client.login_by_sessionid(acct.sessionid)
            client.get_timeline_feed()  # prove the sessionid is actually alive
            client.dump_settings(session_path)
            log.info("session_pool.session_by_sessionid", username=acct.username)
            return client
        except Exception as exc:  # noqa: BLE001
            if not _is_dead_session_error(exc):
                raise
            log.warning("session_pool.sessionid_dead_falling_back_to_password",
                        username=acct.username, error=repr(exc))
            telegram.send(
                f"📷 IG sessionid o'lik · {acct.username} · {type(exc).__name__} "
                f"→ parol bilan kirishga o'tilyapti (self-heal)"
            )
            # Rebuild a clean client (the failed one carries redirect state).
            client = Client()
            client.challenge_code_handler = _challenge_code_handler
            with contextlib.suppress(Exception):
                client.private.max_redirects = 5
            if acct.proxy:
                client.set_proxy(acct.proxy)
            with contextlib.suppress(Exception):
                client.set_uuids(_stable_uuids(acct.username))

    # 3) Password login — triggers IG's challenge when needed; the handler
    #    (Telegram-alerted) lets an operator drop a one-time code. Once this
    #    succeeds the session is dumped to the volume and reused for weeks.
    client.login(acct.username, acct.password)
    client.dump_settings(session_path)
    log.info("session_pool.logged_in", username=acct.username)
    return client


_pool: SessionPool | None = None


def get_pool() -> SessionPool:
    global _pool
    if _pool is None:
        _pool = SessionPool()
    return _pool

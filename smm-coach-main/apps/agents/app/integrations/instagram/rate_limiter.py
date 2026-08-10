"""Global Instagram request pacer + cooldown.

Instagram aggressively rate-limits a single (especially datacenter) IP. Research
(HikerAPI/Scrapfly/BlackHatWorld, 2025-2026) converges on: keep a real session
under ~1-2 req/s, well below ~100 req/hour, with 2-4s gaps, and on a 429 /
challenge BACK OFF for hours — not minutes.

This module funnels EVERY Instagram request (instagrapi, web_profile_info JSON,
Playwright HTML) through one process-wide limiter so the whole service shares a
single budget rather than each path hammering IG independently. It's in-memory
(resets on restart) — good enough for a single agents process; promote to Redis
if you scale horizontally.

Usage:
    from app.integrations.instagram import rate_limiter
    await rate_limiter.acquire()          # blocks for the inter-request gap
    ... do the IG request ...
    # on a 429 / challenge / login-wall:
    rate_limiter.trip_cooldown()          # pause ALL IG traffic for hours
"""
from __future__ import annotations

import asyncio
import os
import random
import time

import structlog

log = structlog.get_logger(__name__)

# Tunables (env-overridable so ops can tighten without a redeploy).
_HOURLY_CAP = int(os.getenv("IG_RATE_HOURLY_CAP", "100"))
_MIN_GAP_S = float(os.getenv("IG_RATE_MIN_GAP_S", "2.5"))
_MAX_GAP_S = float(os.getenv("IG_RATE_MAX_GAP_S", "4.0"))
# Default cooldown on a hard block — practitioners report 6-12h; we use 8h.
_COOLDOWN_HOURS = float(os.getenv("IG_RATE_COOLDOWN_HOURS", "8"))


class IGRateLimited(Exception):
    """Raised by acquire() when the hourly cap is hit or a cooldown is active.
    Callers should treat this as a soft "skip this IG call" — never a crash."""


class _IGRateLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self._window_start = 0.0
        self._count = 0
        self._cooldown_until = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()

            # 1. Hard cooldown after a block — refuse everything until it lifts.
            if now < self._cooldown_until:
                remaining = (self._cooldown_until - now) / 3600
                raise IGRateLimited(f"cooldown faol — {remaining:.1f}h qoldi")

            # 2. Rolling hourly window.
            if now - self._window_start > 3600:
                self._window_start = now
                self._count = 0
            if self._count >= _HOURLY_CAP:
                raise IGRateLimited(f"soatlik cap ({_HOURLY_CAP}) to'ldi")

            # 3. Inter-request gap with jitter (don't fire back-to-back).
            gap = random.uniform(_MIN_GAP_S, _MAX_GAP_S)  # noqa: S311 — pacing, not crypto
            since_last = now - self._last_request
            if 0 < since_last < gap:
                await asyncio.sleep(gap - since_last)

            self._last_request = time.monotonic()
            self._count += 1

    def trip_cooldown(self, hours: float | None = None) -> None:
        """Pause ALL IG traffic for `hours` (default 8h) — call on 429/challenge."""
        h = hours if hours is not None else _COOLDOWN_HOURS
        self._cooldown_until = time.monotonic() + h * 3600
        log.warning("ig_rate.cooldown_tripped", hours=h)

    def status(self) -> dict:
        now = time.monotonic()
        cooling = now < self._cooldown_until
        return {
            "hourly_count": self._count,
            "hourly_cap": _HOURLY_CAP,
            "cooldown_active": cooling,
            "cooldown_remaining_h": round((self._cooldown_until - now) / 3600, 1) if cooling else 0.0,
        }


_limiter = _IGRateLimiter()


async def acquire() -> None:
    """Block for the inter-request gap; raise IGRateLimited if capped/cooling."""
    await _limiter.acquire()


def trip_cooldown(hours: float | None = None) -> None:
    """Pause all IG traffic for `hours` (default 8h) after a 429/challenge."""
    _limiter.trip_cooldown(hours)


def status() -> dict:
    """Current limiter state — for the admin/workers status panel."""
    return _limiter.status()

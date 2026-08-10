"""Per-tenant LLM budget guard with three independent caps + kill-switch.

  Cap 1 — `tenant_monthly_budget_usd`   (default $20)  per-tenant per month
  Cap 2 — `tenant_daily_budget_usd`     (default $3)   per-tenant per 24h
  Cap 3 — `global_daily_budget_usd`     (default $15)  ALL tenants per 24h
  Cap 4 — `EMERGENCY_DISABLE_LLM=1`     env-var kill switch

When a SOFT cap (1-3) trips, LLM clients downgrade premium models (Opus /
2.5 Pro) to cheap ones (Haiku / Flash) and emit `budget.exceeded` on the SSE
bus — they keep running, just cheaper.

The HARD kill-switch (4) is different: each LLM completion / vision / web-search
client checks `kill_switch_on()` at its entry and short-circuits to a stub
BEFORE any provider call, so no money is spent regardless of bugs / loops.
(Voyage embeddings — negligible cost + needed for retrieval stubs — still run.)

DB spend lookups are TTL-cached (30s per tenant, 30s global) to keep the hot
LLM path under 1ms. CAVEAT: `over_cap` is read-then-act on that cached total, so
many premium calls launched inside one 30s window can all observe a pre-limit
total and proceed — the SOFT caps can overshoot by up to (calls-per-30s ×
per-call cost) before the next read trips them. Acceptable: caps are a safety
net (per-tenant default $20 bounds the blast radius), not a hard ledger; the
hard kill-switch above is the real stop. Tighten via a shorter decision-TTL or
an in-process optimistic counter if overshoot ever matters.
"""
from __future__ import annotations

import asyncio
import os
import time

import structlog

from app.config import get_settings
from app.runs.repository import (
    daily_cost_for_tenant,
    global_cost_today,
    monthly_cost_for_tenant,
    tenant_monthly_budget_override,
)

log = structlog.get_logger(__name__)


# Premium → cheap fallback. Cheap models pass through unchanged.
DEGRADE_MAP: dict[str, str] = {
    "claude-opus-4-7": "claude-haiku-4-5",
    "claude-sonnet-4-6": "claude-haiku-4-5",
    "gemini-3.1-pro": "gemini-2.5-flash",
    "gemini-2.5-pro": "gemini-2.5-flash",
}

_CACHE_TTL_SEC = 30.0
_monthly_cache: dict[str, tuple[float, float]] = {}
_daily_cache: dict[str, tuple[float, float]] = {}
_budget_cache: dict[str, tuple[float, float | None]] = {}  # tenant -> (ts, override)
_global_cache: tuple[float, float] | None = None
_lock = asyncio.Lock()

# One-shot Telegram notification flags. `over_cap` runs on every LLM call, so
# without these we'd spam the channel hundreds of times per minute when a cap
# trips. Each tenant gets at most one "cap hit" message per process; emergency
# disable + global cap fire once total. Reset on restart, which is fine — that's
# when we'd want to re-announce anyway.
_warned_emergency: bool = False
_warned_monthly: set[str] = set()
_warned_daily: set[str] = set()
_warned_global: bool = False


def _emergency_disabled() -> bool:
    global _warned_emergency
    v = os.getenv("EMERGENCY_DISABLE_LLM", "").strip().lower()
    is_on = v in {"1", "true", "yes", "on"}
    if is_on and not _warned_emergency:
        _warned_emergency = True
        try:
            from app.integrations import telegram
            telegram.send(
                "🚨 EMERGENCY_DISABLE_LLM faollashtirildi — premium modellar Haiku'ga tushirildi"
            )
        except Exception:  # noqa: BLE001, S110 — never break LLM path on a reporting hiccup
            pass  # never break LLM path on a reporting hiccup
    return is_on


async def monthly_spent(tenant_id: str) -> float:
    now = time.time()
    async with _lock:
        hit = _monthly_cache.get(tenant_id)
        if hit and now - hit[0] < _CACHE_TTL_SEC:
            return hit[1]
    try:
        spent = await monthly_cost_for_tenant(tenant_id)
    except Exception:  # noqa: BLE001
        log.exception("budget.monthly_lookup_failed", tenant_id=tenant_id)
        spent = 0.0
    async with _lock:
        _monthly_cache[tenant_id] = (now, spent)
    return spent


async def daily_spent(tenant_id: str) -> float:
    now = time.time()
    async with _lock:
        hit = _daily_cache.get(tenant_id)
        if hit and now - hit[0] < _CACHE_TTL_SEC:
            return hit[1]
    try:
        spent = await daily_cost_for_tenant(tenant_id)
    except Exception:  # noqa: BLE001
        log.exception("budget.daily_lookup_failed", tenant_id=tenant_id)
        spent = 0.0
    async with _lock:
        _daily_cache[tenant_id] = (now, spent)
    return spent


async def global_spent_today() -> float:
    global _global_cache
    now = time.time()
    async with _lock:
        if _global_cache and now - _global_cache[0] < _CACHE_TTL_SEC:
            return _global_cache[1]
    try:
        spent = await global_cost_today()
    except Exception:  # noqa: BLE001
        log.exception("budget.global_lookup_failed")
        spent = 0.0
    async with _lock:
        _global_cache = (now, spent)
    return spent


async def monthly_cap_for(tenant_id: str) -> float:
    """Effective monthly cap: per-tenant admin override if set, else the env
    default. TTL-cached like the spend lookups."""
    s = get_settings()
    now = time.time()
    async with _lock:
        hit = _budget_cache.get(tenant_id)
        if hit and now - hit[0] < _CACHE_TTL_SEC:
            override = hit[1]
            return override if override is not None else s.tenant_monthly_budget_usd
    try:
        override = await tenant_monthly_budget_override(tenant_id)
    except Exception:  # noqa: BLE001
        log.exception("budget.override_lookup_failed", tenant_id=tenant_id)
        override = None
    async with _lock:
        _budget_cache[tenant_id] = (now, override)
    return override if override is not None else s.tenant_monthly_budget_usd


async def over_cap(tenant_id: str) -> bool:
    """Any cap trip → premium models will be degraded for this tenant."""
    if _emergency_disabled():
        return True
    s = get_settings()
    # Tracking-only mode (BUDGET_ENFORCE=false): the spend is still recorded into token_usage by the
    # LLM clients (the AI-spend panel keeps counting) — we just never degrade. The hard kill-switch
    # above is intentionally still honored; only the soft per-tenant/global caps are bypassed.
    if not s.budget_enforce:
        return False

    monthly_limit = await monthly_cap_for(tenant_id)
    if monthly_limit > 0:
        spent = await monthly_spent(tenant_id)
        if spent >= monthly_limit:
            log.warning("budget.monthly_cap", tenant_id=tenant_id, limit=monthly_limit)
            if tenant_id not in _warned_monthly:
                _warned_monthly.add(tenant_id)
                try:
                    from app.integrations import telegram
                    telegram.send(
                        f"💸 Budget cap (monthly) · tenant={tenant_id} · "
                        f"spent=${spent:.2f}/${monthly_limit:.2f}"
                    )
                except Exception:  # noqa: BLE001, S110 — never break LLM path on a reporting hiccup
                    pass
            return True
    if s.tenant_daily_budget_usd > 0:
        spent = await daily_spent(tenant_id)
        if spent >= s.tenant_daily_budget_usd:
            log.warning("budget.daily_cap", tenant_id=tenant_id)
            if tenant_id not in _warned_daily:
                _warned_daily.add(tenant_id)
                try:
                    from app.integrations import telegram
                    telegram.send(
                        f"💸 Budget cap (daily) · tenant={tenant_id} · "
                        f"spent=${spent:.2f}/${s.tenant_daily_budget_usd:.2f}"
                    )
                except Exception:  # noqa: BLE001, S110 — never break LLM path on a reporting hiccup
                    pass
            return True
    if s.global_daily_budget_usd > 0:
        spent = await global_spent_today()
        if spent >= s.global_daily_budget_usd:
            log.warning("budget.global_cap")
            global _warned_global
            if not _warned_global:
                _warned_global = True
                try:
                    from app.integrations import telegram
                    telegram.send(
                        f"💸 Budget cap (GLOBAL daily) · "
                        f"spent=${spent:.2f}/${s.global_daily_budget_usd:.2f}"
                    )
                except Exception:  # noqa: BLE001, S110 — never break LLM path on a reporting hiccup
                    pass
            return True
    return False


def kill_switch_on() -> bool:
    """Cheap synchronous check used by callers that should bail before
    even composing a prompt (e.g. background workers).
    """
    return _emergency_disabled()


def degrade(model: str) -> str:
    return DEGRADE_MAP.get(model, model)


def invalidate(tenant_id: str) -> None:
    _monthly_cache.pop(tenant_id, None)
    _daily_cache.pop(tenant_id, None)
    _budget_cache.pop(tenant_id, None)
    # Don't invalidate global — wait for TTL.

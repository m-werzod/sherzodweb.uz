"""coach_supervisor — the proactive "nazoratchi" (Faza 4).

Every 24h it scans each active tenant and surfaces ONE prioritised reminder
into the activity feed (open performance review → unaddressed account weakness
→ lapsed posting cadence). It NEVER auto-acts — the product principle is "stay
on the user's chosen path unless THEY approve a change" — it only reminds, so
the user always decides.

Anti-spam: the same reminder text isn't re-posted within 3 days (emit_message
already dedupes inside 10 minutes; this widens it for the slow supervisor loop).

Started by the FastAPI app on boot when RUN_WORKERS=1, or standalone:
    uv run python -m app.workers.coach_supervisor
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.graphs.dispatcher import dispatch_workflow
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 24 * 60 * 60  # daily sweep
_RESEND_AFTER_DAYS = 3  # don't repeat the same reminder more often than this
_AUTOPILOT_COOLDOWN_HOURS = 6  # mirror the manual replan cooldown
_AUTOPILOT_MAX_PER_WEEK = 3  # hard cap: persistent underperformance must not auto-replan endlessly
# (each replan is a full LLM roadmap run); past this the user is nudged to review manually instead.


def should_autopilot_replan(
    autopilot: bool,
    has_open_underperform: bool,
    hours_since_last_replan: float | None,
    cooldown_hours: float = _AUTOPILOT_COOLDOWN_HOURS,
    *,
    replans_this_week: int = 0,
    max_per_week: int = _AUTOPILOT_MAX_PER_WEEK,
) -> bool:
    """Pure decision: auto-apply a replan only when the user opted into autopilot, a confirmed
    underperformance is open, we're past the replan cooldown, AND we haven't already hit the weekly
    auto-replan cap (so a clip that keeps flopping can't burn an LLM replan every 6h forever).
    Default (autopilot off) preserves the 'user approves' principle."""
    if not autopilot or not has_open_underperform:
        return False
    if replans_this_week >= max_per_week:
        return False
    return hours_since_last_replan is None or hours_since_last_replan >= cooldown_hours


def _as_obj(v: Any) -> Any:
    """jsonb columns come back as dict/list (asyncpg) or str (some drivers)."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return None
    return v


async def _reminder_for(session: Any, tenant_id: str) -> str | None:
    """Return the single highest-priority reminder for this tenant, or None."""
    # 1) Open UNDERPERFORM review — the strongest "you have a decision pending".
    # breakout/negative_wave are per-post nudges surfaced by the banner, not a
    # replan decision, so this reminder filters to the roadmap-level kind.
    pr = (
        await session.execute(
            text(
                'SELECT "recommendedPivots" FROM performance_reviews '
                "WHERE \"tenantId\" = :t AND status = 'open' AND kind = 'underperform' "
                'ORDER BY "createdAt" DESC LIMIT 1'
            ),
            {"t": tenant_id},
        )
    ).scalar()
    pivots = _as_obj(pr) or []
    if isinstance(pivots, list) and pivots:
        return (
            f"📊 Natija sharhi tayyor — tavsiya: {pivots[0]} "
            "Yo'l xaritasini shunga moslashtirishni ko'rib chiqing."
        )

    # 2) Unaddressed account weakness from the post-audit.
    da = (
        await session.execute(
            text(
                'SELECT "deepAnalysis" FROM instagram_accounts '
                'WHERE "tenantId" = :t AND "deepAnalysis" IS NOT NULL '
                'ORDER BY "createdAt" DESC LIMIT 1'
            ),
            {"t": tenant_id},
        )
    ).scalar()
    data = _as_obj(da) or {}
    weaknesses = data.get("weaknesses") if isinstance(data, dict) else None
    if isinstance(weaknesses, list) and weaknesses:
        return f"🎯 Diqqat: «{weaknesses[0]}» — bu haftagi kontentni shu kamchilikni yopishga yo'naltiring."

    # 3) Lapsed posting cadence — consistency is the algorithm's main signal.
    last = (
        await session.execute(
            text(
                'SELECT MAX("publishedAt") FROM content_tasks '
                "WHERE \"tenantId\" = :t AND status = 'published'"
            ),
            {"t": tenant_id},
        )
    ).scalar()
    if last is not None:
        now = datetime.now(UTC)
        last_dt = last if last.tzinfo else last.replace(tzinfo=UTC)
        days = (now - last_dt).days
        if days >= 7:
            # Bucket to WHOLE WEEKS so the reminder string is stable within a lapse period. The exact
            # day count changed the message every day → _recently_sent (exact-content dedup) never
            # matched → the nudge re-spammed DAILY. Weekly-stable text lets the 3-day resend window
            # actually apply (the pivot/weakness branches above are already stable, so they stay exact).
            weeks = days // 7
            return (
                f"⏰ {weeks} haftadan beri yangi post yo'q — muntazamlik o'sish uchun muhim. "
                "Navbatdagi postni rejalashtiring."
            )
    return None


async def _recently_sent(session: Any, tenant_id: str, content: str) -> bool:
    row = (
        await session.execute(
            text(
                """
                SELECT 1 FROM agent_messages
                WHERE "tenantId" = :t AND agent = 'audience' AND content = :c
                  AND "createdAt" > NOW() - (CAST(:d AS int) || ' days')::interval
                LIMIT 1
                """
            ),
            {"t": tenant_id, "c": content, "d": _RESEND_AFTER_DAYS},
        )
    ).scalar()
    return row is not None


async def _maybe_autopilot_replan(session: Any, tenant_id: str, user_id: str | None) -> bool:
    """If the tenant enabled autopilot AND has an open underperform alert AND
    isn't on replan cooldown, AUTO-dispatch a replan (the replan's
    roadmap_generator consumes the open review's pivots) and tell the user.
    Returns True when a replan was fired (so the caller skips the reminder)."""
    autopilot = (
        await session.execute(
            text(
                'SELECT "autopilotReplan" FROM onboarding_profiles '
                'WHERE "tenantId" = :t ORDER BY "createdAt" DESC LIMIT 1'
            ),
            {"t": tenant_id},
        )
    ).scalar()
    has_open = (
        await session.execute(
            text(
                "SELECT 1 FROM performance_reviews WHERE \"tenantId\" = :t "
                "AND status = 'open' AND kind = 'underperform' LIMIT 1"
            ),
            {"t": tenant_id},
        )
    ).scalar() is not None
    last_replan = (
        await session.execute(
            text('SELECT MAX("createdAt") FROM agent_runs WHERE "tenantId" = :t AND workflow = \'replan\''),
            {"t": tenant_id},
        )
    ).scalar()
    hours: float | None = None
    if last_replan is not None:
        last_dt = last_replan if last_replan.tzinfo else last_replan.replace(tzinfo=UTC)
        hours = (datetime.now(UTC) - last_dt).total_seconds() / 3600.0

    # Weekly cap: count THIS tenant's autopilot replans in the last 7 days (their run id carries the
    # 'autopilot-replan:{tenant}:' prefix) so persistent underperformance can't auto-replan forever.
    weekly = (
        await session.execute(
            text(
                "SELECT count(*) FROM agent_runs WHERE id LIKE :pat "
                "AND \"createdAt\" > now() - interval '7 days'"
            ),
            {"pat": f"autopilot-replan:{tenant_id}:%"},
        )
    ).scalar() or 0

    if not should_autopilot_replan(bool(autopilot), has_open, hours, replans_this_week=int(weekly)):
        return False

    window = int(datetime.now(UTC).timestamp() // (_AUTOPILOT_COOLDOWN_HOURS * 3600))
    try:
        await dispatch_workflow(
            tenant_id=tenant_id,
            user_id=user_id,
            workflow="replan",
            thread_id=None,
            payload={"reason": "autopilot"},
            idempotency_key=f"autopilot-replan:{tenant_id}:{window}",
        )
    except Exception:  # noqa: BLE001
        log.exception("coach_supervisor.autopilot_dispatch_failed", tenant_id=tenant_id)
        return False
    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="audience",
        role="Murabbiy",
        content="🤖 Avtopilot: oxirgi natijalar past chiqdi — yo'l xaritasi avtomatik moslashtirilmoqda.",
        important=True,
    )
    log.info("coach_supervisor.autopilot_replan", tenant_id=tenant_id)
    return True


async def _run_once() -> None:
    sm = get_sessionmaker()
    reminders = 0
    async with sm() as session:
        tenants = (
            await session.execute(
                text(
                    """
                    SELECT DISTINCT t.id AS tenant_id, u.id AS user_id
                    FROM tenants t
                    JOIN users u ON u."tenantId" = t.id
                    WHERE EXISTS (
                      SELECT 1 FROM roadmaps r
                      WHERE r."tenantId" = t.id AND r.status = 'active'
                    )
                    """
                )
            )
        ).mappings().all()

        for row in tenants:
            tenant_id = row["tenant_id"]
            try:
                # Autopilot: when the user opted in, an open underperformance
                # AUTO-applies a replan (and we skip the manual reminder).
                if await _maybe_autopilot_replan(session, tenant_id, row["user_id"]):
                    continue
                msg = await _reminder_for(session, tenant_id)
                if not msg or await _recently_sent(session, tenant_id, msg):
                    continue
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "coach_supervisor.assess_failed", tenant_id=tenant_id, error=repr(exc)[:200]
                )
                continue
            await emit_message(
                tenant_id=tenant_id,
                user_id=row["user_id"],
                agent="audience",
                role="Murabbiy",
                content=msg,
                important=True,
            )
            reminders += 1

    log.info("coach_supervisor.done", tenants=len(tenants), reminders=reminders)


async def loop_forever() -> None:
    log.info("coach_supervisor.start", interval_seconds=INTERVAL_SECONDS)
    while True:
        try:
            await _run_once()
        except Exception:  # noqa: BLE001
            log.exception("coach_supervisor.batch_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(loop_forever())

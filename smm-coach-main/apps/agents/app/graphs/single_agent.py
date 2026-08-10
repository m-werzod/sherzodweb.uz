"""Run ONE agent node on the tenant's current data, synchronously.

Powers the voice coach's "give this agent a task and report back" capability:
the coach asks (e.g.) the roadmap critic to review the current roadmap; we
build the minimal state that node needs from the DB, run just that node, and
return its output directly — no full workflow, no re-persistence.

Only the agents that operate on the current roadmap + north-star are runnable
standalone (critique / scoring / market signals). Workers, guards that need
mid-flow script state, and IG-scrape-heavy nodes are intentionally excluded.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import structlog
from sqlalchemy import text

from app.graphs.nodes import (
    adversarial_critic,
    groq_scorer,
    industry_news,
    market_analyst,
    openai_critic,
)
from app.graphs.state import GrowthCoachState, empty_cost

if TYPE_CHECKING:
    from app.graphs.state import NorthStar, TaskDraft
from app.memory.db import get_sessionmaker
from app.runs.context import RunContext, reset_current, set_current

log = structlog.get_logger(__name__)

# Friendly key → node.run. Only nodes that work off proposed_tasks + north_star.
_RUNNABLE = {
    "openai_critic": openai_critic.run,
    "groq_scorer": groq_scorer.run,
    "adversarial_critic": adversarial_critic.run,
    "market_analyst": market_analyst.run,
    "industry_news": industry_news.run,
}

# Output keys worth returning to the coach (per node — we return whatever's set).
_SUMMARY_KEYS = (
    "critic_summary",
    "market_signals",
    "industry_signals",
    "adversarial_findings",
    "analysis_summary",
    "notes",
)


async def _load_state(tenant_id: str, user_id: str | None, run_id: str) -> GrowthCoachState:
    """Build a minimal GrowthCoachState from the tenant's active roadmap +
    onboarding, so a single node has the inputs it reads."""
    sm = get_sessionmaker()
    async with sm() as session:
        task_rows = await session.execute(
            text(
                """
                SELECT title, type, hook
                FROM content_tasks
                WHERE "tenantId" = :tid
                  AND "roadmapId" = (
                      SELECT id FROM roadmaps
                      WHERE "tenantId" = :tid AND status = 'active'
                      ORDER BY "createdAt" DESC LIMIT 1
                  )
                  AND "isStation" = false
                ORDER BY "orderInBranch"
                LIMIT 120
                """
            ),
            {"tid": tenant_id},
        )
        tasks = task_rows.mappings().all()
        onb_row = await session.execute(
            text(
                """
                SELECT niche, "nicheDetail", "targetAudience", "currentFollowers", "targetFollowers"
                FROM onboarding_profiles
                WHERE "tenantId" = :tid
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": tenant_id},
        )
        onb = onb_row.mappings().first()

    north_star: dict[str, Any] = {}
    if onb:
        north_star = {
            "niche": onb.get("niche") or "",
            "niche_detail": onb.get("nicheDetail") or "",
            "target_audience": onb.get("targetAudience") or "",
            "current_followers": int(onb.get("currentFollowers") or 0),
            "target_followers": int(onb.get("targetFollowers") or 0),
            "region": "uz",
        }
    proposed = [
        {
            "title": t.get("title") or "",
            "type": t.get("type") or "reel",
            "hook": t.get("hook") or "",
            "goal_description": t.get("hook") or "",
        }
        for t in tasks
    ]
    return GrowthCoachState(
        tenant_id=tenant_id,
        user_id=user_id,
        workflow="agent_probe",
        run_id=run_id,
        north_star=cast("NorthStar", north_star),
        proposed_tasks=cast("list[TaskDraft]", proposed),
        approved_tasks=cast("list[TaskDraft]", list(proposed)),
        market_signals=[],
        industry_signals=[],
        tracker_observations=[],
        rejected_tasks=[],
        drift_warnings=[],
        validation_errors=[],
        cost=empty_cost(),
        notes=[],
    )


async def run_single_agent(*, tenant_id: str, user_id: str | None, agent: str) -> dict[str, Any]:
    """Run one agent node now and return its output (synchronous)."""
    node = _RUNNABLE.get(agent)
    if node is None:
        return {
            "ok": False,
            "error": f"'{agent}' alohida ishga tushirilmaydi",
            "runnable": sorted(_RUNNABLE),
        }

    run_id = uuid.uuid4().hex
    state = await _load_state(tenant_id, user_id, run_id)
    if not state.get("proposed_tasks"):
        return {"ok": False, "agent": agent, "error": "Aktiv yo'l xaritasi topilmadi — avval roadmap kerak."}

    token = set_current(
        RunContext(tenant_id=tenant_id, user_id=user_id, run_id=run_id, workflow="agent_probe")
    )
    try:
        out = await node(state)
    except Exception as exc:  # noqa: BLE001 — one agent's failure must not 500
        log.warning("single_agent.failed", agent=agent, error=str(exc)[:160])
        return {"ok": False, "agent": agent, "error": str(exc)[:200]}
    finally:
        reset_current(token)

    result = {k: out.get(k) for k in _SUMMARY_KEYS if out.get(k) is not None}
    return {
        "ok": True,
        "agent": agent,
        "run_id": run_id,
        "task_count": len(state.get("proposed_tasks") or []),
        "result": result or {"note": "Agent ishladi, lekin bu vazifalar uchun qo'shimcha natija qaytarmadi."},
    }

"""Persistence helpers for AgentRun + TokenUsage rows.

The dispatcher writes one AgentRun row per workflow invocation. Each LLM
call inside the workflow appends a TokenUsage row attributed via
RunContext (contextvars). Both tables are queried by the admin dashboard
to surface per-tenant cost and history.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import text

from app.graphs.state import CostLedger
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)


async def create_run(
    *,
    run_id: str,
    tenant_id: str,
    user_id: str | None,
    workflow: str,
    thread_id: str,
    payload: dict[str, Any],
) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                """
                INSERT INTO agent_runs
                  (id, "tenantId", "userId", workflow, "threadId", status, input,
                   "createdAt", "updatedAt")
                VALUES
                  (:id, :tenant_id, :user_id, :workflow, :thread_id, 'queued',
                   CAST(:input AS jsonb), NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": run_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "workflow": workflow,
                "thread_id": thread_id,
                "input": json.dumps(payload, default=str, ensure_ascii=False),
            },
        )
        await session.commit()


async def mark_completed(run_id: str, *, output: dict[str, Any], cost: CostLedger) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                """
                UPDATE agent_runs
                SET status = 'completed',
                    output = CAST(:output AS jsonb),
                    "inputTokens" = :it,
                    "outputTokens" = :ot,
                    "cachedTokens" = :ct,
                    "costUsd" = :cost,
                    "endedAt" = NOW(),
                    "updatedAt" = NOW()
                WHERE id = :id AND status = 'running'
                """
            ),
            {
                "id": run_id,
                "output": json.dumps(output, default=str, ensure_ascii=False),
                "it": cost["input_tokens"],
                "ot": cost["output_tokens"],
                "ct": cost["cached_tokens"],
                "cost": Decimal(str(round(cost["cost_usd"], 6))),
            },
        )
        await session.commit()


async def mark_failed(run_id: str, *, error: str) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                """
                UPDATE agent_runs
                SET status = 'failed',
                    error = :error,
                    "endedAt" = NOW(),
                    "updatedAt" = NOW()
                WHERE id = :id AND status = 'running'
                """
            ),
            {"id": run_id, "error": error[:2000]},
        )
        await session.commit()


async def reset_revising_task(tenant_id: str, task_id: str, prev_status: str) -> None:
    """Restore a content task stuck in 'revising' back to its prior status — used
    when a content_review/regenerate run crashes BEFORE the persister node (which
    is the only other place that clears 'revising'). Guarded on status='revising'
    so a concurrent success is never clobbered. Best-effort."""
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                """
                UPDATE content_tasks
                SET status = :prev, "updatedAt" = NOW()
                WHERE id = :id AND "tenantId" = :tid AND status = 'revising'
                """
            ),
            {"prev": prev_status or "in_progress", "id": task_id, "tid": tenant_id},
        )
        await session.commit()


async def heartbeat_run(run_id: str, lease_seconds: int = 600) -> None:
    """Touch updatedAt AND extend the visibility-timeout lease so a LIVE run keeps
    its claim — the run_worker only reclaims (or the reaper only fails) a run whose
    lease has EXPIRED (= a dead driver). Called per graph node; best-effort: a
    heartbeat failure must never break the actual run."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text(
                    'UPDATE agent_runs SET "updatedAt" = NOW(), '
                    '"leaseExpiresAt" = NOW() + make_interval(secs => :lease) '
                    "WHERE id = :id AND status = 'running'"
                ),
                {"id": run_id, "lease": lease_seconds},
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        log.warning("repository.heartbeat_failed", run_id=run_id)


async def reap_dead_runs(max_attempts: int, *, legacy_stale_seconds: int = 1800) -> list[str]:
    """Fail in-flight runs that are truly dead:
      (a) crashed REPEATEDLY — expired lease + already at/over the attempt cap (the
          run_worker reclaims/resumes everything BELOW the cap), or
      (b) a `running` orphan with NO lease that hasn't heartbeat in a long time —
          a pre-T7.1 dispatch (in-memory task, no lease) stranded by a restart.
    Returns reaped ids.

    A never-claimed `queued` row has a NULL lease but is left alone (status stays
    'queued', so clause (b)'s status='running' guard protects it — it's waiting for
    a free worker, not dead). The first reaper iteration runs on boot.
    """
    sm = get_sessionmaker()
    async with sm() as session:
        rows = (
            await session.execute(
                text(
                    """
                    UPDATE agent_runs
                    SET status = 'failed', error = :err, "endedAt" = NOW(), "updatedAt" = NOW()
                    WHERE status IN ('queued', 'running')
                      AND (
                        ("leaseExpiresAt" IS NOT NULL
                         AND "leaseExpiresAt" < NOW()
                         AND attempts >= :max_attempts)
                        OR (status = 'running'
                            AND "leaseExpiresAt" IS NULL
                            AND "updatedAt" < NOW() - make_interval(secs => :legacy_stale))
                      )
                    RETURNING id
                    """
                ),
                {
                    "err": "Jarayon bir necha marta uzildi — qayta urinib ko'ring.",
                    "max_attempts": max_attempts,
                    "legacy_stale": legacy_stale_seconds,
                },
            )
        ).mappings().all()
        await session.commit()
        return [r["id"] for r in rows]


async def claim_run(session: Any, *, lease_seconds: int, max_attempts: int) -> dict[str, Any] | None:
    """Claim one runnable agent_run for this worker: a fresh `queued` row, OR a
    `running` row whose lease EXPIRED (its driver died) and is still under the
    attempt cap (so it can be resumed). FOR UPDATE SKIP LOCKED makes the claim
    race-safe across pollers/replicas. Sets running + bumps attempts + (re)sets
    the lease. Returns the row to drive, or None if nothing is runnable.
    """
    row = (
        await session.execute(
            text(
                """
                UPDATE agent_runs
                SET status = 'running',
                    attempts = attempts + 1,
                    "startedAt" = COALESCE("startedAt", NOW()),
                    "leaseExpiresAt" = NOW() + make_interval(secs => :lease_seconds),
                    "updatedAt" = NOW()
                WHERE id = (
                    SELECT id FROM agent_runs
                    WHERE status = 'queued'
                       OR (status = 'running'
                           AND "leaseExpiresAt" IS NOT NULL
                           AND "leaseExpiresAt" < NOW()
                           AND attempts < :max_attempts)
                    ORDER BY "createdAt" ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, "tenantId", "userId", workflow, "threadId", input, attempts
                """
            ),
            {"lease_seconds": lease_seconds, "max_attempts": max_attempts},
        )
    ).mappings().first()
    await session.commit()
    if row is None:
        return None
    return {
        "run_id": row["id"],
        "tenant_id": row["tenantId"],
        "user_id": row["userId"],
        "workflow": row["workflow"],
        "thread_id": row["threadId"],
        "payload": row["input"] or {},
        "attempts": row["attempts"],
    }


async def record_token_usage(
    *,
    tenant_id: str,
    run_id: str | None,
    agent: str,
    provider: str,
    model: str,
    cost: CostLedger,
) -> None:
    if cost["input_tokens"] == 0 and cost["output_tokens"] == 0:
        return
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                """
                INSERT INTO token_usage
                  (id, "tenantId", "runId", agent, provider, model,
                   "inputTokens", "outputTokens", "cachedTokens", "costUsd", "createdAt")
                VALUES
                  (:id, :tenant_id, :run_id, :agent, :provider, :model,
                   :it, :ot, :ct, :cost, NOW())
                """
            ),
            {
                "id": uuid.uuid4().hex,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "agent": agent,
                "provider": provider,
                "model": model,
                "it": cost["input_tokens"],
                "ot": cost["output_tokens"],
                "ct": cost["cached_tokens"],
                "cost": Decimal(str(round(cost["cost_usd"], 6))),
            },
        )
        await session.commit()


async def fetch_run(run_id: str) -> dict[str, Any] | None:
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT id, "tenantId", "userId", workflow, "threadId", status,
                       output, error, "inputTokens", "outputTokens", "cachedTokens",
                       "costUsd", "startedAt", "endedAt", "createdAt"
                FROM agent_runs WHERE id = :id
                """
            ),
            {"id": run_id},
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "runId": row["id"],
            "tenantId": row["tenantId"],
            "userId": row["userId"],
            "workflow": row["workflow"],
            "threadId": row["threadId"],
            "status": row["status"],
            "output": row["output"],
            "error": row["error"],
            "inputTokens": row["inputTokens"],
            "outputTokens": row["outputTokens"],
            "cachedTokens": row["cachedTokens"],
            "costUsd": float(row["costUsd"] or 0),
            "startedAt": _iso(row["startedAt"]),
            "endedAt": _iso(row["endedAt"]),
            "createdAt": _iso(row["createdAt"]),
        }


async def monthly_cost_for_tenant(tenant_id: str) -> float:
    """Returns total USD cost for the current calendar month."""
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT COALESCE(SUM("costUsd"), 0) AS total
                FROM token_usage
                WHERE "tenantId" = :tenant_id
                  AND "createdAt" >= DATE_TRUNC('month', NOW())
                """
            ),
            {"tenant_id": tenant_id},
        )
        row = result.first()
        return float(row[0]) if row else 0.0


async def tenant_monthly_budget_override(tenant_id: str) -> float | None:
    """Per-tenant monthly LLM budget override (USD) set by an admin, or None
    to use the global env default. Read from tenants.monthlyBudgetUsd."""
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text('SELECT "monthlyBudgetUsd" FROM tenants WHERE id = :tenant_id'),
            {"tenant_id": tenant_id},
        )
        row = result.first()
        if row and row[0] is not None:
            return float(row[0])
    return None


async def daily_cost_for_tenant(tenant_id: str) -> float:
    """Returns total USD cost for today (rolling 24h)."""
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT COALESCE(SUM("costUsd"), 0) AS total
                FROM token_usage
                WHERE "tenantId" = :tenant_id
                  AND "createdAt" >= NOW() - INTERVAL '24 hours'
                """
            ),
            {"tenant_id": tenant_id},
        )
        row = result.first()
        return float(row[0]) if row else 0.0


async def global_cost_today() -> float:
    """Returns total USD cost across ALL tenants for today.
    Used by the EMERGENCY_DISABLE_LLM safety net to prevent a single bug
    from burning the entire credit pool overnight.
    """
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT COALESCE(SUM("costUsd"), 0) AS total
                FROM token_usage
                WHERE "createdAt" >= NOW() - INTERVAL '24 hours'
                """
            )
        )
        row = result.first()
        return float(row[0]) if row else 0.0


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

"""Shared writer for PerformanceReview alert rows (Stage 13).

Three nodes raise alerts the dashboard's PerformanceBanner surfaces:
  - performance_review → ``underperform`` (tenant-wide) and ``breakout`` (per-post)
  - comment_sentinel   → ``negative_wave`` (per-post)

They all funnel through ``raise_alert`` so the column set + kind/severity contract
lives in ONE place, and so dedup is uniform: ``tracker_pulse`` re-fetches the last
14 days of posts every 6 hours, so without a guard the SAME post would spawn a
fresh alert on every pulse. ``raise_alert`` skips when an OPEN alert with the same
(tenant, kind, taskId) already exists.
"""
from __future__ import annotations

import json
import uuid

import structlog
from sqlalchemy import text

from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)


async def raise_alert(
    *,
    tenant_id: str,
    kind: str,
    severity: str = "medium",
    summary_count: int = 0,
    root_causes: list | None = None,
    recommended_pivots: list | None = None,
    task_id: str | None = None,
    payload: dict | None = None,
    run_id: str | None = None,
    dedupe: bool = True,
) -> bool:
    """Insert one OPEN PerformanceReview alert. Returns True if a row was written,
    False if it was deduped away or the insert failed.

    Best-effort by contract: the caller's metric/sentiment write has already
    committed before this runs, so a failed banner insert must never bubble up and
    break the pulse — we log and return False instead.
    """
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            if dedupe:
                # IS NOT DISTINCT FROM so a NULL taskId (tenant-wide underperform)
                # dedupes against the other open NULL-task row, not every per-post one.
                existing = (
                    await session.execute(
                        text(
                            """
                            SELECT 1 FROM performance_reviews
                            WHERE "tenantId" = :tid AND kind = :kind
                              AND status = 'open'
                              AND "taskId" IS NOT DISTINCT FROM :task
                            LIMIT 1
                            """
                        ),
                        {"tid": tenant_id, "kind": kind, "task": task_id},
                    )
                ).first()
                if existing:
                    log.info(
                        "alerts.deduped", kind=kind, tenant_id=tenant_id, task_id=task_id
                    )
                    return False

            await session.execute(
                text(
                    """
                    INSERT INTO performance_reviews
                      (id, "tenantId", "runId", kind, severity, "taskId",
                       "underperformedCount", "rootCauses", "recommendedPivots",
                       payload, status, "createdAt")
                    VALUES
                      (:id, :tid, :run, :kind, :sev, :task, :uc,
                       CAST(:rc AS jsonb), CAST(:rp AS jsonb),
                       CAST(:pl AS jsonb), 'open', NOW())
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "tid": tenant_id,
                    "run": run_id,
                    "kind": kind,
                    "sev": severity,
                    "task": task_id,
                    "uc": summary_count,
                    "rc": json.dumps(root_causes or [], ensure_ascii=False),
                    "rp": json.dumps(recommended_pivots or [], ensure_ascii=False),
                    "pl": json.dumps(payload, ensure_ascii=False)
                    if payload is not None
                    else None,
                },
            )
            await session.commit()
        return True
    except Exception:  # noqa: BLE001
        log.exception("alerts.raise_failed", kind=kind, tenant_id=tenant_id)
        return False


async def has_open_alert(tenant_id: str, kind: str, task_id: str | None = None) -> bool:
    """True when an OPEN alert of this (kind, taskId) already exists. Lets a caller
    skip expensive work (e.g. an LLM synthesis) when the banner is already raised
    and would just be deduped away. Best-effort: errors → False (let work proceed)."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT 1 FROM performance_reviews
                        WHERE "tenantId" = :tid AND kind = :kind AND status = 'open'
                          AND "taskId" IS NOT DISTINCT FROM :task
                        LIMIT 1
                        """
                    ),
                    {"tid": tenant_id, "kind": kind, "task": task_id},
                )
            ).first()
            return row is not None
    except Exception:  # noqa: BLE001
        log.warning("alerts.has_open_check_failed", kind=kind, tenant_id=tenant_id)
        return False

"""Per-tenant query helpers for things the scriptwriter wants to ground in
this user's OWN past content (not cross-tenant exemplars from
shared_knowledge, and not Q&A notes from knowledge_vault).

Today this is `tenant_top_hooks` — the user's BEST-performing published
hooks, ranked by actualMetrics when present and falling back to recency
otherwise. Plain recency is fine on day 1 (every shipped hook is a
real voice signal), but once a few posts have run through the
account_tracker the engagement deltas are the more honest "what works
for this user" signal — exactly the loop we want closed.
"""
from __future__ import annotations

import structlog
from sqlalchemy import text

from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)


async def tenant_top_hooks(
    *,
    tenant_id: str,
    exclude_task_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Return up to `limit` published-task hooks for this tenant.

    Ranking (each row gets a perf_score):
      ``max(views, plays, likes × 10)`` from ``actualMetrics`` jsonb
      — reels use ``views``/``plays``, posts use ``likes`` (×10 so a
      strong like-only post can compete with a low-view reel). Rows
      whose actualMetrics is null (account_tracker hasn't run yet)
      score 0 and tie-break on ``publishedAt DESC``, preserving the
      old recency behaviour for fresh tenants.

    Each entry: ``{"title": str, "hook": str, "type": str, "perfScore":
    int, "metrics": dict}``. Empty hooks are skipped — a published task
    with no hook would just noise the prompt.

    Best-effort: a DB hiccup returns ``[]`` and logs a warning. Never
    raises into the agent loop — a missing past-hooks list must not
    break script generation.
    """
    if limit <= 0:
        return []
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            result = await session.execute(
                text(
                    """
                    SELECT title, hook, type, "actualMetrics",
                      GREATEST(
                        COALESCE(("actualMetrics"->>'views')::int, 0),
                        COALESCE(("actualMetrics"->>'plays')::int, 0),
                        COALESCE(("actualMetrics"->>'likes')::int, 0) * 10
                      ) AS perf_score
                    FROM content_tasks
                    WHERE "tenantId" = :tid
                      AND status = 'published'
                      AND hook IS NOT NULL
                      AND hook <> ''
                      AND (:ex_id::text IS NULL OR id <> :ex_id)
                    ORDER BY perf_score DESC, "publishedAt" DESC NULLS LAST,
                             "updatedAt" DESC
                    LIMIT :lim
                    """
                ),
                {"tid": tenant_id, "ex_id": exclude_task_id, "lim": limit},
            )
            rows = result.mappings().all()
    except Exception:  # noqa: BLE001
        log.warning("tenant_top_hooks.query_failed", tenant_id=tenant_id, exc_info=True)
        return []

    out: list[dict] = []
    for r in rows:
        if not r.get("hook"):
            continue
        actual = r.get("actualMetrics") or {}
        # Compact metrics — the prompt only needs the headline signals,
        # not the full jsonb (which can carry Graph API insights blobs).
        metrics = (
            {
                "likes": int(actual.get("likes") or 0),
                "views": int(actual.get("views") or 0),
                "plays": int(actual.get("plays") or 0),
                "comments": int(actual.get("comments") or 0),
            }
            if isinstance(actual, dict)
            else {}
        )
        out.append(
            {
                "title": str(r.get("title") or "")[:160],
                "hook": str(r.get("hook") or "")[:280],
                "type": str(r.get("type") or ""),
                "perfScore": int(r.get("perf_score") or 0),
                "metrics": metrics,
            }
        )
    return out


async def account_reach_baseline(tenant_id: str, *, sample: int = 15) -> dict:
    """Median reach of this tenant's recent published posts + follower count —
    the grounding inputs for the Stage 5 deterministic reach forecast.

    `medianReach` is the median of GREATEST(reach, views, plays) over the last
    `sample` published tasks whose actualMetrics carry a real number; 0 when the
    account has no measured posts yet (a brand-new account → the forecaster
    falls back to a follower-derived estimate). Best-effort → zeros on failure.
    """
    median_reach = 0.0
    followers = 0
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            rows = await session.execute(
                text(
                    """
                    SELECT GREATEST(
                             COALESCE(("actualMetrics"->>'reach')::int, 0),
                             COALESCE(("actualMetrics"->>'views')::int, 0),
                             COALESCE(("actualMetrics"->>'plays')::int, 0)
                           ) AS reach
                    FROM content_tasks
                    WHERE "tenantId" = :tid
                      AND status = 'published'
                      AND "actualMetrics" IS NOT NULL
                    ORDER BY "publishedAt" DESC NULLS LAST
                    LIMIT :lim
                    """
                ),
                {"tid": tenant_id, "lim": sample},
            )
            values = sorted(int(r[0]) for r in rows.all() if r[0] and int(r[0]) > 0)
            if values:
                mid = len(values) // 2
                median_reach = (
                    float(values[mid])
                    if len(values) % 2
                    else (values[mid - 1] + values[mid]) / 2.0
                )

            fol = await session.execute(
                text(
                    """
                    SELECT COALESCE(MAX("followerCount"), 0) AS followers
                    FROM instagram_accounts
                    WHERE "tenantId" = :tid
                    """
                ),
                {"tid": tenant_id},
            )
            followers = int(fol.scalar() or 0)
            if followers <= 0:
                ob = await session.execute(
                    text(
                        """
                        SELECT COALESCE(MAX("currentFollowers"), 0) AS followers
                        FROM onboarding_profiles
                        WHERE "tenantId" = :tid
                        """
                    ),
                    {"tid": tenant_id},
                )
                followers = int(ob.scalar() or 0)
    except Exception:  # noqa: BLE001
        log.warning("account_reach_baseline.query_failed", tenant_id=tenant_id, exc_info=True)
        return {"medianReach": 0.0, "followers": 0, "sampleSize": 0}

    return {"medianReach": median_reach, "followers": followers, "sampleSize": len(values) if median_reach else 0}


async def reach_prediction_ratios(tenant_id: str, *, sample: int = 30) -> list[float]:
    """actual/predicted reach ratios from this tenant's RESOLVED prediction audits
    — the Stage 5 calibration signal (systematic over/under-prediction). Best-effort
    → [] (forecast then uses no correction)."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            rows = await session.execute(
                text(
                    """
                    SELECT "actualValue" / NULLIF("predictedValue", 0) AS ratio
                    FROM prediction_audits
                    WHERE "tenantId" = :tid
                      AND metric = 'reach'
                      AND "actualValue" IS NOT NULL
                      AND "predictedValue" > 0
                      AND "resolvedAt" IS NOT NULL
                    ORDER BY "resolvedAt" DESC
                    LIMIT :lim
                    """
                ),
                {"tid": tenant_id, "lim": sample},
            )
            return [float(r[0]) for r in rows.all() if r[0] is not None and float(r[0]) > 0]
    except Exception:  # noqa: BLE001
        log.warning("reach_prediction_ratios.query_failed", tenant_id=tenant_id, exc_info=True)
        return []

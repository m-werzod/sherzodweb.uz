"""Prediction resolver worker.

Daily, finds `PredictionAudit` rows where `resolvedAt IS NULL` and
`predictedAt + 72h <= NOW()`. For each unresolved row, looks at the
referenced `ContentTask.actualMetrics` and writes `actualValue` and the
error ratio (`(actual - predicted) / predicted`).

This is the loop that turns our agent predictions into a per-agent accuracy
score that the UI surfaces on the agents page.

Stage 5 — it ALSO closes the forecast-accuracy loop: after resolving a batch,
for each tenant whose predictions just resolved it aggregates the last 30 days
of |error| and writes `Forecast.accuracyPct` on that tenant's latest forecast.
Until now nothing ever wrote that column, so the "Prognoz aniqligi" pill on the
roadmap + analytics pages stayed permanently empty. The number here is the
mean per-prediction accuracy (NOT a P10/P50/P90 trajectory backtest) — the
honest, cheap signal the UI already computes inline; we just persist it so it
survives without a live query. The formula MIRRORS the UI's
(1 - AVG(ABS(error))) * 100 clamp in apps/web/src/lib/agents/data.ts so the two
never disagree.
"""
from __future__ import annotations

import asyncio
import json
import math

import structlog
from sqlalchemy import text

from app.graphs.detectors import compute_rates
from app.integrations import telegram
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

INTERVAL_SECONDS = 24 * 60 * 60

# Window over which resolved predictions count toward the displayed accuracy —
# matches the agents-page query (apps/web/src/lib/agents/data.ts).
_ACCURACY_WINDOW_DAYS = 30

# Stage 5: goal-KPI audits store RATE metrics (engagement/save/share per reach),
# not raw counts. They aren't keys in actualMetrics — they're DERIVED from it via
# detectors.compute_rates (reach is the denominator, followerCount for reach_rate).
# Without this, a rate-metric audit row would never find actualMetrics[metric] and
# would sit unresolved forever.
_RATE_METRICS = frozenset({"reach_rate", "er_reach", "save_rate", "send_rate"})


def _as_dict(raw) -> dict:
    """actualMetrics is jsonb — usually a dict, but some driver/column paths hand
    it back as a JSON string. Coerce defensively (account_tracker does the same)
    so compute_rates never calls .get() on a str and silently AttributeErrors the
    row into permanent-unresolved limbo."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:  # noqa: BLE001
            return {}
    return raw if isinstance(raw, dict) else {}


def _metric_actual(metric: str, actual_metrics: dict, followers: int) -> float | None:
    """The resolved actual value for a metric. Rate metrics are recomputed from
    actualMetrics (+ followers) via compute_rates and return None when their
    denominator (reach / followers) isn't available yet, so the row is retried
    rather than resolved against a bogus 0."""
    if metric in _RATE_METRICS:
        return compute_rates(actual_metrics, followers).get(metric)
    if metric == "reach":
        # 'reach' isn't a raw instagrapi key (it returns views/plays) — use the
        # same reach = reach|views|plays fallback compute_rates uses, so reach
        # audits actually resolve for scraped (non-OAuth) metrics instead of
        # sitting forever against a missing 'reach' key. None until reach lands.
        reach = compute_rates(actual_metrics, followers).get("_reach") or 0.0
        return reach if reach > 0 else None
    return _coerce_float((actual_metrics or {}).get(metric))


def compute_accuracy_pct(errors: list[float]) -> float | None:
    """Forecast accuracy from resolved per-prediction error ratios.

    Mirrors the UI exactly: ``(1 - mean(abs(error))) * 100`` clamped to [0, 100]
    (see apps/web/src/lib/agents/data.ts::aggregateAccuracyByKind). Returns None
    when there's no resolved data yet — the caller then leaves accuracyPct as-is
    rather than writing a misleading 0. NaN/inf are filtered (a corrupt error
    value must not silently clamp accuracy to 100)."""
    vals = []
    for e in errors:
        if e is None:
            continue
        f = abs(float(e))
        if math.isfinite(f):
            vals.append(f)
    if not vals:
        return None
    mean_abs = sum(vals) / len(vals)
    return max(0.0, min(100.0, (1.0 - mean_abs) * 100.0))


async def resolve_pending() -> int:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT pa.id, pa."tenantId", pa."taskId", pa.metric,
                       pa."predictedValue", ct."actualMetrics"
                FROM prediction_audits pa
                LEFT JOIN content_tasks ct ON ct.id = pa."taskId"
                WHERE pa."resolvedAt" IS NULL
                  AND pa."predictedAt" + INTERVAL '72 hours' <= NOW()
                  -- Upper bound: stop retrying rows that can never resolve (e.g.
                  -- a photo post with no reach, a tenant whose profile never
                  -- synced) so they don't churn the daily batch forever.
                  AND pa."predictedAt" > NOW() - INTERVAL '21 days'
                LIMIT 200
                """
            )
        )
        pending = rows.mappings().all()

        resolved = 0
        touched_tenants: set[str] = set()
        followers_cache: dict[str, int] = {}
        for r in pending:
            actual_metrics = _as_dict(r["actualMetrics"])
            metric = r["metric"]
            followers = 0
            if metric in _RATE_METRICS:
                followers = await _followers_for(
                    session, r["tenantId"], followers_cache
                )
            actual = _metric_actual(metric, actual_metrics, followers)
            if actual is None:
                # Task hasn't posted actuals yet (or rate denominator still 0) —
                # leave it for tomorrow.
                continue
            predicted = float(r["predictedValue"] or 0)
            error = (actual - predicted) / predicted if predicted else 0.0
            await session.execute(
                text(
                    """
                    UPDATE prediction_audits
                    SET "actualValue" = :a, error = :e, "resolvedAt" = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": r["id"], "a": actual, "e": error},
            )
            resolved += 1
            touched_tenants.add(r["tenantId"])

        # Forecast-accuracy back-write: only for tenants whose audits just
        # resolved (so we don't re-scan the whole table every day). The 30-day
        # SELECT sees this transaction's freshly-resolved rows.
        for tid in touched_tenants:
            await _write_forecast_accuracy(session, tid)

        if resolved:
            await session.commit()
        return resolved


async def _write_forecast_accuracy(session, tenant_id: str) -> None:
    """Recompute this tenant's REACH-prediction accuracy over the last 30 days and
    write it onto their latest Forecast row. Best-effort — a forecast row may not
    exist yet (the forecast worker is opt-in via RUN_WORKERS), in which case the
    UPDATE simply touches 0 rows.

    Scoped to metric='reach' on purpose: Forecast.accuracyPct is the volume signal
    the forecast trajectory is about. Mixing it with the goal-KPI RATE audits
    (er_reach, errors on a 0..1 scale) and the raw reach count (errors up to +∞)
    in one mean would corrupt the number. The per-rate accuracy is surfaced
    separately on the analytics page (grouped BY metric)."""
    err_rows = await session.execute(
        text(
            """
            SELECT error FROM prediction_audits
            WHERE "tenantId" = :tid
              AND metric = 'reach'
              AND "resolvedAt" IS NOT NULL
              AND error IS NOT NULL
              AND "resolvedAt" > NOW() - (CAST(:days AS int) || ' days')::interval
            """
        ),
        {"tid": tenant_id, "days": _ACCURACY_WINDOW_DAYS},
    )
    errors = [row[0] for row in err_rows.all()]
    pct = compute_accuracy_pct(errors)
    if pct is None:
        return
    await session.execute(
        text(
            """
            UPDATE forecasts SET "accuracyPct" = :pct
            WHERE id = (
                SELECT id FROM forecasts
                WHERE "tenantId" = :tid
                ORDER BY "runAt" DESC, id DESC LIMIT 1
            )
            """
        ),
        {"tid": tenant_id, "pct": pct},
    )


async def _followers_for(session, tenant_id: str, cache: dict[str, int]) -> int:
    """Tenant's latest follower count (for reach_rate). Cached per batch so a
    20-post pulse hits instagram_accounts once, not 20×."""
    if tenant_id in cache:
        return cache[tenant_id]
    row = (
        await session.execute(
            text(
                'SELECT "followerCount" FROM instagram_accounts '
                'WHERE "tenantId" = :t ORDER BY "updatedAt" DESC LIMIT 1'
            ),
            {"t": tenant_id},
        )
    ).first()
    followers = int(row[0]) if row and row[0] is not None else 0
    cache[tenant_id] = followers
    return followers


def _coerce_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def loop_forever() -> None:
    log.info("prediction_resolver.start")
    await asyncio.sleep(120)
    while True:
        try:
            n = await resolve_pending()
            log.info("prediction_resolver.resolved", count=n)
            if n:
                telegram.send(f"🎯 Prognoz aniqligi · {n} ta bashorat haqiqiy natija bilan solishtirildi")
        except Exception:  # noqa: BLE001
            log.exception("prediction_resolver.batch_failed")
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(resolve_pending())

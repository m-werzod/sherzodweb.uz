"""Forecast worker.

Daily (02:00 Asia/Tashkent), reads the last 60 days of `FollowerSnapshot`
for each tenant, fits a simple linear regression, runs a Monte Carlo
simulation (1000 iters) around the residual std, and writes P10/P50/P90
arrays for the next 90 days into `Forecast`.

This is intentionally simple. When we have >10K snapshots per tenant we
can swap in an ARIMA model. For now linear + noise is honest enough.
"""
from __future__ import annotations

import asyncio
import math
import statistics
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

HORIZON_DAYS = 90
LOOKBACK_DAYS = 60
MC_ITERATIONS = 1000


def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Returns (slope, intercept)."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    den = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = num / den
    intercept = my - slope * mx
    return slope, intercept


def _project(xs: list[float], ys: list[float]) -> tuple[list[int], list[int], list[int]]:
    """Monte Carlo trajectory — returns (p10, p50, p90) over HORIZON_DAYS."""
    if len(ys) < 7:
        # Too little data — flat-line at last value with widening band.
        last = int(ys[-1]) if ys else 0
        p50 = [last] * HORIZON_DAYS
        p10 = [int(last * (1 - 0.02 * (i + 1))) for i in range(HORIZON_DAYS)]
        p90 = [int(last * (1 + 0.02 * (i + 1))) for i in range(HORIZON_DAYS)]
        return p10, p50, p90

    slope, intercept = _linear_fit(xs, ys)
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys, strict=False)]
    sigma = statistics.pstdev(residuals) or max(1.0, abs(slope) * 5.0)

    import random

    rng = random.Random(0)  # noqa: S311 — Monte Carlo sampling, not cryptographic
    trajectories: list[list[float]] = []
    for _ in range(MC_ITERATIONS):
        traj: list[float] = []
        cur = ys[-1]
        for h in range(1, HORIZON_DAYS + 1):
            mean_step = slope
            # Noise grows with sqrt(t) — Brownian motion ankor
            noise = rng.gauss(0, sigma * math.sqrt(h / 7.0))
            cur = cur + mean_step + noise
            traj.append(max(0.0, cur))
        trajectories.append(traj)

    p10: list[int] = []
    p50: list[int] = []
    p90: list[int] = []
    for h in range(HORIZON_DAYS):
        col = sorted(t[h] for t in trajectories)
        p10.append(int(col[int(0.10 * MC_ITERATIONS)]))
        p50.append(int(col[int(0.50 * MC_ITERATIONS)]))
        p90.append(int(col[int(0.90 * MC_ITERATIONS)]))
    return p10, p50, p90


async def _tenants_with_history() -> list[str]:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT "tenantId"
                FROM follower_snapshots
                WHERE "takenAt" > NOW() - INTERVAL '60 days'
                GROUP BY "tenantId"
                HAVING count(*) >= 7
                """
            )
        )
        return [r[0] for r in rows.all()]


async def _forecast_one(tenant_id: str) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                # LOOKBACK_DAYS is a module-level int constant, not user input.
                f"""
                SELECT "takenAt", count
                FROM follower_snapshots
                WHERE "tenantId" = :tid
                  AND "takenAt" > NOW() - INTERVAL '{LOOKBACK_DAYS} days'
                ORDER BY "takenAt"
                """  # noqa: S608
            ),
            {"tid": tenant_id},
        )
        history = rows.all()
        if len(history) < 7:
            log.info("forecast.skip_short_history", tenant_id=tenant_id, n=len(history))
            return

        xs = list(range(len(history)))
        ys = [float(r[1]) for r in history]
        p10, p50, p90 = _project(xs, ys)

        await session.execute(
            text(
                """
                INSERT INTO forecasts
                  (id, "tenantId", "horizonDays", p10, p50, p90, methodology, "runAt")
                VALUES (:id, :tid, :h, CAST(:p10 AS jsonb), CAST(:p50 AS jsonb),
                        CAST(:p90 AS jsonb), 'monte_carlo', NOW())
                """
            ),
            {
                "id": uuid.uuid4().hex,
                "tid": tenant_id,
                "h": HORIZON_DAYS,
                "p10": _json_list(p10),
                "p50": _json_list(p50),
                "p90": _json_list(p90),
            },
        )
        await session.commit()


def _json_list(arr: list[int]) -> str:
    import json

    return json.dumps(arr)


async def forecast_all() -> None:
    tenants = await _tenants_with_history()
    log.info("forecast.batch", count=len(tenants))
    if tenants:
        telegram.send(f"📈 Monte Carlo prognoz · {len(tenants)} tenant uchun trajectory")
    for tid in tenants:
        try:
            await _forecast_one(tid)
        except Exception:  # noqa: BLE001
            log.exception("forecast.tenant_failed", tenant_id=tid)


async def _seconds_until_next_run() -> float:
    """02:00 Asia/Tashkent = 21:00 UTC previous day."""
    now = datetime.now(UTC)
    target = now.replace(hour=21, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def loop_forever() -> None:
    log.info("forecast.start")
    await asyncio.sleep(60)
    while True:
        try:
            await forecast_all()
        except Exception:  # noqa: BLE001
            log.exception("forecast.batch_failed")
        await asyncio.sleep(await _seconds_until_next_run())


if __name__ == "__main__":
    asyncio.run(forecast_all())

"""Recovery for LLM workflow runs orphaned by a crash/redeploy.

A LangGraph run is driven by an in-memory asyncio task spawned in the dispatcher;
a process restart (Coolify auto-deploys on every push to main) kills it mid-flight
and leaves the `agent_runs` row stuck in 'running'/'queued' forever — the
onboarding loading screen then spins indefinitely with no error and no retry.

This worker periodically fails runs whose heartbeat (touched per graph node in the
dispatcher) went stale, so the UI flips to a failed/retry state instead of an
infinite spinner. The first iteration runs immediately on start, so it doubles as
the on-boot restart-recovery sweep.

NOTE (single-replica assumption): with one agents process, every in-flight run at
boot is genuinely orphaned. The stale-heartbeat threshold keeps it safe for the
future multi-replica split (W2) — a live run on another replica heartbeats and is
spared; only a dead-driver run goes stale.
"""
from __future__ import annotations

import asyncio
import os

import structlog

from app import metrics
from app.runs.repository import reap_dead_runs

log = structlog.get_logger(__name__)

INTERVAL = float(os.getenv("RUN_REAPER_SECONDS") or "120")
# The run_worker reclaims (resumes) every expired-lease run BELOW the attempt cap;
# the reaper only fails a run that crashed repeatedly (attempts >= cap) so a poison
# run doesn't reclaim forever. The cap mirrors run_worker.MAX_ATTEMPTS.
MAX_ATTEMPTS = int(float(os.getenv("RUN_MAX_ATTEMPTS") or "3"))


async def loop_forever() -> None:
    log.info("run_reaper.start", interval=INTERVAL, max_attempts=MAX_ATTEMPTS)
    while True:
        try:
            reaped = await reap_dead_runs(MAX_ATTEMPTS)
            if reaped:
                log.warning("run_reaper.reaped", count=len(reaped), ids=reaped[:20])
                metrics.RUNS_REAPED.inc(len(reaped))
        except Exception:  # noqa: BLE001
            log.exception("run_reaper.iteration_failed")
        await asyncio.sleep(INTERVAL)

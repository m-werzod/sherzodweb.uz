"""Durable run-worker (T7.1) — drives queued LangGraph workflow runs.

`dispatch_workflow` now only INSERTs an agent_runs row as `queued` (with the
payload in `input`); this worker claims it (FOR UPDATE SKIP LOCKED, visibility-
timeout lease + attempt cap) and drives the graph to completion via
`dispatcher.drive_run`. A process crash leaves the row's lease expired → another
worker reclaims it and resumes from the LangGraph checkpoint, so a restart no
longer strands an in-flight run (the old in-memory asyncio task did).

Mirror of montage_worker. Runs on the BRAIN plane (with the schedulers), not the
media plane.

Standalone:  uv run python -m app.workers.run_worker
"""
from __future__ import annotations

import asyncio
import os

import structlog

from app.graphs.dispatcher import drive_run
from app.memory.db import get_sessionmaker
from app.runs.repository import claim_run

log = structlog.get_logger(__name__)

POLL_SECONDS = float(os.getenv("RUN_WORKER_POLL_SECONDS") or "2")
# 1200 (was 600): a full pulse (tracker_pulse steps the whole chain + does several
# LLM calls) was routinely outliving a 600s lease and getting re-claimed as
# attempt 2 — duplicate work. A single slow LLM call between node heartbeats can
# exceed 600s; 1200 gives headroom. Crash recovery still bounded by run_reaper.
LEASE_SECONDS = int(float(os.getenv("RUN_LEASE_SECONDS") or "1200"))
MAX_ATTEMPTS = int(float(os.getenv("RUN_MAX_ATTEMPTS") or "3"))
# Each run is mostly idle network wait on LLM APIs, so a couple overlap cheaply.
CONCURRENCY = max(1, int(float(os.getenv("RUN_CONCURRENCY") or "2")))


async def _run_one() -> bool:
    """Claim + drive one run. Returns True if it drove a run (poll again
    immediately), False if the queue was empty (sleep)."""
    sm = get_sessionmaker()
    async with sm() as session:
        claim = await claim_run(session, lease_seconds=LEASE_SECONDS, max_attempts=MAX_ATTEMPTS)
    if claim is None:
        return False
    log.info(
        "run_worker.claimed",
        run_id=claim["run_id"],
        workflow=claim["workflow"],
        attempt=claim["attempts"],
        resume=claim["attempts"] > 1,
    )
    try:
        # drive_run → _run already marks the run failed + alerts on its own
        # exceptions; we still guard so one bad run never kills the poller.
        # Pass the SAME lease the claim used so per-node heartbeats keep it ahead.
        await drive_run(claim, lease_seconds=LEASE_SECONDS)
    except Exception:  # noqa: BLE001
        log.exception("run_worker.drive_failed", run_id=claim["run_id"])
    return True


async def _runner() -> None:
    while True:
        try:
            drove = await _run_one()
        except Exception:  # noqa: BLE001
            log.exception("run_worker.iteration_failed")
            drove = False
        if not drove:
            await asyncio.sleep(POLL_SECONDS)


async def loop_forever() -> None:
    log.info(
        "run_worker.start",
        poll=POLL_SECONDS,
        lease=LEASE_SECONDS,
        max_attempts=MAX_ATTEMPTS,
        concurrency=CONCURRENCY,
    )
    if CONCURRENCY <= 1:
        await _runner()
    else:
        await asyncio.gather(*[_runner() for _ in range(CONCURRENCY)])


if __name__ == "__main__":
    asyncio.run(loop_forever())

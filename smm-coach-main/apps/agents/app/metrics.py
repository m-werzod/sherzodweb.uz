"""Prometheus metrics for operational visibility — queue depth, worker restarts,
render failures. Currently NO scraper is deployed; the `/metrics` endpoint exists
so one can be pointed at it the moment we need it (the audit's missing-metrics
gap). uvicorn runs single-process per container, so the default registry is fine
(no multiprocess mode).

Gauges are refreshed ON DEMAND when `/metrics` is scraped (see collect_gauges) —
cheap COUNT queries, no extra poller. Counters are incremented at the event site
(_supervise restart, montage failure, reaper).
"""
from __future__ import annotations

import structlog
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy import text

from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

# ── Counters (incremented at the event site) ────────────────────────────────
WORKER_RESTARTS = Counter(
    "smm_worker_restarts_total",
    "Background worker loop restarts (an exception escaped the loop and _supervise restarted it)",
    ["worker"],
)
RENDER_FAILURES = Counter(
    "smm_montage_render_failures_total",
    "Montage renders failed by the reaper after exhausting the attempt cap",
)
RUNS_REAPED = Counter(
    "smm_agent_runs_reaped_total",
    "Stale agent_runs (queued/running past the threshold) failed by the run_reaper",
)

# ── Gauges (refreshed on scrape from the DB) ─────────────────────────────────
MONTAGE_QUEUE_DEPTH = Gauge(
    "smm_montage_queue_depth", "final_render rows in pending or processing state"
)
AGENT_RUNS_QUEUED = Gauge("smm_agent_runs_queued", "agent_runs in the queued state")
AGENT_RUNS_RUNNING = Gauge("smm_agent_runs_running", "agent_runs in the running state")


async def collect_gauges() -> None:
    """Refresh the queue-depth gauges from the DB. Best-effort: a metrics scrape
    must never fail because the DB hiccuped, so we swallow + log."""
    try:
        sm = get_sessionmaker()
        async with sm() as s:
            mq = (
                await s.execute(
                    text(
                        "SELECT count(*) FROM task_media "
                        "WHERE kind='final_render' AND status IN ('pending','processing')"
                    )
                )
            ).scalar() or 0
            MONTAGE_QUEUE_DEPTH.set(mq)

            runs = (
                await s.execute(
                    text(
                        "SELECT count(*) FILTER (WHERE status='queued'), "
                        "count(*) FILTER (WHERE status='running') FROM agent_runs"
                    )
                )
            ).first()
            AGENT_RUNS_QUEUED.set((runs[0] if runs else 0) or 0)
            AGENT_RUNS_RUNNING.set((runs[1] if runs else 0) or 0)
    except Exception as exc:  # noqa: BLE001
        log.warning("metrics.collect_failed", error=repr(exc))


def render() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics exposition."""
    return generate_latest(), CONTENT_TYPE_LATEST

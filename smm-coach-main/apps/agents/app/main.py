"""FastAPI entrypoint for the SMM agent service."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

# psycopg's async driver does NOT work with the default Windows ProactorEventLoop —
# it requires SelectorEventLoop. Install the policy here, before any import or
# asyncio.run() call sees the wrong loop. Harmless no-op on POSIX.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import metrics
from app.api import admin, health, psych_interview, questions, runs, scrape, sse, transcode, video
from app.config import get_settings
from app.integrations import telegram
from app.integrations.instagram import playwright_scraper
from app.memory import redis_cache
from app.security.hmac import HmacAuthMiddleware
from app.streams import bus as stream_bus
from app.telemetry import setup_telemetry
from app.workers import (
    autoqueue_scheduler,
    coach_supervisor,
    comment_sentinel_scheduler,
    competitor_tracker,
    daily_snapshot,
    forecast,
    hashtag_trend_refresher,
    ig_token_refresh,
    insights_scheduler,
    knowledge_refresher,
    montage_worker,
    orphan_cleanup,
    post_sync_scheduler,
    prediction_resolver,
    publish_scheduler,
    run_reaper,
    run_worker,
    tracker_scheduler,
    virale_refresher,
)


def _telegram_error_processor(logger: object, method_name: str, event_dict: dict) -> dict:
    """Every ERROR-level log line ALSO lands in the Telegram channel (user requirement:
    100% of failures visible there). Deduped per event name so a crash-loop is one line,
    not a flood; fire-and-forget so reporting never slows the app."""
    if method_name in ("error", "critical", "exception"):
        # Fully exception-proof: a reporting failure must NEVER corrupt the original log call.
        try:
            event = str(event_dict.get("event") or "error")
            extras = " ".join(
                f"{k}={str(v)[:80]}" for k, v in event_dict.items()
                if k not in ("event", "timestamp", "level", "exception") and isinstance(v, (str, int, float))
            )[:600]
            exc = str(event_dict.get("exception") or "")[:400]
            telegram.send_error(
                f"log:{event}",
                f"🛑 [agents] {event}" + (f"\n{extras}" if extras else "") + (f"\n{exc}" if exc else ""),
            )
        except Exception:  # noqa: BLE001, S110
            pass
    return event_dict


def _configure_logging(level: str) -> None:
    logging.basicConfig(format="%(message)s", level=level.upper())
    # httpx logs every request URL at INFO — for Telegram that URL CONTAINS the bot
    # token (api.telegram.org/bot<TOKEN>/...), a secret leak into container logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # NOT dict_tracebacks (its default show_locals=True serialized frame locals
            # — including the full Settings object with plain-str secrets — into logs).
            structlog.processors.ExceptionRenderer(
                structlog.tracebacks.ExceptionDictTransformer(show_locals=False)
            ),
            _telegram_error_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


async def _supervise(name: str, factory: Callable[[], Awaitable[None]]) -> None:
    """Run a worker's forever-loop under supervision.

    Each worker already sleep-and-continues on errors inside its own loop;
    this guards the rarer case of an exception escaping the loop entirely
    (setup / import-time / a bad sleep argument), which would otherwise
    silently kill that worker for the life of the process with only a
    'Task exception was never retrieved' on GC. On unexpected exit we log and
    restart with capped exponential backoff; a clean cancel (shutdown) is
    re-raised so the lifespan can await it.
    """
    log = structlog.get_logger("smm.agents")
    loop = asyncio.get_running_loop()
    backoff = 5.0
    while True:
        started = loop.time()
        try:
            await factory()
            log.warning("worker.exited_restarting", worker=name)
        except asyncio.CancelledError:
            log.info("worker.cancelled", worker=name)
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("worker.crashed_restarting", worker=name)
            metrics.WORKER_RESTARTS.labels(worker=name).inc()
            telegram.send_error(
                f"worker:{name}",
                f"🛑 [agents] Worker qulab qayta ishga tushmoqda · {name}\n{repr(exc)[:300]}",
            )
        if loop.time() - started > 120:
            backoff = 5.0  # ran healthily for a while — reset the backoff
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 300.0)


# Workers that do CPU-bound media rendering — runnable on a separate deployable.
_MEDIA_WORKERS = {"montage_worker"}


def _select_workers(
    workers: list[tuple[str, Callable[[], Awaitable[None]]]], worker_set: str
) -> list[tuple[str, Callable[[], Awaitable[None]]]]:
    """Pick the workers for this plane (WORKER_SET):
      all   — everything (default: single-process dev/prod)
      media — ONLY the media render workers (a render OOM can't take the API down)
      brain — everything EXCEPT media (API + schedulers + run_reaper)
    Splitting media out lets the cron singletons run on exactly ONE plane (no
    double-fire) while the render isolates/scales independently.
    """
    if worker_set == "media":
        return [w for w in workers if w[0] in _MEDIA_WORKERS]
    if worker_set == "brain":
        return [w for w in workers if w[0] not in _MEDIA_WORKERS]
    return list(workers)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    telegram.register_loop()  # thread-side telegram.send() needs the main loop
    settings = get_settings()
    _configure_logging(settings.log_level)
    setup_telemetry(settings)

    log = structlog.get_logger("smm.agents")
    log.info("agents.starting", env=settings.env)

    background: list[asyncio.Task] = []
    # Workers are opt-in per environment: in dev you usually only want one
    # process running them. Set RUN_WORKERS=1 to enable on this process.
    # knowledge_seeder is NOT looped — it seeds per niche on demand when a
    # user onboards (see initial_analysis). No perpetual seeding job.
    if os.getenv("RUN_WORKERS", "0") == "1":
        all_workers: list[tuple[str, Callable[[], Awaitable[None]]]] = [
            ("tracker_scheduler", tracker_scheduler.loop_forever),
            ("comment_sentinel_scheduler", comment_sentinel_scheduler.loop_forever),
            ("autoqueue_scheduler", autoqueue_scheduler.loop_forever),
            ("knowledge_refresher", knowledge_refresher.loop_forever),
            ("hashtag_trend_refresher", hashtag_trend_refresher.loop_forever),
            ("daily_snapshot", daily_snapshot.loop_forever),
            ("forecast", forecast.loop_forever),
            ("competitor_tracker", competitor_tracker.loop_forever),
            # Pre-warms the Virale Redis cache twice a day so the page never
            # triggers a live scrape fan-out on view.
            ("virale_refresher", virale_refresher.loop_forever),
            ("prediction_resolver", prediction_resolver.loop_forever),
            ("ig_token_refresh", ig_token_refresh.run_forever),
            ("orphan_cleanup", orphan_cleanup.run_forever),
            ("coach_supervisor", coach_supervisor.loop_forever),
            ("publish_scheduler", publish_scheduler.loop_forever),
            ("insights_scheduler", insights_scheduler.loop_forever),
            ("post_sync_scheduler", post_sync_scheduler.loop_forever),
            ("montage_worker", montage_worker.loop_forever),
            # T7.1: claims + drives queued LLM runs (durable — survives a restart
            # by reclaiming an expired lease). Brain plane.
            ("run_worker", run_worker.loop_forever),
            # Fails LLM runs that crashed past the attempt cap (first pass = boot
            # recovery); the run_worker reclaims everything below the cap.
            ("run_reaper", run_reaper.loop_forever),
        ]
        worker_set = os.getenv("WORKER_SET", "all").lower()
        workers = _select_workers(all_workers, worker_set)
        # Each worker runs under _supervise so an exception escaping its loop
        # gets logged + the worker restarts, instead of dying silently.
        for wname, wfn in workers:
            background.append(asyncio.create_task(_supervise(wname, wfn), name=wname))
        log.info("agents.workers.started", count=len(background), worker_set=worker_set)

    try:
        yield
    finally:
        log.info("agents.stopping")
        for task in background:
            task.cancel()
        for task in background:
            # Awaiting a cancelled task re-raises CancelledError; any other
            # error during teardown is irrelevant — we're shutting down.
            with suppress(asyncio.CancelledError, Exception):
                await task
        # Tidy up long-lived resources
        try:
            await playwright_scraper.shutdown()
        except Exception:  # noqa: BLE001
            log.exception("agents.playwright_shutdown_failed")
        try:
            await stream_bus.close()
        except Exception:  # noqa: BLE001
            log.exception("agents.bus_close_failed")
        try:
            await redis_cache.close()
        except Exception:  # noqa: BLE001
            log.exception("agents.redis_cache_close_failed")


app = FastAPI(
    title="SMM Agents",
    version="0.0.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HMAC auth — every /v1/* endpoint requires a valid signature from the
# web service. /health (liveness) + /ready (readiness) are excluded so the
# Docker/Coolify probes don't get 401'd by the middleware.
app.add_middleware(
    HmacAuthMiddleware, exempt_paths=("/health", "/ready", "/metrics", "/docs", "/openapi.json")
)

app.include_router(health.router)
app.include_router(runs.router, prefix="/v1/runs", tags=["runs"])
app.include_router(scrape.router, prefix="/v1/scrape", tags=["scrape"])
app.include_router(sse.router, prefix="/v1/streams", tags=["streams"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
app.include_router(questions.router, prefix="/v1", tags=["questions"])
app.include_router(psych_interview.router, prefix="/v1", tags=["psych"])
app.include_router(transcode.router, prefix="/v1/transcode", tags=["transcode"])
app.include_router(video.router, prefix="/v1/video", tags=["video"])

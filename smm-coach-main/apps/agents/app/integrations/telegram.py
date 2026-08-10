"""Telegram reporting — a live activity feed pushed to a log channel:
process start/finish, every LLM/API call, agent runs, Instagram scraper
activity, voice generation.

Fire-and-forget + paced through an asyncio queue so a burst of events never
blocks the agent loop or trips Telegram's per-chat rate limit. No-op when
TELEGRAM_BOT_TOKEN / TELEGRAM_LOG_CHANNEL_ID are unset.

Note: ``send()`` needs a running event loop (it schedules a background post),
so call it from async code. Code running inside ``asyncio.to_thread`` has no
loop and the call becomes a silent no-op — report from the async caller there.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import threading
import time

import httpx
import structlog

log = structlog.get_logger(__name__)

_queue: asyncio.Queue[str] | None = None
_worker: asyncio.Task | None = None
_main_loop: asyncio.AbstractEventLoop | None = None  # lets THREAD code reach the sender
_DEDUP: dict[str, float] = {}
_DEDUP_TTL = 300.0  # the same error signature at most once per 5 min — no channel floods
_DEDUP_LOCK = threading.Lock()  # send_error is called from BOTH the loop and render threads
_in_send = threading.local()  # reentrancy guard: telegram internals must never re-enter themselves
_MIN_GAP_SEC = 1.5  # ~40 msg/min — comfortably under Telegram's per-chat ceiling


def _token() -> str | None:
    return os.getenv("TELEGRAM_BOT_TOKEN") or None


def _chat() -> str | None:
    return os.getenv("TELEGRAM_LOG_CHANNEL_ID") or None


def enabled() -> bool:
    return bool(_token() and _chat())


async def _post(text: str) -> None:
    token, chat = _token(), _chat()
    if not (token and chat):
        return
    payload = {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code == 429:
                retry = 2.0
                with contextlib.suppress(Exception):
                    retry = float((r.json().get("parameters") or {}).get("retry_after", 2))
                await asyncio.sleep(min(retry + 0.5, 30))
                await client.post(url, json=payload)
    except Exception as exc:  # noqa: BLE001
        log.debug("telegram.post_failed", error=str(exc)[:120])


async def _drain() -> None:
    assert _queue is not None
    while True:
        text = await _queue.get()
        try:
            await _post(text)
        finally:
            _queue.task_done()
        await asyncio.sleep(_MIN_GAP_SEC)


def register_loop() -> None:
    """Capture the main event loop at startup so `send()` also works from
    worker THREADS (asyncio.to_thread ffmpeg/render code) — previously those
    calls were silent no-ops."""
    global _main_loop
    try:
        _main_loop = asyncio.get_running_loop()
    except RuntimeError:
        _main_loop = None


def send_error(key: str, text: str) -> None:
    """Deduped error report: the same `key` fires at most once per _DEDUP_TTL —
    a crash-loop becomes ONE Telegram line instead of a flood.

    MUST be exception-proof: it is invoked from the structlog processor, so any error
    here would corrupt the ORIGINAL log call. Everything is locked + swallowed."""
    if getattr(_in_send, "flag", False):
        return  # reentrancy: an error raised while reporting an error stops here
    try:
        _in_send.flag = True
        now = time.monotonic()
        with _DEDUP_LOCK:
            if now - _DEDUP.get(key, 0.0) < _DEDUP_TTL:
                return
            _DEDUP[key] = now
            if len(_DEDUP) > 500:  # bound the map (safe under the lock)
                cutoff = now - _DEDUP_TTL
                for k in [k for k, v in _DEDUP.items() if v < cutoff]:
                    _DEDUP.pop(k, None)
        send(text)
    except Exception:  # noqa: BLE001, S110 — reporting must never break the caller
        pass
    finally:
        _in_send.flag = False


def send(text: str) -> None:
    """Fire-and-forget enqueue. No-op when Telegram is unconfigured. Works from
    async code AND (via the registered main loop) from worker threads. Drops
    (rather than blocks) under an extreme burst."""
    if not enabled() or not text:
        return
    global _queue, _worker
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Thread context (asyncio.to_thread) — hop onto the registered main loop.
        if _main_loop is not None and not _main_loop.is_closed():
            _main_loop.call_soon_threadsafe(send, text)
        return
    if _queue is None:
        _queue = asyncio.Queue(maxsize=500)
    if _worker is None or _worker.done():
        _worker = loop.create_task(_drain())
    with contextlib.suppress(asyncio.QueueFull):
        _queue.put_nowait(text)

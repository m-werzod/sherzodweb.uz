"""SSE stream of agent events per user, consumed by Next.js → browser."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.streams.bus import subscribe

log = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/{user_id}")
async def stream_user(user_id: str, request: Request) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(user_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_stream(user_id: str, request: Request) -> AsyncIterator[bytes]:
    log.info("sse.connected", user_id=user_id)
    try:
        async for event in subscribe(user_id):
            if await request.is_disconnected():
                break
            data = json.dumps(event, separators=(",", ":"))
            yield f"event: {event['type']}\ndata: {data}\n\n".encode()
    except asyncio.CancelledError:
        pass
    finally:
        log.info("sse.disconnected", user_id=user_id)

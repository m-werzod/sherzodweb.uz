"""HMAC request signing — shared with apps/web/lib/agents/client.ts.

Both sides compute HMAC-SHA256 over `${timestamp}.${body}` and send it as
the `X-Smm-Signature` header along with `X-Smm-Timestamp`. Replay window
is 5 minutes.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Iterable

import structlog
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings

log = structlog.get_logger(__name__)

REPLAY_WINDOW_SEC = 5 * 60


class HmacAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, exempt_paths: Iterable[str] = ()) -> None:
        super().__init__(app)
        self._exempt = tuple(exempt_paths)

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in self._exempt):
            return await call_next(request)

        signature = request.headers.get("x-smm-signature", "")
        ts_raw = request.headers.get("x-smm-timestamp", "")

        if not signature or not ts_raw:
            return _denied("missing_signature")

        try:
            ts = int(ts_raw)
        except ValueError:
            return _denied("bad_timestamp")

        now = int(time.time())
        if abs(now - ts) > REPLAY_WINDOW_SEC:
            return _denied("expired")

        body = await request.body()
        secret = get_settings().agents_hmac_secret.get_secret_value().encode()
        expected = hmac.new(
            secret, f"{ts}.".encode() + body, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            log.warning("hmac.invalid", path=request.url.path)
            return _denied("invalid")

        return await call_next(request)


def _denied(reason: str) -> Response:
    return Response(
        content=f'{{"error":"unauthorized","reason":"{reason}"}}',
        status_code=status.HTTP_401_UNAUTHORIZED,
        media_type="application/json",
    )


def sign(secret: bytes, timestamp: int, body: bytes) -> str:
    """Helper used by tests and tooling — never used in middleware itself."""
    return hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()

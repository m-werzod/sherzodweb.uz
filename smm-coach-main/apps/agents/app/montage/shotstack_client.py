"""Shotstack Edit API client — cloud render for the montage (MONTAGE-PRO F1).

SYNC, worker-thread only, FAIL-SOFT (mirrors fal/runway clients): no key / submit error / FAILED /
timeout → None, and the caller falls back to the LOCAL ffmpeg ladder — a cloud outage can never
break a render. Contract (docs.shotstack.io):

  POST https://api.shotstack.io/edit/{env}/render   headers: x-api-key
    body: the edit JSON (timeline/output)           → {"response": {"id": ...}}
  GET  .../render/{id}                              → {"response": {"status": "queued|fetching|
       rendering|saving|done|failed", "url": <mp4>, "error": ...}}

`stage` env renders watermarked output on the free sandbox key — perfect for the F2 A/B test.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_BASE = "https://api.shotstack.io/edit"
_POLL_INTERVAL_S = 4.0
_DONE = "done"
_FAILED = {"failed"}


def shotstack_api_key() -> str | None:
    key = get_settings().shotstack_api_key
    return key.get_secret_value() if key is not None else None


def shotstack_enabled() -> bool:
    """Whether the cloud render plane can run — flag ON and a key present."""
    return bool(get_settings().enable_shotstack) and shotstack_api_key() is not None


def render(edit: dict[str, Any], *, max_wait_s: float = 600.0, label: str = "shotstack") -> str | None:
    """Submit an edit, poll to completion, return the rendered MP4 URL or None. FAIL-SOFT."""
    key = shotstack_api_key()
    if not key or not isinstance(edit, dict):
        return None
    env = get_settings().shotstack_env
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=30.0) as client:
            sub = client.post(f"{_BASE}/{env}/render", headers=headers, json=edit)
            if sub.status_code >= 400:
                log.warning(f"{label}.submit_error", status=sub.status_code, detail=sub.text[:300])
                return None
            try:
                render_id = (sub.json().get("response") or {}).get("id")
            except ValueError:
                return None
            if not isinstance(render_id, str) or not render_id:
                return None

            waited = 0.0
            while waited < max_wait_s:
                time.sleep(_POLL_INTERVAL_S)
                waited += _POLL_INTERVAL_S
                st = client.get(f"{_BASE}/{env}/render/{render_id}", headers=headers)
                if st.status_code >= 400:
                    continue
                try:
                    resp = st.json().get("response") or {}
                except ValueError:
                    continue
                status = str(resp.get("status") or "").lower()
                if status == _DONE:
                    url = resp.get("url")
                    return url if isinstance(url, str) and url.startswith("http") else None
                if status in _FAILED:
                    log.warning(f"{label}.failed", detail=str(resp.get("error") or "")[:200])
                    return None
            log.warning(f"{label}.timeout", render_id=render_id)
            return None
    except Exception as exc:  # noqa: BLE001 — cloud render is optional; local ladder is the floor
        log.warning(f"{label}.error", error=str(exc)[:200])
        return None

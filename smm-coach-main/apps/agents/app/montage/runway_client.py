"""Runway Gen-4 Aleph video-to-video client — restyle an EXISTING clip by text prompt.

Higgsfield's API can't take a video as input; Runway Aleph can. SYNC, worker-thread only, FAIL-SOFT
(no key / API error / FAILED / timeout → None → the caller keeps the original clip).

Contract (verified live against api.dev.runwayml.com):
  POST {base}/v1/video_to_video
    headers: Authorization: Bearer <key>, X-Runway-Version: <ver>, Content-Type: application/json
    body:    {"model": "gen4_aleph", "videoUri": <PUBLIC url>, "promptText": <str>, "ratio": "720:1280"}
    → {"id": "<task-uuid>"}
  poll GET {base}/v1/tasks/{id}
    → {"status": "PENDING|RUNNING|THROTTLED|SUCCEEDED|FAILED", "output": ["https://...mp4"]}

`videoUri` MUST be a publicly fetchable URL — Runway pulls the asset server-side (a private/unreachable
URL fails validation with "Failed to fetch asset").
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_POLL_INTERVAL_S = 5.0
_TERMINAL_OK = {"SUCCEEDED"}
_TERMINAL_FAIL = {"FAILED", "CANCELLED", "CANCELED", "ERROR"}


def runway_api_key() -> str | None:
    key = get_settings().runway_api_key
    return key.get_secret_value() if key is not None else None


def runway_enabled() -> bool:
    """Whether the restyle path can run — the flag is ON and a key is present."""
    return bool(get_settings().enable_runway_restyle) and runway_api_key() is not None


def _headers(key: str, version: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "X-Runway-Version": version,
        "Content-Type": "application/json",
    }


def extract_output_url(payload: Any) -> str | None:
    """Runway task JSON → first output URL (PURE/testable). output is a list[str] of URLs."""
    if not isinstance(payload, dict):
        return None
    out = payload.get("output")
    if isinstance(out, list):
        for item in out:
            if isinstance(item, str) and item.startswith("http"):
                return item
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.startswith("http"):
                    return url
    if isinstance(out, str) and out.startswith("http"):
        return out
    return None


def build_body(*, model: str, video_url: str, prompt: str, ratio: str, seed: int = 0) -> dict[str, Any]:
    """Assemble the video_to_video request body (PURE/testable)."""
    body: dict[str, Any] = {
        "model": model,
        "videoUri": video_url,
        "promptText": (prompt or "").strip()[:1000],
        "ratio": ratio,
    }
    if seed:
        body["seed"] = int(seed)
    return body


def restyle(
    video_url: str,
    prompt: str,
    *,
    ratio: str | None = None,
    seed: int = 0,
    max_wait_s: float = 600.0,
    label: str = "runway",
) -> str | None:
    """Restyle `video_url` (a PUBLIC url) with `prompt`; return the output clip URL or None. FAIL-SOFT."""
    key = runway_api_key()
    if not key or not (video_url or "").strip():
        return None
    s = get_settings()
    base = s.runway_api_base.rstrip("/")
    headers = _headers(key, s.runway_api_version)
    body = build_body(
        model=s.runway_video_model,
        video_url=video_url,
        prompt=prompt,
        ratio=ratio or s.runway_ratio,
        seed=seed,
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            sub = client.post(f"{base}/v1/video_to_video", headers=headers, json=body)
            if sub.status_code >= 400:
                log.warning(f"{label}.submit_error", status=sub.status_code, detail=sub.text[:300])
                return None
            try:
                task_id = sub.json().get("id")
            except ValueError:
                return None
            if not isinstance(task_id, str) or not task_id:
                return None

            waited = 0.0
            while waited < max_wait_s:
                time.sleep(_POLL_INTERVAL_S)
                waited += _POLL_INTERVAL_S
                st = client.get(f"{base}/v1/tasks/{task_id}", headers=headers)
                if st.status_code >= 400:
                    continue
                try:
                    data = st.json()
                except ValueError:
                    continue
                status = str(data.get("status") or "").upper()
                if status in _TERMINAL_OK:
                    return extract_output_url(data)
                if status in _TERMINAL_FAIL:
                    log.warning(f"{label}.failed", status=status, detail=str(data.get("failure") or "")[:200])
                    return None
            log.warning(f"{label}.timeout", task_id=task_id)
            return None
    except Exception as exc:  # noqa: BLE001 — network/JSON; the restyle pass is optional
        log.warning(f"{label}.error", error=str(exc)[:200])
        return None

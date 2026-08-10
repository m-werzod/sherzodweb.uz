"""Shared fal.ai queue-API client for the montage GPU plane (video gen, inpaint, matte, image gen).

SYNC by design — called only from the montage worker THREAD, never the event loop (mirrors
integrations/stock/pexels.py). Every path is FAIL-SOFT: no FAL_KEY / API error / FAILED / timeout /
bad JSON → None. The queue submit→poll→result flow + shape-tolerant URL extraction + file upload
live here ONCE, used by gen_video (kling), inpaint (void), and decor (bria matte + flux bg).

The fal queue contract (POST queue.fal.run/{model} → status_url/response_url, poll {"status":"COMPLETED"},
GET response_url → {"video":{"url":..}} / {"images":[{"url":..}]}) was confirmed against the live fal
model API pages. KNOWN LIMIT: polling blocks the worker thread (hence ENCODE_GATE) — fine while GPU
passes are opt-in/rare; a non-blocking gpu_worker is the scaling upgrade (master plan §3.2).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_QUEUE_BASE = "https://queue.fal.run"
_POLL_INTERVAL_S = 3.0


def fal_api_key() -> str | None:
    key = get_settings().fal_key
    return key.get_secret_value() if key is not None else None


def extract_video_url(payload: Any) -> str | None:
    """fal.ai result JSON → MP4/WebM URL. Tolerant of the common shapes (PURE/testable):
    {"video":{"url":..}} | {"video_url":..} | {"videos":[{"url":..}]} | {"url":..}."""
    if not isinstance(payload, dict):
        return None
    video = payload.get("video")
    if isinstance(video, dict) and isinstance(video.get("url"), str):
        return str(video["url"])
    if isinstance(payload.get("video_url"), str):
        return str(payload["video_url"])
    vids = payload.get("videos")
    if isinstance(vids, list) and vids and isinstance(vids[0], dict) and isinstance(vids[0].get("url"), str):
        return str(vids[0]["url"])
    if isinstance(payload.get("url"), str):
        return str(payload["url"])
    return None


def extract_image_url(payload: Any) -> str | None:
    """fal.ai result JSON → image URL. Tolerant of the common shapes (PURE/testable):
    {"images":[{"url":..}]} | {"image":{"url":..}} | {"image_url":..} | {"url":..}."""
    if not isinstance(payload, dict):
        return None
    imgs = payload.get("images")
    if isinstance(imgs, list) and imgs and isinstance(imgs[0], dict) and isinstance(imgs[0].get("url"), str):
        return str(imgs[0]["url"])
    image = payload.get("image")
    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return str(image["url"])
    if isinstance(payload.get("image_url"), str):
        return str(payload["image_url"])
    if isinstance(payload.get("url"), str):
        return str(payload["url"])
    return None


def extract_audio_url(payload: Any) -> str | None:
    """fal.ai result JSON → audio URL. Tolerant of the common audio-model shapes (PURE/testable):
    {"audio_file":{"url":..}} | {"audio":{"url":..}} | {"audio_url":..} | {"url":..}."""
    if not isinstance(payload, dict):
        return None
    for key in ("audio_file", "audio"):
        node = payload.get(key)
        if isinstance(node, dict) and isinstance(node.get("url"), str):
            return str(node["url"])
        if isinstance(node, str) and node:
            return node
    if isinstance(payload.get("audio_url"), str):
        return str(payload["audio_url"])
    if isinstance(payload.get("url"), str):
        return str(payload["url"])
    return None


def run_queue_audio(model: str, body: dict[str, Any], *, max_wait_s: float = 180.0, label: str = "fal_audio") -> str | None:
    """Submit to the fal queue, return the result AUDIO URL or None. FAIL-SOFT."""
    return extract_audio_url(_submit_poll_result(model, body, max_wait_s=max_wait_s, label=label))


def _submit_poll_result(model: str, body: dict[str, Any], *, max_wait_s: float, label: str) -> Any:
    """Submit `body` to the fal queue for `model`, poll to completion, return the RESULT JSON (or
    None). FAIL-SOFT — no key / submit error / FAILED / timeout / bad JSON → None."""
    key = fal_api_key()
    if not key:
        return None
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=30.0) as client:
            sub = client.post(f"{_QUEUE_BASE}/{model}", headers=headers, json=body)
            if sub.status_code >= 400:
                log.warning(f"{label}.submit_error", status=sub.status_code, detail=sub.text[:200])
                return None
            sub_json = sub.json()
            status_url = sub_json.get("status_url")
            response_url = sub_json.get("response_url")
            if not isinstance(status_url, str) or not isinstance(response_url, str):
                return None

            waited = 0.0
            while waited < max_wait_s:
                st = client.get(status_url, headers=headers)
                status = st.json().get("status") if st.status_code < 400 else None
                if status == "COMPLETED":
                    break
                if status in ("FAILED", "ERROR"):
                    log.warning(f"{label}.failed", status=status)
                    return None
                time.sleep(_POLL_INTERVAL_S)
                waited += _POLL_INTERVAL_S
            else:
                log.warning(f"{label}.timeout", model=model)
                return None

            res = client.get(response_url, headers=headers)
            if res.status_code >= 400:
                return None
            return res.json()
    except Exception as exc:  # noqa: BLE001 — network/JSON; GPU passes are optional
        log.warning(f"{label}.error", error=str(exc)[:200])
        return None


def run_queue_video(model: str, body: dict[str, Any], *, max_wait_s: float = 180.0, label: str = "fal") -> str | None:
    """Submit to the fal queue, return the result VIDEO URL or None. FAIL-SOFT."""
    return extract_video_url(_submit_poll_result(model, body, max_wait_s=max_wait_s, label=label))


def run_queue_image(model: str, body: dict[str, Any], *, max_wait_s: float = 120.0, label: str = "fal") -> str | None:
    """Submit to the fal queue, return the result IMAGE URL or None. FAIL-SOFT."""
    return extract_image_url(_submit_poll_result(model, body, max_wait_s=max_wait_s, label=label))


def upload_file(path: str) -> str | None:
    """Upload a local file to fal's CDN, return its URL (to pass as a model input), or None.
    FAIL-SOFT — no key / missing file / upload error → None. Uses the official fal_client package
    (lazy import — heavy), which reads FAL_KEY from the environment."""
    key = fal_api_key()
    if not key or not os.path.exists(path):
        return None
    try:
        import fal_client  # lazy: heavy import, only when a GPU pass actually runs

        os.environ.setdefault("FAL_KEY", key)  # ensure the official client sees the key
        url = fal_client.upload_file(Path(path))
        return url if isinstance(url, str) and url else None
    except Exception as exc:  # noqa: BLE001 — optional GPU pass
        log.warning("fal.upload_error", error=str(exc)[:200])
        return None

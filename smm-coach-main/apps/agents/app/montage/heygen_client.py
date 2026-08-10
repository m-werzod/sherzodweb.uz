"""HeyGen avatar-video client for the montage GPU plane (talking-head avatar generation).

SYNC by design — called only from the montage worker THREAD (mirrors fal_client.py + pexels.py),
never the event loop. Every path is FAIL-SOFT: no HEYGEN_API_KEY / API error / failed / timeout /
bad JSON → None. A missing key or a HeyGen outage leaves the montage at v1 (no avatar), never raises.

The contract mirrors the PROVEN web client (apps/web/src/lib/avatar/heygen.ts):
  POST /v2/video/generate {video_inputs:[{character:avatar, voice}], dimension} → {data:{video_id}}
  GET  /v1/video_status.get?video_id=.. → {data:{status, video_url}}  (queued|processing|completed|failed)
Auth header: X-Api-Key. Base: https://api.heygen.com. Cost ≈ $1/min (standard avatar). Vertical
dimension 1080x1920 = 9:16 (reels). voice: audio_url (ElevenLabs MP3, perfect lip-sync) or text+voice_id.

KNOWN LIMIT: like fal, this POLLS and blocks the worker thread (avatar gen can take 1-several min) —
acceptable while avatar is opt-in/rare. HeyGen also supports an async callback webhook
(apps/web/.../webhooks/heygen) — the 2-phase submit→webhook→re-queue path is the scaling upgrade.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_API_BASE = "https://api.heygen.com"
_POLL_INTERVAL_S = 5.0
_SCRIPT_CAP = 4900  # HeyGen text-mode input cap (~5000); leaves headroom

# Video Translation endpoint (lip-sync dub, preserves aspect ratio incl. 9:16). Shape per
# docs.heygen.com/reference/video-translation — VERIFY live before enabling. Extraction below is
# shape-TOLERANT + FAIL-SOFT, so a docs/version mismatch degrades to None (no variant), never a crash.
_TRANSLATE_SUBMIT = "/v2/video_translate"
_TRANSLATE_STATUS = "/v2/video_translate"  # + /{id}

# Aspect label → HeyGen dimension (mirrors heygen.ts dimensionsFor; default vertical 9:16 for reels).
_DIMENSIONS: dict[str, dict[str, int]] = {
    "vertical": {"width": 1080, "height": 1920},
    "horizontal": {"width": 1920, "height": 1080},
    "square": {"width": 1080, "height": 1080},
}


def heygen_api_key() -> str | None:
    key = get_settings().heygen_api_key
    return key.get_secret_value() if key is not None else None


def dimensions_for(aspect: str) -> dict[str, int]:
    """Aspect label → {width,height}. Unknown → vertical 9:16 (reels default). PURE."""
    return _DIMENSIONS.get(aspect, _DIMENSIONS["vertical"])


def extract_status(payload: Any) -> str | None:
    """HeyGen status JSON → status string (queued|processing|completed|failed) or None. PURE.
    Tolerant of {data:{status}} (real shape) and a flat {status} fallback."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("status"), str):
        return str(data["status"])
    if isinstance(payload.get("status"), str):
        return str(payload["status"])
    return None


def extract_video_url(payload: Any) -> str | None:
    """HeyGen status JSON → finished MP4 URL or None. Tolerant of {data:{video_url}} | {video_url}. PURE."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("video_url"), str):
        return str(data["video_url"])
    if isinstance(payload.get("video_url"), str):
        return str(payload["video_url"])
    return None


def build_avatar_body(
    avatar_id: str,
    *,
    audio_url: str | None = None,
    script_text: str | None = None,
    voice_id: str | None = None,
    aspect: str = "vertical",
) -> dict[str, Any]:
    """/v2/video/generate body. voice = audio_url (preferred, mirrors web) OR text+voice_id. PURE."""
    if audio_url:
        voice: dict[str, Any] = {"type": "audio", "audio_url": audio_url}
    else:
        voice = {"type": "text", "input_text": (script_text or "")[:_SCRIPT_CAP]}
        if voice_id:
            voice["voice_id"] = voice_id
    return {
        "video_inputs": [
            {
                "character": {"type": "avatar", "avatar_id": avatar_id, "avatar_style": "normal"},
                "voice": voice,
            }
        ],
        "dimension": dimensions_for(aspect),
    }


def extract_translate_status(payload: Any) -> str | None:
    """HeyGen translate status JSON → status string or None. Tolerant of {data:{status}}|{status}. PURE."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("status"), str):
        return str(data["status"])
    if isinstance(payload.get("status"), str):
        return str(payload["status"])
    return None


def extract_translate_url(payload: Any) -> str | None:
    """HeyGen translate result JSON → translated MP4 URL or None. Tolerant of the documented shapes:
    {data:{url}} | {data:{video_url}} | {url} | {video_url}. PURE."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        for k in ("url", "video_url"):
            if isinstance(data.get(k), str):
                return str(data[k])
    for k in ("url", "video_url"):
        if isinstance(payload.get(k), str):
            return str(payload[k])
    return None


def build_translate_body(video_url: str, output_language: str, *, dynamic_duration: bool = False) -> dict[str, Any]:
    """/v2/video_translate body. dynamic_duration=False is CRITICAL — the translated clip MUST keep the
    source duration so the EDL two-timebase offset table (cuts/captions/motion) stays 1:1 aligned. PURE."""
    return {
        "video_url": video_url,
        "output_language": output_language,
        "translate_audio_only": False,
        "enable_dynamic_duration": dynamic_duration,
    }


def translate_video(
    video_url: str,
    output_language: str,
    *,
    dynamic_duration: bool = False,
    max_wait_s: float = 600.0,
    label: str = "translate",
) -> str | None:
    """Submit a video for lip-sync translation to `output_language` (a HeyGen language NAME, e.g.
    "Russian"), poll to completion, return the translated MP4 URL or None. FAIL-SOFT. Preserves the
    source aspect ratio (9:16 stays 9:16) and — with dynamic_duration=False — the source duration."""
    key = heygen_api_key()
    if not key or not video_url or not output_language:
        return None
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    body = build_translate_body(video_url, output_language, dynamic_duration=dynamic_duration)
    try:
        with httpx.Client(timeout=30.0) as client:
            sub = client.post(f"{_API_BASE}{_TRANSLATE_SUBMIT}", headers=headers, json=body)
            if sub.status_code >= 400:
                log.warning(f"{label}.submit_error", status=sub.status_code, detail=sub.text[:200])
                return None
            data = sub.json().get("data")
            tid = data.get("video_translate_id") if isinstance(data, dict) else None
            if not isinstance(tid, str) or not tid:
                return None

            waited = 0.0
            while waited < max_wait_s:
                st = client.get(f"{_API_BASE}{_TRANSLATE_STATUS}/{tid}", headers=headers)
                payload = st.json() if st.status_code < 400 else None
                status = extract_translate_status(payload)
                if status in ("success", "completed"):
                    return extract_translate_url(payload)
                if status in ("failed", "error"):
                    log.warning(f"{label}.failed", translate_id=tid)
                    return None
                time.sleep(_POLL_INTERVAL_S)
                waited += _POLL_INTERVAL_S
            log.warning(f"{label}.timeout", translate_id=tid)
            return None
    except Exception as exc:  # noqa: BLE001 — network/JSON; translation is optional
        log.warning(f"{label}.error", error=str(exc)[:200])
        return None


def generate_avatar_video(
    *,
    avatar_id: str,
    audio_url: str | None = None,
    script_text: str | None = None,
    voice_id: str | None = None,
    aspect: str = "vertical",
    max_wait_s: float = 300.0,
    label: str = "avatar",
) -> str | None:
    """Submit an avatar video, poll to completion, return the finished MP4 URL or None. FAIL-SOFT.
    Provide EITHER audio_url (ElevenLabs MP3, preferred — perfect lip-sync) OR script_text (+voice_id)."""
    key = heygen_api_key()
    if not key or not avatar_id or not (audio_url or script_text):
        return None
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    body = build_avatar_body(
        avatar_id, audio_url=audio_url, script_text=script_text, voice_id=voice_id, aspect=aspect
    )
    try:
        with httpx.Client(timeout=30.0) as client:
            sub = client.post(f"{_API_BASE}/v2/video/generate", headers=headers, json=body)
            if sub.status_code >= 400:
                log.warning(f"{label}.submit_error", status=sub.status_code, detail=sub.text[:200])
                return None
            data = sub.json().get("data")
            video_id = data.get("video_id") if isinstance(data, dict) else None
            if not isinstance(video_id, str) or not video_id:
                return None

            waited = 0.0
            while waited < max_wait_s:
                st = client.get(
                    f"{_API_BASE}/v1/video_status.get", headers=headers, params={"video_id": video_id}
                )
                payload = st.json() if st.status_code < 400 else None
                status = extract_status(payload)
                if status == "completed":
                    return extract_video_url(payload)
                if status == "failed":
                    log.warning(f"{label}.failed", video_id=video_id)
                    return None
                time.sleep(_POLL_INTERVAL_S)
                waited += _POLL_INTERVAL_S
            log.warning(f"{label}.timeout", video_id=video_id)
            return None
    except Exception as exc:  # noqa: BLE001 — network/JSON; avatar is optional
        log.warning(f"{label}.error", error=str(exc)[:200])
        return None

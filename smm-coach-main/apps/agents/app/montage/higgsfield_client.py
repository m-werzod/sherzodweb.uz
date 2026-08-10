"""Higgsfield image→video client (V2 platform API) for the cinematic per-shot pipeline.

Mirrors the PROVEN web client (apps/web/src/lib/higgsfield) — SAME V2 wire contract + auth — so the
SAME account credentials power both surfaces (no separate key). SYNC, worker-thread only, FAIL-SOFT:
no creds / API error / failed / nsfw / timeout → None, so a single failed shot just drops out and the
reel builds from the rest.

Higgsfield DoP is IMAGE→VIDEO: ONE keyframe image URL + a text prompt + an optional camera-MOTION
preset → a ~5s cinematic clip. It takes NO audio/music and NO whole-video input — so music + final
assembly stay in OUR own compiler (see higgsfield_assemble).

Auth:   Authorization: Key <KEY_ID>:<KEY_SECRET>  (from HF_CREDENTIALS / HF_KEY split on first ':',
        or HF_API_KEY + HF_API_SECRET).
Submit: POST {base}/v1/image2video/dop with the DoP input object as the body.
Poll:   GET  {base}/requests/{request_id}/status  until status in {completed, failed, nsfw}.
Result: response.video.url (fallback images[0].url).
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_POLL_INTERVAL_S = 3.0
_DOP_ENDPOINT = "/v1/image2video/dop"
_SOUL_ENDPOINT = "/v1/text2image/soul"
_TERMINAL_FAIL = {"failed", "nsfw", "error", "canceled", "cancelled"}

# Neutral camera-motion vocabulary the director picks from. These are NAMES, not Higgsfield ids —
# resolve_motion_id() maps a name → a motion UUID via HIGGSFIELD_MOTION_CATALOG. The name is also
# folded into the prompt so the move still lands even when no id mapping is configured.
MOTION_NAMES: tuple[str, ...] = (
    "static", "push_in", "pull_out", "orbit", "arc_left", "arc_right",
    "pan_left", "pan_right", "tilt_up", "tilt_down", "crane_up", "crane_down",
    "handheld", "dolly_zoom", "fpv", "overhead",
)

_MOTION_PROMPT_HINT: dict[str, str] = {
    "static": "static locked-off shot",
    "push_in": "slow cinematic push-in",
    "pull_out": "slow pull-out reveal",
    "orbit": "smooth 360 orbit around the subject",
    "arc_left": "camera arcs to the left",
    "arc_right": "camera arcs to the right",
    "pan_left": "smooth pan left",
    "pan_right": "smooth pan right",
    "tilt_up": "camera tilts up",
    "tilt_down": "camera tilts down",
    "crane_up": "crane shot rising up",
    "crane_down": "crane shot descending",
    "handheld": "energetic handheld motion",
    "dolly_zoom": "dramatic dolly-zoom (vertigo) effect",
    "fpv": "fast FPV drone fly-through",
    "overhead": "top-down overhead move",
}


def credentials() -> tuple[str, str] | None:
    """(KEY_ID, KEY_SECRET) from HF_CREDENTIALS / HF_KEY (split on first ':') or HF_API_KEY +
    HF_API_SECRET, or None. Mirrors the web client's readCredentials()."""
    s = get_settings()
    combined = s.hf_credentials.get_secret_value() if s.hf_credentials else ""
    if not combined:
        combined = os.getenv("HF_KEY", "")
    if ":" in combined:
        i = combined.index(":")
        key, secret = combined[:i], combined[i + 1 :]
        return (key, secret) if key and secret else None
    key = s.hf_api_key or ""
    secret = s.hf_api_secret.get_secret_value() if s.hf_api_secret else ""
    return (key, secret) if key and secret else None


def higgsfield_enabled() -> bool:
    """Whether the cinematic pipeline can run — the flag is ON and credentials are present."""
    return bool(get_settings().enable_higgsfield) and credentials() is not None


def _auth_header() -> str | None:
    creds = credentials()
    return f"Key {creds[0]}:{creds[1]}" if creds else None


def motion_prompt_hint(motion_name: str | None) -> str:
    """Camera-motion NAME → an EN prompt fragment (PURE). Unknown/None → '' (no camera clause)."""
    return _MOTION_PROMPT_HINT.get((motion_name or "").strip().lower(), "")


def _load_motion_catalog() -> dict[str, str]:
    """HIGGSFIELD_MOTION_CATALOG (JSON name→id) → dict. Best-effort → {} on missing/malformed."""
    raw = (get_settings().higgsfield_motion_catalog or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).strip().lower(): str(v) for k, v in data.items() if k and v}


def resolve_motion_id(motion_name: str | None) -> str | None:
    """Camera-motion NAME → a Higgsfield motion UUID via the env catalog, or None (→ omit motion,
    the move still rides in the prompt). Reads settings only."""
    return _load_motion_catalog().get((motion_name or "").strip().lower()) or None


def extract_video_url(payload: Any) -> str | None:
    """Higgsfield V2 result JSON → clip URL (PURE/testable). Tolerant of the shapes the API emits:
    {"video":{"url":..}} (DoP) | {"images":[{"url":..}]} (fallback) | a bare URL string, plus common
    envelopes ({"output"|"result"|"data"|"response": …}) unwrapped recursively."""
    if isinstance(payload, str):
        return payload if payload.startswith("http") else None
    if isinstance(payload, list):
        for item in payload:
            got = extract_video_url(item)
            if got:
                return got
        return None
    if not isinstance(payload, dict):
        return None
    for wrap in ("output", "result", "data", "response", "video", "videos", "images", "outputs", "results"):
        if wrap in payload:
            got = extract_video_url(payload[wrap])
            if got:
                return got
    for key in ("video_url", "url", "mp4", "output_url", "videoUrl"):
        v = payload.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None


def build_dop_body(
    *,
    model: str,
    image_url: str,
    prompt: str,
    motion_id: str | None,
    motion_strength: float,
    seed: int,
) -> dict[str, Any]:
    """Assemble the DoP image→video request body (PURE/testable). The live V2 API nests the generation
    input under a `params` object (a flat body 422s with "params: Field required") — confirmed against
    platform.higgsfield.ai."""
    params: dict[str, Any] = {
        "model": model,
        "prompt": (prompt or "").strip()[:600],
        "input_images": [{"type": "image_url", "image_url": image_url}],
        "enhance_prompt": True,
    }
    if motion_id:
        params["motions"] = [{"id": motion_id, "strength": max(0.0, min(1.0, float(motion_strength)))}]
    if seed:
        # The V2 API constrains seed to [1, 1_000_000]; our crc32-derived seeds overflow that → fold in.
        s = int(seed)
        params["seed"] = s if 1 <= s <= 1_000_000 else 1 + (abs(s) % 1_000_000)
    return {"params": params}


def _submit_poll(
    body: dict[str, Any], headers: dict[str, str], base: str, *, max_wait_s: float, label: str,
    endpoint: str = _DOP_ENDPOINT,
) -> Any:
    """POST a generation body, then poll the status endpoint to a terminal state. Returns the result
    JSON (or None). FAIL-SOFT — never raises."""
    try:
        with httpx.Client(timeout=30.0) as client:
            sub = client.post(f"{base}{endpoint}", headers=headers, json=body)
            if sub.status_code >= 400:
                log.warning(f"{label}.submit_error", status=sub.status_code, detail=sub.text[:200])
                return None
            try:
                data = sub.json()
            except ValueError:
                return None
            status = str(data.get("status") or "").lower()
            if status == "completed" or extract_video_url(data):
                return data
            if status in _TERMINAL_FAIL:
                log.warning(f"{label}.failed", status=status)
                return None
            # Submit returns {"id": ...}; the status endpoint echoes it as "request_id".
            request_id = data.get("id") or data.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                log.warning(f"{label}.no_request_id")
                return None

            waited = 0.0
            while waited < max_wait_s:
                time.sleep(_POLL_INTERVAL_S)
                waited += _POLL_INTERVAL_S
                st = client.get(f"{base}/requests/{request_id}/status", headers=headers)
                if st.status_code >= 400:
                    continue
                try:
                    sd = st.json()
                except ValueError:
                    continue
                sstatus = str(sd.get("status") or "").lower()
                if sstatus == "completed" or extract_video_url(sd):
                    return sd
                if sstatus in _TERMINAL_FAIL:
                    log.warning(f"{label}.failed", status=sstatus)
                    return None
            log.warning(f"{label}.timeout", request_id=request_id)
            return None
    except Exception as exc:  # noqa: BLE001 — network/JSON; the cinematic pass is optional
        log.warning(f"{label}.error", error=str(exc)[:200])
        return None


def generate_clip(
    image_url: str,
    prompt: str,
    *,
    motion_name: str | None = None,
    motion_strength: float = 0.8,
    seed: int = 0,
    duration_s: float = 5.0,  # DoP clip length is model-fixed; kept for caller/assembler symmetry
    max_wait_s: float = 300.0,
    label: str = "higgsfield",
) -> str | None:
    """image→video: return the generated clip's URL or None. FAIL-SOFT.

    `motion_name` is a neutral name (see MOTION_NAMES); resolved to a Higgsfield motion id via the env
    catalog when possible, and its camera clause is folded into the prompt regardless."""
    if not (image_url or "").strip():
        return None
    auth = _auth_header()
    if not auth:
        return None
    s = get_settings()
    hint = motion_prompt_hint(motion_name)
    full_prompt = f"{prompt.strip()}, {hint}" if hint else (prompt or "").strip()
    body = build_dop_body(
        model=s.higgsfield_video_model,
        image_url=image_url,
        prompt=full_prompt,
        motion_id=resolve_motion_id(motion_name),
        motion_strength=motion_strength,
        seed=seed,
    )
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    return extract_video_url(
        _submit_poll(body, headers, s.higgsfield_base_url.rstrip("/"), max_wait_s=max_wait_s, label=label)
    )


def generate_image(
    prompt: str,
    *,
    size: str = "1152x2048",
    quality: str = "720p",
    seed: int = 0,
    max_wait_s: float = 180.0,
    label: str = "higgsfield_soul",
) -> str | None:
    """text→image via Soul (graphics/visual elements for the montage); image URL or None. FAIL-SOFT.
    Same params wrapper + poll contract as DoP; the status payload carries images[0].url."""
    if not (prompt or "").strip():
        return None
    auth = _auth_header()
    if not auth:
        return None
    s = get_settings()
    params: dict[str, Any] = {
        "prompt": prompt.strip()[:600],
        "width_and_height": size,
        "quality": quality,
        "batch_size": 1,
        "enhance_prompt": True,
    }
    if seed:
        sd = int(seed)
        params["seed"] = sd if 1 <= sd <= 1_000_000 else 1 + (abs(sd) % 1_000_000)
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    return extract_video_url(
        _submit_poll({"params": params}, headers, s.higgsfield_base_url.rstrip("/"),
                     max_wait_s=max_wait_s, label=label, endpoint=_SOUL_ENDPOINT)
    )

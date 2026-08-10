"""Generative B-roll — fal.ai text-to-video / Kling (Faza B, GPU plane).

Thin wrapper over fal_client: builds the kling text-to-video body and submits it. SYNC,
worker-thread only, FAIL-SOFT (no key / error → None → montage falls back to Pexels stock).
Returns a direct MP4 URL — the caller downloads it with the same download_video the stock path uses.

OPT-IN: runs only when a plan entry is marked source="generate" AND FAL_KEY is set.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.montage.fal_client import run_queue_video


def generate_broll_url(prompt: str, *, seconds: float = 5.0) -> str | None:
    """Generate a short vertical clip from `prompt` via fal.ai Kling; return its MP4 URL or None."""
    p = (prompt or "").strip()
    if not p:
        return None
    # Kling text-to-video accepts `duration` ONLY as the string enum "5" | "10" (an int → HTTP 422)
    # and does NOT accept image_url on the t2v path (use the image-to-video slug for ref frames).
    body: dict[str, Any] = {
        "prompt": p[:500],
        "duration": "10" if round(seconds) >= 8 else "5",
        "aspect_ratio": "9:16",
    }
    return run_queue_video(get_settings().fal_video_model, body, label="gen_video")

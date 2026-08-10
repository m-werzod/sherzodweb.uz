"""Scenario-matched decor / background replacement — fal.ai (Faza C, GPU plane).

Two halves, both via the shared fal_client queue:
  * matte_subject(video_url)   — bria/video/background-removal, background_color="Transparent"
                                 → an alpha (WebM) cut-out of the speaker (≤30s, ≤4000px input).
  * generate_background(prompt) — FLUX text→image → a scenario-matched vertical background image.

The caller (compile_and_render._maybe_add_decor_background) uploads the normalized clip, mattes it,
generates a bg from the task's decor prompt, composites matte-over-bg with ffmpeg, and appends a
SOURCE-aligned `source_variant(kind="decor")` that STUDIO swaps in as the base (pickSourceVariant) —
no track reshuffle. SYNC, worker-thread only, FAIL-SOFT, FAL_KEY-gated.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.montage.fal_client import run_queue_image, run_queue_video


def matte_subject(video_url: str, *, max_wait_s: float = 300.0) -> str | None:
    """bria video bg-removal → a transparent (alpha) WebM URL of the subject, or None. FAIL-SOFT.
    Input must be ≤30s and ≤4000px (caller's normalized 1080x1920 clip qualifies)."""
    url = (video_url or "").strip()
    if not url:
        return None
    body: dict[str, Any] = {
        "video_url": url,
        "background_color": "Transparent",
        "output_container_and_codec": "webm_vp9",  # alpha-capable container
        "preserve_audio": False,  # audio stays on the original base clip (STUDIO links it back)
    }
    return run_queue_video(get_settings().fal_matte_model, body, max_wait_s=max_wait_s, label="matte")


def generate_background(prompt: str, *, max_wait_s: float = 120.0) -> str | None:
    """FLUX text→image → a scenario-matched vertical (9:16) background image URL, or None. FAIL-SOFT."""
    p = (prompt or "").strip()
    if not p:
        return None
    body: dict[str, Any] = {"prompt": p[:500], "image_size": "portrait_16_9"}
    return run_queue_image(get_settings().fal_image_model, body, max_wait_s=max_wait_s, label="bg")

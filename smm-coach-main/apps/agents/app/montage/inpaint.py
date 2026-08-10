"""Video object removal — fal.ai void-video-inpainting (Faza D, GPU plane).

Removes the element named in `remove` ("person", "logo", "the man in the background") via SAM-3
auto-mask from TEXT — NO mask UI needed — and fills the background, producing a SOURCE-aligned 1:1
cleaned variant of the clip. The caller appends it to edl.source_variants(kind="inpaint"); STUDIO
swaps it in as the base (pickSourceVariant). SYNC, worker-thread only, FAIL-SOFT, FAL_KEY-gated.

void contract (confirmed against fal's live API page): video_url (req) + mask_prompt (what to remove,
SAM-3) + prompt (desired background) + enable_pass2_refinement (temporal consistency on longer clips).
$0.05/video (+$0.05 SAM-3 mask). KNOWN LIMIT: blocks the worker thread (ENCODE_GATE) — opt-in; gpu_worker = upgrade.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.montage.fal_client import run_queue_video, upload_file

_DEFAULT_BG = "clean, natural background consistent with the original scene, photorealistic"


def inpaint_local(path: str, *, remove: str, background: str = "") -> str | None:
    """Upload a LOCAL clip to fal, remove `remove` via void-inpainting, return the cleaned MP4 URL or
    None. FAIL-SOFT (no key / upload / inpaint error → None). Convenience over upload_file+inpaint_video."""
    if not (remove or "").strip():
        return None
    src_url = upload_file(path)
    if not src_url:
        return None
    return inpaint_video(src_url, remove=remove, background=background)


def inpaint_video(video_url: str, *, remove: str, background: str = "", max_wait_s: float = 300.0) -> str | None:
    """Remove `remove` from the video at `video_url` via fal void-inpainting; return the cleaned MP4
    URL or None. FAIL-SOFT. `remove` drives the SAM-3 auto-mask (plain text, no manual masking)."""
    url = (video_url or "").strip()
    rem = (remove or "").strip()
    if not url or not rem:
        return None
    body: dict[str, Any] = {
        "video_url": url,
        "mask_prompt": rem[:200],
        "prompt": (background.strip() or _DEFAULT_BG)[:400],
        "enable_pass2_refinement": True,
    }
    return run_queue_video(get_settings().fal_inpaint_model, body, max_wait_s=max_wait_s, label="inpaint")

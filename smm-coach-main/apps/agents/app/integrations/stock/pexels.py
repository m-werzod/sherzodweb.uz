"""Pexels stock video — vertical B-roll search + download (Faza 3).

Free API (https://www.pexels.com/api/). Used by montage.broll.resolve_broll to fill
storyboard shots the user's own footage doesn't cover. SYNC by design: it's called
only from the montage worker THREAD (compile_and_render → resolve_broll), never the
event loop. Every path is fail-soft — no key / API error / no result → returns None
(or False), so B-roll silently degrades to "no b-roll" and the render proceeds.
"""
from __future__ import annotations

import contextlib

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_SEARCH_URL = "https://api.pexels.com/videos/search"
_MAX_BYTES = 60 * 1024 * 1024  # 60 MB cap — a short vertical clip is far smaller
_MAX_FILE_W = 1280  # don't pull 4K files; ~720-1080 wide vertical is plenty for a 1080x1920 frame


def _api_key() -> str | None:
    key = get_settings().pexels_api_key
    return key.get_secret_value() if key is not None else None


def search_vertical_video(query: str, *, min_dur: float = 2.0, timeout: float = 15.0) -> str | None:
    """Return a direct MP4 URL for a PORTRAIT stock clip matching `query`, or None.

    Picks the highest-resolution portrait (h>w) mp4 file at or under _MAX_FILE_W, from a
    video at least `min_dur` seconds long (so it covers the window without a hard loop seam).
    """
    key = _api_key()
    q = (query or "").strip()
    if not key or not q:
        return None
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(
                _SEARCH_URL,
                headers={"Authorization": key},
                params={"query": q[:80], "orientation": "portrait", "per_page": 8, "size": "medium"},
            )
        if resp.status_code >= 400:
            log.warning("pexels.search_error", status=resp.status_code, detail=resp.text[:200])
            return None
        videos = resp.json().get("videos") or []
    except Exception as exc:  # noqa: BLE001 — network/JSON; b-roll is optional
        log.warning("pexels.search_failed", error=str(exc)[:200])
        return None

    # Prefer a video long enough to cover the window, then the best portrait file in it.
    ranked = sorted(
        (v for v in videos if isinstance(v, dict)),
        key=lambda v: (float(v.get("duration") or 0) >= min_dur, float(v.get("duration") or 0)),
        reverse=True,
    )
    for v in ranked:
        best = _best_portrait_file(v.get("video_files") or [])
        if best:
            return best
    return None


def _best_portrait_file(files: list[object]) -> str | None:
    """The widest portrait mp4 link at/under _MAX_FILE_W (None if no portrait file)."""
    candidates: list[tuple[int, str]] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        link = f.get("link")
        w = f.get("width") or 0
        h = f.get("height") or 0
        ft = str(f.get("file_type") or "")
        if (
            isinstance(link, str)
            and isinstance(w, int)
            and isinstance(h, int)
            and h > w  # portrait
            and 0 < w <= _MAX_FILE_W
            and ("mp4" in ft or link.endswith(".mp4"))
        ):
            candidates.append((w, link))
    if not candidates:
        return None
    candidates.sort(reverse=True)  # widest first (best quality under the cap)
    return candidates[0][1]


def download_video(url: str, dest: str, *, timeout: float = 60.0) -> bool:
    """Stream a stock clip to `dest`. Returns False on any error or an oversized body."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client, client.stream(
            "GET", url
        ) as resp:
            if resp.status_code >= 400:
                return False
            total = 0
            with open(dest, "wb") as fh:
                for chunk in resp.iter_bytes(chunk_size=1 << 16):
                    total += len(chunk)
                    if total > _MAX_BYTES:
                        log.warning("pexels.download_too_big", url=url[:80])
                        return False
                    fh.write(chunk)
        return total > 0
    except Exception as exc:  # noqa: BLE001
        log.warning("pexels.download_failed", error=str(exc)[:200])
        with contextlib.suppress(OSError):
            import os

            if os.path.exists(dest):
                os.remove(dest)
        return False

"""Restyle an uploaded clip via Runway Aleph, keep the user's VOICE, finish it as a 9:16 reel.

Flow (SYNC, montage worker thread, FAIL-SOFT):
  1. upload the clip to a PUBLIC url (fal CDN — Runway fetches the asset server-side);
  2. runway_client.restyle → a restyled clip URL (Aleph trims to ~20s);
  3. download it, then remux the ORIGINAL audio back (Aleph drops the narration) + normalise to 1080×1920;
  4. burn captions (from scriptTimeline) + loudnorm → mp4.

Any failure degrades gracefully: no fal key / restyle fail → return not-ok (worker keeps the plain
upload render); caption failure → drop only captions. Runway's ~20s cap is a known v1 limit
(segmenting a longer clip is the next step).
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx
import structlog

from app.montage import runway_client
from app.montage.captions import render_ass
from app.montage.edl import CAPTION_FONTS, Captions, CaptionStyle, CaptionWindow, CaptionWord
from app.montage.fal_client import upload_file
from app.montage.probe import FFmpegError, probe_clip, run_ff

log = structlog.get_logger(__name__)

_W, _H, _FPS = 1080, 1920, 30
_ENCODE_TAIL = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
]
_NORM_VF = (
    f"scale={_W}:{_H}:force_original_aspect_ratio=decrease,"
    f"pad={_W}:{_H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={_FPS},format=yuv420p"
)
_LN = "loudnorm=I=-14:TP=-1:LRA=11"


def _download(url: str, dest: str) -> bool:
    try:
        with httpx.Client(timeout=180.0, follow_redirects=True) as client:
            r = client.get(url)
            if r.status_code >= 400:
                return False
            with open(dest, "wb") as f:
                f.write(r.content)
    except Exception as exc:  # noqa: BLE001
        log.warning("runway_restyle.download_failed", error=str(exc)[:160])
        return False
    return os.path.exists(dest) and os.path.getsize(dest) > 0


def _parse_range(t: Any) -> tuple[float, float] | None:
    """'0-3s' | '3-13s' → (start, end) seconds (PURE)."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", str(t or ""))
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    return (a, b) if b > a else None


def build_captions(script_timeline: list[Any], max_dur: float, style_spec: dict[str, Any] | None) -> Captions:
    """Karaoke captions from the scriptTimeline segments, clipped to the output duration (PURE)."""
    style = CaptionStyle()
    if isinstance(style_spec, dict):
        font = style_spec.get("font")
        if isinstance(font, str) and font in CAPTION_FONTS:
            style = style.model_copy(update={"font": font})
    windows: list[CaptionWindow] = []
    for seg in script_timeline or []:
        if not isinstance(seg, dict):
            continue
        rng = _parse_range(seg.get("t"))
        text = str(seg.get("text") or "").strip()
        if not rng or not text:
            continue
        start, end = rng
        if start >= max_dur:
            continue
        end = min(end, max_dur)
        words = [w for w in re.split(r"\s+", text) if w]
        if not words or end <= start:
            continue
        per = (end - start) / len(words)
        windows.append(
            CaptionWindow(
                words=[
                    CaptionWord(text=w, start=round(start + i * per, 3), end=round(start + (i + 1) * per, 3))
                    for i, w in enumerate(words)
                ]
            )
        )
    return Captions(play_res=[_W, _H], tier="premium", style=style, windows=windows)


def _remux_normalize(restyled: str, upload: str, dst: str) -> bool:
    """Restyled VIDEO + ORIGINAL upload AUDIO, normalised to 1080×1920 CFR, bounded to the restyled
    length. Synthesises silence if the upload has no audio track. Returns True on success."""
    try:
        has_audio = probe_clip(upload).has_audio
    except (FFmpegError, OSError):
        has_audio = False
    cmd = ["ffmpeg", "-y", "-i", restyled]
    if has_audio:
        cmd += ["-i", upload]
        amap = "1:a:0"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        amap = "1:a:0"
    cmd += [
        "-vf", _NORM_VF, "-map", "0:v:0", "-map", amap,
        "-ar", "48000", "-ac", "2", "-shortest",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-fps_mode", "cfr", "-r", str(_FPS),
        "-movflags", "+faststart", dst,
    ]
    try:
        run_ff(cmd)
    except (FFmpegError, OSError) as exc:
        log.warning("runway_restyle.remux_failed", error=str(exc)[:160])
        return False
    return os.path.exists(dst) and os.path.getsize(dst) > 0


def _finish(styled: str, ass_path: str | None, out: str) -> bool:
    """Burn captions + loudnorm; degrade to loudnorm-only if the caption burn fails."""
    attempts = []
    if ass_path:
        attempts.append(f"[0:v]ass={ass_path}:fontsdir=/usr/share/fonts[vout];[0:a]{_LN}[aout]")
    attempts.append(f"[0:v]copy[vout];[0:a]{_LN}[aout]")
    for fc in attempts:
        try:
            run_ff(["ffmpeg", "-y", "-i", styled, "-filter_complex", fc,
                    "-map", "[vout]", "-map", "[aout]", *_ENCODE_TAIL, out])
            if os.path.exists(out) and os.path.getsize(out) > 0:
                return True
        except (FFmpegError, OSError) as exc:
            log.warning("runway_restyle.finish_attempt_failed", error=str(exc)[:160])
            continue
    # Floor: just copy the styled clip.
    try:
        run_ff(["ffmpeg", "-y", "-i", styled, "-c", "copy", "-movflags", "+faststart", out])
        return os.path.exists(out) and os.path.getsize(out) > 0
    except (FFmpegError, OSError):
        return False


def restyle_upload(
    upload_path: str,
    *,
    work_dir: str,
    prompt: str,
    script_timeline: list[Any] | None = None,
    caption_style: dict[str, Any] | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Restyle the uploaded clip end-to-end. Returns {ok, out_path?, duration, error?}."""
    if not upload_path or not os.path.exists(upload_path):
        return {"ok": False, "duration": 0.0, "error": "no_upload"}
    public_url = upload_file(upload_path)
    if not public_url:
        return {"ok": False, "duration": 0.0, "error": "public_upload_failed (FAL_KEY kerak)"}

    out_url = runway_client.restyle(public_url, prompt, seed=seed)
    if not out_url:
        return {"ok": False, "duration": 0.0, "error": "runway_restyle_failed"}

    restyled = os.path.join(work_dir, "restyled.mp4")
    if not _download(out_url, restyled):
        return {"ok": False, "duration": 0.0, "error": "restyled_download_failed"}

    styled_voiced = os.path.join(work_dir, "styled_voiced.mp4")
    if not _remux_normalize(restyled, upload_path, styled_voiced):
        return {"ok": False, "duration": 0.0, "error": "remux_failed"}

    try:
        dur = probe_clip(styled_voiced).duration or 0.0
    except (FFmpegError, OSError):
        dur = 0.0

    ass_path: str | None = None
    try:
        caps = build_captions(script_timeline or [], dur or 9999.0, caption_style)
        if caps.windows:
            ass_path = render_ass(caps, os.path.join(work_dir, "cap.ass"))
    except Exception as exc:  # noqa: BLE001 — captions are polish
        log.warning("runway_restyle.captions_failed", error=str(exc)[:160])
        ass_path = None

    out = os.path.join(work_dir, "runway.mp4")
    if not _finish(styled_voiced, ass_path, out):
        return {"ok": False, "duration": dur, "error": "finish_failed"}
    try:
        final_dur = probe_clip(out).duration or dur
    except (FFmpegError, OSError):
        final_dur = dur
    return {"ok": True, "out_path": out, "duration": round(final_dur, 2)}

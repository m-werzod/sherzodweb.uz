"""Assemble Higgsfield per-shot clips into a finished 9:16 reel.

Self-contained on purpose: the talking-head compiler is built around ONE narrated source clip + a
transcript, but Higgsfield clips are silent cinematic shots with no speech to align. So instead of
bending that machinery, this module does the small, well-scoped job the cinematic case needs:

  normalize each shot → 1080×1920 CFR (silent) → concat in order → burn captions (from the script
  timeline, mapped to the ACTUAL output offsets) → bed music → loudnorm → mp4.

It REUSES the proven pieces (probe/run_ff, render_ass + the CaptionStyle system, music.pick_track /
gen_music_track) so the look matches the rest of the app. A small degrade ladder guards each optional
layer: caption-burn failure drops captions, music failure drops music, and the floor is the raw
concat — so the render always yields SOMETHING. SYNC — runs in the montage worker thread.
"""
from __future__ import annotations

import os
import re
from typing import Any

import structlog

from app.montage import music
from app.montage.captions import render_ass
from app.montage.edl import (
    CAPTION_FONTS,
    Captions,
    CaptionStyle,
    CaptionWindow,
    CaptionWord,
)
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


def _normalize_shot(src: str, dst: str, dur: float) -> bool:
    """Scale/pad to 1080×1920 CFR, replace audio with silence (music is added later), trim to `dur`.
    Returns True on success. FAIL-SOFT — a shot that won't normalize is dropped by the caller."""
    try:
        run_ff([
            "ffmpeg", "-y", "-i", src,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", _NORM_VF, "-map", "0:v:0", "-map", "1:a:0",
            "-ar", "48000", "-ac", "2", "-t", f"{max(0.2, dur):.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-fps_mode", "cfr", "-r", str(_FPS),
            "-movflags", "+faststart", dst,
        ])
    except (FFmpegError, OSError) as exc:
        log.warning("hf_assemble.normalize_failed", src=os.path.basename(src), error=str(exc)[:160])
        return False
    return os.path.exists(dst) and os.path.getsize(dst) > 0


def _concat(paths: list[str], work_dir: str) -> str | None:
    """Concat uniformly-normalized clips via the demuxer (-c copy). Returns the path or None."""
    if not paths:
        return None
    list_path = os.path.join(work_dir, "concat.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    out = os.path.join(work_dir, "concat.mp4")
    try:
        run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                "-c", "copy", "-movflags", "+faststart", out])
    except (FFmpegError, OSError) as exc:
        log.warning("hf_assemble.concat_failed", n=len(paths), error=str(exc)[:160])
        return None
    return out if os.path.exists(out) and os.path.getsize(out) > 0 else None


def _shot_text(si: int, script_timeline: list[Any], shot_list: list[Any]) -> str:
    """The caption text for shot `si`: script-timeline segments tagged to this shot, else the
    storyboard shot's dialogue / on-screen text / action. PURE."""
    parts: list[str] = []
    for seg in script_timeline:
        if isinstance(seg, dict) and seg.get("shotIndex") == si:
            t = str(seg.get("text") or "").strip()
            if t:
                parts.append(t)
    if parts:
        return " ".join(parts)
    for sh in shot_list:
        if isinstance(sh, dict) and sh.get("i") == si:
            return str(sh.get("dialogue") or sh.get("on_screen_text") or sh.get("action") or "").strip()
    return ""


def _caption_window(text: str, start: float, end: float) -> CaptionWindow | None:
    """Evenly distribute a shot's words across its OUTPUT window (start..end). PURE/testable."""
    words = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    if not words or end <= start:
        return None
    per = (end - start) / len(words)
    cw = [
        CaptionWord(text=w, start=round(start + i * per, 3), end=round(start + (i + 1) * per, 3))
        for i, w in enumerate(words)
    ]
    return CaptionWindow(words=cw)


def build_captions(
    offsets: list[tuple[int, float, float]],
    script_timeline: list[Any],
    shot_list: list[Any],
    style_spec: dict[str, Any] | None = None,
) -> Captions:
    """Map each generated shot's text onto its ACTUAL output time-window → a premium Captions doc.
    `offsets` = [(shot_index, out_start, out_end)] built from the trimmed clip durations. PURE."""
    style = CaptionStyle()
    if isinstance(style_spec, dict):
        font = style_spec.get("font")
        if isinstance(font, str) and font in CAPTION_FONTS:
            style = style.model_copy(update={"font": font})
    windows: list[CaptionWindow] = []
    for si, start, end in offsets:
        win = _caption_window(_shot_text(si, script_timeline, shot_list), start, end)
        if win is not None:
            windows.append(win)
    return Captions(play_res=[_W, _H], tier="premium", style=style, windows=windows)


def _music_energy(durations: list[float]) -> float:
    """Shorter average shot → punchier reel → higher energy (PURE). Clamped 0.2..0.9."""
    if not durations:
        return 0.5
    avg = sum(durations) / len(durations)
    return max(0.2, min(0.9, 1.0 - (avg - 2.0) / 6.0))


def _final_mux(concat_path: str, ass_path: str | None, music_path: str | None, total: float, out: str) -> tuple[bool, int]:
    """Burn captions + bed music + loudnorm. Small degrade ladder: (captions+music) →
    (music only) → (captions only) → (raw concat copy). Returns (ok, degrade_level)."""
    vout_ass = f"[0:v]ass={ass_path}:fontsdir=/usr/share/fonts[vout]" if ass_path else None
    vout_copy = "[0:v]copy[vout]"
    ln = "loudnorm=I=-14:TP=-1:LRA=11"

    def _run_music(vfilter: str) -> None:
        assert music_path is not None  # only invoked from attempts where music_path is set
        fc = f"{vfilter};[1:a]{ln}[aout]"
        run_ff(["ffmpeg", "-y", "-i", concat_path, "-stream_loop", "-1", "-i", music_path,
                "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
                "-t", f"{total:.2f}", *_ENCODE_TAIL, out])

    def _run_silent(vfilter: str) -> None:
        fc = f"{vfilter};[0:a]{ln}[aout]"
        run_ff(["ffmpeg", "-y", "-i", concat_path, "-filter_complex", fc,
                "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}", *_ENCODE_TAIL, out])

    # (attempt callable, degrade level). Ordered best → floor; first that succeeds wins.
    attempts: list[tuple[str, Any, int]] = []
    if vout_ass and music_path:
        attempts.append(("captions+music", lambda: _run_music(vout_ass), 0))
    if vout_ass:
        attempts.append(("captions", lambda: _run_silent(vout_ass), 0))
    if music_path:
        attempts.append(("music", lambda: _run_music(vout_copy), 1))
    attempts.append(("silent", lambda: _run_silent(vout_copy), 1))

    for name, fn, level in attempts:
        try:
            fn()
            if os.path.exists(out) and os.path.getsize(out) > 0:
                log.info("hf_assemble.mux_ok", stage=name, degrade=level)
                return True, level
        except (FFmpegError, OSError) as exc:
            log.warning("hf_assemble.mux_attempt_failed", stage=name, error=str(exc)[:160])
            continue

    # Floor: hand back the raw concat so the user still gets a reel.
    try:
        run_ff(["ffmpeg", "-y", "-i", concat_path, "-c", "copy", "-movflags", "+faststart", out])
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return True, 3
    except (FFmpegError, OSError) as exc:
        log.warning("hf_assemble.passthrough_failed", error=str(exc)[:160])
    return False, 3


def assemble(
    shot_results: list[dict[str, Any]],
    *,
    work_dir: str,
    script_timeline: list[Any] | None = None,
    shot_list: list[Any] | None = None,
    caption_style: dict[str, Any] | None = None,
    hook_text: str | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Assemble the successfully-generated shot clips into the final reel.
    Returns {ok, out_path?, duration, shots_used, degrade, error?}."""
    ok_shots = [r for r in shot_results if r.get("ok") and r.get("clip_path") and os.path.exists(r["clip_path"])]
    if not ok_shots:
        return {"ok": False, "duration": 0.0, "shots_used": 0, "degrade": 3, "error": "no_clips"}

    norm_paths: list[str] = []
    offsets: list[tuple[int, float, float]] = []
    durations: list[float] = []
    t = 0.0
    for r in ok_shots:
        raw = r["clip_path"]
        try:
            actual = probe_clip(raw).duration or 5.0
        except (FFmpegError, OSError):
            actual = float(r.get("duration_s") or 5.0)
        dur = min(float(r.get("duration_s") or actual) or actual, actual)
        if dur <= 0.2:
            dur = actual
        # Explicit int check — a legitimate shot_index 0 is falsy and `or` would remap it, desyncing
        # the caption text lookup for that shot.
        raw_si = r.get("shot_index")
        si = raw_si if isinstance(raw_si, int) else len(norm_paths) + 1
        dst = os.path.join(work_dir, f"norm_{si}.mp4")
        if not _normalize_shot(raw, dst, dur):
            continue
        # Anchor offsets/total to the ACTUAL normalized clip length (frame-quantized by -t), not the
        # requested dur, so captions stay in sync and the final -t matches the real concat length.
        try:
            norm_dur = probe_clip(dst).duration or dur
        except (FFmpegError, OSError):
            norm_dur = dur
        norm_paths.append(dst)
        offsets.append((si, t, t + norm_dur))
        durations.append(norm_dur)
        t += norm_dur

    if not norm_paths:
        return {"ok": False, "duration": 0.0, "shots_used": 0, "degrade": 3, "error": "normalize_all_failed"}

    total = t
    concat_path = _concat(norm_paths, work_dir)
    if not concat_path:
        return {"ok": False, "duration": 0.0, "shots_used": len(norm_paths), "degrade": 3, "error": "concat_failed"}

    # Captions (best-effort — a bad .ass just drops the caption layer in _final_mux).
    ass_path: str | None = None
    try:
        caps = build_captions(offsets, script_timeline or [], shot_list or [], caption_style)
        if caps.windows:
            ass_path = render_ass(caps, os.path.join(work_dir, "cap.ass"), hook_text=hook_text)
    except Exception as exc:  # noqa: BLE001 — captions are polish, never block the render
        log.warning("hf_assemble.captions_failed", error=str(exc)[:160])
        ass_path = None

    # Music bed (bundled track → generated → none).
    energy = _music_energy(durations)
    music_path = music.pick_track(seed, energy=energy) or music.gen_music_track(
        energy=energy, duration_sec=total, work_dir=work_dir
    )

    out = os.path.join(work_dir, "higgsfield.mp4")
    ok, degrade = _final_mux(concat_path, ass_path, music_path, total, out)
    if not ok:
        return {"ok": False, "duration": total, "shots_used": len(norm_paths), "degrade": degrade, "error": "mux_failed"}
    try:
        final_dur = probe_clip(out).duration or total
    except (FFmpegError, OSError):
        final_dur = total
    return {
        "ok": True,
        "out_path": out,
        "duration": round(final_dur, 2),
        "shots_used": len(norm_paths),
        "degrade": degrade,
    }

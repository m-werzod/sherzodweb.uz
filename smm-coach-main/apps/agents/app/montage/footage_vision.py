"""Deterministic footage primitives for footage_analyzer — license-clean ffmpeg only.

Two jobs, both best-effort (the node degrades gracefully if either returns nothing):
  * detect_shots  — scene-change timestamps via the GPL ffmpeg scene-score filter
                    (no PySceneDetect / OpenCV dependency).
  * make_vision_proxy — downscale a clip to a small (<18MB) proxy Gemini can ingest inline.
                    Real reels are 100-500MB; Gemini's inline cap is 18MB, so vision needs a
                    cheap proxy that only has to be SEEN, not played.
"""
from __future__ import annotations

import os
import re

from app.montage.footage import ShotBoundary
from app.montage.probe import FFmpegError, run_ff

_PROXY_MAX_BYTES = 18 * 1024 * 1024
_SCENE_PTS = re.compile(r"pts_time:([0-9.]+)")


def to_analysis_proxy(src_path: str, dst_path: str, *, max_side: int = 1280, fps: int = 20) -> str | None:
    """Downscale ANY clip to a light H.264 working copy so the EXPENSIVE decode (4K / 60fps / HEVC /
    Dolby-Vision phone footage) happens exactly ONCE. detect_shots + both vision proxies then run on
    THIS small copy — decoding 1080p H.264 is ~10-20× faster than 4K60 HEVC, which is the difference
    between footage_analyzer finishing inside its run lease and looping forever (the real cause of a
    montage stuck at 'navbatda'). Duration is preserved, so scene-change timestamps stay valid in
    SOURCE seconds. `ultrafast`/crf 28 — this copy is only ANALYSED, never shipped. Degrade-safe:
    returns None on failure and the caller falls back to the raw source."""
    try:
        run_ff(
            [
                "ffmpeg", "-y", "-i", src_path,
                # Fit within max_side×max_side (preserve AR), force 8-bit SDR (collapses HDR/10-bit),
                # cap fps — all to make the single heavy decode + re-encode cheap.
                "-vf",
                f"scale='min({max_side},iw)':'min({max_side},ih)':force_original_aspect_ratio=decrease,"
                f"format=yuv420p",
                "-r", str(fps),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                # Keep audio (downmixed) — the HQ vision proxy derived from this still needs to HEAR
                # pacing/emphasis; detect_shots + the 360p proxy simply ignore it.
                "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart", dst_path,
            ]
        )
    except FFmpegError:
        return None
    return dst_path if os.path.exists(dst_path) and os.path.getsize(dst_path) > 0 else None


def detect_shots(path: str, *, threshold: float = 0.3, min_shot: float = 0.8) -> list[float]:
    """Scene-change SOURCE-second timestamps. Uses ffmpeg's frame scene-score: the
    `select='gt(scene,T)'` filter passes only frames where the visual delta from the prior
    frame exceeds T, and `showinfo` logs their `pts_time`. `-f null` exits 0; data is on
    stderr (same shape as detect_silences). Degrade-safe: returns [] on any error.

    `min_shot` collapses boundaries closer than that (avoids flicker-driven micro-shots)."""
    try:
        proc = run_ff(
            [
                "ffmpeg", "-i", path,
                "-filter:v", f"select='gt(scene,{threshold})',showinfo",
                "-f", "null", "-",
            ]
        )
    except FFmpegError:
        return []
    stderr = proc.stderr or ""
    times: list[float] = []
    for m in _SCENE_PTS.findall(stderr):
        try:  # the loose [0-9.] charclass can match '1.2.3' — keep the degrade-safe promise
            times.append(float(m))
        except ValueError:
            continue
    times.sort()
    out: list[float] = []
    for t in times:
        if not out or t - out[-1] >= min_shot:
            out.append(t)
    return out


def shots_from_scene_times(scene_times: list[float], duration: float) -> list[ShotBoundary]:
    """Turn scene-change timestamps into contiguous ShotBoundary spans over [0, duration].
    Always returns at least one shot (the whole clip) so the FootageMap is never empty."""
    if duration <= 0:
        return []
    # sorted(set(...)) so unsorted / duplicate scene times can't produce negative- or
    # zero-width shots (defensive — this public helper may get callers beyond detect_shots).
    cuts = [0.0, *sorted({t for t in scene_times if 0.0 < t < duration}), duration]
    shots = [
        ShotBoundary(index=i, src_start=cuts[i], src_end=cuts[i + 1], detected_by="scene")
        for i in range(len(cuts) - 1)
    ]
    if len(shots) <= 1:
        return [ShotBoundary(index=0, src_start=0.0, src_end=duration, detected_by="fallback")]
    return shots


def make_vision_proxy(src_path: str, dst_path: str) -> bytes | None:
    """Downscale to a small proxy Gemini can ingest inline (360px wide, ~8fps, no audio —
    vision only needs to SEE content). Returns the proxy bytes, or None if it still exceeds
    the 18MB inline cap (very long inputs) — the caller then degrades to shots-only."""
    try:
        run_ff(
            [
                "ffmpeg", "-y", "-i", src_path,
                "-vf", "scale=360:-2",
                "-r", "8", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "34",
                "-pix_fmt", "yuv420p",
                dst_path,
            ]
        )
    except FFmpegError:
        return None
    if not os.path.exists(dst_path) or os.path.getsize(dst_path) > _PROXY_MAX_BYTES:
        return None
    with open(dst_path, "rb") as fh:
        return fh.read()


_HQ_PROXY_MAX_BYTES = 120 * 1024 * 1024  # Files API allows ~2GB; keep upload fast for a <60s reel


def make_vision_proxy_hq(src_path: str, dst_path: str) -> str | None:
    """A HIGH-quality vision proxy for the Files API path (no 18MB inline cap): 720px wide, 10fps,
    WITH AUDIO. Unlike the 360p/8fps/no-audio inline proxy, this lets Gemini READ on-screen text,
    see fine effects, and hear pacing/emphasis — the depth that makes video understanding precise.
    Text-readability is RESOLUTION-bound (720p kept), not fps — Gemini samples video at ~1fps for
    understanding, so 10fps keeps the proxy small + fast to transcode/upload (deep critique must
    fit a sync request). `-t 240` bounds a pathological long upload; real reels are far shorter.
    Returns the proxy PATH (Files API uploads by path), or None on failure / oversize."""
    try:
        run_ff(
            [
                "ffmpeg", "-y", "-i", src_path,
                "-t", "240",
                "-vf", "scale=720:-2", "-r", "10",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                "-c:a", "aac", "-b:a", "96k",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                dst_path,
            ]
        )
    except FFmpegError:
        return None
    if not os.path.exists(dst_path) or os.path.getsize(dst_path) > _HQ_PROXY_MAX_BYTES:
        return None
    return dst_path

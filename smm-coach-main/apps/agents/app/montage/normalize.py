"""Mandatory input pre-pass: turn an arbitrary phone clip into a uniform,
constant-frame-rate 9:16 source the rest of the pipeline can trust.

This is load-bearing. Every timebase assumption, the two-timebase offset table,
and the concat filter all assume CFR + known fps + baked rotation + a present
audio stream. Phone clips are VFR, arbitrarily sized, rotated via metadata, and
sometimes have no audio. Normalize once; cut from the normalized file only.
"""
from __future__ import annotations

import os

from app.montage.probe import ClipInfo, probe_clip, run_ff


def _base_grade_vf() -> str:
    """Conservative 'correct-then-grade' pass (playbook Pillar 07): a gentle contrast +
    saturation lift (and, on medium, a mild S-curve) so flat, raw phone footage doesn't
    read as amateur. Returns a filter fragment ending in ',' (or '' when disabled).

    Runs ONCE here on the normalized clip, so BOTH the Shotstack source_url and the local
    ffmpeg ladder inherit the same grade. Deliberately GENTLE — over-grading (crushed
    shadows / neon skin) looks worse than none. Tunable: MONTAGE_BASE_GRADE = off|light|medium.
    """
    mode = os.getenv("MONTAGE_BASE_GRADE", "light").strip().lower()
    if mode == "off":
        return ""
    if mode == "medium":
        # eq bump + a mild S-curve for a graded 'pop' (deeper shadows, brighter highlights).
        return "eq=contrast=1.08:saturation=1.10:gamma=0.98,curves=preset=medium_contrast,"
    # light (default): a subtle correction only, no S-curve — safe on already-decent footage.
    return "eq=contrast=1.05:saturation=1.07:gamma=0.99,"


def normalize_clip(
    src_path: str,
    dst_path: str,
    *,
    target_w: int = 1080,
    target_h: int = 1920,
    fps: int = 30,
) -> ClipInfo:
    """Bake rotation, scale+pad to target 9:16 (no crop — letterbox rather than
    behead the speaker), force CFR fps, and guarantee a 48k stereo audio track
    (synthesize silence if the clip has none). Returns the normalized ClipInfo."""
    info = probe_clip(src_path)

    # scale to fit inside the frame, then pad to exact target (centered), then a gentle
    # baseline grade (once, so both render engines inherit it), then CFR + 8-bit output.
    vf = (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,{_base_grade_vf()}fps={fps},format=yuv420p"
    )

    cmd = ["ffmpeg", "-y", "-i", src_path]
    if not info.has_audio:
        # No audio stream — generate a silent one so cut/concat keeps A/V in lockstep.
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]

    cmd += [
        "-vf", vf,
        "-map", "0:v:0",
        "-map", ("1:a:0" if not info.has_audio else "0:a:0"),
        "-ar", "48000", "-ac", "2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        # `-fps_mode cfr` (the modern `-vsync cfr`): the deployed ffmpeg is 8.x, which REMOVED the
        # deprecated `-vsync` option → "Unrecognized option 'vsync'" → render failed. fps_mode is the
        # supported spelling (ffmpeg 5.1+); the whole pipeline assumes constant frame rate.
        "-fps_mode", "cfr", "-r", str(fps),
        "-movflags", "+faststart",
    ]
    if not info.has_audio:
        cmd += ["-shortest"]
    cmd += [dst_path]

    run_ff(cmd)
    return probe_clip(dst_path)

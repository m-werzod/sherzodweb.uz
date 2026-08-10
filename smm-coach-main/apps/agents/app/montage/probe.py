"""ffprobe / ffmpeg subprocess helpers shared by the montage compiler.

Every montage stage shells out to the GPL ffmpeg build verified by
`ffprobe_check`. These helpers centralize that so the rest of the package
never builds a raw subprocess call itself.
"""
from __future__ import annotations

import contextlib
import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ClipInfo:
    duration: float
    fps: float
    width: int
    height: int
    rotation: int
    has_audio: bool
    codec_name: str = ""  # video codec, e.g. "h264" / "hevc" — lets a remux copy h264


class FFmpegError(RuntimeError):
    """Non-zero ffmpeg/ffprobe exit — carries the tail of stderr for the log."""


def run_ff(cmd: list[str], *, timeout: float = 600.0) -> subprocess.CompletedProcess[str]:
    """Run an ffmpeg/ffprobe command. Raises FFmpegError on non-zero exit with
    the stderr tail so the worker can record a useful errorMessage."""
    proc = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-800:]
        raise FFmpegError(f"{cmd[0]} exit {proc.returncode}: {tail}")
    return proc


def _eval_rate(rate: str) -> float:
    """ffprobe reports fps as a fraction like '30000/1001'."""
    if not rate or rate in {"0/0", "N/A"}:
        return 0.0
    if "/" in rate:
        num, _, den = rate.partition("/")
        try:
            d = float(den)
            return float(num) / d if d else 0.0
        except ValueError:
            return 0.0
    try:
        return float(rate)
    except ValueError:
        return 0.0


def input_reject_reason(info: ClipInfo, *, max_pixels: int, max_seconds: float) -> str | None:
    """A user-facing rejection reason if a clip is too large to render/transcode
    safely, else None. Unbounded input resolution/duration is the real OOM lever
    (ffmpeg decode buffers scale with frame size; the whole clip is held while
    encoding), so we fail fast with a clear message instead of letting the encode
    get OOM-killed mid-flight."""
    if info.width <= 0 or info.height <= 0:
        return "Video oqimi topilmadi yoki o'qib bo'lmadi."
    if max_pixels > 0 and info.width * info.height > max_pixels:
        return f"Video o'lchami juda katta ({info.width}×{info.height}). 4K gacha qo'llab-quvvatlanadi."
    if max_seconds > 0 and info.duration > max_seconds:
        return f"Video juda uzun ({int(info.duration)}s). {int(max_seconds // 60)} daqiqagacha qo'llab-quvvatlanadi."
    return None


def probe_clip(path: str) -> ClipInfo:
    """Inspect a clip: duration, real fps, dimensions, rotation, audio presence.
    Rotation matters because phone clips carry it as side-data metadata — if we
    don't bake it in, every downstream geometry assumption is wrong."""
    out = run_ff(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", path,
        ],
        timeout=60,
    ).stdout
    data = json.loads(out)
    streams = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(data.get("format", {}).get("duration") or 0.0)

    if vstream is None:
        return ClipInfo(duration, 0.0, 0, 0, 0, has_audio)

    fps = _eval_rate(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0")
    width = int(vstream.get("width") or 0)
    height = int(vstream.get("height") or 0)
    codec_name = str(vstream.get("codec_name") or "")

    # Rotation can live in tags.rotate (legacy) or side_data_list (modern).
    rotation = 0
    tag_rot = vstream.get("tags", {}).get("rotate")
    if tag_rot is not None:
        try:
            rotation = int(tag_rot)
        except ValueError:
            rotation = 0
    for sd in vstream.get("side_data_list", []):
        if "rotation" in sd:
            with contextlib.suppress(ValueError, TypeError):
                rotation = int(sd["rotation"])
    return ClipInfo(duration, fps, width, height, rotation % 360, has_audio, codec_name)

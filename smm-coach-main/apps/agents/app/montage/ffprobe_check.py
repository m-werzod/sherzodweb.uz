"""Startup assertion that the montage ffmpeg toolchain is actually present.

The montage subsystem is dead without a full GPL ffmpeg build (see
infra/docker/agents.Dockerfile). Fail LOUD on boot rather than silently
producing broken renders. Run standalone after a deploy:

    python -m app.montage.ffprobe_check
"""
from __future__ import annotations

import shutil
import subprocess

import structlog

log = structlog.get_logger(__name__)

# Filters every montage stage depends on. Missing any => the build is wrong.
# Must mirror what the compiler ACTUALLY shells out — listing a filter the renderer
# never uses (zoompan/xfade/drawtext were dead) turns a complete GPL build into a
# false INCOMPLETE deploy-blocker, while giving false confidence about unused ones.
REQUIRED_FILTERS = (
    "ass",  # burned captions (libass)
    "loudnorm",  # two-pass loudness normalization to -14 LUFS
    "sidechaincompress",  # duck music under the voice
    "afftdn",  # FFT denoise of the voice track
    "deesser",  # tame sibilance
    "concat",  # join the kept cuts
    "scale",  # normalize + proxy resize
    "crop",  # animated centered crop = punch-in motion (motion.py, NOT zoompan)
    "overlay",  # broll / hook / title compositing
    "setpts",  # speed ramps / retiming
)


def missing_filters() -> list[str]:
    """Return the required filters NOT present in the installed ffmpeg, or raise
    FileNotFoundError if ffmpeg itself is absent."""
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError("ffmpeg not on PATH")
    out = subprocess.run(  # noqa: S603
        ["ffmpeg", "-hide_banner", "-filters"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # Each filter line looks like ` ... ass  V->V  ...`; match the token column.
    available = {
        parts[1]
        for line in out.splitlines()
        if len(parts := line.split()) >= 2
    }
    return [f for f in REQUIRED_FILTERS if f not in available]


def assert_toolchain() -> bool:
    """Log one structured line; return True iff the toolchain is complete.
    Never raises in the boot path — a degraded service is better than a crash
    loop, and the montage worker re-checks before each render."""
    try:
        missing = missing_filters()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        log.error("montage.ffmpeg_missing", error=str(exc))
        return False
    if missing:
        log.error("montage.ffmpeg_filters_missing", missing=missing)
        return False
    log.info("montage.ffmpeg_ok", filters=len(REQUIRED_FILTERS))
    return True


if __name__ == "__main__":
    import sys

    ok = assert_toolchain()
    print("montage ffmpeg toolchain:", "OK" if ok else "INCOMPLETE")  # noqa: T201
    sys.exit(0 if ok else 1)

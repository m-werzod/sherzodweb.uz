"""Tests for the montage/transcode input guard — reject oversized clips before
any encode (unbounded resolution/duration is the real OOM lever)."""
from __future__ import annotations

from app.montage.probe import ClipInfo, input_reject_reason

_LIM = {"max_pixels": 3840 * 2160, "max_seconds": 1200.0}


def _info(w: int, h: int, dur: float = 10.0) -> ClipInfo:
    return ClipInfo(duration=dur, fps=30.0, width=w, height=h, rotation=0, has_audio=True)


def test_accepts_normal_reel() -> None:
    assert input_reject_reason(_info(1080, 1920, 60), **_LIM) is None


def test_rejects_missing_video_stream() -> None:
    r = input_reject_reason(_info(0, 0), **_LIM)
    assert r is not None and "oqim" in r.lower()


def test_rejects_oversized_resolution() -> None:
    r = input_reject_reason(_info(7680, 4320, 10), **_LIM)  # 8K
    assert r is not None and "4K" in r


def test_rejects_too_long() -> None:
    r = input_reject_reason(_info(1080, 1920, 5000), **_LIM)
    assert r is not None and "uzun" in r.lower()


def test_boundary_exactly_at_limit_is_ok() -> None:
    assert input_reject_reason(_info(3840, 2160, 1200), **_LIM) is None


def test_disabled_limits_accept_anything() -> None:
    assert input_reject_reason(_info(7680, 4320, 9999), max_pixels=0, max_seconds=0) is None

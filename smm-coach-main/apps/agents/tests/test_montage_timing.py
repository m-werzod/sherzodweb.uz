"""Deterministic timing logic — silence inversion, coverage, caption windows.
These are the license-free MVP's brain; ffmpeg-dependent pieces are smoke-tested
in the deployed container, not here."""
from __future__ import annotations

import pytest

from app.montage.captions import _ass_time
from app.montage.compiler import coverage_ok
from app.montage.edl import EDL, Source
from app.montage.timing import build_caption_windows, build_cuts, speech_coverage


def test_build_cuts_inverts_silences() -> None:
    cuts = build_cuts(12.0, [(3.0, 5.0), (9.0, 10.0)])
    # speech [0,3] [5,9] [10,12], padded 0.08 outward.
    assert len(cuts) == 3
    assert cuts[0].src_start == pytest.approx(0.0)
    assert cuts[0].src_end == pytest.approx(3.08)
    assert cuts[1].src_start == pytest.approx(4.92)
    assert cuts[-1].src_end == pytest.approx(12.0)


def test_build_cuts_no_silence_keeps_whole_clip() -> None:
    cuts = build_cuts(10.0, [])
    assert len(cuts) == 1
    assert cuts[0].src_start == 0.0
    assert cuts[0].src_end == pytest.approx(10.0)


def test_build_cuts_all_silent_falls_back_to_whole_clip() -> None:
    # One silence spanning the entire clip → never produce an empty timeline.
    cuts = build_cuts(8.0, [(0.0, 8.0)])
    assert len(cuts) == 1
    assert cuts[0].src_end == pytest.approx(8.0)


def test_build_cuts_drops_sub_threshold_blips() -> None:
    # A 0.1s speech sliver between two silences is below min_keep (0.20).
    cuts = build_cuts(10.0, [(0.0, 4.95), (5.05, 10.0)], pad=0.0)
    assert cuts == [] or all((c.src_end - c.src_start) >= 0.20 for c in cuts)


def test_speech_coverage_ratio() -> None:
    cuts = build_cuts(10.0, [(4.0, 8.0)], pad=0.0)  # keep [0,4]+[8,10] = 6s
    assert speech_coverage(cuts, 10.0) == pytest.approx(0.6)


@pytest.mark.parametrize(
    ("sec", "want"),
    [(0.0, "0:00:00.00"), (65.5, "0:01:05.50"), (3661.05, "1:01:01.05")],
)
def test_ass_time_format(sec: float, want: str) -> None:
    assert _ass_time(sec) == want


def test_caption_windows_distribute_across_output() -> None:
    cuts = build_cuts(10.0, [])  # 10s output
    script = [{"text": "bir ikki uch tort besh olti yetti sakkiz toqqiz oʻn"}]
    caps = build_caption_windows(cuts, script, words_per_window=5)
    # Width/boundary-aware grouping (≤5 words/window, never overflowing one line) → 2+ windows.
    assert len(caps.windows) >= 2
    assert all(len(win.words) <= 5 for win in caps.windows)
    first = caps.windows[0].words
    assert first[0].text == "bir"
    assert first[0].start == pytest.approx(0.0)
    # last word ends at ~output duration.
    assert caps.windows[-1].words[-1].end == pytest.approx(10.0, abs=0.05)
    # apostrophe normalized in the caption text.
    assert caps.windows[-1].words[-1].text == "o'n"


def _edl_with_output(seconds: float) -> EDL:
    cuts = build_cuts(seconds, [])
    return EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"), cuts=cuts)


def test_coverage_gate_rejects_too_short_clip() -> None:
    ok, reason = coverage_ok(_edl_with_output(2.0), [{"text": "salom dunyo"}])
    assert not ok
    assert "qisqa" in reason.lower()


def test_coverage_gate_lenient_on_short_clip_vs_long_script() -> None:
    # Captions are pace-capped, so a clip shorter than the script still renders
    # (a readable montage of what was said) — no longer rejected for "coverage".
    script = [{"text": " ".join(["soz"] * 200)}]  # long script
    ok, _ = coverage_ok(_edl_with_output(8.0), script)
    assert ok


def test_caption_words_follow_real_speech_times() -> None:
    cuts = build_cuts(5.0, [])
    script = [{"text": "bir ikki uch tort"}]  # 4 words
    # Real per-word end times (output seconds) from a transcript.
    caps = build_caption_windows(
        cuts, script, words_per_window=4, word_out_times=[1.0, 2.0, 3.0, 4.0, 5.0]
    )
    w = caps.windows[0].words
    # Words land on the real cadence, not an even 1.25s spread.
    assert w[0].end == 1.0
    assert w[1].end == 2.0
    assert w[-1].end <= 5.0
    # monotonic
    assert all(w[i].end <= w[i + 1].end for i in range(len(w) - 1))


def test_real_times_fallback_to_char_weighted_when_absent() -> None:
    cuts = build_cuts(6.0, [])
    script = [{"text": "bir ikki uch"}]
    caps = build_caption_windows(cuts, script, words_per_window=3, word_out_times=None)
    # No transcript alignment → CHAR-weighted spread (palmier distribute): bir/uch=3 chars,
    # ikki=4 → total 10 → bir gets 6×3/10 = 1.8s (not an even 2.0s).
    assert caps.windows[0].words[0].end == pytest.approx(1.8)


def test_caption_words_capped_to_clip_length() -> None:
    cuts = build_cuts(5.0, [])  # 5s output
    script = [{"text": " ".join([f"w{i}" for i in range(100)])}]  # 100 words
    caps = build_caption_windows(cuts, script, words_per_window=3)
    total = sum(len(win.words) for win in caps.windows)
    assert total <= int(5.0 * 2.8) + 1  # ~14 words shown, not all 100

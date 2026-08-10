"""Caption WINDOW grouping (Faza palmier-#3). Pins the boundary/width/min-duration logic that
replaced blind 3-word chunking — the failure modes were: windows straddling sentence breaks,
long Uzbek words overflowing to a 2nd line (breaking karaoke), and sub-250ms flashes."""
from __future__ import annotations

from app.montage.edl import EDL, CaptionStyle, Cut, Source
from app.montage.timing import (
    _enforce_min_window,
    _fits_one_line,
    build_caption_windows,
    build_caption_windows_from_transcript,
)

# A small font for the GROUPING tests so the width test never pre-empts the boundary logic under
# scrutiny (the shipped default is a big heavy face — size is exercised separately below).
_SMALL = CaptionStyle(size=64)


def _cuts(dur: float) -> list[Cut]:
    return [Cut(src_start=0.0, src_end=dur)]


def _texts(caps) -> list[str]:
    return [" ".join(w.text for w in win.words) for win in caps.windows]


def test_window_closes_on_sentence_boundary() -> None:
    caps = build_caption_windows(_cuts(20), [{"text": "salom dunyo. yangi gap keldi"}], words_per_window=3)
    # "dunyo." ends a sentence → window closes there, even though it's only 2 words.
    assert _texts(caps)[0] == "salom dunyo."
    assert _texts(caps)[1] == "yangi gap keldi"


def test_clause_boundary_closes_when_two_plus_words() -> None:
    caps = build_caption_windows(
        _cuts(20), [{"text": "birinchi ikkinchi, uchinchi"}], words_per_window=3, style=_SMALL
    )
    assert _texts(caps)[0] == "birinchi ikkinchi,"


def test_long_words_never_overflow_one_line() -> None:
    style = CaptionStyle()  # size 96
    caps = build_caption_windows(
        _cuts(20), [{"text": "mutaxassisligimni tashkilotchilik mas'uliyatim"}], words_per_window=3, style=style
    )
    for win in caps.windows:
        text = " ".join(w.text for w in win.words)
        # Either it fits one line, or it's a lone over-long word (kept, can't be split).
        assert _fits_one_line(text, style.size, 1080, style.margin_lr) or len(win.words) == 1


def test_max_words_cap_respected() -> None:
    caps = build_caption_windows(_cuts(30), [{"text": "bir ikki uch tort besh olti yetti"}], words_per_window=3)
    assert all(len(win.words) <= 3 for win in caps.windows)


def test_decimal_and_abbrev_not_split_as_sentences() -> None:
    # "3.14" / "U.S." have '.' NOT followed by a space → must NOT trigger a window break.
    caps = build_caption_windows(_cuts(20), [{"text": "narx 3.14 dollar"}], words_per_window=3)
    assert _texts(caps) == ["narx 3.14 dollar"]


def test_single_over_long_word_kept_alone() -> None:
    style = CaptionStyle()
    long_word = "a" * 60  # far past one line at font 96
    caps = build_caption_windows(_cuts(10), [{"text": f"{long_word} keyin"}], words_per_window=3, style=style)
    assert caps.windows[0].words[0].text == long_word
    assert len(caps.windows[0].words) == 1


def test_emphasis_pop_flag() -> None:
    caps = build_caption_windows(
        _cuts(20), [{"text": "oddiy MUHIM oddiy"}], words_per_window=3, emphasis_words=["muhim"]
    )
    flags = {w.text: w.pop for win in caps.windows for w in win.words}
    assert flags["MUHIM"] is True
    assert flags["oddiy"] is False


def test_transcript_emphasis_pop_inside_multiword_segment() -> None:
    # On the primary transcript+script path, fewer Whisper slots than script words → each CaptionWord
    # is a MULTI-word segment. The emphasis pop must fire when an emphasis word is ANY token of the
    # segment; the old whole-segment key ("sirkeyin") never matched a single emphasis key → pop dead.
    edl = EDL(
        task_id="t", tenant_id="x",
        source=Source(upload_key="k", duration_sec=10.0),
        cuts=[Cut(src_start=0.0, src_end=10.0)],  # identity source→output
    )
    transcript = [
        {"text": "aa", "start": 0.0, "end": 1.0},
        {"text": "bb", "start": 1.0, "end": 2.0},
        {"text": "cc", "start": 2.0, "end": 3.0},
    ]
    caps = build_caption_windows_from_transcript(
        edl, transcript, words_per_window=4,
        script_words=["juda", "muhim", "sir", "keyin", "yana", "gap"],
        emphasis_words=["sir"],
    )
    flags = {w.text: w.pop for win in caps.windows for w in win.words}
    assert flags.get("sir keyin") is True   # emphasis token inside the multi-word segment pops
    assert flags.get("juda muhim") is False
    assert flags.get("yana gap") is False


def test_enforce_min_window_floors_and_shifts() -> None:
    # three 1-word windows of 0.2s each → each must end up >= 0.5s, no overlap.
    starts = [0.0, 0.2, 0.4]
    ends = [0.2, 0.4, 0.6]
    groups = [[0], [1], [2]]
    _enforce_min_window(starts, ends, groups, out_dur=10.0)
    assert ends[0] - starts[0] >= 0.5 - 1e-6
    assert starts[1] >= ends[0] - 1e-6
    assert ends[1] - starts[1] >= 0.5 - 1e-6
    assert starts[2] >= ends[1] - 1e-6


def test_min_window_clamps_to_out_dur() -> None:
    # No room to extend past the timeline → tail clamps to out_dur, never shows after the video.
    starts = [0.0, 0.2]
    ends = [0.2, 0.4]
    groups = [[0], [1]]
    _enforce_min_window(starts, ends, groups, out_dur=0.6)
    assert ends[-1] <= 0.6 + 1e-6
    assert starts[-1] <= 0.6 + 1e-6

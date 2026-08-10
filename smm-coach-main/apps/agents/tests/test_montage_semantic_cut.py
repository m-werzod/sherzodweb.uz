"""Semantic stumble-cut guards (Stage 9b Faza 2). The Whisper call is container-tested; here we pin
the two PURE pieces that decide what gets cut:
  * align_script_to_transcript — filler + immediate repeats + (alignment-gated) off-script runs,
    high-precision so it never blades good speech on unreliable Uzbek transcripts.
  * subtract_spans — duration-CHANGING removal of SOURCE ranges from the kept cuts, with a min-keep
    floor and shot-linkage preserved.
"""
from __future__ import annotations

from app.montage.edl import EDL, Cut, Source
from app.montage.timing import (
    _is_filler,
    align_script_to_transcript,
    build_caption_windows_from_transcript,
    subtract_spans,
)


def _w(text: str, start: float, end: float) -> dict:
    return {"text": text, "start": start, "end": end}


# --- _is_filler ---------------------------------------------------------------------------------


def test_filler_recognises_hesitations() -> None:
    assert _is_filler("eee") and _is_filler("aaa") and _is_filler("mmm") and _is_filler("hmm")
    assert _is_filler("yani") and _is_filler("короче")


def test_filler_rejects_real_words() -> None:
    assert not _is_filler("salom") and not _is_filler("men") and not _is_filler("biznes")
    assert not _is_filler("")  # empty key is never filler


# --- align_script_to_transcript -----------------------------------------------------------------


def _script(*lines: str) -> list[dict]:
    return [{"text": ln} for ln in lines]


def test_too_short_transcript_returns_nothing() -> None:
    assert align_script_to_transcript([_w("salom", 0, 1)], _script("salom")) == []


def test_filler_token_is_dropped() -> None:
    words = [_w("men", 0.0, 0.4), _w("eee", 0.4, 0.9), _w("biznes", 0.9, 1.4), _w("haqida", 1.4, 1.9)]
    drops = align_script_to_transcript(words, _script("men biznes haqida"))
    assert (0.4, 0.9) in drops  # the 'eee' hesitation span


def test_immediate_repeat_drops_earlier_take() -> None:
    # "men men biznes ..." → drop the FIRST 'men' (stutter), keep the retake.
    words = [_w("men", 0.0, 0.4), _w("men", 0.4, 0.8), _w("biznes", 0.8, 1.2), _w("ochaman", 1.2, 1.7)]
    drops = align_script_to_transcript(words, _script("men biznes ochaman"))
    assert (0.0, 0.4) in drops
    assert (0.4, 0.8) not in drops  # the second (clean) take is kept


def test_clean_take_yields_no_drops() -> None:
    words = [_w("men", 0, 0.4), _w("biznes", 0.4, 0.9), _w("haqida", 0.9, 1.4), _w("gapiraman", 1.4, 2.0)]
    assert align_script_to_transcript(words, _script("men biznes haqida gapiraman")) == []


def test_offscript_run_dropped_only_between_anchors_with_good_alignment() -> None:
    # Script: "men biznes haqida gapiraman". Transcript matches it but inserts a 4-token off-script
    # ramble between 'biznes' and 'haqida' → that run is dropped (forgot the line, rambled, resumed).
    words = [
        _w("men", 0.0, 0.4), _w("biznes", 0.4, 0.9),
        _w("qalesiz", 0.9, 1.3), _w("bugun", 1.3, 1.7), _w("havo", 1.7, 2.1), _w("issiq", 2.1, 2.5),
        _w("haqida", 2.5, 3.0), _w("gapiraman", 3.0, 3.6),
    ]
    drops = align_script_to_transcript(words, _script("men biznes haqida gapiraman"))
    # the off-script run [0.9, 2.5] is removed
    assert any(s <= 0.9 and e >= 2.5 for s, e in drops)


def test_offscript_skipped_when_alignment_poor() -> None:
    # Transcript shares almost nothing with the script (uz Whisper garbled it) → never drop content.
    words = [_w("xyz", 0, 0.4), _w("qwe", 0.4, 0.8), _w("rty", 0.8, 1.2), _w("asd", 1.2, 1.6), _w("zxc", 1.6, 2.0)]
    assert align_script_to_transcript(words, _script("men biznes haqida gapiraman")) == []


# --- subtract_spans -----------------------------------------------------------------------------


def test_subtract_no_spans_is_identity() -> None:
    cuts = [Cut(src_start=0.0, src_end=5.0)]
    assert subtract_spans(cuts, []) is cuts


def test_subtract_splits_straddling_cut() -> None:
    cuts = [Cut(src_start=0.0, src_end=5.0, shot_index=2, script_text="x")]
    out = subtract_spans(cuts, [(2.0, 3.0)])
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 2.0), (3.0, 5.0)]
    assert all(c.shot_index == 2 and c.script_text == "x" for c in out)  # linkage preserved


def test_subtract_drops_fully_covered_and_tiny_fragments() -> None:
    cuts = [Cut(src_start=0.0, src_end=2.0), Cut(src_start=2.0, src_end=4.0)]
    # remove all of cut 1, and shave cut 0 down to a 0.1s sliver (< the 0.20 min_keep).
    out = subtract_spans(cuts, [(0.1, 2.0), (2.0, 4.0)])
    assert out == []  # the sub-min_keep sliver of cut 0 is discarded, cut 1 fully removed


def test_subtract_merges_overlapping_drop_spans() -> None:
    cuts = [Cut(src_start=0.0, src_end=10.0)]
    out = subtract_spans(cuts, [(2.0, 4.0), (3.0, 5.0)])  # overlap → merged to [2,5]
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 2.0), (5.0, 10.0)]


# --- transcript captions (the "subtitles must match my mouth" fix) ------------------------------


def _edl_caps(cuts: list[tuple[float, float]]) -> EDL:
    return EDL(
        task_id="t", tenant_id="x", source=Source(upload_key="k", duration_sec=10.0),
        cuts=[Cut(src_start=a, src_end=b) for a, b in cuts],
    )


def test_captions_use_the_real_transcript_words() -> None:
    edl = _edl_caps([(0.0, 5.0)])
    tr = [
        {"text": "salom", "start": 0.0, "end": 0.5},
        {"text": "dunyo", "start": 0.6, "end": 1.1},
        {"text": "qalaysan", "start": 1.2, "end": 1.8},
    ]
    caps = build_caption_windows_from_transcript(edl, tr)
    words = [w.text for win in caps.windows for w in win.words]
    assert words == ["salom", "dunyo", "qalaysan"]  # the ACTUAL spoken words, not the script


def test_captions_drop_words_inside_a_cut_gap() -> None:
    # The cut removes SOURCE 2–4s; a word spoken at 3.0 (a stumble that got cut) must NOT caption.
    edl = _edl_caps([(0.0, 2.0), (4.0, 6.0)])
    tr = [
        {"text": "bir", "start": 0.5, "end": 1.0},
        {"text": "eee", "start": 3.0, "end": 3.5},  # in the removed gap
        {"text": "ikki", "start": 4.5, "end": 5.0},
    ]
    caps = build_caption_windows_from_transcript(edl, tr)
    words = [w.text for win in caps.windows for w in win.words]
    assert words == ["bir", "ikki"]  # the cut-out word is gone


def test_captions_map_to_post_cut_output_time() -> None:
    # 'ikki' is at SOURCE 4.5 but, after the 2s gap is cut, sits at OUTPUT 2.5.
    edl = _edl_caps([(0.0, 2.0), (4.0, 6.0)])
    caps = build_caption_windows_from_transcript(edl, [
        {"text": "bir", "start": 0.5, "end": 1.0},
        {"text": "ikki", "start": 4.5, "end": 5.0},
    ])
    last = caps.windows[-1].words[-1]
    assert last.text == "ikki" and abs(last.start - 2.5) < 0.05

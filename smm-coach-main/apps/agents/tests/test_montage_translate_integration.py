"""Lokalizatsiya integration — translate gating (compile_and_render) + meta reader (worker) +
caption-window redistribution (pure). No network."""
from __future__ import annotations

from app.montage.compiler import _maybe_add_translate_variants, _redistribute_caption_windows
from app.montage.edl import EDL, CaptionWindow, CaptionWord, Source
from app.workers.montage_worker import _translate_langs_from_meta


def _edl() -> EDL:
    return EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))


def test_translate_skipped_when_disabled_or_no_langs() -> None:
    # ENABLE_VIDEO_TRANSLATE defaults off, and a missing file → upload short-circuits — no variant, no network.
    e = _edl()
    _maybe_add_translate_variants(e, "/nope.mp4", ["ru", "en"], task_id="t")
    assert e.lang_variants == []
    _maybe_add_translate_variants(e, "/nope.mp4", [], task_id="t")
    assert e.lang_variants == []
    _maybe_add_translate_variants(e, "/nope.mp4", ["  "], task_id="t")
    assert e.lang_variants == []


def test_translate_langs_from_meta_reads_list_and_string() -> None:
    assert _translate_langs_from_meta({"translateLangs": ["RU", "en"]}) == ["ru", "en"]
    assert _translate_langs_from_meta({"translateLangs": "ru, en ,uz"}) == ["ru", "en", "uz"]
    assert _translate_langs_from_meta('{"translateLangs":["ru"]}') == ["ru"]


def test_translate_langs_from_meta_absent_or_blank_is_empty() -> None:
    assert _translate_langs_from_meta({"translateLangs": []}) == []
    assert _translate_langs_from_meta({"translateLangs": "  "}) == []
    assert _translate_langs_from_meta({}) == []
    assert _translate_langs_from_meta("not json") == []
    assert _translate_langs_from_meta(None) == []


def _win(words: list[tuple[str, float, float]]) -> CaptionWindow:
    return CaptionWindow(words=[CaptionWord(text=t, start=s, end=e) for t, s, e in words])


def test_redistribute_evenly_across_window_span() -> None:
    # Asl oyna [2,5] (3s), tarjima "bir ikki" → 2 so'z teng: [2,3.5] va [3.5,5].
    w = _win([("hello", 2.0, 3.0), ("world", 3.0, 5.0)])
    out = _redistribute_caption_windows([w], ["bir ikki"])
    assert len(out) == 1
    ws = out[0].words
    assert [x.text for x in ws] == ["bir", "ikki"]
    assert ws[0].start == 2.0
    assert abs(ws[0].end - 3.5) < 1e-9
    assert abs(ws[1].start - 3.5) < 1e-9
    assert ws[1].end == 5.0


def test_redistribute_keeps_original_on_blank_or_invalid() -> None:
    w = _win([("hello", 2.0, 5.0)])
    # bo'sh tarjima → asl saqlanadi
    assert _redistribute_caption_windows([w], [""])[0].words[0].text == "hello"
    assert _redistribute_caption_windows([w], ["   "])[0].words[0].text == "hello"
    # so'zsiz oyna → o'zgarmaydi
    empty = CaptionWindow(words=[])
    assert _redistribute_caption_windows([empty], ["matn"])[0].words == []


def test_redistribute_preserves_window_count() -> None:
    wins = [_win([("a", 0.0, 1.0)]), _win([("b", 1.0, 2.0)])]
    out = _redistribute_caption_windows(wins, ["bitta", "ikkitta uchta"])
    assert len(out) == 2
    assert [x.text for x in out[1].words] == ["ikkitta", "uchta"]

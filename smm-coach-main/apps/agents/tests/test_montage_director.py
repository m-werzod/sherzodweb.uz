"""Faza A4 Slice 2 — montage_director.normalize_intents: LLM JSON → tekshirilgan effectIntent dict'lar.
PURE (LLM/DB kerak emas). Noma'lum intent/shot, dup, yaroqsiz JSON, strength clamp qulflanadi."""
from __future__ import annotations

from app.graphs.nodes.montage_director import normalize_intents


def test_valid_intents_kept() -> None:
    raw = (
        '{"intents":[{"shot_index":1,"intent":"zoom","intensity":"high","params":{}},'
        '{"shot_index":2,"intent":"text_pop","intensity":"med","params":{"text":"YANGI"}}]}'
    )
    assert normalize_intents(raw, {1, 2, 3}) == [
        {"shot_index": 1, "intent": "zoom", "strength": "high", "params": {}},
        {"shot_index": 2, "intent": "text_pop", "strength": "med", "params": {"text": "YANGI"}},
    ]


def test_unknown_intent_and_invalid_shot_dropped() -> None:
    raw = '{"intents":[{"shot_index":1,"intent":"explode"},{"shot_index":9,"intent":"zoom"}]}'
    assert normalize_intents(raw, {1, 2}) == []  # explode noma'lum, shot 9 valid emas


def test_intensity_clamped_and_strength_alias() -> None:
    raw = (
        '{"intents":[{"shot_index":1,"intent":"vfx","intensity":"EXTREME"},'
        '{"shot_index":2,"intent":"zoom","strength":"low"}]}'
    )
    out = normalize_intents(raw, {1, 2})
    assert out[0]["strength"] == "med"  # noma'lum intensity → med
    assert out[1]["strength"] == "low"  # strength aliasi qabul qilinadi


def test_duplicate_shot_dropped() -> None:
    raw = '{"intents":[{"shot_index":1,"intent":"zoom"},{"shot_index":1,"intent":"vfx"}]}'
    out = normalize_intents(raw, {1})
    assert len(out) == 1
    assert out[0]["intent"] == "zoom"  # birinchisi qoladi


def test_bad_json_or_shape_returns_empty() -> None:
    assert normalize_intents("not json", {1}) == []
    assert normalize_intents('{"intents":"nope"}', {1}) == []
    assert normalize_intents('{"other":[]}', {1}) == []
    assert normalize_intents("[]", {1}) == []  # dict emas


def test_params_non_dict_coerced_to_empty() -> None:
    raw = '{"intents":[{"shot_index":1,"intent":"zoom","params":"bad"}]}'
    assert normalize_intents(raw, {1})[0]["params"] == {}


def test_normalize_uses_recipe_default_strength() -> None:
    # No intensity in the LLM output → falls back to the trend recipe's default (passed in).
    out = normalize_intents('{"intents":[{"shot_index":1,"intent":"zoom"}]}', {1}, "high")
    assert out[0]["strength"] == "high"


def test_heuristic_intents_covers_all_shots():
    from app.graphs.nodes.montage_director import heuristic_intents
    out = heuristic_intents({0, 1, 2, 3, 4}, "med")
    assert len(out) == 5
    assert {o["shot_index"] for o in out} == {0, 1, 2, 3, 4}
    # every 3rd shot (index 2 in sorted order) is a vfx accent; rest are zoom
    assert out[2]["intent"] == "vfx"
    assert out[0]["intent"] == "zoom" and out[1]["intent"] == "zoom"
    assert all(o["strength"] == "med" for o in out)


def test_heuristic_intents_empty_and_strength_clamp():
    from app.graphs.nodes.montage_director import heuristic_intents
    assert heuristic_intents(set()) == []
    out = heuristic_intents({0}, "bogus")
    assert out[0]["strength"] == "med"  # invalid strength clamps to med


def test_parse_director_response_full():
    import json as _json

    from app.graphs.nodes.montage_director import parse_director_response
    raw = _json.dumps({
        "intents": [{"shot_index": 1, "intent": "transition", "intensity": "med", "params": {"type": "zoom"}}],
        "music_hint": "upbeat electronic, 120bpm",
        "unwanted": ["stol ustidagi chiqindi", "  ", "begona odam"],
        "face_zone": "TOP",
    })
    intents, music, unwanted, face_zone = parse_director_response(raw, {1, 2})
    assert intents[0]["params"]["type"] == "zoom"
    assert music == "upbeat electronic, 120bpm"
    assert unwanted == ["stol ustidagi chiqindi", "begona odam"]
    assert face_zone == "top"  # case-normalized


def test_parse_director_response_bad_json():
    from app.graphs.nodes.montage_director import parse_director_response
    assert parse_director_response("nope", {1}) == ([], "", [], "")


def test_parse_director_response_junk_face_zone_ignored():
    import json as _json

    from app.graphs.nodes.montage_director import parse_director_response
    raw = _json.dumps({"intents": [], "face_zone": "left-ish"})
    _, _, _, face_zone = parse_director_response(raw, {1})
    assert face_zone == ""  # unknown zone -> empty -> default layout downstream


def test_face_layouts_avoid_the_face():
    # The whole point: no text/card layer may sit in the zone the face occupies.
    from app.montage.shotstack_map import _LAYOUTS, _caption_margin_top, _layout
    for zone, lay in _LAYOUTS.items():
        for element, (pos, _off) in lay.items():
            assert pos != zone or zone == "center", (zone, element, pos)
    # Unknown/None zone falls back to the edge-hugging center layout.
    assert _layout(None) == _LAYOUTS["center"]
    assert _layout("weird") == _LAYOUTS["center"]
    # Caption margin.top: OUTSIDE the face zone AND inside the platform-safe band [0.55, 0.78]
    # (below 0.78 is the app UI dead-zone — a caption there collides with Instagram's own chrome).
    assert 0.55 <= _caption_margin_top("top") <= 0.78  # face above -> captions low but safe
    assert _caption_margin_top("bottom") <= 0.2  # face below -> captions high (below top dead-zone)
    assert _caption_margin_top(None) == _caption_margin_top("center") <= 0.78


def test_transcript_captions_show_script_text_at_real_times():
    # Whisper timing + SCRIPT text: mangled transcript words are replaced by the
    # script's words, in order, on the real speech slots.
    from app.montage.edl import EDL, Cut, Source
    from app.montage.timing import build_caption_windows_from_transcript
    edl = EDL(
        task_id="t", tenant_id="x",
        source=Source(upload_key="k", duration_sec=6.0),
        cuts=[Cut(src_start=0.0, src_end=6.0, shot_index=1)],
    )
    transcript = [
        {"text": "trederləri", "start": 0.0, "end": 0.5},
        {"text": "üçün", "start": 0.5, "end": 1.0},
        {"text": "yənəbid", "start": 1.0, "end": 1.5},
        {"text": "dalayır", "start": 1.5, "end": 2.0},
    ]
    caps = build_caption_windows_from_transcript(
        edl, transcript, script_words=["treyderlar", "uchun", "yangi", "loyiha"],
    )
    shown = [w.text for win in caps.windows for w in win.words]
    assert shown == ["treyderlar", "uchun", "yangi", "loyiha"]
    first = caps.windows[0].words[0]
    assert first.start == 0.0 and first.end == 0.5  # REAL speech slot kept


def test_render_ass_face_zone_moves_captions():
    import os
    import tempfile

    from app.montage.captions import render_ass
    from app.montage.edl import Captions
    caps = Captions()
    with tempfile.TemporaryDirectory() as td:
        with open(render_ass(caps, os.path.join(td, "t.ass"), face_zone="bottom"), encoding="utf-8") as f:
            top = f.read()
        with open(render_ass(caps, os.path.join(td, "b.ass"), face_zone="top"), encoding="utf-8") as f:
            bot = f.read()
    # face at bottom -> captions anchored top-center (alignment 8); face top -> bottom (2).
    # MarginV clears the platform UI dead-zone (top >=260, bottom >=420).
    assert ",8,80,80,300,1" in top
    assert ",2,80,80,430,1" in bot


def test_hook_display_dur_is_content_aware():
    from app.montage.compiler import _hook_display_dur
    from app.montage.edl import EDL, Captions, CaptionWindow, CaptionWord, Source
    edl = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))
    # opening chunks: window ending at 2.8s spans the 2.5s target → hook stays up to 2.8s
    edl.captions = Captions(windows=[
        CaptionWindow(words=[CaptionWord(text="a", start=0.0, end=1.2)]),
        CaptionWindow(words=[CaptionWord(text="b", start=1.2, end=2.8)]),
        CaptionWindow(words=[CaptionWord(text="c", start=2.8, end=4.0)]),
    ])
    assert _hook_display_dur(edl) == 2.8
    # a very long opening chunk is clamped to the readable ceiling
    edl.captions = Captions(windows=[CaptionWindow(words=[CaptionWord(text="x", start=0.0, end=9.0)])])
    assert _hook_display_dur(edl) == 3.2
    # no windows → the EDL default is kept
    edl.captions = Captions(windows=[])
    assert _hook_display_dur(edl) == edl.hook.display_dur


def test_rehook_interrupts_on_longer_reels():
    from app.montage.compiler import _apply_rehook_beats
    from app.montage.edl import EDL, Cut, Source
    # short reel (< 18s) → no re-hook
    short = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k", duration_sec=12.0),
                cuts=[Cut(src_start=0.0, src_end=12.0, shot_index=1)])
    # long reel (~35s) → re-hook punches at 15 and 30
    long = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k", duration_sec=35.0),
               cuts=[Cut(src_start=0.0, src_end=35.0, shot_index=1)])
    _apply_rehook_beats(short)
    _apply_rehook_beats(long)
    assert not any(m.op == "zoom_punch" and m.at_sec in (15.0, 30.0) for m in short.motion)
    long_beats = sorted(m.at_sec for m in long.motion if m.op == "zoom_punch")
    assert long_beats == [15.0, 30.0]
    assert sorted(s.at_sec for s in long.audio.sfx if s.type == "whoosh") == [15.0, 30.0]

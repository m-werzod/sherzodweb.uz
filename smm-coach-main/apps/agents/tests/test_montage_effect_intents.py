"""Faza A4 — resolve_effect_intents: rejalashtirilgan EffectIntent'lar EDL render-lane'lariga.
PURE pass (media kerak emas). shot_index → OUTPUT joylash + har intent turining lane'ga mapping'i
qulflanadi. Bo'sh ro'yxat byte-bir xil no-op (build_edl `if effect_intents:` guard'i shunga tayanadi).
"""
from __future__ import annotations

from app.montage.edl import EDL, Cut, EffectIntent, Source
from app.montage.effects import resolve_effect_intents


def _edl() -> EDL:
    # OUTPUT: shot1 [0,5), shot2 [5,11). total 11.
    return EDL(
        task_id="t",
        tenant_id="x",
        source=Source(upload_key="k"),
        cuts=[Cut(src_start=0, src_end=5, shot_index=1), Cut(src_start=10, src_end=16, shot_index=2)],
    )


def test_empty_intents_is_byte_identical_noop() -> None:
    e = _edl()
    before = e.model_dump()
    resolve_effect_intents(e, [])
    assert e.model_dump() == before


def test_zoom_intent_appends_motion_at_shot_window() -> None:
    e = _edl()
    resolve_effect_intents(e, [EffectIntent(shot_index=2, intent="zoom", strength="high")])
    assert len(e.motion) == 1
    m = e.motion[0]
    assert m.op == "zoom_punch"
    assert m.at_sec == 5.0  # shot 2 OUTPUT start
    assert m.to_scale == 1.20  # high strength


def test_vfx_intent_maps_to_shake_or_glitch() -> None:
    e = _edl()
    resolve_effect_intents(
        e,
        [
            EffectIntent(shot_index=1, intent="vfx", params={"op": "shake"}),
            EffectIntent(shot_index=2, intent="vfx"),  # default glitch
        ],
    )
    assert [m.op for m in e.motion] == ["shake", "glitch"]


def test_decor_intent_appends_overlay() -> None:
    e = _edl()
    resolve_effect_intents(e, [EffectIntent(shot_index=1, intent="decor", params={"text": "YANGI", "color": "#FF0000"})])
    assert len(e.overlays) == 1
    o = e.overlays[0]
    assert (o.text, o.color, o.at_sec) == ("YANGI", "#FF0000", 0.0)


def test_decor_without_text_skipped() -> None:
    e = _edl()
    resolve_effect_intents(e, [EffectIntent(shot_index=1, intent="decor")])
    assert e.overlays == []


def test_explicit_at_sec_overrides_shot_window() -> None:
    e = _edl()
    resolve_effect_intents(e, [EffectIntent(shot_index=1, intent="zoom", at_sec=7.0, dur=0.5)])
    assert e.motion[0].at_sec == 7.0


def test_transition_and_sfx_lanes() -> None:
    e = _edl()
    resolve_effect_intents(
        e,
        [
            EffectIntent(shot_index=2, intent="transition", params={"type": "wipeleft"}),
            EffectIntent(shot_index=1, intent="sfx", params={"type": "boom"}),
        ],
    )
    assert (e.transitions[0].at_sec, e.transitions[0].type) == (5.0, "wipeleft")
    assert e.audio.sfx[0].type == "boom"


def test_transition_at_timeline_start_skipped() -> None:
    e = _edl()
    # shot 1 OUTPUT 0 da boshlanadi → transition birinchi kadrdan oldin → o'tkazib yuboriladi
    resolve_effect_intents(e, [EffectIntent(shot_index=1, intent="transition")])
    assert e.transitions == []


def test_unknown_shot_or_out_of_bounds_skipped() -> None:
    e = _edl()
    resolve_effect_intents(
        e,
        [
            EffectIntent(shot_index=99, intent="zoom"),  # noma'lum shot, at_sec yo'q → skip
            EffectIntent(shot_index=0, intent="zoom", at_sec=999),  # shot 0 + chegaradan tashqari → skip
        ],
    )
    assert e.motion == []


def test_async_or_gpu_intents_are_noop_on_lanes() -> None:
    # b_roll (async asset) / eye_contact / cleanup (GPU) — lane'larga teginmaydi, boshqa joyda.
    e = _edl()
    resolve_effect_intents(
        e,
        [
            EffectIntent(shot_index=1, intent="b_roll"),
            EffectIntent(shot_index=1, intent="eye_contact"),
            EffectIntent(shot_index=2, intent="cleanup"),
        ],
    )
    assert e.motion == [] and e.overlays == [] and e.transitions == [] and e.audio.sfx == []

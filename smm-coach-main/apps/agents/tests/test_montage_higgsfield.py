"""Higgsfield cinematic pipeline — pure-logic guards.

The network/ffmpeg paths are fail-soft and covered by integration; here we lock the PURE pieces that
are easy to break silently: result-URL extraction across provider shapes, request-body assembly,
motion-name → prompt/id mapping, the director's plan normalizer/fallback, and the assembler's
caption/energy math.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.graphs.nodes import higgsfield_director as director
from app.montage import higgsfield_assemble as asm
from app.montage import higgsfield_client as hc


# --- extract_video_url --------------------------------------------------------
@pytest.mark.parametrize(
    "payload,expected",
    [
        ("https://cdn/x.mp4", "https://cdn/x.mp4"),
        ("not-a-url", None),
        ({"video": {"url": "https://cdn/a.mp4"}}, "https://cdn/a.mp4"),
        ({"video_url": "https://cdn/b.mp4"}, "https://cdn/b.mp4"),
        ({"videos": [{"url": "https://cdn/c.mp4"}]}, "https://cdn/c.mp4"),
        ({"output": {"video": {"url": "https://cdn/d.mp4"}}}, "https://cdn/d.mp4"),
        ({"result": {"url": "https://cdn/e.mp4"}}, "https://cdn/e.mp4"),
        ({"data": [{"video_url": "https://cdn/f.mp4"}]}, "https://cdn/f.mp4"),
        ({"status": "COMPLETED"}, None),
        ({}, None),
        (None, None),
        (123, None),
    ],
)
def test_extract_video_url(payload, expected):
    assert hc.extract_video_url(payload) == expected


# --- build_dop_body (real Higgsfield V2 DoP shape — input nested under `params`) --------------
def test_build_dop_body_with_motion():
    body = hc.build_dop_body(
        model="dop-turbo", image_url="https://k/f.jpg", prompt="p",
        motion_id="mid-1", motion_strength=0.8, seed=7,
    )
    assert set(body.keys()) == {"params"}   # live V2 API requires the params wrapper
    p = body["params"]
    assert p["model"] == "dop-turbo"
    assert p["input_images"] == [{"type": "image_url", "image_url": "https://k/f.jpg"}]
    assert p["motions"] == [{"id": "mid-1", "strength": 0.8}]
    assert p["enhance_prompt"] is True
    assert p["seed"] == 7


def test_build_dop_body_without_motion_or_seed():
    p = hc.build_dop_body(
        model="dop-turbo", image_url="https://k/f.jpg", prompt="p",
        motion_id=None, motion_strength=2.0, seed=0,
    )["params"]
    assert "motions" not in p       # None id → omitted
    assert "seed" not in p          # 0 → omitted
    assert p["input_images"][0]["image_url"] == "https://k/f.jpg"


def test_build_dop_body_folds_large_seed():
    # crc32-derived seeds overflow the API's [1, 1_000_000] range → must fold in.
    p = hc.build_dop_body(
        model="dop-turbo", image_url="https://k/f.jpg", prompt="p",
        motion_id=None, motion_strength=0.5, seed=812697152,
    )["params"]
    assert 1 <= p["seed"] <= 1_000_000
    # a small seed passes through unchanged
    p2 = hc.build_dop_body(
        model="dop-turbo", image_url="https://k/f.jpg", prompt="p",
        motion_id=None, motion_strength=0.5, seed=7,
    )["params"]
    assert p2["seed"] == 7


def test_build_dop_body_clamps_strength():
    p = hc.build_dop_body(
        model="dop-turbo", image_url="https://k/f.jpg", prompt="p",
        motion_id="m", motion_strength=5.0, seed=1,
    )["params"]
    assert p["motions"][0]["strength"] == 1.0  # clamped to [0,1]


def test_credentials_from_api_key_secret(monkeypatch):
    monkeypatch.setattr(
        hc, "get_settings",
        lambda: SimpleNamespace(
            hf_credentials=None, hf_api_key="KID", hf_api_secret=SimpleNamespace(get_secret_value=lambda: "SEC"),
        ),
    )
    monkeypatch.delenv("HF_KEY", raising=False)
    assert hc.credentials() == ("KID", "SEC")


def test_credentials_from_combined(monkeypatch):
    monkeypatch.setattr(
        hc, "get_settings",
        lambda: SimpleNamespace(
            hf_credentials=SimpleNamespace(get_secret_value=lambda: "KID:SEC:extra"),
            hf_api_key=None, hf_api_secret=None,
        ),
    )
    # split on FIRST ':' only — a secret may itself contain ':'
    assert hc.credentials() == ("KID", "SEC:extra")


def test_credentials_missing(monkeypatch):
    monkeypatch.setattr(
        hc, "get_settings",
        lambda: SimpleNamespace(hf_credentials=None, hf_api_key=None, hf_api_secret=None),
    )
    monkeypatch.delenv("HF_KEY", raising=False)
    assert hc.credentials() is None


# --- motion helpers -----------------------------------------------------------
def test_motion_prompt_hint():
    assert "push-in" in hc.motion_prompt_hint("push_in")
    assert hc.motion_prompt_hint("PUSH_IN")  # case-insensitive
    assert hc.motion_prompt_hint("nonsense") == ""
    assert hc.motion_prompt_hint(None) == ""


def test_resolve_motion_id_from_catalog(monkeypatch):
    monkeypatch.setattr(
        hc, "get_settings",
        lambda: SimpleNamespace(higgsfield_motion_catalog='{"orbit":"uuid-orbit","push_in":"uuid-push"}'),
    )
    assert hc.resolve_motion_id("orbit") == "uuid-orbit"
    assert hc.resolve_motion_id("ORBIT") == "uuid-orbit"
    assert hc.resolve_motion_id("unmapped") is None


def test_resolve_motion_id_bad_catalog(monkeypatch):
    monkeypatch.setattr(hc, "get_settings", lambda: SimpleNamespace(higgsfield_motion_catalog="{bad json"))
    assert hc.resolve_motion_id("orbit") is None


# --- director.normalize_plan --------------------------------------------------
def test_normalize_plan_valid_and_filtered():
    raw = json.dumps(
        {
            "shots": [
                {"shot_index": 1, "prompt": "a cinematic shot", "motion": "orbit", "motion_strength": 0.7},
                {"shot_index": 2, "prompt": "another", "motion": "BOGUS", "motion_strength": 5},
                {"shot_index": 2, "prompt": "dup dropped"},          # duplicate shot_index
                {"shot_index": 99, "prompt": "out of range"},        # not a valid shot
                {"shot_index": 3, "prompt": ""},                     # empty prompt dropped
            ]
        }
    )
    plan = director.normalize_plan(raw, valid_shots={1, 2, 3}, dur_by_shot={1: 3.0, 2: 5.0})
    assert [p["shot_index"] for p in plan] == [1, 2]
    assert plan[0]["motion"] == "orbit"
    assert plan[1]["motion"] == "push_in"          # bogus → default
    assert plan[1]["motion_strength"] == 0.95      # clamped
    assert plan[0]["duration_s"] == 3.0
    assert plan[1]["duration_s"] == 5.0
    assert all(p["keyframe"] == "generate" for p in plan)
    assert plan[0]["image_prompt"]                  # falls back to prompt when absent


def test_normalize_plan_bad_json():
    assert director.normalize_plan("not json", {1}, {1: 5.0}) == []
    assert director.normalize_plan(json.dumps({"nope": 1}), {1}, {1: 5.0}) == []


def test_fallback_plan_covers_all_shots():
    shots = [{"i": 1, "action": "yugurish"}, {"i": 2, "dialogue": "salom"}]
    plan = director.fallback_plan(shots, {1: 4.0, 2: 5.0})
    assert [p["shot_index"] for p in plan] == [1, 2]
    assert all(p["prompt"] and p["image_prompt"] for p in plan)
    assert all(p["motion"] in hc.MOTION_NAMES for p in plan)
    assert plan[0]["duration_s"] == 4.0


def test_apply_keyframe_source_footage_when_upload():
    plan = [
        {"shot_index": 1, "duration_s": 4.0, "keyframe": "generate", "footage_at_sec": None},
        {"shot_index": 2, "duration_s": 6.0, "keyframe": "generate", "footage_at_sec": None},
    ]
    out = director.apply_keyframe_source(plan, has_upload=True)
    assert [p["keyframe"] for p in out] == ["footage", "footage"]
    # cumulative shot-duration midpoints: shot1 @ 2.0, shot2 @ 4.0 + 3.0 = 7.0
    assert out[0]["footage_at_sec"] == 2.0
    assert out[1]["footage_at_sec"] == 7.0


def test_apply_keyframe_source_generate_when_no_upload():
    plan = [{"shot_index": 1, "duration_s": 5.0, "keyframe": "generate", "footage_at_sec": None}]
    out = director.apply_keyframe_source(plan, has_upload=False)
    assert out[0]["keyframe"] == "generate"
    assert out[0]["footage_at_sec"] is None


def test_clamp_dur():
    assert director._clamp_dur(10) == 6.0
    assert director._clamp_dur(0.5) == 2.0
    assert director._clamp_dur(4) == 4.0
    assert director._clamp_dur(None) == 5.0
    assert director._clamp_dur("x") == 5.0


# --- assembler pure math ------------------------------------------------------
def test_shot_text_prefers_timeline_then_shotlist():
    st = [{"shotIndex": 1, "text": "salom"}, {"shotIndex": 1, "text": "dunyo"}]
    assert asm._shot_text(1, st, []) == "salom dunyo"
    assert asm._shot_text(2, [], [{"i": 2, "dialogue": "gap"}]) == "gap"
    assert asm._shot_text(2, [], [{"i": 2, "on_screen_text": "matn"}]) == "matn"
    assert asm._shot_text(3, [], []) == ""


def test_caption_window_even_distribution():
    win = asm._caption_window("bir ikki uch", 0.0, 3.0)
    assert win is not None
    assert [w.text for w in win.words] == ["bir", "ikki", "uch"]
    assert win.words[0].start == 0.0
    assert win.words[0].end == pytest.approx(1.0)
    assert win.words[2].end == pytest.approx(3.0)


def test_caption_window_empty_or_bad_range():
    assert asm._caption_window("", 0.0, 3.0) is None
    assert asm._caption_window("x", 3.0, 3.0) is None


def test_build_captions_maps_offsets():
    offsets = [(1, 0.0, 3.0), (2, 3.0, 6.0)]
    st = [{"shotIndex": 1, "text": "salom dunyo"}, {"shotIndex": 2, "text": "yaxshi"}]
    caps = asm.build_captions(offsets, st, [], {"font": "Anton"})
    assert caps.tier == "premium"
    assert caps.style.font == "Anton"
    assert len(caps.windows) == 2
    assert caps.windows[1].words[0].start == pytest.approx(3.0)


def test_build_captions_bad_font_falls_back():
    caps = asm.build_captions([(1, 0.0, 2.0)], [{"shotIndex": 1, "text": "hi"}], [], {"font": "ComicSans"})
    assert caps.style.font == "Montserrat"


def test_music_energy_bands():
    assert asm._music_energy([]) == 0.5
    assert asm._music_energy([2.0, 2.0]) == pytest.approx(0.9)   # short → punchy (clamped)
    assert asm._music_energy([8.0]) == pytest.approx(0.2)        # long → calm (clamped)
    assert asm._music_energy([5.0]) == pytest.approx(0.5)

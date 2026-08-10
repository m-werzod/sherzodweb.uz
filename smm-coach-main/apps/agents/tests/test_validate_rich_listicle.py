"""Stage 7 — per-reelType beat check: a listicle must SHOW its items as
on-screen text. High-signal, false-positive-safe."""
from __future__ import annotations

from app.graphs.nodes.scriptwriter import _validate_rich


def _deep_task(reel_type, shots):
    # Satisfy the generic depth checks so only the per-type gap can appear.
    timeline = [{"text": f"seg{i}"} for i in range(6)]
    return {
        "type": "reel", "reel_type": reel_type,
        "script_timeline": timeline, "shot_list": shots,
        "hookVariantB": "b", "music_cues": ["x"],
    }


def _shots(n_with_text):
    shots = []
    for i in range(6):
        s = {"framing": "MS", "camera": "eye-level"}
        if i < n_with_text:
            s["on_screen_text"] = f"item {i}"
        shots.append(s)
    return shots


def test_listicle_without_text_overlays_flagged():
    gaps = _validate_rich(_deep_task("listicle", _shots(1)))
    assert any("listicle" in g for g in gaps)


def test_listicle_with_enough_items_passes():
    gaps = _validate_rich(_deep_task("listicle", _shots(4)))
    assert not any("listicle" in g for g in gaps)


def test_non_listicle_not_subject_to_item_check():
    gaps = _validate_rich(_deep_task("talking_head", _shots(0)))
    assert not any("listicle" in g for g in gaps)


def _shots_broll(n_with_broll):
    shots = []
    for i in range(6):
        s = {"framing": "MS", "camera": "eye-level"}
        if i < n_with_broll:
            s["b_roll"] = f"insert {i}"
        shots.append(s)
    return shots


def test_tutorial_without_inserts_flagged():
    gaps = _validate_rich(_deep_task("tutorial", _shots_broll(1)))
    assert any("tutorial" in g for g in gaps)


def test_tutorial_with_inserts_passes():
    gaps = _validate_rich(_deep_task("tutorial", _shots_broll(3)))
    assert not any("tutorial" in g for g in gaps)


def test_broll_voiceover_mostly_talking_head_flagged():
    # 2/6 b-roll < 50% → flagged
    gaps = _validate_rich(_deep_task("broll_voiceover", _shots_broll(2)))
    assert any("broll_voiceover" in g for g in gaps)


def test_broll_voiceover_majority_broll_passes():
    # 4/6 b-roll ≥ 50% → passes
    gaps = _validate_rich(_deep_task("broll_voiceover", _shots_broll(4)))
    assert not any("broll_voiceover" in g for g in gaps)


def test_broll_null_string_not_counted():
    # A shot whose b_roll is the literal "null" must NOT count as an insert.
    shots = [{"framing": "MS", "camera": "eye-level", "b_roll": "null"} for _ in range(6)]
    gaps = _validate_rich(_deep_task("tutorial", shots))
    assert any("tutorial" in g for g in gaps)

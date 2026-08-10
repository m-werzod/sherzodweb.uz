"""Tests for the write-boundary JSON contract (json_schemas.validated_json).

A malformed LLM payload must raise HERE at the persister (debuggable) instead of
being json.dumps'd straight into jsonb and surfacing as a silent zero downstream.
And a VALID payload must serialize unchanged — unknown/extra keys preserved.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.graphs.json_schemas import (
    HOOK_META,
    MUSIC_CUES,
    PREDICT_EVIDENCE,
    SCRIPT_TIMELINE,
    SHOT_LIST,
    validated_json,
)


def test_hook_meta_valid_roundtrips_unchanged() -> None:
    val = {"cameraDirection": "Statik", "energy": 8, "retention": 0.7, "abVariant": "A"}
    out = validated_json(HOOK_META, val)
    assert json.loads(out) == val  # original serialized unchanged


def test_shot_list_new_shape_ok() -> None:
    val = [{"i": 1, "cam": "Statik", "frame": "Medium", "sec": 3, "action": "x",
            "vfx": [{"type": "text_overlay", "atSec": 0.3, "text": "hi", "position": "top"}]}]
    assert json.loads(validated_json(SHOT_LIST, val)) == val


def test_shot_list_empty_ok_for_action_task() -> None:
    assert validated_json(SHOT_LIST, []) == "[]"


def test_script_timeline_valid_ok() -> None:
    val = [{"t": "0-3s", "text": "Salom", "wordCount": 1, "cue": "Hook"}]
    assert json.loads(validated_json(SCRIPT_TIMELINE, val)) == val


def test_predict_evidence_preserves_extra_keys() -> None:
    # The writer adds `_source` (and may add others) — dump-original must keep it.
    val = {"impactBand": "medium", "note": "no real numbers", "variantA": "A", "_source": "writer_no_data"}
    assert json.loads(validated_json(PREDICT_EVIDENCE, val)) == val


def test_predict_evidence_action_zeros_ok() -> None:
    val = {"reachLow": 0, "reachMid": 0, "reachHigh": 0, "predictedSaves": 0,
           "predictedFollowers": 0, "followersStd": 0, "variantA": "Amaliyot", "llmCritique": "x"}
    assert json.loads(validated_json(PREDICT_EVIDENCE, val)) == val


# ── malformed payloads must RAISE at the boundary ───────────────────────────

def test_shot_list_as_object_not_list_raises() -> None:
    with pytest.raises(ValidationError):
        validated_json(SHOT_LIST, {"i": 1})  # a dict where a list is required


def test_script_timeline_item_missing_text_raises() -> None:
    # t + text are the contract's required fields; a missing one is a real bug.
    with pytest.raises(ValidationError):
        validated_json(SCRIPT_TIMELINE, [{"t": "0-3s", "cue": "Hook"}])


def test_hook_meta_wrong_type_raises() -> None:
    with pytest.raises(ValidationError):
        validated_json(HOOK_META, {"energy": "not-a-number-or-coercible"})


# ── Stage 7: director-grade shots + music cues ──────────────────────────────

def test_shot_list_director_fields_preserved() -> None:
    val = [{"i": 1, "reelType": "talking_head", "framing": "MS", "camera": "eye-level",
            "position": "statik shtativ", "duration_s": 3.0, "dialogue": "Salom",
            "on_screen_text": "Hook", "b_roll": None, "action": "x"}]
    assert json.loads(validated_json(SHOT_LIST, val)) == val


def test_music_cues_valid_ok() -> None:
    val = [{"atSec": 0, "event": "start", "note": "low"}, {"atSec": 8.5, "event": "drop"}]
    assert json.loads(validated_json(MUSIC_CUES, val)) == val


def test_music_cues_empty_ok() -> None:
    assert validated_json(MUSIC_CUES, []) == "[]"


def test_music_cues_wrong_type_raises() -> None:
    with pytest.raises(ValidationError):
        validated_json(MUSIC_CUES, [{"atSec": "not-a-number"}])

"""Faza 1 — footage understanding (G2 fix). Lock the deterministic shot-boundary geometry
and the vision-merge / degrade behaviour of footage_analyzer (the ffmpeg-calling helpers
detect_shots/make_vision_proxy are thin shells over run_ff — exercised in integration, not here)."""
from __future__ import annotations

import json

from app.graphs.nodes.footage_analyzer import _build_footage_map, _parse_json
from app.montage.footage import FootageMap, ShotBoundary
from app.montage.footage_vision import shots_from_scene_times
from app.montage.probe import ClipInfo


def _info(duration: float = 30.0) -> ClipInfo:
    return ClipInfo(
        duration=duration, fps=30.0, width=1080, height=1920,
        rotation=0, has_audio=True, codec_name="h264",
    )


def test_scene_times_become_contiguous_shots() -> None:
    shots = shots_from_scene_times([10.0, 20.0], 30.0)
    assert [(s.src_start, s.src_end) for s in shots] == [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)]
    assert [s.index for s in shots] == [0, 1, 2]
    assert all(s.detected_by == "scene" for s in shots)


def test_no_scene_change_is_single_fallback_shot() -> None:
    shots = shots_from_scene_times([], 30.0)
    assert len(shots) == 1
    assert shots[0].detected_by == "fallback"
    assert (shots[0].src_start, shots[0].src_end) == (0.0, 30.0)


def test_out_of_range_scene_times_ignored() -> None:
    # 0 and >=duration are dropped; only the interior 15.0 splits the clip.
    shots = shots_from_scene_times([0.0, 15.0, 30.0, 99.0], 30.0)
    assert [(s.src_start, s.src_end) for s in shots] == [(0.0, 15.0), (15.0, 30.0)]


def test_zero_duration_yields_no_shots() -> None:
    assert shots_from_scene_times([5.0], 0.0) == []


def test_vision_merge_enriches_shots_by_index() -> None:
    shots = shots_from_scene_times([10.0, 20.0], 30.0)
    answer = json.dumps(
        {
            "shots": [
                {"index": 0, "description": "odam kameraga gapiradi", "subject": "person",
                 "primary_action": "talking", "matched_shot_index": 1, "motion_score": 0.2},
                {"index": 2, "description": "mahsulot yaqindan", "subject": "product",
                 "primary_action": "reveal", "matched_shot_index": 3, "motion_score": 0.7},
            ],
            "vision_summary": "Mahsulot tanishtiruvi",
            "detected_subjects": ["person", "product"],
        }
    )
    fmap = _build_footage_map("t", "x", _info(), shots, answer)
    assert fmap.vision_ok is True
    assert fmap.vision_summary == "Mahsulot tanishtiruvi"
    assert fmap.detected_subjects == ["person", "product"]
    assert fmap.shots[0].subject == "person"
    assert fmap.shots[0].matched_shot_index == 1
    assert fmap.shots[0].motion_score == 0.2
    # shot 1 had no vision entry — keeps scdet geometry, empty description.
    assert fmap.shots[1].description == ""
    assert fmap.shots[1].matched_shot_index == 0
    assert fmap.shots[2].subject == "product"


def test_empty_answer_degrades_to_scdet_only() -> None:
    shots = shots_from_scene_times([10.0], 30.0)
    fmap = _build_footage_map("t", "x", _info(), shots, "")
    assert fmap.vision_ok is False
    assert len(fmap.shots) == 2  # scdet geometry preserved
    assert all(s.description == "" for s in fmap.shots)
    assert fmap.duration_sec == 30.0


def test_malformed_vision_json_is_safe() -> None:
    shots = shots_from_scene_times([], 12.0)
    fmap = _build_footage_map("t", "x", _info(12.0), shots, "not json at all")
    assert fmap.vision_ok is False
    assert len(fmap.shots) == 1


def test_motion_score_clamped_and_zero_match_ignored() -> None:
    shots = shots_from_scene_times([10.0], 30.0)
    answer = json.dumps({
        "shots": [{"index": 0, "motion_score": 5.0, "matched_shot_index": 0}],
        "vision_summary": "x",
    })
    fmap = _build_footage_map("t", "x", _info(), shots, answer)
    assert fmap.shots[0].motion_score == 1.0  # clamped to [0,1]
    assert fmap.shots[0].matched_shot_index == 0  # 0 stays unassigned


def test_confidence_read_clamped_and_defaults_to_one() -> None:
    # confidence must ride the shot so the b-roll / semantic-cut conf_floor (0.5) is a LIVE signal.
    shots = shots_from_scene_times([10.0, 20.0], 30.0)
    answer = json.dumps({
        "shots": [
            {"index": 0, "matched_shot_index": 1, "confidence": 0.3},  # weak match → below conf_floor
            {"index": 1, "matched_shot_index": 2, "confidence": 5.0},  # clamps to 1.0
            {"index": 2, "matched_shot_index": 3},                     # absent → backward-safe 1.0
        ],
        "vision_summary": "x",
    })
    fmap = _build_footage_map("t", "x", _info(), shots, answer)
    assert fmap.shots[0].confidence == 0.3
    assert fmap.shots[1].confidence == 1.0
    assert fmap.shots[2].confidence == 1.0


def test_footage_map_roundtrip_is_lossless() -> None:
    fmap = FootageMap(
        task_id="t", tenant_id="x", duration_sec=12.0,
        shots=[ShotBoundary(index=0, src_start=0.0, src_end=12.0, description="x")],
        vision_ok=True,
    )
    again = FootageMap.model_validate(fmap.model_dump())
    assert again.model_dump() == fmap.model_dump()


def test_parse_json_extracts_embedded_object() -> None:
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json("garbage") == {}


def test_mismatched_indices_not_marked_vision_ok() -> None:
    # Gemini hallucinated indices that match no detected shot, and gave no summary —
    # nothing was actually understood, so vision_ok must be False (review finding).
    shots = shots_from_scene_times([10.0], 30.0)
    answer = json.dumps({"shots": [{"index": 99, "description": "x"}]})
    fmap = _build_footage_map("t", "x", _info(), shots, answer)
    assert fmap.vision_ok is False
    assert all(s.description == "" for s in fmap.shots)


def test_mismatched_indices_with_summary_still_vision_ok() -> None:
    shots = shots_from_scene_times([10.0], 30.0)
    answer = json.dumps({"shots": [{"index": 99}], "vision_summary": "bu reel"})
    fmap = _build_footage_map("t", "x", _info(), shots, answer)
    assert fmap.vision_ok is True  # a summary is real understanding even if per-shot missed


def test_duplicate_scene_times_no_zero_width_shots() -> None:
    shots = shots_from_scene_times([5.0, 5.0, 10.0], 30.0)
    assert all(s.src_end > s.src_start for s in shots)  # no zero-width
    assert [(s.src_start, s.src_end) for s in shots] == [(0.0, 5.0), (5.0, 10.0), (10.0, 30.0)]


def test_unsorted_scene_times_are_sorted() -> None:
    shots = shots_from_scene_times([20.0, 5.0, 15.0], 30.0)
    assert all(s.src_end > s.src_start for s in shots)  # no negative duration
    starts = [s.src_start for s in shots]
    assert starts == sorted(starts)

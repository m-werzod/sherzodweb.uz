"""Pydantic models for the ContentTask jsonb columns, HAND-MIRRORED to the web
read schemas in `packages/shared-types/src/json-columns.ts` (per CLAUDE.md:
hand-mirror, do NOT auto-convert from Zod).

WHY: `roadmap_persister` used to `json.dumps()` ad-hoc LLM dicts straight into
jsonb. A wrong shape then surfaced N layers downstream in the UI (rendered as a
silent zero) instead of at the writer. `validated_json` validates the payload at
the write boundary — raising `pydantic.ValidationError` HERE, where it's
debuggable — then serializes the ORIGINAL value unchanged, so unknown/extra keys
the model doesn't know about are never dropped.

Keep these in sync with json-columns.ts — the cross-language fixture test
(`tests/test_json_contract.py`) parses the SAME `__fixtures__/*.json` with both
sides, so a rename on either side breaks a test.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter


class _Contract(BaseModel):
    # LLM payloads carry extra/optional keys; validate the known fields and
    # tolerate the rest (we serialize the original value, so nothing is dropped).
    model_config = ConfigDict(extra="allow")


class HookMeta(_Contract):
    cameraDirection: str | None = None
    energy: float | None = None
    retention: float | None = None
    abVariant: str | None = None


class ShotVfx(_Contract):
    type: str | None = None
    atSec: float | None = None
    text: str | None = None
    position: str | None = None


class MusicCue(_Contract):
    atSec: float | None = None
    event: str | None = None  # start | drop | stab | silence
    note: str | None = None


class ShotListItem(_Contract):
    # new scriptwriter shape
    i: int | None = None
    index: int | None = None
    cam: str | None = None
    frame: str | None = None
    sec: float | None = None
    action: str | None = None
    vfx: list[ShotVfx] | None = None
    # Stage 7 — director-grade shot direction (all optional, back-compat).
    reelType: str | None = None
    framing: str | None = None  # WS | MS | CU | ECU
    camera: str | None = None  # eye-level | low | high | overhead | handheld
    position: str | None = None  # statik shtativ | qo'lda | push-in | ...
    duration_s: float | None = None
    on_screen_text: str | None = None
    b_roll: str | None = None
    dialogue: str | None = None
    # old shape (back-compat)
    time: str | None = None
    cue: str | None = None
    caption: str | None = None


class ScriptTimelineEntry(_Contract):
    # _normalize_timeline guarantees t + text (non-empty) + wordCount + cue.
    t: str
    text: str
    cue: str = ""
    delivery: str | None = None
    wordCount: int | None = None
    shotIndex: int | None = None
    pacingNote: str | None = None


class PredictEvidence(_Contract):
    # The writer emits a union — exemplar-grounded, qualitative back-fill, or
    # action zeros — so every key is optional.
    reachLow: float | None = None
    reachMid: float | None = None
    reachHigh: float | None = None
    predictedSaves: float | None = None
    predictedFollowers: float | None = None
    followersStd: float | None = None
    variantA: str | None = None
    impactBand: str | None = None
    note: str | None = None
    llmCritique: str | None = None
    exemplarSource: str | None = None
    exemplarReach: float | None = None


HOOK_META: TypeAdapter[HookMeta] = TypeAdapter(HookMeta)
SHOT_LIST: TypeAdapter[list[ShotListItem]] = TypeAdapter(list[ShotListItem])
MUSIC_CUES: TypeAdapter[list[MusicCue]] = TypeAdapter(list[MusicCue])
SCRIPT_TIMELINE: TypeAdapter[list[ScriptTimelineEntry]] = TypeAdapter(list[ScriptTimelineEntry])
PREDICT_EVIDENCE: TypeAdapter[PredictEvidence] = TypeAdapter(PredictEvidence)


def validated_json(adapter: TypeAdapter[Any], value: Any) -> str:
    """Validate `value` against the cross-language contract — raising
    `pydantic.ValidationError` on a malformed shape (debuggable at the writer,
    not downstream in the UI) — then serialize the ORIGINAL value unchanged so
    unknown/extra keys are never dropped.
    """
    adapter.validate_python(value)
    return json.dumps(value)

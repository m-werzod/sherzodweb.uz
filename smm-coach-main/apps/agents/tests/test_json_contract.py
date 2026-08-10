"""Cross-language contract test (agents side). Parses the SHARED golden fixtures
(packages/shared-types/__fixtures__/json-columns.fixtures.json) with the Pydantic
WRITE models. The web side (apps/web/src/lib/json-contract.test.ts) parses the
SAME file with the Zod READ schemas. A key rename on either side — schema or
fixture — breaks one of these tests; that's the binding nothing else provides.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.graphs.json_schemas import (
    PREDICT_EVIDENCE,
    SCRIPT_TIMELINE,
    SHOT_LIST,
    HookMeta,
    PredictEvidence,
    ShotListItem,
)

_FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "shared-types"
    / "__fixtures__"
    / "json-columns.fixtures.json"
)
fx = json.loads(_FIXTURES.read_text(encoding="utf-8"))


def test_hook_meta_keeps_all_four_fields() -> None:
    m = HookMeta.model_validate(fx["hookMeta"])
    assert m.cameraDirection == "Statik portret"
    assert m.energy == 8
    assert m.retention == 0.72
    assert m.abVariant == "A"


def test_script_timeline_required_and_conditional() -> None:
    rows = SCRIPT_TIMELINE.validate_python(fx["scriptTimeline"])
    assert rows[0].t == "0-3s"
    assert rows[0].text
    assert rows[0].cue == "Hook"
    assert rows[1].delivery == "tez, energetik"
    assert rows[1].shotIndex == 2
    assert rows[1].pacingNote


def test_shot_list_keeps_writer_keys() -> None:
    shots = SHOT_LIST.validate_python(fx["shotList"])
    assert isinstance(shots[0], ShotListItem)
    assert shots[0].i == 1
    assert shots[0].cam == "Statik"
    assert shots[0].frame == "Medium"
    assert shots[0].sec == 3
    assert shots[0].action == fx["shotList"][0]["action"]
    assert shots[0].vfx is not None and shots[0].vfx[0].type == "text_overlay"


def test_predict_evidence_qualitative_and_extra_key() -> None:
    p = PredictEvidence.model_validate(fx["predictEvidence"])
    assert p.impactBand == "medium"
    assert p.note
    assert p.variantA == "A"
    # extra='allow' keeps the writer's `_source`
    assert p.model_extra is not None and p.model_extra.get("_source") == "writer_no_data"


def test_predict_evidence_serializes_unchanged() -> None:
    # validated_json must round-trip the original (incl. _source) byte-for-byte.
    from app.graphs.json_schemas import validated_json

    out = json.loads(validated_json(PREDICT_EVIDENCE, fx["predictEvidence"]))
    assert out == fx["predictEvidence"]

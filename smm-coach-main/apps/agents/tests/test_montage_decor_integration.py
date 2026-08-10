"""Faza C integration — decor gating (compile_and_render) + meta reader (worker). Pure, no network."""
from __future__ import annotations

from app.montage.compiler import _maybe_add_decor_background
from app.montage.edl import EDL, Source
from app.workers.montage_worker import _decor_prompt_from_meta


def _edl() -> EDL:
    return EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))


def test_decor_skipped_when_disabled_or_no_prompt() -> None:
    # ENABLE_DECOR defaults off, and a missing file → upload short-circuits — never a variant, no network.
    e = _edl()
    _maybe_add_decor_background(e, "/nope.mp4", "modern neon studio", task_id="t", work_dir=".")
    assert e.source_variants == []
    _maybe_add_decor_background(e, "/nope.mp4", None, task_id="t", work_dir=".")
    assert e.source_variants == []
    _maybe_add_decor_background(e, "/nope.mp4", "   ", task_id="t", work_dir=".")
    assert e.source_variants == []


def test_decor_prompt_from_meta_reads_instruction() -> None:
    assert _decor_prompt_from_meta({"decorBackground": "modern studio"}) == "modern studio"
    assert _decor_prompt_from_meta({"decorBackground": "  neon  "}) == "neon"
    assert _decor_prompt_from_meta('{"decorBackground":"library"}') == "library"


def test_decor_prompt_from_meta_absent_or_blank_is_none() -> None:
    assert _decor_prompt_from_meta({"decorBackground": ""}) is None
    assert _decor_prompt_from_meta({}) is None
    assert _decor_prompt_from_meta("not json") is None
    assert _decor_prompt_from_meta(None) is None

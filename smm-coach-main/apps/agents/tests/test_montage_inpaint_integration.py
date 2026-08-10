"""Faza D integration — inpaint gating (compile_and_render) + meta reader (worker). Pure, no network."""
from __future__ import annotations

from app.montage.compiler import _maybe_add_inpaint_variant
from app.montage.edl import EDL, Source
from app.workers.montage_worker import _inpaint_remove_from_meta


def _edl() -> EDL:
    return EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))


def test_inpaint_variant_skipped_when_disabled_or_no_remove() -> None:
    # ENABLE_INPAINT defaults off, and a missing file → upload short-circuits — never a variant, no network.
    e = _edl()
    _maybe_add_inpaint_variant(e, "/nope.mp4", "person in background", task_id="t")
    assert e.source_variants == []
    _maybe_add_inpaint_variant(e, "/nope.mp4", None, task_id="t")
    assert e.source_variants == []
    _maybe_add_inpaint_variant(e, "/nope.mp4", "   ", task_id="t")
    assert e.source_variants == []


def test_inpaint_remove_from_meta_reads_instruction() -> None:
    assert _inpaint_remove_from_meta({"inpaintRemove": "person in background"}) == "person in background"
    assert _inpaint_remove_from_meta({"inpaintRemove": "  logo  "}) == "logo"
    assert _inpaint_remove_from_meta('{"inpaintRemove":"car"}') == "car"


def test_inpaint_remove_from_meta_absent_or_blank_is_none() -> None:
    assert _inpaint_remove_from_meta({"inpaintRemove": ""}) is None
    assert _inpaint_remove_from_meta({"inpaintRemove": "   "}) is None
    assert _inpaint_remove_from_meta({}) is None
    assert _inpaint_remove_from_meta("not json") is None
    assert _inpaint_remove_from_meta(None) is None

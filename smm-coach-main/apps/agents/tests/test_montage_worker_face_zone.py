"""Regression lock — captions must never land back on the speaker's face after a refine round-trip.

face_zone (top|center|bottom, from the F6 vision director) is a fact about the SOURCE clip, not a
user edit. The web EDL wire-contract (zod EdlSchema) doesn't carry it yet, so a STUDIO / manual
re-render round-trips meta.edl WITHOUT face_zone — and render_from_edl would then place captions
over the face (the exact regression a bad reel was deleted over). The manual worker path re-hydrates
it from the durable director notes via _reattach_face_zone. This test pins that helper's contract.
"""
from __future__ import annotations

import pytest

from app.montage.edl import EDL, Source
from app.workers.montage_worker import _reattach_face_zone


def _edl(face_zone: str | None = None) -> EDL:
    e = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))
    e.face_zone = face_zone
    return e


def test_fills_missing_face_zone_from_notes() -> None:
    # Round-tripped EDL lost face_zone; the director note re-hydrates it → captions dodge the face.
    e = _edl(None)
    _reattach_face_zone(e, "bottom")
    assert e.face_zone == "bottom"


@pytest.mark.parametrize("existing", ["top", "center", "bottom"])
def test_does_not_overwrite_face_zone_already_on_edl(existing: str) -> None:
    # A face_zone already on the EDL (fresh AUTO cut, or a future contract that carries it) is
    # authoritative — the note must NOT clobber it.
    e = _edl(existing)
    _reattach_face_zone(e, "top" if existing != "top" else "bottom")
    assert e.face_zone == existing


@pytest.mark.parametrize("note", [None, "", "left", "middle", "unknown", "TOP"])
def test_ignores_absent_or_invalid_note(note: str | None) -> None:
    # No usable note → leave it None (proportional/center placement), never inject junk that the
    # ASS/Shotstack layout maps wouldn't recognize. Note the check is exact-lowercase: "TOP" is junk.
    e = _edl(None)
    _reattach_face_zone(e, note)
    assert e.face_zone is None

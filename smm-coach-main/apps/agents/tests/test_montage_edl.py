"""The two-timebase offset table is the single most desync-prone piece of the
montage subsystem — one off-by-one shifts every caption. Lock it down."""
from __future__ import annotations

import pytest

from app.montage.edl import EDL, Cut, Source

# cuts keep source [0,5], [10,15], [20,22] -> 12s output timeline.
_CUTS = [
    Cut(src_start=0.0, src_end=5.0),
    Cut(src_start=10.0, src_end=15.0),
    Cut(src_start=20.0, src_end=22.0),
]


def _edl() -> EDL:
    return EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"), cuts=_CUTS)


def test_output_duration_sums_kept_segments() -> None:
    assert _edl().output_duration() == pytest.approx(12.0)


@pytest.mark.parametrize(
    ("src", "out"),
    [(0.0, 0.0), (5.0, 5.0), (10.0, 5.0), (12.0, 7.0), (15.0, 10.0), (22.0, 12.0)],
)
def test_source_to_output(src: float, out: float) -> None:
    assert _edl().source_to_output(src) == pytest.approx(out)


def test_source_in_removed_gap_has_no_output() -> None:
    # 7.0 lies in the cut-out gap (5,10) — it has no home on the output timeline.
    assert _edl().source_to_output(7.0) is None


@pytest.mark.parametrize(
    ("out", "src"),
    [(0.0, 0.0), (5.0, 5.0), (6.0, 11.0), (10.0, 15.0), (12.0, 22.0)],
)
def test_output_to_source_roundtrips(out: float, src: float) -> None:
    assert _edl().output_to_source(out) == pytest.approx(src)


def test_output_to_source_clamps_out_of_range() -> None:
    assert _edl().output_to_source(-3.0) == pytest.approx(0.0)
    assert _edl().output_to_source(999.0) == pytest.approx(22.0)


def test_validate_output_atsec_bounds() -> None:
    e = _edl()
    assert e.validate_output_atsec(0.0)
    assert e.validate_output_atsec(12.0)
    assert e.validate_output_atsec(12.0005)  # within float tolerance
    assert not e.validate_output_atsec(12.5)
    assert not e.validate_output_atsec(-0.5)


def test_empty_cuts_is_safe() -> None:
    e = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))
    assert e.output_duration() == 0.0
    assert e.output_to_source(3.0) == 0.0
    assert e.source_to_output(3.0) is None


def test_edl_dump_validate_roundtrip_is_identity() -> None:
    # The editor persists/loads the EDL as JSON — round-trip must be lossless.
    from app.montage.edl import Motion

    e = EDL(
        task_id="t", tenant_id="x", source=Source(upload_key="k"), cuts=_CUTS,
        motion=[Motion(op="zoom_punch", at_sec=2.0, dur=0.5)],
    )
    again = EDL.model_validate(e.model_dump())
    assert again.output_duration() == e.output_duration()
    assert again.motion[0].op == "zoom_punch"
    assert again.model_dump() == e.model_dump()


def test_validate_inbound_edl_guards() -> None:
    from app.montage.compiler import validate_inbound_edl
    from app.montage.edl import Motion

    ok, _ = validate_inbound_edl(_edl())
    assert ok  # 12s output, no motion
    short = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"),
                cuts=[Cut(src_start=0.0, src_end=1.0)])
    assert not validate_inbound_edl(short)[0]  # < 3s
    bad = _edl()
    bad.motion = [Motion(op="rm -rf", at_sec=1.0, dur=0.5)]
    assert not validate_inbound_edl(bad)[0]  # op not in allowlist


def test_validate_inbound_edl_rejects_unsafe_broll_asset() -> None:
    """A hand-edited EDL must not smuggle an arbitrary local path into ffmpeg -i."""
    import os
    import tempfile

    from app.montage.compiler import validate_inbound_edl
    from app.montage.edl import Broll

    def _with_broll(asset_url: str | None) -> EDL:
        e = _edl()
        e.broll = [Broll(shot_index=1, placement="overlay", asset_url=asset_url,
                         at_sec=1.0, output_dur_sec=2.0)]
        return e

    tmp = tempfile.gettempdir()
    # REJECTED — arbitrary local path (server-local file probe across the boundary).
    assert not validate_inbound_edl(_with_broll("/etc/passwd"))[0]
    # REJECTED — traversal that escapes the temp dir (realpath collapses the ..).
    assert not validate_inbound_edl(_with_broll(os.path.join(tmp, "..", "etc", "passwd")))[0]
    # ALLOWED — none, http(s), and a path under the temp dir (auto-flow download dir).
    assert validate_inbound_edl(_with_broll(None))[0]
    assert validate_inbound_edl(_with_broll("https://cdn.example.com/b.mp4"))[0]
    assert validate_inbound_edl(_with_broll(os.path.join(tmp, "broll_0.mp4")))[0]

"""Faza 0 — the G1 fix: timing.assign_shot_index threads the scriptwriter storyboard
shot (scriptTimeline[].shotIndex -> shotList[].i) onto each silence-derived cut, so the
storyboard stops being orphaned once the clip is cut. Lock the linkage + the trust-boundary
guard."""
from __future__ import annotations

from app.montage.edl import EDL, Broll, Cut, Source
from app.montage.timing import assign_shot_index


def test_assigns_storyboard_shot_proportionally() -> None:
    # 2 equal-weight segments over a 10s output timeline (cuts: 0-5 then 5-10 output).
    cuts = [Cut(src_start=0.0, src_end=5.0), Cut(src_start=10.0, src_end=15.0)]
    timeline = [
        {"text": "bir ikki uch", "shotIndex": 1},
        {"text": "tort besh olti", "shotIndex": 2},
    ]
    assign_shot_index(cuts, timeline)
    assert cuts[0].shot_index == 1
    assert cuts[1].shot_index == 2
    assert cuts[0].script_text  # narration carried onto the cut
    assert cuts[1].script_text


def test_missing_shot_index_stays_unassigned() -> None:
    # No shotIndex on the segments (e.g. older script / ACTION task) -> 0 = unassigned.
    cuts = [Cut(src_start=0.0, src_end=6.0)]
    timeline = [{"text": "profil rasmini almashtiring"}]
    assign_shot_index(cuts, timeline)
    assert cuts[0].shot_index == 0
    assert cuts[0].script_text  # script_text still threaded through


def test_non_positive_shot_index_normalized_to_zero() -> None:
    cuts = [Cut(src_start=0.0, src_end=6.0)]
    assign_shot_index(cuts, [{"text": "salom dunyo", "shotIndex": 0}])
    assert cuts[0].shot_index == 0


def test_empty_timeline_leaves_cuts_untouched() -> None:
    cuts = [Cut(src_start=0.0, src_end=5.0)]
    assign_shot_index(cuts, [])
    assert cuts[0].shot_index == 0
    assert cuts[0].script_text == ""


def test_no_cuts_is_safe() -> None:
    assign_shot_index([], [{"text": "salom", "shotIndex": 1}])  # must not raise


def test_three_cuts_span_three_shots() -> None:
    # Three equal segments over three equal cuts -> 1:1 mapping.
    cuts = [
        Cut(src_start=0.0, src_end=4.0),
        Cut(src_start=10.0, src_end=14.0),
        Cut(src_start=20.0, src_end=24.0),
    ]
    timeline = [
        {"text": "aaa bbb ccc ddd", "shotIndex": 1},
        {"text": "eee fff ggg hhh", "shotIndex": 2},
        {"text": "iii jjj kkk lll", "shotIndex": 3},
    ]
    assign_shot_index(cuts, timeline)
    assert [c.shot_index for c in cuts] == [1, 2, 3]


def test_validate_inbound_rejects_negative_shot_index() -> None:
    from app.montage.compiler import validate_inbound_edl

    cuts = [
        Cut(src_start=0.0, src_end=5.0),
        Cut(src_start=10.0, src_end=15.0),
        Cut(src_start=20.0, src_end=22.0),
    ]
    edl = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"), cuts=cuts)
    assert validate_inbound_edl(edl)[0]  # 12s, shot_index defaults 0 -> ok
    edl.cuts[0].shot_index = -1
    assert not validate_inbound_edl(edl)[0]
    edl.cuts[0].shot_index = 0
    edl.broll = [Broll(shot_index=-2)]
    assert not validate_inbound_edl(edl)[0]

"""Crossfade transition render guards (Stage 9b — render the xfade the montage_director plans).

The ffmpeg run itself is container-tested; here we pin the two PURE pieces:
  * `_transition_plan` — maps EDL transitions onto cut boundaries, injection-safe (closed map),
    snap-to-boundary, one-per-boundary, and dropped when there's no source room to stay
    DURATION-NEUTRAL.
  * `_join_parts` — builds the filtergraph join. No transitions → the original n-way concat
    (BYTE-IDENTICAL, no regression). With transitions → xfade/acrossfade fold whose duration math
    nets back to the hard-cut total (offset on the original boundary).
"""
from __future__ import annotations

from app.montage.compiler import _join_parts, _transition_plan
from app.montage.edl import EDL, Cut, Source, Transition


def _edl(cuts: list[tuple[float, float]], trans: list[Transition], *, src_dur: float = 10.0) -> EDL:
    return EDL(
        task_id="t",
        tenant_id="x",
        source=Source(upload_key="k", duration_sec=src_dur),
        cuts=[Cut(src_start=a, src_end=b) for a, b in cuts],
        transitions=trans,
    )


# OUTPUT boundaries for cuts (0,2),(3,5),(6,8) [each 2s] = after-cut0 @2.0, after-cut1 @4.0.
_CUTS = [(0.0, 2.0), (3.0, 5.0), (6.0, 8.0)]


# --- _transition_plan ---------------------------------------------------------------------------


def test_transition_snaps_to_boundary() -> None:
    plan = _transition_plan(_edl(_CUTS, [Transition(at_sec=2.0, type="xfade", dur=0.3)]))
    assert plan == {0: ("fade", 0.3)}  # boundary after cut 0, mapped xfade->fade


def test_dissolve_maps_and_second_boundary() -> None:
    plan = _transition_plan(_edl(_CUTS, [Transition(at_sec=4.05, type="dissolve", dur=0.4)]))
    assert plan == {1: ("dissolve", 0.4)}


def test_unknown_type_is_not_planned() -> None:
    # An unrecognised type never enters the filtergraph (injection guard) → no plan entry.
    assert _transition_plan(_edl(_CUTS, [Transition(at_sec=2.0, type="rm -rf", dur=0.3)])) == {}


def test_transition_far_from_boundary_dropped() -> None:
    # 3.0s is >0.30 from both boundaries (2.0, 4.0) → not snapped.
    assert _transition_plan(_edl(_CUTS, [Transition(at_sec=3.0, type="fade", dur=0.3)])) == {}


def test_one_transition_per_boundary() -> None:
    plan = _transition_plan(
        _edl(_CUTS, [Transition(at_sec=2.0, type="fade", dur=0.3), Transition(at_sec=2.05, type="fade", dur=0.5)])
    )
    assert list(plan.keys()) == [0]  # the second can't double-book boundary 0


def test_dropped_when_no_source_room() -> None:
    # src_dur barely past cut 0's end → no room to extend the tail by `dur` → hard cut.
    plan = _transition_plan(_edl(_CUTS, [Transition(at_sec=2.0, type="fade", dur=0.3)], src_dur=2.1))
    assert plan == {}


def test_disabled_returns_empty() -> None:
    assert _transition_plan(_edl(_CUTS, [Transition(at_sec=2.0, type="fade", dur=0.3)]), enabled=False) == {}


def test_no_transitions_empty_plan() -> None:
    assert _transition_plan(_edl(_CUTS, [])) == {}


# --- _join_parts --------------------------------------------------------------------------------


def test_join_empty_plan_is_byte_identical_concat() -> None:
    # The no-transition path MUST be the exact old single n-way concat (regression guard).
    parts = _join_parts(3, {}, [2.0, 2.0, 2.0])
    assert parts == ["[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[vc][ac]"]


def test_join_single_cut() -> None:
    assert _join_parts(1, {}, [2.0]) == ["[v0][a0]concat=n=1:v=1:a=1[vc][ac]"]


def test_join_with_xfade_then_hardcut() -> None:
    # plan: crossfade after cut 0 (fade, 0.3); hard cut after cut 1. rendered_lens reflect the +0.3
    # tail extension on cut 0 (2.0 -> 2.3).
    parts = _join_parts(3, {0: ("fade", 0.3)}, [2.3, 2.0, 2.0])
    joined = " | ".join(parts)
    # crossfade exactly on the original boundary (offset = 2.3 - 0.3 = 2.0).
    assert "[v0][v1]xfade=transition=fade:duration=0.300:offset=2.000[vj1]" in joined
    assert "[a0][a1]acrossfade=d=0.300[aj1]" in joined
    # second boundary is a hard cut, last step emits the public [vc]/[ac] labels.
    assert "[vj1][v2]concat=n=2:v=1:a=0[vc]" in joined
    assert "[aj1][a2]concat=n=2:v=0:a=1[ac]" in joined


def test_join_duration_neutral_two_cuts() -> None:
    # Two cuts, crossfade between them: cut0 rendered 2.3 (2.0 + 0.3 tail), cut1 2.0.
    # output = 2.3 + 2.0 - 0.3 = 4.0 = the hard-cut total (2.0 + 2.0). offset = 2.0 (original seam).
    parts = _join_parts(2, {0: ("fade", 0.3)}, [2.3, 2.0])
    assert parts == ["[v0][v1]xfade=transition=fade:duration=0.300:offset=2.000[vc]",
                     "[a0][a1]acrossfade=d=0.300[ac]"]

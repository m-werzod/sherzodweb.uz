"""Faza 1b — content-aware cuts. subdivide_cuts splits cuts at visual scene changes so the
montage cuts where the footage cuts, WITHOUT changing which frames are kept (duration-preserving,
so the two-timebase offset table is untouched). Lock the split math + the safety guards."""
from __future__ import annotations

import pytest

from app.montage.edl import Cut
from app.montage.timing import subdivide_cuts, subdivide_evenly


def _dur(cuts: list[Cut]) -> float:
    return sum(c.src_end - c.src_start for c in cuts)


def test_splits_cut_at_interior_scene_boundary() -> None:
    cuts = [Cut(src_start=0.0, src_end=10.0)]
    out = subdivide_cuts(cuts, [4.0])
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 4.0), (4.0, 10.0)]
    assert _dur(out) == pytest.approx(10.0)  # duration preserved


def test_multiple_boundaries_in_one_cut() -> None:
    out = subdivide_cuts([Cut(src_start=0.0, src_end=10.0)], [3.0, 6.0])
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 3.0), (3.0, 6.0), (6.0, 10.0)]


def test_boundary_too_close_to_edges_is_skipped() -> None:
    # within min_sub (0.5) of either edge -> no split (avoids jittery micro-shots).
    cuts = [Cut(src_start=0.0, src_end=10.0)]
    assert subdivide_cuts(cuts, [0.3]) == cuts  # too near start
    assert subdivide_cuts(cuts, [9.8]) == cuts  # too near end


def test_no_scene_times_returns_unchanged() -> None:
    cuts = [Cut(src_start=0.0, src_end=5.0), Cut(src_start=10.0, src_end=15.0)]
    assert subdivide_cuts(cuts, []) is cuts


def test_scene_outside_cut_range_ignored() -> None:
    # cuts keep [0,5] and [10,15]; a scene at 7.0 lies in the removed gap -> no split.
    cuts = [Cut(src_start=0.0, src_end=5.0), Cut(src_start=10.0, src_end=15.0)]
    out = subdivide_cuts(cuts, [7.0])
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 5.0), (10.0, 15.0)]


def test_split_only_the_cut_that_contains_the_boundary() -> None:
    cuts = [Cut(src_start=0.0, src_end=5.0), Cut(src_start=10.0, src_end=20.0)]
    out = subdivide_cuts(cuts, [14.0])  # inside the second cut only
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 5.0), (10.0, 14.0), (14.0, 20.0)]
    assert _dur(out) == pytest.approx(_dur(cuts))  # total kept footage unchanged


def test_duplicate_and_unsorted_scene_times_safe() -> None:
    out = subdivide_cuts([Cut(src_start=0.0, src_end=10.0)], [6.0, 3.0, 6.0])
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 3.0), (3.0, 6.0), (6.0, 10.0)]


def test_adjacent_boundaries_within_min_sub_dont_make_tiny_fragments() -> None:
    # scenes 5.0 and 5.2 are < min_sub (0.5) apart — the second is skipped, so no 0.2s shard.
    out = subdivide_cuts([Cut(src_start=0.0, src_end=10.0)], [5.0, 5.2])
    assert [(c.src_start, c.src_end) for c in out] == [(0.0, 5.0), (5.0, 10.0)]
    assert all(c.src_end - c.src_start >= 0.5 for c in out)  # every fragment >= min_sub


# ── subdivide_evenly (edit floor) ─────────────────────────────────────────────


def test_evenly_splits_a_long_fluent_cut_into_rhythm_segments() -> None:
    # A 10.7s single cut (the prod passthrough) → several ~2.8s fragments.
    out = subdivide_evenly([Cut(src_start=0.0, src_end=10.7)])
    assert len(out) >= 3
    assert _dur(out) == pytest.approx(10.7)  # duration preserved
    assert all(c.src_end - c.src_start >= 1.2 for c in out)  # no micro-shards
    # fragments are contiguous
    for a, b in zip(out, out[1:], strict=False):
        assert a.src_end == pytest.approx(b.src_start)


def test_evenly_leaves_short_cut_untouched() -> None:
    cuts = [Cut(src_start=0.0, src_end=3.0)]
    assert subdivide_evenly(cuts) == cuts


def test_evenly_preserves_multiple_cuts_total_duration() -> None:
    cuts = [Cut(src_start=0.0, src_end=9.0), Cut(src_start=20.0, src_end=21.0)]
    out = subdivide_evenly(cuts)
    assert _dur(out) == pytest.approx(_dur(cuts))
    assert len(out) > len(cuts)  # the 9s cut was subdivided

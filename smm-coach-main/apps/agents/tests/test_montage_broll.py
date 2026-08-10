"""B-roll curation guards (Faza 3). The Pexels network + the ffmpeg overlay splice are
smoke-tested in the deployed container; here we pin the pure decision logic that must NEVER
over-fetch (drowning a montage in stock) or mis-place a clip."""
from __future__ import annotations

import os

import pytest

from app.montage.broll import resolve_broll, select_broll_shots, select_reject_shots
from app.montage.compiler import _renderable_broll
from app.montage.edl import EDL, Broll, Cut, Source


def _shotlist(*ids: int) -> list[dict]:
    return [{"i": i, "action": f"action {i}"} for i in ids]


def _fmap(vision_ok: bool, matched: list[tuple[int, float]]) -> dict:
    """A FootageMap-shaped dict whose shots matched the given (shot_index, confidence)."""
    return {
        "vision_ok": vision_ok,
        "shots": [{"matched_shot_index": mi, "confidence": c} for mi, c in matched],
    }


# --- select_broll_shots --------------------------------------------------------------------


def test_select_skips_when_vision_unreliable() -> None:
    # vision_ok False → we have NO coverage signal, so we must never fabricate misses.
    fmap = _fmap(False, [])
    assert select_broll_shots(fmap, _shotlist(1, 2, 3)) == []


def test_select_full_coverage_adds_middle_inserts() -> None:
    # Full coverage no longer means zero b-roll: pro edits cut away over a fluent
    # talking-head, so alternate MIDDLE shots get inserts (never the hook/CTA).
    fmap = _fmap(True, [(1, 1.0), (2, 1.0), (3, 1.0)])
    out = select_broll_shots(fmap, _shotlist(1, 2, 3))
    assert [s["shot_index"] for s in out] == [2]


def test_select_returns_uncovered_shots() -> None:
    fmap = _fmap(True, [(1, 1.0), (3, 1.0)])  # shot 2 has no footage
    out = select_broll_shots(fmap, _shotlist(1, 2, 3))
    assert [s["shot_index"] for s in out] == [2]
    assert out[0]["action"] == "action 2"


def test_select_low_confidence_match_is_not_coverage() -> None:
    fmap = _fmap(True, [(1, 0.2)])  # matched but below the 0.5 floor → still uncovered
    out = select_broll_shots(fmap, _shotlist(1))
    assert [s["shot_index"] for s in out] == [1]


def test_select_respects_max_shots() -> None:
    fmap = _fmap(True, [])  # nothing covered, but vision_ok so the signal is trusted
    out = select_broll_shots(fmap, _shotlist(1, 2, 3, 4, 5, 6), max_shots=2)
    assert len(out) == 2


def test_select_ignores_shots_without_action() -> None:
    fmap = _fmap(True, [])
    out = select_broll_shots(fmap, [{"i": 1, "action": ""}, {"i": 2, "action": "ok"}])
    assert [s["shot_index"] for s in out] == [2]


# --- select_reject_shots (Stage 9b Faza 3 — footage bad-take cutting) ----------------------


def _fmap_spans(vision_ok: bool, shots: list[tuple[int, float, float, float]]) -> dict:
    """FootageMap with (matched_shot_index, confidence, src_start, src_end) per shot."""
    return {
        "vision_ok": vision_ok,
        "shots": [
            {"matched_shot_index": mi, "confidence": c, "src_start": ss, "src_end": se}
            for mi, c, ss, se in shots
        ],
    }


def test_reject_skips_when_vision_unreliable() -> None:
    fmap = _fmap_spans(False, [(0, 1.0, 0.0, 2.0), (1, 1.0, 2.0, 4.0), (2, 1.0, 4.0, 6.0)])
    assert select_reject_shots(fmap, _shotlist(1, 2)) == []


def test_reject_drops_unmatched_shot_when_majority_matched() -> None:
    # 2 of 3 shots matched the storyboard well → the unmatched one (shot at 2-4s) is a real outtake.
    fmap = _fmap_spans(True, [(1, 1.0, 0.0, 2.0), (0, 1.0, 2.0, 4.0), (2, 1.0, 4.0, 6.0)])
    assert select_reject_shots(fmap, _shotlist(1, 2)) == [(2.0, 4.0)]


def test_reject_skips_when_alignment_weak() -> None:
    # Only 1 of 3 matched → vision alignment isn't trustworthy → never cut (could be a vision miss).
    fmap = _fmap_spans(True, [(0, 1.0, 0.0, 2.0), (0, 1.0, 2.0, 4.0), (1, 1.0, 4.0, 6.0)])
    assert select_reject_shots(fmap, _shotlist(1)) == []


def test_reject_skips_too_few_shots() -> None:
    fmap = _fmap_spans(True, [(1, 1.0, 0.0, 2.0), (0, 1.0, 2.0, 4.0)])
    assert select_reject_shots(fmap, _shotlist(1)) == []


def test_reject_never_cuts_more_than_half() -> None:
    # 2 matched, 2 unmatched (exactly half unmatched is allowed; >half is refused). Here 3 unmatched
    # of 5 = more than half → refuse entirely (a misfire shouldn't gut the take).
    fmap = _fmap_spans(
        True,
        [(1, 1.0, 0, 2), (2, 1.0, 2, 4), (0, 1.0, 4, 6), (0, 1.0, 6, 8), (0, 1.0, 8, 10)],
    )
    # only 2 matched of 5 → majority gate already fails → []
    assert select_reject_shots(fmap, _shotlist(1, 2)) == []


# --- resolve_broll (Pexels monkeypatched — no network) -------------------------------------


def _edl_two_shots() -> EDL:
    return EDL(
        task_id="t",
        tenant_id="tn",
        source=Source(upload_key="k", duration_sec=6.0),
        cuts=[
            Cut(src_start=0.0, src_end=3.0, shot_index=1),
            Cut(src_start=3.0, src_end=6.0, shot_index=2),
        ],
    )


def test_resolve_empty_plan_is_noop() -> None:
    edl = _edl_two_shots()
    assert resolve_broll(edl, [], "/tmp") == 0
    assert edl.broll == []


def test_resolve_places_broll_on_shot_output_window(tmp_path, monkeypatch) -> None:
    def fake_search(query: str, *, min_dur: float = 2.0) -> str:
        return "http://example/clip.mp4"

    def fake_download(url: str, dest: str, **_: object) -> bool:
        with open(dest, "wb") as fh:
            fh.write(b"x")
        return True

    monkeypatch.setattr("app.montage.broll.search_vertical_video", fake_search)
    monkeypatch.setattr("app.montage.broll.download_video", fake_download)

    # A 3-shot / 9s timeline so a single 2.5s cutaway fits under the 35% coverage budget
    # (a 6s reel would rightly reject a 2.5s b-roll = 42% coverage — tested separately).
    edl = EDL(
        task_id="t", tenant_id="tn", source=Source(upload_key="k", duration_sec=9.0),
        cuts=[
            Cut(src_start=0.0, src_end=3.0, shot_index=1),
            Cut(src_start=3.0, src_end=6.0, shot_index=2),
            Cut(src_start=6.0, src_end=9.0, shot_index=3),
        ],
    )
    n = resolve_broll(edl, [{"shot_index": 2, "query": "cash"}], str(tmp_path))
    assert n == 1
    b = edl.broll[0]
    # shot 2 occupies OUTPUT [3,6] (3s) → the overlay is a SHORT cutaway at the shot start,
    # capped to _BROLL_MAX_SEC so the speaker fills the rest of the shot (not a full cover).
    from app.montage.broll import _BROLL_MAX_SEC
    assert b.shot_index == 2
    assert b.at_sec == pytest.approx(3.0)
    assert b.output_dur_sec == pytest.approx(min(3.0, _BROLL_MAX_SEC))
    assert b.placement == "overlay"
    assert b.provider == "pexels"
    assert b.asset_url and os.path.exists(b.asset_url)


def test_resolve_skips_shot_with_no_output_block(tmp_path, monkeypatch) -> None:
    # shot 9 isn't in the storyboard cuts → no OUTPUT home → must be skipped, no network call.
    called = {"search": False}

    def fake_search(*a: object, **k: object) -> str:
        called["search"] = True
        return "http://x"

    monkeypatch.setattr("app.montage.broll.search_vertical_video", fake_search)
    edl = _edl_two_shots()
    assert resolve_broll(edl, [{"shot_index": 9, "query": "x"}], str(tmp_path)) == 0
    assert called["search"] is False
    assert edl.broll == []


def test_resolve_download_failure_skips(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.montage.broll.search_vertical_video", lambda *a, **k: "http://x")
    monkeypatch.setattr("app.montage.broll.download_video", lambda *a, **k: False)
    edl = _edl_two_shots()
    assert resolve_broll(edl, [{"shot_index": 1, "query": "x"}], str(tmp_path)) == 0
    assert edl.broll == []


# --- _renderable_broll (render-side guard) -------------------------------------------------


def test_renderable_broll_filters_unusable(tmp_path) -> None:
    real = os.path.join(str(tmp_path), "real.mp4")
    with open(real, "wb") as fh:
        fh.write(b"x")
    edl = _edl_two_shots()
    edl.broll = [
        Broll(shot_index=1, placement="overlay", asset_url=real, at_sec=0.0, output_dur_sec=3.0),
        Broll(shot_index=2, placement="segment", asset_url=real, at_sec=3.0, output_dur_sec=3.0),  # not overlay
        Broll(shot_index=2, placement="overlay", asset_url="/no/such.mp4", at_sec=3.0, output_dur_sec=3.0),  # missing file
        Broll(shot_index=1, placement="overlay", asset_url=real, at_sec=None, output_dur_sec=3.0),  # unplaced
    ]
    out = _renderable_broll(edl)
    assert len(out) == 1
    assert out[0].shot_index == 1 and out[0].at_sec == 0.0


# --- _broll_window (speaker-first coverage budget) -----------------------------------------


def test_broll_window_caps_full_shot_to_a_cutaway() -> None:
    from app.montage.broll import _BROLL_MAX_SEC, _broll_window
    # A 7s shot must NOT yield a 7s full-shot cover — capped to a short accent cutaway.
    assert _broll_window(7.0, 30.0, 0.0) == _BROLL_MAX_SEC


def test_broll_window_honors_coverage_budget() -> None:
    from app.montage.broll import _BROLL_MAX_COVERAGE, _broll_window
    out_total = 20.0
    budget = out_total * _BROLL_MAX_COVERAGE  # 7.0s of 20s
    # Already used most of the budget → a new 2.5s window would blow it → rejected.
    assert _broll_window(3.0, out_total, budget - 0.5) is None
    # Fresh budget → allowed.
    assert _broll_window(3.0, out_total, 0.0) is not None


def test_broll_window_rejects_too_short() -> None:
    from app.montage.broll import _broll_window
    assert _broll_window(0.3, 30.0, 0.0) is None


def test_generic_broll_queries_dropped() -> None:
    from app.graphs.nodes.broll_curator import _is_generic_query
    # Talking-person queries duplicate the real speaker → dropped.
    assert _is_generic_query("person talking to camera")
    assert _is_generic_query("person offering free subscription")
    assert _is_generic_query("woman speaking")
    # Concrete external visuals → kept.
    assert not _is_generic_query("trading chart on screen")
    assert not _is_generic_query("robot arm assembling")
    assert not _is_generic_query("stock market graph")

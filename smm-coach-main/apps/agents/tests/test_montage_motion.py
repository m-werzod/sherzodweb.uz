"""Ken Burns motion filter — string shape (the render itself is container-tested)."""
from __future__ import annotations

from app.montage.compiler import _cut_motion
from app.montage.edl import EDL, Cut, Motion, Source
from app.montage.motion import _ease, glitch, ken_burns, shake, zoom_punch
from app.montage.timing import build_motion


def test_zoom_in_pushes_crop_from_wide_to_tight() -> None:
    f = ken_burns(3.0, zoom_in=True)
    assert "scale=1166:2074," in f  # pre-scale by ~8%
    assert "1166-86*min(t/3.000\\,1)" in f  # width shrinks → push-in
    assert f.endswith("scale=1080:1920,setsar=1")


def test_zoom_out_grows_crop() -> None:
    f = ken_burns(2.0, zoom_in=False)
    assert "1080+86*min(t/2.000\\,1)" in f  # width grows → pull-out


def test_short_duration_is_clamped() -> None:
    # duration 0 would divide by zero in the progress expr — clamp to 0.1.
    f = ken_burns(0.0)
    assert "min(t/0.100\\,1)" in f


# --- Faza 2b: EDL-driven motion (zoom_punch from the storyboard) ---------

# shot 1 OUTPUT [0,5], shot 2 OUTPUT [5,10].
_CUTS = [
    Cut(src_start=0.0, src_end=5.0, shot_index=1),
    Cut(src_start=10.0, src_end=15.0, shot_index=2),
]


def _edl(cuts: list[Cut], motion: list[Motion]) -> EDL:
    return EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"), cuts=cuts, motion=motion)


def test_zoom_punch_filter_is_well_formed() -> None:
    f = zoom_punch(3.0)
    assert f.startswith("scale=")
    assert "crop=" in f
    assert f.endswith("setsar=1")
    assert "min(t/0.350\\,1)" in f  # snaps over the punch window then holds


def test_zoom_punch_keeps_a_hold_phase_on_short_cuts() -> None:
    # On a 0.4s cut the punch must not exceed half (0.2s) so a hold phase remains.
    assert "min(t/0.200\\,1)" in zoom_punch(0.4)


def test_zoom_vfx_becomes_motion_on_shot_span() -> None:
    shot_list = [
        {"i": 1, "vfx": [{"type": "zoom"}]},
        {"i": 2, "vfx": [{"type": "cut"}]},  # not a zoom → default ken-burns
    ]
    ms = build_motion(_CUTS, shot_list)
    zooms = [m for m in ms if m.op == "zoom_punch"]
    assert len(zooms) == 1
    assert zooms[0].at_sec == 0.0  # shot 1 OUTPUT start
    assert zooms[0].dur == 5.0
    # shot 2's cut is not zoomed → it now carries an explicit default ken-burns entry.
    assert any(m.op == "kenburns" for m in ms)


def test_one_punch_per_shot_even_with_multiple_zoom_vfx() -> None:
    shot_list = [{"i": 1, "vfx": [{"type": "zoom"}, {"type": "zoom_punch"}]}]
    ms = build_motion(_CUTS, shot_list)
    assert len([m for m in ms if m.op == "zoom_punch"]) == 1


def test_build_motion_default_kenburns_per_uncovered_cut() -> None:
    # No zoom planned → every cut gets an explicit ken-burns entry (was [] before; the drift was
    # implicit at render). No cuts → still nothing.
    ms = build_motion(_CUTS, [{"i": 1, "vfx": [{"type": "text_overlay", "text": "x"}]}])
    assert len(ms) == 2 and all(m.op == "kenburns" for m in ms)
    assert build_motion([], [{"i": 1, "vfx": [{"type": "zoom"}]}]) == []


def test_default_kenburns_entries_render_byte_identical_to_old_i2_default() -> None:
    # build_motion now bakes the per-cut drift into the EDL; _cut_motion must render it IDENTICALLY
    # to the old i%2 default (ffmpeg export unchanged — only STUDIO now sees the same drift).
    cuts = [Cut(src_start=0.0, src_end=2.0), Cut(src_start=2.0, src_end=4.0)]
    ms = build_motion(cuts, [])
    edl = _edl(cuts, ms)
    assert _cut_motion(edl, 0) == ken_burns(2.0, zoom_in=True)   # idx 0 → zoom-in
    assert _cut_motion(edl, 1) == ken_burns(2.0, zoom_in=False)  # idx 1 → zoom-out


def test_planned_zoom_wins_over_default_kenburns() -> None:
    # A cut under a planned zoom_punch must render the punch, not the default ken-burns, even though
    # build_motion may also have considered it.
    shot_list = [{"i": 1, "vfx": [{"type": "zoom"}]}]
    ms = build_motion(_CUTS, shot_list)
    edl = _edl(_CUTS, ms)
    assert _cut_motion(edl, 0) == zoom_punch(5.0)  # cut 0 = shot 1 = planned punch


def test_cut_motion_uses_zoom_punch_only_for_targeted_cut() -> None:
    # zoom_punch at OUTPUT 0.0 targets cut 0 (span [0,5]); cut 1 (span [5,10]) keeps ken-burns.
    edl = _edl(_CUTS, [Motion(op="zoom_punch", at_sec=0.0, dur=5.0)])
    assert _cut_motion(edl, 0) == zoom_punch(5.0)
    assert _cut_motion(edl, 1) != zoom_punch(5.0)
    assert "scale=" in _cut_motion(edl, 1)  # still a valid ken-burns filter


def test_cut_motion_targets_second_cut_by_output_time() -> None:
    edl = _edl(_CUTS, [Motion(op="zoom_punch", at_sec=6.0, dur=5.0)])  # 6.0 in cut 1 span [5,10]
    assert _cut_motion(edl, 0) != zoom_punch(5.0)  # cut 0 unaffected
    assert _cut_motion(edl, 1) == zoom_punch(5.0)


def test_cut_motion_default_when_no_edl_motion() -> None:
    edl = _edl(_CUTS, [])
    assert "crop=" in _cut_motion(edl, 0)  # ken-burns default everywhere
    assert _cut_motion(edl, 0) != zoom_punch(5.0)


def test_short_cuts_get_gentler_zoom() -> None:
    import re

    def scale_w(f: str) -> int:
        m = re.match(r"scale=(\d+):", f)
        assert m is not None
        return int(m.group(1))

    # a 0.2s cut pre-scales less than a 2s cut (less zoom → no few-frame snap/jitter).
    assert scale_w(ken_burns(0.2)) < scale_w(ken_burns(2.0))
    assert scale_w(zoom_punch(0.2)) < scale_w(zoom_punch(2.0))
    # cuts >= 0.5s keep the full zoom (no regression).
    assert scale_w(ken_burns(0.5)) == scale_w(ken_burns(5.0))


# --- palmier #4: easing curves drive the (previously dead) Motion.easing field ----------

def test_ease_linear_is_identity() -> None:
    assert _ease("P", "linear") == "P"
    assert _ease("P", "") == "P"
    assert _ease("P", "bogus") == "P"  # unknown → linear, never breaks the filter


def test_ease_curve_forms() -> None:
    assert _ease("P", "ease-out") == "(P)*(2-(P))"
    assert _ease("P", "ease-in") == "(P)*(P)"
    assert _ease("P", "ease-in-out") == "(P)*(P)*(3-2*(P))"
    assert _ease("P", "smooth") == "(P)*(P)*(3-2*(P))"


def test_ken_burns_default_drift_stays_byte_identical() -> None:
    # The safe default Ken-Burns drift must NOT change (no easing applied) — no baseline regression.
    f = ken_burns(3.0, zoom_in=True)
    assert "1166-86*min(t/3.000\\,1)" in f
    assert "(2-(" not in f


def test_ken_burns_eased_decelerates() -> None:
    assert "(min(t/3.000\\,1))*(2-(min(t/3.000\\,1)))" in ken_burns(3.0, easing="ease-out")


def test_zoom_punch_default_eases_out() -> None:
    # The storyboard punch now settles softly into the hold (ease-out) instead of stopping dead.
    assert "(min(t/0.350\\,1))*(2-(min(t/0.350\\,1)))" in zoom_punch(3.0)


def test_cut_motion_honours_motion_easing() -> None:
    edl = _edl(_CUTS, [Motion(op="zoom_punch", at_sec=0.0, dur=5.0, easing="ease-in-out")])
    assert "(3-2*(" in _cut_motion(edl, 0)  # smoothstep applied from the EDL's easing field


# --- Stage 9b: vfx (shake/glitch) now RENDER (were a silent no-op) ----------------------------


def test_shake_builds_animated_crop() -> None:
    f = shake(1.0)
    assert f.startswith("scale=") and "crop=w=1080:h=1920" in f and f.endswith("setsar=1")
    assert "sin(2*PI*8.00*t)" in f and "cos(2*PI*8.00*t)" in f  # animated position, decays over cut
    # No bare comma inside the sinusoid expression (would corrupt the filtergraph).
    crop_expr = f.split("crop=", 1)[1]
    assert ",1)" not in crop_expr and "min(" not in crop_expr


def test_glitch_uses_core_filters_only() -> None:
    f = glitch(0.5)
    assert "rgbashift=rh=6:bh=-6" in f  # chromatic split
    assert "noise=alls=14:allf=t" in f  # temporal film noise
    assert f.endswith("scale=1080:1920,setsar=1")


def test_glitch_renders_instead_of_noop() -> None:
    # A planned glitch on cut 0 (OUTPUT span [0,5)) now reaches the filtergraph.
    edl = _edl(_CUTS, [Motion(op="glitch", at_sec=1.0, dur=0.6)])
    assert "rgbashift" in _cut_motion(edl, 0)


def test_zoom_and_glitch_compose_on_same_cut() -> None:
    edl = _edl(_CUTS, [Motion(op="zoom_punch", at_sec=0.2, dur=5.0), Motion(op="glitch", at_sec=1.0, dur=0.6)])
    chain = _cut_motion(edl, 0)
    assert "crop=w='" in chain  # zoom_punch's shrinking crop kept
    assert "rgbashift" in chain  # AND the glitch chained after it
    assert chain.index("crop=w='") < chain.index("rgbashift")  # framing first, vfx after


def test_shake_only_keeps_default_framing_then_chains() -> None:
    edl = _edl(_CUTS, [Motion(op="shake", at_sec=1.0, dur=2.0)])
    chain = _cut_motion(edl, 0)
    assert chain.startswith(ken_burns(5.0, zoom_in=True))  # default framing preserved
    assert chain.count("crop=") >= 2  # ken-burns crop + shake crop


def test_vfx_outside_window_ignored_default_byte_identical() -> None:
    # glitch planned at OUTPUT 6.0 (cut 1) must not touch cut 0 → byte-identical ken-burns default.
    edl = _edl(_CUTS, [Motion(op="glitch", at_sec=6.0, dur=0.5)])
    assert _cut_motion(edl, 0) == ken_burns(5.0, zoom_in=True)
    assert "rgbashift" not in _cut_motion(edl, 0)

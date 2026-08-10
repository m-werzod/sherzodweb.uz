"""Faza 2a — render the storyboard's planned on-screen text. build_overlays maps
shotList[].vfx (type=text_overlay) onto the OUTPUT timeline via cut.shot_index, and render_ass
burns them as extra ASS lines (no filtergraph change). Lock the mapping + the .ass output."""
from __future__ import annotations

from pathlib import Path

from app.montage.captions import _ass_time, _hex_to_ass, render_ass
from app.montage.edl import Captions, Cut, Overlay
from app.montage.timing import build_overlays

# shot 1 occupies OUTPUT [0,5], shot 2 OUTPUT [5,10].
_CUTS = [
    Cut(src_start=0.0, src_end=5.0, shot_index=1),
    Cut(src_start=10.0, src_end=15.0, shot_index=2),
]


def test_text_overlay_vfx_becomes_output_timed_overlay() -> None:
    shot_list = [
        {"i": 1, "vfx": [{"type": "text_overlay", "atSec": 1.0, "text": "Salom", "position": "top"}]},
        {"i": 2, "vfx": [{"type": "cut"}]},  # not a text_overlay → ignored
    ]
    ovs = build_overlays(_CUTS, shot_list)
    assert len(ovs) == 1
    assert ovs[0].text == "Salom"
    assert ovs[0].position == "top"
    assert ovs[0].at_sec == 1.0  # shot 1 OUTPUT start (0) + atSec 1.0
    assert ovs[0].dur == 2.5


def test_overlay_at_sec_clamped_into_shot_span() -> None:
    # atSec beyond the shot's OUTPUT span [0,5] clamps to (shot_end - 0.4); at+dur <= shot_end.
    shot_list = [{"i": 1, "vfx": [{"type": "text_overlay", "atSec": 99.0, "text": "X"}]}]
    ovs = build_overlays(_CUTS, shot_list)
    assert ovs[0].at_sec == 4.6
    assert ovs[0].dur == 0.4
    assert ovs[0].at_sec + ovs[0].dur <= 5.0  # never past the shot/output end


def test_overlay_for_second_shot_offsets_from_its_output_start() -> None:
    shot_list = [{"i": 2, "vfx": [{"type": "text_overlay", "atSec": 0.5, "text": "Ikki"}]}]
    ovs = build_overlays(_CUTS, shot_list)
    assert ovs[0].at_sec == 5.5  # shot 2 OUTPUT start (5) + 0.5


def test_empty_text_and_unknown_shot_skipped() -> None:
    shot_list = [
        {"i": 1, "vfx": [{"type": "text_overlay", "text": "   "}]},  # blank text
        {"i": 9, "vfx": [{"type": "text_overlay", "text": "Yo'q"}]},  # shot not in cuts
    ]
    assert build_overlays(_CUTS, shot_list) == []


def test_no_cuts_or_no_shotlist_is_empty() -> None:
    assert build_overlays([], [{"i": 1, "vfx": [{"type": "text_overlay", "text": "x"}]}]) == []
    assert build_overlays(_CUTS, []) == []


def test_hex_to_ass_bgr_order() -> None:
    assert _hex_to_ass("#FFFFFF") == "&H00FFFFFF&"
    assert _hex_to_ass("#FF0000") == "&H000000FF&"  # red: BBGGRR
    assert _hex_to_ass("#00FF00") == "&H0000FF00&"
    assert _hex_to_ass("nope") == "&H00FFFFFF&"  # malformed → white


def test_render_ass_emits_overlay_dialogue(tmp_path: Path) -> None:
    dst = str(tmp_path / "c.ass")
    overlays = [
        Overlay(template="title", at_sec=1.0, dur=2.0, text="Salom dunyo",
                position="bottom", color="#00FF00"),
    ]
    # Face-aware layout: the planner's position is overridden by the face zone —
    # face at the top pushes ALL overlays to the bottom row.
    render_ass(Captions(), dst, overlays=overlays, face_zone="top")
    content = Path(dst).read_text(encoding="utf-8")
    assert "Style: Over," in content
    assert "Salom dunyo" in content
    assert "\\an2" in content  # bottom alignment (opposite of the face)
    assert "&H0000FF00&" in content  # green, BGR-ordered
    assert "Dialogue: 1," in content  # overlay layer above captions


def test_non_contiguous_same_shot_uses_first_block() -> None:
    # cuts: shot1[0,2], shot2[2,4], shot1[4,6] — the second shot-1 block must NOT extend
    # shot1's span across shot2 (review BUG #1). Overlay for shot1 stays in its first block.
    cuts = [
        Cut(src_start=0.0, src_end=2.0, shot_index=1),
        Cut(src_start=10.0, src_end=12.0, shot_index=2),
        Cut(src_start=20.0, src_end=22.0, shot_index=1),
    ]
    ovs = build_overlays(cuts, [{"i": 1, "vfx": [{"type": "text_overlay", "atSec": 0.0, "text": "A"}]}])
    assert len(ovs) == 1
    assert ovs[0].at_sec + ovs[0].dur <= 2.0  # first block [0,2], never into shot2's [2,4]


def test_tiny_shot_overlay_stays_in_bounds() -> None:
    # A sub-0.4s shot must not push the overlay before shot_start or past shot_end (BUG #2/#3).
    cuts = [Cut(src_start=0.0, src_end=0.2, shot_index=1)]  # OUTPUT [0, 0.2]
    ovs = build_overlays(cuts, [{"i": 1, "vfx": [{"type": "text_overlay", "atSec": 0.0, "text": "T"}]}])
    assert len(ovs) == 1
    assert ovs[0].at_sec >= 0.0
    assert ovs[0].at_sec + ovs[0].dur <= 0.2 + 1e-9


def test_overlay_color_extracted_from_vfx() -> None:
    shot_list = [{"i": 1, "vfx": [{"type": "text_overlay", "text": "C", "color": "#FF0000"}]}]
    ovs = build_overlays(_CUTS, shot_list)
    assert ovs[0].color == "#FF0000"


def test_ass_time_propagates_rounding_carry() -> None:
    # cs rounding to 100 must carry up the units, never emit a 60 (review CRITICAL).
    assert _ass_time(59.999) == "0:01:00.00"
    assert _ass_time(3599.999) == "1:00:00.00"
    assert _ass_time(119.999) == "0:02:00.00"
    assert _ass_time(2.5) == "0:00:02.50"


def test_render_ass_no_overlays_still_valid(tmp_path: Path) -> None:
    dst = str(tmp_path / "c.ass")
    render_ass(Captions(), dst)  # overlays default None
    content = Path(dst).read_text(encoding="utf-8")
    assert "Style: Over," in content  # style always present; just no Over Dialogue lines
    assert "[Events]" in content

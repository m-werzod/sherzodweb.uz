from __future__ import annotations

from app.graphs.nodes.scriptwriter import (
    SYSTEM_PROMPT_RICH,
    _parse_carousel_md_to_timeline,
    _validate_rich,
)


def test_rich_prompt_enforces_grounding_and_psych() -> None:
    # The anti-fabrication rule keys off `grounding`, and the prompt now consumes
    # psych_profile + brand_voice for tone.
    assert "grounding" in SYSTEM_PROMPT_RICH
    assert "psych_profile" in SYSTEM_PROMPT_RICH
    assert "brand_voice" in SYSTEM_PROMPT_RICH


def test_carousel_timeline_parses_slides_not_caption_garbage() -> None:
    md = (
        "SLAYD 1: 500$ dan 16 500$ gacha — bitta proyekt hikoyasi\n"
        "qisqacha hook matni\n\n"
        "SLAYD 2: Muammo nima edi\n"
        "**bold** bozorda raqobat baland\n\n"
        "SLAYD 3: Yechim va natija\n"
    )
    tl = _parse_carousel_md_to_timeline(md)
    assert [r["t"] for r in tl] == ["Slayd 1", "Slayd 2", "Slayd 3"]
    # No leaked markdown markers, real slide body captured.
    assert all("**" not in r["text"] for r in tl)
    assert "16 500" in tl[0]["text"]
    assert tl[1]["cue"] == "Slayd"


def test_carousel_timeline_empty_when_no_slides() -> None:
    # Better an empty timeline than caption-scraped nonsense.
    assert _parse_carousel_md_to_timeline("Oddiy post matni, slayd yo'q.") == []
    assert _parse_carousel_md_to_timeline("") == []


def test_carousel_timeline_blank_line_separated_no_heading_leak() -> None:
    # LLMs overwhelmingly put a BLANK line between slide sections. The heading
    # marker ("SLAYD N:") and its text must NOT leak/duplicate into the body.
    md = (
        "\n"  # leading blank line (also must not corrupt slide 1)
        "SLAYD 1: 500$ dan 16 500$ gacha\n"
        "hook davomi matni\n\n"
        "SLAYD 2: Muammo nima edi\n"
        "bozorda raqobat baland\n\n"
        "SLAYD 3: Yechim va natija\n"
    )
    tl = _parse_carousel_md_to_timeline(md)
    assert [r["t"] for r in tl] == ["Slayd 1", "Slayd 2", "Slayd 3"]
    for r in tl:
        assert "SLAYD" not in r["text"].upper(), r["text"]  # no marker leak
    assert tl[0]["text"] == "500$ dan 16 500$ gacha hook davomi matni"
    assert tl[1]["text"] == "Muammo nima edi bozorda raqobat baland"


def test_rich_prompt_defines_a_beat_skeleton_per_reeltype() -> None:
    # reelType must drive STRUCTURE, not just be a tag — the prompt now carries a beat-skeleton for
    # every supported type so the script/shotList follow the right shape.
    assert "BEAT-SKELET" in SYSTEM_PROMPT_RICH
    for rt in ("talking_head", "tutorial", "listicle", "story", "pov", "skit", "broll_voiceover", "day_in_life"):
        assert rt in SYSTEM_PROMPT_RICH, rt


def _deep() -> dict:
    shots = [{"i": i, "framing": "MS", "camera": "eye-level", "duration_s": 3} for i in range(1, 7)]
    return {
        "type": "reel",
        "script_timeline": [{"t": str(i), "text": "x"} for i in range(6)],
        "shot_list": shots,
        "reelType": "talking_head",
        "hookVariantB": "B hook",
        "musicCues": [{"atSec": 0, "event": "start"}],
    }


def test_deep_task_has_no_gaps() -> None:
    assert _validate_rich(_deep()) == []


def test_action_task_is_exempt() -> None:
    assert _validate_rich({"type": "action", "shot_list": [], "script_timeline": []}) == []


def test_shallow_task_reports_every_gap() -> None:
    joined = " ".join(_validate_rich({"type": "reel", "script_timeline": [], "shot_list": []}))
    for token in ("scriptTimeline", "shotList", "reelType", "hookVariantB", "musicCues"):
        assert token in joined


def test_undirected_shots_flagged_but_others_ok() -> None:
    shots = [{"i": i, "action": "umumiy tavsif"} for i in range(1, 7)]
    gaps = _validate_rich(
        {
            "type": "reel",
            "script_timeline": [{"t": str(i), "text": "x"} for i in range(6)],
            "shot_list": shots,
            "reelType": "pov",
            "hookVariantB": "b",
            "musicCues": [{"atSec": 0}],
        }
    )
    assert any("rejissyorligi" in g for g in gaps)
    assert all("reelType" not in g and "musicCues" not in g for g in gaps)

"""ASS caption rendering — premium karaoke sweep vs cheap window tier."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.montage.captions import render_ass
from app.montage.edl import Captions, CaptionStyle, CaptionWindow, CaptionWord

if TYPE_CHECKING:
    from pathlib import Path


def _caps(tier: str) -> Captions:
    win = CaptionWindow(
        words=[
            CaptionWord(text="Bugun", start=0.0, end=0.4),
            CaptionWord(text="oʻzgarish", start=0.4, end=1.0),  # raw U+02BB
            CaptionWord(text="boshlandi", start=1.0, end=1.6),
        ]
    )
    return Captions(tier=tier, style=CaptionStyle(), windows=[win])


def test_premium_emits_karaoke_and_active_primary(tmp_path: Path) -> None:
    out = tmp_path / "p.ass"
    render_ass(_caps("premium"), str(out))
    body = out.read_text(encoding="utf-8")
    assert "\\kf" in body  # karaoke sweep tags present
    # PrimaryColour is the accent (active) colour in premium karaoke.
    assert "Style: Cap,Montserrat,104,&H0000D7FF,&H00FFFFFF" in body
    # apostrophe normalized to ASCII in the burned text.
    assert "o'zgarish" in body
    assert "oʻzgarish" not in body


def test_cheap_is_plain_window(tmp_path: Path) -> None:
    out = tmp_path / "c.ass"
    render_ass(_caps("cheap"), str(out))
    body = out.read_text(encoding="utf-8")
    assert "\\kf" not in body  # no karaoke
    # whole phrase on one Dialogue line.
    assert "Bugun o'zgarish boshlandi" in body
    # white primary in cheap tier.
    assert "Style: Cap,Montserrat,104,&H00FFFFFF,&H00FFFFFF" in body


def test_premium_word_durations_match_centiseconds(tmp_path: Path) -> None:
    out = tmp_path / "d.ass"
    render_ass(_caps("premium"), str(out))
    body = out.read_text(encoding="utf-8")
    # 0.4s -> 40cs, 0.6s -> 60cs.
    assert "{\\kf40}Bugun" in body
    assert "{\\kf60}" in body


def test_hook_overlay_burns_on_its_own_layer(tmp_path: Path) -> None:
    out = tmp_path / "h.ass"
    render_ass(_caps("premium"), str(out), hook_text="Bu sirni biласizmi?")
    body = out.read_text(encoding="utf-8")
    assert "Style: Hook," in body  # the big top-third hook style exists
    assert "Dialogue: 1," in body  # rendered on layer 1, above the captions
    assert "\\fad(200,250)" in body  # fades in/out
    assert "Bu sirni biласizmi?" in body


def test_no_hook_when_absent(tmp_path: Path) -> None:
    out = tmp_path / "n.ass"
    render_ass(_caps("premium"), str(out))
    body = out.read_text(encoding="utf-8")
    assert "Dialogue: 1," not in body  # no hook layer when no hook text

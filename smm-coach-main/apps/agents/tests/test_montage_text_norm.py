"""Uzbek apostrophe normalization for burned captions — the tofu landmine."""
from __future__ import annotations

from app.montage.text_norm import ass_escape, normalize_apostrophes, normalize_caption_text


def test_all_apostrophe_variants_collapse_to_ascii() -> None:
    # U+02BB (correct Uzbek), smart quotes, prime, grave, acute → all ASCII '.
    src = "oʻzbek gʻalaba ‘x’ y′ z` w´"
    out = normalize_apostrophes(src)
    assert out == "o'zbek g'alaba 'x' y' z' w'"
    assert "ʻ" not in out


def test_normalize_caption_text_collapses_whitespace_and_controls() -> None:
    src = "  Bu\tyangi   post\x07  oʻzgardi  "
    out = normalize_caption_text(src)
    # apostrophe unified, control char dropped, whitespace single-spaced + trimmed.
    assert out == "Bu yangi post o'zgardi"
    assert "\x07" not in out


def test_ass_escape_neutralizes_override_syntax() -> None:
    assert ass_escape("{drop}") == "\\{drop\\}"
    assert ass_escape("a\\b") == "a/b"
    assert ass_escape("line1\nline2") == "line1\\Nline2"

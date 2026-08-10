"""Caption text normalization for burned ASS subtitles.

The Uzbek apostrophe landmine: oʻ/gʻ are written with several different code
points across the codebase (the "correct" U+02BB, smart quotes, a bare ASCII ').
libass renders whatever glyph the chosen font has — mix forms and you get curly
quotes next to straight ones, or tofu when the font lacks the glyph. We collapse
EVERY apostrophe variant to ONE ASCII form (U+0027), the form the rest of the
codebase already uses, and bundle a font that has it.
"""
from __future__ import annotations

# Every apostrophe-like code point that shows up in Uzbek Latin text → ASCII '.
_APOSTROPHES = {
    "ʻ",  # ʻ MODIFIER LETTER TURNED COMMA (the orthographically-correct one)
    "ʼ",  # ʼ MODIFIER LETTER APOSTROPHE
    "‘",  # ‘ LEFT SINGLE QUOTATION MARK
    "’",  # ’ RIGHT SINGLE QUOTATION MARK
    "′",  # ′ PRIME
    "`",  # ` GRAVE ACCENT
    "´",  # ´ ACUTE ACCENT
}
_APOSTROPHE_TABLE = {ord(ch): "'" for ch in _APOSTROPHES}


def normalize_apostrophes(text: str) -> str:
    """Collapse all apostrophe variants to a single ASCII apostrophe."""
    return text.translate(_APOSTROPHE_TABLE)


def normalize_caption_text(text: str) -> str:
    """Full caption cleanup: unify apostrophes, drop control chars, collapse
    whitespace to single spaces. Safe to run on every on-screen word."""
    text = normalize_apostrophes(text)
    # Drop non-whitespace control chars (e.g. \x07) that libass would choke on,
    # but KEEP whitespace controls (\t, \n) so .split() can use them as word
    # separators — dropping them first would merge adjacent words.
    cleaned = "".join(ch for ch in text if ch.isspace() or ch >= " ")
    return " ".join(cleaned.split())


def ass_escape(text: str) -> str:
    """Escape characters that are syntactically meaningful inside an ASS
    Dialogue line. `{` opens an override block and `\\` starts a tag — leaving
    them raw would silently swallow or corrupt the caption."""
    return (
        text.replace("\\", "/")  # a stray backslash could start a tag — neutralize
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")  # ASS hard line break
    )

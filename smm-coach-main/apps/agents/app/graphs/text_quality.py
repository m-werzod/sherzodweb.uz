"""Shared answer-quality heuristics.

The scriptwriter grounds a script on the user's Q&A answers. When those answers
are filler ("sen", "ha", "faqat sen borsan") the model would otherwise pad the
script with fabricated first-person claims ("men 2 yil oldin...") — the exact
"juda sayoz" failure the founder reported. These helpers detect thin input so
the interview can re-ask and the scriptwriter can switch to a generic, non-
fabricated voice instead of inventing a personal story.

Pure stdlib so it stays trivially unit-testable in isolation.
"""
from __future__ import annotations

import re

# Common single-token filler / deflection in Uzbek chat answers. Kept lowercase;
# matched after stripping punctuation. Not exhaustive — the length + count gate
# does most of the work; this only removes obvious non-content tokens.
_FILLER = {
    "sen", "san", "siz", "men", "meni", "sening", "seni",
    "ha", "haa", "aha", "ha'a", "yoq", "yo'q", "yoʻq", "ok", "okay", "okey",
    "mayli", "bilmayman", "bilmadim", "bilman", "shunchaki", "faqat", "borsan",
    "bor", "yaxshi", "zor", "nimadir", "hech", "narsa", "hmm", "uxum", "aa",
    "test", "salom", "qanaqa", "nima", "sanmi", "senmi",
}

# Word = letters/digits incl. Uzbek apostrophes and Cyrillic.
_WORD = re.compile(r"[0-9A-Za-zÀ-ɏЀ-ӿ'ʻʼ‘’]+")


def _answer_segments(text: str) -> list[str]:
    """When a transcript is passed in the "S: <savol> / J: <javob>" shape, keep
    only the user's answers (J:) so the AI's own questions don't inflate the
    count. A single answer may span multiple lines (Shift+Enter in the textarea,
    or voice transcription line breaks) — fold the continuation lines into that
    answer instead of dropping them (dropping them undercounts a rich answer and
    would flag a genuine interview as junk). Otherwise treat the whole string as
    one answer."""
    answers: list[str] = []
    cur: list[str] | None = None
    for ln in text.splitlines():
        low = ln.strip().lower()
        if low.startswith(("j:", "javob:")):
            if cur is not None:
                answers.append(" ".join(cur).strip())
            cur = [ln.split(":", 1)[1].strip()]
        elif low.startswith(("s:", "savol:")):
            # A question line closes the current answer and is itself excluded.
            if cur is not None:
                answers.append(" ".join(cur).strip())
                cur = None
        elif cur is not None and ln.strip():
            cur.append(ln.strip())
    if cur is not None:
        answers.append(" ".join(cur).strip())
    return answers if answers else [text]


def meaningful_word_count(text: str) -> int:
    """Count content words across the user's answers, dropping 1-2 char tokens
    and obvious filler."""
    total = 0
    for seg in _answer_segments(text or ""):
        for w in _WORD.findall(seg.lower()):
            if len(w) < 3 or w in _FILLER:
                continue
            total += 1
    return total


def is_substantive_answer(text: str, *, min_words: int = 12) -> bool:
    """True if the answer(s) carry enough real content to ground a script on.

    min_words=12 for a full interview transcript (a real interview yields dozens);
    pass a smaller floor (e.g. 4) to judge a single answer turn.
    """
    return meaningful_word_count(text) >= min_words

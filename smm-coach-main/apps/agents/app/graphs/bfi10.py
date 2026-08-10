"""Stage 1 — validated Big-Five instrument (BFI-10, Rammstedt & John 2007).

Ten short self-rating items, two per OCEAN dimension (one reverse-keyed), each
answered on a 1-5 Likert scale. Scoring is DETERMINISTIC — no LLM — so the
OCEAN numbers are psychometrically grounded instead of an LLM guess. The LLM is
then used ONLY for the narrative/archetype/voice, fed the real scores.

Pure module: items + score_bfi10() have no I/O, so they're fully unit-tested.
Uzbek item text (the onboarding renders 10 sliders). Agreement scale:
1 = mutlaqo qo'shilmayman … 5 = mutlaqo qo'shilaman.
"""
from __future__ import annotations

# Each item: id, Uzbek statement, OCEAN dimension, reverse-keyed?
# Reverse items are scored 6 - answer (a high agreement LOWERS the trait).
BFI_10_ITEMS: list[dict] = [
    {"id": "e_rev", "dim": "E", "reverse": True, "text": "Men o'zimni kamgap, ichki odam deb bilaman."},
    {"id": "a", "dim": "A", "reverse": False, "text": "Men odamlarga ishonaman, ularda yaxshilik ko'raman."},
    {"id": "c_rev", "dim": "C", "reverse": True, "text": "Men ba'zan dangasalik qilaman, ishni cho'zaman."},
    {"id": "n_rev", "dim": "N", "reverse": True, "text": "Men bosiqman, stressni yaxshi boshqaraman."},
    {"id": "o_rev", "dim": "O", "reverse": True, "text": "Menda badiiy/ijodiy qiziqishlar kam."},
    {"id": "e", "dim": "E", "reverse": False, "text": "Men ochiq, kirishimli, odamlar bilan oson til topaman."},
    {"id": "a_rev", "dim": "A", "reverse": True, "text": "Men boshqalarning kamchiligini tez ko'raman, tanqid qilaman."},
    {"id": "c", "dim": "C", "reverse": False, "text": "Men ishni puxta, oxiriga yetkazib bajaraman."},
    {"id": "n", "dim": "N", "reverse": False, "text": "Men tez asabiylashaman, hayajonga tushaman."},
    {"id": "o", "dim": "O", "reverse": False, "text": "Menda kuchli tasavvur, yangi g'oyalarga qiziqish bor."},
]

_BY_DIM: dict[str, list[dict]] = {}
for _it in BFI_10_ITEMS:
    _BY_DIM.setdefault(_it["dim"], []).append(_it)

_DIMS = ("O", "C", "E", "A", "N")


def _clamp_likert(v: object) -> int | None:
    try:
        n = int(round(float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 5 else None


def score_bfi10(answers: dict) -> dict:
    """Score raw 1-5 answers (keyed by item id) into OCEAN 0-100 + a confidence.

    Per dimension we average its (up to 2) valid items — reverse items flipped
    (6 - answer) — then map the 1-5 mean to 0-100. A dimension with no valid
    answer is omitted. `confidence` is 'high' only when ALL 10 items answered
    (a complete validated instrument), else 'medium', else (nothing) the caller
    keeps the LLM estimate.

    Returns {} when no item was answered (caller falls back to the LLM ocean).
    """
    if not isinstance(answers, dict):
        return {}

    out: dict[str, int] = {}
    answered = 0
    for dim in _DIMS:
        vals: list[int] = []
        for item in _BY_DIM[dim]:
            raw = _clamp_likert(answers.get(item["id"]))
            if raw is None:
                continue
            answered += 1
            vals.append(6 - raw if item["reverse"] else raw)
        if vals:
            mean = sum(vals) / len(vals)  # 1..5
            out[dim] = max(0, min(100, round((mean - 1) / 4 * 100)))

    if not out:
        return {}
    out["confidence"] = "high" if answered >= len(BFI_10_ITEMS) else "medium"  # type: ignore[assignment]
    return out

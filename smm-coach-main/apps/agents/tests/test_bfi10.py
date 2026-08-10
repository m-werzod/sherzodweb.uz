"""Stage 1 — BFI-10 deterministic OCEAN scoring."""
from __future__ import annotations

from app.graphs.bfi10 import BFI_10_ITEMS, score_bfi10


def _all(v: int) -> dict:
    return {it["id"]: v for it in BFI_10_ITEMS}


def test_ten_items_two_per_dimension():
    dims = {}
    for it in BFI_10_ITEMS:
        dims[it["dim"]] = dims.get(it["dim"], 0) + 1
    assert dims == {"O": 2, "C": 2, "E": 2, "A": 2, "N": 2}


def test_empty_returns_empty():
    assert score_bfi10({}) == {}
    assert score_bfi10(None) == {}  # type: ignore[arg-type]


def test_all_neutral_is_fifty_high_confidence():
    out = score_bfi10(_all(3))
    for d in ("O", "C", "E", "A", "N"):
        assert out[d] == 50
    assert out["confidence"] == "high"


def test_high_openness_via_mixed_keys():
    # Agree with "imagination" (o=5) + DISAGREE with "few artistic" (o_rev=1)
    # → both point to high O → 100.
    out = score_bfi10({"o": 5, "o_rev": 1})
    assert out["O"] == 100
    assert "C" not in out  # only O answered
    assert out["confidence"] == "medium"  # partial instrument


def test_low_openness():
    out = score_bfi10({"o": 1, "o_rev": 5})
    assert out["O"] == 0


def test_consistent_max_cancels_on_mixed_dims():
    # All 5s: each dim has one normal + one reverse → averages to neutral 50.
    out = score_bfi10(_all(5))
    for d in ("O", "C", "E", "A", "N"):
        assert out[d] == 50


def test_invalid_values_ignored():
    out = score_bfi10({"o": 0, "o_rev": 6, "e": "x", "e_rev": 4})  # type: ignore[dict-item]
    # o/o_rev invalid → O omitted; e invalid, e_rev=4(reverse)→2 → E from one item.
    assert "O" not in out
    assert out["E"] == round((2 - 1) / 4 * 100)  # == 25


def test_single_item_dim_scored():
    out = score_bfi10({"c": 5})
    assert out["C"] == 100
    assert out["confidence"] == "medium"

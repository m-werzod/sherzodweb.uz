"""Stage 9c informational VFX — deterministic numeric callouts. A stat in a shot's
action text (number + unit) becomes an on-screen text_pop overlay."""
from __future__ import annotations

from app.graphs.nodes.montage_director import numeric_callout_intents


def _shot(i, action):
    return {"i": i, "action": action}


def test_stat_with_unit_becomes_text_pop():
    out = numeric_callout_intents([_shot(1, "10 daqiqada post tayyor bo'ladi")])
    assert len(out) == 1
    assert out[0]["intent"] == "text_pop"
    assert out[0]["shot_index"] == 1
    assert "10" in out[0]["params"]["text"]
    assert "daqiqa" in out[0]["params"]["text"].lower()


def test_percentage_callout():
    out = numeric_callout_intents([_shot(2, "konversiya 50% oshdi")])
    assert len(out) == 1
    assert "50" in out[0]["params"]["text"]


def test_bare_number_without_unit_is_ignored():
    # "3 kadr" — a bare small count with no stat-unit shouldn't be highlighted.
    out = numeric_callout_intents([_shot(1, "shu yerda 3 narsani ko'rsataman")])
    assert out == []


def test_capped_and_deduped():
    shots = [
        _shot(1, "1000 obunachi yig'dim"),
        _shot(2, "yana 1000 obunachi"),  # duplicate label → skipped
        _shot(3, "har kuni 5 soat ishladim"),
        _shot(4, "20 marta sinadim"),
        _shot(5, "30 kun davomida"),  # would be 4th unique → over cap of 3
    ]
    out = numeric_callout_intents(shots, max_callouts=3)
    assert len(out) == 3
    # 1000 obunachi counted once (dedup), then 5 soat, 20 marta.
    assert sum(1 for o in out if "1000" in o["params"]["text"]) == 1


def test_no_stats_returns_empty():
    out = numeric_callout_intents([_shot(1, "salom, bugun gaplashamiz")])
    assert out == []

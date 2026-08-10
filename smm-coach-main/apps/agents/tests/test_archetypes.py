"""Stage 1 — deterministic 12-archetype OCEAN matcher. Pins that distinct OCEAN
profiles map to the expected archetype + the no-data default."""
from __future__ import annotations

from app.graphs.archetypes import match_archetype


def test_no_ocean_defaults_to_everyman():
    m = match_archetype(None)
    assert m["primary"] == "Everyman"
    assert m["secondary"] is None
    m2 = match_archetype({})
    assert m2["primary"] == "Everyman"


def test_high_openness_creativity_maps_to_creator():
    # High O + high C + mid rest → Creator is nearest.
    m = match_archetype({"O": 90, "C": 75, "E": 48, "A": 50, "N": 50})
    assert m["primary"] == "Creator"


def test_high_conscientiousness_low_openness_maps_to_ruler():
    m = match_archetype({"O": 35, "C": 88, "E": 64, "A": 45, "N": 38})
    assert m["primary"] == "Ruler"


def test_high_agreeableness_caregiver():
    m = match_archetype({"O": 52, "C": 70, "E": 55, "A": 90, "N": 35})
    assert m["primary"] == "Caregiver"


def test_returns_distinct_secondary_and_voice():
    m = match_archetype({"O": 80, "C": 45, "E": 70, "A": 42, "N": 45})
    assert m["primary"] and m["secondary"]
    assert m["primary"] != m["secondary"]
    assert m["tone"] and isinstance(m["antiVoice"], list) and m["antiVoice"]
    assert "primaryLabel" in m and m["primaryLabel"]

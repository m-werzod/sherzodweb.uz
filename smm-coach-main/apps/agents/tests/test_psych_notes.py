from __future__ import annotations

from app.graphs.nodes.initial_analysis import _build_psych_notes

_FULL = {
    "voice": {"label": "Iliq Donishmand", "archetypePrimary": "Sage",
              "archetypeSecondary": "Everyman", "antiVoice": ["quruq rasmiy"]},
    "motivation": {"whyStatement": "Odamlarga ishonch berish"},
    "values": {"core": ["o'sish", "halollik"], "philosophicalProblem": "SMM oddiy"},
    "originStory": {"catalyst": "0 dan boshladim", "transformation": "10K ga yetdim"},
    "audience": {"avatar": "28 yoshli tadbirkor", "internalPain": "havaskor ko'rinish"},
}


def test_full_profile_yields_four_notes():
    notes = _build_psych_notes(_FULL)
    titles = [t for t, _ in notes]
    assert titles == [
        "Brend ovozi va arxetip",
        "Why va qadriyatlar",
        "Origin story",
        "Auditoriya va og'riq",
    ]
    # bodies non-empty and carry the key facts
    body_by_title = dict(notes)
    assert "Sage" in body_by_title["Brend ovozi va arxetip"]
    assert "halollik" in body_by_title["Why va qadriyatlar"]


def test_empty_profile_yields_no_notes():
    assert _build_psych_notes({}) == []
    assert _build_psych_notes({"voice": {}, "audience": {}}) == []


def test_partial_profile_only_present_sections():
    notes = _build_psych_notes({"audience": {"avatar": "X"}})
    assert [t for t, _ in notes] == ["Auditoriya va og'riq"]

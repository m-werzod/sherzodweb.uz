"""Faza A4 trend-binding — trend_edits: recipe parsing + prompt hint (pure, DB kerak emas)."""
from __future__ import annotations

from app.montage.trend_edits import (
    EVERGREEN_RECIPE,
    EditRecipe,
    recipe_from_llm,
    recipe_from_metadata,
    recipe_prompt_hint,
    recipe_to_metadata,
)


def test_evergreen_prompt_hint_has_core_guidance() -> None:
    h = recipe_prompt_hint(EVERGREEN_RECIPE)
    assert "tempo" in h
    assert "intensivlik" in h.lower()
    assert "transition" in h  # evergreen transition_on_scene=True


def test_recipe_from_metadata_parses_valid() -> None:
    r = recipe_from_metadata(
        {
            "recipe": {
                "pace": "fast",
                "default_intensity": "high",
                "favored_intents": ["vfx", "zoom", "bogus"],
                "sfx_on_beat": True,
            }
        }
    )
    assert r.pace == "fast"
    assert r.default_intensity == "high"
    assert r.favored_intents == ("vfx", "zoom")  # noma'lum 'bogus' tashlandi
    assert r.sfx_on_beat is True


def test_recipe_from_metadata_defaults_on_junk() -> None:
    assert recipe_from_metadata(None) == EVERGREEN_RECIPE
    assert recipe_from_metadata({"recipe": "nope"}) == EVERGREEN_RECIPE
    assert recipe_from_metadata({"recipe": {"pace": "ludicrous"}}).pace == EVERGREEN_RECIPE.pace
    assert (
        recipe_from_metadata({"recipe": {"favored_intents": []}}).favored_intents
        == EVERGREEN_RECIPE.favored_intents
    )


# ── producer side (knowledge_seeder writes what montage_director reads) ──


def test_recipe_to_metadata_round_trips() -> None:
    # Whatever the seeder persists must parse back to the SAME recipe the director will read.
    r = EditRecipe(pace="fast", favored_intents=("vfx", "transition"), default_intensity="high", sfx_on_beat=True)
    assert recipe_from_metadata(recipe_to_metadata(r)) == r
    assert recipe_from_metadata(recipe_to_metadata(EVERGREEN_RECIPE)) == EVERGREEN_RECIPE


def test_recipe_from_llm_validates_payload() -> None:
    # The raw LLM payload IS the recipe object (no metadata wrapper); bad values are clamped.
    r = recipe_from_llm(
        {"pace": "fast", "favored_intents": ["zoom", "bogus", "decor"], "default_intensity": "high"}
    )
    assert r.pace == "fast"
    assert r.favored_intents == ("zoom", "decor")  # 'bogus' tashlandi
    assert r.default_intensity == "high"


def test_recipe_from_llm_junk_is_evergreen() -> None:
    assert recipe_from_llm(None) == EVERGREEN_RECIPE
    assert recipe_from_llm("not a dict") == EVERGREEN_RECIPE
    assert recipe_from_llm({}) == EVERGREEN_RECIPE  # bo'sh payload → barcha default


def test_seeder_producer_consumer_loop() -> None:
    # End-to-end pure loop: LLM payload → validated → stored shape → re-read == validated.
    payload = {"pace": "slow", "favored_intents": ["text_pop", "sfx"], "sfx_on_beat": True}
    recipe = recipe_from_llm(payload)
    stored = recipe_to_metadata(recipe)
    assert recipe_from_metadata(stored) == recipe

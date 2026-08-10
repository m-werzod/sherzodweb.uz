"""Trend-driven EDIT RECIPE for the montage_director (Faza A4 trend-binding).

The recipe says HOW the current reels meta wants cuts edited — pace, which effect intents to
favour, default intensity, whether scene changes get transitions. The montage_director feeds it
into its effect-selection prompt so the chosen effects track the latest trend, not just the script
(the product vision: "doimiy eng oxirgi trendlarga moslashgan").

Source of truth: `shared_knowledge` rows of kind='trending_edit' (region-scoped, populated by the
seed/refresh jobs, metadata.recipe). Until those exist the EVERGREEN default applies — a solid reels
baseline — so the director is improved NOW and sharpens as trends are seeded. Fail-soft: any read
error → evergreen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import text

from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

_INTENTS = ("zoom", "vfx", "text_pop", "decor", "transition", "sfx")
_PACES = ("slow", "medium", "fast")
_STRENGTHS = ("low", "med", "high")


@dataclass(frozen=True)
class EditRecipe:
    pace: str = "medium"
    favored_intents: tuple[str, ...] = ("zoom", "text_pop", "transition")
    default_intensity: str = "med"
    transition_on_scene: bool = True
    sfx_on_beat: bool = False


EVERGREEN_RECIPE = EditRecipe()


def recipe_prompt_hint(r: EditRecipe) -> str:
    """PURE: recipe → Uzbek prompt fragment that biases the director's effect choices."""
    favored = ", ".join(r.favored_intents) or "zoom, text_pop"
    parts = [
        f"Hozirgi reels uslubi: {r.pace} tempo.",
        f"Afzal ko'riladigan effektlar: {favored}.",
        f"Odatiy intensivlik: {r.default_intensity}.",
    ]
    if r.transition_on_scene:
        parts.append("Sahna o'zgarishlarida transition qo'shishga moyil bo'l.")
    if r.sfx_on_beat:
        parts.append("Kuchli ta'kid nuqtalarida sfx ishlat.")
    return " ".join(parts)


def recipe_to_metadata(r: EditRecipe) -> dict[str, Any]:
    """PURE inverse of recipe_from_metadata — EditRecipe → a `trending_edit` row's metadata.
    The seeder validates an LLM payload through recipe_from_metadata, then stores this clean shape so
    every persisted recipe round-trips exactly back to the same EditRecipe the director will read."""
    return {
        "recipe": {
            "pace": r.pace,
            "favored_intents": list(r.favored_intents),
            "default_intensity": r.default_intensity,
            "transition_on_scene": r.transition_on_scene,
            "sfx_on_beat": r.sfx_on_beat,
        }
    }


def recipe_from_llm(data: Any) -> EditRecipe:
    """PURE: a raw LLM edit-meta payload (the recipe object itself) → a validated EditRecipe.
    Wraps the payload as metadata.recipe so ALL clamping/allowlisting lives in one place."""
    return recipe_from_metadata({"recipe": data} if isinstance(data, dict) else None)


def recipe_from_metadata(metadata: Any) -> EditRecipe:
    """PURE: a trending_edit row's metadata.recipe → EditRecipe (validated, evergreen-defaulted)."""
    if not isinstance(metadata, dict):
        return EVERGREEN_RECIPE
    rec = metadata.get("recipe")
    if not isinstance(rec, dict):
        return EVERGREEN_RECIPE
    pace = str(rec.get("pace") or "").lower()
    intensity = str(rec.get("default_intensity") or "").lower()
    favored = tuple(i for i in (rec.get("favored_intents") or []) if isinstance(i, str) and i in _INTENTS)
    return EditRecipe(
        pace=pace if pace in _PACES else EVERGREEN_RECIPE.pace,
        favored_intents=favored or EVERGREEN_RECIPE.favored_intents,
        default_intensity=intensity if intensity in _STRENGTHS else EVERGREEN_RECIPE.default_intensity,
        transition_on_scene=bool(rec.get("transition_on_scene", EVERGREEN_RECIPE.transition_on_scene)),
        sfx_on_beat=bool(rec.get("sfx_on_beat", EVERGREEN_RECIPE.sfx_on_beat)),
    )


async def edit_recipe_for(region: str = "uz") -> EditRecipe:
    """The top trending_edit recipe for the region, or EVERGREEN. Fail-soft (DB error → evergreen)."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT metadata FROM shared_knowledge
                        WHERE region = :region AND kind = 'trending_edit'
                          AND ("expiresAt" IS NULL OR "expiresAt" > NOW())
                        ORDER BY score DESC NULLS LAST, "observedAt" DESC
                        LIMIT 1
                        """
                    ),
                    {"region": region},
                )
            ).mappings().first()
        return recipe_from_metadata(row["metadata"]) if row else EVERGREEN_RECIPE
    except Exception as exc:  # noqa: BLE001 — trend read is optional; fall back to evergreen
        log.warning("trend_edits.read_failed", error=str(exc)[:160])
        return EVERGREEN_RECIPE

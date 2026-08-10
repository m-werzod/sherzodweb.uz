"""Generative visual cards (MONTAGE-PRO F3) — Higgsfield Soul graphics behind stat callouts.

The reference-grade look puts key numbers on a DESIGNED card, not bare text. AI models render text
unreliably, so the split is: Higgsfield Soul generates a TEXT-FREE background graphic matched to the
shot's theme; the renderer (Shotstack) lays OUR crisp text on top. Fail-soft everywhere: no creds /
generation error → that overlay stays plain text, exactly as before.

Cost control: only `callout` overlays (the montage_director's stat text_pops) get cards, capped at
_MAX_CARDS per montage.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.montage.higgsfield_client import generate_image, higgsfield_enabled

if TYPE_CHECKING:
    from app.montage.edl import EDL

log = structlog.get_logger(__name__)

_MAX_CARDS = 3


def card_prompt(overlay_text: str) -> str:
    """Overlay text → a TEXT-FREE Soul graphic prompt (PURE). The text itself is rendered by the
    editor on top, so the prompt explicitly forbids lettering."""
    hint = (overlay_text or "").strip()[:60]
    return (
        f"Modern minimal social-media stat card background inspired by: {hint}. "
        "Bold gradient shapes, subtle glow, dark premium palette with one vivid accent color, "
        "flat design, centered empty space for a headline, 9:16 vertical composition. "
        "Absolutely no text, no letters, no numbers, no watermark."
    )


def generate_overlay_cards(edl: EDL, *, limit: int = _MAX_CARDS) -> dict[int, str]:
    """{overlay index → card image URL} for callout overlays. Gated by higgsfield_enabled();
    FAIL-SOFT — errors just skip that card. SYNC (montage worker thread)."""
    if not higgsfield_enabled():
        return {}
    out: dict[int, str] = {}
    for idx, ov in enumerate(edl.overlays):
        if len(out) >= limit:
            break
        if (ov.template or "").strip().lower() != "callout":
            continue
        txt = (ov.text or "").strip()
        if not txt:
            continue
        url = generate_image(card_prompt(txt), size="1152x2048", seed=idx + 1, label=f"soul_card{idx}")
        if url:
            out[idx] = url
    if out:
        log.info("visual_cards.generated", cards=len(out))
    return out

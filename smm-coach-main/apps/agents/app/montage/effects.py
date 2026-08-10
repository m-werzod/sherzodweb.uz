"""Rejalashtirilgan EffectIntent'larni EDL render-lane'lariga aylantirish.

montage_director node (graf) EffectIntent'lar chiqaradi — ssenariy-bilan, trend-bilan HINT'lar
("3-shotda zoom", "shu yerda dekor caption"). Bu PURE pass har birini MAVJUD render-lane'ga
(motion / overlays / transitions / sfx) joylaydi, shunda ikkala renderer ham (ffmpeg compiler VA
STUDIO editor) ularni amalga oshiradi. Faqat QO'SHADI — build_motion/build_overlays bergan
heuristik default'larni o'chirmaydi. Async asset (b_roll) yoki GPU (eye_contact/cleanup) kerak
bo'lgan intent'lar edl.effect_intents'da qayd etiladi, ammo bu yerda amalga oshirilmaydi.

OUTPUT joylash: intent.at_sec berilsa (chegara tekshirilgan), aks holda shot_index ning birinchi
cut oynasi. Chaqiruv joyida `if effect_intents:` bilan guard — bo'sh ro'yxat bayt-bir xil no-op.
"""
from __future__ import annotations

from app.montage.edl import EDL, EffectIntent, Motion, Overlay, Sfx, Transition
from app.montage.timing import _shot_output_blocks

# intensivlik → zoom delta / effekt miqdori
_STRENGTH = {"low": 0.06, "med": 0.12, "high": 0.20}


def resolve_effect_intents(edl: EDL, intents: list[EffectIntent]) -> None:
    """Intent'larni EDL render-lane'lariga qo'shadi (joyida o'zgartiradi). Modul docstring'iga qarang."""
    # Shot → OUTPUT oyna: build_overlays/build_motion bilan BIR XIL helper (multi-cut shotni to'liq
    # qoplaydi, faqat birinchi sub-cut emas).
    windows = _shot_output_blocks(edl.cuts)
    total = edl.output_duration()

    def _placement(fx: EffectIntent) -> tuple[float, float] | None:
        if fx.at_sec is not None and 0.0 <= fx.at_sec <= total:
            d = fx.dur if (fx.dur and fx.dur > 0) else 0.6
            return fx.at_sec, min(total, fx.at_sec + d)
        return windows.get(fx.shot_index)

    for fx in intents:
        win = _placement(fx)
        if win is None:
            continue
        at, end = win
        dur = max(0.1, end - at)
        amt = _STRENGTH.get(fx.strength, 0.12)
        params = fx.params if isinstance(fx.params, dict) else {}
        intent = fx.intent

        if intent == "zoom":
            edl.motion.append(
                Motion(op="zoom_punch", at_sec=at, dur=min(dur, 1.0), from_scale=1.0, to_scale=1.0 + amt)
            )
        elif intent == "vfx":
            op = str(params.get("op") or "glitch")
            edl.motion.append(
                Motion(op=op if op in ("shake", "glitch") else "glitch", at_sec=at, dur=min(dur, 1.0))
            )
        elif intent in ("text_pop", "decor"):
            text = str(params.get("text") or "").strip()
            if text:
                edl.overlays.append(
                    Overlay(
                        template=str(params.get("template") or "callout"),
                        at_sec=at,
                        dur=min(dur, 3.0),
                        text=text,
                        color=str(params.get("color") or "#FFFFFF"),
                    )
                )
        elif intent == "transition":
            if at > 0.05:  # birinchi kadrdan oldin transition bo'lmaydi
                edl.transitions.append(
                    Transition(at_sec=at, type=str(params.get("type") or "xfade"), dur=min(dur, 0.6))
                )
        elif intent == "sfx":
            edl.audio.sfx.append(Sfx(at_sec=at, type=str(params.get("type") or "whoosh")))
        # b_roll | eye_contact | cleanup → edl.effect_intents'da qayd, boshqa joyda amalga oshiriladi

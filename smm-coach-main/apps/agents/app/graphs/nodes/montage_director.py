"""Montage Director — picks text-matched visual effects per storyboard shot (Faza A4).

Runs in the montage_generation branch AFTER broll_curator and BEFORE caption_stylist:

  1. read the storyboard shotList,
  2. ONE fast-LLM call chooses an EffectIntent (zoom/vfx/text_pop/transition/sfx) for the
     shots that warrant emphasis — NOT every shot,
  3. persist to the user_upload TaskMedia.meta (`effectIntents`); the montage WORKER threads
     them into build_edl, where resolve_effect_intents maps each onto an EXISTING render lane
     (motion/overlays/transitions/sfx) — realised by both the ffmpeg compiler AND STUDIO.

Runs inside the graph RunContext so the (cheap) fast-LLM call is billed. Fail-soft throughout:
any error just skips effects and lets caption_stylist + the render proceed unchanged. Effects are
ADDITIVE — they augment the heuristic motion/overlays, never block or shrink a montage.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import tempfile
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.integrations.llm.fast_llm import fast_chat
from app.integrations.llm.gemini_client import analyze_video_file
from app.memory.db import get_sessionmaker
from app.montage.storage import download_object
from app.montage.trend_edits import edit_recipe_for, recipe_prompt_hint

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

_INTENTS = {"zoom", "vfx", "text_pop", "decor", "transition", "sfx"}
_STRENGTHS = {"low", "med", "high"}

VISION_PROMPT = (
    "Sen professional reels MONTAJ REJISSYORISAN. Bu videoni TOMOSHA QILIB va TINGLAB, "
    "quyidagi storyboard kadrlariga KO'RGANINGGA MOS montaj rejasini tuz:\n{listing}\n\n"
    "FAQAT JSON qaytar:\n"
    '{{"intents":[{{"shot_index":1,"intent":"zoom|vfx|text_pop|transition|sfx",'
    '"intensity":"low|med|high","params":{{}}}}],'
    '"music_hint":"<fon musiqa uslubi: janr+temp, videoning kayfiyatiga mos, EN>",'
    '"face_zone":"<top|center|bottom — gapiruvchining YUZI kadrda asosan qaysi zonada>",'
    '"unwanted":["<kadrda ko\'ringan ORTIQCHA/xalaqit beruvchi obyekt, masalan: chalkash fon, '
    "begona odam, stol ustidagi chiqindi — faqat ANIQ ko'ringanlarini yoz, yo'q bo'lsa bo'sh ro'yxat>\"]}}\n"
    "Qoidalar: transition params.type — fade(sokin)/zoom(energiya)/slide(yangi mavzu)/wipe(kontrast), "
    "gapning ohangi va VIDEODAGI harakatga qarab tanla; sfx params.type — whoosh/glitch/click; "
    "text_pop params.text — ekranda KO'RINGAN yoki AYTILGAN muhim raqam/so'z. "
    "Hammasiga emas — urg'u kerak joylargagina. Markdown yo'q."
)

SYSTEM_PROMPT = (
    "Sen reels montaj REJISSYORISAN. Senga storyboard kadrlari beriladi (raqam + o'zbekcha "
    "'action' tavsifi). Ba'zi kadrlarga MATNGA MOS bitta vizual effekt tanla — lekin HAMMASIGA "
    "emas, faqat urg'u kerak bo'lgan kadrlarga (taxminan yarmiga). Variantlar:\n"
    "- zoom: urg'u/yaqinlashish\n"
    "- vfx: energiya/keskin o'zgarish\n"
    "- text_pop: muhim so'z yoki raqam (params.text — qisqa o'zbekcha matn)\n"
    "- transition: sahna/fikr o'zgarishi — params.type MATNGA MOS tanla: fade (sokin/xulosa), "
    "zoom (energiya/urg'u), slide (yangi mavzu), wipe (qarama-qarshilik)\n"
    "- sfx: ovozli ta'kid — params.type: whoosh (matn/harakat), glitch (keskin burilish), "
    "click (CTA/ishora)\n"
    "intensity: low|med|high. Brend/ism YO'Q. FAQAT JSON qaytar: "
    '{"intents":[{"shot_index":1,"intent":"zoom","intensity":"high","params":{}}]}'
)


def heuristic_intents(valid_shots: set[int], default_strength: str = "med") -> list[dict[str, Any]]:
    """Deterministic fallback effects when the LLM is down or returns nothing — so
    a montage is never FLAT (a real risk on low-confidence uz transcripts). Every
    shot gets a baseline framing move (zoom); every 3rd adds a vfx accent. PURE."""
    strength = default_strength if default_strength in _STRENGTHS else "med"
    out: list[dict[str, Any]] = []
    for n, si in enumerate(sorted(valid_shots)):
        intent = "vfx" if n % 3 == 2 else "zoom"
        out.append({"shot_index": si, "intent": intent, "strength": strength, "params": {}})
    return out


# A digit-group followed by a unit/percent is a STAT worth putting on screen; a bare
# lone digit ("3 kadr") is usually noise, so a unit is required to avoid false positives.
_STAT_RE = re.compile(
    r"(\d[\d.,]*)\s*"
    r"(%|foiz|daqiqa|soniya|soat|kun|hafta|oy|yil|marta|barobar|baravar|"
    r"obunachi|follower|ko['ʼ]?rish|like|million|ming|so['ʼ]?m|\$|dollar)",
    re.IGNORECASE,
)


def numeric_callout_intents(
    shots: list[dict[str, Any]], *, max_callouts: int = 3, strength: str = "high"
) -> list[dict[str, Any]]:
    """Stage-9c informational VFX (deterministic): surface a prominent STAT from a shot's
    action text as an on-screen `text_pop` callout — so "10 daqiqada", "50%", "1000 obunachi"
    get a visual emphasis even when the LLM (or the heuristic fallback) didn't ask for one.
    Reuses the EXISTING text_pop overlay lane → no new render capability. PURE/testable.
    Capped + de-duped so a stat-heavy script doesn't clutter the whole montage."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in shots:
        if len(out) >= max_callouts:
            break
        si = s.get("i")
        if not isinstance(si, int):
            continue
        m = _STAT_RE.search(str(s.get("action") or ""))
        if not m:
            continue
        label = f"{m.group(1).strip()} {m.group(2).strip()}".strip()
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {"shot_index": si, "intent": "text_pop", "strength": strength,
             "params": {"text": label[:24], "template": "callout"}}
        )
    return out


def normalize_intents(raw: str, valid_shots: set[int], default_strength: str = "med") -> list[dict[str, Any]]:
    """LLM JSON → tekshirilgan effectIntent dict'lari (effect_intents storage shakli). PURE/testable.
    Noma'lum intent/shot tashlanadi, strength clamp (yo'q bo'lsa `default_strength` — trend retseptidan),
    params dict bo'lib qoladi, dup shot tashlanadi. Yaroqsiz JSON → []."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    items = data.get("intents") if isinstance(data, dict) else None
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        si = it.get("shot_index")
        intent = str(it.get("intent") or "").strip()
        if not isinstance(si, int) or si in seen or si not in valid_shots or intent not in _INTENTS:
            continue
        strength = str(it.get("intensity") or it.get("strength") or default_strength).strip().lower()
        params = it.get("params") if isinstance(it.get("params"), dict) else {}
        out.append(
            {
                "shot_index": si,
                "intent": intent,
                "strength": strength if strength in _STRENGTHS else "med",
                "params": params,
            }
        )
        seen.add(si)
    return out


def parse_director_response(
    raw: str, valid_shots: set[int], default_strength: str = "med"
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Vision-director JSON → (intents, music_hint, unwanted, face_zone). PURE/testable;
    bad JSON → ([], "", [], "")."""
    intents = normalize_intents(raw, valid_shots, default_strength)
    music_hint, unwanted, face_zone = "", [], ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            mh = data.get("music_hint")
            if isinstance(mh, str):
                music_hint = mh.strip()[:150]
            fz = data.get("face_zone")
            if isinstance(fz, str) and fz.strip().lower() in ("top", "center", "bottom"):
                face_zone = fz.strip().lower()
            uw = data.get("unwanted")
            if isinstance(uw, list):
                unwanted = [str(x).strip()[:80] for x in uw if str(x).strip()][:5]
    except (json.JSONDecodeError, TypeError):
        pass
    return intents, music_hint, unwanted, face_zone


async def _watch_video(object_key: str, listing: str) -> str:
    """F6: download the upload and let Gemini WATCH it with the storyboard in hand. Fail-soft → ''."""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        await asyncio.to_thread(download_object, object_key, tmp)
        raw = await analyze_video_file(
            path=tmp, question=VISION_PROMPT.format(listing=listing),
            agent_name="montage_director", json_mode=True,
        )
        return raw or ""
    except Exception as exc:  # noqa: BLE001 — vision is an upgrade, never a blocker
        log.warning("montage_director.vision_failed", error=str(exc)[:160])
        return ""
    finally:
        if tmp:
            with contextlib.suppress(OSError):
                os.unlink(tmp)


async def run(state: GrowthCoachState) -> dict[str, Any]:
    if state.get("workflow") != "montage_generation":
        return {}
    task_id = state.get("task_id")
    if not task_id:
        return {}
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    try:
        up = await _latest_upload(task_id, tenant_id)
        if not up:
            return {"notes": ["montage_director: no upload"]}
        upload_id, object_key = up
        shot_list = await _storyboard(task_id, tenant_id)
        shots = [s for s in shot_list if isinstance(s, dict) and isinstance(s.get("i"), int)]
        if not shots:
            return {"notes": ["montage_director: no storyboard"]}
        valid = {int(s["i"]) for s in shots}

        # Trend retsepti effekt tanlovini boshqaradi (seed bo'lmasa — evergreen default).
        recipe = await edit_recipe_for()
        listing = "\n".join(f'{s["i"]}: {str(s.get("action") or "")[:80]}' for s in shots)
        # F6: the director WATCHES the actual footage (Gemini vision) — content-aware choices.
        music_hint, unwanted, face_zone = "", [], ""
        raw = await _watch_video(object_key, listing)
        if raw:
            intents, music_hint, unwanted, face_zone = parse_director_response(raw, valid, recipe.default_intensity)
        else:
            intents = []
        if not intents:
            # Fallback: the original text-only pass (script text still carries the speech).
            try:
                raw = await fast_chat(
                    system=SYSTEM_PROMPT,
                    user=f"{recipe_prompt_hint(recipe)}\n\nKadrlar:\n{listing}",
                    json=True,
                    max_tokens=600,
                    agent_name="montage_director",
                )
            except Exception as exc:  # noqa: BLE001 — LLM down → deterministic fallback effects
                log.warning("montage_director.llm_failed", error=str(exc)[:160])
                raw = ""
            intents = normalize_intents(raw, valid, recipe.default_intensity)
        if not intents:
            # Never leave a montage flat — apply baseline framing/vfx heuristically.
            intents = heuristic_intents(valid, recipe.default_intensity)
            log.info("montage_director.heuristic_fallback", shots=len(valid), intents=len(intents))
        # Informational VFX (Stage 9c): guarantee prominent stats get an on-screen callout,
        # overriding whatever effect that shot had (a number IS the highlight there).
        callouts = numeric_callout_intents(shots)
        if callouts:
            co_shots = {c["shot_index"] for c in callouts}
            intents = [i for i in intents if i.get("shot_index") not in co_shots] + callouts
        if not intents:
            return {"notes": ["montage_director: no effects"]}
        await _persist(upload_id, tenant_id, intents)
        if music_hint or unwanted or face_zone:
            await _persist_notes(upload_id, tenant_id, music_hint, unwanted, face_zone)

        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="writer",
            content=f"Vizual effektlar rejalashtirildi · {len(intents)} ta kadrga matnga-mos effekt",
            run_id=run_id,
        )
        return {"notes": [f"montage_director: planned {len(intents)} effects"]}
    except Exception as exc:  # noqa: BLE001 — never block caption_stylist / the render
        log.warning("montage_director.failed", error=str(exc)[:200])
        return {"notes": ["montage_director: skipped (error)"]}


async def _latest_upload(task_id: str, tenant_id: str) -> tuple[str, str] | None:
    """(media_id, objectKey) of the newest user upload, or None."""
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text(
                    'SELECT id, "objectKey" FROM task_media '
                    "WHERE \"taskId\"=:t AND \"tenantId\"=:tn AND kind='user_upload' "
                    'AND "objectKey" IS NOT NULL ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"t": task_id, "tn": tenant_id},
            )
        ).mappings().first()
    return (str(row["id"]), str(row["objectKey"])) if row else None


async def _persist_notes(
    media_id: str, tenant_id: str, music_hint: str, unwanted: list[str], face_zone: str = ""
) -> None:
    """F6 director notes onto the upload meta: content-matched music hint + spotted unwanted
    elements (consumed by the worker: music prompt priority + gated auto-inpaint)."""
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                "UPDATE task_media SET "
                "meta = COALESCE(meta, '{}'::jsonb) || "
                "jsonb_build_object('directorNotes', CAST(:dn AS jsonb)), "
                '"updatedAt" = NOW() WHERE id = :id AND "tenantId" = :tn'
            ),
            {"dn": json.dumps(
                {"music_hint": music_hint, "unwanted": unwanted, "face_zone": face_zone},
                ensure_ascii=False,
            ),
             "id": media_id, "tn": tenant_id},
        )
        await session.commit()


async def _storyboard(task_id: str, tenant_id: str) -> list[Any]:
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text('SELECT "shotList" FROM content_tasks WHERE id=:id AND "tenantId"=:tn'),
                {"id": task_id, "tn": tenant_id},
            )
        ).mappings().first()
    raw = row["shotList"] if row else None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    return raw if isinstance(raw, list) else []


async def _persist(media_id: str, tenant_id: str, intents: list[dict[str, Any]]) -> None:
    """Merge effectIntents into the user_upload row meta (jsonb concat preserves footageMap/brollPlan)."""
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                "UPDATE task_media SET "
                "meta = COALESCE(meta, '{}'::jsonb) || "
                "jsonb_build_object('effectIntents', CAST(:ei AS jsonb)), "
                '"updatedAt" = NOW() WHERE id = :id AND "tenantId" = :tn'
            ),
            {"ei": json.dumps(intents), "id": media_id, "tn": tenant_id},
        )
        await session.commit()

"""Caption Stylist — the first montage agent in the graph.

Runs as the single-node `montage_generation` branch when the user uploads a clip.
Claude Sonnet reads the script + the hook's energy and decides:
  * tier      — premium karaoke vs cheap window
  * accent    — the highlight colour that fits the content's mood
  * size      — caption size
  * emphasis  — 2-5 key words to enlarge for punch

It then writes a `final_render` pending TaskMedia row carrying that spec in
`meta` — the hand-off the montage_worker renders. LLMs decide style; the
deterministic compiler renders it (agents emit data, code acts).

Fail-soft: on any LLM error it still writes the pending row with a sane default
style, so the upload always produces a montage.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.config import get_settings
from app.graphs.prompt_store import resolve_prompt
from app.integrations.llm.anthropic_client import call_claude
from app.memory.db import get_sessionmaker
from app.montage.edl import CAPTION_FONTS
from app.montage.storage import delete_object

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

# Mood name → ASS colour (&H00BBGGRR). The LLM picks a name; we own the hex.
_ACCENT = {
    "amber": "&H0000D7FF",
    "white": "&H00FFFFFF",
    "green": "&H0000FF6E",
    "cyan": "&H00FFE000",
    "pink": "&H00B469FF",
    "red": "&H003C3CFF",
}

_DEFAULT_SPEC = {
    "tier": "premium",
    "accent": "amber",
    "size": 96,
    "font": "Montserrat",
    "emphasis_words": [],
    "hook_overlay": "",
}

SYSTEM_PROMPT = """Sen qisqa video (Reels) uchun professional SUBTITR dizayneri va
muharrirsan (Submagic uslubida). Senga senariy matni + hook + energiya darajasi
beriladi. Sen subtitr uslubini tanlaysan.

QOIDALAR:
- tier: "premium" (so'zma-so'z karaoke — energetik/dinamik kontentga) yoki "cheap"
  (sokin/jiddiy kontentga).
- accent: faol so'z rangi — kontent kayfiyatiga mos BITTA tanla: amber, white,
  green, cyan, pink, red. (Pul/biznes=green, hayajon=amber, jiddiy=white.)
- size: 88-104 (yuqori energiya = kattaroq).
- font: subtitr shrifti — kayfiyatga mos BITTA tanla: "Anton" (eng zarbdor, qalin —
  hayajon/energiya), "Bebas Neue" (baland, ixcham — trend/zamonaviy), "Oswald" (ixcham,
  jiddiy — biznes/ma'lumot), "Montserrat" (universal, toza — default). Trend Reels'da
  Anton/Bebas Neue ko'p ishlatiladi.
- emphasis_words: senariyDAGI eng MUHIM 2-5 ta so'z (aniq yozilishida) — ular
  ekranda kattalashtiriladi. Faqat haqiqatan kuchli, e'tibor tortadigan so'zlar.
- hook_overlay: videoning birinchi 2.5 soniyasida ekranda KATTA ko'rsatiladigan
  QISQA, zarbdor hook — 3-6 so'z, eng kuchli ibora. TO'LIQ JUMLA EMAS (uzun jumla
  2.5s da o'qilmaydi). MUHIM: hookni `opening` (videoning birinchi ~2.5s da AYTILGAN
  so'zlar) MAZMUNIGA MOS qil — yangi da'vo IXTIRO QILMA, aks holda ekrandagi matn
  aytilayotgan ovozga mos kelmay clickbait bo'lib qoladi. Ochilishning eng kuchli
  qismini qisqartir. Masalan opening="Biz treyderlar uchun bepul loyiha..." → "Treyderlar uchun bepul!".

FAQAT JSON:
{"tier":"premium|cheap","accent":"<rang>","size":<88-104>,"font":"Anton|Bebas Neue|Oswald|Montserrat","emphasis_words":["...","..."],"hook_overlay":"<3-6 so'z>"}"""


async def run(state: GrowthCoachState) -> dict[str, Any]:
    if state.get("workflow") != "montage_generation":
        return {}
    task_id = state.get("task_id")
    if not task_id:
        log.warning("caption_stylist.no_task_id")
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    task = await _load_task(task_id)
    if task is None:
        return {"notes": ["caption_stylist: task not found"]}

    spec = await _choose_spec(task, state.get("instructions"))
    await _write_render_row(
        task_id, tenant_id, spec,
        inpaint_remove=state.get("inpaint_remove"),
        decor_background=state.get("decor_background"),
    )

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=(
            f"Subtitr ustasi uslubni tanladi · {spec['tier']} · {spec['accent']} · "
            f"{len(spec['emphasis_words'])} urg'u so'z. Montaj navbatga qo'yildi."
        ),
        run_id=run_id,
        important=True,
    )
    return {
        "notes": [
            f"caption_stylist: {spec['tier']}/{spec['accent']}, "
            f"{len(spec['emphasis_words'])} emphasis"
        ]
    }


async def _choose_spec(
    task: dict[str, Any], instructions: str | None = None
) -> dict[str, Any]:
    script_text = _script_text(task.get("scriptTimeline"))
    hook_meta = task.get("hookMeta") or {}
    if isinstance(hook_meta, str):
        try:
            hook_meta = json.loads(hook_meta)
        except json.JSONDecodeError:
            hook_meta = {}
    payload = {
        "hook": task.get("hook") or "",
        "energy": hook_meta.get("energy"),
        # The opening ~200 chars ≈ what the speaker says in the first ~2.5s — the hook overlay
        # must reflect THIS so the on-screen hook matches the audio (not an invented claim).
        "opening": script_text[:200],
        "script": script_text[:1200],
    }
    system = await resolve_prompt("caption_stylist", SYSTEM_PROMPT)
    if instructions:
        # Re-montage with the user's verbal feedback (voice coach remontage tool) — it overrides
        # the energy-derived defaults for the lanes this agent owns (tier/accent/size/emphasis).
        fb = str(instructions)[:500]
        payload["user_feedback"] = fb
        system += (
            "\n\nMUHIM — foydalanuvchining QAYTA-MONTAJ tuzatishi (ustuvor): "
            + fb
            + "\nUni iloji boricha hisobga ol (tier / accent / size / emphasis_words)."
        )
    s = get_settings()
    try:
        response, _usage = await call_claude(
            model=s.model_scriptwriter_revise,  # Sonnet — cheap, instruction-following
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            max_tokens=300,
            response_format="json",
            agent_name="caption_stylist",
        )
        parsed = _parse(response.get("text") or "{}")
    except Exception as exc:  # noqa: BLE001
        log.warning("caption_stylist.failed", error=str(exc)[:120])
        return dict(_DEFAULT_SPEC)
    return _sanitize(parsed)


def _sanitize(parsed: dict[str, Any]) -> dict[str, Any]:
    tier = parsed.get("tier")
    accent = parsed.get("accent")
    try:
        size = int(parsed.get("size") or 96)
    except (TypeError, ValueError):
        size = 96
    font = parsed.get("font")
    emph = parsed.get("emphasis_words")
    hook = parsed.get("hook_overlay")
    # Keep the on-screen hook punchy — a long one is unreadable in 2.5s.
    hook_overlay = " ".join(str(hook).split()[:7]) if isinstance(hook, str) else ""
    return {
        "tier": tier if tier in ("premium", "cheap") else "premium",
        "accent": accent if accent in _ACCENT else "amber",
        "size": max(80, min(108, size)),
        # Only allow bundled trend faces; anything else → Montserrat (libass won't fall back blind).
        "font": font if font in CAPTION_FONTS else "Montserrat",
        "emphasis_words": [str(w) for w in emph][:6] if isinstance(emph, list) else [],
        "hook_overlay": hook_overlay,
    }


def _render_meta(
    spec: dict[str, Any], inpaint_remove: str | None, decor_background: str | None = None
) -> dict[str, Any]:
    """The final_render meta the worker reads: caption style + (Faza D) optional inpaint target +
    (Faza C) optional scenario-matched background."""
    meta: dict[str, Any] = {
        "captionStyle": {
            "size": spec["size"],
            "active": _ACCENT[spec["accent"]],
            "font": spec.get("font", "Montserrat"),
        },
        "tier": spec["tier"],
        "emphasisWords": spec["emphasis_words"],
        "hookOverlay": spec["hook_overlay"],
    }
    rem = (inpaint_remove or "").strip()
    if rem:
        meta["inpaintRemove"] = rem
    dec = (decor_background or "").strip()
    if dec:
        meta["decorBackground"] = dec
    return meta


async def _write_render_row(
    task_id: str,
    tenant_id: str,
    spec: dict[str, Any],
    inpaint_remove: str | None = None,
    decor_background: str | None = None,
) -> None:
    """Create the pending final_render row carrying the style spec the worker
    renders. Created AFTER the spec is resolved so the worker never claims a
    half-styled row."""
    meta = json.dumps(_render_meta(spec, inpaint_remove, decor_background))
    sm = get_sessionmaker()
    async with sm() as session:
        # Capture the superseded render's object keys BEFORE the delete so we can
        # reclaim them from MinIO after the swap (the row delete alone leaks the
        # object — nothing else GCs it). New render writes a fresh key, so these
        # are now unreferenced.
        prior_keys = [
            r["objectKey"]
            for r in (
                await session.execute(
                    text(
                        "SELECT \"objectKey\" FROM task_media "
                        "WHERE \"taskId\"=:t AND kind='final_render' AND \"objectKey\" IS NOT NULL"
                    ),
                    {"t": task_id},
                )
            ).mappings().all()
        ]
        # Replace any prior render so a re-upload restarts cleanly.
        await session.execute(
            text("DELETE FROM task_media WHERE \"taskId\"=:t AND kind='final_render'"),
            {"t": task_id},
        )
        await session.execute(
            text(
                """
                INSERT INTO task_media
                  (id, "taskId", "tenantId", kind, provider, status, meta,
                   "createdAt", "updatedAt")
                VALUES
                  (:id, :t, :tn, 'final_render', 'ffmpeg', 'pending',
                   CAST(:meta AS jsonb), NOW(), NOW())
                """
            ),
            {"id": uuid.uuid4().hex, "t": task_id, "tn": tenant_id, "meta": meta},
        )
        await session.commit()
    # Best-effort object reclaim AFTER the rows are gone — a failure here only
    # leaks an object (the prior behaviour), never breaks the re-render.
    for key in prior_keys:
        try:
            await asyncio.to_thread(delete_object, key)
        except Exception:  # noqa: BLE001
            log.warning("caption_stylist.orphan_reclaim_failed", key=key, exc_info=True)


async def _load_task(task_id: str) -> dict[str, Any] | None:
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text(
                    'SELECT "scriptTimeline", hook, "hookMeta", type '
                    "FROM content_tasks WHERE id=:id"
                ),
                {"id": task_id},
            )
        ).mappings().first()
    return dict(row) if row else None


def _script_text(raw: Any) -> str:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return ""
    if not isinstance(raw, list):
        return ""
    return " ".join(
        str(e.get("text") or "") for e in raw if isinstance(e, dict)
    ).strip()


def _parse(raw: str) -> dict[str, Any]:
    candidates = [raw]
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}

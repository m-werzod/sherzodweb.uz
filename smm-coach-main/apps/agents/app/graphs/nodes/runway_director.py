"""Runway Director — builds a cinematic RESTYLE prompt for the user's UPLOADED clip.

Single-node `runway_restyle` branch. Reads the scenario (hook + reelType + shot themes), asks Claude
for ONE English restyle instruction (what cinematic look to apply while PRESERVING the subject and
motion), then writes a `final_render` pending row (meta.renderSource='runway_restyle' + runwayPrompt)
— the hand-off the montage_worker's Runway branch renders. Requires an upload (Runway edits an existing
video). Fail-soft: LLM down → a sane default restyle prompt; no upload → a failed row that the UI shows.
"""
from __future__ import annotations

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

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

_DEFAULT_PROMPT = (
    "Apply a clean cinematic color grade: warm key light, soft teal shadows, shallow depth of field, "
    "gentle film grain and subtle bloom. Keep the person and their motion natural and recognizable. "
    "No text overlays."
)

SYSTEM_PROMPT = """Sen video RESTYLE bo'yicha ijodiy rejissyorisan (Runway Aleph uchun). Foydalanuvchi
o'z videosini (odatda talking-head / senariy bo'yicha yozilgan) yuklagan. Sen unga qanday KINEMATIK
ko'rinish berishni bitta INGLIZ TILIDA prompt bilan tasvirlaysan.

QOIDALAR:
- Odam va uning harakati TANIB olinadigan bo'lib qolsin (yuzini butunlay o'zgartirma).
- Yorug'lik, rang-grading, atmosfera, uslub (masalan: cinematic, teal-orange, film grain, bokeh).
- Ekran matni/subtitr QO'SHMA (buni biz alohida qo'shamiz).
- 1-2 jumla, faqat prompt matnini qaytar (JSON emas, izohsiz)."""


async def run(state: GrowthCoachState) -> dict[str, Any]:
    if state.get("workflow") != "runway_restyle":
        return {}
    task_id = state.get("task_id")
    if not task_id:
        log.warning("runway_director.no_task_id")
        return {}
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    if not await _has_upload(task_id, tenant_id):
        await _write_failed_row(task_id, tenant_id, "Video yuklanmagan — Runway restyle uchun avval videongizni yuklang.")
        return {"notes": ["runway_director: no upload"]}

    task = await _load_task(task_id)
    prompt = await _build_prompt(task or {})
    hook = _short_hook((task or {}).get("hook"))
    await _write_render_row(task_id, tenant_id, prompt, hook=hook)

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content="Runway rejissyori kinematik restyle prompt tayyorladi. Videongiz qayta ishlashga navbatga qo'yildi.",
        run_id=run_id,
        important=True,
    )
    return {"notes": ["runway_director: prompt ready"]}


async def _build_prompt(task: dict[str, Any]) -> str:
    hook = str(task.get("hook") or "").strip()
    reel_type = str(task.get("reelType") or "").strip()
    shots = task.get("shotList")
    themes = ""
    if isinstance(shots, str):
        try:
            shots = json.loads(shots)
        except json.JSONDecodeError:
            shots = None
    if isinstance(shots, list):
        themes = " · ".join(
            str(s.get("action") or s.get("dialogue") or "")[:60] for s in shots[:4] if isinstance(s, dict)
        )
    system = await resolve_prompt("runway_director", SYSTEM_PROMPT)
    s = get_settings()
    try:
        response, _usage = await call_claude(
            model=s.model_scriptwriter_revise,
            system=system,
            messages=[{"role": "user", "content": f"Mavzu/hook: {hook}\nTur: {reel_type}\nKadrlar: {themes}"}],
            max_tokens=200,
            agent_name="runway_director",
        )
        text_out = (response.get("text") or "").strip()
    except Exception as exc:  # noqa: BLE001 — LLM down → default restyle
        log.warning("runway_director.llm_failed", error=str(exc)[:160])
        text_out = ""
    return (text_out[:1000] or _DEFAULT_PROMPT)


def _short_hook(hook: Any) -> str:
    if not isinstance(hook, str):
        return ""
    return " ".join(hook.split()[:7])


async def _write_render_row(task_id: str, tenant_id: str, prompt: str, *, hook: str) -> None:
    meta = json.dumps(
        {
            "renderSource": "runway_restyle",
            "runwayPrompt": prompt,
            "hookOverlay": hook,
            "captionStyle": {"font": "Montserrat"},
            "tier": "premium",
        },
        ensure_ascii=False,
    )
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("DELETE FROM task_media WHERE \"taskId\"=:t AND kind='final_render'"),
            {"t": task_id},
        )
        await session.execute(
            text(
                """
                INSERT INTO task_media
                  (id, "taskId", "tenantId", kind, provider, status, meta, "createdAt", "updatedAt")
                VALUES
                  (:id, :t, :tn, 'final_render', 'runway', 'pending', CAST(:meta AS jsonb), NOW(), NOW())
                """
            ),
            {"id": uuid.uuid4().hex, "t": task_id, "tn": tenant_id, "meta": meta},
        )
        await session.commit()


async def _write_failed_row(task_id: str, tenant_id: str, message: str) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("DELETE FROM task_media WHERE \"taskId\"=:t AND kind='final_render'"),
            {"t": task_id},
        )
        await session.execute(
            text(
                """
                INSERT INTO task_media
                  (id, "taskId", "tenantId", kind, provider, status, "errorMessage", "createdAt", "updatedAt")
                VALUES
                  (:id, :t, :tn, 'final_render', 'runway', 'failed', :err, NOW(), NOW())
                """
            ),
            {"id": uuid.uuid4().hex, "t": task_id, "tn": tenant_id, "err": message[:500]},
        )
        await session.commit()


async def _has_upload(task_id: str, tenant_id: str) -> bool:
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text(
                    "SELECT 1 FROM task_media WHERE \"taskId\"=:t AND \"tenantId\"=:tn "
                    "AND kind='user_upload' AND \"objectKey\" IS NOT NULL LIMIT 1"
                ),
                {"t": task_id, "tn": tenant_id},
            )
        ).first()
    return row is not None


async def _load_task(task_id: str) -> dict[str, Any] | None:
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text('SELECT hook, "reelType", "shotList", "audioSuggestion" FROM content_tasks WHERE id=:id'),
                {"id": task_id},
            )
        ).mappings().first()
    return dict(row) if row else None

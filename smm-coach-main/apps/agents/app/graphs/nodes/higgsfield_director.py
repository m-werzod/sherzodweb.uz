"""Higgsfield Director — turns a scenario storyboard into a per-shot AI-video plan.

The single-node `higgsfield_generation` branch. Claude reads the storyboard (shotList) + script and,
for EACH shot, writes an ENGLISH cinematic image→video prompt + a keyframe still prompt + a
camera-motion preset — this is where the AI "adds its own ideas" (it enriches every Uzbek shot into a
strong, brand-free cinematic direction). It then writes a `final_render` pending row carrying the plan
in `meta.higgsfieldPlan` + `meta.renderSource="higgsfield"` — the hand-off the montage_worker's
Higgsfield branch generates + assembles.

Agents emit data, code acts: this node NEVER calls Higgsfield or ffmpeg — it only plans. Fail-soft: on
any LLM error it falls back to a deterministic plan (one cinematic move per shot) so the render always
has something to build. Requires ENABLE_HIGGSFIELD + a key at RENDER time; the plan is written
regardless so enabling the key later lights it up with no re-plan.
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
from app.montage.higgsfield_client import MOTION_NAMES
from app.montage.storage import delete_object

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

_MAX_SHOTS = 10
_DEFAULT_MOTIONS = ("push_in", "orbit", "pull_out", "arc_left", "crane_up", "handheld")

SYSTEM_PROMPT = """Sen KINEMATIK AI-video rejissyorisan (Higgsfield DoP uchun). Senga qisqa video
storyboard KADRLARI beriladi (raqam + o'zbekcha 'action'/'dialogue' tavsifi).

Har kadr uchun Higgsfield image→video generatsiyasiga mo'ljallangan quyidagilarni yoz:
- "prompt": INGLIZ TILIDA kuchli, vizual, kinematik harakat prompti (kamera, yorug'lik, kayfiyat).
  Qisqa, aniq, brendsiz va EKRAN MATNISIZ. Odam gapirayotgan bo'lsa ham — vizual sahnani tasvirla.
- "image_prompt": INGLIZ TILIDA shu kadrning boshlang'ich KADR (still) tasviri uchun prompt
  (9:16 vertikal, kinematik, fotorealistik yoki mos uslub).
- "motion": kamera harakati — FAQAT bu ro'yxatdan BITTA: static, push_in, pull_out, orbit,
  arc_left, arc_right, pan_left, pan_right, tilt_up, tilt_down, crane_up, crane_down, handheld,
  dolly_zoom, fpv, overhead.
- "motion_strength": 0.3-0.9 (dinamik kadr = yuqori).

O'z ijodiy g'oyalaringni QO'SH — har kadrni jonli, kinematik qil. FAQAT JSON qaytar:
{"shots":[{"shot_index":1,"prompt":"...","image_prompt":"...","motion":"push_in","motion_strength":0.6}]}"""


async def run(state: GrowthCoachState) -> dict[str, Any]:
    if state.get("workflow") != "higgsfield_generation":
        return {}
    task_id = state.get("task_id")
    if not task_id:
        log.warning("higgsfield_director.no_task_id")
        return {}
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    task = await _load_task(task_id)
    if task is None:
        return {"notes": ["higgsfield_director: task not found"]}
    shot_list = _as_list(task.get("shotList"))
    shots = [s for s in shot_list if isinstance(s, dict) and isinstance(s.get("i"), int)]
    if not shots:
        # Surface the dead-end to the UI (a failed render row) instead of a silent no-op — the web
        # route's storyboard guard is looser (non-empty array) than this integer-`i` requirement.
        await _write_failed_row(task_id, tenant_id, "Storyboard topilmadi — avval senariy/kadrlarni yozdiring.")
        return {"notes": ["higgsfield_director: no storyboard — avval senariy/kadrlar kerak"]}

    # When the user uploaded a clip, EDIT it: each shot's keyframe is grabbed from THEIR footage
    # (keyframe="footage"). With no upload, generate keyframes from scratch (FLUX). This is the
    # difference the user asked for — "take the uploaded video + scenario and edit it via Higgsfield".
    has_upload = await _has_upload(task_id, tenant_id)
    plan = await _build_plan(shots, task, has_upload=has_upload)
    if not plan:
        await _write_failed_row(task_id, tenant_id, "Kinematik reja tuzilmadi — senariy kadrlarini tekshiring.")
        return {"notes": ["higgsfield_director: empty plan"]}

    hook = _short_hook(task.get("hook"))
    await _write_render_row(task_id, tenant_id, plan, hook=hook)

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=(
            f"Higgsfield rejissyori {len(plan)} ta kadrga kinematik prompt + kamera harakati "
            f"tayyorladi. AI-video generatsiyasi navbatga qo'yildi."
        ),
        run_id=run_id,
        important=True,
    )
    return {"notes": [f"higgsfield_director: planned {len(plan)} shots"]}


async def _build_plan(
    shots: list[dict[str, Any]], task: dict[str, Any], *, has_upload: bool = False
) -> list[dict[str, Any]]:
    valid = {int(s["i"]) for s in shots}
    dur_by_shot = {int(s["i"]): _clamp_dur(s.get("duration_s")) for s in shots}
    listing = "\n".join(
        f'{s["i"]}: {str(s.get("action") or s.get("dialogue") or "")[:120]}' for s in shots
    )[:4000]
    system = await resolve_prompt("higgsfield_director", SYSTEM_PROMPT)
    s = get_settings()
    raw = ""
    try:
        response, _usage = await call_claude(
            model=s.model_scriptwriter_revise,
            system=system,
            messages=[{"role": "user", "content": f"Mavzu: {task.get('hook') or ''}\n\nKadrlar:\n{listing}"}],
            max_tokens=2000,
            response_format="json",
            agent_name="higgsfield_director",
        )
        raw = response.get("text") or ""
    except Exception as exc:  # noqa: BLE001 — LLM down → deterministic fallback plan
        log.warning("higgsfield_director.llm_failed", error=str(exc)[:160])

    plan = normalize_plan(raw, valid, dur_by_shot)
    if not plan:
        plan = fallback_plan(shots, dur_by_shot)
        log.info("higgsfield_director.fallback_plan", shots=len(plan))
    plan = plan[:_MAX_SHOTS]
    return apply_keyframe_source(plan, has_upload=has_upload)


def apply_keyframe_source(plan: list[dict[str, Any]], *, has_upload: bool) -> list[dict[str, Any]]:
    """When a user clip exists, EDIT it: each shot grabs its keyframe from the uploaded footage at a
    per-shot timestamp (cumulative shot-duration midpoint — the worker clamps to the real duration).
    No upload → keep keyframe='generate' (FLUX from scratch). PURE/testable."""
    if not has_upload:
        return plan
    t = 0.0
    for p in plan:
        dur = float(p.get("duration_s") or 5.0)
        p["keyframe"] = "footage"
        p["footage_at_sec"] = round(t + dur / 2.0, 2)
        t += dur
    return plan


def _clamp_dur(v: Any) -> float:
    """Higgsfield clips are ~5s; clamp the storyboard duration into a sane per-clip band. PURE."""
    try:
        d = float(v)
    except (TypeError, ValueError):
        return 5.0
    return max(2.0, min(6.0, d)) if d > 0 else 5.0


def normalize_plan(
    raw: str, valid_shots: set[int], dur_by_shot: dict[int, float]
) -> list[dict[str, Any]]:
    """LLM JSON → validated per-shot Higgsfield plan (PURE/testable). Unknown/dup shots dropped,
    motion clamped to MOTION_NAMES, strength clamped, keyframe defaults to generate. Bad JSON → []."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    items = data.get("shots") if isinstance(data, dict) else None
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        si = it.get("shot_index")
        if not isinstance(si, int) or si in seen or si not in valid_shots:
            continue
        prompt = str(it.get("prompt") or "").strip()
        if not prompt:
            continue
        motion = str(it.get("motion") or "").strip().lower()
        if motion not in MOTION_NAMES:
            motion = "push_in"
        try:
            strength = float(it.get("motion_strength") or 0.6)
        except (TypeError, ValueError):
            strength = 0.6
        image_prompt = str(it.get("image_prompt") or prompt).strip()
        out.append(
            {
                "shot_index": si,
                "prompt": prompt[:600],
                "image_prompt": image_prompt[:500],
                "motion": motion,
                "motion_strength": max(0.2, min(0.95, strength)),
                "duration_s": dur_by_shot.get(si, 5.0),
                "keyframe": "generate",
                "footage_at_sec": None,
            }
        )
        seen.add(si)
    return out


def fallback_plan(shots: list[dict[str, Any]], dur_by_shot: dict[int, float]) -> list[dict[str, Any]]:
    """Deterministic plan when the LLM is unavailable — uses the (Uzbek) shot text as the prompt and
    cycles cinematic camera moves so a reel can still be generated. PURE."""
    out: list[dict[str, Any]] = []
    for n, s in enumerate(shots):
        si = int(s["i"])
        txt = str(s.get("action") or s.get("dialogue") or "cinematic vertical shot").strip()[:400]
        out.append(
            {
                "shot_index": si,
                "prompt": f"{txt}, cinematic vertical 9:16, natural lighting",
                "image_prompt": f"{txt}, cinematic vertical 9:16 still, photorealistic",
                "motion": _DEFAULT_MOTIONS[n % len(_DEFAULT_MOTIONS)],
                "motion_strength": 0.6,
                "duration_s": dur_by_shot.get(si, 5.0),
                "keyframe": "generate",
                "footage_at_sec": None,
            }
        )
    return out


def _short_hook(hook: Any) -> str:
    """The task hook, trimmed to a punchy on-screen overlay (unreadable if long). PURE."""
    if not isinstance(hook, str):
        return ""
    return " ".join(hook.split()[:7])


async def _write_render_row(task_id: str, tenant_id: str, plan: list[dict[str, Any]], *, hook: str) -> None:
    """Create the pending final_render row carrying the Higgsfield plan. Mirrors caption_stylist:
    replace any prior render + reclaim its MinIO objects so a re-generate restarts cleanly."""
    meta = json.dumps(
        {
            "renderSource": "higgsfield",
            "higgsfieldPlan": plan,
            "hookOverlay": hook,
            "captionStyle": {"font": "Montserrat"},
            "tier": "premium",
        },
        ensure_ascii=False,
    )
    sm = get_sessionmaker()
    async with sm() as session:
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
                  (:id, :t, :tn, 'final_render', 'higgsfield', 'pending', CAST(:meta AS jsonb), NOW(), NOW())
                """
            ),
            {"id": uuid.uuid4().hex, "t": task_id, "tn": tenant_id, "meta": meta},
        )
        await session.commit()
    for key in prior_keys:
        try:
            await asyncio.to_thread(delete_object, key)
        except Exception:  # noqa: BLE001 — orphan reclaim is best-effort
            log.warning("higgsfield_director.orphan_reclaim_failed", key=key, exc_info=True)


async def _write_failed_row(task_id: str, tenant_id: str, message: str) -> None:
    """Replace any prior render with a FAILED final_render row so the studio surfaces why cinematic
    generation didn't start (e.g. no usable storyboard) instead of showing nothing."""
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
                  (:id, :t, :tn, 'final_render', 'higgsfield', 'failed', :err, NOW(), NOW())
                """
            ),
            {"id": uuid.uuid4().hex, "t": task_id, "tn": tenant_id, "err": message[:500]},
        )
        await session.commit()


async def _has_upload(task_id: str, tenant_id: str) -> bool:
    """True when the task has an uploaded clip — so the Higgsfield edit uses the user's OWN footage
    frames as keyframes instead of generating stills from scratch."""
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
                text('SELECT "shotList", "scriptTimeline", hook, "audioSuggestion" FROM content_tasks WHERE id=:id'),
                {"id": task_id},
            )
        ).mappings().first()
    return dict(row) if row else None


def _as_list(raw: Any) -> list[Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw if isinstance(raw, list) else []

"""B-roll Curator — fills storyboard shots the user's footage misses with stock B-roll (Faza 3).

Runs in the montage_generation branch AFTER footage_analyzer (which it depends on) and BEFORE
caption_stylist:

  1. read the FootageMap (footage_analyzer persisted it) + the storyboard shotList,
  2. set-difference → storyboard shots the user's own footage does NOT cover,
  3. ONE fast-LLM call turns each missing shot's Uzbek `action` into a concise English
     Pexels search query (degrades to the raw action if the LLM is down),
  4. persist the plan to the user_upload TaskMedia.meta (`brollPlan`); the montage WORKER
     then deterministically searches+downloads Pexels and renders the clip as a full-frame
     overlay on that shot's OUTPUT window.

Runs inside the graph RunContext so the (cheap) fast-LLM call is billed. Fail-soft throughout:
any error just skips B-roll and lets caption_stylist + the render proceed unchanged. B-roll is
additive — it must never block or shrink a montage.
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.config import get_settings
from app.integrations.llm.fast_llm import fast_chat
from app.memory.db import get_sessionmaker
from app.montage.broll import select_broll_shots

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "Sen montaj uchun STOCK B-ROLL qidiruv so'rovlarini tuzuvchisan. Senga o'zbekcha kadr "
    "tavsiflari (storyboard 'action') beriladi. B-roll — bu gapiruvchi ustiga QO'YILADIGAN "
    "qisqa kesim, shuning uchun u faqat nutqda aytilgan ANIQ TASHQI ob'ekt/tushuncha uchun "
    "kerak (masalan: robot, grafik/diagramma, pul, telefon, savdo ekrani). "
    "AGAR kadr shunchaki odam gapirayotgan bo'lsa (person talking, speaking, presenter, "
    "camera, obuna) — b-roll KERAK EMAS, o'sha kadrni tashlab ket (unga query berma). "
    "Har bir mos kadr uchun QISQA INGLIZCHA so'rov (2-4 so'z, aniq vizual ob'ekt, brend/ism YO'Q). "
    'FAQAT JSON qaytar: {"queries":[{"shot_index":1,"query":"trading chart on screen"}]}'
)

# A query that just depicts a talking person adds nothing over the REAL speaker and yields
# distracting generic stock — drop it so the shot stays on the actual footage.
_GENERIC_BROLL_RE = re.compile(
    r"\b(persons?|people|man|men|woman|women|guy|girl|speaker|host|presenter|talking|"
    r"speaks?|speaking|presenting|camera|selfie|face|subscrib\w*|influencer|vlogger|blogger)\b",
    re.IGNORECASE,
)


def _is_generic_query(q: str) -> bool:
    """True when the query merely shows a talking person (redundant with the real speaker).
    PURE/testable."""
    return bool(_GENERIC_BROLL_RE.search(q or ""))


def mark_generation(plan: list[dict[str, Any]], enabled: bool) -> list[dict[str, Any]]:
    """Opt-in cinematic: when enabled (ENABLE_GEN_BROLL + FAL_KEY), mark each planned shot
    source='generate' with the search query as the gen prompt — resolve_broll then GENERATES the
    clip (fal.ai) and falls back to the stock `query` on any failure. PURE/testable."""
    if not enabled:
        return plan
    return [{**e, "source": "generate", "prompt": str(e.get("query") or "")} for e in plan]


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
        upload = await _latest_upload(task_id, tenant_id)
        if not upload:
            return {"notes": ["broll_curator: no upload"]}
        footage_map = _meta_dict(upload.get("meta")).get("footageMap")
        shot_list = await _storyboard(task_id, tenant_id)
        shots = select_broll_shots(footage_map, shot_list)
        if not shots:
            # Either full coverage or the vision pass was unreliable — no b-roll (correct).
            return {"notes": ["broll_curator: no b-roll needed"]}

        plan = await _craft_queries(shots)
        if not plan:
            return {"notes": ["broll_curator: no plan"]}
        s = get_settings()
        plan = mark_generation(plan, bool(s.enable_gen_broll and s.fal_key))
        await _persist(upload["id"], tenant_id, plan)

        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="writer",
            content=f"B-roll rejalashtirildi · {len(plan)} ta yetishmagan kadr stock video bilan to'ldiriladi",
            run_id=run_id,
        )
        return {"notes": [f"broll_curator: planned {len(plan)} b-roll shots"]}
    except Exception as exc:  # noqa: BLE001 — never block caption_stylist / the render
        log.warning("broll_curator.failed", error=str(exc)[:200])
        return {"notes": ["broll_curator: skipped (error)"]}


async def _craft_queries(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Uz `action` → concise EN Pexels query (one batched fast-LLM call). On any failure,
    fall back to the raw action so b-roll still works (Pexels handles many languages)."""
    fallback = [
        {"shot_index": s["shot_index"], "query": s["action"][:60]}
        for s in shots
        if not _is_generic_query(s["action"])
    ]
    try:
        listing = "\n".join(f'{s["shot_index"]}: {s["action"][:80]}' for s in shots)
        raw = await fast_chat(
            system=SYSTEM_PROMPT,
            user=f"Kadrlar:\n{listing}",
            json=True,
            max_tokens=400,
            agent_name="broll_curator",
        )
        data = json.loads(raw)
        by_index: dict[int, str] = {}
        for q in data.get("queries") or []:
            if isinstance(q, dict) and isinstance(q.get("shot_index"), int):
                qs = str(q.get("query") or "").strip()
                if qs:
                    by_index[q["shot_index"]] = qs[:80]
        out: list[dict[str, Any]] = []
        for s in shots:
            q = by_index.get(s["shot_index"]) or s["action"][:60]
            if _is_generic_query(q):
                continue  # a talking-person query duplicates the real speaker — keep the footage
            out.append({"shot_index": s["shot_index"], "query": q})
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("broll_curator.llm_fallback", error=str(exc)[:160])
        return fallback


def _meta_dict(meta: Any) -> dict[str, Any]:
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return {}
    return meta if isinstance(meta, dict) else {}


async def _latest_upload(task_id: str, tenant_id: str) -> dict[str, Any] | None:
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text(
                    'SELECT id, meta FROM task_media '
                    "WHERE \"taskId\"=:t AND \"tenantId\"=:tn AND kind='user_upload' "
                    'AND "objectKey" IS NOT NULL ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"t": task_id, "tn": tenant_id},
            )
        ).mappings().first()
    return dict(row) if row else None


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


async def _persist(media_id: str, tenant_id: str, plan: list[dict[str, Any]]) -> None:
    """Merge the B-roll plan into the user_upload row meta (jsonb concat preserves footageMap)."""
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                "UPDATE task_media SET "
                "meta = COALESCE(meta, '{}'::jsonb) || "
                "jsonb_build_object('brollPlan', CAST(:bp AS jsonb)), "
                '"updatedAt" = NOW() WHERE id = :id AND "tenantId" = :tn'
            ),
            {"bp": json.dumps(plan), "id": media_id, "tn": tenant_id},
        )
        await session.commit()

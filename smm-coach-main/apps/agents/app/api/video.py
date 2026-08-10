"""Deep video critique — the user-facing half of "video understanding everywhere".

The coach WATCHES the task's uploaded clip (Gemini Files API, 720p+audio) and returns a precise,
structured critique: what's on screen (incl. read-back of on-screen text), effects, pacing, hook,
strengths, concrete fixes, quality issues, a score. Synchronous (the caller waits ~20-40s) — used
by the voice coach's `critique_video` tool and (next) a task-page panel. HMAC-protected like the
rest of the agents API. Fail-soft: any failure returns ok=False with an Uzbek reason.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import tempfile
import uuid
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.integrations import telegram
from app.integrations.instagram import instagrapi_client
from app.integrations.llm.gemini_client import analyze_video, analyze_video_file
from app.memory.db import get_sessionmaker
from app.montage.footage_vision import make_vision_proxy_hq
from app.montage.storage import download_object
from app.montage.transcribe import TranscriptError, transcribe_words
from app.runs.context import RunContext, reset_current, set_current

log = structlog.get_logger(__name__)

router = APIRouter()

# In-flight guard: the critique is a synchronous ~20-40s billable Gemini run. A double-click, or the
# voice-coach `critique_video` tool firing at the same time as the task-page panel, would otherwise
# launch the same expensive run twice. Keyed by tenant:task; self-cleaning via the finally discard.
_critique_inflight: set[str] = set()

_CRITIQUE_PROMPT = """Sen — tajribali SMM montaj murabbiysi. Bu foydalanuvchining YUKLAGAN xom videosini DIQQAT bilan ko'r va ESHIT (audio bor), keyin ANIQ, foydali kritika ber. Maqtab o'tirma — aniq ko'rgan narsangga asoslan.
FAQAT JSON qaytar (o'zbekcha qiymatlar):
{
  "summary": "1-2 jumla: video nima haqida va umumiy taassurot",
  "on_screen_text": ["ekranda ko'ringan HAR BIR yozuvni aynan o'qib yoz (yo'q bo'lsa bo'sh)"],
  "visual_elements": ["asosiy vizual element / effekt / o'tish — har biri qisqa, aniq"],
  "pacing": "ritm va tempo haqida 1 jumla (sekin/tez, zerikarli joy bormi)",
  "hook": "dastlabki 3 soniya tomoshabinni ushlab turadimi — 1 jumla",
  "strengths": ["kuchli tomonlar — aniq"],
  "improvements": ["ANIQ tuzatish tavsiyalari — nima qilsa yaxshilanadi"],
  "quality_issues": ["texnik muammolar: qorong'ilik, fokus yo'q, ovoz past, matn o'qilmaydi, titrash... (yo'q bo'lsa bo'sh)"],
  "overall_score": 7
}"""


class VideoCritiqueRequest(BaseModel):
    tenantId: str = Field(..., min_length=1)
    userId: str | None = None
    taskId: str = Field(..., min_length=1)
    force: bool = False  # bypass the cached critique and re-run Gemini


@router.post("/critique")
async def video_critique(req: VideoCritiqueRequest) -> dict[str, Any]:
    upload = await _latest_upload(req.taskId, req.tenantId)
    if not upload or not upload.get("objectKey"):
        return {"ok": False, "error": "Bu vazifaga hali video yuklanmagan."}

    # vuc-04: the critique is a slow (~proxy + 150s Files-poll + generate) billable run that can
    # exceed the 180s client timeout. If we already have one cached on the upload row, return it
    # instantly — a post-timeout retry then costs nothing instead of re-paying Gemini. force=true
    # (explicit "qayta tahlil qil") bypasses the cache.
    if not req.force:
        cached = (upload.get("meta") or {}).get("videoCritique")
        if isinstance(cached, dict) and cached:
            return {"ok": True, "critique": cached, "cached": True}

    key = f"{req.tenantId}:{req.taskId}"
    if key in _critique_inflight:
        return {"ok": False, "error": "Tahlil allaqachon davom etmoqda — bir lahza kuting."}
    _critique_inflight.add(key)
    telegram.send("🎥 Yuklangan video AI tomonidan ko'rilmoqda (montaj kritikasi)")

    # RunContext so the (billable) Gemini call attributes to the tenant + shows in the Inspector
    # + respects the budget guard — exactly like a graph node.
    token = set_current(
        RunContext(
            tenant_id=req.tenantId, user_id=req.userId,
            run_id="vcrit-" + uuid.uuid4().hex[:12], workflow="video_critique",
        )
    )
    try:
        hq_path = await asyncio.to_thread(_prepare_proxy, upload["objectKey"])
        if not hq_path:
            return {"ok": False, "error": "Videoni o'qib bo'lmadi."}
        try:
            raw = await analyze_video_file(
                path=hq_path, question=_CRITIQUE_PROMPT,
                agent_name="video_critic", json_mode=True, max_output_tokens=3000,
            )
        finally:
            with contextlib.suppress(OSError):
                os.unlink(hq_path)

        crit = _parse_critique(raw)
        if not crit:
            return {"ok": False, "error": "Tahlil qilib bo'lmadi — qayta urinib ko'ring."}
        with contextlib.suppress(Exception):
            await _persist_critique(req.taskId, req.tenantId, crit)
        score = crit.get("overall_score")
        telegram.send(
            f"✅ Video kritikasi tayyor{f' · baho {score}/10' if score is not None else ''}"
        )
        return {"ok": True, "critique": crit}
    except Exception as exc:  # noqa: BLE001 — best-effort; surface a clean reason
        log.warning("video_critique.failed", error=str(exc)[:200])
        telegram.send("❌ Video kritikasi xatosi")
        return {"ok": False, "error": "Tahlil xatosi — qayta urinib ko'ring."}
    finally:
        _critique_inflight.discard(key)
        reset_current(token)


def _prepare_proxy(object_key: str) -> str | None:
    """SYNC, thread-offloaded: download the upload → build a 720p+audio HQ proxy on a SURVIVING
    temp path (the async Files-API upload needs a path that outlives this temp dir)."""
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "src")
        download_object(object_key, src)
        fd, hq = tempfile.mkstemp(suffix=".mp4", prefix="vcrit-")
        os.close(fd)
        out = make_vision_proxy_hq(src, hq)
        if out is None:
            with contextlib.suppress(OSError):
                os.remove(hq)
        return out


_LIST_KEYS = ("on_screen_text", "visual_elements", "strengths", "improvements", "quality_issues")


def _parse_critique(raw: str) -> dict[str, Any] | None:
    """Parse + sanitise the critique JSON. Returns None if nothing usable came back."""
    if not raw:
        return None
    candidates = [raw]
    s, e = raw.find("{"), raw.rfind("}")
    if s >= 0 and e > s:
        candidates.append(raw[s : e + 1])
    data: dict[str, Any] | None = None
    for c in candidates:
        with contextlib.suppress(json.JSONDecodeError):
            parsed = json.loads(c)
            if isinstance(parsed, dict):
                data = parsed
                break
    if data is None:
        return None
    out: dict[str, Any] = {
        "summary": str(data.get("summary") or "")[:600],
        "pacing": str(data.get("pacing") or "")[:300],
        "hook": str(data.get("hook") or "")[:300],
    }
    for k in _LIST_KEYS:
        v = data.get(k)
        out[k] = [str(x)[:240] for x in v][:12] if isinstance(v, list) else []
    score = data.get("overall_score")
    out["overall_score"] = int(score) if isinstance(score, (int, float)) and 0 <= score <= 10 else None
    # Require at least SOME signal — an all-empty parse is a failure.
    if not out["summary"] and not out["visual_elements"] and not out["improvements"]:
        return None
    return out


async def _latest_upload(task_id: str, tenant_id: str) -> dict[str, Any] | None:
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text(
                    'SELECT id, "objectKey", meta FROM task_media '
                    "WHERE \"taskId\"=:t AND \"tenantId\"=:tn AND kind='user_upload' "
                    'AND "objectKey" IS NOT NULL ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"t": task_id, "tn": tenant_id},
            )
        ).mappings().first()
    return dict(row) if row else None


async def _persist_critique(task_id: str, tenant_id: str, crit: dict[str, Any]) -> None:
    """Cache the critique on the latest user_upload row (jsonb merge preserves footageMap/brollPlan)."""
    sm = get_sessionmaker()
    async with sm() as session:
        # Stamp ONLY the latest upload (the row that was actually critiqued) — the old WHERE matched
        # EVERY user_upload row, so re-uploading left stale identical critiques on older clips.
        await session.execute(
            text(
                "UPDATE task_media SET "
                "meta = COALESCE(meta, '{}'::jsonb) || "
                "jsonb_build_object('videoCritique', CAST(:c AS jsonb)), "
                '"updatedAt" = NOW() '
                "WHERE id = (SELECT id FROM task_media "
                "WHERE \"taskId\"=:t AND \"tenantId\"=:tn AND kind='user_upload' "
                'AND "objectKey" IS NOT NULL ORDER BY "createdAt" DESC LIMIT 1)'
            ),
            {"c": json.dumps(crit), "t": task_id, "tn": tenant_id},
        )
        await session.commit()


# ── Reference / competitor video technique breakdown ─────────────────────────

_REFERENCE_PROMPT = """Sen — viral SMM montaj tahlilchisi. Bu REFERENCE (namuna/raqobatchi) videoni DIQQAT bilan ko'r va ESHIT. Maqsad: NEGA bu video ishlaydi va foydalanuvchi shu TEXNIKANI o'z kontentiga qanday qo'llashini ANIQ ayt (umumiy gap emas, amaliy).
FAQAT JSON (o'zbekcha qiymatlar):
{
  "summary": "video nima haqida va nega e'tibor tortadi (1-2 jumla)",
  "hook_technique": "dastlabki 3 soniya tomoshabinni qanday ushlaydi — aniq texnika",
  "editing": "kesim ritmi, o'tishlar, effektlar, tempo — nima qilingan",
  "structure": "tuzilishi: hook → asosiy → yakun/CTA",
  "why_it_works": ["nega ishlaydi — aniq sabablar"],
  "apply_to_you": ["SENGA qanday qo'llash — aniq, amaliy qadamlar"]
}"""


class VideoReferenceRequest(BaseModel):
    tenantId: str = Field(..., min_length=1)
    userId: str | None = None
    ref: str = Field(..., min_length=1, max_length=400)  # IG reel link/shortcode OR a direct video URL


@router.post("/reference")
async def video_reference(req: VideoReferenceRequest) -> dict[str, Any]:
    ref = req.ref.strip()
    # Same in-flight guard as /critique: resolving + analyzing a reel is a billable Gemini run, so a
    # double-submit of the same link must not fire it twice.
    key = f"{req.tenantId}:{ref}"
    if key in _critique_inflight:
        return {"ok": False, "error": "Bu video tahlili davom etmoqda — bir lahza kuting."}
    _critique_inflight.add(key)
    telegram.send(f"🔬 Namuna (reference) video texnikasi tahlil qilinmoqda · {ref[:60]}")
    token = set_current(
        RunContext(
            tenant_id=req.tenantId, user_id=req.userId,
            run_id="vref-" + uuid.uuid4().hex[:12], workflow="video_reference",
        )
    )
    try:
        # An IG link/shortcode is resolved to its CDN video URL via instagrapi; a direct video URL
        # is used as-is. analyze_video routes big reels through the Files API (no 18MB cap).
        video_url = ref
        if "instagram.com" in ref or not ref.startswith("http"):
            try:
                detail = await instagrapi_client.fetch_post_detail(ref, comments_limit=0)
                video_url = str(detail.get("video_url") or "")
            except Exception as exc:  # noqa: BLE001 — scraping is flaky (challenge/rate-limit)
                log.warning("video_reference.resolve_failed", error=str(exc)[:160])
                video_url = ""
        if not video_url or not video_url.startswith("http"):
            return {"ok": False, "error": "Videoni ololmadim — to'g'ridan-to'g'ri video URL bering."}

        raw = await analyze_video(
            video_url=video_url, question=_REFERENCE_PROMPT,
            agent_name="reference_critic", json_mode=True, max_output_tokens=3000,
        )
        data = _parse_reference(raw)
        if not data:
            return {"ok": False, "error": "Tahlil qilib bo'lmadi — qayta urinib ko'ring."}
        telegram.send("✅ Namuna video texnikasi tahlili tayyor")
        return {"ok": True, "reference": data}
    except Exception as exc:  # noqa: BLE001
        log.warning("video_reference.failed", error=str(exc)[:200])
        telegram.send("❌ Namuna video tahlili xatosi")
        return {"ok": False, "error": "Tahlil xatosi — qayta urinib ko'ring."}
    finally:
        _critique_inflight.discard(key)
        reset_current(token)


def _parse_reference(raw: str) -> dict[str, Any] | None:
    """Parse + sanitise the reference-technique JSON. None if nothing usable came back."""
    if not raw:
        return None
    candidates = [raw]
    s, e = raw.find("{"), raw.rfind("}")
    if s >= 0 and e > s:
        candidates.append(raw[s : e + 1])
    data: dict[str, Any] | None = None
    for c in candidates:
        with contextlib.suppress(json.JSONDecodeError):
            parsed = json.loads(c)
            if isinstance(parsed, dict):
                data = parsed
                break
    if data is None:
        return None
    out: dict[str, Any] = {
        "summary": str(data.get("summary") or "")[:600],
        "hook_technique": str(data.get("hook_technique") or "")[:400],
        "editing": str(data.get("editing") or "")[:400],
        "structure": str(data.get("structure") or "")[:400],
    }
    for k in ("why_it_works", "apply_to_you"):
        v = data.get(k)
        out[k] = [str(x)[:240] for x in v][:8] if isinstance(v, list) else []
    if not out["summary"] and not out["why_it_works"] and not out["apply_to_you"]:
        return None
    return out


# ── Word-level transcript of the task's upload (SOURCE seconds) ───────────────


class VideoTranscriptRequest(BaseModel):
    tenantId: str = Field(..., min_length=1)
    taskId: str = Field(..., min_length=1)


@router.post("/transcript")
async def video_transcript(req: VideoTranscriptRequest) -> dict[str, Any]:
    """Word-level transcript [{text, start, end}] in SOURCE seconds of the task's uploaded clip —
    so the coach can target edits by WHAT is said at a given moment ('cut where I stumble'). Cached
    by the upload identity (transcribe_words). The coach route maps these to OUTPUT/timeline time."""
    upload = await _latest_upload(req.taskId, req.tenantId)
    if not upload or not upload.get("objectKey"):
        return {"ok": False, "error": "Bu vazifaga hali video yuklanmagan."}
    key = str(upload["objectKey"])
    telegram.send("📝 Video nutqi transkript qilinmoqda (so'zma-so'z)")
    try:
        words = await asyncio.to_thread(_transcript_words, key)
    except TranscriptError as exc:
        # Infrastructure failure (key missing / extract / API) — tell the user the real cause
        # instead of the misleading "no speech".
        log.warning("video_transcript.unavailable", reason=exc.reason)
        return {"ok": False, "error": exc.message}
    except Exception as exc:  # noqa: BLE001
        log.warning("video_transcript.failed", error=str(exc)[:200])
        return {"ok": False, "error": "Transkript xatosi."}
    if not words:
        return {"ok": False, "error": "Nutq topilmadi (subtitr-mos transkript yo'q)."}
    # Cap so a 90s reel's transcript can't blow the coach's context window.
    return {"ok": True, "words": words[:400]}


def _transcript_words(object_key: str) -> list[dict[str, Any]] | None:
    """SYNC, thread-offloaded: download the upload, transcribe (Whisper extracts audio from any
    video; cached by object_key so re-asks are free). strict=True so infrastructure failures raise
    TranscriptError (distinct from a genuinely silent clip)."""
    with tempfile.TemporaryDirectory(prefix="vtr-") as wd:
        src = os.path.join(wd, "src")
        download_object(object_key, src)
        return transcribe_words(src, cache_key=object_key, strict=True)

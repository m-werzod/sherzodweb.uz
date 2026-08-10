"""Footage Analyzer — the montage system's eyes (Faza 1, G2 fix).

Before this node the montage was blind: it cut on silence and never saw the footage.
footage_analyzer runs FIRST in the montage_generation branch (before caption_stylist):

  1. find the user's uploaded clip, download it (+ probe + scene-detect) in a thread,
     and build a small <18MB vision proxy   — all license-clean ffmpeg, no LLM.
  2. Gemini WATCHES the proxy and describes each shot + which storyboard shot it matches.
  3. persist the FootageMap into the user_upload TaskMedia.meta (inspectable; consumed by
     later faza for content-aware cuts / transitions / b-roll).

Runs inside the graph's RunContext, so the Gemini call IS billed to the tenant (the
montage_worker can't bill — it has no RunContext). Fail-soft throughout: any error just
skips the analysis and lets caption_stylist + the render proceed unchanged.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import tempfile
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.integrations.llm.gemini_client import analyze_video_bytes, analyze_video_file
from app.memory.db import get_sessionmaker
from app.montage.footage import FootageMap, ShotBoundary
from app.montage.footage_vision import (
    detect_shots,
    make_vision_proxy,
    make_vision_proxy_hq,
    shots_from_scene_times,
    to_analysis_proxy,
)
from app.montage.probe import ClipInfo, probe_clip
from app.montage.storage import download_object

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)


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
            return {"notes": ["footage_analyzer: no upload to analyse"]}
        shot_list = await _storyboard(task_id, tenant_id)

        # I/O + ffmpeg (download, probe, scene-detect, proxy) — no LLM, no RunContext needed,
        # so it goes to a thread. The Gemini call stays in the async node where context lives.
        proxy, hq_path, shots, info = await asyncio.to_thread(_prepare, upload["objectKey"])
        if not shots:
            if hq_path:
                with contextlib.suppress(OSError):
                    os.unlink(hq_path)
            return {"notes": ["footage_analyzer: clip unreadable"]}

        answer = ""
        # DEEP path first: Gemini WATCHES a 720p+audio proxy via the Files API — it reads on-screen
        # text + fine effects the 360p inline proxy can't show. Falls back to inline on any failure.
        if hq_path:
            answer = await analyze_video_file(
                path=hq_path,
                question=_prompt(shots, shot_list),
                agent_name="footage_analyzer",
                json_mode=True,
                max_output_tokens=2500,
            )
            with contextlib.suppress(OSError):
                os.unlink(hq_path)
        if not answer and proxy is not None:
            answer = await analyze_video_bytes(
                video_bytes=proxy,
                question=_prompt(shots, shot_list),
                agent_name="footage_analyzer",
                json_mode=True,
                max_output_tokens=1500,
            )
        fmap = _build_footage_map(task_id, tenant_id, info, shots, answer)
        await _persist(upload["id"], tenant_id, fmap)

        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="writer",
            content=(
                f"Footage ko'rib chiqildi · {len(fmap.shots)} shot"
                + (f" · {fmap.vision_summary}" if fmap.vision_ok and fmap.vision_summary else "")
            ),
            run_id=run_id,
        )
        return {"notes": [f"footage_analyzer: {len(fmap.shots)} shots, vision={fmap.vision_ok}"]}
    except Exception as exc:  # noqa: BLE001 — never block caption_stylist / the render
        log.warning("footage_analyzer.failed", error=str(exc)[:200])
        return {"notes": ["footage_analyzer: skipped (error)"]}


def _prepare(object_key: str) -> tuple[bytes | None, str | None, list[ShotBoundary], ClipInfo]:
    """SYNC, thread-offloaded: download → probe → scene-detect → BOTH vision proxies. Returns
    (inline_proxy_bytes, hq_proxy_path, shots, info). The HQ proxy (Files API) is written OUTSIDE
    the temp dir so it survives for the async upload; the caller deletes it."""
    hq_path: str | None = None
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "src")
        download_object(object_key, src)
        info = probe_clip(src)
        # The EXPENSIVE decode (4K / 60fps / HEVC / Dolby-Vision phone footage) happens ONCE here,
        # producing a light working copy; detect_shots + both vision proxies then run on THAT instead
        # of re-decoding the raw 4K clip three times (which overran the run lease → the node looped
        # forever → montage stuck at 'navbatda'). Duration is preserved, so shot times stay valid.
        # Degrade-safe: if the downscale fails, fall back to the raw source.
        work = to_analysis_proxy(src, os.path.join(wd, "work.mp4")) or src
        shots = shots_from_scene_times(detect_shots(work), info.duration)
        proxy = make_vision_proxy(work, os.path.join(wd, "proxy.mp4"))
        fd, hq_candidate = tempfile.mkstemp(suffix=".mp4", prefix="vproxy-hq-")
        os.close(fd)
        hq_path = make_vision_proxy_hq(work, hq_candidate)
        if hq_path is None:  # build failed → don't leave the empty mkstemp file behind
            with contextlib.suppress(OSError):
                os.remove(hq_candidate)
    return proxy, hq_path, shots, info


def _prompt(shots: list[ShotBoundary], shot_list: list[Any]) -> str:
    shot_lines = "\n".join(f"  shot {s.index}: {s.src_start:.1f}-{s.src_end:.1f}s" for s in shots)
    sb_lines = (
        "\n".join(
            f"  kadr {sl.get('i')}: {str(sl.get('action') or '')[:60]} ({sl.get('frame') or ''})"
            for sl in shot_list
            if isinstance(sl, dict) and isinstance(sl.get("i"), int)
        )
        or "  (storyboard yo'q)"
    )
    return f"""Bu yuklangan XOM videoni DIQQAT bilan ko'r va ESHIT (audio bor). Video {len(shots)} ta shotga bo'lingan (vaqtlar quyida — SOURCE soniya).
Har shot uchun ayt: ekranda AYNAN nima ko'rinadi — agar EKRAN-MATNI (subtitr/titr/raqam) bo'lsa uni AYNAN o'qib yoz, vizual EFFEKT yoki o'tish bo'lsa nomla (description, 8-16 so'z, aniq); asosiy sub'ekt (subject: person/product/text/screen/hands/scene), asosiy harakat (primary_action), va STORYBOARD kadrlaridan qaysi biriga eng mos kelishini (matched_shot_index = kadr raqami; ishonchli mos yo'q bo'lsa 0). motion_score = harakat darajasi 0..1. confidence = matched_shot_index mosligi qanchalik ishonchli 0..1 (mos yo'q yoki shubhali bo'lsa past qo'y — b-roll shu asosda to'ldiradi).

SHOTLAR:
{shot_lines}

STORYBOARD (rejalashtirilgan kadrlar):
{sb_lines}

FAQAT JSON:
{{"shots":[{{"index":0,"description":"...","subject":"...","primary_action":"...","matched_shot_index":0,"motion_score":0.5,"confidence":0.8}}],"vision_summary":"<1-2 jumla: bu qanday video>","detected_subjects":["..."]}}"""


def _build_footage_map(
    task_id: str,
    tenant_id: str,
    info: ClipInfo,
    shots: list[ShotBoundary],
    answer: str,
) -> FootageMap:
    parsed = _parse_json(answer)
    by_index: dict[int, dict[str, Any]] = {}
    for sd in parsed.get("shots") or []:
        if isinstance(sd, dict) and isinstance(sd.get("index"), int):
            by_index[sd["index"]] = sd
    merged = 0
    for s in shots:
        sd = by_index.get(s.index)
        if not isinstance(sd, dict):
            continue
        s.description = str(sd.get("description") or "")[:240]
        s.subject = str(sd.get("subject") or "")[:40]
        s.primary_action = str(sd.get("primary_action") or "")[:40]
        if isinstance(sd.get("matched_shot_index"), int) and sd["matched_shot_index"] >= 1:
            s.matched_shot_index = sd["matched_shot_index"]
        ms = sd.get("motion_score")
        if isinstance(ms, (int, float)):
            s.motion_score = max(0.0, min(1.0, float(ms)))
        # Match confidence — makes the b-roll/semantic-cut conf_floor (_CONF_FLOOR=0.5) a LIVE signal.
        # Was never set (stayed the 1.0 default), so every match counted as fully confident and the
        # guard never discriminated: a weak/wrong storyboard match was treated as covered, so b-roll
        # didn't fill it and the semantic cut trusted a shaky alignment. Absent → keep 1.0 (old behavior).
        cf = sd.get("confidence")
        if isinstance(cf, (int, float)):
            s.confidence = max(0.0, min(1.0, float(cf)))
        merged += 1
    subjects = parsed.get("detected_subjects")
    summary = str(parsed.get("vision_summary") or "")[:400]
    return FootageMap(
        task_id=task_id,
        tenant_id=tenant_id,
        duration_sec=info.duration,
        fps=info.fps or 30.0,
        width=info.width or 1080,
        height=info.height or 1920,
        shots=shots,
        vision_summary=summary,
        detected_subjects=(
            [str(x)[:40] for x in subjects][:12] if isinstance(subjects, list) else []
        ),
        # vision_ok reflects ACTUAL enrichment: Gemini returning a shots[] whose indices
        # match nothing (zero shots enriched) must not falsely claim the footage was seen.
        vision_ok=bool(merged or summary),
    )


def _parse_json(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
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


async def _latest_upload(task_id: str, tenant_id: str) -> dict[str, Any] | None:
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


async def _persist(media_id: str, tenant_id: str, fmap: FootageMap) -> None:
    """Merge the FootageMap into the user_upload row's meta (jsonb concat — preserves any
    other meta keys; the footageMap key itself is replaced on re-analysis). Tenant-scoped
    WHERE for defense-in-depth even though media_id was fetched tenant-scoped."""
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                "UPDATE task_media SET "
                "meta = COALESCE(meta, '{}'::jsonb) || "
                "jsonb_build_object('footageMap', CAST(:fm AS jsonb)), "
                '"updatedAt" = NOW() WHERE id = :id AND "tenantId" = :tn'
            ),
            {"fm": fmap.model_dump_json(), "id": media_id, "tn": tenant_id},
        )
        await session.commit()

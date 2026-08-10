"""POST /v1/transcode — ensure a browser-friendly MP4 (H.264/AAC) of a task's
source upload exists.

STUDIO (the browser editor) decodes source audio via the Web Audio API's
``decodeAudioData``, which Chromium **rejects for QuickTime/.mov** containers —
so a montage built from an iPhone .mov exports SILENTLY with no audio (video,
decoded by the native <video> element, is fine). We sidestep that by remuxing
the upload to a plain MP4 once, server-side, and handing STUDIO that instead.

ASYNC: this endpoint NO LONGER blocks on ffmpeg. It returns immediately —
``ready`` (cached), ``passthrough`` (already MP4), or ``pending`` (transcode
kicked off in the background) — so the web's "Studioga kirish" click never holds
a multi-minute HTTP connection. The clip route serves the raw upload until the
``studio_source`` MP4 is ready. The encode also runs under ENCODE_GATE so it
never races the montage render for CPU. HMAC-protected like every ``/v1/*`` route.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from typing import cast

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.integrations import telegram
from app.memory.db import get_sessionmaker
from app.montage.gate import ENCODE_GATE
from app.montage.probe import input_reject_reason, probe_clip, run_ff
from app.montage.storage import download_object, media_url, upload_object

log = structlog.get_logger(__name__)
router = APIRouter()

# Containers Chromium's decodeAudioData can't demux → must be remuxed to MP4.
_TRANSCODE_EXT = (".mov", ".qt", ".mkv", ".webm", ".avi", ".m4v", ".3gp", ".flv", ".wmv", ".mts", ".ts")
# Input guard — shared limits with the montage worker (OOM lever).
_MAX_INPUT_PIXELS = int(os.getenv("MONTAGE_MAX_INPUT_PIXELS") or str(3840 * 2160))
_MAX_INPUT_SECONDS = float(os.getenv("MONTAGE_MAX_INPUT_SECONDS") or "1200")

# Per-process guards so one task can't spawn two concurrent transcodes, and the
# fire-and-forget tasks aren't GC'd before they finish.
_inflight: set[str] = set()
_tasks: set[asyncio.Task[None]] = set()


class TranscodeRequest(BaseModel):
    tenant_id: str = Field(..., alias="tenantId")
    task_id: str = Field(..., alias="taskId")
    model_config = {"populate_by_name": True}


class TranscodeResponse(BaseModel):
    status: str  # 'ready' (cached) | 'passthrough' (already mp4) | 'pending' (transcoding)
    object_key: str | None = Field(default=None, alias="objectKey")
    url: str | None = None
    model_config = {"populate_by_name": True}


def _needs_transcode(object_key: str, content_type: str | None) -> bool:
    key = object_key.lower()
    if key.endswith(".mp4") or key.endswith(".m4a"):
        return False  # mp4 container — decodeAudioData handles it
    if any(key.endswith(ext) for ext in _TRANSCODE_EXT):
        return True
    # unknown extension → transcode unless the content-type says mp4
    return "mp4" not in (content_type or "").lower()


def _transcode(upload_key: str, out_key: str) -> None:
    """Sync, thread-offloaded: pull the upload, remux to a browser MP4, push it."""
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "src")
        out = os.path.join(wd, "out.mp4")
        download_object(upload_key, src)
        info = probe_clip(src)
        reason = input_reject_reason(info, max_pixels=_MAX_INPUT_PIXELS, max_seconds=_MAX_INPUT_SECONDS)
        if reason:
            raise ValueError(reason)
        # Probe-first: if the video is already H.264, COPY it — audio is the only
        # reason to convert (decodeAudioData rejects .mov), so a video re-encode is
        # wasted work. ~10x cheaper/faster than libx264 for the common H.264 case.
        # Otherwise (HEVC / 4K / 60fps / Dolby-Vision phone footage) we MUST re-encode — and we
        # DOWNSCALE to <=1080x1920 + cap 30fps + collapse HDR (format=yuv420p) so encoding a 4K60
        # clip is feasible on CPU libx264 (encoding at native 4K ran at ~0.4fps → 600s timeout). The
        # editor target is a 9:16 1080p reel, so nothing is lost. superfast keeps it quick.
        vargs = ["-c:v", "copy"] if info.codec_name == "h264" else [
            "-vf",
            "scale='min(1080,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "superfast", "-crf", "23",
        ]
        with ENCODE_GATE:  # never race the montage render for CPU
            run_ff(
                ["ffmpeg", "-y", "-i", src, *vargs,
                 "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
            )
        upload_object(out_key, out, content_type="video/mp4")


async def _persist_studio_source(tenant_id: str, task_id: str, out_key: str, upload_key: str) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                """INSERT INTO task_media
                     (id, "taskId", "tenantId", kind, provider, status, "objectKey", url,
                      "contentType", "costUsd", meta, "completedAt", "createdAt", "updatedAt")
                   VALUES
                     (:id, :t, :tn, 'studio_source', 'ffmpeg', 'ready', :key, :url,
                      'video/mp4', 0, CAST(:meta AS jsonb), NOW(), NOW(), NOW())"""
            ),
            {
                "id": uuid.uuid4().hex, "t": task_id, "tn": tenant_id,
                "key": out_key, "url": media_url(out_key),
                "meta": json.dumps({"sourceKey": upload_key}),
            },
        )
        await session.commit()


async def _transcode_bg(tenant_id: str, task_id: str, upload_key: str) -> None:
    """Background: transcode + persist a studio_source MP4. A restart orphans this
    (no ready row) but it self-heals — the next /v1/transcode re-spawns it, and the
    clip route serves the raw upload meanwhile."""
    media_id = uuid.uuid4().hex
    out_key = f"{tenant_id}/{task_id}/studio-src-{media_id}.mp4"
    telegram.send("🎞 Video studiya uchun MP4 formatiga o'girilmoqda")
    try:
        await asyncio.to_thread(_transcode, upload_key, out_key)
        await _persist_studio_source(tenant_id, task_id, out_key, upload_key)
        log.info("transcode.done", task_id=task_id, out_key=out_key)
        telegram.send("✅ Video studiyaga tayyor (MP4)")
    except Exception as exc:  # noqa: BLE001
        log.exception("transcode.failed", task_id=task_id, error=str(exc))
        telegram.send("❌ Video o'girishda xato")
    finally:
        _inflight.discard(task_id)


@router.post("", response_model=TranscodeResponse)
async def ensure_source_mp4(req: TranscodeRequest) -> TranscodeResponse:
    sm = get_sessionmaker()
    async with sm() as session:
        existing = await session.execute(
            text(
                """SELECT "objectKey", url FROM task_media
                   WHERE "taskId"=:t AND kind='studio_source' AND status='ready'
                     AND "objectKey" IS NOT NULL ORDER BY "createdAt" DESC LIMIT 1"""
            ),
            {"t": req.task_id},
        )
        row = existing.first()
        if row:
            return TranscodeResponse(status="ready", object_key=cast("str", row[0]), url=cast("str", row[1]))

        up = await session.execute(
            text(
                """SELECT "objectKey", "contentType" FROM task_media
                   WHERE "taskId"=:t AND kind='user_upload' AND "objectKey" IS NOT NULL
                   ORDER BY "createdAt" DESC LIMIT 1"""
            ),
            {"t": req.task_id},
        )
        uprow = up.first()
    if not uprow:
        raise HTTPException(status_code=404, detail="no_upload")
    upload_key = cast("str", uprow[0])
    content_type = cast("str | None", uprow[1])

    if not _needs_transcode(upload_key, content_type):
        return TranscodeResponse(status="passthrough", object_key=upload_key, url=media_url(upload_key))

    # Not cached + needs transcode → kick it off in the BACKGROUND and return
    # immediately (no 180s held HTTP connection). The clip route serves the raw
    # upload until the studio_source MP4 is ready.
    if req.task_id not in _inflight:
        _inflight.add(req.task_id)
        t = asyncio.create_task(_transcode_bg(req.tenant_id, req.task_id, upload_key))
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)
    return TranscodeResponse(status="pending", object_key=None, url=None)

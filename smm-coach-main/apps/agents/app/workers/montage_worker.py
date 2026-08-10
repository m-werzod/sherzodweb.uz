"""Montage render worker — polls pending `final_render` rows and renders them.

The agents have no job queue (every worker is a DB-poller), so the hand-off is a
TaskMedia row: the web creates a `final_render` row with status='pending' when
the user uploads a clip; this worker claims it (FOR UPDATE SKIP LOCKED), runs the
deterministic compiler in a thread (ffmpeg is CPU-bound — never block the event
loop), mirrors the MP4 to MinIO, and flips the row to ready/failed.

Concurrency is 1 (CPU libx264, no GPU on Coolify). Registered in main.py under
RUN_WORKERS=1.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import tempfile
import zlib
from typing import Any, cast

import structlog
from sqlalchemy import text

from app import metrics
from app.agents.messaging import emit_message
from app.integrations import telegram
from app.integrations.llm.gemini_client import analyze_video_file
from app.memory.db import get_sessionmaker
from app.montage import higgsfield_assemble, higgsfield_gen, runway_restyle
from app.montage.broll import select_reject_shots
from app.montage.compiler import (
    compile_and_render,
    quality_verdict,
    render_from_edl,
    validate_inbound_edl,
)
from app.montage.edl import EDL, EffectIntent
from app.montage.gate import ENCODE_GATE
from app.montage.higgsfield_client import higgsfield_enabled
from app.montage.probe import input_reject_reason, probe_clip, run_ff
from app.montage.runway_client import runway_enabled
from app.montage.storage import download_object, media_url, upload_object

log = structlog.get_logger(__name__)

POLL_INTERVAL = float(os.getenv("MONTAGE_POLL_SECONDS") or "15")
# Input guard — reject oversized clips before any encode (unbounded resolution/
# duration is the real OOM lever). Generous defaults; phone reels are far under.
MAX_INPUT_PIXELS = int(os.getenv("MONTAGE_MAX_INPUT_PIXELS") or str(3840 * 2160))
MAX_INPUT_SECONDS = float(os.getenv("MONTAGE_MAX_INPUT_SECONDS") or "1200")
# Visibility-timeout lease. A claimed render must finish within this window or it
# is considered abandoned (worker crash / Coolify redeploy mid-render) and becomes
# reclaimable. Comfortably exceeds a normal "minutes" render; the single-worker
# loop never reaps a render it is actively running (it's blocked in _process).
LEASE_SECONDS = int(float(os.getenv("MONTAGE_LEASE_SECONDS") or "1200"))
# Total claim attempts before a stranded row is failed for good.
MAX_ATTEMPTS = int(os.getenv("MONTAGE_MAX_ATTEMPTS") or "3")
# A 'processing' row with NO lease is a legacy orphan (pre-leasing, before the row
# ever carried a lease) — neither the lease-based reclaim nor reap touches it, so
# fail it once it's clearly dead (well beyond any real render). Mirrors agent_runs.
LEGACY_STALE_SECONDS = int(float(os.getenv("MONTAGE_LEGACY_STALE_SECONDS") or "3600"))
# Concurrent claim→process loops. Safe because the claim is FOR UPDATE SKIP LOCKED
# (no double-claim) and ENCODE_GATE serializes the actual ffmpeg (no core thrash);
# K just overlaps the I/O-bound parts (download, the Whisper network wait, upload)
# of one job with another's encode, so user 2 doesn't wait the full render of
# user 1. Raise it (e.g. 2) only on the dedicated media plane (W2/T2.4).
MONTAGE_CONCURRENCY = max(1, int(os.getenv("MONTAGE_CONCURRENCY") or "1"))


async def loop_forever() -> None:
    log.info(
        "montage.worker.start",
        interval=POLL_INTERVAL, lease=LEASE_SECONDS,
        max_attempts=MAX_ATTEMPTS, concurrency=MONTAGE_CONCURRENCY,
    )
    if MONTAGE_CONCURRENCY == 1:
        await _run_one()
    else:
        await asyncio.gather(*[_run_one() for _ in range(MONTAGE_CONCURRENCY)])


async def _run_one() -> None:
    """One claim→process loop. K of these run concurrently (see MONTAGE_CONCURRENCY)."""
    sm = get_sessionmaker()
    while True:
        try:
            async with sm() as session:
                await _reap_abandoned(session)
                claimed = await _claim_one(session)
            if claimed:
                await _process(claimed)
                continue  # drain the queue without sleeping while work remains
        except Exception:  # noqa: BLE001
            log.exception("montage.worker.iteration_failed")
        await asyncio.sleep(POLL_INTERVAL)


async def _reap_abandoned(session: Any) -> None:
    """Fail renders whose worker died mid-flight (lease expired) and that have
    exhausted their retry budget. Without this, a crash/redeploy strands the row
    in 'processing' forever and the web dedup guard (render route 409
    'already_rendering') permanently blocks re-rendering that task."""
    rows = (
        await session.execute(
            text(
                """
                UPDATE task_media
                SET status='failed',
                    "errorMessage"='Render bekor qilindi — qayta urinishlar tugadi.',
                    "updatedAt"=NOW()
                WHERE kind='final_render' AND status='processing'
                  AND (
                    ("leaseExpiresAt" IS NOT NULL AND "leaseExpiresAt" < NOW()
                     AND attempts >= :max_attempts)
                    OR ("leaseExpiresAt" IS NULL
                        AND "updatedAt" < NOW() - make_interval(secs => :legacy_stale))
                  )
                RETURNING id
                """
            ),
            {"max_attempts": MAX_ATTEMPTS, "legacy_stale": LEGACY_STALE_SECONDS},
        )
    ).mappings().all()
    await session.commit()
    if rows:
        log.warning("montage.worker.reaped", count=len(rows), ids=[r["id"] for r in rows])
        metrics.RENDER_FAILURES.inc(len(rows))


async def _claim_one(session: Any) -> dict[str, Any] | None:
    """Atomically claim the oldest renderable row — a pending one OR one whose
    lease expired (its worker died) and that is still under the attempt cap — so
    two pollers never collide and a crashed render is retried, not stranded."""
    row = (
        await session.execute(
            text(
                """
                UPDATE task_media
                SET status='processing', attempts=attempts+1,
                    "leaseExpiresAt"=NOW() + make_interval(secs => :lease_seconds),
                    "updatedAt"=NOW()
                WHERE id = (
                    SELECT id FROM task_media
                    WHERE kind='final_render'
                      AND (
                        status='pending'
                        OR (status='processing'
                            AND "leaseExpiresAt" IS NOT NULL
                            AND "leaseExpiresAt" < NOW()
                            AND attempts < :max_attempts)
                      )
                    ORDER BY "createdAt" ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, "taskId", "tenantId", meta
                """
            ),
            {"lease_seconds": LEASE_SECONDS, "max_attempts": MAX_ATTEMPTS},
        )
    ).mappings().first()
    await session.commit()
    if not row:
        return None
    return {
        "media_id": row["id"],
        "task_id": row["taskId"],
        "tenant_id": row["tenantId"],
        "meta": row["meta"],
    }


def _parse_meta(meta: Any) -> dict[str, Any]:
    if isinstance(meta, str):
        try:
            parsed = json.loads(meta)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return meta if isinstance(meta, dict) else {}


async def _process(claimed: dict[str, Any]) -> None:
    media_id, task_id, tenant_id = claimed["media_id"], claimed["task_id"], claimed["tenant_id"]
    meta = _parse_meta(claimed.get("meta"))

    # Higgsfield cinematic branch — generates its OWN per-shot footage from the scenario, so it needs
    # NO user upload. Handled before the upload requirement below.
    if meta.get("renderSource") == "higgsfield":
        await _process_higgsfield(media_id, task_id, tenant_id, meta)
        return

    # Runway Aleph branch — RESTYLE the user's uploaded clip (requires an upload).
    if meta.get("renderSource") == "runway_restyle":
        await _process_runway(media_id, task_id, tenant_id, meta)
        return

    sm = get_sessionmaker()
    async with sm() as session:
        upload_key = await _latest_upload_key(session, task_id)
    if not upload_key:
        await _fail(media_id, "Yuklangan klip topilmadi.")
        return

    # MANUAL refine: a hand-edited EDL came from the Studio — render it directly,
    # NO planning agents, NO LLM, NO caption_stylist (must not clobber edits).
    if meta.get("editSource") == "manual" and isinstance(meta.get("edl"), dict):
        log.info("montage.worker.manual_start", media_id=media_id, task_id=task_id)
        telegram.send("✂️ Studiya montaji render qilinmoqda (qo'lda tahrir)")
        # The web zod EdlSchema doesn't carry face_zone yet, so the round-tripped meta.edl has it
        # stripped. Re-read the vision fact from the durable director notes so the refine-render
        # keeps captions off the speaker's face (same source as the AUTO path below).
        async with sm() as session:
            _notes = await _upload_director_notes(session, task_id)
        _face_zone = _notes.get("face_zone") if _notes.get("face_zone") in ("top", "center", "bottom") else None
        try:
            result = await asyncio.to_thread(
                _manual_render_upload, upload_key, meta["edl"], task_id, tenant_id, media_id, _face_zone
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("montage.worker.manual_crashed", media_id=media_id)
            await _fail(media_id, f"Render xatosi: {str(exc)[:300]}")
            return
        if not result["ok"]:
            await _fail(media_id, str(result["error"]))
            return
        await _complete(media_id, result, meta)
        log.info("montage.worker.manual_done", media_id=media_id, degrade=result["degradeLevel"])
        return

    # AUTO first-cut: the AI plans + renders the EDL from the script.
    style = _caption_style_from_meta(meta)
    inpaint_remove = _inpaint_remove_from_meta(meta)
    decor_prompt = _decor_prompt_from_meta(meta)
    translate_langs = _translate_langs_from_meta(meta)
    async with sm() as session:
        script_timeline = await _script_timeline(session, task_id)
        shot_list = await _shot_list(session, task_id)
        broll_plan = await _broll_plan(session, task_id)
        effect_intents = await _effect_intents(session, task_id)
        shot_src_times = await _footage_shot_times(session, task_id)
        footage_map = await _footage_map(session, task_id)
        hook = _hook_from_meta(meta) or await _task_hook(session, task_id)
        notes = await _upload_director_notes(session, task_id)
        # F6 priority: what the director HEARD/SAW in the footage beats the script's guess.
        music_hint = notes.get("music_hint") or await _task_audio_suggestion(session, task_id)
        face_zone = notes.get("face_zone") if notes.get("face_zone") in ("top", "center", "bottom") else None
        if not inpaint_remove and os.getenv("ENABLE_AUTO_INPAINT", "").strip().lower() in ("1", "true", "yes"):
            unwanted = [x for x in (notes.get("unwanted") or []) if isinstance(x, str) and x.strip()]
            if unwanted:
                inpaint_remove = unwanted[0]
                log.info("montage.worker.auto_inpaint", target=inpaint_remove[:60])
    if not script_timeline:
        await _fail(media_id, "Senariy hali tayyor emas — avval senariyni yozdiring.")
        return

    # Stage 9b Faza 3: footage shots that match no storyboard shot (off-script outtakes) → drop spans
    # fed into the SAME subtract_spans path as the semantic stumble-cut. Conservative + degrade-safe.
    drop_src_ranges = select_reject_shots(footage_map, shot_list) if footage_map else []

    log.info("montage.worker.render_start", media_id=media_id, task_id=task_id)
    telegram.send("🎬 Video AI montaji render qilinmoqda")
    try:
        result = await asyncio.to_thread(
            _download_render_upload,
            upload_key, script_timeline, task_id, tenant_id, media_id, style, hook, shot_list,
            broll_plan, shot_src_times, effect_intents, inpaint_remove, decor_prompt, translate_langs,
            drop_src_ranges, music_hint, face_zone,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("montage.worker.render_crashed", media_id=media_id)
        await _fail(media_id, f"Render xatosi: {str(exc)[:300]}")
        return

    if not result["ok"]:
        await _fail(media_id, str(result["error"]))
        return
    await _complete(media_id, result, meta)
    log.info("montage.worker.render_done", media_id=media_id, degrade=result["degradeLevel"])
    # Stage 14 — async result confirmation: ping the user's feed (DB + SSE) that
    # the autonomous montage finished, so they don't have to sit on the polling UI.
    await _notify_render_done(tenant_id, task_id)
    # Stage 9b/Faza-4 (critique-only): score the FINISHED montage so the studio
    # shows the user a quality read on the autonomous edit. Advisory — never
    # auto-re-renders, never blocks. Fire-and-forget so the next poll isn't held.
    asyncio.create_task(_critique_render(media_id, result["objectKey"]))


async def _process_higgsfield(media_id: str, task_id: str, tenant_id: str, meta: dict[str, Any]) -> None:
    """Render the cinematic path: generate a clip per planned shot via Higgsfield, then assemble them
    (concat + captions + music). No user upload required — the shots ARE the footage."""
    plan = meta.get("higgsfieldPlan")
    if not isinstance(plan, list) or not plan:
        await _fail(media_id, "Higgsfield reja topilmadi.")
        return
    if not higgsfield_enabled():
        await _fail(media_id, "Higgsfield yoqilmagan — ENABLE_HIGGSFIELD + HIGGSFIELD_API_KEY kerak.")
        return

    sm = get_sessionmaker()
    async with sm() as session:
        script_timeline = await _script_timeline(session, task_id)
        shot_list = await _shot_list(session, task_id)
        upload_key = await _latest_upload_key(session, task_id)  # optional — footage keyframes only
    caption_style = meta.get("captionStyle") if isinstance(meta.get("captionStyle"), dict) else None
    hook = _hook_from_meta(meta)
    seed = zlib.crc32(task_id.encode()) & 0x7FFFFFFF

    log.info("montage.worker.higgsfield_start", media_id=media_id, task_id=task_id, shots=len(plan))
    telegram.send(f"🎨 AI kinematik kadrlar generatsiya qilinmoqda (Higgsfield) · {len(plan)} kadr")
    # Higgsfield generation is minutes/shot and can exceed LEASE_SECONDS. Unlike the run_worker, the
    # montage worker has no per-node heartbeat, so on the media plane (MONTAGE_CONCURRENCY>=2) a peer
    # loop could reclaim + double-render this row. A background heartbeat keeps the lease fresh.
    hb = asyncio.create_task(_lease_heartbeat(media_id))
    try:
        try:
            result = await asyncio.to_thread(
                _higgsfield_render_upload,
                plan, script_timeline, shot_list, caption_style, hook,
                task_id, tenant_id, media_id, upload_key, seed,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("montage.worker.higgsfield_crashed", media_id=media_id)
            await _fail(media_id, f"Higgsfield xatosi: {str(exc)[:300]}")
            return
        if not result["ok"]:
            await _fail(media_id, str(result["error"]))
            return
        await _complete(media_id, result, meta)
        log.info("montage.worker.higgsfield_done", media_id=media_id, degrade=result["degradeLevel"], shots=result["cuts"])
        await _notify_render_done(tenant_id, task_id)
        asyncio.create_task(_critique_render(media_id, result["objectKey"]))
    finally:
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb


async def _lease_heartbeat(media_id: str) -> None:
    """Periodically extend a processing render's lease so a long Higgsfield generation isn't reclaimed
    (and double-rendered) by a peer loop on the media plane. Cancelled when the render finishes.
    Best-effort — a failed heartbeat just risks reclaim, never breaks the render."""
    interval = max(30.0, LEASE_SECONDS / 3.0)
    sm = get_sessionmaker()
    while True:
        await asyncio.sleep(interval)
        try:
            async with sm() as session:
                await session.execute(
                    text(
                        'UPDATE task_media SET "leaseExpiresAt"=NOW() + make_interval(secs => :s), '
                        "\"updatedAt\"=NOW() WHERE id=:id AND status='processing'"
                    ),
                    {"s": LEASE_SECONDS, "id": media_id},
                )
                await session.commit()
        except Exception:  # noqa: BLE001 — heartbeat is best-effort
            log.warning("montage.worker.hf_heartbeat_failed", media_id=media_id)


async def _process_runway(media_id: str, task_id: str, tenant_id: str, meta: dict[str, Any]) -> None:
    """Restyle the user's UPLOADED clip via Runway Aleph. Requires an upload (that's the whole point)."""
    if not runway_enabled():
        await _fail(media_id, "Runway yoqilmagan — ENABLE_RUNWAY_RESTYLE + RUNWAY_API_KEY kerak.")
        return
    prompt = meta.get("runwayPrompt")
    if not isinstance(prompt, str) or not prompt.strip():
        await _fail(media_id, "Runway prompt topilmadi.")
        return
    sm = get_sessionmaker()
    async with sm() as session:
        upload_key = await _latest_upload_key(session, task_id)
        script_timeline = await _script_timeline(session, task_id)
    if not upload_key:
        await _fail(media_id, "Video yuklanmagan — Runway restyle uchun avval video yuklang.")
        return
    caption_style = meta.get("captionStyle") if isinstance(meta.get("captionStyle"), dict) else None
    seed = zlib.crc32(task_id.encode()) & 0x7FFFFFFF

    log.info("montage.worker.runway_start", media_id=media_id, task_id=task_id)
    telegram.send("🎨 Video AI uslubga o'girilmoqda (Runway restyle)")
    hb = asyncio.create_task(_lease_heartbeat(media_id))
    try:
        try:
            result = await asyncio.to_thread(
                _runway_render_upload, upload_key, prompt, script_timeline, caption_style,
                task_id, tenant_id, media_id, seed,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("montage.worker.runway_crashed", media_id=media_id)
            await _fail(media_id, f"Runway xatosi: {str(exc)[:300]}")
            return
        if not result["ok"]:
            await _fail(media_id, str(result["error"]))
            return
        await _complete(media_id, result, meta)
        log.info("montage.worker.runway_done", media_id=media_id)
        await _notify_render_done(tenant_id, task_id)
        asyncio.create_task(_critique_render(media_id, result["objectKey"]))
    finally:
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb


def _runway_render_upload(
    upload_key: str,
    prompt: str,
    script_timeline: list[object],
    caption_style: dict[str, Any] | None,
    task_id: str,
    tenant_id: str,
    media_id: str,
    seed: int,
) -> dict[str, Any]:
    """Sync, thread-offloaded: pull the upload → Runway restyle → assemble → push. Network-bound
    (fal upload + Runway poll), so it runs UNGATED; the heartbeat keeps the lease alive."""
    with tempfile.TemporaryDirectory(prefix="runway-") as wd:
        upload_path = os.path.join(wd, "upload.mp4")
        download_object(upload_key, upload_path)
        work = os.path.join(wd, "work")
        os.makedirs(work, exist_ok=True)
        asm = runway_restyle.restyle_upload(
            upload_path, work_dir=work, prompt=prompt,
            script_timeline=script_timeline, caption_style=caption_style, seed=seed,
        )
        if not asm["ok"] or not asm.get("out_path"):
            return {"ok": False, "error": f"Runway restyle muvaffaqiyatsiz ({asm.get('error') or 'unknown'})."}
        out_key = f"{tenant_id}/{task_id}/runway-{media_id}.mp4"
        upload_object(out_key, asm["out_path"], content_type="video/mp4")
        return {
            "ok": True,
            "objectKey": out_key,
            "url": media_url(out_key),
            "durationSec": round(float(asm["duration"]), 2),
            "sizeBytes": os.path.getsize(asm["out_path"]),
            "degradeLevel": 0,
            "cuts": 1,
            "edl": None,
        }


# Higgsfield's own degrade ladder (0=captions ok, 1=no captions, 3=raw concat) → the montage
# compiler's scale that quality_verdict reads (0=full, 2=no captions, 3=raw) so the studio's
# structural verdict text is truthful for cinematic renders.
_HF_DEGRADE_MAP = {0: 0, 1: 2, 3: 3}


def _higgsfield_render_upload(
    plan: list[dict[str, Any]],
    script_timeline: list[object],
    shot_list: list[object],
    caption_style: dict[str, Any] | None,
    hook_text: str | None,
    task_id: str,
    tenant_id: str,
    media_id: str,
    upload_key: str | None,
    seed: int,
) -> dict[str, Any]:
    """Sync, thread-offloaded: generate each shot's clip → assemble → push the result. Generation
    (network-bound, minutes) runs UNGATED; only the ffmpeg assembly is serialized by ENCODE_GATE so a
    long generation doesn't block other renders' encodes."""
    with tempfile.TemporaryDirectory(prefix="higgsfield-") as wd:
        upload_path: str | None = None
        if upload_key:
            candidate = os.path.join(wd, "upload.mp4")
            try:
                download_object(upload_key, candidate)
                upload_path = candidate
            except Exception as exc:  # noqa: BLE001 — footage is optional; fall back to generated keyframes
                log.warning("montage.worker.hf_upload_dl_failed", error=str(exc)[:160])
        gen_dir = os.path.join(wd, "gen")
        os.makedirs(gen_dir, exist_ok=True)
        shot_results = higgsfield_gen.generate_all(
            plan, work_dir=gen_dir, upload_path=upload_path, seed_base=seed
        )
        with ENCODE_GATE:  # serialize the heavy ffmpeg assembly with the other renders
            asm = higgsfield_assemble.assemble(
                shot_results, work_dir=gen_dir, script_timeline=script_timeline,
                shot_list=shot_list, caption_style=caption_style, hook_text=hook_text, seed=seed,
            )
        if not asm["ok"] or not asm.get("out_path"):
            n_ok = sum(1 for r in shot_results if r.get("ok"))
            reason = asm.get("error") or "assembly_failed"
            return {"ok": False, "error": f"Higgsfield yig'ish muvaffaqiyatsiz ({reason}); {n_ok}/{len(plan)} kadr tayyor bo'ldi."}
        out_key = f"{tenant_id}/{task_id}/higgsfield-{media_id}.mp4"
        upload_object(out_key, asm["out_path"], content_type="video/mp4")
        return {
            "ok": True,
            "objectKey": out_key,
            "url": media_url(out_key),
            "durationSec": round(float(asm["duration"]), 2),
            "sizeBytes": os.path.getsize(asm["out_path"]),
            "degradeLevel": _HF_DEGRADE_MAP.get(asm["degrade"], asm["degrade"]),
            "cuts": asm["shots_used"],
            "edl": None,
        }


def _caption_style_from_meta(meta: Any) -> dict[str, Any] | None:
    """Pull the caption_stylist agent's spec out of the render row meta."""
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return None
    if not isinstance(meta, dict):
        return None
    spec: dict[str, Any] = {}
    if isinstance(meta.get("captionStyle"), dict):
        spec["style"] = meta["captionStyle"]
    if meta.get("tier") in ("premium", "cheap"):
        spec["tier"] = meta["tier"]
    if isinstance(meta.get("emphasisWords"), list):
        spec["emphasis"] = [str(w) for w in meta["emphasisWords"]]
    return spec or None


def _hook_from_meta(meta: Any) -> str | None:
    """The caption_stylist agent's short on-screen hook, if it wrote one."""
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return None
    if isinstance(meta, dict):
        hook = meta.get("hookOverlay")
        if isinstance(hook, str) and hook.strip():
            return hook.strip()
    return None


def _inpaint_remove_from_meta(meta: Any) -> str | None:
    """The task's 'remove this element' instruction (meta.inpaintRemove) — drives Faza D inpaint.
    Absent/blank → no inpaint."""
    m: Any = meta
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except json.JSONDecodeError:
            return None
    v = m.get("inpaintRemove") if isinstance(m, dict) else None
    return v.strip() if isinstance(v, str) and v.strip() else None


def _decor_prompt_from_meta(meta: Any) -> str | None:
    """The task's scenario-matched background instruction (meta.decorBackground) — drives Faza C decor.
    Absent/blank → no decor."""
    m: Any = meta
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except json.JSONDecodeError:
            return None
    v = m.get("decorBackground") if isinstance(m, dict) else None
    return v.strip() if isinstance(v, str) and v.strip() else None


def _translate_langs_from_meta(meta: Any) -> list[str]:
    """The task's localization targets (meta.translateLangs: list[str] or comma-string) — drives Video
    Translation. Empty → none here; the compiler falls back to the VIDEO_TRANSLATE_LANGS config default."""
    m: Any = meta
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except json.JSONDecodeError:
            return []
    raw = m.get("translateLangs") if isinstance(m, dict) else None
    if isinstance(raw, list):
        return [str(c).strip().lower() for c in raw if str(c).strip()]
    if isinstance(raw, str):
        return [c.strip().lower() for c in raw.split(",") if c.strip()]
    return []


def _extract_cover(
    video_path: str, tenant_id: str, task_id: str, media_id: str, duration: float
) -> tuple[str | None, str | None]:
    """Grab a profile-grid COVER frame from the finished reel and upload it — without one the
    reel shows a random auto-frame in the grid + search (playbook: a 'random cover' loses reach).
    Picks an early settled frame (~1.2s, past the raw first-frame), where the speaker is on-camera
    and the hook text is up. FAIL-SOFT → (None, None). JPEG, high quality."""
    try:
        at = min(1.2, max(0.3, duration * 0.1))
        cover_path = os.path.join(os.path.dirname(video_path), f"cover-{media_id}.jpg")
        run_ff(
            ["ffmpeg", "-y", "-ss", f"{at:.2f}", "-i", video_path,
             "-frames:v", "1", "-q:v", "3", cover_path],
            timeout=30,
        )
        if not (os.path.exists(cover_path) and os.path.getsize(cover_path) > 0):
            return None, None
        cover_key = f"{tenant_id}/{task_id}/cover-{media_id}.jpg"
        upload_object(cover_key, cover_path, content_type="image/jpeg")
        return cover_key, media_url(cover_key)
    except Exception as exc:  # noqa: BLE001 — the cover is a nice-to-have, never fail the render
        log.warning("montage.cover_failed", media_id=media_id, error=str(exc)[:120])
        return None, None


def _download_render_upload(
    upload_key: str,
    script_timeline: list[object],
    task_id: str,
    tenant_id: str,
    media_id: str,
    caption_spec: dict[str, Any] | None,
    hook_text: str | None,
    shot_list: list[object] | None = None,
    broll_plan: list[object] | None = None,
    shot_src_times: list[float] | None = None,
    effect_intents: list[EffectIntent] | None = None,
    inpaint_remove: str | None = None,
    decor_prompt: str | None = None,
    translate_langs: list[str] | None = None,
    drop_src_ranges: list[tuple[float, float]] | None = None,
    music_hint: str | None = None,
    face_zone: str | None = None,
) -> dict[str, Any]:
    """Sync, thread-offloaded: pull the upload, render, push the result."""
    with tempfile.TemporaryDirectory(prefix="montage-") as wd:
        upload_path = os.path.join(wd, "upload.mp4")
        download_object(upload_key, upload_path)
        reason = input_reject_reason(
            probe_clip(upload_path), max_pixels=MAX_INPUT_PIXELS, max_seconds=MAX_INPUT_SECONDS
        )
        if reason:
            return {"ok": False, "error": reason}
        # F4b: the encode gate moved INSIDE the compiler (normalize + local ladder only), so the
        # Shotstack submit/poll and the Whisper network wait no longer serialize other renders.
        edl, result = compile_and_render(
            upload_path, script_timeline,
            task_id=task_id, tenant_id=tenant_id, upload_key=upload_key,
            work_dir=os.path.join(wd, "work"), caption_spec=caption_spec,
            hook_text=hook_text, shot_list=shot_list, broll_plan=broll_plan,
            shot_src_times=shot_src_times, drop_src_ranges=drop_src_ranges,
            effect_intents=effect_intents,
            inpaint_remove=inpaint_remove, decor_prompt=decor_prompt,
            translate_langs=translate_langs, music_hint=music_hint, face_zone=face_zone,
        )
        if not result.ok or not result.out_path:
            return {"ok": False, "error": result.error or "render failed"}
        out_key = f"{tenant_id}/{task_id}/montage-{media_id}.mp4"
        upload_object(out_key, result.out_path, content_type="video/mp4")
        cover_key, cover_url = _extract_cover(
            result.out_path, tenant_id, task_id, media_id, result.duration
        )
        # Persist the normalized+GRADED base clip so "open in STUDIO" edits a source that MATCHES
        # the render (same grade, same 9:16, browser-decodable mp4) — otherwise STUDIO loads the raw
        # upload and looks flat/different next to the polished reel. Duration-preserving, so the
        # EDL's SOURCE times still line up 1:1. Fail-soft.
        normalized_key: str | None = None
        norm_path = os.path.join(wd, "work", "normalized.mp4")
        if os.path.exists(norm_path):
            try:
                normalized_key = f"{tenant_id}/{task_id}/normalized-{media_id}.mp4"
                upload_object(normalized_key, norm_path, content_type="video/mp4")
            except Exception as exc:  # noqa: BLE001 — nice-to-have, never fail the render
                log.warning("montage.normalized_upload_failed", error=str(exc)[:120])
                normalized_key = None
        return {
            "ok": True,
            "objectKey": out_key,
            "url": media_url(out_key),
            "coverKey": cover_key,
            "coverUrl": cover_url,
            "normalizedKey": normalized_key,
            "durationSec": round(result.duration, 2),
            "sizeBytes": result.size_bytes,
            "degradeLevel": result.degrade_level,
            "engine": result.engine,
            "cuts": len(edl.cuts) if edl else 0,
            # Persist the EDL so it becomes the editor's starting document — the
            # AI auto-montage is "EDL v1", the user's first cut to refine.
            "edl": edl.model_dump() if edl else None,
        }


def _reattach_face_zone(edl: EDL, face_zone: str | None) -> None:
    """Re-attach the VISION face_zone onto a round-tripped EDL that lost it.

    face_zone (where the speaker's face sits) is a fact about the SOURCE clip, not a user edit.
    The web EDL wire-contract (zod EdlSchema) doesn't carry it yet, so a STUDIO/manual round-trip
    strips it from meta.edl — and render_from_edl would then place captions back OVER the face (the
    exact regression a bad reel was deleted over). We fill a MISSING face_zone from the durable
    director notes; a face_zone already on the EDL (fresh AUTO cut, or a future contract that carries
    it) wins and is never overwritten. Mirrors the AUTO path (_process) + compile_and_render."""
    if not edl.face_zone and face_zone in ("top", "center", "bottom"):
        edl.face_zone = face_zone


def _manual_render_upload(
    upload_key: str,
    edl_dict: dict[str, Any],
    task_id: str,
    tenant_id: str,
    media_id: str,
    face_zone: str | None = None,
) -> dict[str, Any]:
    """Sync, thread-offloaded: render a hand-edited EDL (no agents/LLM)."""
    with tempfile.TemporaryDirectory(prefix="montage-m-") as wd:
        upload_path = os.path.join(wd, "upload.mp4")
        download_object(upload_key, upload_path)
        reason = input_reject_reason(
            probe_clip(upload_path), max_pixels=MAX_INPUT_PIXELS, max_seconds=MAX_INPUT_SECONDS
        )
        if reason:
            return {"ok": False, "error": reason}
        try:
            edl = EDL.model_validate(edl_dict)
        except Exception as exc:  # noqa: BLE001 — untrusted client input
            return {"ok": False, "error": f"Tahrirlangan EDL yaroqsiz: {str(exc)[:160]}"}
        _reattach_face_zone(edl, face_zone)
        ok, reason = validate_inbound_edl(edl)
        if not ok:
            return {"ok": False, "error": reason}
        # F4b: gate lives inside the compiler now (normalize + local ladder only).
        result = render_from_edl(upload_path, edl, os.path.join(wd, "work"))
        if not result.ok or not result.out_path:
            return {"ok": False, "error": result.error or "render failed"}
        out_key = f"{tenant_id}/{task_id}/montage-{media_id}.mp4"
        upload_object(out_key, result.out_path, content_type="video/mp4")
        return {
            "ok": True,
            "objectKey": out_key,
            "url": media_url(out_key),
            "durationSec": round(result.duration, 2),
            "sizeBytes": result.size_bytes,
            "degradeLevel": result.degrade_level,
            "engine": result.engine,
            "cuts": len(edl.cuts),
            "edl": edl.model_dump(),
        }


async def _latest_upload_key(session: Any, task_id: str) -> str | None:
    result = await session.execute(
        text(
            """
            SELECT "objectKey" FROM task_media
            WHERE "taskId"=:tid AND kind='user_upload' AND "objectKey" IS NOT NULL
            ORDER BY "createdAt" DESC LIMIT 1
            """
        ),
        {"tid": task_id},
    )
    return cast("str | None", result.scalar_one_or_none())


async def _script_timeline(session: Any, task_id: str) -> list[object]:
    raw = (
        await session.execute(
            text('SELECT "scriptTimeline" FROM content_tasks WHERE id=:tid'),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw if isinstance(raw, list) else []


async def _shot_list(session: Any, task_id: str) -> list[object]:
    """The scriptwriter storyboard (shotList) — feeds the planned text overlays (Faza 2)."""
    raw = (
        await session.execute(
            text('SELECT "shotList" FROM content_tasks WHERE id=:tid'),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw if isinstance(raw, list) else []


async def _footage_shot_times(session: Any, task_id: str) -> list[float]:
    """AG-2: the footage_analyzer's vision-detected scene boundaries (meta.footageMap.shots[].src_start
    on the latest user_upload, SOURCE seconds). Threaded into build_edl so the montage cuts land on
    the SAME shots the Gemini vision pass saw — not a redundant second scene-detect on the normalized
    clip. Empty when footage_analyzer didn't run; build_edl then falls back to detect_shots."""
    raw = (
        await session.execute(
            text(
                """
                SELECT meta->'footageMap'->'shots' FROM task_media
                WHERE "taskId"=:tid AND kind='user_upload' AND "objectKey" IS NOT NULL
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    times: list[float] = []
    for s in raw:
        v = s.get("src_start") if isinstance(s, dict) else None
        if isinstance(v, (int, float)) and v > 0:  # the first shot starts at 0 — not a boundary
            times.append(float(v))
    return sorted(set(times))


async def _footage_map(session: Any, task_id: str) -> dict[str, Any] | None:
    """The full FootageMap (meta.footageMap on the latest user_upload) — vision_ok + per-shot
    matched_shot_index/motion_score/src bounds. Feeds the Stage-9b footage bad-take reject
    (select_reject_shots). None when footage_analyzer didn't run."""
    raw = (
        await session.execute(
            text(
                """
                SELECT meta->'footageMap' FROM task_media
                WHERE "taskId"=:tid AND kind='user_upload' AND "objectKey" IS NOT NULL
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw if isinstance(raw, dict) else None


async def _broll_plan(session: Any, task_id: str) -> list[object]:
    """The broll_curator's plan (meta.brollPlan on the latest user_upload) — which storyboard
    shots get stock B-roll (Faza 3). Empty when coverage was full or the curator didn't run."""
    raw = (
        await session.execute(
            text(
                """
                SELECT meta->'brollPlan' FROM task_media
                WHERE "taskId"=:tid AND kind='user_upload' AND "objectKey" IS NOT NULL
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw if isinstance(raw, list) else []


async def _effect_intents(session: Any, task_id: str) -> list[EffectIntent]:
    """The montage_director's planned EffectIntents (meta.effectIntents on the latest user_upload).
    Empty when the director didn't run or found nothing; each dict validated → EffectIntent."""
    raw = (
        await session.execute(
            text(
                """
                SELECT meta->'effectIntents' FROM task_media
                WHERE "taskId"=:tid AND kind='user_upload' AND "objectKey" IS NOT NULL
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    out: list[EffectIntent] = []
    for d in raw:
        try:
            out.append(EffectIntent.model_validate(d))
        except Exception:  # noqa: BLE001, S112 — drop a bad intent, keep the rest
            continue
    return out


async def _upload_director_notes(session: Any, task_id: str) -> dict[str, Any]:
    """F6 director notes (meta.directorNotes on the latest user_upload) — {} when absent."""
    raw = (
        await session.execute(
            text(
                """
                SELECT meta->'directorNotes' FROM task_media
                WHERE "taskId"=:tid AND kind='user_upload' AND "objectKey" IS NOT NULL
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


async def _task_audio_suggestion(session: Any, task_id: str) -> str | None:
    """The scriptwriter's music brief (genre/tempo/reference) — makes the generated bed
    CONTENT-matched instead of energy-only."""
    raw = (
        await session.execute(
            text('SELECT "audioSuggestion" FROM content_tasks WHERE id=:tid'),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    return cast("str | None", raw)


async def _task_hook(session: Any, task_id: str) -> str | None:
    """The task's hook line — burned big over the opening seconds."""
    raw = (
        await session.execute(
            text("SELECT hook FROM content_tasks WHERE id=:tid"),
            {"tid": task_id},
        )
    ).scalar_one_or_none()
    return cast("str | None", raw)


async def _notify_render_done(tenant_id: str, task_id: str) -> None:
    """Stage 14 async confirmation: surface a 'montage ready' message in the
    user's agent feed (+ SSE) so a finished autonomous render is noticed even if
    they navigated away. Best-effort; emit_message dedupes identical content."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            uid = (
                await session.execute(
                    text('SELECT id FROM users WHERE "tenantId" = :t LIMIT 1'),
                    {"t": tenant_id},
                )
            ).scalar()
        await emit_message(
            tenant_id=tenant_id,
            user_id=uid,
            agent="writer",
            content="🎬 Montajingiz tayyor — ko'rib chiqing va kerak bo'lsa STUDIO'da tahrirlang.",
            important=True,
        )
    except Exception:  # noqa: BLE001 — notification must never affect the render
        log.warning("montage.worker.notify_failed", task_id=task_id)


# F4 telemetry: rough per-render cost so the AI-spend panel sees the media plane too.
# Cloud engines bill per output minute (env-tunable); the local ladder is "free" (own CPU).
_ENGINE_COST_PER_MIN = {
    "shotstack": float(os.getenv("SHOTSTACK_COST_PER_MIN") or "0.30"),
    "higgsfield": float(os.getenv("HIGGSFIELD_COST_PER_RENDER") or "1.50"),
    "runway": float(os.getenv("RUNWAY_COST_PER_MIN") or "1.00"),
    "ffmpeg": 0.0,
}


def _estimate_render_cost(engine: str, duration_sec: float) -> float:
    rate = _ENGINE_COST_PER_MIN.get(engine, 0.0)
    if engine == "higgsfield":  # per-render flat-ish (per-clip credits), not per-minute
        return round(rate, 4)
    return round(rate * max(0.0, duration_sec) / 60.0, 4)


async def _complete(media_id: str, result: dict[str, Any], original_meta: Any) -> None:
    sm = get_sessionmaker()
    # Preserve the caption_stylist spec (tier/accent/emphasisWords) the agent
    # wrote, so the studio can show what the AI chose; add the render stats.
    base: dict[str, Any] = {}
    if isinstance(original_meta, str):
        try:
            base = json.loads(original_meta)
        except json.JSONDecodeError:
            base = {}
    elif isinstance(original_meta, dict):
        base = dict(original_meta)
    base["degradeLevel"] = result["degradeLevel"]
    base["cuts"] = result["cuts"]
    engine = str(result.get("engine") or ("higgsfield" if base.get("renderSource") == "higgsfield"
                 else "runway" if base.get("renderSource") == "runway_restyle" else "ffmpeg"))
    base["renderEngine"] = engine
    # Faza-4: instant deterministic quality verdict (structural) — the studio shows it
    # right away; the async Gemini critique later layers a subjective visual score on top.
    base["renderVerdict"] = quality_verdict(
        result["degradeLevel"], result["cuts"], float(result.get("durationSec") or 0.0)
    )
    if result.get("edl") is not None:
        base["edl"] = result["edl"]
    if result.get("coverKey"):
        base["coverKey"] = result["coverKey"]
        base["coverUrl"] = result.get("coverUrl")
    if result.get("normalizedKey"):
        base["normalizedKey"] = result["normalizedKey"]
    meta = json.dumps(base)
    async with sm() as session:
        await session.execute(
            text(
                """
                UPDATE task_media SET
                    status='ready', url=:url, "objectKey"=:key,
                    "contentType"='video/mp4', "durationSec"=:dur,
                    "sizeBytes"=:size, "costUsd"=:cost, "provider"=:prov,
                    meta=CAST(:meta AS jsonb), "completedAt"=NOW(), "updatedAt"=NOW()
                WHERE id=:id AND status='processing'
                """
            ),
            {
                "url": result["url"], "key": result["objectKey"],
                "dur": result["durationSec"], "size": result["sizeBytes"],
                "cost": _estimate_render_cost(engine, float(result.get("durationSec") or 0.0)),
                "prov": engine,
                "meta": meta, "id": media_id,
            },
        )
        await session.commit()
    dur = int(result.get("durationSec") or 0)
    telegram.send(f"✅ Video montaj tayyor · {result.get('cuts', 0)} kesim · {dur}s")


_RENDER_CRITIQUE_Q = (
    "Bu AVTOMATIK montaj qilingan Instagram reel (tayyor natija). Uni boshidan oxirigacha "
    "tomosha va tingla, montaj SIFATINI baholab FAQAT JSON qaytar: "
    '{"overallScore":<0-10>,"summary":"<1 jumla umumiy>",'
    '"issues":[{"type":"<pacing|caption|audio|cut|motion|hook>","detail":"<qisqa muammo>"}]}. '
    "Tekshir: kesimlar sur'ati (juda tez/sekin), subtitr o'qilishi + nutqqa sinxroni, audio "
    "balansi, qora/bo'sh kadrlar, hook birinchi 3 soniyada. O'zbekcha. Markdown yo'q."
)


async def _critique_render(media_id: str, object_key: str) -> None:
    """Best-effort post-render quality critique: Gemini watches the FINISHED
    montage and we persist {renderQualityScore, renderQualityIssues} into the
    final_render meta so the studio shows the user a quality read. Advisory only
    — NEVER auto-re-renders; a failure leaves the (already-ready) render intact."""
    if not object_key:
        return
    tmp: str | None = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        await asyncio.to_thread(download_object, object_key, tmp)
        raw = await analyze_video_file(
            path=tmp, question=_RENDER_CRITIQUE_Q, agent_name="montage_critique", json_mode=True
        )
        if not raw:
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        try:
            score = max(0, min(10, int(float(data.get("overallScore")))))
        except (TypeError, ValueError):
            return
        issues = [
            {"type": str(i.get("type") or "")[:20], "detail": str(i.get("detail") or "")[:160]}
            for i in (data.get("issues") or [])
            if isinstance(i, dict) and (i.get("detail") or i.get("type"))
        ][:5]
        q = json.dumps(
            {
                "renderQualityScore": score,
                "renderQualityIssues": issues,
                "renderQualitySummary": str(data.get("summary") or "").strip()[:200],
            },
            ensure_ascii=False,
        )
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text(
                    "UPDATE task_media SET meta = COALESCE(meta, '{}'::jsonb) || CAST(:q AS jsonb), "
                    '"updatedAt" = NOW() WHERE id = :id'
                ),
                {"q": q, "id": media_id},
            )
            await session.commit()
        log.info("montage.critique_done", media_id=media_id, score=score, issues=len(issues))
    except Exception:  # noqa: BLE001 — advisory critique is best-effort
        log.warning("montage.critique_failed", media_id=media_id, exc_info=True)
    finally:
        if tmp:
            with contextlib.suppress(OSError):
                os.unlink(tmp)


async def _fail(media_id: str, message: str) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text(
                """
                UPDATE task_media
                SET status='failed', "errorMessage"=:err, "updatedAt"=NOW()
                WHERE id=:id AND status='processing'
                """
            ),
            {"err": message[:500], "id": media_id},
        )
        await session.commit()
    log.info("montage.worker.failed", media_id=media_id, message=message[:120])
    telegram.send(f"❌ Video montaj xatosi · {message[:120]}")

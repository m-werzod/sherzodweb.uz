"""Per-shot cinematic clip generation for the Higgsfield pipeline.

For each storyboard shot: resolve a KEYFRAME image (a FLUX-generated still, or a frame grabbed from
the user's footage) → animate it into a ~5s clip via higgsfield_client → download the clip locally.
SYNC, worker-thread only, FAIL-SOFT: a shot with no keyframe / a failed generation is skipped (ok
=False) so the assembler builds from whatever succeeded — one bad shot never sinks the whole reel.

Keyframes need a PUBLIC url (the provider fetches it server-side): FLUX stills come back as a public
fal URL already; footage frames are uploaded to the fal CDN. Both therefore need FAL_KEY — without it
keyframe resolution returns None and that shot is skipped.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import structlog

from app.config import get_settings
from app.montage import higgsfield_client
from app.montage.fal_client import run_queue_image, upload_file
from app.montage.probe import FFmpegError, probe_clip, run_ff

log = structlog.get_logger(__name__)

# DoP generation can take several minutes/shot; give it room (live runs showed some shots > 5 min).
_MAX_CLIP_WAIT_S = float(os.getenv("HIGGSFIELD_CLIP_WAIT_S") or "600")
# Guard total wall-clock: generation is minutes/shot and the worker holds a lease. Cap the shots we
# actually generate so a long storyboard can't blow past the render lease.
MAX_SHOTS = int(os.getenv("HIGGSFIELD_MAX_SHOTS") or "10")
# Generate shots CONCURRENTLY (I/O-bound: each is network keyframe + DoP poll + download). Sequential
# 7×minutes would blow the lease; a bounded pool keeps total ≈ slowest shot. Env-tunable.
_GEN_CONCURRENCY = int(os.getenv("HIGGSFIELD_GEN_CONCURRENCY") or "4")


def generate_keyframe(prompt: str, *, seed: int = 0) -> str | None:
    """Generate a vertical keyframe still via fal FLUX; return its public URL or None. FAIL-SOFT."""
    p = (prompt or "").strip()
    if not p:
        return None
    body: dict[str, Any] = {"prompt": p[:500], "image_size": "portrait_16_9"}
    if seed:
        body["seed"] = int(seed)
    return run_queue_image(get_settings().higgsfield_image_model, body, label="hf_keyframe")


def frame_from_footage(upload_path: str, at_sec: float, work_dir: str, *, idx: int) -> str | None:
    """Grab one frame from the local footage at `at_sec` (clamped to the clip's real duration), upload
    to the fal CDN, return its public URL or None. FAIL-SOFT (ffmpeg error / missing file / no fal
    key → None)."""
    if not upload_path or not os.path.exists(upload_path):
        return None
    # The director's at_sec is derived from scenario timing, which may overrun the actual footage —
    # clamp so we always land on a real frame instead of past the end.
    grab = max(0.0, at_sec)
    try:
        dur = probe_clip(upload_path).duration
        if dur and dur > 0.2:
            grab = min(grab, dur - 0.1)
    except (FFmpegError, OSError):
        pass
    out = os.path.join(work_dir, f"keyframe_{idx}.jpg")
    try:
        run_ff(
            ["ffmpeg", "-y", "-ss", f"{grab:.2f}", "-i", upload_path,
             "-frames:v", "1", "-q:v", "3", out],
            timeout=60,
        )
    except (FFmpegError, OSError) as exc:
        log.warning("hf_gen.frame_grab_failed", idx=idx, error=str(exc)[:160])
        return None
    if not (os.path.exists(out) and os.path.getsize(out) > 0):
        return None
    return upload_file(out)


def _download(url: str, dest: str) -> bool:
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            r = client.get(url)
            if r.status_code >= 400:
                return False
            with open(dest, "wb") as f:
                f.write(r.content)
    except Exception as exc:  # noqa: BLE001 — optional GPU pass; never break the render
        log.warning("hf_gen.download_failed", error=str(exc)[:160])
        return False
    return os.path.exists(dest) and os.path.getsize(dest) > 0


def _resolve_keyframe(shot: dict[str, Any], *, work_dir: str, upload_path: str | None, seed: int, si: int) -> str | None:
    """A footage frame when the plan asked for it AND an upload exists; else a generated still."""
    if shot.get("keyframe") == "footage" and upload_path:
        url = frame_from_footage(upload_path, float(shot.get("footage_at_sec") or 0.0), work_dir, idx=si)
        if url:
            return url
    return generate_keyframe(str(shot.get("image_prompt") or shot.get("prompt") or ""), seed=seed)


def generate_shot_clip(
    shot: dict[str, Any], *, work_dir: str, upload_path: str | None = None, seed: int = 0
) -> dict[str, Any]:
    """Resolve keyframe → animate → download one shot. Returns {shot_index, ok, clip_path?, duration_s?, reason?}."""
    raw_si = shot.get("shot_index")
    si = raw_si if isinstance(raw_si, int) else 0
    dur = float(shot.get("duration_s") or 5.0)
    kf_url = _resolve_keyframe(shot, work_dir=work_dir, upload_path=upload_path, seed=seed, si=si)
    if not kf_url:
        return {"shot_index": si, "ok": False, "reason": "no_keyframe"}
    clip_url = higgsfield_client.generate_clip(
        kf_url,
        str(shot.get("prompt") or ""),
        motion_name=shot.get("motion"),
        motion_strength=float(shot.get("motion_strength") or 0.8),
        seed=seed,
        duration_s=dur,
        max_wait_s=_MAX_CLIP_WAIT_S,
        label=f"hf_shot{si}",
    )
    if not clip_url:
        return {"shot_index": si, "ok": False, "reason": "no_clip"}
    dest = os.path.join(work_dir, f"shot_{si}.mp4")
    if not _download(clip_url, dest):
        return {"shot_index": si, "ok": False, "reason": "download"}
    return {"shot_index": si, "ok": True, "clip_path": dest, "duration_s": dur}


def generate_all(
    plan: list[dict[str, Any]], *, work_dir: str, upload_path: str | None = None, seed_base: int = 0
) -> list[dict[str, Any]]:
    """Generate every shot in `plan` (capped at MAX_SHOTS), in order. Returns per-shot result dicts;
    the assembler keeps only ok=True ones. SYNC — runs in the montage worker thread."""
    shots = [s for s in plan if isinstance(s, dict)][:MAX_SHOTS]

    def _one(pair: tuple[int, dict[str, Any]]) -> dict[str, Any]:
        i, shot = pair
        raw_si = shot.get("shot_index")
        si = raw_si if isinstance(raw_si, int) else 0
        # Per-shot guard so one malformed shot is SKIPPED (ok=False), never sinking the whole reel.
        try:
            return generate_shot_clip(shot, work_dir=work_dir, upload_path=upload_path, seed=(seed_base + i * 7))
        except Exception as exc:  # noqa: BLE001 — isolate a bad shot; the reel builds from the rest
            log.warning("hf_gen.shot_crashed", shot_index=si, error=str(exc)[:160])
            return {"shot_index": si, "ok": False, "reason": "error"}

    results: list[dict[str, Any]] = []
    workers = max(1, min(_GEN_CONCURRENCY, len(shots) or 1))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        # ex.map preserves input order, so `results` stays in shot order for the assembler.
        for r in ex.map(_one, list(enumerate(shots))):
            results.append(r)
            log.info("hf_gen.shot_done", shot_index=r.get("shot_index"), ok=r.get("ok"), reason=r.get("reason"))
    ok = sum(1 for r in results if r.get("ok"))
    log.info("hf_gen.all_done", total=len(results), ok=ok)
    return results

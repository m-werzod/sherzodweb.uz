"""Background music bed selection.

Royalty-free / CC0 tracks live under app/assets/music/*.mp3. The compiler beds
the chosen track UNDER the voice (sidechain-ducked) so it lifts the energy
without fighting the narration. Returns None when no tracks are bundled — the
compiler then renders voice-only, so the feature is dormant (not broken) until
tracks are dropped in.

Mood/energy matching: an OPTIONAL `manifest.json` in the music dir maps each
file to {"energy": 0..1, "mood": "...", "bpm": N}. When present, pick_track
selects the track whose energy best matches the montage's pacing (cut density);
without a manifest it falls back to the deterministic seed pick. So adding
tracks + a manifest upgrades selection with no code change.
"""
from __future__ import annotations

import glob
import json
import os

_MUSIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "music")
_MANIFEST = os.path.join(_MUSIC_DIR, "manifest.json")


def available_tracks() -> list[str]:
    return sorted(glob.glob(os.path.join(_MUSIC_DIR, "*.mp3")))


def _load_manifest() -> dict[str, dict]:
    """filename → {energy, mood, bpm}. Best-effort → {} (missing/malformed)."""
    try:
        with open(_MANIFEST, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def select_track(tracks: list[str], manifest: dict, *, seed: int, energy: float | None) -> str | None:
    """Pure selection: energy-match via the manifest when possible, else seed pick.

    `energy` is the montage's target 0..1 (higher = faster cuts). A track's
    manifest energy closest to the target wins; ties + manifest-less tracks fall
    back to the deterministic seed pick so output stays reproducible.
    """
    if not tracks:
        return None
    if energy is not None and manifest:
        scored: list[tuple[float, int, str]] = []
        for i, path in enumerate(tracks):
            meta = manifest.get(os.path.basename(path))
            if not isinstance(meta, dict) or meta.get("energy") is None:
                continue
            try:
                te = float(meta["energy"])
            except (TypeError, ValueError):
                continue
            # Lower distance is better; (i + seed) breaks ties deterministically.
            scored.append((abs(te - energy), (i + abs(seed)) % len(tracks), path))
        if scored:
            scored.sort(key=lambda x: (x[0], x[1]))
            return scored[0][2]
    return tracks[abs(seed) % len(tracks)]


def pick_track(seed: int = 0, *, energy: float | None = None) -> str | None:
    """Pick a bundled track, energy-aware when a manifest is present (varies per
    task via `seed`)."""
    return select_track(available_tracks(), _load_manifest(), seed=seed, energy=energy)


def music_prompt(energy: float | None, style_hint: str | None = None) -> str:
    """Energy 0..1 → a stable-audio text prompt (PURE/testable). Always instrumental +
    no-vocals so it sits UNDER the narration without competing words."""
    e = energy if energy is not None else 0.5
    if e >= 0.66:
        mood = "upbeat energetic, driving beat, motivational"
    elif e <= 0.33:
        mood = "calm soft lo-fi, gentle, ambient"
    else:
        mood = "modern light, steady groove"
    base = f"{mood} background music, instrumental, no vocals, seamless loop"
    hint = (style_hint or "").strip()[:120]
    # the scriptwriter's audioSuggestion (genre/tempo/reference) makes the bed CONTENT-matched
    return f"{hint}, {base}" if hint else base


def music_gen_enabled() -> bool:
    """Whether to generate a background track when no CC0 asset is bundled.

    DEFAULT ON when a FAL_KEY exists — background music is a core product promise and
    every render was previously silent (no bundled mp3s ship). An explicit
    MONTAGE_MUSIC_GEN of 0/false/no still disables it; with no fal key generation is
    impossible so it stays off regardless.
    """
    flag = os.getenv("MONTAGE_MUSIC_GEN", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    return bool(os.getenv("FAL_KEY", "").strip())


def gen_music_track(*, energy: float | None, duration_sec: float, work_dir: str, style_hint: str | None = None) -> str | None:
    """Generate a background track via fal.ai stable-audio when no CC0 asset is bundled —
    closes the 'no music at all' gap until real tracks are dropped in. Gated by
    music_gen_enabled() (DEFAULT ON when FAL_KEY is set); FAIL-SOFT (no key / API error /
    bad download → None → the compiler renders voice-only). SYNC — runs in the montage
    worker thread (mirrors fal_client)."""
    if not music_gen_enabled():
        return None
    # The bedding chain LOOPS the track to cover the video, so a ~30s clip is enough
    # (cheaper + within stable-audio's window); clamp to a sane band.
    secs = int(max(20.0, min(duration_sec or 30.0, 47.0)))
    # Lazy import keeps fal/httpx off the hot path when music-gen is disabled.
    import httpx

    from app.montage.fal_client import run_queue_audio

    url = run_queue_audio(
        "fal-ai/stable-audio",
        {"prompt": music_prompt(energy, style_hint), "seconds_total": secs},
        label="music_gen",
    )
    if not url:
        return None
    out = os.path.join(work_dir, "gen_music.wav")
    try:
        with httpx.Client(timeout=90.0) as client:
            r = client.get(url)
            if r.status_code >= 400:
                return None
            with open(out, "wb") as f:
                f.write(r.content)
        return out if os.path.exists(out) and os.path.getsize(out) > 0 else None
    except Exception:  # noqa: BLE001 — optional GPU pass; never break the render
        return None

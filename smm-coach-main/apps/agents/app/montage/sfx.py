"""Sound-design (SFX) for the montage — whoosh/glitch/click accents, synthesized with ffmpeg.

The professional-reference edits (CapCut-style reels) always carry SFX: a "whoosh" as on-screen text
pops in, a "glitch" hit on hard transitions, a "click" on the CTA gesture. The EDL has carried
`audio.sfx` events (planned by montage_director's sfx intents) since Faza A4 — but the compiler never
RENDERED them. This module closes that gap without shipping binary assets: each SFX type is
synthesized on the fly via ffmpeg lavfi (noise sweeps / sine ticks), so the feature works everywhere
the encoder does. Everything is FAIL-SOFT: a synthesis error just drops SFX from the mix.
"""
from __future__ import annotations

import os

import structlog

from app.montage.edl import EDL, Sfx
from app.montage.probe import FFmpegError, run_ff

log = structlog.get_logger(__name__)

_MAX_SFX = 6          # cap so a stat-heavy edit doesn't turn into a slot machine
_MIN_GAP_S = 0.8      # two accents closer than this read as noise — keep the louder story

# type → lavfi synthesis recipe (0.06-0.4s, 48k stereo). Deterministic; no binary assets.
_RECIPES: dict[str, str] = {
    # airy noise swell — text/overlay pop-in
    "whoosh": (
        "anoisesrc=d=0.35:color=pink:amplitude=0.9,"
        "lowpass=f=4000,afade=t=in:d=0.08,afade=t=out:st=0.15:d=0.2"
    ),
    # harsh chopped noise burst — glitch/hard transition hit
    "glitch": (
        "anoisesrc=d=0.18:color=white:amplitude=0.95,"
        "tremolo=f=28:d=0.9,highpass=f=900,afade=t=out:st=0.1:d=0.08"
    ),
    # short bright tick — CTA/emphasis click
    "click": "sine=frequency=1500:duration=0.06,afade=t=out:st=0.02:d=0.04",
}
_FALLBACK_TYPE = "whoosh"
_COMMON_TAIL = ",aformat=sample_rates=48000:channel_layouts=stereo"


def synth_sfx(sfx_type: str, work_dir: str) -> str | None:
    """Synthesize one SFX wav into `work_dir` (cached per type); path or None. FAIL-SOFT."""
    t = sfx_type if sfx_type in _RECIPES else _FALLBACK_TYPE
    out = os.path.join(work_dir, f"sfx_{t}.wav")
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out
    try:
        run_ff(["ffmpeg", "-y", "-f", "lavfi", "-i", _RECIPES[t] + _COMMON_TAIL, out], timeout=30)
    except (FFmpegError, OSError) as exc:
        log.warning("sfx.synth_failed", type=t, error=str(exc)[:120])
        return None
    return out if os.path.exists(out) and os.path.getsize(out) > 0 else None


def derive_sfx_events(edl: EDL) -> list[Sfx]:
    """Deterministic sound-design floor when the LLM planned none (PURE):
    whoosh on each planned on-screen overlay, glitch on each transition — de-crowded to _MIN_GAP_S,
    capped at _MAX_SFX, sorted by time. Mirrors heuristic_intents: a montage should never be flat."""
    events: list[tuple[float, str]] = []
    for ov in edl.overlays:
        events.append((max(0.0, ov.at_sec), "whoosh"))
    for tr in edl.transitions:
        events.append((max(0.0, tr.at_sec), "glitch"))
    events.sort(key=lambda e: e[0])
    out: list[Sfx] = []
    last = -10.0
    for at, typ in events:
        if at - last < _MIN_GAP_S:
            continue
        out.append(Sfx(at_sec=round(at, 3), type=typ))
        last = at
        if len(out) >= _MAX_SFX:
            break
    return out


def sfx_graph(
    events: list[Sfx], work_dir: str, first_input_idx: int
) -> tuple[list[str], list[str]]:
    """(extra ffmpeg -i args, filter parts ending in [sfxall]) for the given events (≤_MAX_SFX).
    Empty lists when nothing could be synthesized — the caller then keeps its plain audio map."""
    files: list[tuple[str, float]] = []
    for ev in events[:_MAX_SFX]:
        p = synth_sfx(ev.type, work_dir)
        if p:
            files.append((p, max(0.0, ev.at_sec)))
    if not files:
        return [], []
    inputs: list[str] = []
    parts: list[str] = []
    labels: list[str] = []
    for k, (path, at) in enumerate(files):
        inputs += ["-i", path]
        ms = int(at * 1000)
        parts.append(f"[{first_input_idx + k}:a]adelay={ms}|{ms}[sd{k}]")
        labels.append(f"[sd{k}]")
    if len(labels) == 1:
        parts.append(f"{labels[0]}volume=2.2[sfxall]")
    else:
        parts.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,volume=2.2[sfxall]"
        )
    return inputs, parts

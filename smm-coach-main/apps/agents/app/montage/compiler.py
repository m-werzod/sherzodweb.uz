"""The deterministic montage compiler: EDL -> ONE ffmpeg render.

Orchestrates the spine — normalize -> silence-cut -> captions -> voice chain ->
burn -> encode — and owns the RENDER-FAILURE DEGRADE LADDER so the user always
gets *something* back even when the full filtergraph chokes on real phone input:

    L0  cuts + captions + voice chain   (the intended montage)
    L1  no cuts + captions + voice      (guards a concat failure)
    L2  no cuts + voice only            (guards a libass failure)
    L3  the normalized clip, untouched  (guaranteed deliverable)

Captions are burned LAST so nothing downstream blurs the text. ffmpeg is CPU
libx264 (Coolify has no GPU/NVENC).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

from app.config import get_settings
from app.integrations.stock.pexels import download_video
from app.montage.audio import build_voice_chain
from app.montage.broll import resolve_broll
from app.montage.captions import render_ass
from app.montage.decor import generate_background, matte_subject
from app.montage.edl import (
    CAPTION_FONTS,
    EDL,
    AssetRef,
    Audio,
    Broll,
    CaptionStyle,
    CaptionWindow,
    CaptionWord,
    EffectIntent,
    LangVariant,
    Motion,
    Sfx,
    Source,
    SourceVariant,
    Transition,
)
from app.montage.effects import resolve_effect_intents
from app.montage.fal_client import upload_file
from app.montage.footage_vision import detect_shots
from app.montage.gate import ENCODE_GATE
from app.montage.heygen_client import translate_video
from app.montage.inpaint import inpaint_local
from app.montage.motion import glitch, ken_burns, shake, zoom_punch
from app.montage.music import available_tracks, gen_music_track, pick_track
from app.montage.normalize import normalize_clip
from app.montage.probe import FFmpegError, probe_clip, run_ff
from app.montage.sfx import derive_sfx_events, sfx_graph
from app.montage.shotstack_client import shotstack_enabled
from app.montage.shotstack_map import render_via_shotstack
from app.montage.timing import (
    _script_words,
    align_script_to_transcript,
    assign_shot_index,
    build_caption_windows,
    build_caption_windows_from_transcript,
    build_cuts,
    build_motion,
    build_overlays,
    detect_silences,
    subdivide_cuts,
    subdivide_evenly,
    subtract_spans,
)
from app.montage.transcribe import transcribe_words, word_times

log = structlog.get_logger(__name__)

_MIN_OUTPUT_SEC = 3.0
# Closed allowlist — a hand-edited EDL must not inject arbitrary ffmpeg ops.
_MOTION_OPS = {"zoom_punch", "kenburns", "shake", "glitch"}
# Closed map EDL transition.type -> ffmpeg xfade `transition=` name. This is the INJECTION GUARD:
# the value fed to ffmpeg ALWAYS comes from this dict's values ({fade,dissolve}), never from the
# (possibly hand-edited) EDL string — an unrecognised type simply isn't in the map, so that
# boundary renders as a plain hard cut. Restricted to the two transitions STUDIO's drawScene also
# renders as an opacity ramp (Crossfade/Dissolve), so the ffmpeg export matches the STUDIO preview.
_XFADE_MAP = {
    "xfade": "fade",
    "crossfade": "fade",
    "fade": "fade",
    "dissolve": "dissolve",
    "fadeblack": "dissolve",
}
_TRANSITION_MAX_DUR = 0.6  # cap a crossfade so it can't eat a short cut
_TRANSITION_SNAP = 0.30  # how near (OUTPUT sec) a transition must sit to a cut boundary to apply


@dataclass
class RenderResult:
    ok: bool
    out_path: str | None
    duration: float
    size_bytes: int
    degrade_level: int
    error: str | None = None
    engine: str = "ffmpeg"  # ffmpeg (local ladder) | shotstack (cloud) — cost/scale telemetry


def coverage_ok(edl: EDL, script_timeline: list[object]) -> tuple[bool, str]:
    """Reject only a genuinely unusable clip (essentially no speech). The
    caption pace is capped to the clip length (build_caption_windows), so a clip
    shorter than the script still produces a readable montage of what was said —
    no need to reject for not covering the whole script."""
    out = edl.output_duration()
    if out < _MIN_OUTPUT_SEC:
        return False, "Klip juda qisqa yoki nutq topilmadi — qayta yozib yuklang."
    return True, ""


def _caption_params(
    caption_spec: dict[str, Any] | None,
) -> tuple[CaptionStyle | None, str, list[str]]:
    """Translate the caption_stylist agent's spec into build_caption_windows args.
    Falls back to deterministic defaults when no agent ran (no spec)."""
    if not caption_spec:
        return None, "premium", []
    style = CaptionStyle()
    raw = caption_spec.get("style") or {}
    if isinstance(raw, dict):
        if "size" in raw:
            with contextlib.suppress(TypeError, ValueError):
                style.size = int(raw["size"])
        if raw.get("active"):
            style.active = str(raw["active"])
        if raw.get("font") in CAPTION_FONTS:  # bundled trend face; else keep Montserrat default
            style.font = str(raw["font"])
    tier = "premium"
    if caption_spec.get("tier") in ("premium", "cheap"):
        tier = str(caption_spec["tier"])
    emphasis = caption_spec.get("emphasis") or []
    emph = [str(w) for w in emphasis] if isinstance(emphasis, list) else []
    return style, tier, emph


def build_edl(
    normalized_path: str,
    upload_key: str,
    script_timeline: list[object],
    *,
    task_id: str,
    tenant_id: str,
    caption_spec: dict[str, Any] | None = None,
    word_src_times: list[float] | None = None,
    transcript: list[dict[str, Any]] | None = None,
    drop_src_ranges: list[tuple[float, float]] | None = None,
    enable_semantic_cut: bool = True,
    shot_list: list[object] | None = None,
    shot_src_times: list[float] | None = None,
    effect_intents: list[EffectIntent] | None = None,
) -> EDL:
    """Build the EDL deterministically from a NORMALIZED clip + the script.
    `word_src_times` (transcript word END times in SOURCE seconds) are mapped to
    OUTPUT seconds via the cuts so captions follow the real speech cadence.
    `transcript` (the FULL word list text+start+end) drives the Stage-9b semantic stumble-cut.
    `shot_list` (the scriptwriter storyboard) feeds the planned text overlays.
    `shot_src_times` (footage_analyzer's vision-detected scene boundaries) drive the cuts."""
    info = probe_clip(normalized_path)
    silences = detect_silences(normalized_path)
    cuts = build_cuts(info.duration, silences)
    # Faza 1b: cut where the FOOTAGE cuts — subdivide silence-derived cuts at real visual
    # scene changes so motion/overlays land on content boundaries. Duration-preserving, so
    # the OUTPUT offset table is unchanged; degrade-safe (no scenes -> cuts unchanged).
    # AG-2: prefer footage_analyzer's vision-detected boundaries (detected on the RAW upload, but
    # normalize preserves duration so they map 1:1 to normalized seconds) — so cuts land on the SAME
    # shots the Gemini vision pass saw, instead of a redundant second scene-detect on the
    # letterboxed/CFR clip whose deltas don't line up. Fall back to re-detecting when absent.
    scene_times = shot_src_times if shot_src_times else detect_shots(normalized_path)
    cuts = subdivide_cuts(cuts, scene_times)
    # Stage 9b: drop the spans the speaker fumbled — semantic stumble-cut (filler/repeats/off-script
    # from the transcript↔script alignment) UNION footage bad-take rejects (shots matching no
    # storyboard shot, passed in as drop_src_ranges). Keeps only the clean delivery, not just
    # non-silent audio. Duration-CHANGING, so it MUST run here (before assign_shot_index + the OUTPUT
    # lanes) and the offset table is rebuilt from the shortened cuts. (Kill switch in compile_and_render.)
    drops: list[tuple[float, float]] = list(drop_src_ranges or [])
    if transcript and enable_semantic_cut:
        drops += align_script_to_transcript(transcript, script_timeline)
    if drops:
        trimmed = subtract_spans(cuts, drops)
        orig_dur = sum(c.src_end - c.src_start for c in cuts)
        trim_dur = sum(c.src_end - c.src_start for c in trimmed)
        # Apply only if a usable AND not-over-cut montage survives: ≥3s absolute
        # AND ≥40% of the speech retained. A higher drop ratio means the aligner
        # over-flagged (aggressive uz filler/off-script detection) → keep the safer
        # silence-only cuts so the result is never jittery/incoherent.
        if trim_dur >= _MIN_OUTPUT_SEC and (orig_dur <= 0 or trim_dur >= 0.40 * orig_dur):
            cuts = trimmed
    # Edit floor: a fluent clip (few/no silences, no detected scenes) collapses to
    # ~1 cut → a flat passthrough montage with no rhythm and no boundary for
    # transitions/zoom-punch to attach to (the "montaj ishlamaydi" report). If we
    # ended up with <3 cuts on a clip long enough to carry rhythm, subdivide evenly
    # so each ~3s segment gets its own motion + a transition anchor. Duration-
    # preserving → the two-timebase offset table is unchanged; degrade-safe.
    if len(cuts) < 3 and sum(c.src_end - c.src_start for c in cuts) >= 8.0:
        cuts = subdivide_evenly(cuts)
    # G1 fix: thread the scriptwriter storyboard shot onto each cut (in place) so the
    # planned cam/frame/action/vfx stay reachable from the cut. Must run BEFORE the EDL
    # is constructed so the persisted EDL carries the linkage.
    assign_shot_index(cuts, script_timeline)
    style, tier, emphasis = _caption_params(caption_spec)
    edl = EDL(
        task_id=task_id,
        tenant_id=tenant_id,
        source=Source(
            upload_key=upload_key,
            duration_sec=info.duration,
            fps=info.fps or 30.0,
            w=info.width or 1080,
            h=info.height or 1920,
        ),
        cuts=cuts,
        audio=Audio(),
    )
    # Transcript times are in SOURCE seconds; the cuts removed dead air, so map
    # each onto the OUTPUT timeline (drop any that fell in a cut-out gap).
    word_out: list[float] | None = None
    if word_src_times:
        mapped = [edl.source_to_output(t) for t in word_src_times]
        word_out = [t for t in mapped if t is not None]
        if len(word_out) < 3:
            word_out = None
    # Captions from the ACTUAL transcript (the real spoken words at their real timestamps, mapped
    # onto the post-cut timeline) — this is what makes the karaoke match the speaker's mouth. The
    # planned-script proportional builder is only the fallback when there's no transcript (Whisper
    # off/failed) or it yields nothing after the cuts.
    caps = None
    if transcript:
        caps = build_caption_windows_from_transcript(
            edl, transcript, style=style, tier=tier, emphasis_words=emphasis,
            script_words=_script_words(script_timeline),
        )
    if caps is None or not caps.windows:
        caps = build_caption_windows(
            cuts, script_timeline, style=style, tier=tier,
            emphasis_words=emphasis, word_out_times=word_out,
        )
    edl.captions = caps
    # Faza 2: render the storyboard's planned on-screen text (was orphaned). OUTPUT-timed
    # via the cut.shot_index linkage; burned as extra ASS lines, no filtergraph change.
    edl.overlays = build_overlays(cuts, shot_list or [])
    # Faza 2b: the storyboard's planned camera zooms drive per-cut motion (zoom_punch);
    # cuts with no planned zoom keep the default ken-burns drift (see _cut_motion).
    edl.motion = build_motion(cuts, shot_list or [])
    # Faza A4: the montage_director's planned EffectIntents AUGMENT the heuristic lanes
    # (zoom/vfx/decor/transition/sfx). Guarded — empty/absent intents leave the EDL byte-identical.
    if effect_intents:
        edl.effect_intents = list(effect_intents)
        resolve_effect_intents(edl, edl.effect_intents)
    # Transition floor: hard cuts everywhere read as "keskin" (abrupt) next to reference edits.
    # When the director planned none, crossfade ALTERNATE internal boundaries deterministically —
    # _transition_plan still drops any boundary lacking source tail, so this stays duration-neutral.
    if not edl.transitions and len(edl.cuts) >= 3:
        acc = 0.0
        for i in range(len(edl.cuts) - 1):
            acc += max(0.0, edl.cuts[i].src_end - edl.cuts[i].src_start)
            edl.transitions.append(Transition(at_sec=round(acc, 3), type="fade", dur=0.3))
    # Sound-design floor: reference-grade reels always carry SFX accents (whoosh on text pops,
    # glitch on transitions). When the director planned none, derive them deterministically so
    # the mix is never flat — same philosophy as heuristic_intents.
    if not edl.audio.sfx:
        edl.audio.sfx = derive_sfx_events(edl)
    _apply_rehook_beats(edl)
    return edl


def _apply_rehook_beats(edl: EDL) -> None:
    """Re-hook interrupts (playbook Pillar 01): attention drifts mid-reel, so on longer reels add a
    short visual+audio INTERRUPT — a punch-in (guaranteed: build_edit/_cut_motion read edl.motion)
    + a whoosh — at ~15s (and ~30s) to reset the retention curve at the seconds people usually
    leave. No invented text (that would risk a clickbait mismatch); the interrupt re-grabs and the
    speaker's own words carry the re-hook. Duration-neutral (an accent, not a cut). Mutates edl."""
    out = edl.output_duration()
    for beat in (15.0, 30.0):
        if out < beat + 3.0:  # need real content AFTER the beat for a re-hook to matter
            break
        edl.motion.append(Motion(op="zoom_punch", at_sec=round(beat, 3), dur=0.5, to_scale=1.12))
        edl.audio.sfx.append(Sfx(at_sec=round(beat, 3), type="whoosh"))
    edl.audio.sfx.sort(key=lambda s: s.at_sec)


def _hook_display_dur(edl: EDL, target: float = 2.5, lo: float = 2.5, hi: float = 3.2) -> float:
    """Content-aware on-screen hook duration: keep the hook slogan up through the END of the
    caption window that spans the ~2.5s opening (the playbook's first-3s hook window), so a
    ~2.8s spoken hook isn't chopped at a static 2.0s nor a 1s one stretched to it. Clamped to a
    readable range. PURE. Falls back to the EDL default when there are no caption windows."""
    end = 0.0
    for w in edl.captions.windows:
        we = max((x.end for x in w.words), default=0.0)
        if we <= 0.0:
            continue
        end = we
        if we >= target:
            break
    if end <= 0.0:
        return edl.hook.display_dur
    return max(lo, min(hi, round(end, 3)))


def _encode_tail(out_path: str) -> list[str]:
    return [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path,
    ]


def _cut_motion(edl: EDL, i: int) -> str:
    """The video-motion filter chain for cut `i` = ONE framing move + any additive vfx.

    Framing move: the storyboard's planned zoom (an EDL zoom_punch whose OUTPUT at_sec lands
    inside the cut) if present, else the safe default ken-burns drift (alternating push/pull so
    shots don't feel mechanical). VFX: shake/glitch Motion ops whose OUTPUT window overlaps the
    cut are CHAINED after the framing move (composable — a cut can both punch-in AND glitch).
    The `montage_director` already emits these vfx ops; until now `_cut_motion` silently dropped
    them (only zoom_punch was honoured). Pure string-building; no ffmpeg — unit-testable.

    Default path (no shake/glitch motion) returns the framing move unchanged → byte-identical to
    before, so existing montages don't regress."""
    c = edl.cuts[i]
    dur = c.src_end - c.src_start
    out_start = sum(max(0.0, x.src_end - x.src_start) for x in edl.cuts[:i])
    out_end = out_start + max(0.0, dur)
    zoom = kb = None
    vfx: list[str] = []
    for m in edl.motion:
        if not (out_start - 1e-3 <= m.at_sec < out_end):
            continue
        if m.op == "zoom_punch":
            zoom = zoom or m
        elif m.op == "kenburns":
            kb = kb or m
        elif m.op == "shake":
            vfx.append(shake(dur, easing=m.easing))
        elif m.op == "glitch":
            vfx.append(glitch(dur))
    # Framing move: a planned punch wins over the default drift; an explicit kenburns entry
    # (build_motion now emits one per cut) wins over the i%2 fallback (kept for EDLs without one).
    if zoom is not None:
        base = zoom_punch(dur, easing=zoom.easing)
    elif kb is not None:
        base = ken_burns(dur, zoom_in=(kb.to_scale >= kb.from_scale), easing=kb.easing)
    else:
        base = ken_burns(dur, zoom_in=(i % 2 == 0))
    return ",".join([base, *vfx]) if vfx else base


def _renderable_broll(edl: EDL) -> list[Broll]:
    """B-roll entries that can ACTUALLY render: overlay placement, a downloaded local asset that
    still exists, and a valid OUTPUT window inside the timeline. Sorted by start (deterministic
    input order). The os.path.exists guard means a persisted EDL whose temp asset is long gone
    (e.g. a manual re-render) simply renders without that b-roll — never a broken input."""
    out: list[Broll] = []
    for b in edl.broll:
        if (
            b.placement == "overlay"
            and b.asset_url
            and b.at_sec is not None
            and b.output_dur_sec
            and b.output_dur_sec > 0
            and edl.validate_output_atsec(b.at_sec)
            and os.path.exists(b.asset_url)
        ):
            out.append(b)
    out.sort(key=lambda b: b.at_sec or 0.0)
    return out


def _transition_plan(edl: EDL, *, enabled: bool = True) -> dict[int, tuple[str, float]]:
    """Map each EDL transition onto a cut BOUNDARY → {cut_index: (ffmpeg_name, dur)} meaning
    'crossfade the tail of cut `i` into cut `i+1`'. Pure + unit-testable.

    Guards: only types in the closed `_XFADE_MAP` (injection-safe); snapped to the nearest internal
    boundary within `_TRANSITION_SNAP`; one transition per boundary; dropped if there isn't `dur`
    seconds of source left after the cut to extend its tail into (so the crossfade can stay
    DURATION-NEUTRAL — see `_join_parts`). `enabled=False` → {} (the degrade-ladder isolation rung
    that falls back to hard cuts)."""
    n = len(edl.cuts)
    if not enabled or n < 2 or not edl.transitions:
        return {}
    bounds: list[float] = []  # bounds[i] = OUTPUT sec of the boundary AFTER cut i
    acc = 0.0
    for i in range(n - 1):
        acc += max(0.0, edl.cuts[i].src_end - edl.cuts[i].src_start)
        bounds.append(acc)
    src_dur = edl.source.duration_sec or (edl.cuts[-1].src_end if edl.cuts else 0.0)
    plan: dict[int, tuple[str, float]] = {}
    for t in edl.transitions:
        ff = _XFADE_MAP.get((t.type or "").strip().lower())
        if ff is None:
            continue
        d = max(0.05, min(t.dur or 0.3, _TRANSITION_MAX_DUR))
        best_i, best_dist = None, _TRANSITION_SNAP
        for i, b in enumerate(bounds):
            if i in plan:
                continue
            dist = abs(b - t.at_sec)
            if dist < best_dist:
                best_i, best_dist = i, dist
        if best_i is None:
            continue
        # Need `d` seconds of source after cut best_i to extend its tail into (the trimmed silence),
        # else the crossfade would shrink the timeline / overrun the clip — drop to a hard cut.
        if src_dur - edl.cuts[best_i].src_end < d:
            continue
        plan[best_i] = (ff, d)
    return plan


def _join_parts(n: int, plan: dict[int, tuple[str, float]], rendered_lens: list[float]) -> list[str]:
    """Build the filtergraph step(s) that join per-cut [v0..v{n-1}]/[a0..a{n-1}] into [vc][ac].

    No transitions → the original single n-way concat (BYTE-IDENTICAL, no regression). Otherwise a
    left-fold: each boundary is either a 2-input `concat` (hard cut) or `xfade`+`acrossfade`
    (crossfade). DURATION-NEUTRAL: the cut before a crossfade was rendered with `dur` extra source
    seconds (see `_try_full`), so `offset = acc_len - dur` puts the fade exactly on the original
    boundary and `out = in1 + in2 - dur` nets back to the hard-cut total. Pure + unit-testable."""
    if not plan:
        concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
        return [f"{concat_in}concat=n={n}:v=1:a=1[vc][ac]"]
    parts: list[str] = []
    v_label, a_label = "v0", "a0"
    acc = rendered_lens[0]
    for i in range(1, n):
        vout = "vc" if i == n - 1 else f"vj{i}"
        aout = "ac" if i == n - 1 else f"aj{i}"
        ent = plan.get(i - 1)
        if ent:
            ff, d = ent
            offset = max(0.0, acc - d)
            parts.append(f"[{v_label}][v{i}]xfade=transition={ff}:duration={d:.3f}:offset={offset:.3f}[{vout}]")
            parts.append(f"[{a_label}][a{i}]acrossfade=d={d:.3f}[{aout}]")
            acc = acc + rendered_lens[i] - d
        else:
            parts.append(f"[{v_label}][v{i}]concat=n=2:v=1:a=0[{vout}]")
            parts.append(f"[{a_label}][a{i}]concat=n=2:v=0:a=1[{aout}]")
            acc = acc + rendered_lens[i]
        v_label, a_label = vout, aout
    return parts


def _try_full(edl: EDL, src: str, ass: str, out: str, *, with_broll: bool = True, with_transitions: bool = True) -> None:
    """L0: cut + concat + (B-roll overlays) + burn captions + voice chain (+ ducked music bed).

    `with_broll` full-frame stock overlays cover the shots the footage missed — a cut-away LOOK
    (voice continues underneath, captions stay on top) that is OUTPUT-timed and duration-
    preserving, so the two-timebase table is untouched. The ladder retries with_broll=False, so
    a b-roll splice failure only drops b-roll, never the cuts/captions."""
    ln = edl.audio.loudnorm
    # Energy proxy from pacing: cuts-per-second mapped to 0..1 (≈0.15/s calm →
    # ≈0.8/s punchy). When a music manifest is present, pick_track uses this to
    # match a track's energy; otherwise it's ignored (seed pick).
    _out_dur = sum((c.src_end - c.src_start) for c in edl.cuts) or edl.source.duration_sec or 1.0
    _energy = max(0.0, min(1.0, (len(edl.cuts) / _out_dur) / 0.8))
    # Prefer a pre-resolved track (worker-generated fal.ai music when no CC0 asset is
    # bundled), else fall back to a bundled CC0 pick. None → voice-only (dormant, not broken).
    track = edl.audio.music_path or pick_track(seed=len(edl.cuts) + int(edl.source.duration_sec), energy=_energy)
    # Crossfade plan: a cut FOLLOWED by a transition is rendered with `dur` extra source seconds so
    # the xfade overlap nets back to the hard-cut duration (duration-neutral → the two-timebase
    # offset table the captions/overlays/motion depend on is untouched). Empty plan → byte-identical
    # to the old hard-cut concat path (no regression).
    plan = _transition_plan(edl, enabled=with_transitions)
    parts: list[str] = []
    rendered_lens: list[float] = []
    for i, c in enumerate(edl.cuts):
        motion = _cut_motion(edl, i)
        ext = plan.get(i, ("", 0.0))[1]  # extend this cut's tail into the trimmed silence for the xfade
        v_end = c.src_end + ext
        rendered_lens.append(max(0.0, v_end - c.src_start))
        parts.append(
            f"[0:v]trim=start={c.src_start:.3f}:end={v_end:.3f},"
            f"setpts=PTS-STARTPTS,{motion}[v{i}]"
        )
        parts.append(
            f"[0:a]atrim=start={c.src_start:.3f}:end={v_end:.3f},"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )
    n = len(edl.cuts)
    parts.extend(_join_parts(n, plan, rendered_lens))

    # B-roll overlays: each rides OVER the concatenated speaker on its OUTPUT window, inserted
    # BEFORE the caption burn so karaoke text stays on top. B-roll video inputs come AFTER the
    # upload (input 0) and the optional music bed (input 1) — so the first b-roll's stream index
    # is 2 with music, 1 without. setpts shifts the looped clip to start at the window.
    brolls = _renderable_broll(edl) if with_broll else []
    broll_inputs: list[str] = []
    vlabel = "vc"
    base_idx = 2 if track else 1
    w, h = edl.source.w or 1080, edl.source.h or 1920
    for k, b in enumerate(brolls):
        idx = base_idx + k
        assert b.asset_url and b.at_sec is not None and b.output_dur_sec is not None  # _renderable_broll guaranteed
        broll_inputs += ["-stream_loop", "-1", "-i", b.asset_url]
        end = b.at_sec + b.output_dur_sec
        parts.append(
            f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"setsar=1,trim=0:{b.output_dur_sec:.3f},setpts=PTS-STARTPTS+{b.at_sec:.3f}/TB[bk{k}]"
        )
        parts.append(
            f"[{vlabel}][bk{k}]overlay=enable='between(t,{b.at_sec:.3f},{end:.3f})'"
            f":eof_action=pass[vb{k}]"
        )
        vlabel = f"vb{k}"
    parts.append(f"[{vlabel}]ass={ass}:fontsdir=/usr/share/fonts[vout]")

    if track:
        # Voice cleaned, then split: one copy mixes, one keys the sidechain so
        # the music ducks whenever the speaker talks. loudnorm the final mix.
        _d = edl.audio.duck
        parts.append("[ac]afftdn=nf=-25,deesser,asplit=2[v1][v2]")
        parts.append(f"[1:a]volume={_d.volume}[mlow]")
        parts.append(
            f"[mlow][v2]sidechaincompress=threshold={_d.threshold}:ratio={_d.ratio}"
            f":attack={_d.attack}:release={_d.release}[mduck]"
        )
        parts.append(
            f"[v1][mduck]amix=inputs=2:duration=first:dropout_transition=0,"
            f"loudnorm=I={ln.i}:TP={ln.tp}:LRA={ln.lra}[aout]"
        )
        sfx_in, sfx_parts = sfx_graph(edl.audio.sfx, os.path.dirname(out), 2 + len(brolls))
        amap = "[aout]"
        if sfx_parts:
            parts.extend(sfx_parts)
            parts.append("[aout][sfxall]amix=inputs=2:duration=first:normalize=0[afin]")
            amap = "[afin]"
        cmd = ["ffmpeg", "-y", "-i", src, "-stream_loop", "-1", "-i", track, *broll_inputs, *sfx_in,
               "-filter_complex", ";".join(parts),
               "-map", "[vout]", "-map", amap, *_encode_tail(out)]
    else:
        parts.append(f"[ac]{build_voice_chain(edl.audio)}[aout]")
        sfx_in, sfx_parts = sfx_graph(edl.audio.sfx, os.path.dirname(out), 1 + len(brolls))
        amap = "[aout]"
        if sfx_parts:
            parts.extend(sfx_parts)
            parts.append("[aout][sfxall]amix=inputs=2:duration=first:normalize=0[afin]")
            amap = "[afin]"
        cmd = ["ffmpeg", "-y", "-i", src, *broll_inputs, *sfx_in, "-filter_complex", ";".join(parts),
               "-map", "[vout]", "-map", amap, *_encode_tail(out)]
    run_ff(cmd)


def _try_captions_only(edl: EDL, src: str, ass: str, out: str) -> None:
    """L1: skip cuts (guards a concat failure), keep captions + voice chain."""
    chain = build_voice_chain(edl.audio)
    fc = f"[0:v]ass={ass}:fontsdir=/usr/share/fonts[vout];[0:a]{chain}[aout]"
    cmd = ["ffmpeg", "-y", "-i", src, "-filter_complex", fc,
           "-map", "[vout]", "-map", "[aout]", *_encode_tail(out)]
    run_ff(cmd)


def _try_audio_only(edl: EDL, src: str, out: str) -> None:
    """L2: skip captions (guards a libass failure), keep the voice chain."""
    chain = build_voice_chain(edl.audio)
    cmd = ["ffmpeg", "-y", "-i", src, "-af", chain,
           "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", out]
    run_ff(cmd)


def _try_passthrough(src: str, out: str) -> None:
    """L3: hand back the normalized clip untouched — guaranteed deliverable."""
    run_ff(["ffmpeg", "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", out])


def render_edl(edl: EDL, normalized_path: str, ass_path: str, out_path: str) -> RenderResult:
    """Run the degrade ladder; return the first level that produces output."""
    ladder: list[tuple[int, Callable[[], None]]] = [
        (0, lambda: _try_full(edl, normalized_path, ass_path, out_path, with_broll=True, with_transitions=True)),
        # B-roll is additive polish: if its overlay splice fails, drop ONLY b-roll and keep the
        # full montage (cuts+captions+transitions) rather than degrading all the way to L1 (no cuts).
        (0, lambda: _try_full(edl, normalized_path, ass_path, out_path, with_broll=False, with_transitions=True)),
        # Transitions are additive polish too: an xfade chain can choke on odd CFR/dimension input.
        # Drop ONLY the crossfades (back to hard-cut concat) but KEEP cuts+captions+b-roll at L0 —
        # never degrade the whole montage to L1 just because a transition failed.
        (0, lambda: _try_full(edl, normalized_path, ass_path, out_path, with_broll=True, with_transitions=False)),
        (0, lambda: _try_full(edl, normalized_path, ass_path, out_path, with_broll=False, with_transitions=False)),
        (1, lambda: _try_captions_only(edl, normalized_path, ass_path, out_path)),
        (2, lambda: _try_audio_only(edl, normalized_path, out_path)),
        (3, lambda: _try_passthrough(normalized_path, out_path)),
    ]
    last_err: str | None = None
    for level, attempt in ladder:
        try:
            attempt()
        except (FFmpegError, OSError) as exc:
            last_err = str(exc)
            log.warning("montage.render_degrade", level=level, error=str(exc)[:200])
            continue
        info = probe_clip(out_path)
        return RenderResult(
            ok=True,
            out_path=out_path,
            duration=info.duration,
            size_bytes=os.path.getsize(out_path),
            degrade_level=level,
            error=None if level == 0 else last_err,
        )
    return RenderResult(False, None, 0.0, 0, degrade_level=4, error=last_err)


def quality_verdict(degrade_level: int, cuts: int, duration_sec: float) -> dict[str, object]:
    """Deterministic, INSTANT post-render quality read (Faza-4 gate) from the degrade
    ladder + output stats — complements the async Gemini critique (subjective visual) with a
    structural verdict the studio can show immediately. ADVISORY: the caller surfaces
    `remontageRecommended`; it never auto-re-renders (a blind retry loop on a deterministic
    degrade would just waste a render). Pure → unit-testable, no ffmpeg.

    degrade_level: 0 = full montage (L0), 1 = no cuts, 2 = no captions, 3 = raw clip, 4 = total fail.
    """
    reasons: list[str] = []
    if degrade_level <= 0:
        level = "good"
    elif degrade_level == 1:
        level = "fair"
        reasons.append("Kesimlarsiz montaj (concat muammosi) — subtitr saqlandi.")
    elif degrade_level == 2:
        level = "poor"
        reasons.append("Subtitrsiz va kesimsiz — faqat ovoz qoldi.")
    else:  # 3 (raw clip) or 4 (total fail)
        level = "poor"
        reasons.append("Avtomatik montaj amalga oshmadi — xom klip qaytarildi.")

    # Duration sanity: a sub-5s "reel" almost always means something broke upstream.
    if duration_sec and duration_sec < 5:
        level = "poor"
        reasons.append(f"Natija juda qisqa ({duration_sec:.0f}s).")

    # A full (L0) render that made 0-1 cuts on a non-trivial clip is a shallow edit
    # (a single cut = the whole clip uncut = passthrough) — worth a heads-up. The
    # edit floor now subdivides such clips, so a truthful L0 render lands >=3 cuts;
    # a <=1 cut result on an >=8s clip means the floor didn't fire and the montage
    # is effectively normalize+captions. (Was cuts==0 && >=20s, which let the real
    # 10.7s/1-cut passthrough score "good".)
    if level == "good" and cuts <= 1 and duration_sec >= 8:
        level = "fair"
        reasons.append("Deyarli kesimsiz montaj — sayoz bo'lishi mumkin.")

    return {
        "level": level,
        "reasons": reasons,
        "remontageRecommended": level == "poor",
    }


def _maybe_add_inpaint_variant(edl: EDL, normalized: str, remove: str | None, *, task_id: str) -> None:
    """Faza D (opt-in): remove the task's named element (SAM-3 text auto-mask, NO mask UI) → a
    SOURCE-aligned cleaned variant on edl.source_variants. STUDIO swaps it in as the base
    (pickSourceVariant). FAIL-SOFT; gated on ENABLE_INPAINT + FAL_KEY + a remove instruction so it
    never runs unrequested. The SMM auto-render stays on the original — the user refines in STUDIO."""
    s = get_settings()
    if not (remove and remove.strip() and s.enable_inpaint and s.fal_key):
        return
    with contextlib.suppress(Exception):
        cleaned = inpaint_local(normalized, remove=remove.strip())
        if cleaned:
            edl.source_variants.append(
                SourceVariant(
                    kind="inpaint",
                    asset=AssetRef(
                        asset_id=f"inpaint:{task_id}",
                        url=cleaned,
                        kind="video",
                        duration_sec=edl.source.duration_sec,
                        w=edl.source.w,
                        h=edl.source.h,
                        fps=edl.source.fps,
                    ),
                    aligned_to_source=True,
                )
            )


def _maybe_add_decor_background(
    edl: EDL, normalized: str, decor_prompt: str | None, *, task_id: str, work_dir: str
) -> None:
    """Faza C (opt-in): replace the background with a scenario-matched scene → a SOURCE-aligned
    composited variant for the STUDIO base swap (pickSourceVariant). Mattes the speaker (bria → alpha
    WebM) + generates a vertical bg (FLUX), composites matte-over-bg via ffmpeg, and appends a
    source_variant(kind="decor"). FAIL-SOFT; gated on ENABLE_DECOR + FAL_KEY + a decor instruction.
    NOTE: the vp9-alpha ffmpeg overlay needs live verification; any failure leaves the montage unchanged."""
    s = get_settings()
    if not (decor_prompt and decor_prompt.strip() and s.enable_decor and s.fal_key):
        return
    with contextlib.suppress(Exception):
        src_url = upload_file(normalized)
        if not src_url:
            return
        matte = matte_subject(src_url)
        bg = generate_background(decor_prompt.strip())
        if not (matte and bg):
            return
        matte_path = os.path.join(work_dir, "decor_matte.webm")
        bg_path = os.path.join(work_dir, "decor_bg.png")
        if not (download_video(matte, matte_path) and download_video(bg, bg_path)):
            return
        out_path = os.path.join(work_dir, "decor.mp4")
        # bg (looped, scaled to fill the frame) UNDER the alpha matte (the speaker); silent — STUDIO
        # links the original audio back to the swapped base. shortest=1 ends at the matte's length.
        run_ff(
            [
                "ffmpeg", "-y", "-loop", "1", "-i", bg_path, "-i", matte_path,
                "-filter_complex",
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[bg];"
                "[bg][1:v]overlay=format=auto:shortest=1[o]",
                "-map", "[o]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", out_path,
            ]
        )
        variant_url = upload_file(out_path)
        if variant_url:
            edl.source_variants.append(
                SourceVariant(
                    kind="decor",
                    asset=AssetRef(
                        asset_id=f"decor:{task_id}",
                        url=variant_url,
                        kind="video",
                        duration_sec=edl.source.duration_sec,
                        w=edl.source.w,
                        h=edl.source.h,
                        fps=edl.source.fps,
                    ),
                    aligned_to_source=True,
                )
            )


_HEYGEN_LANG_NAMES = {"uz": "Uzbek", "ru": "Russian", "en": "English"}


def _redistribute_caption_windows(windows: list[CaptionWindow], lines: list[str]) -> list[CaptionWindow]:
    """PURE: har asl subtitr-oynaning [start,end] OUTPUT span'iga tarjima qatorini SO'ZMA-SO'Z teng
    taqsimlaydi (karaoke timing tildan-tilga ko'chmaydi → oyna-darajada sinxron). Bo'sh tarjima yoki
    yaroqsiz span → asl oyna saqlanadi. Oynalar soni o'zgarmaydi (STUDIO indeks bo'yicha almashtiradi)."""
    out: list[CaptionWindow] = []
    for w, line in zip(windows, lines, strict=False):
        toks = (line or "").split()
        starts = [x.start for x in w.words]
        ends = [x.end for x in w.words]
        if not w.words or not toks or not starts:
            out.append(w)
            continue
        span_start, span_end = min(starts), max(ends)
        if span_end <= span_start:
            out.append(w)
            continue
        step = (span_end - span_start) / len(toks)
        new_words = [
            CaptionWord(text=t, start=span_start + i * step, end=span_start + (i + 1) * step)
            for i, t in enumerate(toks)
        ]
        out.append(CaptionWindow(words=new_words))
    return out


def _translate_caption_lines(lines: list[str], lang_name: str) -> list[str]:
    """Subtitr qatorlarini `lang_name` tiliga tarjima qiladi (bitta batch LLM chaqiruvi). FAIL-SOFT —
    xato/uzunlik mos kelmasa asl qatorlar qaytadi. Compiler worker-thread'da (event loop yo'q), shuning
    uchun async groq_client'ni asyncio.run bilan ko'priklab chaqiramiz."""
    if not lines:
        return lines
    try:
        from app.integrations.llm import groq_client

        result = asyncio.run(
            groq_client.chat_json(
                system=(
                    f"Translate each short subtitle line into {lang_name}. Keep each line natural, "
                    "spoken, and concise (it is on-screen karaoke text). Do NOT merge or split lines. "
                    'Return JSON {"lines": [...]} with EXACTLY the same number of lines, same order.'
                ),
                user=json.dumps({"lines": lines}, ensure_ascii=False),
                max_tokens=1500,
                agent_name="caption_localize",
            )
        )
        out = result.get("lines") if isinstance(result, dict) else None
        if isinstance(out, list) and len(out) == len(lines):
            return [str(x) for x in out]
    except Exception as exc:  # noqa: BLE001 — caption translation is optional; degrade to source lines
        log.warning("caption_localize.failed", lang=lang_name, error=str(exc)[:160])
    return lines


def _maybe_add_translate_variants(
    edl: EDL, normalized: str, target_langs: list[str], *, task_id: str
) -> None:
    """Lokalizatsiya (opt-in): user reelini har target tilga HeyGen Video Translation bilan lip-sync
    dublyaj qilib EDL.lang_variants'ga 1:1 til-variant qo'shadi. STUDIO base VIDEO'ni shu tilga
    almashtiradi (pickLangVariant). FAIL-SOFT; ENABLE_VIDEO_TRANSLATE + HEYGEN_API_KEY + til ro'yxati
    bilan gated. dynamic_duration=False — davomiylik saqlanadi, two-timebase (offset-jadval) buzilmaydi."""
    s = get_settings()
    langs = [c.strip().lower() for c in target_langs if c and c.strip()]
    if not langs:  # meta bermasa — config default til ro'yxati (VIDEO_TRANSLATE_LANGS)
        langs = [c.strip().lower() for c in s.video_translate_langs.split(",") if c.strip()]
    if not (langs and s.enable_video_translate and s.heygen_api_key):
        return
    with contextlib.suppress(Exception):
        src_url = upload_file(normalized)  # decor naqshi: normalized → public URL (fal CDN)
        if not src_url:
            return
        for lang in langs:
            name = _HEYGEN_LANG_NAMES.get(lang, lang.capitalize())
            translated = translate_video(src_url, name, dynamic_duration=False, label=f"translate:{lang}")
            if not translated:
                continue
            variant = LangVariant(
                lang=lang,
                asset=AssetRef(
                    asset_id=f"translate:{lang}:{task_id}",
                    url=translated,
                    kind="video",
                    duration_sec=edl.source.duration_sec,
                    w=edl.source.w,
                    h=edl.source.h,
                    fps=edl.source.fps,
                ),
                aligned_to_source=True,
                lip_sync="precision",
            )
            # Ekran-subtitrlarini ham shu tilga tarjima qilamiz (oyna-darajada, vaqt asl span'da).
            # FAIL-SOFT: tarjima bo'lmasa captions=None → STUDIO asl tildagi subtitrlarni saqlaydi.
            with contextlib.suppress(Exception):
                windows = edl.captions.windows
                if windows:
                    lines = [" ".join(x.text for x in w.words).strip() for w in windows]
                    translated_lines = _translate_caption_lines(lines, name)
                    if translated_lines != lines:
                        variant.captions = edl.captions.model_copy(
                            update={"windows": _redistribute_caption_windows(windows, translated_lines)}
                        )
            edl.lang_variants.append(variant)


def compile_and_render(
    upload_path: str,
    script_timeline: list[object],
    *,
    task_id: str,
    tenant_id: str,
    upload_key: str,
    work_dir: str,
    caption_spec: dict[str, Any] | None = None,
    hook_text: str | None = None,
    shot_list: list[object] | None = None,
    broll_plan: list[object] | None = None,
    shot_src_times: list[float] | None = None,
    drop_src_ranges: list[tuple[float, float]] | None = None,
    effect_intents: list[EffectIntent] | None = None,
    inpaint_remove: str | None = None,
    decor_prompt: str | None = None,
    translate_langs: list[str] | None = None,
    music_hint: str | None = None,
    face_zone: str | None = None,
) -> tuple[EDL | None, RenderResult]:
    """Full deterministic spine: normalize -> EDL -> coverage gate -> B-roll -> render.
    Returns (edl, result). On a coverage-gate failure edl is None and
    result.error carries the user-facing 're-record' message."""
    os.makedirs(work_dir, exist_ok=True)
    normalized = os.path.join(work_dir, "normalized.mp4")
    with ENCODE_GATE:  # heavy libx264 encode — one at a time (F4b: gated here, not in the worker)
        normalize_clip(upload_path, normalized)

    # ONE cached Whisper call gives BOTH the caption cadence (word END times) and the full transcript
    # the Stage-9b semantic stumble-cut aligns to the script. Cached by upload identity so a
    # remontage / A-B-aspect re-render reuses it. Degrade-safe → None → proportional captions, no cut.
    # MONTAGE_SEMANTIC_CUT=0 disables the stumble-cut (kill switch) without touching captions.
    transcript = transcribe_words(normalized, cache_key=upload_key)
    word_src = word_times(normalized, cache_key=upload_key)
    semantic_cut = os.getenv("MONTAGE_SEMANTIC_CUT", "1").strip().lower() not in ("0", "false", "no")

    edl = build_edl(
        normalized, upload_key, script_timeline,
        task_id=task_id, tenant_id=tenant_id, caption_spec=caption_spec,
        # transcript ALWAYS feeds captions (real spoken words, synced); the semantic stumble-cut +
        # footage reject are the only things gated by the kill switch.
        word_src_times=word_src, transcript=transcript,
        drop_src_ranges=drop_src_ranges if semantic_cut else None,
        enable_semantic_cut=semantic_cut,
        shot_list=shot_list, shot_src_times=shot_src_times,
        effect_intents=effect_intents,
    )
    if face_zone in ("top", "center", "bottom"):
        edl.face_zone = face_zone  # vision fact -> rides the EDL into BOTH render engines
    ok, reason = coverage_ok(edl, script_timeline)
    if not ok:
        log.info("montage.coverage_gate_failed", reason=reason)
        return None, RenderResult(False, None, 0.0, 0, degrade_level=-1, error=reason)

    # Faza D: opt-in element removal → a cleaned SOURCE-aligned variant for the STUDIO base swap.
    _maybe_add_inpaint_variant(edl, normalized, inpaint_remove, task_id=task_id)
    # Faza C: opt-in scenario-matched decor → a composited source_variant for the STUDIO base swap.
    _maybe_add_decor_background(edl, normalized, decor_prompt, task_id=task_id, work_dir=work_dir)
    # Lokalizatsiya: opt-in HeyGen Video Translation → 1:1 til-variantlari (lip-sync, 9:16 saqlanadi).
    _maybe_add_translate_variants(edl, normalized, translate_langs or [], task_id=task_id)

    # Faza 3: fill storyboard shots the user's footage doesn't cover with stock B-roll — searches
    # Pexels + downloads into work_dir + populates edl.broll (overlay, duration-preserving, so the
    # offset table is untouched). Additive + fail-soft: any failure leaves edl.broll empty.
    if broll_plan:
        with contextlib.suppress(Exception):
            resolve_broll(edl, broll_plan, work_dir)

    if hook_text:
        edl.hook.hook_text = hook_text
    ass_path = os.path.join(work_dir, "captions.ass")
    # Honor the EDL's hook.display_dur (was a dead field — render_ass always used its 2.5s default),
    # clamped so the hook can't cover more than half of a short montage.
    edl.hook.display_dur = _hook_display_dur(edl)  # content-aware: through the ~2.5s opening
    _hook_dur = min(edl.hook.display_dur, edl.output_duration() * 0.5)
    render_ass(
        edl.captions, ass_path, hook_text=edl.hook.hook_text or None,
        overlays=edl.overlays, hook_dur=_hook_dur, face_zone=edl.face_zone,
    )
    # Stage 9c: with no CC0 track bundled, optionally generate a fal.ai background track
    # (opt-in MONTAGE_MUSIC_GEN, fail-soft) so the montage isn't silent. Gen ONCE here —
    # not per degrade-ladder attempt — using the same pacing energy the bedding uses.
    if not edl.audio.music_path and not available_tracks():
        _md = sum((c.src_end - c.src_start) for c in edl.cuts) or edl.source.duration_sec or 1.0
        _e = max(0.0, min(1.0, (len(edl.cuts) / _md) / 0.8))
        edl.audio.music_path = gen_music_track(
            energy=_e, duration_sec=edl.output_duration(), work_dir=work_dir, style_hint=music_hint
        )
    out_path = os.path.join(work_dir, "montage.mp4")
    # MONTAGE-PRO F1: cloud-first render (Shotstack) — offloads the CPU-only host (the
    # 10k-customer scale path). ANY cloud failure falls back to the local ladder below,
    # so a render always completes. A CAPTIONS-ONLY ASS (no hook/overlays — those stay Shotstack
    # text/cards) is burned locally onto the cloud render so the primary reel gets word-by-word
    # karaoke, which Shotstack's static caption asset can't do.
    if shotstack_enabled():
        caption_ass = os.path.join(work_dir, "captions_only.ass")
        render_ass(edl.captions, caption_ass, hook_text=None, overlays=None, face_zone=edl.face_zone)
        with contextlib.suppress(Exception):
            if render_via_shotstack(edl, normalized, work_dir, out_path, caption_ass=caption_ass):
                log.info("montage.compiled_cloud", engine="shotstack", cuts=len(edl.cuts))
                return edl, RenderResult(
                    True, out_path, edl.output_duration(), os.path.getsize(out_path),
                    degrade_level=0, engine="shotstack",
                )
        log.warning("montage.cloud_render_fell_back")
    with ENCODE_GATE:  # local ffmpeg ladder — the other heavy encode
        result = render_edl(edl, normalized, ass_path, out_path)
    log.info(
        "montage.compiled",
        cuts=len(edl.cuts),
        out_dur=round(edl.output_duration(), 2),
        degrade=result.degrade_level,
        ok=result.ok,
    )
    return edl, result


def _safe_broll_asset(asset_url: str | None) -> bool:
    """A hand-edited EDL must NOT feed an arbitrary local path to ffmpeg `-i`
    (that turns the manual-refine endpoint into a server-local file probe across
    the trust boundary). Allow only: empty/None (b-roll just won't render), an
    http(s) URL (harmless — _renderable_broll's os.path.exists check drops it),
    or a path that resolves to somewhere UNDER the system temp dir, which is where
    the auto-flow downloads b-roll (broll.py joins onto a tempfile work_dir).
    realpath collapses any `..` traversal before the prefix check."""
    if not asset_url:
        return True
    if asset_url.startswith(("http://", "https://")):
        return True
    real = os.path.realpath(asset_url)
    tmp_root = os.path.realpath(tempfile.gettempdir())
    return real == tmp_root or real.startswith(tmp_root + os.sep)


def validate_inbound_edl(edl: EDL) -> tuple[bool, str]:
    """Trust boundary for a hand-edited EDL POSTed from the web — it's now
    untrusted ffmpeg-filtergraph input. Reject too-short output, out-of-bounds
    OUTPUT atSecs, and any value outside the compiler's closed allowlists."""
    if edl.output_duration() < _MIN_OUTPUT_SEC:
        return False, "Montaj juda qisqa bo'lib qoldi — kamida 3 soniya kerak."
    for m in edl.motion:
        if not edl.validate_output_atsec(m.at_sec) or m.op not in _MOTION_OPS:
            return False, "Noto'g'ri harakat (motion) qiymati."
    for t in edl.transitions:
        if not edl.validate_output_atsec(t.at_sec):
            return False, "Noto'g'ri o'tish (transition) vaqti."
    for o in edl.overlays:
        if not edl.validate_output_atsec(o.at_sec):
            return False, "Noto'g'ri overlay vaqti."
    # shot_index is a storyboard pointer (shotList[].i, 1-indexed; 0 = unassigned). We
    # can't upper-bound it here (the EDL doesn't carry the shotList), but a negative
    # index is always malformed — reject it at the trust boundary.
    if any(c.shot_index < 0 for c in edl.cuts) or any(b.shot_index < 0 for b in edl.broll):
        return False, "Noto'g'ri kadr (shot) indeksi."
    # SOURCE-time cut bounds: a hand-edited EDL can carry src_end past the clip length (or an
    # inverted range). ffmpeg would silently clamp → a montage shorter/different than the user
    # assembled. src_start<src_end and src_start>=0 are always required; the upper bound only
    # when source.duration_sec is known (>0; 0 = unprobed). Tolerance covers CFR/VFR rounding.
    src_dur = edl.source.duration_sec
    for c in edl.cuts:
        if not (c.src_start >= 0 and c.src_start < c.src_end):
            return False, "Noto'g'ri kesim chegarasi (boshlanish/tugash vaqti)."
        if src_dur > 0 and c.src_end > src_dur + 0.5:
            return False, "Kesim manba video uzunligidan oshib ketdi."
    for b in edl.broll:
        if b.at_sec is not None and not edl.validate_output_atsec(b.at_sec):
            return False, "Noto'g'ri B-roll vaqti."
        if b.placement not in ("overlay", "segment"):
            return False, "Noto'g'ri B-roll joylashuvi."
        if not _safe_broll_asset(b.asset_url):
            return False, "Noto'g'ri B-roll manba havolasi."
    return True, ""


def render_from_edl(upload_path: str, edl: EDL, work_dir: str) -> RenderResult:
    """Render a SUPPLIED EDL (e.g. hand-edited in the Studio) — normalize the
    upload deterministically, burn the EDL's captions, run the ffmpeg spine.
    NO planning agents, NO LLM. The manual-refine render path."""
    os.makedirs(work_dir, exist_ok=True)
    normalized = os.path.join(work_dir, "normalized.mp4")
    with ENCODE_GATE:  # heavy libx264 encode — one at a time (F4b: gated here, not in the worker)
        normalize_clip(upload_path, normalized)
    ass_path = os.path.join(work_dir, "captions.ass")
    edl.hook.display_dur = _hook_display_dur(edl)  # content-aware: through the ~2.5s opening
    _hook_dur = min(edl.hook.display_dur, edl.output_duration() * 0.5)
    render_ass(
        edl.captions, ass_path, hook_text=edl.hook.hook_text or None,
        overlays=edl.overlays, hook_dur=_hook_dur, face_zone=edl.face_zone,
    )
    # Stage 9c: same opt-in fal.ai music-gen fallback as the auto path — a manual
    # re-montage with no chosen/bundled track isn't left silent (fail-soft, default off).
    if not edl.audio.music_path and not available_tracks():
        _md = sum((c.src_end - c.src_start) for c in edl.cuts) or edl.source.duration_sec or 1.0
        _e = max(0.0, min(1.0, (len(edl.cuts) / _md) / 0.8))
        edl.audio.music_path = gen_music_track(
            energy=_e, duration_sec=edl.output_duration(), work_dir=work_dir
        )
    out_path = os.path.join(work_dir, "montage.mp4")
    # MONTAGE-PRO F1: cloud-first render for MANUAL (studio-save) EDLs too — same fail-soft +
    # local karaoke burn.
    if shotstack_enabled():
        caption_ass = os.path.join(work_dir, "captions_only.ass")
        render_ass(edl.captions, caption_ass, hook_text=None, overlays=None, face_zone=edl.face_zone)
        with contextlib.suppress(Exception):
            if render_via_shotstack(edl, normalized, work_dir, out_path, caption_ass=caption_ass):
                log.info("montage.compiled_cloud", engine="shotstack", cuts=len(edl.cuts))
                return RenderResult(
                    True, out_path, edl.output_duration(), os.path.getsize(out_path),
                    degrade_level=0, engine="shotstack",
                )
        log.warning("montage.cloud_render_fell_back")
    with ENCODE_GATE:  # local ffmpeg ladder — the other heavy encode
        result = render_edl(edl, normalized, ass_path, out_path)
    log.info("montage.manual_render", cuts=len(edl.cuts), degrade=result.degrade_level, ok=result.ok)
    return result

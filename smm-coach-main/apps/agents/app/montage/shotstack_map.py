"""EDL → Shotstack edit JSON mapper + cloud-render orchestration (MONTAGE-PRO F1).

The EDL stays the single source of truth (locked decision): cuts, caption word-times, overlays,
transitions, music — all decided in-house. This module only TRANSLATES that EDL into Shotstack's
declarative timeline and hands the heavy ffmpeg work to their cloud (offloads the CPU-only host —
the 10k-customer scale path). Pure builders (`srt_from_captions`, `build_edit`) are unit-testable;
`render_via_shotstack` does the asset publishing (fal CDN) + submit/poll/download and is FAIL-SOFT:
False → the caller renders on the local ladder instead.

Mapping notes:
- track order: first track = TOP layer (captions above overlays above b-roll above the base video);
- each EDL cut → one video clip (`trim` = SOURCE start, `start` = OUTPUT position) — the same
  two-timebase contract the local compiler uses;
- ken-burns → alternating zoomIn/zoomOut clip effects; EDL transitions → fade in/out on the clips
  flanking that boundary;
- captions → Shotstack `caption` asset fed our SRT (built from EDL word windows) — language-agnostic
  (Uzbek included), karaoke-styled with the caption accent color.
"""
from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from app.montage import shotstack_client
from app.montage.audio import build_voice_chain
from app.montage.fal_client import upload_file
from app.montage.probe import run_ff
from app.montage.sfx import sfx_graph

if TYPE_CHECKING:
    from app.montage.edl import EDL, Captions

log = structlog.get_logger(__name__)

_W, _H, _FPS = 1080, 1920, 30


def _ts(sec: float) -> str:
    """Seconds → SRT timestamp HH:MM:SS,mmm (PURE)."""
    ms = max(0, int(round(sec * 1000)))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt_from_captions(captions: Captions) -> str:
    """EDL caption windows (OUTPUT-timed karaoke words) → SRT text, one cue per window (PURE).
    Empty windows → '' (caller then skips the caption track)."""
    cues: list[str] = []
    n = 0
    for win in captions.windows:
        words = [w for w in win.words if w.text.strip()]
        if not words:
            continue
        start = min(w.start for w in words)
        end = max(w.end for w in words)
        if end <= start:
            end = start + 0.4
        n += 1
        text = " ".join(w.text for w in words)
        cues.append(f"{n}\n{_ts(start)} --> {_ts(end)}\n{text}\n")
    return "\n".join(cues)



# Face-aware element placement: put every text/card layer in the zone the face is NOT in.
# Default (unknown face zone) assumes the typical talking-head framing — face top/center —
# so titles hug the very top edge and captions the very bottom edge, the two strips a face
# almost never occupies. offset.y > 0 moves UP in Shotstack.
# COORDINATED with the burned-caption band (captions.py _FACE_LAYOUT): the karaoke caption is
# hard-burned by _finish, so these Shotstack hook/overlay/card rows must NOT share its band or
# text lands on text. Caption sits at ~0.78 (face top/center) or ~0.16 (face bottom); these rows
# keep a clear gap from it AND stay off the face. (_layouts_clear_of_captions() locks the gap.)
_LAYOUTS: dict[str, dict[str, tuple[str, float]]] = {
    "top": {  # face fills the upper half; caption at the bottom → text/cards in the safe MIDDLE
        "hook": ("bottom", 0.50),     # ~0.50 from top
        "overlay": ("bottom", 0.46),  # ~0.54 from top — below the face, above the caption
        "card": ("bottom", 0.48),     # ~0.52 from top
    },
    "center": {  # close-up; caption at the bottom → text/cards hug the top edge (face leaves it free)
        "hook": ("top", -0.05),
        "overlay": ("top", -0.10),
        "card": ("top", -0.15),
    },
    "bottom": {  # face at the bottom; caption at the TOP → hook above it, overlay/card in the middle
        "hook": ("top", -0.02),       # ~0.02 from top, above the caption band (~0.16)
        "overlay": ("top", -0.34),    # ~0.34 from top — below the caption, above the face
        "card": ("top", -0.42),
    },
}

# The caption asset ignores clip position — its vertical anchor is margin.top, a FRACTION
# of the frame height where the caption block starts. Face-avoidance AND platform-safe:
# the montage playbook's 9:16 caption safe-band is [0.55, 0.78] — below 0.78 is the platform
# UI dead-zone (Instagram/TikTok paint their OWN caption/username/buttons there), so a caption
# hugging the extreme bottom (0.88) collides with the app UI once posted. Keep it in-band.
_CAPTION_MARGIN_TOP: dict[str, float] = {
    "top": 0.72,  # face above → captions at the bottom of the SAFE band (not the UI dead-zone)
    "center": 0.72,  # close-up → same safe lower-third, clear of the platform UI
    "bottom": 0.16,  # face below → captions up top, just clear of the top dead-zone (~0.13)
}


def _caption_margin_top(face_zone: str | None) -> float:
    return _CAPTION_MARGIN_TOP.get((face_zone or "").strip().lower(), _CAPTION_MARGIN_TOP["center"])


def _layout(face_zone: str | None) -> dict[str, tuple[str, float]]:
    """Element → (position, offset.y). Unknown/None face_zone → the 'center' (edge-hugging)
    layout — the safest default for talking-head reels."""
    return _LAYOUTS.get((face_zone or "").strip().lower(), _LAYOUTS["center"])


def _hex_accent(edl: EDL) -> str:
    """EDL caption active color (ASS &H00BBGGRR) → #RRGGBB for Shotstack (PURE)."""
    raw = (edl.captions.style.active or "").strip().lstrip("&H")
    if len(raw) == 8:
        b, g, r = raw[2:4], raw[4:6], raw[6:8]
        return f"#{r}{g}{b}"
    return "#FFD700"


def build_edit(
    edl: EDL,
    source_url: str,
    *,
    srt_url: str | None = None,
    music_url: str | None = None,
    broll_urls: dict[int, str] | None = None,
    card_urls: dict[int, str] | None = None,
) -> dict[str, Any]:
    """EDL + published asset URLs → a complete Shotstack edit JSON (PURE/testable)."""
    out_dur = round(edl.output_duration(), 3)
    lay = _layout(edl.face_zone)
    # boundary index -> Shotstack transition name, honoring the DIRECTOR'S planned type
    # (content-matched: calm->fade, energy->zoom, topic shift->slide/wipe). Unknown -> zoom.
    _type_map = {"fade": "fade", "dissolve": "fade", "xfade": "fade", "crossfade": "fade",
                 "zoom": "zoom", "glitch": "zoom", "slide": "slideLeft", "slideleft": "slideLeft",
                 "slideup": "slideUp", "wipe": "wipeRight", "wiperight": "wipeRight"}
    tr_bounds: dict[int, str] = {}
    if edl.transitions:
        acc = 0.0
        bounds = []
        for c in edl.cuts[:-1]:
            acc += max(0.0, c.src_end - c.src_start)
            bounds.append(acc)
        for tr in edl.transitions:
            for bi, bound in enumerate(bounds):
                if abs(bound - tr.at_sec) <= 0.35:
                    tr_bounds[bi] = _type_map.get((tr.type or "").strip().lower(), "zoom")

    # Planned emphasis punches (from the director / motion planner): a cut whose OUTPUT window
    # contains a zoom_punch gets a STRONGER push (a talking-head emphasis beat), instead of the
    # blind positional cycle that ignored edl.motion entirely.
    punch_ats = [m.at_sec for m in edl.motion if (getattr(m, "op", "") or "").strip() == "zoom_punch"]

    # Base video track: one clip per cut, SOURCE trim → OUTPUT start; ken-burns via zoom effects.
    clips: list[dict[str, Any]] = []
    t = 0.0
    for i, c in enumerate(edl.cuts):
        dur = round(max(0.05, c.src_end - c.src_start), 3)
        # Emphasis: a planned punch inside this cut's OUTPUT window → a pronounced zoomIn push;
        # otherwise a GENTLE alternating push/pull ken-burns. (Slides were dropped — a slideLeft
        # on a talking head slides the speaker sideways, which reads as a jarring glitch.)
        has_punch = any(t <= pa < t + dur for pa in punch_ats)
        effect = "zoomIn" if has_punch else ("zoomInSlow", "zoomOutSlow")[i % 2]
        clip: dict[str, Any] = {
            "asset": {"type": "video", "src": source_url, "trim": round(c.src_start, 3), "volume": 1},
            "start": round(t, 3),
            "length": dur,
            "fit": "crop",
            "effect": effect,
        }
        transition: dict[str, str] = {}
        if (i - 1) in tr_bounds:
            transition["in"] = tr_bounds[i - 1]
        if i in tr_bounds:
            transition["out"] = tr_bounds[i]
        if transition:
            clip["transition"] = transition
        clips.append(clip)
        t += dur

    tracks: list[dict[str, Any]] = []

    # 1) captions (top) — karaoke-styled from OUR word timings; language-agnostic via SRT.
    if srt_url:
        tracks.append({
            "clips": [{
                "asset": {
                    # Plain "caption" — the true per-cue subtitle renderer. PROBED LIVE
                    # (2026-07-03, frames inspected): rich-caption merges ALL SRT cues into ONE
                    # center-screen paragraph and ignores clip position AND font — it rendered the
                    # whole transcript across the speaker's face. caption shows cue-by-cue,
                    # honors font/background, and is placed via margin.top (fraction of height).
                    "type": "caption",
                    "src": srt_url,
                    "font": {"family": "Montserrat ExtraBold", "size": 42, "color": "#FFFFFF"},
                    "background": {"color": "#000000", "opacity": 0.55, "padding": 14,
                                   "borderRadius": 10},
                    "margin": {"top": _caption_margin_top(edl.face_zone)},
                },
                "start": 0,
                "length": out_dur,
            }]
        })

    # 2) hook title + planned on-screen overlays.
    text_clips: list[dict[str, Any]] = []
    hook = (edl.hook.hook_text or "").strip()
    if hook:
        text_clips.append({
            "asset": {"type": "text", "text": hook[:90],
                      "font": {"family": "Montserrat ExtraBold", "size": 44, "color": _hex_accent(edl)},
                      "alignment": {"horizontal": "center"},
                      "stroke": {"color": "#000000", "width": 2}},
            "start": 0, "length": round(min(edl.hook.display_dur, out_dur / 2), 3),
            "position": lay["hook"][0], "offset": {"y": lay["hook"][1]},
            "transition": {"in": "zoom", "out": "fade"},
        })
    for ov in edl.overlays:
        txt = (ov.text or "").strip()
        if not txt or ov.at_sec >= out_dur:
            continue
        text_clips.append({
            "asset": {"type": "text", "text": txt[:80],
                      "font": {"family": "Montserrat ExtraBold", "size": 32, "color": ov.color or "#FFFFFF"},
                      "alignment": {"horizontal": "center"},
                      "stroke": {"color": "#000000", "width": 2}},
            "start": round(max(0.0, ov.at_sec), 3),
            "length": round(max(0.4, min(ov.dur, out_dur - ov.at_sec)), 3),
            "position": lay["overlay"][0], "offset": {"y": lay["overlay"][1]},
            "transition": {"in": "slideUp", "out": "fade"},
        })
    if text_clips:
        tracks.append({"clips": text_clips})

    # 2b) F3 generative cards — Soul graphics UNDER the overlay text (text stays crisp on top).
    card_clips: list[dict[str, Any]] = []
    for idx, ov in enumerate(edl.overlays):
        url = (card_urls or {}).get(idx)
        if not url or ov.at_sec >= out_dur:
            continue
        card_clips.append({
            "asset": {"type": "image", "src": url},
            "start": round(max(0.0, ov.at_sec), 3),
            "length": round(max(0.4, min(ov.dur, out_dur - ov.at_sec)), 3),
            "fit": "none",
            "scale": 0.55,
            "position": lay["card"][0],
            "offset": {"y": lay["card"][1]},
            "transition": {"in": "slideUp", "out": "fade"},
        })
    if card_clips:
        tracks.append({"clips": card_clips})

    # 3) b-roll cutaways over their OUTPUT windows.
    broll_clips: list[dict[str, Any]] = []
    _bk = 0
    for br in edl.broll:
        url = (broll_urls or {}).get(br.shot_index)
        if not url or br.at_sec is None or br.output_dur_sec is None:
            continue
        broll_clips.append({
            "asset": {"type": "video", "src": url, "volume": 0},
            "start": round(max(0.0, br.at_sec), 3),
            "length": round(max(0.4, br.output_dur_sec), 3),
            "fit": "crop",
            # alternate push/pull so consecutive cutaways don't all drift the same way (the
            # 'canned slideshow' feel the playbook warns about).
            "effect": ("zoomInSlow", "zoomOutSlow")[_bk % 2],
            "transition": {"in": "zoom", "out": "fade"},
        })
        _bk += 1
    if broll_clips:
        tracks.append({"clips": broll_clips})

    # 4) base video.
    tracks.append({"clips": clips})

    # 5) music bed (bottom) — quiet under the voice (the voice rides in the base clips).
    if music_url:
        tracks.append({
            "clips": [{
                "asset": {"type": "audio", "src": music_url, "volume": 0.15, "effect": "fadeOut"},
                "start": 0, "length": out_dur,
            }]
        })

    return {
        "timeline": {"background": "#000000", "tracks": tracks},
        # quality:high → Shotstack targets a high-bitrate 1080p master. Omitting it defaults to
        # "medium" (visibly lower bitrate); since Instagram re-compresses on upload, a medium
        # master double-compresses into macroblocking. A master should be encoded generously.
        "output": {"format": "mp4", "fps": _FPS, "size": {"width": _W, "height": _H}, "quality": "high"},
    }


def _finish(
    raw_path: str, edl: EDL, work_dir: str, out_path: str, caption_ass: str | None = None
) -> bool:
    """Post-Shotstack polish Shotstack can't do. The Shotstack render is already OUTPUT-timed,
    so everything lines up 1:1. FAIL-SOFT → False keeps the raw render.

    AUDIO (always): denoise + de-ess the voice, sidechain-DUCK the music under it, layer the SFX
    accents, loudnorm the mix to the -14 LUFS target. (Shotstack renders VOICE-ONLY — music is
    dropped from build_edit — because a true sidechain duck needs the dry voice as the compressor
    key, which the cloud can't provide.)

    VIDEO: when `caption_ass` is given, burn the per-word KARAOKE ASS on top (word-by-word
    highlight + emphasis + the stylist's font/size/accent — Shotstack's caption asset can only do
    static blocks). Burning AFTER the cloud render means the captions sit FIXED over the moving
    video (they don't ride Shotstack's zoom/slide). Re-encodes the video (gated); otherwise the
    Shotstack video is copied (cheap).
    """
    try:
        ln = edl.audio.loudnorm
        inputs = ["-i", raw_path]
        parts: list[str] = []
        music = edl.audio.music_path
        if music and os.path.exists(music):
            inputs += ["-i", music]
            # voice cleaned then split: one copy mixes, one keys the sidechain so the bed ducks
            # whenever the speaker talks; loudnorm the final mix to target.
            d = edl.audio.duck
            parts.append("[0:a]afftdn=nf=-25,deesser,asplit=2[v1][v2]")
            parts.append(f"[1:a]volume={d.volume}[mlow]")
            parts.append(
                f"[mlow][v2]sidechaincompress=threshold={d.threshold}:ratio={d.ratio}"
                f":attack={d.attack}:release={d.release}[mduck]"
            )
            parts.append(
                f"[v1][mduck]amix=inputs=2:duration=first:dropout_transition=0,"
                f"loudnorm=I={ln.i}:TP={ln.tp}:LRA={ln.lra}[aout]"
            )
            sfx_first = 2
        else:
            parts.append(f"[0:a]{build_voice_chain(edl.audio)}[aout]")
            sfx_first = 1
        sfx_in, sfx_parts = sfx_graph(edl.audio.sfx, work_dir, sfx_first)
        amap = "[aout]"
        if sfx_parts:
            parts.extend(sfx_parts)
            parts.append("[aout][sfxall]amix=inputs=2:duration=first:normalize=0[afin]")
            amap = "[afin]"

        burn = bool(caption_ass and os.path.exists(caption_ass))
        if burn:
            # ffmpeg's ass filter can't take a bare Windows drive path, but in-container paths are
            # POSIX (/tmp/...) so no escaping needed.
            parts.append(f"[0:v]ass={caption_ass}:fontsdir=/usr/share/fonts[vout]")
            vmap = "[vout]"
            venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        else:
            vmap = "0:v"
            venc = ["-c:v", "copy"]
        cmd = [
            "ffmpeg", "-y", *inputs, *sfx_in,
            "-filter_complex", ";".join(parts),
            "-map", vmap, "-map", amap,
            *venc, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            out_path,
        ]
        if burn:
            # A caption burn re-encodes 1080p video — serialize like the local ladder so
            # concurrent renders on the media plane don't thrash the CPU. Lazy import: the
            # compiler imports this module, so importing it at top level would cycle.
            from app.montage.compiler import ENCODE_GATE

            with ENCODE_GATE:
                run_ff(cmd)
        else:
            run_ff(cmd)  # audio-only + video copy — cheap, no gate needed
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception as exc:  # noqa: BLE001 — never let the polish pass fail the render
        log.warning("shotstack.finish_failed", error=str(exc)[:160])
        return False


def render_via_shotstack(
    edl: EDL, normalized_path: str, work_dir: str, out_path: str, caption_ass: str | None = None
) -> bool:
    """Publish assets → build edit → cloud render → local finish → out_path. FAIL-SOFT
    (False → the caller falls back to the local ffmpeg ladder).

    When `caption_ass` is given, the cloud renders WITHOUT captions and the per-word karaoke ASS
    is burned locally in _finish (Shotstack's caption asset can only do static blocks). Without
    it, the static SRT caption asset is used (the legacy path)."""
    if not shotstack_client.shotstack_enabled():
        return False
    source_url = upload_file(normalized_path)
    if not source_url:
        log.warning("shotstack.source_upload_failed")
        return False

    srt_url: str | None = None
    # When we burn karaoke ASS locally, do NOT also ship the static SRT to Shotstack (would
    # double-render captions). Only build the SRT for the legacy no-ASS path.
    if not caption_ass:
        srt_text = srt_from_captions(edl.captions)
        if srt_text:
            srt_path = os.path.join(work_dir, "captions.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_text)
            srt_url = upload_file(srt_path)

    broll_urls: dict[int, str] = {}
    for br in edl.broll:
        a = br.asset_url or ""
        if a.startswith("http"):
            broll_urls[br.shot_index] = a
        elif a and os.path.exists(a):
            u = upload_file(a)
            if u:
                broll_urls[br.shot_index] = u

    # F3: generative visual cards (Higgsfield Soul) behind stat callouts — fail-soft, capped.
    from app.montage.visual_cards import generate_overlay_cards

    card_urls = generate_overlay_cards(edl)
    # music_url=None: the bed is mixed+ducked locally in _finish_audio (Shotstack can't sidechain),
    # so the cloud renders voice-only.
    edit = build_edit(edl, source_url, srt_url=srt_url, music_url=None,
                      broll_urls=broll_urls, card_urls=card_urls)
    url = shotstack_client.render(edit)
    if not url:
        return False
    raw_path = os.path.join(work_dir, "shotstack_raw.mp4")
    try:
        with httpx.Client(timeout=300.0, follow_redirects=True) as client:
            r = client.get(url)
            if r.status_code >= 400:
                return False
            with open(raw_path, "wb") as f:
                f.write(r.content)
    except Exception as exc:  # noqa: BLE001 — fall back to the local ladder
        log.warning("shotstack.download_failed", error=str(exc)[:160])
        return False
    if not (os.path.exists(raw_path) and os.path.getsize(raw_path) > 0):
        return False
    log.info("shotstack.render_done", size=os.path.getsize(raw_path))
    # Local finish: audio (denoise + duck + SFX + LUFS) + optional karaoke burn.
    if _finish(raw_path, edl, work_dir, out_path, caption_ass=caption_ass):
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    # _finish FAILED. When karaoke ASS was requested, the cloud render has ZERO captions (captions
    # are burned ONLY in _finish for the ASS path — the cloud renders voice-only, caption-less), so
    # moving the raw file would silently deliver an UNCAPTIONED, unpolished reel that the compiler
    # records as degrade=0/'good' — the exact class of regression the montage must never ship.
    # Fail instead → compile_and_render falls through to the local ffmpeg ladder, which burns the
    # captions from the same EDL (a captioned reel beats a caption-less one). Only when NO ASS was
    # requested (legacy SRT path — the cloud already baked static captions in) is the raw render an
    # acceptable audio-unpolished fallback worth keeping.
    if caption_ass and os.path.exists(caption_ass):
        log.warning("shotstack.finish_failed_uncaptioned_fallback_local")
        return False
    shutil.move(raw_path, out_path)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0

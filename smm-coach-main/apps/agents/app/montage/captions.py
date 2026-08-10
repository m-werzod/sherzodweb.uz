"""Render the EDL captions into a burnable .ass subtitle file.

Two tiers:
  * premium — per-word karaoke (\\kf sweep): each word fills with the accent
    colour as it's "spoken", the iconic Submagic / captions.ai look. Uses the
    per-word proportional times build_caption_windows already computes (no extra
    alignment data needed; honest best-effort sync on Uzbek).
  * cheap — the whole window shown at once (the safe fallback / low-energy look).

Every on-screen string runs through the Uzbek apostrophe normalizer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.montage.text_norm import ass_escape, normalize_caption_text

if TYPE_CHECKING:
    from app.montage.edl import Captions, CaptionStyle, CaptionWindow, Overlay

# Face-aware vertical layout (mirrors shotstack_map._LAYOUTS): per face zone —
# (cap_align, cap_marginV, hook_an, hook_marginV, over_an, over_marginV).
# ASS numpad: 2=bottom-center, 8=top-center; MarginV is measured from the anchored edge
# (PlayResY 1920). Platform-safe per the montage playbook: the bottom ~420px (0.219) and
# top ~250px (0.13) are the app UI dead-zones (Instagram/TikTok paint their own overlays
# there), so a bottom-anchored element needs MarginV >= ~420 and a top-anchored one >= ~260
# to clear the app chrome once posted. Unknown/None zone → "center".
_FACE_LAYOUT = {
    "top": (2, 430, 2, 500, 2, 440),  # face up → all elements low, clear of the bottom UI
    "center": (2, 430, 8, 280, 8, 320),  # close-up → captions low, hook/overlay high, both safe
    "bottom": (8, 300, 8, 270, 8, 360),  # face down → all elements up, clear of the top UI
}

def _ass_time(seconds: float) -> str:
    """ASS timestamp: H:MM:SS.cc (centiseconds)."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:  # rounding spilled over — propagate the carry up the units
        cs = 0
        s += 1
        if s == 60:
            s = 0
            m += 1
            if m == 60:
                m = 0
                h += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _style_line(st: CaptionStyle, *, premium: bool, alignment: int, margin_v: int) -> str:
    # Karaoke needs PrimaryColour = the swept-to (active) colour and
    # SecondaryColour = the not-yet-spoken base; window tier just shows white.
    # alignment/margin_v come from the face-zone layout, NOT the stylist's blind default.
    primary = st.active if premium else st.primary
    secondary = st.primary
    return (
        f"Style: Cap,{st.font},{st.size},{primary},{secondary},"
        f"{st.outline_color},&H64000000,1,0,1,{st.outline},{st.shadow},"
        f"{alignment},{st.margin_lr},{st.margin_lr},{margin_v},1"
    )


def _karaoke_text(win: CaptionWindow) -> str:
    """`{\\kf<cs>}word ` per word — the fill sweeps across the line in sync with
    each word's proportional duration. Emphasis (`pop`) words from the
    caption_stylist agent get a static size bump for punch."""
    parts: list[str] = []
    for w in win.words:
        cs = max(1, int(round((w.end - w.start) * 100)))
        word = ass_escape(normalize_caption_text(w.text))
        tags = f"\\kf{cs}"
        if w.pop:
            tags += "\\fscx118\\fscy118"
        parts.append(f"{{{tags}}}{word} ")
    return "".join(parts).rstrip()


def _over_style_line(font: str) -> str:
    # Mid-size overlay title with a semi-opaque box (BorderStyle 4) so storyboard text is
    # legible over any footage. Default alignment 8; each line overrides it inline via \an.
    return (
        f"Style: Over,{font},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        f"1,0,4,2,1,8,60,60,260,1"
    )


def _hex_to_ass(hex_color: str) -> str:
    """#RRGGBB -> ASS &H00BBGGRR& colour (white on anything malformed)."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return "&H00FFFFFF&"
    try:
        int(h, 16)
    except ValueError:
        return "&H00FFFFFF&"
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _hook_style_line(font: str) -> str:
    # Big top-third hook with an opaque box (BorderStyle 4) for instant
    # readability over any footage. Alignment 8 = top-center, MarginV from top.
    return (
        f"Style: Hook,{font},104,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,"
        f"1,0,4,3,2,8,80,80,420,1"
    )


def render_ass(
    captions: Captions,
    dst_path: str,
    *,
    hook_text: str | None = None,
    hook_dur: float = 2.5,
    overlays: list[Overlay] | None = None,
    face_zone: str | None = None,
) -> str:
    """Write a complete .ass file and return its path. When `hook_text` is given
    it's burned big across the opening seconds (the first-3-second retention
    grab) on its own layer, above the rolling captions. `overlays` are the
    storyboard's planned on-screen titles (EDL.overlays), each OUTPUT-timed."""
    st = captions.style
    premium = captions.tier == "premium"
    play_w, play_h = captions.play_res
    # Face-aware placement: every text layer goes to the zone the face is NOT in.
    cap_align, cap_mv, hook_an, hook_mv, over_an, over_mv = _FACE_LAYOUT.get(
        (face_zone or "").strip().lower(), _FACE_LAYOUT["center"]
    )

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"  # smart-wrap long lines instead of running off-screen
        "ScaledBorderAndShadow: yes\n"
        f"PlayResX: {play_w}\n"
        f"PlayResY: {play_h}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{_style_line(st, premium=premium, alignment=cap_align, margin_v=cap_mv)}\n"
        f"{_hook_style_line(st.font)}\n"
        f"{_over_style_line(st.font)}\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )

    lines: list[str] = []
    if hook_text:
        hook = ass_escape(normalize_caption_text(hook_text))[:90]
        if hook:
            lines.append(
                f"Dialogue: 1,{_ass_time(0)},{_ass_time(hook_dur)},Hook,,0,0,{hook_mv},,"
                f"{{\\an{hook_an}\\fad(200,250)}}{hook}"
            )
    for ov in overlays or []:
        # Truncate the CLEAN text before escaping so a cut never splits an escape sequence
        # (a dangling '\' would start a stray ASS tag and corrupt the line).
        txt = ass_escape(normalize_caption_text(ov.text)[:88])
        if not txt:
            continue
        # The planner chose ov.position blind to the footage — the face zone overrides
        # the vertical row so a title can never land on the speaker.
        an = over_an
        start = max(0.0, ov.at_sec)
        end = start + max(0.3, ov.dur)
        lines.append(
            f"Dialogue: 1,{_ass_time(start)},{_ass_time(end)},Over,,0,0,{over_mv},,"
            f"{{\\an{an}\\c{_hex_to_ass(ov.color)}\\fad(150,150)}}{txt}"
        )
    for win in captions.windows:
        if not win.words:
            continue
        start = min(w.start for w in win.words)
        end = max(w.end for w in win.words)
        if end <= start:
            end = start + 0.4
        if premium:
            text = _karaoke_text(win)
        else:
            text = ass_escape(normalize_caption_text(" ".join(w.text for w in win.words)))
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Cap,,0,0,0,,{text}"
        )

    with open(dst_path, "w", encoding="utf-8") as fh:
        fh.write(header + "\n".join(lines) + "\n")
    return dst_path

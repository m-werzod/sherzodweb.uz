"""Deterministic camera motion — a gentle Ken Burns push so static talking-head
footage feels edited instead of locked-off.

Implemented as pre-scale + animated CENTERED crop (not zoompan, which jitters on
video): scale the segment up by `zoom`, then crop a region that smoothly shrinks
(push-in) or grows (pull-out) over the segment and scale back to 1080x1920. The
direction alternates per cut so consecutive shots don't feel mechanical.

Later, the camera_dynamics agent will emit per-beat EDL.motion specs (zoom on
emphasis words, face-centered); until then every cut gets this safe default.
"""
from __future__ import annotations


def _even(n: int) -> int:
    return n - (n % 2)


def _ease(p: str, easing: str) -> str:
    """Wrap a 0→1 LINEAR progress expression `p` in an easing curve so a camera move decelerates /
    accelerates instead of crawling at constant speed (palmier Keyframe.swift: smoothstep =
    t*t*(3-2t)). The dead `Motion.easing` field finally drives the render. Unknown / 'linear' →
    returns `p` unchanged (byte-identical, so the default Ken-Burns baseline never regresses)."""
    e = (easing or "").strip().lower()
    if e in ("ease-out", "easeout", "out"):
        return f"({p})*(2-({p}))"  # decelerate — fast start, soft landing (good for a punch)
    if e in ("ease-in", "easein", "in"):
        return f"({p})*({p})"  # accelerate — slow start
    if e in ("ease-in-out", "easeinout", "smooth", "inout"):
        return f"({p})*({p})*(3-2*({p}))"  # smoothstep s-curve
    return p  # linear / unrecognised — unchanged


def ken_burns(duration: float, *, zoom: float = 0.08, zoom_in: bool = True, easing: str = "linear") -> str:
    """ffmpeg video-filter chain for a centered Ken Burns push over `duration`s. `zoom`=0.08 keeps
    the move subtle (≤120% is the legibility ceiling). `easing` defaults to LINEAR so the safe
    default drift is byte-identical to before; a planner can request an eased drift."""
    d = max(0.1, duration)
    z = zoom * min(1.0, d / 0.5)  # gentler zoom on sub-0.5s cuts so it can't snap in a few frames
    sw = _even(round(1080 * (1 + z)))
    sh = _even(round(1920 * (1 + z)))
    dw = sw - 1080
    dh = sh - 1920
    p = _ease(f"min(t/{d:.3f}\\,1)", easing)  # 0→1 progress; comma escaped for the filtergraph
    if zoom_in:
        cw, ch = f"{sw}-{dw}*{p}", f"{sh}-{dh}*{p}"
    else:
        cw, ch = f"1080+{dw}*{p}", f"1920+{dh}*{p}"
    return (
        f"scale={sw}:{sh},"
        f"crop=w='{cw}':h='{ch}':x='(in_w-out_w)/2':y='(in_h-out_h)/2',"
        f"scale=1080:1920,setsar=1"
    )


def zoom_punch(duration: float, *, zoom: float = 0.12, punch: float = 0.35, easing: str = "ease-out") -> str:
    """A fast push-IN that snaps to the zoomed framing over `punch` seconds then HOLDS — the
    energetic 'punch in on the beat' move (vs ken_burns' slow continuous drift). Same proven
    scale+centered-crop technique; the progress curve is faster and `easing` (default ease-out)
    makes it settle softly into the hold instead of stopping dead."""
    d = max(0.1, duration)
    # Keep the punch fast + CONSTANT on normal cuts (a punch is a snappy fixed move, not a
    # duration-scaled drift), but never let it eat more than half a short cut so a hold phase
    # always remains.
    pt = min(punch, d * 0.5)
    z = zoom * min(1.0, d / 0.5)  # gentler zoom on sub-0.5s cuts so it can't snap in a few frames
    sw = _even(round(1080 * (1 + z)))
    sh = _even(round(1920 * (1 + z)))
    dw = sw - 1080
    dh = sh - 1920
    p = _ease(f"min(t/{pt:.3f}\\,1)", easing)  # 0→1 over the punch window, then clamps to 1 (holds)
    cw, ch = f"{sw}-{dw}*{p}", f"{sh}-{dh}*{p}"
    return (
        f"scale={sw}:{sh},"
        f"crop=w='{cw}':h='{ch}':x='(in_w-out_w)/2':y='(in_h-out_h)/2',"
        f"scale=1080:1920,setsar=1"
    )


def shake(duration: float, *, zoom: float = 0.06, amp: float = 0.7, freq: float = 8.0, easing: str = "ease-out") -> str:
    """Camera-shake vfx: scale up by `zoom` to make headroom, then MOVE a 1080x1920 crop on a
    sinusoid (decaying to 0 over the cut so it settles instead of buzzing the whole shot). Same
    scale+crop technique as ken_burns/zoom_punch but the crop POSITION animates, not its size, so
    framing is preserved. Pure string-building — no ffmpeg, unit-testable; mirrors STUDIO's
    drawVisual 'Shake' jitter so preview≈export. The `montage_director` already emits
    Motion(op='shake'); this is the renderer it lacked."""
    d = max(0.1, duration)
    sw = _even(round(1080 * (1 + zoom)))
    sh = _even(round(1920 * (1 + zoom)))
    dw, dh = sw - 1080, sh - 1920
    # Stay strictly inside the scaled margin: max |offset| <= half the headroom.
    ax = max(1, round(dw * amp / 2))
    ay = max(1, round(dh * amp / 2))
    # Decay 1→0 across the cut (eased), so the shake is strongest on the cut-in and settles. No
    # commas in the expression → no filtergraph escaping needed (unlike ken_burns' min()).
    decay = _ease(f"(1-t/{d:.3f})", easing)
    cx = f"(in_w-out_w)/2+{ax}*({decay})*sin(2*PI*{freq:.2f}*t)"
    cy = f"(in_h-out_h)/2+{ay}*({decay})*cos(2*PI*{freq:.2f}*t)"
    return (
        f"scale={sw}:{sh},"
        f"crop=w=1080:h=1920:x='{cx}':y='{cy}',"
        f"setsar=1"
    )


def glitch(duration: float, *, shift: int = 6, noise: int = 14) -> str:
    """Digital-glitch vfx: a static RGB channel split (chromatic aberration) + light temporal
    film noise. Uses only core, widely-available filters (rgbashift, noise) with NO per-frame
    expressions — libx264/CPU-safe so it can't blow the single serial ENCODE_GATE. `duration` is
    accepted for a uniform builder signature (the look is constant over the cut). The
    `montage_director` already emits Motion(op='glitch'); this is the renderer it lacked. STUDIO's
    drawVisual gets a matching 'Glitch' handler so the planned glitch isn't a no-op in preview."""
    _ = duration  # constant-over-cut look; signature parity with the other builders
    s = max(1, int(shift))
    n = max(0, int(noise))
    return (
        f"rgbashift=rh={s}:bh=-{s},"
        f"noise=alls={n}:allf=t,"
        f"scale=1080:1920,setsar=1"
    )

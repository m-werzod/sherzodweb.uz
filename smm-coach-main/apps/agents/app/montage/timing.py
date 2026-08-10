"""License-free MVP timing: dead-air trimming + proportional caption windows.

This deliberately avoids phoneme forced-alignment (whose only good Uzbek model,
Meta MMS, is CC-BY-NC = non-commercial). Instead:

  * cuts come from ffmpeg `silencedetect` — remove dead air, keep speech. This
    alone is the "edited" feel, and it's deterministic + license-clean.
  * captions are distributed proportionally across the kept (output) duration
    from the script text — window-level, NOT per-word karaoke. Honest about the
    fact that we don't have trustworthy Uzbek word timing yet (that's a premium
    Phase-2 path gated on confidence).
"""
from __future__ import annotations

import difflib
import re
from typing import Any

from app.montage.edl import (
    EDL,
    Captions,
    CaptionStyle,
    CaptionWindow,
    CaptionWord,
    Cut,
    Motion,
    Overlay,
)
from app.montage.probe import run_ff
from app.montage.text_norm import normalize_caption_text

_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")


def detect_silences(
    path: str, *, noise_db: int = -30, min_silence: float = 0.35
) -> list[tuple[float, float]]:
    """Return (start, end) silence spans in SOURCE seconds via ffmpeg
    silencedetect. `-f null` always exits 0; the data is on stderr."""
    proc = run_ff(
        [
            "ffmpeg", "-i", path,
            "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f", "null", "-",
        ]
    )
    stderr = proc.stderr or ""
    starts = [float(m) for m in _SILENCE_START.findall(stderr)]
    ends = [float(m) for m in _SILENCE_END.findall(stderr)]
    # Pair them in order; a trailing unmatched start means silence runs to EOF.
    spans: list[tuple[float, float]] = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        spans.append((s, e if e is not None else s))
    return spans


def build_cuts(
    duration: float,
    silences: list[tuple[float, float]],
    *,
    pad: float = 0.08,
    min_keep: float = 0.20,
) -> list[Cut]:
    """Invert the silence spans into KEEP segments (the speech), pad each outward
    slightly so we never blade a word, merge overlaps. If nothing is detectable
    as silence (or the whole clip is silent), keep the entire clip as one cut so
    the pipeline never produces an empty timeline."""
    if duration <= 0:
        return []
    # Build speech spans = complement of silence over [0, duration].
    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in sorted(silences):
        s_start = max(0.0, min(s_start, duration))
        s_end = max(0.0, min(s_end, duration))
        if s_start > cursor:
            speech.append((cursor, s_start))
        cursor = max(cursor, s_end)
    if cursor < duration:
        speech.append((cursor, duration))

    if not speech:
        return [Cut(src_start=0.0, src_end=duration)]

    # Pad outward + clamp, then merge overlapping/adjacent segments.
    padded = [(max(0.0, a - pad), min(duration, b + pad)) for a, b in speech]
    merged: list[tuple[float, float]] = []
    for a, b in padded:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))

    cuts = [Cut(src_start=a, src_end=b) for a, b in merged if (b - a) >= min_keep]
    return cuts or [Cut(src_start=0.0, src_end=duration)]


def speech_coverage(cuts: list[Cut], duration: float) -> float:
    """Fraction of the source clip kept as speech (0..1)."""
    if duration <= 0:
        return 0.0
    kept = sum(max(0.0, c.src_end - c.src_start) for c in cuts)
    return min(1.0, kept / duration)


def assign_shot_index(cuts: list[Cut], script_timeline: list[Any]) -> None:
    """Link each kept Cut back to the scriptwriter STORYBOARD shot whose narration
    plays over it — the G1 fix that stops the storyboard (shotList: cam/frame/action/
    vfx) from being orphaned the moment the clip is cut.

    `shot_index` is the storyboard shot number (scriptTimeline[].shotIndex ->
    shotList[].i, 1-indexed; 0 = unassigned), NOT a cut-enumeration index. Cuts come
    from silencedetect on the user's REAL recording while the scriptTimeline is the
    PLANNED narration, so — exactly like build_caption_windows spreads words — we lay
    the planned segments across the kept OUTPUT timeline proportionally to their word
    counts and tag each cut with the segment it overlaps most. Best-effort and fully
    deterministic; Faza 1 footage-understanding replaces this proportional guess with
    real transcription alignment. Mutates `cuts` in place (sets shot_index + script_text).
    """
    out_dur = sum(max(0.0, c.src_end - c.src_start) for c in cuts)
    if out_dur <= 0 or not cuts or not script_timeline:
        return
    # Planned segments carrying a positive word weight (blank rows can't host a cut).
    segs: list[tuple[int, str, float]] = []  # (shot_index, text, weight)
    for entry in script_timeline:
        if not isinstance(entry, dict):
            continue
        text = normalize_caption_text(str(entry.get("text") or ""))
        weight = float(len(text.split()))
        if weight <= 0:
            continue
        raw_idx = entry.get("shotIndex")
        shot_idx = raw_idx if isinstance(raw_idx, int) and raw_idx >= 1 else 0
        segs.append((shot_idx, text, weight))
    if not segs:
        return
    # Place each segment on [0, out_dur] proportionally to cumulative word weight.
    total = sum(w for _, _, w in segs)
    spans: list[tuple[float, float, int, str]] = []  # (out_start, out_end, shot_index, text)
    cursor = 0.0
    for shot_idx, text, w in segs:
        start = cursor
        cursor += out_dur * (w / total)
        spans.append((start, cursor, shot_idx, text))
    spans[-1] = (spans[-1][0], out_dur, spans[-1][2], spans[-1][3])  # absorb float drift
    # Tag each cut by the planned segment it overlaps most on the OUTPUT timeline.
    out_cursor = 0.0
    for cut in cuts:
        c_start = out_cursor
        c_end = out_cursor + max(0.0, cut.src_end - cut.src_start)
        out_cursor = c_end
        best_overlap = 0.0
        best: tuple[int, str] | None = None
        for s_start, s_end, shot_idx, text in spans:
            overlap = min(c_end, s_end) - max(c_start, s_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best = (shot_idx, text)
        if best is None:  # zero-length / degenerate cut — fall back to nearest by midpoint
            mid = (c_start + c_end) / 2.0
            nearest = min(spans, key=lambda s: abs(((s[0] + s[1]) / 2.0) - mid))
            best = (nearest[2], nearest[3])
        cut.shot_index, cut.script_text = best


def subdivide_cuts(cuts: list[Cut], scene_times: list[float], *, min_sub: float = 0.5) -> list[Cut]:
    """Split any cut that straddles a visual scene-change (SOURCE seconds, from detect_shots)
    at that boundary — so the montage cuts where the FOOTAGE actually cuts and per-cut motion
    re-starts on real content, not just on silence. Faza 1b: this is how the footage
    understanding (Faza 1) feeds the cut structure.

    Preserves total duration exactly (the fragments sum to the original cut), so the OUTPUT
    offset table / output_duration / caption timing are all unchanged. Never makes a fragment
    shorter than `min_sub` (avoids jittery micro-shots). Degrade-safe: no scene_times -> cuts
    returned unchanged. The new fragments carry default shot_index — assign_shot_index runs
    AFTER this on the finer list."""
    if not scene_times:
        return cuts
    scene = sorted(set(scene_times))
    out: list[Cut] = []
    for c in cuts:
        start = c.src_start
        for t in scene:
            # Accept a split only when BOTH the new fragment [start, t] and the remainder
            # [t, src_end] are >= min_sub — guarding the cut edges AND adjacent boundaries
            # too close together, so every emitted fragment is at least min_sub long.
            if t - start >= min_sub and c.src_end - t >= min_sub:
                out.append(Cut(src_start=start, src_end=t))
                start = t
        out.append(Cut(src_start=start, src_end=c.src_end))
    return out


def subdivide_evenly(
    cuts: list[Cut], *, target_sec: float = 2.8, min_sub: float = 1.2
) -> list[Cut]:
    """Edit-floor: split long cuts into ~`target_sec` fragments so a fluent, un-cut
    clip still gets per-segment motion rhythm and transition/zoom boundaries to
    attach to. Without this a short continuous clip yields ~1 silence-cut → a flat
    "passthrough" montage (the founder's "montaj ishlamaydi").

    Duration-preserving (fragments sum to the original cut) so the OUTPUT offset
    table / caption timing are unchanged — same guarantee as subdivide_cuts. Only
    splits a cut long enough to yield ≥2 fragments each ≥ min_sub; carries no
    shot_index (assign_shot_index runs after)."""
    out: list[Cut] = []
    for c in cuts:
        dur = c.src_end - c.src_start
        # Need room for at least two >=min_sub fragments to bother splitting.
        if dur < 2 * min_sub or dur <= target_sec + min_sub:
            out.append(c)
            continue
        n = max(2, int(dur // target_sec))
        # Cap so the last fragment can't fall below min_sub.
        while n > 2 and dur / n < min_sub:
            n -= 1
        step = dur / n
        start = c.src_start
        for k in range(1, n):
            t = round(c.src_start + step * k, 3)
            if t - start >= min_sub and c.src_end - t >= min_sub:
                out.append(Cut(src_start=start, src_end=t))
                start = t
        out.append(Cut(src_start=start, src_end=c.src_end))
    return out


def _merge_spans(spans: list[tuple[float, float]], *, gap: float = 0.0) -> list[tuple[float, float]]:
    """Sort, drop non-positive, and merge overlapping/touching (within `gap`) SOURCE spans."""
    cleaned = sorted((min(a, b), max(a, b)) for a, b in spans if max(a, b) - min(a, b) > 1e-3)
    out: list[tuple[float, float]] = []
    for s, e in cleaned:
        if out and s <= out[-1][1] + gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def subtract_spans(cuts: list[Cut], drop_spans: list[tuple[float, float]], *, min_keep: float = 0.20) -> list[Cut]:
    """Remove SOURCE-second `drop_spans` from the kept Cuts — duration-CHANGING (unlike
    subdivide_cuts, which only splits). A Cut straddling a drop is split into the surviving
    fragment(s); a fully-covered fragment vanishes; fragments shorter than `min_keep` are discarded.
    Cut order + shot_index/script_text are preserved onto the fragments.

    This is how the Stage-9b semantic stumble-cut (filler/repeat/off-script ranges from
    align_script_to_transcript) and footage bad-take rejects actually shorten the montage. MUST run
    in build_edl BEFORE assign_shot_index / build_caption_windows / build_motion so the two-timebase
    offset table and every OUTPUT lane are computed on the final cut list. Degrade-safe: no spans →
    cuts returned unchanged."""
    spans = _merge_spans(drop_spans)
    if not spans:
        return cuts
    out: list[Cut] = []
    for c in cuts:
        segments: list[tuple[float, float]] = [(c.src_start, c.src_end)]
        for ds, de in spans:
            nxt: list[tuple[float, float]] = []
            for s, e in segments:
                if de <= s or ds >= e:  # no overlap → keep whole
                    nxt.append((s, e))
                    continue
                if ds > s:  # surviving left fragment
                    nxt.append((s, ds))
                if de < e:  # surviving right fragment
                    nxt.append((de, e))
            segments = nxt
        for s, e in segments:
            if e - s >= min_keep:
                out.append(
                    Cut(
                        src_start=round(s, 3), src_end=round(e, 3), beat_index=c.beat_index,
                        shot_index=c.shot_index, script_text=c.script_text,
                        align_confidence=c.align_confidence,
                    )
                )
    return out


# Hesitation sounds (repeated vowels / common interjections) — high-precision filler across uz/ru/en.
_FILLER_RE = re.compile(r"^(?:e{2,}|a{2,}|o{2,}|i{2,}|u{2,}|m{2,}|h+m+|u+h+|e+h+|a+h+|x+m+)$")
_FILLER_WORDS = {"yani", "tipa", "ну", "короче", "значит", "эм", "ээ", "уу", "ммм", "эээ"}


def _is_filler(key: str) -> bool:
    """A normalized token that is a hesitation/filler, never meaningful content."""
    return bool(key) and (key in _FILLER_WORDS or _FILLER_RE.match(key) is not None)


def align_script_to_transcript(
    words: list[dict[str, Any]], script_timeline: list[Any], *, min_offscript_run: int = 4
) -> list[tuple[float, float]]:
    """Find SOURCE-second spans to DROP from a raw take so the montage keeps only the clean delivery.
    THREE high-precision, deterministic signals (no LLM, no Whisper-confidence — whisper-1 returns
    none — so it never trusts a single mangled Uzbek token):

      (A) immediate repeats — the same word spoken twice in a row (stutter / false start): drop the
          EARLIER one, keep the (usually cleaner) retake.
      (B) filler — hesitation sounds (eee/aaa/mmm/…) and common interjections.
      (C) off-script insertions — ONLY when the transcript aligns well to the script (>=50% of tokens
          match): a run of >= `min_offscript_run` transcript tokens that matches NOTHING in the
          script and sits BETWEEN two matched anchors (forgot the line, rambled, got back on) → drop.
          Skipped entirely when alignment is poor (uz Whisper failed) so we never blade good speech.

    Returns merged (start, end) SOURCE spans; the caller (build_edl) runs subtract_spans + the
    coverage floor so over-cutting can never empty the montage."""
    toks: list[tuple[str, float, float]] = []
    for w in words:
        k = _match_key(str(w.get("text") or ""))
        s, e = w.get("start"), w.get("end")
        if k and isinstance(s, (int, float)) and isinstance(e, (int, float)) and e > s:
            toks.append((k, float(s), float(e)))
    if len(toks) < 4:
        return []
    drops: list[tuple[float, float]] = []
    # (B) filler tokens
    drops += [(s, e) for k, s, e in toks if _is_filler(k)]
    # (A) adjacent exact repeats — drop the earlier occurrence (keep the retake)
    drops += [
        (toks[i][1], toks[i][2])
        for i in range(len(toks) - 1)
        if toks[i][0] == toks[i + 1][0] and not _is_filler(toks[i][0])
    ]
    # (C) off-script insertions — gated on trustworthy alignment
    skeys = [k for k in (_match_key(x) for x in _script_words(script_timeline)) if k]
    tkeys = [t[0] for t in toks]
    if skeys:
        sm = difflib.SequenceMatcher(a=skeys, b=tkeys, autojunk=False)
        matched = sum(b.size for b in sm.get_matching_blocks())
        if matched >= max(4, int(0.5 * len(tkeys))):
            covered = [False] * len(tkeys)
            for blk in sm.get_matching_blocks():
                for j in range(blk.b, blk.b + blk.size):
                    covered[j] = True
            i, n = 0, len(tkeys)
            while i < n:
                if covered[i]:
                    i += 1
                    continue
                j = i
                while j < n and not covered[j]:
                    j += 1
                # a long unmatched run BETWEEN two anchors (not at the head/tail) = a clear insertion
                if j - i >= min_offscript_run and i > 0 and j < n:
                    drops.append((toks[i][1], toks[j - 1][2]))
                i = j
    return _merge_spans(drops)


def _shot_output_blocks(cuts: list[Cut]) -> dict[int, tuple[float, float]]:
    """The FIRST contiguous OUTPUT block (start, end) per storyboard shot_index. A shot's
    cuts are normally consecutive; if the same shot_index reappears later (proportional
    mapping can interleave shots), keep only its first block so an effect bound to a shot
    never spans another shot. Shared by build_overlays + build_motion."""
    blocks: dict[int, tuple[float, float]] = {}
    cursor = 0.0
    idx = 0
    n = len(cuts)
    while idx < n:
        si = cuts[idx].shot_index
        start = cursor
        while idx < n and cuts[idx].shot_index == si:
            cursor += max(0.0, cuts[idx].src_end - cuts[idx].src_start)
            idx += 1
        if si >= 1 and si not in blocks:
            blocks[si] = (start, cursor)
    return blocks


def build_motion(cuts: list[Cut], shot_list: list[Any]) -> list[Motion]:
    """Per-cut OUTPUT-timed camera motion: a planned zoom_punch where the storyboard asked for one,
    else an explicit ken-burns drift on EVERY remaining cut.

    The ken-burns drift used to be implicit — `_cut_motion` computed `i%2` at render time, so the
    ffmpeg export drifted on every cut but STUDIO (which only reads EXPLICIT EDL.motion entries)
    showed a static preview = export≠preview, and the i%2 index would desync if a later pass changed
    the cut count. Emitting an explicit `kenburns` Motion per cut makes BOTH renderers read the SAME
    drift from the EDL. Direction alternates by cut index (stable at build time, when the cut list is
    final); easing 'linear' + zoom encoded in from/to_scale keep the ffmpeg output BYTE-IDENTICAL to
    the old default while STUDIO's clipsFromEdl turns the same entry into matching scale keyframes.
    Degrade-safe: no cuts → []."""
    if not cuts:
        return []
    blocks = _shot_output_blocks(cuts)
    motions: list[Motion] = []
    for item in shot_list or []:
        if not isinstance(item, dict):
            continue
        i = item.get("i")
        if not isinstance(i, int) or i not in blocks:
            continue
        shot_start, shot_end = blocks[i]
        for v in item.get("vfx") or []:
            if not isinstance(v, dict):
                continue
            if str(v.get("type") or "") not in ("zoom", "zoom_punch", "punch"):
                continue
            motions.append(
                Motion(
                    op="zoom_punch", at_sec=round(shot_start, 3),
                    dur=round(max(0.1, shot_end - shot_start), 3),
                    from_scale=1.0, to_scale=1.12,
                )
            )
            break  # one punch per shot
    # Explicit default ken-burns on every cut NOT already under a planned zoom (same drift the
    # old i%2 default produced; from/to_scale encode direction so STUDIO renders it too).
    out_cursor = 0.0
    for idx, c in enumerate(cuts):
        c_len = max(0.0, c.src_end - c.src_start)
        c_start = out_cursor
        out_cursor += c_len
        if c_len <= 0:
            continue
        covered = any(
            m.op == "zoom_punch" and m.at_sec - 1e-3 <= c_start < m.at_sec + m.dur for m in motions
        )
        if covered:
            continue
        zoom_in = idx % 2 == 0
        motions.append(
            Motion(
                op="kenburns", at_sec=round(c_start, 3), dur=round(max(0.1, c_len), 3),
                from_scale=1.0 if zoom_in else 1.08, to_scale=1.08 if zoom_in else 1.0,
                easing="linear",
            )
        )
    return motions


def build_overlays(cuts: list[Cut], shot_list: list[Any]) -> list[Overlay]:
    """Translate the scriptwriter storyboard's planned on-screen text (shotList[].vfx with
    type='text_overlay') into OUTPUT-timed EDL overlays — the AI's titles/callouts that were
    orphaned until now. They render as extra ASS lines (NOT a filtergraph change), so the
    deterministic render spine + degrade ladder are untouched.

    Each vfx hangs off a storyboard shot (shotList[].i); cuts carry that shot via
    Cut.shot_index (assign_shot_index), so a shot's OUTPUT span = the cuts tagged with it.
    The vfx atSec is relative to the shot, so we offset from the shot's OUTPUT start and clamp
    into its OUTPUT span. Best-effort + deterministic (the Faza 0/1 philosophy)."""
    if not cuts or not shot_list:
        return []
    blocks = _shot_output_blocks(cuts)
    overlays: list[Overlay] = []
    for item in shot_list:
        if not isinstance(item, dict):
            continue
        i = item.get("i")
        if not isinstance(i, int) or i not in blocks:
            continue
        shot_start, shot_end = blocks[i]
        for v in item.get("vfx") or []:
            if not isinstance(v, dict) or v.get("type") != "text_overlay":
                continue
            txt = str(v.get("text") or "").strip()
            if not txt:
                continue
            off = v.get("atSec")
            at = shot_start + (float(off) if isinstance(off, (int, float)) else 0.0)
            # Keep the overlay strictly inside the shot's OUTPUT span (shot_end <=
            # output_duration), with room to be seen: shot_start <= at, at + dur <= shot_end.
            at = min(max(at, shot_start), max(shot_start, shot_end - 0.4))
            dur = min(2.5, shot_end - at)
            if dur <= 0.05:  # no room left in a tiny shot — skip rather than flash
                continue
            overlays.append(
                Overlay(
                    template="title", at_sec=round(at, 3), dur=round(dur, 3),
                    text=txt[:80], position=str(v.get("position") or "top"),
                    color=str(v.get("color") or "#FFFFFF"),
                )
            )
    return overlays


def build_caption_windows_from_transcript(
    edl: EDL,
    transcript: list[Any],
    *,
    words_per_window: int = 4,
    style: CaptionStyle | None = None,
    tier: str = "premium",
    emphasis_words: list[str] | None = None,
    script_words: list[str] | None = None,
) -> Captions:
    """Karaoke captions from the ACTUAL Whisper transcript — the words the speaker really said, at
    their REAL per-word timestamps mapped onto the post-cut OUTPUT timeline. THIS is what makes the
    text match the speaker's mouth (CapCut/Submagic style). The script-based builder only spread the
    PLANNED script proportionally, so it drifted AND showed words the speaker didn't actually say
    (if they ad-libbed off-script) — the user's exact complaint. Words landing in a removed
    (silence/stumble) gap are dropped, so the caption only ever shows speech that survived the cut."""
    caps = Captions(style=style or CaptionStyle(), tier=tier)
    emphasis = {_match_key(w) for w in (emphasis_words or []) if _match_key(w)}
    words: list[str] = []
    starts: list[float] = []
    ends: list[float] = []
    prev = 0.0
    for w in transcript:
        if not isinstance(w, dict):
            continue
        text = str(w.get("text") or "").strip()
        s, e = w.get("start"), w.get("end")
        if not text or not isinstance(s, (int, float)) or not isinstance(e, (int, float)):
            continue
        out_s = edl.source_to_output(float(s))
        out_e = edl.source_to_output(float(e))
        if out_s is None and out_e is None:
            continue  # the whole word fell inside a removed gap
        if out_s is None:
            out_s = out_e
        if out_e is None:
            out_e = out_s
        # Monotonic, min 80ms on screen so a fast word is still readable as it's spoken.
        out_s = max(float(out_s), prev)
        out_e = max(float(out_e), out_s + 0.08)
        words.append(text)
        starts.append(round(out_s, 3))
        ends.append(round(out_e, 3))
        prev = out_e
    if not words:
        return caps
    # Whisper timing is robust but its TEXT is not (the API rejects language=uz, so Uzbek
    # decodes via a cousin language — mangled spelling). The script IS what the speaker reads:
    # substitute the script words onto the REAL speech slots, distributed proportionally and
    # in order, so the captions show correct Uzbek at the true spoken cadence.
    if script_words and len(words) >= 3:
        sw = [w for w in script_words if w.strip()]
        if sw:
            new_words: list[str] = []
            new_starts: list[float] = []
            new_ends: list[float] = []
            c_prev = 0
            total = len(words)
            for k in range(total):
                c = round((k + 1) * len(sw) / total)
                seg = " ".join(sw[c_prev:c]).strip()
                c_prev = max(c_prev, c)
                if not seg:
                    continue  # more slots than script words — drop the empty slot
                new_words.append(seg)
                new_starts.append(starts[k])
                new_ends.append(ends[k])
            if new_words:
                words, starts, ends = new_words, new_starts, new_ends
    st = caps.style
    play_w = caps.play_res[0] if caps.play_res else 1080
    groups = _group_windows(
        words, font_size=st.size, play_w=play_w, margin_lr=st.margin_lr, max_words=max(1, words_per_window)
    )
    _enforce_min_window(starts, ends, groups, edl.output_duration())
    caps.windows = [
        CaptionWindow(
            words=[
                # pop per CONSTITUENT token: after the script-word substitution above, words[k] is a
                # MULTI-word segment ("juda muhim sir"), so _match_key(whole) → "judamuhimsir" never
                # matches a single emphasis key ("sir") and the karaoke pop was dead on this path.
                CaptionWord(
                    text=words[k], start=starts[k], end=ends[k],
                    pop=any(_match_key(tok) in emphasis for tok in words[k].split()),
                )
                for k in g
            ]
        )
        for g in groups
        if g
    ]
    return caps


def _script_words(script_timeline: list[Any]) -> list[str]:
    """Flatten the scriptTimeline into an ordered word list."""
    parts: list[str] = []
    for entry in script_timeline:
        raw = str(entry.get("text") or "") if isinstance(entry, dict) else str(entry)
        text = normalize_caption_text(raw)
        if text:
            parts.append(text)
    return " ".join(parts).split()


def _match_key(word: str) -> str:
    """Lowercased alphanumeric core, so 'Sirni!' matches emphasis 'sirni'."""
    return "".join(ch for ch in word.lower() if ch.isalnum())


def _real_times(n: int, word_out_times: list[float], out_dur: float) -> tuple[list[float], list[float]]:
    """Map N script words onto the transcript's real per-word END times
    (OUTPUT seconds) positionally — captions follow the speaker's actual cadence
    (pauses, pace) instead of an even spread. Monotonic, min 80ms/word."""
    m = len(word_out_times)
    ends: list[float] = []
    prev = 0.0
    for i in range(n):
        idx = round(i * (m - 1) / (n - 1)) if n > 1 else m - 1
        idx = min(max(idx, 0), m - 1)
        e = min(out_dur, max(word_out_times[idx], prev + 0.08))
        ends.append(round(e, 3))
        prev = e
    starts = [0.0, *ends[:-1]]
    return starts, ends


# Caption window grouping (palmier CaptionBuilder ideas, adapted to our per-word karaoke model).
_SENT_DELIM = ".!?…"  # break a window AFTER a sentence end
_CLAUSE_DELIM = ",;:"  # break after a clause boundary (if the window already has >=2 words)
_CHAR_W_RATIO = 0.50  # rough char advance ≈ 0.50×font_size (bold sans, mixed-case) — catches the
# egregious long-word overflow while still allowing normal 2-3 word lines on one line
_MIN_WINDOW_SEC = 0.5  # a window flashing shorter than this is unreadable on a fast reel


def _fits_one_line(text: str, font_size: int, play_w: int, margin_lr: int) -> bool:
    """Rough single-line width test: would `text` fit the caption safe-width WITHOUT ASS wrapping
    to a 2nd line (which breaks the one-line karaoke look)? Resolution-based estimate, no font
    metrics — deliberately slightly generous so we break long Uzbek words BEFORE they overflow."""
    usable = max(1, play_w - 2 * max(0, margin_lr))
    return len(text) * (font_size * _CHAR_W_RATIO) <= usable


def _group_windows(
    words: list[str], *, font_size: int, play_w: int, margin_lr: int, max_words: int
) -> list[list[int]]:
    """Group word INDICES into caption windows. Closes a window on (1) a sentence end .!?, (2) a
    clause boundary ,;: once it has >=2 words, (3) width overflow, or (4) the max-word cap — so
    captions land on natural pauses and never wrap to a second line. A single over-long word is
    kept alone (palmier's rule)."""
    groups: list[list[int]] = []
    cur: list[int] = []
    cur_text = ""
    for i, w in enumerate(words):
        cand = f"{cur_text} {w}".strip() if cur_text else w
        if cur and not _fits_one_line(cand, font_size, play_w, margin_lr):
            groups.append(cur)
            cur, cur_text = [], ""
            cand = w
        cur.append(i)
        cur_text = cand
        end_ch = w[-1] if w else ""
        sentence = end_ch in _SENT_DELIM
        clause = end_ch in _CLAUSE_DELIM
        if sentence or (clause and len(cur) >= 2) or len(cur) >= max_words:
            groups.append(cur)
            cur, cur_text = [], ""
    if cur:
        groups.append(cur)
    return groups


def _char_weighted_times(words: list[str], out_dur: float) -> tuple[list[float], list[float]]:
    """Fallback (no transcript alignment): share OUTPUT time across words by CHARACTER count, so a
    14-char word stays on screen longer than a 2-char one — reading-speed-correct (palmier
    distribute). Back-to-back, monotonic."""
    total = sum(max(len(w), 1) for w in words) or 1
    starts: list[float] = []
    ends: list[float] = []
    t = 0.0
    for w in words:
        starts.append(round(t, 3))
        t += out_dur * max(len(w), 1) / total
        ends.append(round(min(t, out_dur), 3))
    return starts, ends


def _enforce_min_window(
    starts: list[float], ends: list[float], groups: list[list[int]], out_dur: float
) -> None:
    """Guarantee each window stays up at least _MIN_WINDOW_SEC, cascade-shifting later words so
    they don't double-stack (palmier enforceMinDuration). Mutates starts/ends in place; clamps the
    tail to out_dur so a window never shows after the video ends (our windows can't overflow past
    output the way palmier's can past a clip end)."""
    n = len(starts)
    for g in groups:
        a, b = g[0], g[-1]
        if ends[b] - starts[a] < _MIN_WINDOW_SEC:
            shift = (starts[a] + _MIN_WINDOW_SEC) - ends[b]
            if shift > 0:
                ends[b] = round(ends[b] + shift, 3)
                for k in range(b + 1, n):
                    starts[k] = round(starts[k] + shift, 3)
                    ends[k] = round(ends[k] + shift, 3)
    for k in range(n):
        starts[k] = round(min(starts[k], out_dur), 3)
        ends[k] = round(min(max(ends[k], starts[k]), out_dur), 3)


def build_caption_windows(
    cuts: list[Cut],
    script_timeline: list[Any],
    *,
    words_per_window: int = 4,
    style: CaptionStyle | None = None,
    tier: str = "premium",
    emphasis_words: list[str] | None = None,
    word_out_times: list[float] | None = None,
) -> Captions:
    """Distribute the script text evenly across the OUTPUT timeline in ~3 word
    windows (the punchy Submagic cadence — one readable line, fast changes) with
    per-word proportional times (the premium tier renders these as a karaoke
    sweep). The caption_stylist agent's emphasis words are flagged `pop` so the
    renderer enlarges them. Proportional sync — best-effort on Uzbek, honest."""
    out_dur = sum(max(0.0, c.src_end - c.src_start) for c in cuts)
    words = _script_words(script_timeline)
    caps = Captions(style=style or CaptionStyle(), tier=tier)
    if not words or out_dur <= 0:
        return caps

    # Cap to a readable pace so a clip shorter than the script doesn't cram all
    # the words into too little time (unreadable). ~2.8 words/sec keeps captions
    # legible; the clip's real speech is roughly this many words anyway.
    max_words = max(1, int(out_dur * 2.8))
    words = words[:max_words]

    emphasis = {_match_key(w) for w in (emphasis_words or []) if _match_key(w)}
    n = len(words)
    if word_out_times and len(word_out_times) >= 3:
        starts, ends = _real_times(n, word_out_times, out_dur)
    else:
        starts, ends = _char_weighted_times(words, out_dur)

    # Group into boundary- + width-aware windows (NOT blind N-word chunks, which straddle sentence
    # breaks and overflow long Uzbek words to a 2nd line), then guarantee a readable min on-screen
    # time per window. `words_per_window` is now the MAX per window, not a fixed stride.
    st = caps.style
    play_w = caps.play_res[0] if caps.play_res else 1080
    groups = _group_windows(
        words, font_size=st.size, play_w=play_w, margin_lr=st.margin_lr, max_words=max(1, words_per_window)
    )
    _enforce_min_window(starts, ends, groups, out_dur)

    caps.windows = [
        CaptionWindow(
            words=[
                CaptionWord(
                    text=words[k], start=starts[k], end=ends[k],
                    pop=any(_match_key(tok) in emphasis for tok in words[k].split()),
                )
                for k in g
            ]
        )
        for g in groups
        if g
    ]
    return caps

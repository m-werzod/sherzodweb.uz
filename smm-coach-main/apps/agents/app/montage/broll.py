"""Stock B-roll curation + resolution (Faza 3).

Two halves, mirroring how F1/F2 split decide-vs-execute:

  * `select_broll_shots` — PURE: which storyboard shots does the user's own footage NOT
    cover? (the FootageMap set-difference). Runs in the broll_curator graph node.
  * `resolve_broll` — I/O: for each planned shot, search Pexels, download the clip, and
    populate the EDL's (previously dead) `broll` lane with an OUTPUT-time overlay anchor.
    Runs in the montage worker THREAD (compile_and_render), never the event loop.

B-roll is ADDITIVE polish: every path is fail-soft, and the render's degrade ladder drops
b-roll entirely (keeping cuts+captions) if the splice ever fails. It must never shrink a
montage. Only `placement='overlay'` (full-frame cover, duration-preserving) is produced —
a true cut-away that extends the timeline would break the two-timebase contract.
"""
from __future__ import annotations

import os
from typing import Any

import structlog

from app.integrations.stock.pexels import download_video, search_vertical_video
from app.montage.edl import EDL, Broll
from app.montage.gen_video import generate_broll_url
from app.montage.timing import _shot_output_blocks

log = structlog.get_logger(__name__)

_CONF_FLOOR = 0.5  # below this a footage→storyboard match doesn't count as coverage
_MAX_BROLL = 3  # cap per montage — relevance + render time + Pexels courtesy
_MIN_BROLL_SEC = 0.8  # a shorter window isn't worth a stock cutaway
_BROLL_MAX_SEC = 2.5  # a b-roll is a SHORT accent cutaway, NOT a full-shot cover — the
# speaker stays the base layer and fills the rest of every shot (talking-head reels are
# speaker-first; a full-shot b-roll overlay at opacity 1.0 hid the presenter for most of the reel).
_BROLL_MAX_COVERAGE = 0.35  # b-roll never hides the speaker for more than this fraction of the reel


def _broll_window(shot_dur: float, out_total: float, used_sec: float) -> float | None:
    """On-screen seconds for a b-roll in this shot, or None if it's too short OR adding it
    would blow the speaker-first coverage budget. PURE/testable."""
    dur = round(min(shot_dur, _BROLL_MAX_SEC), 3)
    if dur < _MIN_BROLL_SEC:
        return None
    if out_total > 0 and used_sec + dur > out_total * _BROLL_MAX_COVERAGE + 1e-3:
        return None
    return dur


def select_broll_shots(
    footage_map: Any, shot_list: list[Any], *, conf_floor: float = _CONF_FLOOR, max_shots: int = _MAX_BROLL
) -> list[dict[str, Any]]:
    """Storyboard shots the footage doesn't cover → B-roll candidates (in storyboard order).

    Returns [{shot_index, action}]. Empty when the vision pass was unreliable (`vision_ok`
    false) — we NEVER fabricate misses from a blind FootageMap, else every montage would
    drown in stock footage. A shot is 'covered' when some footage shot matched it with
    confidence >= conf_floor.
    """
    if not isinstance(footage_map, dict) or not footage_map.get("vision_ok"):
        return []
    covered: set[int] = set()
    for s in footage_map.get("shots") or []:
        if not isinstance(s, dict):
            continue
        msi = s.get("matched_shot_index")
        conf = s.get("confidence", 1.0)
        if isinstance(msi, int) and msi >= 1 and isinstance(conf, (int, float)) and conf >= conf_floor:
            covered.add(msi)

    out: list[dict[str, Any]] = []
    for sl in shot_list:
        if not isinstance(sl, dict):
            continue
        i = sl.get("i")
        action = str(sl.get("action") or "").strip()
        if isinstance(i, int) and i >= 1 and i not in covered and action:
            out.append({"shot_index": i, "action": action})
        if len(out) >= max_shots:
            break

    # INSERT cutaways — the reference-grade look for a fluent talking-head that covers every shot.
    # Coverage alone yields ZERO b-roll there, but pro edits still cut away over the speaker:
    # (a) shots whose storyboard explicitly requested an insert (`b_roll`) always get one;
    # (b) failing that, alternate middle shots (never the hook or the last/CTA shot) get a cutaway
    #     from their action text. Both respect the same overall cap.
    have = {o["shot_index"] for o in out}
    if len(out) < max_shots:
        for sl in shot_list:
            if not isinstance(sl, dict):
                continue
            i = sl.get("i")
            req = str(sl.get("b_roll") or "").strip()
            if isinstance(i, int) and i >= 1 and i not in have and req and req.lower() != "null":
                out.append({"shot_index": i, "action": req})
                have.add(i)
                if len(out) >= max_shots:
                    break
    if not out:
        middles = [
            sl for sl in shot_list
            if isinstance(sl, dict) and isinstance(sl.get("i"), int)
            and str(sl.get("action") or "").strip()
        ]
        # skip the hook (first) and CTA (last) — the speaker must stay on screen there
        for sl in middles[1:-1][::2][: max(1, max_shots // 2)]:
            out.append({"shot_index": int(sl["i"]), "action": str(sl["action"]).strip()})

    out.sort(key=lambda o: o["shot_index"])
    return out


def select_reject_shots(
    footage_map: Any, shot_list: list[Any], *, conf_floor: float = _CONF_FLOOR
) -> list[tuple[float, float]]:
    """Footage shots that match NO storyboard shot (an off-script take / fumbled outtake) → SOURCE
    drop spans for subtract_spans (Stage 9b Faza 3 — the first consumer of matched_shot_index for
    CUTTING, not just b-roll coverage).

    Conservative by construction (uz vision can misfire): returns [] unless (1) vision_ok, (2) there
    are >=3 shots, and (3) the MAJORITY of footage matched the storyboard well — so an unmatched shot
    is a genuine outtake, not a lone vision miss. Never rejects more than half the shots. The caller
    (build_edl) still runs subtract_spans + the 3s coverage floor, so this can never empty a montage.
    motion_score is left for a future 'bad camera move' pass — matched_shot_index==0 is the clear
    'doesn't belong to the script' signal."""
    if not isinstance(footage_map, dict) or not footage_map.get("vision_ok"):
        return []
    shots = [s for s in (footage_map.get("shots") or []) if isinstance(s, dict)]
    if len(shots) < 3:
        return []
    matched = sum(
        1
        for s in shots
        if isinstance(s.get("matched_shot_index"), int)
        and s["matched_shot_index"] >= 1
        and float(s.get("confidence", 1.0)) >= conf_floor
    )
    if matched < max(2, len(shots) // 2):  # alignment not trustworthy → never cut
        return []
    spans: list[tuple[float, float]] = []
    for s in shots:
        ss, se = s.get("src_start"), s.get("src_end")
        if s.get("matched_shot_index") == 0 and isinstance(ss, (int, float)) and isinstance(se, (int, float)) and se > ss:
            spans.append((float(ss), float(se)))
    if len(spans) > len(shots) // 2:  # a misfire shouldn't gut the take
        return []
    return spans


def resolve_broll(edl: EDL, plan: list[Any], work_dir: str, *, max_broll: int = _MAX_BROLL) -> int:
    """Download a stock clip per planned shot and append it to `edl.broll` as an OUTPUT-time
    overlay. Mutates `edl` in place; returns how many landed. Fail-soft per entry."""
    if not plan:
        return 0
    blocks = _shot_output_blocks(edl.cuts)  # {shot_index: (out_start, out_end)}
    out_total = edl.output_duration()
    used = 0
    used_sec = 0.0  # accumulated on-screen b-roll — bounds total coverage to _BROLL_MAX_COVERAGE
    for entry in plan:
        if used >= max_broll:
            break
        if not isinstance(entry, dict):
            continue
        si_raw = entry.get("shot_index")
        if not isinstance(si_raw, (int, float, str)):
            continue
        try:
            si = int(si_raw)
        except (TypeError, ValueError):
            continue
        query = str(entry.get("query") or "").strip()
        prompt = str(entry.get("prompt") or "").strip()
        want_gen = str(entry.get("source") or "").strip() == "generate"
        block = blocks.get(si)
        if block is None or (not query and not prompt):
            continue  # no OUTPUT home (shot was cut entirely) or nothing to fetch → skip
        out_start, out_end = block
        # A b-roll is a SHORT accent cutaway placed at the shot START — the speaker fills the
        # rest of the shot. _broll_window also enforces the reel-wide coverage budget.
        window = _broll_window(out_end - out_start, out_total, used_sec)
        if window is None or not edl.validate_output_atsec(out_start) or out_start + window > out_total + 1e-3:
            continue
        dur = window
        # Faza B opt-in: GENERATE the clip (fal.ai) when the plan asks for it AND a key is set; else
        # stock. Fail-soft — generation returns None (no key / error) → fall back to the stock query.
        url: str | None = None
        generated = False
        if want_gen and prompt:
            url = generate_broll_url(prompt, seconds=min(dur, 6.0))
            generated = url is not None
        if not url and query:
            url = search_vertical_video(query, min_dur=min(dur, 3.0))
        if not url:
            continue
        dest = os.path.join(work_dir, f"broll_{used}.mp4")
        if not download_video(url, dest):
            continue
        edl.broll.append(
            Broll(
                shot_index=si,
                source="generate" if generated else "stock",
                provider="fal" if generated else "pexels",
                query=query or None,
                prompt=prompt or None,
                asset_url=dest,
                dur_sec=dur,
                at_sec=round(out_start, 3),
                output_dur_sec=dur,
                placement="overlay",
                est_cost_usd=0.5 if generated else 0.0,
                ai_flag=generated,
            )
        )
        used += 1
        used_sec += dur
    if used:
        log.info("montage.broll_resolved", count=used, coverage_sec=round(used_sec, 2))
    return used

"""Persists generated tasks to the database.

After Scriptwriter + drift_detector + output_validator have produced
`approved_tasks`, this terminal node:

  1. Upserts a Roadmap row for the tenant (active, version+1 if one exists).
  2. Writes each approved task as a ContentTask row.
  3. Inserts 3 station rows at 25%/50%/75% follower targets so the
     `/roadmap` page renders the Trajectory-style "Bekat" badges out of the
     box.

NOT idempotent at run-id level: each run mints a FRESH active Roadmap and
archives the prior active one (nothing keys on `runId`). Rapid re-dispatch is
guarded web-side (the onboarding route returns the in-flight run for ~10 min);
a rare LangGraph reclaim that re-runs this node after it already committed
leaves an orphaned archived roadmap (the user still sees the correct latest
active one — the N-tasks invariant holds — it's just data bloat).
"""
from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.graphs.json_schemas import (
    HOOK_META,
    MUSIC_CUES,
    PREDICT_EVIDENCE,
    SCRIPT_TIMELINE,
    SHOT_LIST,
    validated_json,
)
from app.memory.db import get_sessionmaker

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)


async def run(state: GrowthCoachState) -> dict:
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    approved = state.get("approved_tasks") or []

    # Soft-quality fallback (content_review): the adversarial_critic is ADVISORY. If it rejected the
    # script after the rewrite budget was spent, the task lands in rejected_tasks with a fully-written,
    # usable script. The old behavior discarded it + rolled the status back — so the user spent money
    # and saw NOTHING, and could get stuck (every regenerate hits the same soft reject). Persist the
    # best (last) rejected attempt instead, folding the critique into the coach note so the flag
    # becomes visible FEEDBACK rather than silent data loss.
    if not approved and state.get("workflow") == "content_review":
        rejected = state.get("rejected_tasks") or []
        fallback = next(
            (t for t in reversed(rejected) if (t.get("script_md") or t.get("scriptMd"))),
            None,
        )
        if fallback:
            reasons = fallback.get("critic_reasons") or (
                [fallback["critic_reason"]] if fallback.get("critic_reason") else []
            )
            if reasons:
                note = "⚠️ AI sifat-eslatmasi (skript baribir saqlandi): " + "; ".join(
                    str(r) for r in reasons[:3]
                )
                prev_note = fallback.get("ai_coach_note") or ""
                fallback = {**fallback, "ai_coach_note": f"{prev_note}\n\n{note}".strip()}
            approved = [fallback]
            log.info(
                "roadmap_persister.soft_reject_fallback",
                run_id=run_id,
                task_id=state.get("task_id"),
                reasons=len(reasons),
            )

    if not approved:
        log.info("roadmap_persister.empty", run_id=run_id)
        # content_review with ZERO approved tasks (drift_detector / output_validator
        # rejected the single task and the rewrite budget is spent) must NOT leave
        # the task stuck in 'revising' with no script — that bricks the brief (the
        # Q&A gate is already lifted, so there's no way back). Restore the
        # pre-review status so the user can retry.
        if state.get("workflow") == "content_review" and state.get("task_id"):
            try:
                sm = get_sessionmaker()
                async with sm() as session:
                    await session.execute(
                        text(
                            'UPDATE content_tasks SET status = :st, "updatedAt" = NOW() '
                            'WHERE id = :id AND "tenantId" = :tid AND status = \'revising\''
                        ),
                        {
                            "st": state.get("prev_status") or "planned",
                            "id": state.get("task_id"),
                            "tid": tenant_id,
                        },
                    )
                    await session.commit()
            except Exception:  # noqa: BLE001
                log.warning("roadmap_persister.empty_status_restore_failed", run_id=run_id)
        return {}

    # content_review updates a single task in-place instead of creating a
    # brand-new roadmap. This prevents the "task opens → whole roadmap
    # regenerates" bug that wiped user progress on every brief fill.
    if state.get("workflow") == "content_review":
        return await _update_single_task(state, approved)

    north = state.get("north_star") or {}
    target = int(north.get("target_followers") or 0)
    current = int(north.get("current_followers") or 0)
    # Goal category (Dizayn B) — shapes the station SUBTITLE so a sales/reach/
    # engagement user sees milestones framed in THEIR metric, not a follower
    # count (which isn't their goal). Ordering still uses the follower threshold.
    goal = str(north.get("primary_goal") or "").lower()
    # Summary deliberately omits a task count — the UI's pill reads the
    # real DB row count and surfaces it there. Embedding a number here
    # used to produce "13 ta vazifa" subtitles next to a "12 TA TOPSHIRIQ"
    # pill when one task silently failed to insert.
    summary = (
        f"{north.get('niche', 'general')} · {current:,} → {target:,} obunachi."
    )

    sm = get_sessionmaker()
    async with sm() as session:
        ig_row = await session.execute(
            text(
                """
                SELECT id FROM instagram_accounts WHERE "tenantId" = :tid
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": tenant_id},
        )
        ig_id = ig_row.scalar()
        if not ig_id:
            log.warning("roadmap_persister.no_ig_account", tenant_id=tenant_id)
            return {}

        # Mark prior active roadmap as archived so we always have one active.
        await session.execute(
            text(
                """
                UPDATE roadmaps SET status = 'archived', "updatedAt" = NOW()
                WHERE "tenantId" = :tid AND status = 'active'
                """
            ),
            {"tid": tenant_id},
        )

        roadmap_id = uuid.uuid4().hex
        version_row = await session.execute(
            text(
                'SELECT COALESCE(MAX(version), 0) + 1 FROM roadmaps WHERE "tenantId" = :tid'
            ),
            {"tid": tenant_id},
        )
        version = int(version_row.scalar() or 1)

        await session.execute(
            text(
                """
                INSERT INTO roadmaps
                  (id, "tenantId", "instagramAccountId", status, version, summary,
                   "activeStageOrder", "riskScore", "generatedAt", "createdAt", "updatedAt")
                VALUES (:id, :tid, :ig, 'active', :ver, :summary, 0, 0.12, NOW(), NOW(), NOW())
                """
            ),
            {
                "id": roadmap_id,
                "tid": tenant_id,
                "ig": ig_id,
                "ver": version,
                "summary": summary,
            },
        )

        # Compute progressive follower targets for each task.
        # We spread the total growth across ALL approved tasks so each task
        # contributes a small, realistic step. The old linear formula assigned
        # huge chunks when there were only 3 tasks (e.g. 333 each for 0→1K).
        total_tasks = len(approved)
        for i, t in enumerate(approved):
            follower_target = int(
                current + (target - current) * ((i + 1) ** 1.2) / (total_tasks ** 1.2)
            )
            t["_follower_target"] = max(follower_target, current + 1)

        # Build milestone thresholds: 0% (start), 25%, 50%, 75%, 100% (goal)
        # BB25: the first milestone was "Bekat 00" — a zero-indexed station
        # label most users read as confusing ("why does it start at 0?").
        # Label it "Boshlang'ich" (Start) instead; the numbered milestones
        # 01/02/03 stay for the quartile markers.
        milestones = [
            (0.00, "Boshlang'ich", _station_title(current, goal, 0.00)),
            (0.25, "Bekat 01", _station_title(current + int((target - current) * 0.25), goal, 0.25)),
            (0.50, "Bekat 02", _station_title(current + int((target - current) * 0.50), goal, 0.50)),
            (0.75, "Bekat 03", _station_title(current + int((target - current) * 0.75), goal, 0.75)),
        ]
        # Only add the final milestone if the goal is meaningfully above current
        if target > current + 100:
            milestones.append((1.00, "Maqsad", _station_title(target, goal, 1.00)))

        # Interleave stations with tasks: insert a station before the first task
        # that crosses its follower threshold.
        order_idx = 0
        next_task_idx = 0
        for milestone_frac, milestone_label, milestone_title in milestones:
            milestone_target = current + int((target - current) * milestone_frac)
            # Find the first task whose follower_target is >= milestone_target
            inserted = False
            while next_task_idx < total_tasks:
                task = approved[next_task_idx]
                if task["_follower_target"] >= milestone_target:
                    # Insert station before this task
                    await _insert_station(
                        session,
                        tenant_id=tenant_id,
                        roadmap_id=roadmap_id,
                        order_in_branch=order_idx,
                        label=milestone_label,
                        title=milestone_title,
                        target=milestone_target,
                    )
                    order_idx += 1
                    inserted = True
                    break
                # Insert the task itself
                await _insert_task(
                    session,
                    tenant_id=tenant_id,
                    roadmap_id=roadmap_id,
                    order_in_branch=order_idx,
                    title=task.get("title", f"Vazifa {next_task_idx + 1}"),
                    type_=task.get("type", "reel"),
                    hook=task.get("hook") or task.get("goal_description"),
                    script_md=task.get("script_md") or task.get("scriptMd"),
                    shot_list=task.get("shot_list") or task.get("shotList") or [],
                    hashtags=task.get("hashtags") or [],
                    audio=task.get("audio_suggestion"),
                    drift=task.get("drift_score"),
                    follower_target=(
                        None
                        if (task.get("type") or "").lower() == "action"
                        else task["_follower_target"]
                    ),
                    hook_meta=task.get("hook_meta") or {},
                    predict_evidence=task.get("predict_evidence") or {},
                    funnel_stage=task.get("funnel_stage"),
                    cta_type=task.get("cta_type"),
                )
                order_idx += 1
                next_task_idx += 1

            if not inserted:
                # All tasks are below this milestone — insert station at the end
                await _insert_station(
                    session,
                    tenant_id=tenant_id,
                    roadmap_id=roadmap_id,
                    order_in_branch=order_idx,
                    label=milestone_label,
                    title=milestone_title,
                    target=milestone_target,
                )
                order_idx += 1

        # Insert any remaining tasks after the last station
        while next_task_idx < total_tasks:
            task = approved[next_task_idx]
            await _insert_task(
                session,
                tenant_id=tenant_id,
                roadmap_id=roadmap_id,
                order_in_branch=order_idx,
                title=task.get("title", f"Vazifa {next_task_idx + 1}"),
                type_=task.get("type", "reel"),
                # Same fallback as the interleave loop above — tasks landing after
                # the last station must not get a NULL hook for identical input.
                hook=task.get("hook") or task.get("goal_description"),
                script_md=task.get("script_md") or task.get("scriptMd"),
                shot_list=task.get("shot_list") or task.get("shotList") or [],
                hashtags=task.get("hashtags") or [],
                audio=task.get("audio_suggestion"),
                drift=task.get("drift_score"),
                follower_target=(
                    None
                    if (task.get("type") or "").lower() == "action"
                    else task["_follower_target"]
                ),
                hook_meta=task.get("hook_meta") or {},
                predict_evidence=task.get("predict_evidence") or {},
                funnel_stage=task.get("funnel_stage"),
                cta_type=task.get("cta_type"),
            )
            order_idx += 1
            next_task_idx += 1

        # Action tasks get checklist rows populated from their script_timeline.
        # The UI reads task_checklist_items via Prisma relation; without these
        # rows the action-task brief view shows no actionable steps.
        await _populate_action_checklists(session, tenant_id, roadmap_id, approved)

        # Activate the first non-station task so the dashboard has a
        # concrete "JORIY" node + the roadmap shows a clickable in_progress
        # card. Otherwise every task is 'planned' and the user lands on a
        # dashboard with nothing highlighted as the next action.
        await session.execute(
            text(
                """
                UPDATE content_tasks
                SET status = 'in_progress', "updatedAt" = NOW()
                WHERE id = (
                  SELECT id FROM content_tasks
                  WHERE "roadmapId" = :rid
                    AND "isStation" = false
                    AND status = 'planned'
                  ORDER BY "orderInBranch" ASC
                  LIMIT 1
                )
                """
            ),
            {"rid": roadmap_id},
        )
        await session.commit()

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=(
            f"Yo'l xaritasi tayyor — {len(approved)} ta vazifa va 3 ta Bekat. "
            "Birinchi vazifangiz JORIY deb belgilandi. Dashboard'ga o'tib ko'rishingiz mumkin."
        ),
        run_id=run_id,
        important=True,
    )

    return {
        "notes": [f"roadmap_persister: roadmap={roadmap_id[:8]} tasks={len(approved)}"],
    }


async def _update_single_task(state: GrowthCoachState, approved: list[dict[str, Any]]) -> dict[str, Any]:
    """Write scriptwriter output back to an existing ContentTask row."""
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    task_id = state.get("task_id")

    if not task_id:
        log.warning("roadmap_persister.content_review_missing_task_id", run_id=run_id)
        return {}

    task = approved[0]
    sm = get_sessionmaker()
    async with sm() as session:
        # Merge new fields with existing ones using COALESCE so we never
        # accidentally overwrite data with NULL.
        script_md = task.get("script_md") or task.get("scriptMd")
        shot_list = task.get("shot_list") or task.get("shotList") or []
        # The RICH scriptwriter emits camelCase "scriptTimeline"; older/template
        # paths use snake_case. Read both or the timed script is silently lost
        # (persisted as []), which left regenerate changing only the hook.
        script_timeline = (
            task.get("script_timeline") or task.get("scriptTimeline") or []
        )
        # Stage 7 — music beat-sheet + reel type. music_cues written
        # unconditionally (like shot_list) so a reel→action change clears stale
        # cues; reel_type via COALESCE so a missing value keeps the prior one.
        music_cues = task.get("music_cues") or task.get("musicCues") or []
        reel_type = task.get("reel_type") or task.get("reelType")
        ai_coach_note = task.get("ai_coach_note") or ""
        predict_evidence = task.get("predict_evidence") or task.get("predictEvidence") or {}
        hook_meta = task.get("hook_meta") or task.get("hookMeta") or {}
        hashtags = task.get("hashtags") or []
        audio = task.get("audio_suggestion") or task.get("audioSuggestion")
        hook = task.get("hook")
        format_str = task.get("format")
        publish_window = task.get("publish_window") or task.get("publishWindow")
        # Variant B — Claude RICH emits `hookVariantB` alongside the primary
        # hook. Pack it into `scriptVariantB` jsonb so the brief's A/B toggle
        # finally has data to render. We store the hook plus a copy of the
        # scriptMd/timeline so switching variants in the UI gives the user a
        # concrete second take (not just a different hook over the same body).
        # If Claude didn't emit a B hook, leave the column null — the UI
        # already keeps the toggle hidden when scriptVariantB is null.
        hook_variant_b = task.get("hookVariantB") or task.get("hook_variant_b")
        script_variant_b = None
        if hook_variant_b and isinstance(hook_variant_b, str) and hook_variant_b.strip():
            script_variant_b = json.dumps(
                {
                    "hook": hook_variant_b.strip(),
                    "scriptMd": script_md or "",
                    "scriptTimeline": script_timeline or [],
                },
                ensure_ascii=False,
            )
        # Creative sub-agent enrichment (hook_optimizer + caption_translator).
        # These ride along on the same task dict the creative chain mutated in
        # place; COALESCE keeps the existing value when a node failed soft.
        hook_variant_score = task.get("hookVariantScore")
        ig_caption = task.get("igCaption")

        await session.execute(
            text(
                """
                UPDATE content_tasks
                SET hook               = COALESCE(:hook, hook),
                    "scriptMd"         = COALESCE(:script_md, "scriptMd"),
                    "shotList"         = COALESCE(CAST(:shots AS jsonb), "shotList"),
                    "scriptTimeline"   = COALESCE(CAST(:timeline AS jsonb), "scriptTimeline"),
                    "musicCues"        = COALESCE(CAST(:music AS jsonb), "musicCues"),
                    "reelType"         = COALESCE(:reel_type, "reelType"),
                    "aiCoachNote"      = COALESCE(:coach_note, "aiCoachNote"),
                    "predictEvidence"  = COALESCE(CAST(:predict AS jsonb), "predictEvidence"),
                    "hookMeta"         = COALESCE(CAST(:hook_meta AS jsonb), "hookMeta"),
                    "scriptVariantB"   = COALESCE(CAST(:variant_b AS jsonb), "scriptVariantB"),
                    "hookVariantScore" = COALESCE(:hook_score, "hookVariantScore"),
                    "igCaption"        = COALESCE(:ig_caption, "igCaption"),
                    hashtags           = COALESCE(:hashtags, hashtags),
                    "audioSuggestion"  = COALESCE(:audio, "audioSuggestion"),
                    format             = COALESCE(:format, format),
                    "publishWindow"    = COALESCE(:publish_window, "publishWindow"),
                    status             = CASE WHEN status = 'revising' THEN :prev_status ELSE status END,
                    "updatedAt"        = NOW()
                WHERE id = :task_id AND "tenantId" = :tenant_id
                """
            ),
            {
                "task_id": task_id,
                "tenant_id": tenant_id,
                "hook": hook,
                "script_md": script_md,
                # validated_json raises ValidationError on a malformed LLM shape
                # HERE (debuggable) instead of letting it render as a silent zero
                # downstream; the original value is serialized unchanged.
                # These four are ALWAYS produced by the content_review enrichment
                # (defaulted to []/{} at read above), so write them UNCONDITIONALLY
                # — a falsy `if x else None` guard would convert a legit empty
                # []/{} to NULL, and the COALESCE would then keep STALE data (e.g.
                # a reel→action change left the old shots in place).
                "shots": validated_json(SHOT_LIST, shot_list),
                "timeline": validated_json(SCRIPT_TIMELINE, script_timeline),
                "music": validated_json(MUSIC_CUES, music_cues),
                "reel_type": reel_type,
                "coach_note": ai_coach_note if ai_coach_note else None,
                "predict": validated_json(PREDICT_EVIDENCE, predict_evidence),
                "hook_meta": validated_json(HOOK_META, hook_meta),
                "variant_b": script_variant_b,
                "hook_score": hook_variant_score,
                "ig_caption": ig_caption if ig_caption else None,
                "hashtags": hashtags if hashtags else None,
                "audio": audio,
                "format": format_str,
                "publish_window": publish_window,
                # Restore the status the task had BEFORE regenerate flipped it to
                # 'revising'. Without this, rewriting a 'planned' task promoted it
                # to 'in_progress', so it hijacked "Joriy topshiriq" (current
                # task) from the real active task.
                "prev_status": state.get("prev_status") or "in_progress",
            },
        )

        # For action tasks, refresh task_checklist_items from the updated
        # script_timeline. The UI reads these via Prisma relation; if we
        # don't refresh them on content_review, the user sees the old (or
        # empty) checklist after regenerating.
        if task.get("type") == "action" and script_timeline:
            # Replace existing checklist atomically.
            await session.execute(
                text('DELETE FROM task_checklist_items WHERE "taskId" = :task_id'),
                {"task_id": task_id},
            )
            for idx, step in enumerate(script_timeline):
                if not isinstance(step, dict):
                    continue
                body = (step.get("text") or "").strip()
                if not body:
                    continue
                await session.execute(
                    text(
                        """
                        INSERT INTO task_checklist_items
                          (id, "taskId", text, done, "orderIdx", "createdAt", "updatedAt")
                        VALUES (:id, :task_id, :body, false, :idx, NOW(), NOW())
                        """
                    ),
                    {
                        "id": uuid.uuid4().hex,
                        "task_id": task_id,
                        "body": body[:500],
                        "idx": idx,
                    },
                )

        await session.commit()

    log.info("roadmap_persister.content_review_updated",
             run_id=run_id, task_id=task_id)

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=(
            f"\"{task.get('title', 'Task')}\" brief'i yangilandi — "
            f"stsenariy, kadrlar va prognoz tayyor."
        ),
        run_id=run_id,
        important=True,
    )

    return {
        "notes": [f"roadmap_persister: updated brief for task {task_id}"],
    }


async def _populate_action_checklists(
    session: Any,
    tenant_id: str,
    roadmap_id: str,
    approved: list[dict[str, Any]],
) -> None:
    """Create task_checklist_items rows for every action task whose
    script_timeline carries checklist-style steps.

    Why: scriptwriter._enrich_action_task() writes the steps into the JSON
    column `scriptTimeline`, but the brief-view UI reads from the relation
    `task_checklist_items`. Without this bridge action tasks render empty.

    Looks up tasks by (tenant, roadmap, title) which is stable enough for
    a fresh persistence — titles inside a single roadmap are unique by
    construction.
    """
    for task in approved:
        if task.get("type") != "action":
            continue
        timeline = task.get("script_timeline") or task.get("scriptTimeline") or []
        # Sometimes script_timeline isn't populated yet — fall back to parsing
        # script_md inline so the checklist still appears.
        if not isinstance(timeline, list) or not timeline:
            from app.graphs.nodes.scriptwriter import _parse_action_md_to_checklist
            md = task.get("script_md") or task.get("scriptMd") or ""
            timeline = _parse_action_md_to_checklist(md) if md else []
        if not timeline:
            continue

        title = task.get("title") or ""
        # Find the row just inserted for this task.
        row = await session.execute(
            text(
                """
                SELECT id FROM content_tasks
                WHERE "tenantId" = :tid AND "roadmapId" = :rid
                  AND title = :title AND "isStation" = false
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tid": tenant_id, "rid": roadmap_id, "title": title},
        )
        task_id = row.scalar()
        if not task_id:
            continue

        for idx, step in enumerate(timeline):
            text_val = (step.get("text") if isinstance(step, dict) else None) or ""
            text_val = text_val.strip()
            if not text_val:
                continue
            await session.execute(
                text(
                    """
                    INSERT INTO task_checklist_items
                      (id, "taskId", text, done, "orderIdx", "createdAt", "updatedAt")
                    VALUES (:id, :task_id, :body, false, :idx, NOW(), NOW())
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "task_id": task_id,
                    "body": text_val[:500],
                    "idx": idx,
                },
            )


# Non-follower goal categories → the station subtitle is framed in the goal's
# own metric (a follower count would be the wrong yardstick for them). Keyed to
# the quartile fraction so each station reads as a progressive stage.
_GOAL_STATION_WORD = {
    "sales": "sotuv",
    "reach": "qamrov",
    "views": "ko'rishlar",
    "engagement": "faollik",
    "authority": "nufuz",
}
_FRAC_STAGE_UZ = {
    0.00: "tayyorlanish",
    0.25: "birinchi natijalar",
    0.50: "barqaror o'sish",
    0.75: "tezlashish",
    1.00: "maqsad",
}


def _station_title(target: int, goal: str | None = None, frac: float | None = None) -> str:
    # Goal-aware framing for non-follower goals (sales/reach/views/engagement/
    # authority): show the milestone as a stage in THAT metric, not a follower #.
    word = _GOAL_STATION_WORD.get((goal or "").lower())
    if word and frac is not None:
        stage = _FRAC_STAGE_UZ.get(frac, "bosqich")
        return f"{word} · {stage}"
    # Followers (or unknown goal) → the follower count IS the milestone.
    if target == 0:
        return "Boshlang'ich · tayyorlanish"
    if target >= 1_000_000:
        return f"{target / 1_000_000:.1f}M · maqsadli nuqta"
    if target >= 1000:
        return f"{round(target / 1000)}K · yangi bosqich"
    return f"{target} · bosqich"


async def _insert_station(
    session: Any,
    *,
    tenant_id: str,
    roadmap_id: str,
    order_in_branch: int,
    label: str,
    title: str,
    target: int,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO content_tasks
              (id, "tenantId", "roadmapId", "parentId", "orderInBranch", depth,
               title, type, status, "isStation", "stationLabel", "followerTarget",
               hashtags, "createdAt", "updatedAt")
            VALUES
              (:id, :tid, :rid, NULL, :order, 0, :title, 'reel', 'planned',
               true, :label, :target, ARRAY[]::text[], NOW(), NOW())
            """
        ),
        {
            "id": uuid.uuid4().hex,
            "tid": tenant_id,
            "rid": roadmap_id,
            "order": order_in_branch,
            "title": title,
            "label": label,
            "target": target,
        },
    )


async def _insert_task(
    session: Any,
    *,
    tenant_id: str,
    roadmap_id: str,
    order_in_branch: int,
    title: str,
    type_: str,
    hook: str | None,
    script_md: str | None,
    shot_list: list[dict],
    hashtags: list[str],
    audio: str | None,
    drift: float | None,
    follower_target: int,
    hook_meta: dict,
    predict_evidence: dict,
    funnel_stage: str | None = None,
    cta_type: str | None = None,
) -> None:
    await session.execute(
        text(
            # depth is HARD-CODED 0 (like _insert_station): parentId is NULL here (branching isn't
            # shipped), and every web/voice consumer (lib/roadmap/data.ts, voice tools) filters
            # WHERE depth=0 — so a depth>0 task would be silently orphaned/hidden (the coach counts
            # it, the page never shows it). Force a flat, visible roadmap until a real parent tree lands.
            """
            INSERT INTO content_tasks
              (id, "tenantId", "roadmapId", "parentId", "orderInBranch", depth,
               title, type, "nicheTag", "funnelStage", "ctaType", hook, "scriptMd",
               "shotList", hashtags, "audioSuggestion", status, "driftScore",
               "followerTarget", "hookMeta", "predictEvidence", "isStation",
               "createdAt", "updatedAt")
            VALUES
              (:id, :tid, :rid, NULL, :order, 0, :title, :type, NULL,
               :funnel, :cta, :hook, :script, CAST(:shots AS jsonb), :hashtags,
               :audio, 'planned', :drift, :target, CAST(:meta AS jsonb),
               CAST(:predict AS jsonb), false, NOW(), NOW())
            """
        ),
        {
            "id": uuid.uuid4().hex,
            "tid": tenant_id,
            "rid": roadmap_id,
            "order": order_in_branch,
            "title": title,
            "type": type_,
            "funnel": funnel_stage,
            "cta": cta_type,
            "hook": hook,
            "script": script_md,
            "shots": validated_json(SHOT_LIST, shot_list),
            "hashtags": hashtags,
            "audio": audio,
            "drift": drift,
            "target": follower_target,
            "meta": validated_json(HOOK_META, hook_meta),
            "predict": validated_json(PREDICT_EVIDENCE, predict_evidence),
        },
    )

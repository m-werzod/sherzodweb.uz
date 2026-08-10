"""Performance review — turns the tracker's per-post verdicts into dashboard
alerts the user can act on.

account_tracker (via detectors.py) already classified each observation with a
deterministic ``verdict`` (underperform / watch / norm / breakout). This node:

  - raises a tenant-wide ``underperform`` alert (with LLM-written causes + pivots)
    when posts genuinely underperformed against the tenant's own baseline, and
  - raises a per-post ``breakout`` alert so the user can double down on what hit.

We deliberately do NOT auto-regenerate the roadmap — the product principle is
"stay on the user's chosen path unless THEY approve a change". This node only
produces the recommendation; roadmap_generator picks it up on a user-triggered
``replan`` run.

The deterministic verdict is the source of truth for WHETHER to alert; the LLM
only supplies the human-readable causes/pivots. That split fixes the old bug
where the node went silent whenever the LLM happened to return no pivots — a real
underperformance now always surfaces.
"""
from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.graphs.nodes._alerts import has_open_alert, raise_alert
from app.integrations.llm.anthropic_client import call_claude
from app.memory.db import get_sessionmaker
from app.memory.knowledge_vault import save_note
from app.memory.vault_context import load_vault_context

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

_SYSTEM = """Sen Performance Review agentisan — strategik tahlilchi. Senga
foydalanuvchining kuzatilgan postlari beriladi: har birida metrikalar, qisqa
izoh va `verdict` (deterministik baho: underperform/watch/norm/breakout).

Vazifa — past natijali (underperform) postlarga e'tibor qaratib:
1. Asosiy sabablar (root_causes) — 2-4 ta qisqa.
2. Keyingi sikl uchun aniq, amaliy tavsiyalar (recommended_pivots) — 2-4 ta
   (nimani ko'paytirish, qaysi formatdan voz kechish). Agar breakout post bo'lsa,
   undan o'rganib, shu yondashuvni takrorlashni tavsiya qil.
3. 1-2 jumlali umumiy xulosa (summary).

JSON qaytar: {"root_causes": ["..."], "recommended_pivots": ["..."], "summary": "<1-2 jumla>"}
O'zbekcha, qisqa. Markdown yo'q, faqat JSON."""


def _slim_metrics(o: dict) -> dict:
    m = o.get("metrics") or {}
    return {k: m.get(k) for k in ("likes", "comments", "saves", "reach", "views")}


async def run(state: GrowthCoachState) -> dict:
    obs = state.get("tracker_observations") or []
    if not obs:
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    underperformers = [o for o in obs if o.get("verdict") == "underperform"]
    breakouts = [o for o in obs if o.get("verdict") == "breakout"]

    raised = 0
    breakout_raised = 0

    # ── Breakout opportunities (per-post, positive, no LLM needed) ──
    # raise_alert dedupes on (tenant, kind, taskId), so a post that stays in the
    # 14-day tracker window won't re-alert on every 6-hourly pulse.
    for o in breakouts:
        ok = await raise_alert(
            tenant_id=tenant_id,
            kind="breakout",
            severity="low",
            task_id=o.get("task_id"),
            summary_count=1,
            recommended_pivots=[
                "Shu post formatidan yana tayyorlang — auditoriya kuchli javob berdi."
            ],
            payload={"rates": o.get("rates") or {}, "metrics": _slim_metrics(o)},
            run_id=run_id,
        )
        raised += int(ok)
        breakout_raised += int(ok)

    # Stage 13 "viral mavzuni yo'l xaritaga qo'shish": a breakout's TOPIC is written to the vault as
    # a win-lesson. roadmap_generator reads the vault on a replan (load_vault_context) → the viral
    # topic organically drives continuation tasks, without auto-regenerating behind the user's back.
    followup_added = 0
    if breakout_raised:
        await _save_breakout_lesson(
            tenant_id, run_id, [o.get("task_id") for o in breakouts]
        )
        # Stage 13 — direct roadmap continuation. The vault win-lesson above only
        # surfaces on a replan; for users who opted INTO autonomy (autopilot), add
        # ONE planned follow-up task right now so a viral topic is continued
        # without waiting for a manual replan. Gated + deduped + announced.
        followup_added = await _maybe_add_breakout_followup(
            tenant_id, user_id, run_id, breakouts
        )

    # ── Underperformance (tenant-wide, needs LLM causes/pivots) ──
    synthesis: dict = {}
    if underperformers:
        # Skip the LLM entirely when an underperform banner is already open and
        # unactioned — it would only be deduped away after a wasted Sonnet call.
        if await has_open_alert(tenant_id, "underperform", None):
            log.info("performance_review.underperform_already_open", tenant_id=tenant_id)
        else:
            synthesis = await _synthesise(tenant_id, obs)
            pivots = [str(p) for p in (synthesis.get("recommended_pivots") or []) if p]
            # Stage 13 — "consider removing" CTA: a post that BOTH underperformed
            # AND drew strongly negative comments is a delete/hide candidate. Read
            # per-post sentiment and, if any qualify, prepend a concrete pivot to
            # the existing underperform banner (no new alert kind / UI needed).
            neg_by_task = await _negative_by_task(
                tenant_id, [u.get("task_id") for u in underperformers]
            )
            removal = _removal_pivot(underperformers, neg_by_task)
            if removal:
                pivots = [removal, *pivots]
            causes = synthesis.get("root_causes") or []
            summary = (synthesis.get("summary") or "").strip()
            det_count = len(underperformers)
            # high when it's a pattern: ≥3 underperformers, or ≥half of the posts
            # that actually got a verdict (exclude `norm` — a quiet post the
            # detector declined to judge shouldn't dilute "half the batch flopped").
            judged = sum(1 for o in obs if o.get("verdict", "norm") != "norm")
            severity = (
                "high"
                if det_count >= 3 or (judged and det_count * 2 >= judged)
                else "medium"
            )
            ok = await raise_alert(
                tenant_id=tenant_id,
                kind="underperform",
                severity=severity,
                summary_count=det_count,
                root_causes=causes,
                recommended_pivots=pivots,
                payload={"post_task_ids": [u.get("task_id") for u in underperformers]},
                run_id=run_id,
            )
            raised += int(ok)

            if ok:
                # Closed-loop memory: write what flopped / worked to the vault so the
                # scriptwriter (and a future replan) retrieve the lesson alongside
                # topics. Only when we actually opened an alert (avoids 6-hourly dupes).
                await _save_lesson(tenant_id, run_id, det_count, causes, pivots, summary)
                if summary:
                    await emit_message(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        agent="audience",
                        content=summary + (f" Tavsiya: {pivots[0]}" if pivots else ""),
                        run_id=run_id,
                        important=True,
                    )
    elif breakouts and raised:
        # Only good news this cycle — a short encouraging nudge (no LLM).
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="audience",
            content=f"{len(breakouts)} ta post breakout bo'ldi — bu formatdan ko'proq foydalaning!",
            run_id=run_id,
            important=True,
        )

    return {
        "performance_synthesis": synthesis,
        "notes": [
            f"performance_review: {len(underperformers)} under, "
            f"{len(breakouts)} breakout, {raised} alerts, {followup_added} followup tasks"
        ],
    }


# A post with negative sentiment at/above this % (and an underperform verdict)
# is a remove/hide candidate.
_NEG_REMOVE_THRESHOLD = 55


def _removal_pivot(underperformers: list[dict], neg_by_task: dict[str, int]) -> str | None:
    """Pure: if any underperforming post also drew ≥ threshold negative comments,
    return a concrete 'consider removing' pivot naming the worst one. None when no
    post qualifies (most cycles)."""
    worst_id: str | None = None
    worst_neg = -1
    for o in underperformers:
        tid = o.get("task_id")
        neg = int(neg_by_task.get(tid, 0)) if tid else 0
        if neg >= _NEG_REMOVE_THRESHOLD and neg > worst_neg:
            worst_neg, worst_id = neg, tid
    if not worst_id:
        return None
    return (
        "Bitta post past natija + kuchli salbiy izohlar oldi — uni o'chirish yoki "
        "yashirishni ko'rib chiqing (profil o'rtacha sifatini tushirmasin); yoki "
        "izohlarga ochiq javob bering."
    )


async def _negative_by_task(tenant_id: str, task_ids: list) -> dict[str, int]:
    """Map task_id → negative sentiment % from content_tasks.commentSentiment
    (written by comment_sentinel/post_analyzer). Best-effort → {}."""
    ids = [t for t in task_ids if t]
    if not ids:
        return {}
    out: dict[str, int] = {}
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            rows = (
                await session.execute(
                    text(
                        'SELECT id, "commentSentiment" FROM content_tasks '
                        'WHERE "tenantId" = :tid AND id = ANY(:ids) '
                        'AND "commentSentiment" IS NOT NULL'
                    ),
                    {"tid": tenant_id, "ids": ids},
                )
            ).mappings().all()
        for r in rows:
            data = r.get("commentSentiment")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    continue
            if isinstance(data, dict):
                try:
                    out[str(r["id"])] = int(data.get("negative") or 0)
                except (TypeError, ValueError):
                    continue
    except Exception:  # noqa: BLE001 — best-effort enrichment
        log.warning("performance_review.negative_by_task_failed", exc_info=True)
    return out


def _top_breakout(breakouts: list[dict]) -> dict | None:
    """The breakout with the strongest reach/views — the one worth continuing."""
    def _eng(o: dict) -> int:
        m = o.get("metrics") or {}
        return max(int(m.get("reach") or 0), int(m.get("views") or 0), int(m.get("likes") or 0))

    ranked = sorted([o for o in breakouts if o.get("task_id")], key=_eng, reverse=True)
    return ranked[0] if ranked else None


async def _maybe_add_breakout_followup(
    tenant_id: str, user_id: str | None, run_id: str, breakouts: list[dict]
) -> int:
    """If the tenant opted into autopilot, append ONE planned follow-up task that
    continues the strongest breakout topic. Deduped by title so the 6-hourly
    pulse can't pile up duplicates. Best-effort → 0 on any failure."""
    top = _top_breakout(breakouts)
    if not top:
        return 0
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            autopilot = (
                await session.execute(
                    text(
                        'SELECT "autopilotReplan" FROM onboarding_profiles '
                        'WHERE "tenantId" = :tid ORDER BY "createdAt" DESC LIMIT 1'
                    ),
                    {"tid": tenant_id},
                )
            ).scalar()
            if not autopilot:
                return 0

            src = (
                await session.execute(
                    text(
                        'SELECT title, type, "roadmapId" FROM content_tasks '
                        'WHERE "tenantId" = :tid AND id = :id'
                    ),
                    {"tid": tenant_id, "id": top.get("task_id")},
                )
            ).mappings().first()
            if not src or not src.get("title"):
                return 0

            # Prefer the SAME roadmap the breakout lives on; fall back to the
            # tenant's active roadmap.
            roadmap_id = src.get("roadmapId")
            if not roadmap_id:
                roadmap_id = (
                    await session.execute(
                        text(
                            "SELECT id FROM roadmaps WHERE \"tenantId\" = :tid "
                            "AND status = 'active' ORDER BY version DESC LIMIT 1"
                        ),
                        {"tid": tenant_id},
                    )
                ).scalar()
            if not roadmap_id:
                return 0

            new_title = f"{str(src['title'])[:120]} — davomi"
            exists = (
                await session.execute(
                    text(
                        'SELECT 1 FROM content_tasks '
                        'WHERE "tenantId" = :tid AND title = :title LIMIT 1'
                    ),
                    {"tid": tenant_id, "title": new_title},
                )
            ).scalar()
            if exists:
                return 0

            next_order = int(
                (
                    await session.execute(
                        text(
                            'SELECT COALESCE(MAX("orderInBranch"), 0) + 1 '
                            'FROM content_tasks WHERE "roadmapId" = :rid'
                        ),
                        {"rid": roadmap_id},
                    )
                ).scalar()
                or 1
            )

            await session.execute(
                text(
                    """
                    INSERT INTO content_tasks
                      (id, "tenantId", "roadmapId", "parentId", "orderInBranch", depth,
                       title, type, status, "isStation", "followerTarget",
                       "shotList", hashtags, "hookMeta", "predictEvidence",
                       "createdAt", "updatedAt")
                    VALUES
                      (:id, :tid, :rid, NULL, :order, 0, :title, :type, 'planned',
                       false, 0, '[]'::jsonb, '{}'::text[], '{}'::jsonb, '{}'::jsonb,
                       NOW(), NOW())
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "tid": tenant_id,
                    "rid": roadmap_id,
                    "order": next_order,
                    "title": new_title,
                    "type": str(src.get("type") or "reel"),
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — autonomous add is best-effort
        log.warning("performance_review.breakout_followup_failed", exc_info=True)
        return 0

    # Transparency: an autonomous roadmap change MUST be announced.
    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="audience",
        content=(
            f"🚀 \"{str(src['title'])[:60]}\" breakout bo'ldi — avtopilot yo'l xaritaga "
            f"davomini (yangi vazifa) qo'shdi."
        ),
        run_id=run_id,
        important=True,
    )
    return 1


async def _synthesise(tenant_id: str, obs: list[dict]) -> dict:
    """Ask Sonnet for causes + pivots across the batch (verdicts included so it can
    contrast winners vs losers). Reads past-cycle lessons from the vault so it
    builds on history instead of repeating last cycle's advice. Best-effort."""
    compact = [
        {
            "task_id": o.get("task_id"),
            "verdict": o.get("verdict", "norm"),
            "metrics": _slim_metrics(o),
            "note": o.get("audience_reaction_summary", ""),
        }
        for o in obs
    ]
    vault = await load_vault_context(
        tenant_id,
        "o'tmish sikl saboqlari past natija strategiya tavsiya",
        "O'TMISH SABOQLARI (bularni TAKRORLAMA — ularga asoslanib YANGI tavsiya ber)",
    )
    try:
        resp, _ledger = await call_claude(
            model="claude-sonnet-4-6",
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps({"posts": compact}, ensure_ascii=False) + vault,
                }
            ],
            max_tokens=900,
            response_format="json",
            agent_name="performance_review",
        )
        return json.loads(resp.get("text") or "{}")
    except Exception as exc:  # noqa: BLE001
        log.warning("performance_review.synthesis_failed", error=str(exc)[:120])
        return {}


async def _task_titles(tenant_id: str, task_ids: list) -> list[str]:
    """Titles of the given content tasks (tenant-scoped) — so a breakout lesson names the actual
    topics that hit, making it retrievable by keyword when the scriptwriter/roadmap read the vault."""
    ids = [t for t in task_ids if t]
    if not ids:
        return []
    sm = get_sessionmaker()
    async with sm() as session:
        rows = (
            await session.execute(
                text('SELECT title FROM content_tasks WHERE "tenantId"=:tn AND id = ANY(:ids)'),
                {"tn": tenant_id, "ids": ids},
            )
        ).scalars().all()
    return [str(r) for r in rows if r]


async def _save_breakout_lesson(tenant_id: str, run_id: str, task_ids: list) -> None:
    """Write the viral topics to the vault as a WIN lesson so a later replan continues them."""
    try:
        titles = await _task_titles(tenant_id, task_ids)
        if not titles:
            return
        await save_note(
            tenant_id=tenant_id,
            title="Breakout — uchgan mavzular",
            body=(
                "Bu mavzu/format auditoriyada KUCHLI ishladi (breakout): "
                + "; ".join(titles[:5])
                + ". Yo'l xaritada shu yo'nalishni DAVOM ettir — o'xshash mavzu/formatda yana post tayyorla."
            ),
            kind="lessons_learned",
            tags=["breakout", "win", "continue"],
            source_task_id=f"breakout:{run_id}",
        )
    except Exception:  # noqa: BLE001 — vault write is best-effort
        log.warning("performance_review.breakout_vault_failed")


async def _save_lesson(
    tenant_id: str,
    run_id: str,
    underperformed: int,
    causes: list,
    pivots: list,
    summary: str,
) -> None:
    try:
        body_parts = []
        if causes:
            body_parts.append(
                "Past natija sabablari: " + "; ".join(str(c) for c in causes[:4])
            )
        if pivots:
            body_parts.append("Keyingi siklga tavsiyalar: " + "; ".join(pivots[:4]))
        if summary:
            body_parts.append(summary)
        if not body_parts:
            return
        await save_note(
            tenant_id=tenant_id,
            title=f"Sikl natijalari ({underperformed} past post)",
            body=" ".join(body_parts),
            kind="lessons_learned",
            tags=["performance", "lesson"],
            source_task_id=f"perf:{run_id}",
        )
    except Exception:  # noqa: BLE001
        log.warning("performance_review.vault_failed")

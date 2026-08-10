"""Pulls fresh Instagram metrics for the user's recently-published tasks
and writes them back to ContentTask.actualMetrics so the rest of the
system can compare expected vs actual.

Two entry points share this node:

  A. /api/tasks/[id]/publish dispatches `tracker_pulse` with
     ``task_id`` + ``instagram_post_id`` (the shortcode the user pasted).
     We refresh just that one post.

  B. The 6-hour tracker_scheduler dispatches `tracker_pulse` per tenant
     with no task_id. We query content_tasks for everything published in
     the last 14 days for this tenant and refresh each one.

Either way, each fetched payload lands in ``content_tasks.actualMetrics``
(jsonb). That's the column the brief UI and the scriptwriter's hook bank
both read from — without this write, the "AI learns from actual
performance" promise was theatre. Prior to this fix the node read a
non-existent ``state.onboarding.recentlyPublishedPosts`` and dropped
observations into ephemeral state that never made it to the DB.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.graphs.detectors import classify_verdict, compute_rates, rolling_baseline
from app.graphs.goal_profiles import goal_kpi
from app.graphs.state import GrowthCoachState, TrackerObservation
from app.integrations.instagram.dispatcher import fetch_post_metrics
from app.integrations.llm import groq_client
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)


# How far back to look when the dispatch didn't specify a single task.
# IG insights drift after 30 days (Graph API quirk), so 14 covers the
# "still actively monitored" window without re-fetching ancient posts.
_BATCH_WINDOW_DAYS = 14
_BATCH_MAX_POSTS = 30

_ROOTCAUSE_SYS = """Sen Account Tracker agentisan — auditoriya reaktsiyasi tahlilchisi.
Senga foydalanuvchining oxirgi postlari (sarlavha + haqiqiy metrikalar:
like/comment/save/reach/views) beriladi. Har post uchun: u qanchalik yaxshi
ishlagani va EHTIMOLIY sabab (hook, format, mavzu yoki vaqt) — 1 jumla. Hamda
umumiy 1-2 jumlali xulosa + keyingi kontent uchun amaliy tavsiya.

Har post `verdict` (deterministik baho: underperform/watch/norm/breakout) bilan
keladi — uni inobatga ol. `goal_kpi` — foydalanuvchi MAQSADI uchun asosiy
ko'rsatkich(lar); tahlil va tavsiyani aynan shu KPI atrofida qur.

JSON qaytar: {"overall": "<1-2 jumla umumiy xulosa + tavsiya>", "per_task": [{"task_id": "<id>", "insight": "<1 jumla sabab>"}]}
O'zbekcha, qisqa. Markdown yo'q, faqat JSON."""


async def run(state: GrowthCoachState) -> dict:
    workflow = state.get("workflow") or ""
    # Other workflows (roadmap_generation, content_review, replan) walk
    # past this node on their way to persist — they have nothing to track.
    if workflow != "tracker_pulse":
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    targets = await _resolve_targets(state, tenant_id)
    if not targets:
        return {"notes": ["account_tracker: no published tasks to track"]}

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="audience",
        content=f"{len(targets)} ta postning metric'lari yangilanmoqda...",
        run_id=run_id,
    )

    observations: list[TrackerObservation] = []
    sm = get_sessionmaker()
    async with sm() as session:
        followers, baseline = await _load_followers_and_baseline(
            session, tenant_id, [t["task_id"] for t in targets]
        )
        for tgt in targets:
            task_id = tgt["task_id"]
            post_id = tgt["post_id"]
            # Prefer the OFFICIAL metrics the web's refresh-insights cron already
            # wrote (Graph reach/views/saves/likes/comments). The instagrapi scraper
            # is the datacenter-IP-blocked fallback — used only when official is
            # absent, and its result must not clobber good official data.
            official = _coerce_metrics(tgt.get("actual_metrics"))
            if official and _has_real_metrics(official):
                metrics = official  # already persisted by the cron — no DB write
            else:
                try:
                    metrics = await fetch_post_metrics(post_id)
                except Exception as exc:  # noqa: BLE001
                    # IG scraping is flaky; one bad post must not block the batch.
                    log.warning(
                        "account_tracker.fetch_failed",
                        task_id=task_id,
                        post_id=post_id,
                        error=str(exc)[:160],
                    )
                    continue

                try:
                    await session.execute(
                        text(
                            """
                            UPDATE content_tasks
                            SET "actualMetrics" = CAST(:metrics AS jsonb),
                                "updatedAt" = NOW()
                            WHERE id = :task_id AND "tenantId" = :tid
                            """
                        ),
                        {
                            "task_id": task_id,
                            "tid": tenant_id,
                            "metrics": json.dumps(metrics),
                        },
                    )
                except Exception:  # noqa: BLE001
                    log.exception(
                        "account_tracker.db_write_failed",
                        task_id=task_id,
                    )
                    continue

            rates = compute_rates(metrics, followers)
            verdict = classify_verdict(rates, baseline, int(metrics.get("comments") or 0))
            observations.append(
                TrackerObservation(
                    task_id=task_id,
                    instagram_post_id=post_id,
                    metrics=metrics,
                    audience_reaction_summary="",  # filled in by the root-cause pass
                    observed_at=_now(),
                    verdict=verdict,
                    rates=rates,
                )
            )

        await session.commit()

    if observations:
        # Root-cause pass: compare each post's actual numbers against its title
        # and surface WHY it performed as it did (Haiku). This turns the tracker
        # from a silent metric-writer into an agent — it fills each
        # observation's audience_reaction_summary + emits the headline insight.
        await _root_cause_pass(
            tenant_id, user_id, run_id, observations, goal_kpi(state.get("north_star") or {})
        )

    log.info(
        "account_tracker.observed",
        tenant_id=tenant_id,
        attempted=len(targets),
        succeeded=len(observations),
    )

    return {
        "tracker_observations": observations,
        "notes": [
            f"account_tracker: wrote actualMetrics for {len(observations)}/"
            f"{len(targets)} posts"
        ],
    }


def _coerce_metrics(raw: object) -> dict | None:
    """actualMetrics jsonb comes back as a dict (asyncpg) or occasionally a JSON
    string — normalise to a dict, or None when absent/unparseable."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            v = json.loads(raw)
        except Exception:  # noqa: BLE001
            return None
        return v if isinstance(v, dict) else None
    return None


def _has_real_metrics(m: dict) -> bool:
    """True when the official cron actually populated something (not an empty/zero
    placeholder) — so we use it instead of falling back to the scraper."""
    return any(int(m.get(k) or 0) > 0 for k in ("reach", "views", "plays", "likes", "comments"))


async def _resolve_targets(
    state: GrowthCoachState, tenant_id: str
) -> list[dict]:
    """Returns the targets we should refresh this run, each carrying any OFFICIAL
    metrics the web's refresh-insights cron already wrote (so we prefer those over
    the scraper).

    Single-task path: when /publish dispatches with task_id + post_id, just
    that one. Batch path: tracker_scheduler hits us with nothing — we read
    the recently-published-task slate from the DB ourselves.
    """
    single_task = state.get("task_id")
    single_post = state.get("instagram_post_id")
    if single_task and single_post:
        return [{"task_id": single_task, "post_id": single_post, "actual_metrics": None}]

    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                SELECT id AS task_id, "instagramPostId" AS post_id,
                       "actualMetrics" AS actual_metrics
                FROM content_tasks
                WHERE "tenantId" = :tid
                  AND status = 'published'
                  AND "instagramPostId" IS NOT NULL
                  AND "instagramPostId" <> ''
                  AND "publishedAt" > NOW() - (CAST(:window_days AS int) || ' days')::interval
                ORDER BY "publishedAt" DESC
                LIMIT :max_posts
                """
            ),
            {
                "tid": tenant_id,
                "window_days": _BATCH_WINDOW_DAYS,
                "max_posts": _BATCH_MAX_POSTS,
            },
        )
        return [
            {
                "task_id": str(r["task_id"]),
                "post_id": str(r["post_id"]),
                "actual_metrics": r["actual_metrics"],
            }
            for r in rows.mappings().all()
        ]


async def _load_followers_and_baseline(
    session, tenant_id: str, exclude_ids: list[str]
) -> tuple[int, dict]:
    """Follower count + a rolling baseline of recent published-post rates, so the
    detector judges each new post against the tenant's OWN history. Empty baseline
    (new account / no history) → classify_verdict returns 'norm' (no false alarms).
    Best-effort: any failure → (0, {}) and verdicts default to 'norm'."""
    followers = 0
    baseline: dict = {}
    try:
        frow = (
            await session.execute(
                text(
                    'SELECT "followerCount" FROM instagram_accounts '
                    'WHERE "tenantId" = :tid ORDER BY "updatedAt" DESC LIMIT 1'
                ),
                {"tid": tenant_id},
            )
        ).first()
        if frow and frow[0] is not None:
            followers = int(frow[0])

        rows = await session.execute(
            text(
                """
                SELECT "actualMetrics" FROM content_tasks
                WHERE "tenantId" = :tid AND status = 'published'
                  AND "actualMetrics" IS NOT NULL
                  AND NOT (id = ANY(:ex))
                ORDER BY "publishedAt" DESC NULLS LAST
                LIMIT 30
                """
            ),
            {"tid": tenant_id, "ex": exclude_ids or [""]},
        )
        history: list[dict] = []
        for r in rows.mappings().all():
            m = r["actualMetrics"]
            if isinstance(m, str):
                try:
                    m = json.loads(m)
                except Exception:  # noqa: BLE001
                    m = None
            if isinstance(m, dict):
                history.append(compute_rates(m, followers))
        baseline = rolling_baseline(history)
    except Exception as exc:  # noqa: BLE001
        log.warning("account_tracker.baseline_failed", error=str(exc)[:120])
    return followers, baseline


async def _root_cause_pass(
    tenant_id: str,
    user_id: str | None,
    run_id: str,
    observations: list[TrackerObservation],
    kpis: list[str],
) -> None:
    """Asks Haiku why each tracked post performed as it did, fills each
    observation's audience_reaction_summary in place, and emits the headline
    insight. Best-effort — the metric write already succeeded, so any failure
    here just falls back to a plain like-count message."""
    task_ids = [o["task_id"] for o in observations]
    titles: dict[str, str] = {}
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            rows = await session.execute(
                text('SELECT id, title FROM content_tasks WHERE "tenantId" = :tid AND id = ANY(:ids)'),
                {"tid": tenant_id, "ids": task_ids},
            )
            titles = {str(r["id"]): str(r["title"]) for r in rows.mappings().all()}
    except Exception as exc:  # noqa: BLE001
        log.warning("account_tracker.title_fetch_failed", error=str(exc)[:120])

    compact = [
        {
            "task_id": o["task_id"],
            "title": titles.get(o["task_id"], ""),
            "verdict": o.get("verdict", "norm"),
            "metrics": {
                k: o.get("metrics", {}).get(k)
                for k in ("likes", "comments", "saves", "reach", "views")
            },
        }
        for o in observations
    ]

    overall = ""
    try:
        parsed = await groq_client.chat_json(
            system=_ROOTCAUSE_SYS,
            user=json.dumps({"posts": compact, "goal_kpi": kpis}, ensure_ascii=False),
            max_tokens=700,
            agent_name="account_tracker",
        )
        overall = (parsed.get("overall") or "").strip()
        per = {
            str(p.get("task_id")): (p.get("insight") or "").strip()
            for p in parsed.get("per_task", [])
        }
        for o in observations:
            summary = per.get(o["task_id"], "")
            if summary:
                o["audience_reaction_summary"] = summary
    except Exception as exc:  # noqa: BLE001
        log.warning("account_tracker.root_cause_failed", error=str(exc)[:120])

    if overall:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="audience",
            content=overall,
            run_id=run_id,
            important=True,
        )
    else:
        total_likes = sum(int(o.get("metrics", {}).get("likes", 0)) for o in observations)
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="audience",
            content=f"{len(observations)} ta post yangilandi · jami {total_likes} like.",
            run_id=run_id,
            important=True,
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()

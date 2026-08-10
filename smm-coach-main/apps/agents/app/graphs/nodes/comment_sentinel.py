"""Comment Sentinel — Groq Llama reads a published post's recent comments and
summarises audience sentiment: {positive, negative, neutral, topThemes[]}.

Runs as the `comment_sentinel_pulse` workflow, fired ~24h after a post goes
live (the tracker_scheduler can enqueue it). Two entry shapes, like
account_tracker:

  A. Single post: dispatch with `instagram_post_id` (+ optional `task_id`).
  B. Batch: no post id → we read recently-published tasks for the tenant.

Writes:
  - `instagram_posts.commentSentiment` + `sentimentObservedAt`
  - `content_tasks.commentSentiment` (when the post maps to a task)

Comments come from `instagrapi` via the dispatcher (no OAuth token needed).
Fail-soft: a post with no comments, or a Groq error, just records an empty
summary and moves on — never blocks the batch.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.graphs.detectors import detect_negative_wave
from app.graphs.lead_detector import detect_leads
from app.graphs.nodes._alerts import raise_alert
from app.integrations import email_notify, telegram
from app.integrations.instagram.dispatcher import fetch_recent_comments
from app.integrations.llm import groq_client
from app.memory.db import get_sessionmaker
from app.memory.knowledge_vault import save_note

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

_BATCH_WINDOW_DAYS = 14
_BATCH_MAX_POSTS = 20
_MAX_COMMENTS = 30

_SYS = """Sen Comment Sentinel agentisan — auditoriya izohlari tahlilchisi.
Senga bitta Instagram postning izohlari (matn ro'yxati) beriladi.

JSON qaytar:
{
  "positive": <0-100 foiz>,
  "negative": <0-100 foiz>,
  "neutral": <0-100 foiz>,
  "topThemes": ["<2-5 ta asosiy mavzu/savol, o'zbekcha qisqa>"],
  "summary": "<1 jumla umumiy xulosa + agar ko'p so'ralsa, nima qo'shish kerakligi>"
}
Foizlar yig'indisi ~100 bo'lsin. Markdown yo'q, faqat JSON."""


async def run(state: GrowthCoachState) -> dict:
    if state.get("workflow") != "comment_sentinel_pulse":
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    targets = await _resolve_targets(state, tenant_id)
    if not targets:
        return {"notes": ["comment_sentinel: no published posts to scan"]}

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="audience",
        content=f"{len(targets)} ta postning izohlari tahlil qilinmoqda...",
        run_id=run_id,
    )

    sm = get_sessionmaker()
    scanned = 0
    leads_found = 0
    last_summary: dict | None = None
    # Posts that tripped the negative-comment-wave detector. We raise their alerts
    # AFTER the sentiment is committed, so a user who clicks the banner finds the
    # commentSentiment already persisted.
    waves: list[dict] = []
    async with sm() as session:
        # Load the blogger's persona ONCE so lead-reply drafts sound like the actual
        # user (niche + brand voice), not a generic bot. Best-effort → '' if missing.
        persona = await _load_persona(session, tenant_id)
        for tgt in targets:
            post_id = tgt["post_id"]
            task_id = tgt.get("task_id")
            try:
                comments = await fetch_recent_comments(post_id, limit=_MAX_COMMENTS)
            except Exception as exc:  # noqa: BLE001
                log.warning("comment_sentinel.fetch_failed", post_id=post_id, error=str(exc)[:120])
                continue

            records = _extract_records(comments)
            texts = [r["text"] for r in records]
            n_comments = len(texts)
            if not texts:
                # No comment text (dev mode / empty) — record an explicit empty.
                summary = {"positive": 0, "negative": 0, "neutral": 0, "topThemes": [], "summary": ""}
            else:
                summary = await _analyze(texts)

            last_summary = summary
            await _persist(session, tenant_id, post_id, task_id, summary)
            scanned += 1

            # Stage 12 — autonomous sales funnel: flag comments with buying intent
            # as `leads` rows with an AI-drafted reply the user can send from
            # ChatPlace. Best-effort: a lead-detector failure never blocks the pulse.
            if records:
                try:
                    leads = await detect_leads(texts, persona=persona)
                    leads_found += await _persist_leads(
                        session, tenant_id, post_id, task_id, records, leads
                    )
                except Exception:  # noqa: BLE001
                    log.exception("comment_sentinel.lead_persist_failed", post_id=post_id)

            if detect_negative_wave(summary, total_comments=n_comments):
                waves.append(
                    {"task_id": (task_id or None), "summary": summary, "n": n_comments}
                )

        await session.commit()

    # Negative-wave alerts (per-post). raise_alert dedupes on (tenant, kind,
    # taskId), so a post lingering in the 14-day batch window won't re-alert.
    waves_raised = 0
    for w in waves:
        s = w["summary"]
        neg = int(s.get("negative") or 0)
        ok = await raise_alert(
            tenant_id=tenant_id,
            kind="negative_wave",
            severity="high" if neg >= 50 else "medium",
            task_id=w["task_id"],
            summary_count=w["n"],
            root_causes=s.get("topThemes") or [],
            recommended_pivots=[
                "Izohlardagi asosiy e'tirozga javob bering yoki tushuntiruvchi kontent tayyorlang."
            ],
            payload={
                "sentiment": {k: s.get(k) for k in ("positive", "negative", "neutral")},
                "topThemes": s.get("topThemes") or [],
                "comments_analyzed": w["n"],
            },
            run_id=run_id,
        )
        waves_raised += int(ok)

    # Closed-loop memory (symmetric to breakout win-lessons): when a real
    # negative wave surfaced this cycle, write its recurring objections to the
    # vault so the scriptwriter + a future replan retrieve "what triggered
    # backlash" and steer around it. Only on a freshly-raised alert (waves_raised
    # > 0) so the 6-hourly batch can't spam duplicate lessons.
    if waves_raised:
        await _save_negative_lesson(tenant_id, run_id, waves)

    if last_summary and last_summary.get("summary"):
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="audience",
            content=last_summary["summary"],
            run_id=run_id,
            important=True,
        )

    # New-leads nudge — one consolidated message so the user opens ChatPlace and
    # sends the drafted replies while the comments are fresh. The leads surface
    # (badge + /leads) is the durable record; this is just the heads-up.
    if leads_found:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="audience",
            content=(
                f"🟢 {leads_found} ta yangi LID topildi — izohlarda sotuv/qiziqish signali bor. "
                f"ChatPlace'da tayyor javoblarni ko'rib, yuboring."
            ),
            run_id=run_id,
            important=True,
        )
        # Real-time push so the owner can act on a hot sales lead immediately,
        # not only when they next open the app. No-op when Telegram is unset.
        telegram.send(
            f"🟢 {leads_found} ta yangi LID · sotuv/qiziqish izohlari · /leads bo'limini oching"
        )
        # Email is a second, universal channel (Telegram needs the bot configured).
        # No-op when SMTP/owner-email is unset — never blocks the pulse.
        owner_email = await _owner_email(tenant_id)
        if owner_email:
            await email_notify.send(
                owner_email,
                f"🟢 {leads_found} ta yangi lid — SMM Coach",
                f"Postlaringiz izohlarida {leads_found} ta yangi sotuv/qiziqish signali topildi.\n\n"
                f"ChatPlace'dagi /leads bo'limini ochib, AI tayyorlagan javoblarni yuboring:\n"
                f"https://smm.brotech.uz/leads\n",
            )

    log.info(
        "comment_sentinel.done",
        tenant_id=tenant_id,
        scanned=scanned,
        targets=len(targets),
        waves=waves_raised,
        leads=leads_found,
    )
    return {
        "comment_sentiment": last_summary or {},
        "notes": [
            f"comment_sentinel: scanned {scanned}/{len(targets)} posts, "
            f"{waves_raised} negative-wave alerts, {leads_found} leads"
        ],
    }


async def _load_persona(session, tenant_id: str) -> str:
    """Short blogger-context block (niche + voice) so lead-reply drafts sound like the
    actual user. Best-effort → '' on any miss (lead_detector falls back to a generic
    reply, the pre-existing behaviour)."""
    try:
        row = await session.execute(
            text(
                """
                SELECT niche, "nicheDetail", "brandVoice"
                FROM onboarding_profiles WHERE "tenantId" = :tid
                ORDER BY "updatedAt" DESC LIMIT 1
                """
            ),
            {"tid": tenant_id},
        )
        r = row.first()
        if not r:
            return ""
        parts: list[str] = []
        if r.niche:
            parts.append(f"Soha: {r.niche}")
        if r.nicheDetail:
            parts.append(f"Yo'nalish: {r.nicheDetail}")
        if r.brandVoice:
            parts.append(f"Brend ovozi/uslubi: {str(r.brandVoice)[:300]}")
        return " · ".join(parts)
    except Exception as exc:  # noqa: BLE001
        log.warning("comment_sentinel.persona_load_failed", error=str(exc)[:120])
        return ""


async def _owner_email(tenant_id: str) -> str | None:
    """The tenant owner's email for alert notifications (own session — the nudge runs
    outside the scan session). Best-effort → None (no user / no email / DB hiccup)."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = await session.execute(
                text(
                    'SELECT email FROM users WHERE "tenantId" = :tid AND email IS NOT NULL '
                    'ORDER BY "createdAt" ASC LIMIT 1'
                ),
                {"tid": tenant_id},
            )
            email = row.scalar()
            return str(email) if email else None
    except Exception as exc:  # noqa: BLE001
        log.warning("comment_sentinel.owner_email_failed", error=str(exc)[:120])
        return None


async def _resolve_targets(state: GrowthCoachState, tenant_id: str) -> list[dict[str, str]]:
    single_post = state.get("instagram_post_id")
    single_task = state.get("task_id")
    if single_post:
        return [{"post_id": single_post, "task_id": single_task or ""}]

    sm = get_sessionmaker()
    async with sm() as session:
        rows = await session.execute(
            text(
                """
                -- Prefer the NUMERIC instagramMediaId (insights/comments edge); fall back
                -- to instagramPostId (shortcode) which _media_pk() now converts safely.
                SELECT id AS task_id,
                       COALESCE(NULLIF("instagramMediaId", ''), "instagramPostId") AS post_id
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
            {"tid": tenant_id, "window_days": _BATCH_WINDOW_DAYS, "max_posts": _BATCH_MAX_POSTS},
        )
        return [
            {"task_id": str(r["task_id"]), "post_id": str(r["post_id"])}
            for r in rows.mappings().all()
        ]


def _extract_records(comments: list[dict]) -> list[dict]:
    """Filter to comments with real text, keeping the metadata lead persistence
    needs (commenter handle + comment id). Index in this list is the stable key
    the lead detector returns, so the two must stay aligned."""
    out: list[dict] = []
    for c in comments:
        if not isinstance(c, dict):
            continue
        body = (c.get("text") or c.get("comment") or "").strip()
        if not body:
            continue
        out.append(
            {
                "text": body[:300],
                "user": (c.get("user") or c.get("username") or "") or None,
                "pk": (str(c.get("pk")) if c.get("pk") else (str(c.get("id")) if c.get("id") else None)),
            }
        )
    return out


async def _persist_leads(
    session,
    tenant_id: str,
    post_id: str,
    task_id: str | None,
    records: list[dict],
    leads: list[dict],
) -> int:
    """Upsert detected leads into `leads`. Dedupe key is (tenantId, commentId)
    when a comment id exists; instagrapi comments without a pk fall back to a
    deterministic synthetic id so re-scanning the same post in the 14-day batch
    window doesn't duplicate the same lead row."""
    written = 0
    for lead in leads:
        idx = lead.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(records):
            continue
        rec = records[idx]
        # Synthetic id for pk-less comments (mocks/dev/alt sources). MUST be a
        # STABLE hash — builtin hash() is per-process salted (PEP 456), so it
        # would change across run_worker restarts/replicas and the ON CONFLICT
        # dedup below would miss → duplicate leads + re-notification. blake2b
        # over user+text is deterministic everywhere.
        syn = hashlib.blake2b(
            f"{rec.get('user') or ''}|{rec['text']}".encode(), digest_size=8
        ).hexdigest()
        comment_id = rec.get("pk") or f"syn:{post_id}:{syn}"
        try:
            res = await session.execute(
                text(
                    """
                    INSERT INTO leads
                      ("id", "tenantId", "igUsername", "commentText", "intent",
                       "status", "taskId", "postId", "commentId", "draftReply",
                       "createdAt", "updatedAt")
                    VALUES
                      (:id, :tenant, :user, :ctext, :intent,
                       'new', :task, :post, :cid, :reply,
                       NOW(), NOW())
                    ON CONFLICT ("tenantId", "commentId") DO UPDATE
                      SET "draftReply" = EXCLUDED."draftReply",
                          "intent"     = EXCLUDED."intent",
                          "updatedAt"  = NOW()
                    RETURNING (xmax = 0) AS inserted
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "tenant": tenant_id,
                    "user": rec.get("user"),
                    "ctext": rec["text"],
                    "intent": lead.get("intent") or "lead",
                    "task": task_id or None,
                    "post": post_id,
                    "cid": comment_id,
                    "reply": lead.get("draftReply") or None,
                },
            )
            # xmax = 0 ⇒ this was a fresh INSERT, not an ON CONFLICT update.
            # Only fresh leads count toward the "new leads" nudge so a re-scan
            # of the same post in the batch window doesn't re-notify.
            row = res.first()
            if row and row[0]:
                written += 1
        except Exception:  # noqa: BLE001
            log.exception("comment_sentinel.lead_insert_failed", post_id=post_id, index=idx)
    return written


async def _analyze(texts: list[str]) -> dict:
    try:
        parsed = await groq_client.chat_json(
            system=_SYS,
            user=json.dumps({"comments": texts[:_MAX_COMMENTS]}, ensure_ascii=False),
            max_tokens=500,
            agent_name="comment_sentinel",
        )
        return {
            "positive": _pct(parsed.get("positive")),
            "negative": _pct(parsed.get("negative")),
            "neutral": _pct(parsed.get("neutral")),
            "topThemes": [str(t)[:80] for t in (parsed.get("topThemes") or [])][:5],
            "summary": (parsed.get("summary") or "").strip(),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("comment_sentinel.analyze_failed", error=str(exc)[:120])
        return {"positive": 0, "negative": 0, "neutral": 0, "topThemes": [], "summary": ""}


async def _persist(session, tenant_id: str, post_id: str, task_id: str | None, summary: dict) -> None:
    observed = _now()
    payload = json.dumps({**summary, "observedAt": observed}, ensure_ascii=False)
    try:
        await session.execute(
            text(
                """
                UPDATE instagram_posts
                SET "commentSentiment" = CAST(:s AS jsonb),
                    "sentimentObservedAt" = NOW()
                WHERE "postId" = :pid OR shortcode = :pid
                """
            ),
            {"s": payload, "pid": post_id},
        )
        if task_id:
            await session.execute(
                text(
                    """
                    UPDATE content_tasks
                    SET "commentSentiment" = CAST(:s AS jsonb),
                        "updatedAt" = NOW()
                    WHERE id = :tid AND "tenantId" = :tenant
                    """
                ),
                {"s": payload, "tid": task_id, "tenant": tenant_id},
            )
    except Exception:  # noqa: BLE001
        log.exception("comment_sentinel.persist_failed", post_id=post_id)


async def _save_negative_lesson(tenant_id: str, run_id: str, waves: list[dict]) -> None:
    """Write the recurring negative themes to the vault as a CAUTION lesson, so
    future scripts/replans avoid what triggered backlash. Best-effort."""
    themes: list[str] = []
    seen: set[str] = set()
    for w in waves:
        for t in (w.get("summary") or {}).get("topThemes") or []:
            key = str(t).strip().lower()
            if key and key not in seen:
                seen.add(key)
                themes.append(str(t).strip())
    if not themes:
        return
    try:
        await save_note(
            tenant_id=tenant_id,
            title="Salbiy to'lqin — qochish kerak bo'lgan mavzular",
            body=(
                "Izohlarda KUCHLI salbiy reaksiya keltirgan mavzular/e'tirozlar: "
                + "; ".join(themes[:6])
                + ". Keyingi kontentda bu nuqtalardan EHTIYOT bo'l — yoki ularni "
                "ochiq tushuntiruvchi post bilan yopib qo'y."
            ),
            kind="lessons_learned",
            tags=["negative_wave", "caution", "avoid"],
            source_task_id=f"negwave:{run_id}",
        )
    except Exception:  # noqa: BLE001 — vault write is best-effort
        log.warning("comment_sentinel.negative_vault_failed")


def _pct(val: object) -> int:
    try:
        return max(0, min(100, int(float(val))))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _now() -> str:
    return datetime.now(UTC).isoformat()

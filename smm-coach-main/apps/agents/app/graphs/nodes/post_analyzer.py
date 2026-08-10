"""post_analyzer — Faza 2: deep per-post analysis of the user's OWN posts.

Runs as the single node of the `onboarding_post_audit` workflow, AFTER the web
has synced the account (Faza 1: all posts + comments + mirrored media). For each
recent post it:

  1. VISION — hands the cover/thumbnail to Gemini and scores visual quality,
     hook strength, brand consistency (the thing caption-only analysis can't see).
  2. COMMENT SENTIMENT — reads the synced `instagram_comments` text and labels
     the audience reaction (positive/negative/neutral + themes).

Then it SYNTHESISES across posts into `instagram_accounts.deepAnalysis`
(weaknesses + visual patterns + audience insights + top performers) which
initial_analysis (Faza 3) reads to make the roadmap weakness-driven. Every
per-post insight is also written to the knowledge vault so nothing is re-derived.

Vision needs an ABSOLUTE image url; the mirrored `thumbnailUrl` is a relative
`/api/media/...` proxy path, so we read the original IG CDN url out of
`rawPayload` (still fresh — this runs minutes after the sync).
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.integrations.llm import groq_client
from app.integrations.llm.anthropic_client import call_claude
from app.integrations.llm.gemini_client import analyze_media, analyze_video
from app.memory.db import get_sessionmaker
from app.memory.knowledge_vault import save_note

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

# Vision is the expensive bit (Gemini). The product promise is "every post
# analysed", so default to 40 (covers a normal creator's whole catalogue).
# Tunable via POST_AUDIT_MAX_VISION — keep it generous on a paid Gemini tier
# (GEMINI_MIN_GAP_S≈0 → per-call latency negligible), lower it only if stuck on
# the free tier's ~7s/call gap where a huge back-catalogue would stall.
_MAX_VISION_POSTS = int(os.getenv("POST_AUDIT_MAX_VISION") or "40")
_MAX_COMMENTS = 40

_VISION_Q = (
    "Bu Instagram post muqovasi (cover/thumbnail). Uni baholab FAQAT JSON qaytar: "
    '{"summary":"<bir jumla: nima ko\'rsatilgan>","visualQuality":<1-10>,'
    '"hookStrength":<1-10>,"brandConsistency":<1-10>,"issues":["<vizual kamchilik>"]}. '
    "visualQuality — sifat/kompozitsiya; hookStrength — birinchi soniyada e'tibor "
    "tortishi; brandConsistency — brend uslubi izchilligi. O'zbekcha. Markdown yo'q."
)

# Same JSON shape as _VISION_Q (so the scoring is identical) but the model WATCHES
# the whole reel — pacing, hook over time, transitions, retention risk.
_VIDEO_Q = (
    "Bu Instagram reel/video. Uni boshidan oxirigacha TOMOSHA va TINGLA, baholab FAQAT JSON qaytar: "
    '{"summary":"<1-2 jumla: video davomida nima bo\'ladi, hook qanday ochiladi, '
    'sur\'at/pacing, o\'tishlar>","spokenHook":"<videoda AYTILGAN birinchi jumla — so\'zma-so\'z, '
    'agar nutq bo\'lmasa bo\'sh>","visualQuality":<1-10>,"hookStrength":<1-10 (birinchi 3s)>,'
    '"brandConsistency":<1-10>,"issues":["<retention xavfi yoki vizual kamchilik>"]}. '
    "spokenHook — aynan eshitilgan so\'zlar (foydalanuvchining o\'z ovozi/uslubi). O'zbekcha. Markdown yo'q."
)

_SENTIMENT_SYS = (
    "Sen izoh sentiment tahlilchisisan. Senga bir postning izohlari beriladi. "
    'FAQAT JSON qaytar: {"positive":<0-100>,"negative":<0-100>,"neutral":<0-100>,'
    '"topThemes":["<mavzu>"],"summary":"<bir jumla>"}. Foizlar yig\'indisi ~100. O\'zbekcha.'
)

_AGG_SYS = """Sen Instagram kontent strategisisan. Senga foydalanuvchining postlari
(vision tahlili + metrika + izoh sentimenti) beriladi. Butun akkaunt bo'yicha
tahlil qil va FAQAT JSON qaytar:
{"weaknesses":["..."],"visualPatterns":["..."],"audienceInsights":["..."],"topPerformers":["<shortcode> — <nega>"]}
- weaknesses: 3-6 ta ANIQ kamchilik (vizual sifat, hook, format, izoh asosida) — yo'l xaritasi shularni yechishi kerak.
- visualPatterns: takrorlanuvchi vizual naqshlar (yaxshi yoki yomon).
- audienceInsights: izohlardan auditoriya nima xohlashi/so'rashi.
- topPerformers: eng yaxshi 2-3 post va nega.
O'zbekcha, qisqa. Markdown yo'q, faqat JSON."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_json(raw: str) -> dict[str, Any]:
    """Gemini/Claude sometimes wrap JSON in ```fences``` — extract defensively."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _clamp(v: Any, lo: int = 0, hi: int = 10) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return 0


async def run(state: GrowthCoachState) -> dict:
    if state.get("workflow") != "onboarding_post_audit":
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    sm = get_sessionmaker()
    async with sm() as session:
        acc = (
            await session.execute(
                text(
                    'SELECT id FROM instagram_accounts WHERE "tenantId" = :tid '
                    'ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"tid": tenant_id},
            )
        ).scalar()
        if not acc:
            return {"notes": ["post_analyzer: no instagram account"]}

        rows = (
            await session.execute(
                text(
                    """
                    SELECT id, "postId", shortcode, caption, "mediaType",
                           "thumbnailUrl",
                           "rawPayload"->'media'->>'thumbnail_url' AS ig_thumb,
                           "rawPayload"->>'thumbnail_url'          AS scr_thumb,
                           "rawPayload"->'media'->>'media_url'     AS ig_video,
                           "rawPayload"->>'video_url'              AS scr_video,
                           "likeCount", "commentCount", reach, views,
                           "visionSummary", "contentQualityScore"
                    FROM instagram_posts
                    WHERE "instagramAccountId" = :acc
                    ORDER BY "postedAt" DESC NULLS LAST
                    LIMIT :lim
                    """
                ),
                {"acc": acc, "lim": _MAX_VISION_POSTS},
            )
        ).mappings().all()

    if not rows:
        return {"notes": ["post_analyzer: no posts to analyze"]}

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="audience",
        content=f"{len(rows)} ta postni chuqur tahlil qilyapman (vizual + izohlar)...",
        run_id=run_id,
    )

    analyzed: list[dict[str, Any]] = []
    vision_done = 0
    for row in rows:
        post_id = row["postId"]
        shortcode = row["shortcode"] or post_id
        entry: dict[str, Any] = {
            "shortcode": shortcode,
            "likes": row["likeCount"],
            "comments": row["commentCount"],
            "reach": row["reach"],
            "views": row["views"],
        }

        # 1) VISION — for reels, WATCH the actual video (pacing, hook over time,
        #    transitions); fall back to the cover frame. Bounded by _MAX_VISION_POSTS.
        is_video = (row["mediaType"] or "") in ("VIDEO", "2", "REEL")
        video_url = (
            next((u for u in (row["ig_video"], row["scr_video"]) if u and u.startswith("http")), None)
            if is_video
            else None
        )
        vision_url = next(
            (u for u in (row["ig_thumb"], row["scr_thumb"], row["thumbnailUrl"]) if u and u.startswith("http")),
            None,
        )
        already_vision = (row.get("visionSummary") or "").strip()
        if already_vision:
            # Idempotent: reuse a prior vision analysis instead of re-paying the
            # Gemini call on every resync tick (a single new post used to re-vision
            # the whole 40-post back-catalogue). The aggregation below still sees it.
            entry["vision"] = already_vision
            if row.get("contentQualityScore") is not None:
                entry["quality"] = int(row["contentQualityScore"])
        elif vision_done < _MAX_VISION_POSTS and (video_url or vision_url):
            raw = ""
            if video_url:
                raw = await analyze_video(
                    video_url=video_url, question=_VIDEO_Q, agent_name="post_analyzer", json_mode=True
                )
            if not raw and vision_url:
                raw = await analyze_media(
                    image_url=vision_url, question=_VISION_Q, agent_name="post_analyzer", json_mode=True
                )
            v = _parse_json(raw)
            if v:
                score = round(
                    (_clamp(v.get("visualQuality")) + _clamp(v.get("hookStrength")) + _clamp(v.get("brandConsistency")))
                    / 3
                    * 10
                )
                issues = "; ".join(str(i) for i in (v.get("issues") or [])[:3])
                # Capture the verbatim spoken hook (the user's OWN voice/phrasing)
                # so it flows into deepAnalysis → vault → scriptwriter, not just a
                # visual gist. Stage 2 "reel nutq" gap, via the audio Gemini already hears.
                spoken = str(v.get("spokenHook") or "").strip()
                summary = (
                    str(v.get("summary") or "").strip()
                    + (f' Aytilgan hook: "{spoken[:160]}"' if spoken else "")
                    + (f" Kamchilik: {issues}" if issues else "")
                ).strip()
                entry["vision"] = summary
                entry["quality"] = score
                vision_done += 1
                async with sm() as s2:
                    await s2.execute(
                        text(
                            'UPDATE instagram_posts SET "visionSummary" = :s, '
                            '"contentQualityScore" = :q, "visionAnalyzedAt" = NOW() '
                            'WHERE "postId" = :pid'
                        ),
                        {"s": summary[:1000], "q": score, "pid": post_id},
                    )
                    await s2.commit()

        # 2) COMMENT SENTIMENT from synced instagram_comments (empty pre-App-Review).
        async with sm() as s3:
            ctexts = [
                r["text"]
                for r in (
                    await s3.execute(
                        text(
                            'SELECT text FROM instagram_comments '
                            'WHERE "instagramPostId" = :pid LIMIT :lim'
                        ),
                        {"pid": row["id"], "lim": _MAX_COMMENTS},
                    )
                ).mappings().all()
                if (r["text"] or "").strip()
            ]
        if ctexts:
            try:
                parsed = await groq_client.chat_json(
                    system=_SENTIMENT_SYS,
                    user=json.dumps({"comments": ctexts}, ensure_ascii=False),
                    max_tokens=400,
                    agent_name="post_analyzer",
                )
                sent: dict[str, Any] = {
                    "positive": parsed.get("positive", 0),
                    "negative": parsed.get("negative", 0),
                    "neutral": parsed.get("neutral", 0),
                    "topThemes": [str(t)[:80] for t in (parsed.get("topThemes") or [])][:5],
                    "summary": str(parsed.get("summary") or "").strip(),
                }
                entry["sentiment"] = sent["summary"]
                entry["themes"] = sent["topThemes"]
                async with sm() as s4:
                    await s4.execute(
                        text(
                            'UPDATE instagram_posts SET "commentSentiment" = CAST(:s AS jsonb), '
                            '"sentimentObservedAt" = NOW() WHERE "postId" = :pid'
                        ),
                        {"s": json.dumps({**sent, "observedAt": _now()}, ensure_ascii=False), "pid": post_id},
                    )
                    await s4.commit()
            except Exception as exc:  # noqa: BLE001
                log.warning("post_analyzer.sentiment_failed", post_id=post_id, error=str(exc)[:120])

        analyzed.append(entry)

        # Per-post insight → vault (idempotent per post). Skip thin entries.
        if entry.get("vision") or entry.get("sentiment"):
            body = (
                f"Post {shortcode}: {entry.get('vision', '')} "
                f"Sentiment: {entry.get('sentiment', '')} "
                f"({entry.get('likes')} like, {entry.get('comments')} izoh)."
            ).strip()
            await save_note(
                tenant_id=tenant_id,
                title=f"Post tahlili: {shortcode}",
                body=body,
                kind="post_insight",
                tags=["post", "audit"],
                source_task_id=f"post:{post_id}",
            )

    # 3) AGGREGATE across posts → weaknesses (read by Faza 3 roadmap).
    qualities = [e["quality"] for e in analyzed if isinstance(e.get("quality"), int)]
    avg_quality = round(sum(qualities) / len(qualities)) if qualities else None
    deep: dict[str, Any] = {}
    try:
        resp, _ = await call_claude(
            model="claude-sonnet-4-6",
            system=_AGG_SYS,
            messages=[{"role": "user", "content": json.dumps({"posts": analyzed}, ensure_ascii=False)}],
            max_tokens=1100,
            response_format="json",
            agent_name="post_analyzer",
        )
        deep = _parse_json(resp.get("text") or "")
    except Exception as exc:  # noqa: BLE001
        log.warning("post_analyzer.aggregate_failed", error=str(exc)[:160])

    deep_analysis: dict[str, Any] = {
        "weaknesses": [str(w) for w in (deep.get("weaknesses") or [])][:6],
        "visualPatterns": [str(p) for p in (deep.get("visualPatterns") or [])][:5],
        "audienceInsights": [str(a) for a in (deep.get("audienceInsights") or [])][:5],
        "topPerformers": [str(t) for t in (deep.get("topPerformers") or [])][:3],
        "avgQuality": avg_quality,
        "analyzedPosts": len(analyzed),
        "visionPosts": vision_done,
        "analyzedAt": _now(),
    }
    async with sm() as s5:
        await s5.execute(
            text(
                'UPDATE instagram_accounts SET "deepAnalysis" = CAST(:d AS jsonb), '
                '"deepAnalyzedAt" = NOW() WHERE id = :acc'
            ),
            {"d": json.dumps(deep_analysis, ensure_ascii=False), "acc": acc},
        )
        await s5.commit()

    # Aggregate weaknesses → a single vault note so the scriptwriter retrieves
    # "what's weak about this account" alongside topics.
    if deep_analysis["weaknesses"]:
        await save_note(
            tenant_id=tenant_id,
            title="Akkaunt kamchiliklari (post audit)",
            body="Aniqlangan kamchiliklar: " + " • ".join(deep_analysis["weaknesses"]),
            kind="insight",
            tags=["weakness", "audit"],
            source_task_id="account:weaknesses",
        )

    if deep_analysis["weaknesses"]:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="audience",
            content=(
                f"{len(analyzed)} post tahlil qilindi. Asosiy kamchilik: "
                f"{deep_analysis['weaknesses'][0]}"
            ),
            run_id=run_id,
            important=True,
        )

    log.info(
        "post_analyzer.done",
        tenant_id=tenant_id,
        analyzed=len(analyzed),
        vision=vision_done,
        weaknesses=len(deep_analysis["weaknesses"]),
    )
    return {
        "deep_analysis": deep_analysis,
        "notes": [
            f"post_analyzer: {len(analyzed)} posts, {vision_done} vision, "
            f"{len(deep_analysis['weaknesses'])} weaknesses"
        ],
    }

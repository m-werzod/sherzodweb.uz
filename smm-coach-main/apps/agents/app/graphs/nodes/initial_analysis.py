"""Bootstraps the per-user north-star.

Pulls the Instagram profile snapshot, calls Sonnet to produce
strengths/weaknesses/opportunities + suggested content pillars, then
persists pillars to `content_pillars` so the dashboard shows them
immediately after onboarding.

Runs once when the user finishes onboarding.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.config import get_settings
from app.graphs.nodes._template_roadmap import synthesize_analysis
from app.graphs.prompt_store import resolve_prompt
from app.graphs.state import AccountSnapshot, CostLedger, GrowthCoachState
from app.integrations.instagram.dispatcher import fetch_account_snapshot
from app.integrations.llm.anthropic_client import call_claude
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

# A live IG profile fetch is best-effort: cap it so a dead scraper proxy
# (connect timeout=None → ~9 min of instagrapi retries) can't stall the whole
# roadmap run. On timeout/failure we fall back to onboarding-declared data.
_SNAPSHOT_TIMEOUT_S = 25


SYSTEM_PROMPT = """Sen Instagram'da o'sish bo'yicha tahlilchisan. Akkauntning hozirgi holatini, audutoriyasini, kontent uslubini va sohani o'rganib, foydalanuvchining maqsadiga yetishi uchun kuchli va zaif tomonlarni va kontent ustunlarini taklif ber. Faqat ko'rinadigan ma'lumotga tayan, taxminiy gap aytma.

JSON formatda ber:
{
  "strengths": string[],
  "weaknesses": string[],
  "opportunities": string[],
  "recommendedNiche": string,
  "audience": {
    "summary": string,
    "inferredAgeBand": string,
    "inferredLocations": string[],
    "activeHours": string[]
  },
  "pillars": [
    { "name": string, "sharePct": number, "rationale": string }
  ]
}

Pillars ro'yxati 4-5 element bo'lsin. sharePct yig'indisi 100 bo'lishi kerak."""


async def run(state: GrowthCoachState) -> dict:
    # content_review skips initial_analysis — it operates on a single existing
    # task and does not need profile re-analysis or pillar re-generation.
    # tracker_pulse skips it too: refreshing actualMetrics has nothing to do
    # with re-analysing the profile, and the Claude call here was firing on
    # every 6-hour scheduler tick for no benefit.
    if state.get("workflow") in ("content_review", "tracker_pulse"):
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    handle = state.get("onboarding", {}).get("instagramHandle")
    if not handle:
        return {"validation_errors": [{"node": "initial_analysis", "error": "missing instagramHandle"}]}

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="market",
        content=f"@{handle} profilini va so'nggi postlarini ko'rib chiqyapman.",
        run_id=run_id,
    )

    # Prefer the account data already synced from the Meta Graph API at OAuth
    # link time — it's the user's REAL profile (followers/bio/type), not a
    # login-less scrape that IG aggressively blocks from datacenter IPs. Only
    # when no Graph-synced row exists do we fall to the live instagrapi scrape.
    snapshot = await _snapshot_from_db(tenant_id, handle)
    if snapshot is None:
        # Best-effort: a live profile fetch must NOT crash the whole roadmap run.
        # The scraper proxy / instagrapi can be down (dead proxy, IG block, rate
        # limit) — when it is, fall back to a snapshot built from the onboarding
        # answers so initial_analysis + the rest of the chain still produce a
        # roadmap. Time-boxed so a hung proxy can't stall onboarding for minutes.
        try:
            snapshot = await asyncio.wait_for(
                fetch_account_snapshot(handle), timeout=_SNAPSHOT_TIMEOUT_S
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("initial_analysis.snapshot_failed_fallback", error=str(exc)[:160])
            snapshot = AccountSnapshot(
                handle=handle,
                follower_count=int((state.get("onboarding") or {}).get("currentFollowers") or 0),
                account_type="unknown",
            )

    north = state.get("north_star") or {}
    onboarding = state.get("onboarding") or {}

    # Try LLM first; if BOTH Claude AND Gemini are throttled/exhausted,
    # synthesize a deterministic analysis from the onboarding inputs so
    # the rest of the graph still has a `pillars` payload to persist.
    try:
        response, usage = await call_claude(
            model=get_settings().model_initial_analysis,
            system=await resolve_prompt("initial_analysis", SYSTEM_PROMPT),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Akkaunt: @{snapshot.get('handle')}\n"
                        f"Followers: {snapshot.get('follower_count')}\n"
                        f"Bio: {snapshot.get('bio') or '(yoʼq)'}\n"
                        f"Soha: {onboarding.get('niche')}\n"
                        f"Maqsad: {onboarding.get('targetFollowers')} obunachi "
                        f"({onboarding.get('targetAudience')})\n\n"
                        "JSON ber: strengths, weaknesses, opportunities, audience, pillars."
                    ),
                }
            ],
            max_tokens=2000,
            response_format="json",
            agent_name="initial_analysis",
        )
        parsed: dict = {}
        try:
            parsed = json.loads(response.get("text") or "{}")
        except json.JSONDecodeError:
            log.warning("initial_analysis.json_parse_failed", run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "initial_analysis.llm_failed — using template fallback",
            error=str(exc)[:120],
        )
        parsed = synthesize_analysis(
            niche=str(onboarding.get("niche") or "general"),
            target_audience=str(onboarding.get("targetAudience") or ""),
            current_followers=int(onboarding.get("currentFollowers") or 0),
        )
        response = {"text": json.dumps(parsed, ensure_ascii=False), "model": "template-fallback"}
        usage = CostLedger(input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0)

    # Empty `pillars` means the LLM returned a stub (no key) or didn't
    # follow the schema. Fall back to the template so the dashboard at
    # least has 4 content pillars to render.
    if not parsed.get("pillars"):
        log.info("initial_analysis.empty_pillars — synthesizing")
        synth = synthesize_analysis(
            niche=str(onboarding.get("niche") or "general"),
            target_audience=str(onboarding.get("targetAudience") or ""),
            current_followers=int(onboarding.get("currentFollowers") or 0),
        )
        parsed = {**parsed, **synth}

    pillars = parsed.get("pillars") or []
    if pillars:
        try:
            await _persist_pillars(tenant_id, pillars)
            await emit_message(
                tenant_id=tenant_id,
                user_id=user_id,
                agent="market",
                content=(
                    f"{len(pillars)} ta kontent ustuni aniqlandi: "
                    + ", ".join(p.get("name", "?") for p in pillars[:4])
                ),
                run_id=run_id,
                important=True,
            )
        except Exception:  # noqa: BLE001
            log.exception("initial_analysis.persist_pillars_failed")

    # On-demand niche seeding: ensure the Market Analyst has trend data for
    # THIS user's niche. Runs only here (onboarding) — there is no perpetual
    # seeding loop anymore.
    niche = str(onboarding.get("niche") or "").strip()
    if niche:
        try:
            from app.workers import knowledge_seeder

            if not await knowledge_seeder.niche_has_knowledge(niche):
                await emit_message(
                    tenant_id=tenant_id, user_id=user_id, agent="market",
                    content=f"{niche} sohasi uchun trend bazasini tayyorlayapman...",
                    run_id=run_id,
                )
                await knowledge_seeder.seed_niche(niche)
        except Exception:  # noqa: BLE001
            log.warning("initial_analysis.seed_niche_failed", niche=niche)

    # Quantitative cadence → roadmap size: a roadmap is the NEXT FEW WEEKS of content the user can
    # actually act on, NOT a task for every post until the goal deadline. Sizing on days-to-deadline
    # produced ~345 unusable tasks for an ambitious goal (1→100K) with a far date ("129-hafta" titles,
    # 690 rows across two runs). Clamp the horizon to ~3 weeks and the count to 8..28; the roadmap is
    # regenerated/extended as the user progresses. The onboarding wizard captures postsPerDay; if
    # absent, leave None so roadmap_generator uses its follower-gap heuristic.
    _HORIZON_DAYS = 21
    roadmap_size: int | None = None
    posts_per_day = onboarding.get("postsPerDay")
    if posts_per_day:
        days = _HORIZON_DAYS
        deadline_raw = onboarding.get("deadline")
        if deadline_raw:
            try:
                dl = datetime.fromisoformat(str(deadline_raw).replace("Z", "+00:00"))
                # Near-term focus — clamp to the horizon, NOT the full days-to-goal.
                days = max(7, min(_HORIZON_DAYS, (dl - datetime.now(dl.tzinfo or UTC)).days))
            except (ValueError, TypeError):
                days = _HORIZON_DAYS
        roadmap_size = max(8, min(28, round(float(posts_per_day) * days)))

    # Past-content awareness: the web /api/onboarding/analyze-posts wrote an
    # analysis of the user's existing posts to instagram_accounts.pastPostsAnalysis.
    # Pull the already-covered topics, seed them into the vault (so the
    # scriptwriter's retrieval knows them), and hand them to roadmap_generator
    # so the new roadmap doesn't repeat them.
    existing_topics: list[str] = []
    try:
        existing_topics, theme_summary = await _load_existing_topics(tenant_id)
        if existing_topics:
            await _seed_topic_vault(tenant_id, existing_topics, niche, theme_summary)
            await emit_message(
                tenant_id=tenant_id,
                user_id=user_id,
                agent="market",
                content=(
                    f"O'tmishdagi {len(existing_topics)} mavzuni bilim bazasiga yozdim — "
                    "yo'l xaritasi ularni takrorlamaydi."
                ),
                run_id=run_id,
            )
    except Exception:  # noqa: BLE001
        log.warning("initial_analysis.existing_topics_failed")

    # Faza 3 — post-audit weaknesses: post_analyzer (onboarding_post_audit) wrote
    # the account's concrete weaknesses + audience wants to
    # instagram_accounts.deepAnalysis. Feed them into the roadmap context so the
    # plan TARGETS them (not just avoids repeating topics) and surface them for
    # the scorer's addresses_weakness dimension.
    detected_weaknesses: list[str] = []
    audience_insights: list[str] = []
    try:
        detected_weaknesses, audience_insights = await _load_deep_analysis(tenant_id)
    except Exception:  # noqa: BLE001
        log.warning("initial_analysis.deep_analysis_failed")

    # Niche-derived FOUNDATION: seed the vault with coaching knowledge for the
    # niche (+ a profile note) so the scriptwriter's retrieval and the voice
    # coach have a real, embedded base from day one — even when the account's
    # past captions are sparse and yield few topics. Always runs.
    try:
        seeded = await _seed_niche_foundations(
            tenant_id,
            niche,
            str(onboarding.get("nicheDetail") or ""),
            str(onboarding.get("targetAudience") or ""),
            int(onboarding.get("currentFollowers") or 0),
            int(onboarding.get("targetFollowers") or 0),
        )
        if seeded:
            await emit_message(
                tenant_id=tenant_id,
                user_id=user_id,
                agent="writer",
                content=f"Soha bo'yicha {seeded} ta asos bilim eslatmasini bilim bazasiga qo'shdim.",
                run_id=run_id,
            )
    except Exception:  # noqa: BLE001
        log.warning("initial_analysis.niche_foundations_failed")

    # Psychological profile (Dizayn A) — captured during onboarding and copied
    # onto onboarding_profiles.psychProfile by /api/onboarding. Seed it into the
    # vault as insight notes so the scriptwriter/hook/caption agents pull the
    # user's voice, why, story and audience via related_notes. No-op when absent.
    try:
        psych = await _load_psych_profile(tenant_id)
        if psych:
            pn = await _seed_psych_notes(tenant_id, psych)
            if pn:
                await emit_message(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent="writer",
                    content=f"Shaxsiyat profilingdan {pn} ta eslatmani bilim bazasiga qo'shdim.",
                    run_id=run_id,
                )
    except Exception:  # noqa: BLE001
        log.warning("initial_analysis.psych_notes_failed")

    return {
        "account": snapshot,
        "north_star": {
            **north,
            "niche": onboarding.get("niche", north.get("niche", "")),
            "niche_detail": onboarding.get("nicheDetail", ""),
            "target_audience": onboarding.get("targetAudience", north.get("target_audience", "")),
            "current_followers": int(
                onboarding.get("currentFollowers", snapshot.get("follower_count", 0))
            ),
            "target_followers": int(onboarding.get("targetFollowers", 0)),
            "region": "uz",
            "roadmap_size": roadmap_size,
            # Goal taxonomy (Dizayn B) — carried from onboarding into north_star
            # so roadmap_generator can size the funnel. None → legacy behaviour.
            "primary_goal": onboarding.get("primaryGoal") or north.get("primary_goal"),
            "secondary_goal": onboarding.get("secondaryGoal") or north.get("secondary_goal"),
            "goal_weight": float(onboarding.get("goalWeight") or north.get("goal_weight") or 0.7),
        },
        "analysis_summary": _augment_analysis(
            response.get("text", ""), detected_weaknesses, audience_insights
        ),
        "existing_post_topics": existing_topics,
        "detected_weaknesses": detected_weaknesses,
        "cost": usage,
        "notes": [
            f"initial_analysis: synthesized for @{handle}, {len(pillars)} pillars"
            + (f", {len(detected_weaknesses)} weaknesses" if detected_weaknesses else "")
        ],
    }


def _augment_analysis(
    base: str, weaknesses: list[str], audience_insights: list[str]
) -> str:
    """Fold the post-audit findings into the analysis context so every roadmap
    prompt builder (regular + cadence-sized) tells Claude to SOLVE them."""
    out = base
    if weaknesses:
        out += (
            "\n\n--- POST AUDIT: AKKAUNTNING ANIQLANGAN KAMCHILIKLARI ---\n"
            + "\n".join(f"- {w}" for w in weaknesses[:6])
            + "\nYO'L XARITASI shu kamchiliklarni ANIQ yechishga qaratilsin — "
            "har bir kamchilik uchun uni bartaraf etadigan kontent rejalashtir."
        )
    if audience_insights:
        out += (
            "\n\n--- AUDITORIYA NIMA XOHLAYDI (izohlardan) ---\n"
            + "\n".join(f"- {a}" for a in audience_insights[:5])
        )
    return out


async def _load_deep_analysis(tenant_id: str) -> tuple[list[str], list[str]]:
    """Read the latest IG account's post-audit (post_analyzer wrote
    instagram_accounts.deepAnalysis) → (weaknesses, audienceInsights)."""
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text(
                    'SELECT "deepAnalysis" FROM instagram_accounts '
                    'WHERE "tenantId" = :tid AND "deepAnalysis" IS NOT NULL '
                    'ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"tid": tenant_id},
            )
        ).first()
    if not row or row[0] is None:
        return [], []
    data = row[0]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return [], []
    if not isinstance(data, dict):
        return [], []
    weaknesses = [str(w).strip() for w in (data.get("weaknesses") or []) if str(w).strip()][:6]
    audience = [str(a).strip() for a in (data.get("audienceInsights") or []) if str(a).strip()][:5]
    return weaknesses, audience


async def _snapshot_from_db(tenant_id: str, handle: str) -> AccountSnapshot | None:
    """Build the profile snapshot from the Graph-synced instagram_accounts row
    (real OAuth data) instead of a login-less scrape. Returns None when there's
    no genuinely-synced row (lastSyncedAt null) so the caller falls to scraping.
    Best-effort → None on any error."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = (
                await session.execute(
                    text(
                        'SELECT handle, "instagramUserId", "followerCount", "followingCount", '
                        '"postsCount", bio, "profileUrl", "isPrivate", "accountType", '
                        '"lastSyncedAt" FROM instagram_accounts '
                        'WHERE "tenantId" = :tid AND "lastSyncedAt" IS NOT NULL '
                        'ORDER BY "lastSyncedAt" DESC LIMIT 1'
                    ),
                    {"tid": tenant_id},
                )
            ).mappings().first()
    except Exception as exc:  # noqa: BLE001
        log.warning("initial_analysis.db_snapshot_failed", error=str(exc)[:160])
        return None
    if not row:
        return None

    acct_type = str(row.get("accountType") or "unknown").lower()
    if acct_type not in ("personal", "business", "creator"):
        acct_type = "unknown"
    synced = row.get("lastSyncedAt")
    return AccountSnapshot(
        handle=str(row.get("handle") or handle),
        instagram_user_id=row.get("instagramUserId"),
        follower_count=int(row.get("followerCount") or 0),
        following_count=int(row.get("followingCount") or 0),
        posts_count=int(row.get("postsCount") or 0),
        bio=row.get("bio"),
        profile_url=row.get("profileUrl"),
        is_private=bool(row.get("isPrivate")),
        account_type=acct_type,  # type: ignore[typeddict-item]
        last_synced_at=synced.isoformat() if synced else "",
    )


async def _persist_pillars(tenant_id: str, pillars: list[dict]) -> None:
    """Replaces this tenant's content_pillars with the fresh batch."""
    sm = get_sessionmaker()
    palette = ['#a78bfa', '#22d3ee', '#f472b6', '#fb923c', '#84cc16']
    async with sm() as session:
        await session.execute(
            text('DELETE FROM content_pillars WHERE "tenantId" = :tid'),
            {"tid": tenant_id},
        )
        for i, p in enumerate(pillars[:5]):
            await session.execute(
                text(
                    """
                    INSERT INTO content_pillars
                      (id, "tenantId", name, "sharePct", "perfScore", color, "createdAt", "updatedAt")
                    VALUES (:id, :tid, :name, :share, 0.0, :color, NOW(), NOW())
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "tid": tenant_id,
                    "name": str(p.get("name", f"Pillar {i + 1}"))[:80],
                    "share": int(p.get("sharePct") or 25),
                    "color": palette[i % len(palette)],
                },
            )
        await session.commit()


async def _load_existing_topics(tenant_id: str) -> tuple[list[str], str]:
    """Read the latest IG account's onboarding post-analysis (written by the web
    /api/onboarding/analyze-posts) → (topicsCovered, themeSummary)."""
    sm = get_sessionmaker()
    async with sm() as session:
        row = (
            await session.execute(
                text(
                    'SELECT "pastPostsAnalysis" FROM instagram_accounts '
                    'WHERE "tenantId" = :tid AND "pastPostsAnalysis" IS NOT NULL '
                    'ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"tid": tenant_id},
            )
        ).first()
    if not row or row[0] is None:
        return [], ""
    data = row[0]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return [], ""
    if not isinstance(data, dict):
        return [], ""
    raw_topics = data.get("topicsCovered") or []
    topics = [str(t).strip() for t in raw_topics if isinstance(t, str) and t.strip()][:14]
    theme = str(data.get("themeSummary") or "")
    return topics, theme


async def _seed_topic_vault(tenant_id: str, topics: list[str], niche: str, theme: str) -> None:
    """Seed the per-user vault with already-covered topics so the scriptwriter's
    semantic retrieval is aware of them from day one (best-effort per topic)."""
    from app.memory.knowledge_vault import save_note

    for topic in topics[:10]:
        body = f"Foydalanuvchi o'tmishda '{topic}' mavzusida kontent chop etgan."
        if theme:
            body += f" Umumiy yo'nalish: {theme}"
        try:
            await save_note(
                tenant_id=tenant_id,
                title=topic[:120],
                body=body,
                kind="topic",
                tags=[niche] if niche else None,
                # Stable per-topic key so a re-analysis REFRESHES this note instead
                # of inserting a duplicate ("topic" kind is excluded from the
                # cosine dedup, so the sourceTaskId upsert is the only idempotency).
                source_task_id=f"seed-topic:{topic.strip().lower()[:100]}",
            )
        except Exception:  # noqa: BLE001
            log.warning("initial_analysis.vault_topic_failed", topic=topic[:40])


async def _load_psych_profile(tenant_id: str) -> dict | None:
    """Read onboarding_profiles.psychProfile (set by /api/onboarding submit)."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = (
                await session.execute(
                    text(
                        'SELECT "psychProfile" FROM onboarding_profiles '
                        'WHERE "tenantId" = :t ORDER BY "createdAt" DESC LIMIT 1'
                    ),
                    {"t": tenant_id},
                )
            ).first()
        if not row or row[0] is None:
            return None
        val = row[0]
        if isinstance(val, str):
            val = json.loads(val)
        return val if isinstance(val, dict) else None
    except Exception as exc:  # noqa: BLE001
        log.warning("initial_analysis.psych_load_failed", error=str(exc)[:120])
        return None


def _build_psych_notes(psych: dict) -> list[tuple[str, str]]:
    """Pure: turn a UserPsychProfile into (title, body) insight notes. Only emits
    a note when its source section has content — so a sparse profile yields fewer
    notes rather than empty ones."""
    voice = psych.get("voice") or {}
    motivation = psych.get("motivation") or {}
    values = psych.get("values") or {}
    origin = psych.get("originStory") or {}
    audience = psych.get("audience") or {}
    notes: list[tuple[str, str]] = []

    vparts: list[str] = []
    if voice.get("label"):
        vparts.append(f"Brend ovozi: {voice['label']}.")
    if voice.get("archetypePrimary"):
        sec = f" / {voice['archetypeSecondary']}" if voice.get("archetypeSecondary") else ""
        vparts.append(f"Arxetip: {voice['archetypePrimary']}{sec} (taxminiy yo'nalish).")
    if voice.get("antiVoice"):
        vparts.append("Bu uslublardan QOCH: " + ", ".join(str(x) for x in voice["antiVoice"]) + ".")
    if vparts:
        notes.append(("Brend ovozi va arxetip", " ".join(vparts)))

    wparts: list[str] = []
    if motivation.get("whyStatement"):
        wparts.append(f"Why: {motivation['whyStatement']}.")
    if values.get("core"):
        wparts.append("Qadriyatlar: " + ", ".join(str(x) for x in values["core"]) + ".")
    if values.get("philosophicalProblem"):
        wparts.append(f"Asosiy muammo: {values['philosophicalProblem']}.")
    if wparts:
        notes.append(("Why va qadriyatlar", " ".join(wparts)))

    oparts = [
        str(origin[k]) for k in ("catalyst", "challenge", "transformation", "impact") if origin.get(k)
    ]
    if oparts:
        notes.append(("Origin story", " ".join(oparts)))

    aparts: list[str] = []
    if audience.get("avatar"):
        aparts.append(f"Ideal auditoriya: {audience['avatar']}.")
    if audience.get("internalPain"):
        aparts.append(f"Ichki og'riq: {audience['internalPain']}.")
    if audience.get("desire"):
        aparts.append(f"Istak: {audience['desire']}.")
    if aparts:
        notes.append(("Auditoriya va og'riq", " ".join(aparts)))

    return notes


async def _seed_psych_notes(tenant_id: str, psych: dict) -> int:
    """Embed the psych-profile insight notes into the vault. Best-effort per note."""
    from app.memory.knowledge_vault import save_note

    seeded = 0
    for title, body in _build_psych_notes(psych):
        try:
            await save_note(
                tenant_id=tenant_id, title=title, body=body, kind="insight", tags=["shaxsiyat"],
                # Stable per-insight key so a re-analysis refreshes rather than
                # duplicating ("insight" kind is excluded from the cosine dedup).
                source_task_id=f"seed-psych:{title.strip().lower()[:100]}",
            )
            seeded += 1
        except Exception:  # noqa: BLE001
            log.warning("initial_analysis.psych_note_failed", title=title[:30])
    return seeded


async def _seed_niche_foundations(
    tenant_id: str,
    niche: str,
    niche_detail: str,
    audience: str,
    current_followers: int,
    target_followers: int,
) -> int:
    """Seed the vault with foundational coaching knowledge for the niche (via a
    cheap LLM pass) plus a profile note, so the scriptwriter's semantic retrieval
    and the voice coach have a real, embedded knowledge base from day one — even
    when the account's past captions are sparse. Best-effort per note."""
    from app.memory.knowledge_vault import save_note

    if not niche:
        return 0
    seeded = 0

    # Profile note (no LLM) — the user's own goal/audience as retrievable knowledge.
    profile_parts = [f"Soha: {niche}."]
    if niche_detail:
        profile_parts.append(f"Tafsilot: {niche_detail}.")
    if audience:
        profile_parts.append(f"Auditoriya: {audience}.")
    if current_followers or target_followers:
        profile_parts.append(f"Maqsad: {current_followers} dan {target_followers} obunachiga.")
    try:
        await save_note(
            tenant_id=tenant_id,
            title="Mening profilim va maqsadim",
            body=" ".join(profile_parts),
            kind="insight",
            tags=[niche],
        )
        seeded += 1
    except Exception:  # noqa: BLE001
        log.warning("initial_analysis.profile_note_failed")

    # Niche foundations (LLM) — pillars, hooks, formats, cadence, mistakes, plan.
    s = get_settings()
    system = (
        "Sen — Instagram o'sish strategi. Berilgan soha uchun murabbiy bilim "
        "bazasiga asos bo'ladigan amaliy eslatmalar yarat. Faqat o'zbekcha. Har "
        "biri shu sohaga xos, konkret va amaliy bo'lsin (umumiy nasihat emas)."
    )
    user_msg = (
        f"Soha: {niche}."
        + (f" Tafsilot: {niche_detail}." if niche_detail else "")
        + (f" Auditoriya: {audience}." if audience else "")
        + " 7 ta asos eslatma ber, har biri quyidagilardan biri haqida: kontent "
        "ustunlari, ishlaydigan hook shablonlari, format aralashmasi "
        "(Reels/karusel/post), posting kadensi, engagement taktikalari, ko'p "
        "uchraydigan xatolar, birinchi 30 kun rejasi. "
        'FAQAT JSON: {"notes":[{"title":"qisqa sarlavha","body":"2-4 jumla amaliy matn"}]}'
    )
    try:
        resp, _ = await call_claude(
            model=s.model_vault_seeder,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            max_tokens=2000,
            response_format="json",
            agent_name="vault_seeder",
        )
    except Exception:  # noqa: BLE001
        log.warning("initial_analysis.niche_seed_llm_failed")
        return seeded

    try:
        data = json.loads(resp.get("text", "") or "{}")
    except (json.JSONDecodeError, TypeError):
        data = {}
    notes = data.get("notes") if isinstance(data, dict) else None
    if isinstance(notes, list):
        for n in notes[:8]:
            if not isinstance(n, dict):
                continue
            title = str(n.get("title") or "").strip()[:120]
            body = str(n.get("body") or "").strip()[:2000]
            if len(title) < 3 or len(body) < 10:
                continue
            try:
                await save_note(
                    tenant_id=tenant_id,
                    title=title,
                    body=body,
                    kind="insight",
                    tags=[niche],
                )
                seeded += 1
            except Exception:  # noqa: BLE001
                log.warning("initial_analysis.niche_seed_save_failed", title=title[:40])
    return seeded

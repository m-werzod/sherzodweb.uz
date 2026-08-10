"""Cross-tenant shared_knowledge seeder.

Periodically scrapes the public Instagram surfaces (Reels Explore, top
hashtags for the top 30 UZ niches) and populates `shared_knowledge` so the
Market Analyst agent can read from a single source of truth.

Run standalone:
    uv run python -m app.workers.knowledge_seeder

In production it runs as a Coolify scheduled service every 4-6 hours.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.integrations.instagram import playwright_scraper
from app.integrations.llm import groq_client
from app.integrations.llm.embeddings import embed_batch, embed_text
from app.memory.db import get_sessionmaker
from app.montage.trend_edits import recipe_from_llm, recipe_prompt_hint, recipe_to_metadata

log = structlog.get_logger(__name__)

# Top niches we want to keep fresh shared_knowledge for. Updated when launch
# data shows actual user distribution.
SEED_NICHES_UZ = [
    "fitness",
    "beauty",
    "cooking",
    "education",
    "fashion",
    "travel",
    "tech",
    "business",
    "parenting",
    "comedy",
    "music",
    "real_estate",
    "automotive",
    "psychology",
    "language",
    "health",
    "finance",
    "kids",
    "wedding",
    "gaming",
]


_ALLOWED_TREND_KINDS = {"trending_hook", "trending_format", "trending_audio", "hashtag_trend"}

# Freshness TTL by kind. Trends decay FAST — a 45-day TTL on an LLM-invented "trend"
# makes the agency confidently recommend stale/fabricated trends well after they'd be
# dead. Trend kinds expire in ~2 weeks (forcing a refresh via knowledge_refresher),
# news in ~3 weeks; only evergreen exemplars/insights keep the long 45-day window.
_TTL_DAYS_BY_KIND = {
    "trending_hook": 14,
    "trending_format": 14,
    "trending_audio": 14,
    "hashtag_trend": 14,
    "niche_news": 21,
}


def _ttl_days(kind: str) -> int:
    return _TTL_DAYS_BY_KIND.get(kind, 45)

_LLM_SYSTEM = (
    "You are a senior Instagram content strategist for the Uzbekistan market "
    "(Uzbek-language content, Tashkent + regional audience). You output ONLY "
    "valid JSON, no prose. All human-readable text must be in Uzbek (Latin script)."
)


def _llm_user_prompt(niche: str) -> str:
    return (
        f"Niche: {niche}. Platforma: Instagram. Bozor: O'zbekiston, 2026.\n"
        "Shu nisha uchun dolzarb, real kontent-intellektni JSON sifatida bering:\n"
        "{\n"
        '  "trends": [3-5 ta: {"label": "<qisqa trend/hook/format nomi>", '
        '"kind": "trending_hook|trending_format|trending_audio|hashtag_trend", '
        '"score": 0.0-1.0, "detail": "<1-2 gap: nega ishlaydi>"}],\n'
        '  "exemplars": [3-5 ta: {"idea": "<aniq reel/post goyasi>", '
        '"why": "<nega yaxshi natija beradi>", "format": "reel|carousel|story"}],\n'
        '  "news": [2-3 ta: {"headline": "<nisha uchun dolzarb burchak>", '
        '"summary": "<2-3 gap>"}]\n'
        "}\n"
        f"Barcha matn ozbek tilida (lotin). {niche} ijodkorlari uchun aniq va "
        "amaliy bo'ling. score trendning hozirgi qizg'inligini bildiradi (0..1)."
    )


async def _llm_niche_knowledge(niche: str) -> dict:
    return await groq_client.chat_json(
        # Routed via fast_llm (Cerebras/OpenRouter), Haiku fallback.
        system=_LLM_SYSTEM,
        user=_llm_user_prompt(niche),
        max_tokens=1600,
        temperature=0.7,
        agent_name="knowledge_seeder",
    )


async def _save_llm_knowledge(sm, niche: str, data: dict) -> int:
    """Map an LLM niche-knowledge payload into shared_knowledge rows that the
    Market Analyst (trending_*), Industry News (niche_news), and Scriptwriter
    retrieval (exemplar_post) read. Idempotent per niche via source='llm_seed'."""
    rows: list[dict] = []
    for t in (data.get("trends") or [])[:5]:
        kind = t.get("kind") if t.get("kind") in _ALLOWED_TREND_KINDS else "trending_hook"
        label = (t.get("label") or "").strip()
        detail = (t.get("detail") or label).strip()
        if not label:
            continue
        rows.append({
            "kind": kind, "content": detail or label,
            "score": float(t.get("score") or 0.6),
            "metadata": {"label": label, "detail": detail},
        })
    for ex in (data.get("exemplars") or [])[:5]:
        idea = (ex.get("idea") or "").strip()
        why = (ex.get("why") or "").strip()
        if not idea:
            continue
        rows.append({
            "kind": "exemplar_post", "content": (idea + "\n\n" + why).strip(),
            "score": float(ex.get("score") or 0.5),
            "metadata": {"idea": idea, "why": why, "format": ex.get("format")},
        })
    for n in (data.get("news") or [])[:3]:
        headline = (n.get("headline") or "").strip()
        summary = (n.get("summary") or "").strip()
        if not (headline or summary):
            continue
        rows.append({
            "kind": "niche_news", "content": summary or headline,
            "score": None, "metadata": {"headline": headline},
        })
    if not rows:
        return 0

    embeddings = await embed_batch([r["content"] for r in rows])
    async with sm() as session:
        await session.execute(
            text('DELETE FROM shared_knowledge WHERE source = :src AND "nicheTag" = :niche'),
            {"src": "llm_seed", "niche": niche},
        )
        for r, emb in zip(rows, embeddings, strict=False):
            await session.execute(
                text(
                    """
                    INSERT INTO shared_knowledge
                      (id, kind, region, "nicheTag", source, "sourceUrl", content,
                       score, embedding, metadata, "observedAt", "expiresAt", "createdAt")
                    VALUES
                      (:id, CAST(:kind AS "SharedKnowledgeKind"), 'uz', :niche, 'llm_seed',
                       NULL, :content, :score, CAST(:embedding AS jsonb),
                       CAST(:metadata AS jsonb), NOW(), NOW() + make_interval(days => :ttl_days), NOW())
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "kind": r["kind"],
                    "niche": niche,
                    "content": r["content"],
                    "score": r["score"],
                    "embedding": json.dumps(emb),
                    "metadata": json.dumps(r["metadata"], ensure_ascii=False),
                    "ttl_days": _ttl_days(r["kind"]),
                },
            )
        await session.commit()
    return len(rows)


# ── trend → MONTAGE edit recipe (Faza A4 producer) ───────────────────────
# The montage_director reads ONE region-scoped `trending_edit` row (metadata.recipe) and biases its
# effect choices toward the current reels editing meta (pace/effects/intensity). Without this the
# director always falls to EVERGREEN. We generate the recipe from the same LLM strategist as the
# niche knowledge, validate it through the consumer's own parser, and persist the clean shape.

_EDIT_RECIPE_SYSTEM = (
    "You are a senior short-form video EDITOR who tracks the current Instagram Reels editing meta "
    "for the Uzbekistan market (2026). You output ONLY valid JSON, no prose."
)


def _edit_recipe_user_prompt(region: str) -> str:
    return (
        f"Region: {region}. Platforma: Instagram Reels. Yil: 2026.\n"
        "Hozir eng yaxshi natija beradigan MONTAJ uslubini bitta retsept JSON sifatida bering "
        "(ssenariy mazmuni emas — faqat MONTAJ tempi va effektlari):\n"
        "{\n"
        '  "pace": "slow|medium|fast",\n'
        '  "favored_intents": [2-4 ta: "zoom"|"vfx"|"text_pop"|"decor"|"transition"|"sfx"],\n'
        '  "default_intensity": "low|med|high",\n'
        '  "transition_on_scene": true|false,\n'
        '  "sfx_on_beat": true|false\n'
        "}\n"
        "Faqat hozirgi trendga mos qiymatlarni tanlang. Boshqa kalit qo'shmang."
    )


async def _llm_edit_recipe(region: str) -> dict[str, Any]:
    return await groq_client.chat_json(
        system=_EDIT_RECIPE_SYSTEM,
        user=_edit_recipe_user_prompt(region),
        max_tokens=400,
        temperature=0.4,  # a recipe should be stable, not wildly creative
        agent_name="knowledge_seeder",
    )


async def seed_edit_recipe_once(region: str = "uz") -> int:
    """Generate + persist the region's montage edit recipe as a `trending_edit` row. Returns 1 on
    write, 0 on skip. The LLM payload is clamped through recipe_from_llm (the consumer's own parser),
    so a junk payload degrades to EVERGREEN rather than poisoning the director."""
    sm = get_sessionmaker()
    data = await _llm_edit_recipe(region)
    recipe = recipe_from_llm(data)  # validate/allowlist via the shared parser
    metadata = recipe_to_metadata(recipe)  # clean shape that round-trips back to `recipe`
    content = recipe_prompt_hint(recipe)  # human-readable summary (also the embed text)
    embedding = await embed_text(content)
    async with sm() as session:
        await session.execute(
            text(
                'DELETE FROM shared_knowledge '
                "WHERE source = 'llm_seed' AND region = :region "
                "AND kind = CAST('trending_edit' AS \"SharedKnowledgeKind\")"
            ),
            {"region": region},
        )
        await session.execute(
            text(
                """
                INSERT INTO shared_knowledge
                  (id, kind, region, "nicheTag", source, "sourceUrl", content,
                   score, embedding, metadata, "observedAt", "expiresAt", "createdAt")
                VALUES
                  (:id, CAST('trending_edit' AS "SharedKnowledgeKind"), :region, NULL, 'llm_seed',
                   NULL, :content, :score, CAST(:embedding AS jsonb),
                   CAST(:metadata AS jsonb), NOW(), NOW() + INTERVAL '14 days', NOW())
                """
            ),
            {
                "id": uuid.uuid4().hex,
                "region": region,
                "content": content,
                "score": 0.9,  # the single active recipe — top of the ORDER BY score in edit_recipe_for
                "embedding": json.dumps(embedding),
                "metadata": json.dumps(metadata, ensure_ascii=False),
            },
        )
        await session.commit()
    log.info("seed_edit_recipe.done", region=region, pace=recipe.pace)
    return 1


async def ensure_edit_recipe(region: str = "uz") -> int:
    """Seed the region's montage trend recipe ONLY if no fresh one exists — so the
    montage_director stops falling back to the hardcoded EVERGREEN recipe once any user
    onboards, without paying an LLM call on every niche-onboard. Returns 1 if seeded, 0 if
    a fresh row already covered it."""
    sm = get_sessionmaker()
    async with sm() as session:
        existing = await session.execute(
            text(
                "SELECT 1 FROM shared_knowledge "
                "WHERE source = 'llm_seed' AND region = :region "
                "AND kind = CAST('trending_edit' AS \"SharedKnowledgeKind\") "
                'AND ("expiresAt" IS NULL OR "expiresAt" > NOW()) LIMIT 1'
            ),
            {"region": region},
        )
        if existing.first():
            return 0
    return await seed_edit_recipe_once(region)


async def seed_llm_once() -> None:
    """Populate shared_knowledge from LLM domain knowledge (no scraping).

    Instagram aggressively blocks datacenter/proxy scraping, so for MVP we
    ground the Market Analyst, Industry News, and Scriptwriter with
    LLM-generated, Uzbek-language niche intelligence. Real scraped exemplars
    augment this in Faza 2 once rotating residential proxies are in place.
    """
    sm = get_sessionmaker()
    telegram.send(f"📊 Market Analyst seed boshlandi · LLM · {len(SEED_NICHES_UZ)} niche")
    total = 0
    for niche in SEED_NICHES_UZ:
        try:
            data = await _llm_niche_knowledge(niche)
            n = await _save_llm_knowledge(sm, niche, data)
            total += n
            log.info("seed_llm.niche_done", niche=niche, rows=n)
        except Exception:  # noqa: BLE001
            log.exception("seed_llm.niche_failed", niche=niche)
        await asyncio.sleep(1.5)  # gentle LLM pacing (Groq free-tier TPM)
    # The region's montage edit recipe (one row) — fail-soft so a recipe failure never blocks the
    # niche-knowledge seed. No-ops harmlessly until the trending_edit enum migration is deployed.
    try:
        await seed_edit_recipe_once("uz")
    except Exception:  # noqa: BLE001
        log.exception("seed_llm.edit_recipe_failed")
    log.info("seed_llm.done", total_rows=total)
    telegram.send(f"📊 Market Analyst seed tugadi · {total} qator · {len(SEED_NICHES_UZ)} niche")


async def niche_has_knowledge(niche: str) -> bool:
    """True if shared_knowledge already holds LLM-seeded rows for this niche."""
    sm = get_sessionmaker()
    async with sm() as session:
        row = await session.execute(
            text(
                """
                SELECT 1 FROM shared_knowledge
                WHERE source = 'llm_seed' AND "nicheTag" = :niche
                LIMIT 1
                """
            ),
            {"niche": niche},
        )
        return row.scalar() is not None


async def seed_niche(niche: str) -> int:
    """Seed ONE niche on demand — called when a user onboards (no perpetual
    loop). Returns the number of rows written."""
    sm = get_sessionmaker()
    data = await _llm_niche_knowledge(niche)
    n = await _save_llm_knowledge(sm, niche, data)
    # Also ensure the region's montage trend recipe exists (best-effort, idempotent) so the
    # montage_director adapts to a real recipe instead of the hardcoded EVERGREEN fallback.
    try:
        await ensure_edit_recipe("uz")
    except Exception:  # noqa: BLE001 — trend recipe is optional; never block niche seeding
        log.exception("seed_niche.edit_recipe_failed", niche=niche)
    log.info("seed_niche.done", niche=niche, rows=n)
    telegram.send(f"📊 Niche seed (on-demand) · {niche} · {n} qator")
    return n


async def seed_once() -> None:
    sm = get_sessionmaker()
    # 1. Reels Explore for the region (sourcing trending audio + format)
    try:
        explore = await playwright_scraper.fetch_reels_explore("uz-UZ", limit=40)
        await _save_explore_items(sm, explore)
    except Exception:  # noqa: BLE001
        log.exception("seed.explore_failed")

    # 2. Per-niche hashtag tops (exemplar posts)
    for niche in SEED_NICHES_UZ:
        try:
            items = await playwright_scraper.fetch_hashtag_top_posts(niche, limit=20)
            await _save_hashtag_items(sm, niche, items)
            await asyncio.sleep(15)  # rate-friendly pacing
        except Exception:  # noqa: BLE001
            log.exception("seed.hashtag_failed", niche=niche)


async def _save_explore_items(sm, items: list[dict]) -> None:
    async with sm() as session:
        for item in items:
            shortcode = item.get("shortcode")
            if not shortcode:
                continue
            content = json.dumps(item, ensure_ascii=False)
            embedding = await embed_text(content)
            await session.execute(
                text(
                    """
                    INSERT INTO shared_knowledge
                      (id, kind, region, "nicheTag", source, "sourceUrl", content, score, embedding, "observedAt", "createdAt")
                    VALUES
                      (:id, 'trending_format'::"SharedKnowledgeKind", 'uz', NULL,
                       'playwright', :url, :content, NULL, CAST(:embedding AS jsonb), NOW(), NOW())
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "url": item.get("permalink"),
                    "content": content,
                    "embedding": embedding,
                },
            )
        await session.commit()


async def _save_hashtag_items(sm, niche: str, items: list[dict]) -> None:
    async with sm() as session:
        for item in items:
            shortcode = item.get("shortcode")
            if not shortcode:
                continue
            content = json.dumps(item, ensure_ascii=False)
            embedding = await embed_text(content)
            await session.execute(
                text(
                    """
                    INSERT INTO shared_knowledge
                      (id, kind, region, "nicheTag", source, "sourceUrl", content, score, embedding, "observedAt", "createdAt")
                    VALUES
                      (:id, 'exemplar_post'::"SharedKnowledgeKind", 'uz', :niche,
                       'playwright', :url, :content, NULL, CAST(:embedding AS jsonb), NOW(), NOW())
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": uuid.uuid4().hex,
                    "niche": niche,
                    "url": item.get("permalink"),
                    "content": content,
                    "embedding": embedding,
                },
            )
        await session.commit()


async def loop_forever() -> None:
    log.info("seeder.start")
    while True:
        try:
            # LLM-seed is the primary source for MVP — Instagram blocks
            # datacenter/proxy scraping, so seed_once() (Playwright) is left
            # for Faza 2 (rotating residential proxies).
            await seed_llm_once()
        except Exception:  # noqa: BLE001
            log.exception("seed.batch_failed")
        await asyncio.sleep(6 * 60 * 60)


if __name__ == "__main__":
    asyncio.run(seed_llm_once())

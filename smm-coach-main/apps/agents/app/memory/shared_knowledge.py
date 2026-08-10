"""Reads cross-tenant trends and per-niche news from the `shared_knowledge`
table. These rows are populated by the seed job and the periodic Market
Analyst / Industry News refreshers.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from app.graphs.state import IndustrySignal, MarketSignal
from app.integrations.llm.embeddings import embed_batch, embed_text, embedding_health
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

# Below this cosine similarity an exemplar match is noise, not a real analogue —
# don't ground a forecast/script on it. Mirrors knowledge_vault._MIN_SIMILARITY
# (0.15 — below drift's 0.18 on-topic line, because cross-corpus matches run lower).
_MIN_SIMILARITY = 0.15


_SOURCE_WEIGHTS = {
    "graph_api": 1.35,  # official Hashtag Search top_media — measured, not guessed
    "business_discovery": 1.35,  # official competitor snapshots
    "web_search": 1.25,  # live web-grounded
    "llm_seed": 0.75,  # model-generated hypothesis — weakest evidence
}


def _effective_signal_score(score: float | None, source: str | None, age_days: float) -> float:
    """Weighted trend ranking ('vaznlangan signal'): trends decay fast, so a FRESH and/or
    web-grounded signal should outrank a high-but-stale LLM-seeded one — raw `score DESC`
    let a 40-day-old seed beat yesterday's real trend. effective = base × source × recency.
    Pure → unit-testable (age passed in, not computed)."""
    base = score if score is not None else 0.5
    # Source-confidence ladder: OFFICIAL measured Instagram data (Graph API) beats a
    # live web hit, which beats an LLM-invented seed — a fabricated "trend" must never
    # outrank a real one at comparable freshness.
    src_w = _SOURCE_WEIGHTS.get(source or "", 1.0)
    # Linear decay to a 0.4 floor over ~21 days (trend half-life-ish).
    decay = max(0.4, 1.0 - min(0.6, max(0.0, age_days) / 21.0))
    return base * src_w * decay


async def top_signals_for_region(*, region: str, limit: int = 20) -> list[MarketSignal]:
    sm = get_sessionmaker()
    async with sm() as session:
        # Prisma keeps column names in camelCase. Double-quote so Postgres
        # doesn't fold them to lowercase. `label` doesn't exist on the table —
        # we derive it from metadata at read time. Fetch a WIDER pool, then re-rank by
        # the weighted effective score below (recency + source-confidence, not raw score).
        result = await session.execute(
            text(
                """
                SELECT kind, score, source, "nicheTag", "sourceUrl",
                       "observedAt", metadata, content
                FROM shared_knowledge
                WHERE region = :region
                  AND kind IN ('trending_hook', 'trending_audio', 'trending_format', 'hashtag_trend')
                  AND ("expiresAt" IS NULL OR "expiresAt" > NOW())
                -- Pool by RECENCY first: the Python re-rank below weights recency
                -- heavily, so a fresh low-raw-score trend must survive INTO the pool
                -- to be promotable. A score-DESC pool would exclude it before the
                -- re-rank ever sees it.
                ORDER BY "observedAt" DESC, score DESC NULLS LAST
                LIMIT :pool
                """
            ),
            {"region": region, "pool": max(limit * 3, limit)},
        )
        rows = result.mappings().all()

    now = datetime.now(UTC)

    def _age_days(observed: object) -> float:
        if not isinstance(observed, datetime):
            return 0.0
        obs = observed if observed.tzinfo else observed.replace(tzinfo=UTC)
        return max(0.0, (now - obs).total_seconds() / 86400.0)

    ranked = sorted(
        rows,
        key=lambda r: _effective_signal_score(
            float(r["score"]) if r["score"] is not None else None, r["source"], _age_days(r["observedAt"])
        ),
        reverse=True,
    )[:limit]

    return [
        MarketSignal(
            kind=row["kind"].split("_")[-1],
            region=region,
            label=(row.get("metadata") or {}).get("label")
            or (row["content"][:80] if row["content"] else (row.get("sourceUrl") or "")),
            score=float(row["score"] or 0.0),
            source=row["source"],
            captured_at=row["observedAt"].isoformat() if row["observedAt"] else "",
            payload=row.get("metadata") or {},
        )
        for row in ranked
    ]


async def trending_content_for_region(*, region: str, limit: int = 6) -> list[dict]:
    """The actual top-performing POST captions behind the region's hashtag trends —
    what CONTENT is winning, not just which tags. `top_signals_for_region` surfaces
    only the '#tag' label; this feeds competitor_intel → roadmap the real winning
    topics so suggestions echo proven performers. Ordered by engagement."""
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT content, score, metadata
                FROM shared_knowledge
                WHERE region = :region AND kind = 'hashtag_trend'
                  AND ("expiresAt" IS NULL OR "expiresAt" > NOW())
                  AND content IS NOT NULL AND content <> ''
                ORDER BY score DESC NULLS LAST, "observedAt" DESC
                LIMIT :limit
                """
            ),
            {"region": region, "limit": limit},
        )
        rows = result.mappings().all()
    return [
        {
            "hashtag": (r.get("metadata") or {}).get("hashtag", ""),
            "text": (r["content"] or "")[:200],
            "engagement": int(r["score"] or 0),
        }
        for r in rows
    ]


async def recent_niche_news(*, niche: str, region: str = "uz", limit: int = 10) -> list[IndustrySignal]:
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT content, source, "sourceUrl", "observedAt", metadata
                FROM shared_knowledge
                WHERE region = :region
                  AND "nicheTag" = :niche
                  AND kind = 'niche_news'
                  AND ("expiresAt" IS NULL OR "expiresAt" > NOW())
                ORDER BY "observedAt" DESC
                LIMIT :limit
                """
            ),
            {"region": region, "niche": niche, "limit": limit},
        )
        rows = result.mappings().all()

    return [
        IndustrySignal(
            niche=niche,
            headline=(row.get("metadata") or {}).get("headline", "")
            or (row["content"][:80] if row["content"] else ""),
            summary=row["content"] or "",
            source_url=row["sourceUrl"] or "",
            captured_at=row["observedAt"].isoformat() if row["observedAt"] else "",
        )
        for row in rows
    ]


def _shape_web_rows(results: list[dict]) -> list[dict]:
    """Pure: web-search hits → niche_news row dicts (deduped by url, capped 8,
    empties dropped). Separated from I/O so it's unit-testable."""
    out: list[dict] = []
    seen: set[str] = set()
    for r in results:
        title = str(r.get("title") or "").strip()
        snippet = str(r.get("snippet") or "").strip()
        url = str(r.get("url") or "").strip()
        content = (snippet or title).strip()
        if not content:
            continue
        key = url or content[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append({"content": content[:600], "url": url, "headline": title[:160]})
        if len(out) >= 8:
            break
    return out


async def save_web_results(niche: str, region: str, results: list[dict]) -> int:
    """Cache live web-search hits as kind='niche_news', source='web_search', so
    the 3 grounding nodes + future runs reuse them instead of each re-querying.
    Replace-per-(niche,region,source) (like the seeder) + a 7-day TTL so the
    cache stays fresh. Best-effort → 0 on failure (caller already has the live
    results in hand). Cross-tenant by design (shared_knowledge has no tenantId)."""
    niche = (niche or "").strip()
    if not niche or not results:
        return 0
    rows = _shape_web_rows(results)
    if not rows:
        return 0
    try:
        embeddings = await embed_batch([r["content"] for r in rows])
    except Exception as exc:  # noqa: BLE001 — cache write is best-effort
        log.warning("shared_knowledge.web_embed_failed", error=str(exc)[:120])
        return 0
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text(
                    'DELETE FROM shared_knowledge WHERE source = :src '
                    'AND "nicheTag" = :niche AND region = :region'
                ),
                {"src": "web_search", "niche": niche, "region": region},
            )
            for r, emb in zip(rows, embeddings, strict=False):
                await session.execute(
                    text(
                        """
                        INSERT INTO shared_knowledge
                          (id, kind, region, "nicheTag", source, "sourceUrl", content,
                           score, embedding, metadata, "observedAt", "expiresAt", "createdAt")
                        VALUES
                          (:id, CAST('niche_news' AS "SharedKnowledgeKind"), :region, :niche,
                           'web_search', :url, :content, NULL, CAST(:embedding AS jsonb),
                           CAST(:metadata AS jsonb), NOW(), NOW() + INTERVAL '7 days', NOW())
                        """
                    ),
                    {
                        "id": uuid.uuid4().hex,
                        "region": region,
                        "niche": niche,
                        "url": r["url"] or None,
                        "content": r["content"],
                        "embedding": json.dumps(emb),
                        "metadata": json.dumps({"headline": r["headline"]}, ensure_ascii=False),
                    },
                )
            await session.commit()
        return len(rows)
    except Exception:  # noqa: BLE001
        log.warning("shared_knowledge.web_save_failed", niche=niche, exc_info=True)
        return 0


async def competitor_snapshots(*, niche: str, region: str = "uz", limit: int = 10) -> list[dict]:
    """Top competitor posts cached as kind='competitor_snapshot' (written by the
    competitor_tracker worker). Returns [] when none exist yet — graceful for the
    competitor_intel node, which simply works from the other sources."""
    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT content, score, source, "sourceUrl", "observedAt", metadata
                FROM shared_knowledge
                WHERE region = :region
                  AND "nicheTag" = :niche
                  AND kind = 'competitor_snapshot'
                  AND ("expiresAt" IS NULL OR "expiresAt" > NOW())
                ORDER BY score DESC NULLS LAST, "observedAt" DESC
                LIMIT :limit
                """
            ),
            {"region": region, "niche": niche, "limit": limit},
        )
        rows = result.mappings().all()

    return [
        {
            "content": row["content"] or "",
            "handle": (row.get("metadata") or {}).get("handle", ""),
            # business_discovery gives no view count — engagement (likes+comments)
            # is the real signal, stored in `score`. Surface likes/comments too;
            # don't read a 'views' key that save_competitor_posts never writes.
            "likes": int((row.get("metadata") or {}).get("likes") or 0),
            "comments": int((row.get("metadata") or {}).get("comments") or 0),
            "score": float(row["score"] or 0.0),
        }
        for row in rows
    ]


async def save_competitor_posts(
    *, handle: str, niche: str, posts: list[dict], region: str = "uz", keep_top: int = 6
) -> int:
    """Cache a competitor's top posts as kind='competitor_snapshot' so the
    competitor_intel node (and the dashboard) can surface 'what's working in this
    niche'. Cross-tenant by design (niche/region-keyed, no tenantId). Refresh
    semantics: delete this (niche, handle)'s prior rows, then insert the current
    top `keep_top` by engagement — so it never accumulates duplicates across the
    12h tracker runs. Best-effort (never raises into the worker)."""
    h = (handle or "").lstrip("@").strip()
    if not h or not niche or not posts:
        return 0
    ranked = sorted(
        posts,
        key=lambda p: int(p.get("like_count") or 0) + int(p.get("comments_count") or 0),
        reverse=True,
    )[: max(1, keep_top)]
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            # Refresh: drop the prior snapshot for this niche+handle before re-inserting.
            await session.execute(
                text(
                    "DELETE FROM shared_knowledge WHERE kind = 'competitor_snapshot' "
                    'AND region = :region AND "nicheTag" = :niche '
                    "AND metadata->>'handle' = :handle"
                ),
                {"region": region, "niche": niche, "handle": h},
            )
            for p in ranked:
                eng = int(p.get("like_count") or 0) + int(p.get("comments_count") or 0)
                meta = json.dumps(
                    {
                        "handle": h,
                        "likes": int(p.get("like_count") or 0),
                        "comments": int(p.get("comments_count") or 0),
                        "media_type": p.get("media_type"),
                    },
                    ensure_ascii=False,
                )
                await session.execute(
                    text(
                        """
                        INSERT INTO shared_knowledge
                          (id, kind, region, "nicheTag", source, "sourceUrl", content,
                           score, metadata, "observedAt", "expiresAt", "createdAt")
                        VALUES
                          (:id, CAST('competitor_snapshot' AS "SharedKnowledgeKind"), :region,
                           :niche, 'business_discovery', :url, :content, :score,
                           CAST(:metadata AS jsonb), NOW(), NOW() + INTERVAL '14 days', NOW())
                        """
                    ),
                    {
                        "id": uuid.uuid4().hex,
                        "region": region,
                        "niche": niche,
                        "url": p.get("permalink") or None,
                        "content": (p.get("caption") or "")[:2000],
                        "score": float(eng),
                        "metadata": meta,
                    },
                )
            await session.commit()
        return len(ranked)
    except Exception:  # noqa: BLE001
        log.warning("shared_knowledge.competitor_save_failed", handle=h, niche=niche, exc_info=True)
        return 0


async def save_hashtag_trends(
    *, hashtag: str, region: str = "uz", posts: list[dict], niche: str | None = None, keep_top: int = 5
) -> int:
    """Cache a hashtag's top posts as kind='hashtag_trend' so top_signals_for_region
    (→ competitor_intel → roadmap) surfaces 'what's trending in this niche/region'.
    Cross-tenant by design (region/hashtag-keyed, no tenantId — one fetch shared by
    every tenant in that region). Refresh: delete this (region, hashtag)'s prior rows,
    then insert the top `keep_top` by engagement. 7-day TTL (trends decay fast — and
    it doubles as the refresher's quota guard: a live row means 'don't re-query').
    Best-effort (never raises into the worker)."""
    tag = re.sub(r"[^A-Za-z0-9_]", "", (hashtag or "").lstrip("#").strip())
    if not tag or not posts:
        return 0
    ranked = sorted(
        posts,
        key=lambda p: int(p.get("like_count") or 0) + int(p.get("comments_count") or 0),
        reverse=True,
    )[: max(1, keep_top)]
    label = f"#{tag}"  # what top_signals_for_region surfaces to competitor_intel
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text(
                    "DELETE FROM shared_knowledge WHERE kind = 'hashtag_trend' "
                    "AND region = :region AND metadata->>'hashtag' = :tag"
                ),
                {"region": region, "tag": tag},
            )
            for p in ranked:
                eng = int(p.get("like_count") or 0) + int(p.get("comments_count") or 0)
                meta = json.dumps(
                    {
                        "label": label,
                        "hashtag": tag,
                        "region": region,
                        "likes": int(p.get("like_count") or 0),
                        "comments": int(p.get("comments_count") or 0),
                        "media_type": p.get("media_type"),
                    },
                    ensure_ascii=False,
                )
                await session.execute(
                    text(
                        """
                        INSERT INTO shared_knowledge
                          (id, kind, region, "nicheTag", source, "sourceUrl", content,
                           score, metadata, "observedAt", "expiresAt", "createdAt")
                        VALUES
                          (:id, CAST('hashtag_trend' AS "SharedKnowledgeKind"), :region,
                           :niche, 'graph_api', :url, :content, :score,
                           CAST(:metadata AS jsonb), NOW(), NOW() + INTERVAL '7 days', NOW())
                        """
                    ),
                    {
                        "id": uuid.uuid4().hex,
                        "region": region,
                        "niche": niche,
                        "url": p.get("permalink") or None,
                        "content": (p.get("caption") or "")[:2000],
                        "score": float(eng),
                        "metadata": meta,
                    },
                )
            await session.commit()
        return len(ranked)
    except Exception:  # noqa: BLE001
        log.warning("shared_knowledge.hashtag_trend_save_failed", hashtag=tag, region=region, exc_info=True)
        return 0


async def similar_exemplar_posts(*, query: str, niche: str, limit: int = 5) -> list[dict]:
    """Semantic-search exemplar posts by cosine similarity over Voyage embeddings.

    pgvector is not installed in local dev, so the `embedding` column is
    `jsonb` (list[float]) rather than `vector(1024)`. We pull a bounded
    candidate set (niche-filtered, top-200 by score), then rank in Python.
    Production swap-in: replace this with the `<=>` operator + HNSW index
    once pgvector is shipped (Bosqich J).
    """
    sm = get_sessionmaker()
    async with sm() as session:
        # asyncpg can't infer parameter type when the same `:niche` is used
        # in both `IS NULL` and `= text` positions in the same query. Casting
        # explicitly with `CAST(:niche AS text)` settles it; we also dropped
        # the `IS NULL` branch since the caller always passes a niche.
        result = await session.execute(
            text(
                """
                SELECT id, content, "sourceUrl", score, metadata, embedding
                FROM shared_knowledge
                WHERE kind = 'exemplar_post'
                  AND "nicheTag" = CAST(:niche AS text)
                  AND embedding IS NOT NULL
                ORDER BY score DESC NULLS LAST, "observedAt" DESC
                LIMIT 200
                """
            ),
            {"niche": niche},
        )
        rows = result.mappings().all()

    if not rows:
        return []

    # Degraded embeddings → random cosine → arbitrary "exemplars". Skip rather
    # than ground a forecast on noise.
    if embedding_health().get("degraded"):
        return []

    qv = await embed_text(query)
    qnorm = _norm(qv)
    if qnorm == 0.0:
        return []

    scored: list[tuple[float, dict]] = []
    for row in rows:
        emb = row["embedding"]
        if not emb:
            continue
        # jsonb stores the list as Python list[float] when loaded by psycopg.
        if isinstance(emb, str):
            import json as _json
            try:
                emb = _json.loads(emb)
            except Exception:  # noqa: BLE001, S112 — skip a malformed embedding row
                continue
        sim = _cosine(qv, emb, qnorm)
        scored.append((sim, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "id": row["id"],
            "content": row["content"],
            "permalink": row["sourceUrl"],
            "engagement": (row.get("metadata") or {}).get("engagement"),
            "similarity": sim,
        }
        for sim, row in scored[:limit]
        if sim >= _MIN_SIMILARITY  # floor: don't ground on a non-analogue
    ]


def _norm(v: list[float]) -> float:
    return (sum(x * x for x in v)) ** 0.5


def _cosine(a: list[float], b: list[float], anorm: float) -> float:
    """Cosine similarity. Caller passes anorm so we don't recompute the
    query vector's norm for every candidate."""
    if len(a) != len(b):
        return 0.0
    bnorm = _norm(b)
    if bnorm == 0.0:
        return 0.0
    # len(a) == len(b) guaranteed above, so strict zip is safe + lint-clean.
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (anorm * bnorm)

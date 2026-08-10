"""Competitor + trend + niche intel — folded into `analysis_summary` BEFORE the
roadmap is generated, so the onboarding roadmap is shaped by what's actually
winning in the niche.

This fixes the ordering problem where market_analyst / industry_news run AFTER
roadmap_generator (too late to influence the roadmap strategy). This node sits on
the initial_analysis → roadmap_generator edge and reads cross-tenant
`shared_knowledge` (trends, competitor snapshots, niche news) + the tenant's
`CompetitorTrack` rows — all DB reads, no live scrape here, so it always works.

Fail-soft: any error or no data → returns {} and the roadmap is unchanged
(existing tenants with an empty knowledge base are unaffected).
"""
from __future__ import annotations

import json
import re
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.integrations.llm import groq_client
from app.integrations.search import web_search, web_search_enabled
from app.memory.db import get_sessionmaker
from app.memory.shared_knowledge import (
    competitor_snapshots,
    recent_niche_news,
    top_signals_for_region,
    trending_content_for_region,
)
from app.memory.vault_context import load_vault_context

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

# Only the onboarding / replan roadmap build benefits from re-analysing the
# niche; content_review (single-task) and pulses must not pay for it again.
_SKIP_WORKFLOWS = {"content_review", "tracker_pulse"}

_SYSTEM = """Sen Raqobatchi-Trend tahlilchisisan — Instagram o'sish strategi.
Senga foydalanuvchining niche'i, region trending signallari (hook/audio/format),
soha yangiliklari va shu niche'dagi raqobatchilarning top postlari beriladi.

Signallarda `manba` bor: "real" = rasmiy Instagram o'lchovi, "web" = jonli
web-qidiruv, "taxmin" = model gipotezasi. Intel'ni "real"/"web" signallarga qur;
"taxmin"ni fakt sifatida ishlatma.

Vazifa: shulardan kelib chiqib yo'l xaritasi uchun amaliy intel ber. G'olib
postlardan TAKRORLANADIGAN burchak/strukturani ajrat (aniq mavzuni nusxalama —
originallik uchun), va raqobatchilar yoritMAGAN, imkoniyat bo'lgan bo'shliqlarni
(content gap) top.

JSON qaytar (faqat JSON, markdown yo'q):
{"competitor_angles": ["<g'olib burchak/struktura>", ...],
 "content_gaps": ["<yoritilmagan, imkoniyatli mavzu>", ...],
 "trending_formats": ["reel", "carousel", ...],
 "recommended_audio": ["<trend audio nomi>", ...]}
O'zbekcha, qisqa. Har massiv bo'sh bo'lishi mumkin."""


# IG path segments + generic words that look like handles but aren't real
# competitor accounts — filtered out of auto-discovery.
_HANDLE_STOPWORDS = {
    "instagram", "explore", "reels", "reel", "p", "tv", "stories", "accounts",
    "about", "developer", "privacy", "terms", "help", "tags", "directory",
    "instagramcom", "www", "com", "http", "https",
}
_HANDLE_RE = re.compile(r"(?:@|instagram\.com/)([A-Za-z0-9._]{2,30})", re.IGNORECASE)


def _extract_handles(results: list[dict], *, limit: int = 8) -> list[str]:
    """Pull plausible IG @handles from web-search titles/snippets/urls. Pure +
    testable. Lowercased, deduped, stopword-filtered, '_'/'.'-only rejected.
    Handles that appear in a result's URL (real instagram.com/<handle> links) are
    taken FIRST — they're far more likely to be real accounts than prose-only
    mentions, which are often brand names or hallucinated by the search fallback."""
    out: list[str] = []
    seen: set[str] = set()

    def _take(blob: str) -> None:
        for m in _HANDLE_RE.findall(blob):
            h = m.strip().strip(".").lower()
            if not h or h in seen or h in _HANDLE_STOPWORDS:
                continue
            if not any(c.isalnum() for c in h):  # all dots/underscores
                continue
            seen.add(h)
            out.append(h)

    # Pass 1 — real IG links in the URL field.
    for r in results:
        _take(r.get("url") or "")
        if len(out) >= limit:
            return out[:limit]
    # Pass 2 — prose mentions in title/snippet.
    for r in results:
        _take(f"{r.get('title') or ''} {r.get('snippet') or ''}")
        if len(out) >= limit:
            return out[:limit]
    return out[:limit]


async def _discover_competitors_web(niche: str, region: str, *, limit: int = 8) -> list[dict]:
    """Stage 3a — find top niche accounts via web search when the user hasn't
    tracked any. Returns [{handle, source_url, discovered:True}] (up to `limit`).
    Best-effort → [] (never raises into the node)."""
    if not niche or not web_search_enabled():
        return []
    # Several angles: the old single Uzbek query surfaced almost no @handles /
    # instagram.com links (verified live → 0 discovered). An English "influencers"
    # query + an explicit "instagram.com … blogger" query reliably surface real
    # handles; we merge unique hits across all three for coverage.
    # Region-aware geo terms sharpen the search for local accounts (the raw code
    # "uz" alone is weak). The site:instagram.com query returns real IG profile
    # URLs directly, which _extract_handles now prefers over prose mentions.
    geo = "Uzbekistan Toshkent" if (region or "").lower() == "uz" else region
    queries = [
        f"site:instagram.com {niche} {geo}",
        f"top {niche} instagram influencers {geo}",
        f"instagram.com {niche} blogger {geo}",
        f"eng mashhur {niche} instagram bloggerlari {region}",
    ]
    handles: list[str] = []
    by_handle: dict[str, str] = {}
    for q in queries:
        try:
            hits = await web_search(q, limit=6)
        except Exception as exc:  # noqa: BLE001
            log.warning("competitor_intel.discovery_failed", query=q[:60], error=str(exc)[:120])
            continue
        for hit in hits or []:
            for hh in _extract_handles([hit]):
                if hh not in by_handle:
                    by_handle[hh] = hit.get("url") or ""
                    handles.append(hh)
    return [
        {"handle": h, "source_url": by_handle.get(h, ""), "discovered": True}
        for h in handles[: max(1, limit)]
    ]


async def _load_competitors(tenant_id: str) -> list[dict]:
    """The tenant's tracked competitor handles (user-entered). Best-effort."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            rows = await session.execute(
                text(
                    'SELECT handle, followers, "growthRate" FROM competitor_tracks '
                    'WHERE "tenantId" = :t ORDER BY followers DESC NULLS LAST LIMIT 10'
                ),
                {"t": tenant_id},
            )
            return [dict(r) for r in rows.mappings().all()]
    except Exception as exc:  # noqa: BLE001
        log.warning("competitor_intel.competitors_load_failed", error=str(exc)[:120])
        return []


async def _persist_discovered(tenant_id: str, discovered: list[dict], *, limit: int = 5) -> int:
    """Seed web-discovered niche accounts into competitor_tracks so competitor_tracker
    (official business_discovery) starts populating REAL competitor_snapshot rows for
    them — turning "LLM/web-guessed competitors" into officially-read follower+post
    data on the next tracker tick. Dedup by (tenantId, handle); handles sanitized to
    the IG charset. Best-effort (never raises into the node)."""
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for d in discovered:
        h = re.sub(r"[^A-Za-z0-9._]", "", str(d.get("handle") or "").lstrip("@").strip())
        if not h or h.lower() in seen:
            continue
        seen.add(h.lower())
        rows.append((h, str(d.get("source_url") or "")))
        if len(rows) >= limit:
            break
    if not rows:
        return 0
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            for h, url in rows:
                await session.execute(
                    text(
                        """
                        INSERT INTO competitor_tracks
                          (id, "tenantId", handle, followers, "growthRate", "overlapPct",
                           meta, "createdAt", "updatedAt")
                        VALUES (:id, :t, :h, 0, 0, 0, CAST(:meta AS jsonb), NOW(), NOW())
                        ON CONFLICT ("tenantId", handle) DO NOTHING
                        """
                    ),
                    {
                        "id": uuid.uuid4().hex,
                        "t": tenant_id,
                        "h": h,
                        "meta": json.dumps(
                            {"source": "web_discovered", "sourceUrl": url}, ensure_ascii=False
                        ),
                    },
                )
            await session.commit()
        return len(rows)
    except Exception as exc:  # noqa: BLE001
        log.warning("competitor_intel.persist_discovered_failed", error=str(exc)[:120])
        return 0


def _fold(
    existing: str,
    intel: dict,
    signals: list,
    competitors: list,
    discovered: list | None = None,
    trending_content: list | None = None,
) -> str:
    """Append a RAQOBATCHI VA TREND block to the existing analysis text. Uses the
    LLM intel when present, and falls back to the raw trend signals so trends still
    surface even when the synthesis call failed. Returns `existing` unchanged when
    there's nothing useful to add."""
    angles = [str(x) for x in (intel.get("competitor_angles") or []) if str(x).strip()]
    gaps = [str(x) for x in (intel.get("content_gaps") or []) if str(x).strip()]
    fmts = [str(x) for x in (intel.get("trending_formats") or []) if str(x).strip()]
    audio = [str(x) for x in (intel.get("recommended_audio") or []) if str(x).strip()]
    if not fmts:
        fmts = [s.get("label") for s in signals if s.get("kind") == "format" and s.get("label")][:5]
    if not audio:
        audio = [s.get("label") for s in signals if s.get("kind") == "audio" and s.get("label")][:5]
    handles = [f"@{c.get('handle')}" for c in competitors[:5] if c.get("handle")]
    # hashtag_trend surfaces via top_signals as kind='trend' (label='#tag'); the
    # winning POST content comes from trending_content. Fold BOTH deterministically
    # so the real, live trend data reaches the roadmap even when the LLM synthesis
    # call degrades (empty intel) — not only through the model.
    tags = [s.get("label") for s in signals if s.get("kind") == "trend" and s.get("label")][:6]
    winners = [str(t.get("text") or "").strip() for t in (trending_content or []) if str(t.get("text") or "").strip()]

    lines: list[str] = []
    if angles:
        lines.append("G'olib burchaklar (ilhom ol, nusxalama): " + "; ".join(angles[:6]))
    if gaps:
        lines.append("Yoritilmagan imkoniyatlar (shularga urg'u ber): " + "; ".join(gaps[:6]))
    if winners:
        lines.append(
            "Trenddagi g'olib mavzular (real, engagement bo'yicha): "
            + " | ".join(w[:80] for w in winners[:4])
        )
    if tags:
        lines.append("Trenddagi hashtag'lar: " + ", ".join(str(t) for t in tags))
    if fmts:
        lines.append("Trenddagi formatlar: " + ", ".join(str(f) for f in fmts[:5]))
    if audio:
        lines.append("Trenddagi audio: " + ", ".join(str(a) for a in audio[:5]))
    if handles:
        lines.append("Kuzatilayotgan raqobatchilar: " + ", ".join(handles))
    disc_handles = [f"@{d.get('handle')}" for d in (discovered or []) if d.get("handle")]
    if disc_handles:
        lines.append("Sohada topilgan akkauntlar (web — o'rgan): " + ", ".join(disc_handles[:6]))
    if not lines:
        return existing
    return (existing or "") + "\n\n--- RAQOBATCHI VA TREND TAHLILI ---\n" + "\n".join(lines)


async def run(state: GrowthCoachState) -> dict:
    if (state.get("workflow") or "") in _SKIP_WORKFLOWS:
        return {}

    north = state.get("north_star") or {}
    region = north.get("region", "uz")
    niche = str(north.get("niche") or "")
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    async def _safe(coro, label: str, default: Any):
        try:
            return await coro
        except Exception as exc:  # noqa: BLE001
            log.warning(f"competitor_intel.{label}_failed", error=str(exc)[:120])
            return default

    signals = await _safe(top_signals_for_region(region=region, limit=20), "signals", [])
    snapshots = (
        await _safe(competitor_snapshots(niche=niche, region=region, limit=10), "snapshots", [])
        if niche
        else []
    )
    news = (
        await _safe(recent_niche_news(niche=niche, region=region, limit=6), "news", [])
        if niche
        else []
    )
    # The winning CONTENT behind the region's live hashtag trends (not just tag names)
    # — so the roadmap echoes proven topics.
    trending_content = await _safe(
        trending_content_for_region(region=region, limit=6), "trending_content", []
    )
    competitors = await _load_competitors(tenant_id)

    # Stage 3a — when the user hasn't tracked competitors, auto-discover top
    # niche accounts via web search (gated on a search provider). Deduped against
    # any tracked handles; surfaced separately (not persisted as tracks).
    discovered: list[dict] = []
    if niche and not competitors:
        tracked = {str(c.get("handle") or "").lower() for c in competitors}
        discovered = [
            d for d in await _discover_competitors_web(niche, region)
            if str(d.get("handle") or "").lower() not in tracked
        ]
        # Seed the top discoveries into competitor_tracks so competitor_tracker
        # (business_discovery) turns them into REAL competitor_snapshot data — the
        # "mashhur akkauntlarni haqiqiy o'rganish" gap. Only when the user has none
        # tracked, so we never override their own curated list.
        if discovered:
            n = await _persist_discovered(tenant_id, discovered)
            if n:
                log.info("competitor_intel.seeded_tracks", tenant_id=tenant_id, count=n)

    if not signals and not snapshots and not news and not competitors and not discovered and not trending_content:
        return {}  # nothing to add — roadmap unchanged (existing tenants safe)

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="market",
        content="Sohangizdagi raqobatchilar, trendlar va yangiliklarni yo'l xaritasi uchun tahlil qilyapman.",
        run_id=run_id,
    )

    payload = json.dumps(
        {
            "niche": niche,
            "niche_detail": north.get("niche_detail", ""),
            "target_audience": north.get("target_audience", ""),
            "region": region,
            "trending_signals": [
                {
                    "kind": s.get("kind"),
                    "label": s.get("label"),
                    "manba": "real" if s.get("source") in ("graph_api", "business_discovery") else ("web" if s.get("source") == "web_search" else "taxmin"),
                }
                for s in signals[:12]
            ],
            "trending_content": [
                {"text": (t.get("text") or "")[:140], "engagement": int(t.get("engagement") or 0)}
                for t in trending_content[:6]
            ],
            "competitor_posts": [
                # engagement = likes+comments (the real "what's working" signal);
                # business_discovery exposes no view count, so don't claim one.
                {"text": (s.get("content") or "")[:140], "engagement": int(s.get("score") or 0)}
                for s in snapshots[:8]
            ],
            "niche_news": [(n.get("summary") or "")[:140] for n in news[:5]],
            "competitors": [c.get("handle") for c in competitors[:8] if c.get("handle")],
            "discovered_competitors": [d.get("handle") for d in discovered[:8]],
            # Stage 6 — the user's own brand/voice context so content-gap picks fit
            # THEM, not just the niche. Empty/onboarding → '' (no-op).
            "vault_context": await load_vault_context(
                tenant_id, f"{niche} {north.get('target_audience', '')}",
                "FOYDALANUVCHI BRENDI (bilim vault)",
            ),
        },
        ensure_ascii=False,
    )

    intel: dict = {}
    try:
        result = await groq_client.chat_json(
            system=_SYSTEM, user=payload, max_tokens=500, agent_name="competitor_intel"
        )
        if isinstance(result, dict):
            intel = result
    except Exception as exc:  # noqa: BLE001
        log.warning("competitor_intel.synthesis_failed", error=str(exc)[:120])

    # Fold into analysis_summary (roadmap_generator already reads it). initial_analysis
    # ran first, so state["analysis_summary"] holds its output — APPEND, never replace.
    existing = state.get("analysis_summary") or ""
    folded = _fold(existing, intel, signals, competitors, discovered, trending_content)

    out: dict = {
        "competitor_intel": intel,
        "notes": [
            f"competitor_intel: {len(signals)} signals, {len(snapshots)} competitor posts, "
            f"{len(news)} news, {len(competitors)} competitors, {len(discovered)} web-discovered"
        ],
    }
    if folded != existing:
        out["analysis_summary"] = folded
    return out

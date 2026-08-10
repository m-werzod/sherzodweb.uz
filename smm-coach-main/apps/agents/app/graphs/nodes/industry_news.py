"""Industry News — reads recent niche news from `shared_knowledge` and uses
Claude Haiku to synthesize WHICH shift matters most for the user's content
strategy, emitting it into `agent_messages`. Pulls kind=niche_news populated by
`knowledge_seeder.py`.

Previously this node just echoed the top deduped headline. Now it reasons over
the headlines in the user's niche and says what content opportunity opens up.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.agents.messaging import emit_message
from app.integrations.llm import groq_client
from app.integrations.search import web_search, web_search_enabled
from app.memory.shared_knowledge import recent_niche_news, save_web_results
from app.memory.vault_context import load_vault_context

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState, IndustrySignal

log = structlog.get_logger(__name__)

_SYSTEM = """Sen Industry News agentisan — soha kuzatuvchisi. Senga foydalanuvchi
niche'i + so'nggi sarlavhalar (`headlines`) va JONLI web-qidiruv natijalari
(`web`) beriladi. `web` bo'lsa — unga ustunlik ber (u dolzarbroq). Vazifa: shu
yangiliklardan QAYSI BIRI foydalanuvchining kontent strategiyasini eng ko'p
o'zgartirishini ayt va NEGA — qanday kontent imkoniyati ochiladi. 1-2 jumla.

JSON qaytar: {"insight": "<1-2 jumla — qaysi yangilik muhim va qanday kontent qilsa bo'ladi>", "headline": "<asosiy sarlavha>"}
O'zbekcha, qisqa. Markdown yo'q, faqat JSON."""


# content_review / tracker_pulse skip the live web-search grounding (see run) — mirror competitor_intel.
_SKIP_WORKFLOWS = {"content_review", "tracker_pulse"}


async def run(state: GrowthCoachState) -> dict:
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    north = state.get("north_star") or {}
    # Niche resolution: niche_detail is meant to be a SHORT, specific niche
    # (algotrading, weight-loss-for-busy-moms). But users paste a rambling
    # sentence about their goal there, and searching news for a whole paragraph
    # returns nothing ("no news for niche=hullas bu akkaunt..."). So only use
    # niche_detail when it's keyword-short; otherwise fall back to the clean
    # niche (tech, fitness). We DON'T fall back to "general".
    _detail = (north.get("niche_detail") or "").strip()
    _niche = (north.get("niche") or "").strip()
    niche_raw = _detail if (_detail and len(_detail.split()) <= 5) else _niche

    if not niche_raw:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="industry",
            content="Soha aniqlanmagan — yangiliklar tahlili o'tkazib yuborildi.",
            run_id=run_id,
        )
        return {
            "industry_signals": [],
            "notes": ["industry_news: skipped (no niche set)"],
        }

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="industry",
        content=f"{niche_raw} sohasidagi bugungi yangiliklarni o'qiyapman.",
        run_id=run_id,
    )

    region = north.get("region", "uz")
    signals: list[IndustrySignal] = await recent_niche_news(
        niche=niche_raw,
        region=region,
    )

    # Stage 3b — REAL web grounding. The DB cache (knowledge_seeder) is
    # LLM-invented + stale; a live search makes "industry news" actually about
    # the present. Best-effort + time-bounded inside web_search; merged with the
    # DB signals. When a web result is found, the node works even with an empty
    # DB cache (the old `if not signals: return` no longer kills it).
    # On the content_review / tracker_pulse HOT path, skip the live web-search grounding and reason
    # over the shared_knowledge cache only — fresh news shapes a ROADMAP, but a single-script regen /
    # pulse doesn't need it and shouldn't pay the web latency (mirror market_analyst / competitor_intel).
    hot_path = (state.get("workflow") or "") in _SKIP_WORKFLOWS
    web_snippets: list[str] = []
    if not hot_path and web_search_enabled():
        try:
            hits = await web_search(
                f"{niche_raw} Instagram trend yangiliklari {region} 2026", limit=6
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("industry_news.web_search_failed", error=str(exc)[:120])
            hits = []
        # Cache the live hits so competitor_intel/market_analyst + future runs
        # reuse them (read via recent_niche_news) instead of each re-querying.
        if hits:
            try:
                await save_web_results(niche_raw, region, hits)
            except Exception as exc:  # noqa: BLE001
                log.warning("industry_news.web_cache_failed", error=str(exc)[:120])
        for h in hits:
            title = (h.get("title") or "").strip()
            snippet = (h.get("snippet") or "").strip()
            if title or snippet:
                web_snippets.append(f"{title}: {snippet}".strip(": "))
            # Surface web hits as signals too (source_url provenance) so
            # competitor_intel / market_analyst can reuse them downstream.
            if title:
                signals.append(
                    {
                        "niche": niche_raw,
                        "headline": title,
                        "summary": snippet,
                        "source_url": h.get("url") or "",
                        "captured_at": "",
                    }  # type: ignore[typeddict-item]
                )

    if not signals and not web_snippets:
        return {
            "industry_signals": signals,
            "notes": [f"industry_news: no news for niche={niche_raw}"],
        }

    # Dedupe headlines (the source RSS + prior runs produce repeats — the
    # Industry Scout was spamming the same line 4-5x).
    seen: set[str] = set()
    unique: list[str] = []
    for s in signals:
        headline = (s.get("headline") or s.get("summary", "")[:120] or "").strip()
        key = headline.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(headline)

    # Synthesize which shift matters most for THIS niche (Haiku — cheap).
    analysis: dict = {}
    if unique or web_snippets:
        # Stage 6 — ground relevance in the user's own vault (their topics/brand),
        # so "which shift matters" is judged for THEM. Empty/onboarding → '' (no-op).
        vault = await load_vault_context(
            tenant_id, niche_raw, "FOYDALANUVCHI KONTEKSTI (bilim vault — shunga moslab tanla)"
        )
        payload = json.dumps(
            {"niche": niche_raw, "headlines": unique[:8], "web": web_snippets[:6], "vault": vault or None},
            ensure_ascii=False,
        )
        try:
            analysis = await groq_client.chat_json(
                system=_SYSTEM,
                user=payload,
                max_tokens=400,
                agent_name="industry_news",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("industry_news.synthesis_failed", error=str(exc)[:120])

    insight = (analysis.get("insight") or "").strip()
    if insight:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="industry",
            content=insight,
            run_id=run_id,
            important=True,
        )
    elif unique:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="industry",
            content=f"Yangi: {unique[0]}",
            run_id=run_id,
            important=True,
        )

    return {
        "industry_signals": signals,
        "industry_analysis": analysis,
        "notes": [
            f"industry_news: synthesized from {len(unique)} headlines "
            f"({len(web_snippets)} live web)"
        ],
    }

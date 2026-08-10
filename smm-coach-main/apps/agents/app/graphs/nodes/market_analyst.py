"""Market Analyst — combines the cross-tenant `shared_knowledge` cache with a
LIVE Instagram hashtag scrape, then turns both into ONE actionable insight via
Cerebras/Haiku, surfaced into `agent_messages` for the dashboard / agents feed.

Two data sources:
1. `shared_knowledge` — cross-tenant cache populated by `knowledge_seeder.py`
   (cheap, always available).
2. Live instagrapi hashtag scrape — REAL top posts in the user's niche right
   now (captions + view counts). Best-effort: skipped when scrapers aren't
   configured or IG blocks us, so the node still works on the cache alone.

The live posts make the insight grounded in what's ACTUALLY winning today,
not just the seeded signals — that's what "the market analyst uses the scraper
fully" means.
"""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import structlog

from app.agents.messaging import emit_message
from app.integrations.instagram import instagrapi_client
from app.integrations.llm import groq_client
from app.integrations.search import web_search, web_search_enabled
from app.memory.shared_knowledge import top_signals_for_region
from app.memory.vault_context import load_vault_context

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState, MarketSignal

log = structlog.get_logger(__name__)

# Cap the live scrape so a slow/rate-limited IG call never stalls the onboarding
# fan-out (market_analyst runs in parallel with industry_news). On timeout we
# fall back to shared_knowledge only.
_LIVE_SCRAPE_TIMEOUT_S = 25.0
_LIVE_POSTS_LIMIT = 8

_SYSTEM = """Sen Market Analyst agentisan — Instagram o'sish bo'yicha strateg.
Senga region trending signallari (hook/audio/format/hashtag), foydalanuvchining
niche'i va auditoriyasi, HAMDA shu niche'dagi BUGUNGI haqiqiy top postlar
(jonli hashtag scrape — sarlavha + ko'rishlar soni) beriladi.

Vazifa: shu ma'lumotlardan kelib chiqib BITTA amaliy, aniq tavsiya ber — bugun
shu niche+region uchun qaysi hook turi yoki format eng yaxshi ishlaydi va NEGA.
Jonli postlar yoki `web_trends` (jonli web-qidiruv) bor bo'lsa — ulardan REAL
misol keltir (qaysi mavzu/uslub ko'p ko'rilmoqda). Dalil sifatida 1-2 signal,
post yoki web-natija mavzusini keltir.
Har bir signalda `manba` bor: "real" = rasmiy Instagram o'lchovi (eng ishonchli),
"web" = jonli web-qidiruv, "taxmin" = model gipotezasi. Tavsiyani "real" va "web"
signallarga QUR; "taxmin" signalni hech qachon fakt sifatida taqdim etma — u faqat
yo'nalish beruvchi gipoteza, dalil emas.
`vault_context` (foydalanuvchining o'z brend/auditoriya faktlari) bo'lsa — tavsiyani
SHUNGA moslab ber, generik signaldan ustun qo'y.

JSON qaytar: {"insight": "<1-2 jumla amaliy tavsiya, dalil bilan>", "evidence": ["<signal/post>", ...]}
O'zbekcha, qisqa. Markdown yo'q, faqat JSON."""


# content_review / tracker_pulse skip the live scrape + web-search (see run) — mirror competitor_intel.
_SKIP_WORKFLOWS = {"content_review", "tracker_pulse"}


async def run(state: GrowthCoachState) -> dict:
    north = state.get("north_star") or {}
    region = north.get("region", "uz")
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="market",
        content=f"{region.upper()} regionining bugungi trending hook va audio'larini ko'rib chiqyapman.",
        run_id=run_id,
    )

    signals: list[MarketSignal] = await top_signals_for_region(region=region, limit=20)

    # On the content_review / tracker_pulse HOT path, skip the ~25s live IG scrape + web-search
    # grounding. Those exist to freshly shape a ROADMAP (onboarding/replan); a single-script regen or
    # a pulse just needs market_signals populated, which the cross-tenant shared_knowledge cache above
    # already provides. This kept the hottest user path (open task → regenerate) waiting ~25s for
    # trend data the script barely uses.
    hot_path = (state.get("workflow") or "") in _SKIP_WORKFLOWS

    # LIVE hashtag scrape — what's actually winning in this niche right now.
    # Best-effort + time-boxed so it never stalls the parallel fan-out.
    live_posts = [] if hot_path else await _scrape_live_posts(north)

    # Stage 3b — when the IG scrape returns nothing (no IG_SCRAPER_ACCOUNTS),
    # fall back to a live web search so the analyst still reasons over CURRENT
    # signals rather than only the stale cache. Best-effort + gated on a provider.
    web_trends: list[str] = []
    niche_q = (north.get("niche_detail") or north.get("niche") or "").strip()
    if not hot_path and not live_posts and niche_q and web_search_enabled():
        try:
            hits = await web_search(f"{niche_q} Instagram trend {region} 2026", limit=5)
        except Exception as exc:  # noqa: BLE001
            log.warning("market_analyst.web_search_failed", error=str(exc)[:120])
            hits = []
        web_trends = [
            f"{(h.get('title') or '').strip()}: {(h.get('snippet') or '').strip()}".strip(": ")
            for h in hits
            if h.get("title") or h.get("snippet")
        ]

    if not signals and not live_posts and not web_trends:
        return {
            "market_signals": signals,
            "notes": [f"market_analyst: no signals for region={region}"],
        }
    if live_posts:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="market",
            content=f"Sohangizdagi {len(live_posts)} ta bugungi top postni jonli ko'rib chiqdim.",
            run_id=run_id,
        )

    # Synthesize ONE actionable insight from the raw signals + live posts
    # (Cerebras/Haiku — cheap + reliable). This is what makes the agent reason
    # rather than echo a ranking.
    compact = [
        {
            "kind": s.get("kind"),
            "label": s.get("label"),
            "score": round(s.get("score", 0.0), 2),
            "manba": "real" if s.get("source") in ("graph_api", "business_discovery") else ("web" if s.get("source") == "web_search" else "taxmin"),
        }
        for s in signals[:12]
    ]

    # Stage 6 — ground the insight in this tenant's own vault (brand facts,
    # audience specifics, past wins) so the recommendation fits THIS user, not
    # just the generic niche signal.
    vault = await load_vault_context(
        tenant_id,
        f"{north.get('niche', '')} {north.get('niche_detail', '')} {north.get('target_audience', '')}",
        "BILIM VAULT (foydalanuvchining brend/auditoriya konteksti)",
    )

    payload = json.dumps(
        {
            "niche": north.get("niche", ""),
            "niche_detail": north.get("niche_detail", ""),
            "target_audience": north.get("target_audience", ""),
            "region": region,
            "signals": compact,
            "live_top_posts": live_posts,
            "web_trends": web_trends,
            "vault_context": vault,
        },
        ensure_ascii=False,
    )

    analysis: dict = {}
    try:
        # Cerebras (fast) with Haiku fallback — provider chosen centrally in groq_client.
        analysis = await groq_client.chat_json(
            system=_SYSTEM,
            user=payload,
            max_tokens=400,
            agent_name="market_analyst",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("market_analyst.synthesis_failed", error=str(exc)[:120])

    insight = (analysis.get("insight") or "").strip()
    if insight:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="market",
            content=insight,
            run_id=run_id,
            important=True,
        )
    elif signals:
        # LLM produced nothing — fall back to the raw top signal so the feed
        # still shows something concrete.
        hot = signals[0]
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="market",
            content=(
                f"Bugun {region.upper()}'da kuchli signal: {hot.get('label')} "
                f"(score {hot.get('score', 0.0):.2f}). Sohangiz uchun mos."
            ),
            run_id=run_id,
            important=True,
        )
    elif live_posts:
        top = max(live_posts, key=lambda p: p.get("views", 0))
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="market",
            content=(
                f"Sohangizda bugun eng ko'p ko'rilgan post: \"{(top.get('caption') or '')[:80]}\" "
                f"({top.get('views', 0):,} ko'rish). Shu uslubdan ilhom oling."
            ),
            run_id=run_id,
            important=True,
        )

    return {
        "market_signals": signals,
        "market_analysis": analysis,
        "notes": [
            f"market_analyst: {len(signals)} signals + {len(live_posts)} live posts "
            f"+ {len(web_trends)} web"
        ],
    }


def _niche_to_hashtag(north: dict) -> str | None:
    """Pick a hashtag to scrape from the user's niche. Falls back through
    niche → niche_detail → sub_niche; returns None when nothing usable."""
    for key in ("niche", "niche_detail", "sub_niche"):
        raw = str(north.get(key) or "").strip().lower()
        # Keep alnum only (hashtags can't contain spaces/punctuation).
        cleaned = "".join(c for c in raw.replace(" ", "") if c.isalnum() or c == "_")
        if len(cleaned) >= 3:
            return cleaned
    return None


async def _scrape_live_posts(north: dict) -> list[dict]:
    """Live IG hashtag scrape for the niche — best-effort + time-boxed.

    Returns a compact list of {caption, views, likes} for the top posts, or []
    when scrapers aren't configured / IG blocks us / it times out. Never raises
    into the node — market_analyst must keep working on the cache alone.
    """
    tag = _niche_to_hashtag(north)
    if not tag:
        return []
    try:
        result = await asyncio.wait_for(
            instagrapi_client.fetch_hashtag_posts(tag, limit=_LIVE_POSTS_LIMIT),
            timeout=_LIVE_SCRAPE_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort (incl. asyncio timeout)
        log.warning("market_analyst.live_scrape_failed", tag=tag, error=str(exc)[:120])
        return []
    if not result.get("ok"):
        return []
    return [
        {
            "caption": (p.get("caption") or "")[:120],
            "views": int(p.get("view_count") or p.get("play_count") or 0),
            "likes": int(p.get("like_count") or 0),
        }
        for p in result.get("posts", [])
    ]

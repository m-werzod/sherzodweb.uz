"""Top-level LangGraph for the growth-coach product.

The four cooperating agents run as parallel branches feeding a shared state,
then drift_detector + output_validator gate any proposed task before the
human approval step. Persistence is delegated to the Postgres checkpointer
so a user can leave at any node and resume days later.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings
from app.graphs.nodes import (
    account_tracker,
    adversarial_critic,
    broll_curator,
    caption_stylist,
    caption_translator,
    comment_sentinel,
    competitor_intel,
    drift_detector,
    footage_analyzer,
    groq_scorer,
    hashtag_curator,
    higgsfield_director,
    hook_optimizer,
    industry_news,
    initial_analysis,
    market_analyst,
    montage_director,
    openai_critic,
    output_validator,
    performance_review,
    post_analyzer,
    profile_auditor,
    roadmap_generator,
    roadmap_persister,
    runway_director,
    scriptwriter,
)
from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

_compiled: Any | None = None
_pool: Any | None = None
_compile_lock = asyncio.Lock()  # serialize cold-start compilation so two callers can't each
# build (and leak) a whole AsyncConnectionPool before either caches `_compiled`


def _strip_prisma_query_params(url: str) -> str:
    """Drops `?schema=...` and other Prisma-only query params that libpq
    rejects. Anything else (sslmode, host, etc.) is left alone."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    if not parts.query:
        return url
    safe = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "schema"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe), parts.fragment))


async def compile_graph() -> Any:
    """Lazy-compile the graph once per process. Idempotent + concurrency-safe."""
    global _compiled, _pool

    if _compiled is not None:
        return _compiled
    # Double-checked lock: without it, two concurrent first-callers (run_worker fans out) both
    # pass the guard above and each opens a pool — one is cached, the other leaks past shutdown().
    async with _compile_lock:
        if _compiled is not None:
            return _compiled

        settings = get_settings()
        # psycopg / libpq does not understand Prisma-specific query params like
        # `?schema=public`. Strip the query string before handing the URL to the
        # checkpointer.
        #
        # A health-checked connection POOL, not a single cached connection:
        # `from_conn_string` hands the (process-cached) compiled graph ONE connection for
        # the whole process life, so after a Postgres restart (deploy) or an idle-timeout
        # that connection stays dead forever and EVERY subsequent run fails with
        # "the connection is closed" until the process restarts. The pool's
        # `check_connection` runs a cheap liveness ping on checkout and transparently
        # replaces a dead connection, so runs self-heal across DB bounces. Connection kwargs
        # mirror what AsyncPostgresSaver.from_conn_string uses (autocommit + no prepared
        # statements + dict rows), which the checkpointer requires.
        _pool = AsyncConnectionPool(
            conninfo=_strip_prisma_query_params(settings.database_url),
            min_size=1,
            max_size=10,
            open=False,
            check=AsyncConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await _pool.open()
        saver = AsyncPostgresSaver(_pool)
        await saver.setup()

        builder: StateGraph = StateGraph(GrowthCoachState)

        builder.add_node("initial_analysis", initial_analysis.run)
        builder.add_node("competitor_intel", competitor_intel.run)
        builder.add_node("profile_auditor", profile_auditor.run)
        builder.add_node("roadmap_generator", roadmap_generator.run)
        builder.add_node("groq_scorer", groq_scorer.run)
        builder.add_node("openai_critic", openai_critic.run)
        builder.add_node("market_analyst", market_analyst.run)
        builder.add_node("industry_news", industry_news.run)
        builder.add_node("scriptwriter", scriptwriter.run)
        builder.add_node("hashtag_curator", hashtag_curator.run)
        builder.add_node("hook_optimizer", hook_optimizer.run)
        builder.add_node("caption_translator", caption_translator.run)
        builder.add_node("account_tracker", account_tracker.run)
        builder.add_node("comment_sentinel", comment_sentinel.run)
        builder.add_node("post_analyzer", post_analyzer.run)
        builder.add_node("caption_stylist", caption_stylist.run)
        builder.add_node("footage_analyzer", footage_analyzer.run)
        builder.add_node("broll_curator", broll_curator.run)
        builder.add_node("montage_director", montage_director.run)
        builder.add_node("higgsfield_director", higgsfield_director.run)
        builder.add_node("runway_director", runway_director.run)
        builder.add_node("drift_detector", drift_detector.run)
        builder.add_node("output_validator", output_validator.run)
        builder.add_node("adversarial_critic", adversarial_critic.run)
        builder.add_node("performance_review", performance_review.run)
        builder.add_node("roadmap_persister", roadmap_persister.run)

        # Entry router: the two lightweight "pulse" workflows skip the whole
        # roadmap chain — they only need their one node. Everything else enters
        # at initial_analysis as before.
        builder.add_conditional_edges(
            START,
            _entry_router,
            {
                "profile_audit": "profile_auditor",
                "comment_sentinel": "comment_sentinel",
                "post_analyzer": "post_analyzer",
                "montage": "footage_analyzer",
                "higgsfield": "higgsfield_director",
                "runway": "runway_director",
                "main": "initial_analysis",
            },
        )
        builder.add_edge("profile_auditor", END)
        builder.add_edge("comment_sentinel", END)
        builder.add_edge("post_analyzer", END)
        # Cinematic AI-video: one node plans the per-shot Higgsfield prompts + camera moves and writes the
        # final_render row (meta.renderSource=higgsfield); the montage_worker generates + assembles.
        builder.add_edge("higgsfield_director", END)
        # Runway restyle: one node builds the restyle prompt + writes the final_render row; the
        # montage_worker's runway branch does the video-to-video + assembly.
        builder.add_edge("runway_director", END)
        # Montage: see the footage (FootageMap) → curate stock B-roll for the shots the footage
        # misses → style captions → render. broll_curator only PLANS (writes meta.brollPlan); the
        # worker downloads + splices, so a b-roll failure never blocks captions or the render.
        builder.add_edge("footage_analyzer", "broll_curator")
        builder.add_edge("broll_curator", "montage_director")
        builder.add_edge("montage_director", "caption_stylist")
        builder.add_edge("caption_stylist", END)
        # Before the roadmap is generated, fold competitor + trend + niche intel into
        # analysis_summary so the onboarding roadmap is shaped by what's winning now.
        builder.add_edge("initial_analysis", "competitor_intel")
        builder.add_edge("competitor_intel", "roadmap_generator")

        # Quality chain: Claude generates tasks → Groq scores them → GPT-4o
        # critiques the whole roadmap. Three independent models, three views.
        builder.add_edge("roadmap_generator", "groq_scorer")
        builder.add_edge("groq_scorer", "openai_critic")

        # After the critique pass, fan out market + industry signals in parallel
        # before scriptwriter takes over.
        for node in ("market_analyst", "industry_news"):
            builder.add_edge("openai_critic", node)

        builder.add_edge("market_analyst", "scriptwriter")
        builder.add_edge("industry_news", "scriptwriter")

        # content_review writes a real script, so it gets the creative enrichment
        # chain (hashtags → A/B hook → IG caption) before the guards. Onboarding
        # (topics-only) skips straight to drift — there's no script to enrich yet.
        builder.add_conditional_edges(
            "scriptwriter",
            _after_scriptwriter,
            {
                "enrich": "hashtag_curator",
                "guards": "drift_detector",
            },
        )
        builder.add_edge("hashtag_curator", "hook_optimizer")
        builder.add_edge("hook_optimizer", "caption_translator")
        builder.add_edge("caption_translator", "drift_detector")
        builder.add_edge("drift_detector", "output_validator")

        # Adversarial critic runs AFTER the cheap regex/embedding guards so we
        # don't spend Gemini tokens critiquing scripts the cheap checks already
        # rejected. It demotes approved → rejected based on softer quality
        # signals (empty platitudes, fake urgency, unsupported quotes, hook-vs-
        # body contradictions) that regex can't see. Same routing as validator —
        # the _after_validator hook reads accumulators that both nodes populate.
        builder.add_edge("output_validator", "adversarial_critic")
        builder.add_conditional_edges(
            "adversarial_critic",
            _after_validator,
            {
                "persist": "roadmap_persister",
                "tracker": "account_tracker",
                "rewrite": "scriptwriter",
            },
        )

        # Persister → END. The roadmap is now a list of N bare topics; scripts are
        # written per-topic on demand (content_review) after the user answers the
        # Q&A interview — there is no bulk enrichment pass at onboarding.
        builder.add_edge("roadmap_persister", END)
        builder.add_edge("account_tracker", "performance_review")
        builder.add_edge("performance_review", END)

        _compiled = builder.compile(checkpointer=saver)
        log.info("graph.compiled")
        return _compiled


_MAX_REWRITES = 2


def _entry_router(state: GrowthCoachState) -> str:
    """START router — the two lightweight pulse workflows have their own
    single-node path; everything else runs the full chain from
    initial_analysis."""
    workflow = state.get("workflow")
    if workflow == "profile_audit_pulse":
        return "profile_audit"
    if workflow == "comment_sentinel_pulse":
        return "comment_sentinel"
    if workflow == "onboarding_post_audit":
        return "post_analyzer"
    if workflow == "montage_generation":
        return "montage"
    if workflow == "higgsfield_generation":
        return "higgsfield"
    if workflow == "runway_restyle":
        return "runway"
    return "main"


def _after_scriptwriter(state: GrowthCoachState) -> str:
    """Only content_review produced a real script worth enriching with
    hashtags / A/B hook / caption. Onboarding (topics-only) goes straight
    to the guards."""
    if state.get("workflow") == "content_review":
        return "enrich"
    return "guards"


def _after_validator(state: GrowthCoachState) -> str:
    """Route post-validation:
       - validation errors AND we haven't burned the rewrite budget yet
         AND there are still tasks to rewrite → scriptwriter for another pass
       - workflow == tracker_pulse → run tracker → performance_review
       - otherwise persist approved tasks to DB and end (HITL)

    The rewrite budget is read off `rejected_tasks` (accumulating reducer):
    each round adds rejected items, so once len(rejected) >= _MAX_REWRITES
    we stop looping. Without the cap the graph hits LangGraph's 50-step
    recursion limit when Claude can't satisfy the validator.
    """
    errors = state.get("validation_errors") or []
    proposed = state.get("proposed_tasks") or []
    rejected = state.get("rejected_tasks") or []
    log.info(
        "validator.routing",
        errors=len(errors),
        proposed=len(proposed),
        rejected_total=len(rejected),
        workflow=state.get("workflow"),
    )

    # No proposed tasks left to rewrite → nothing to do but persist what we
    # have (might be zero approved — that's the user's signal to retry).
    if errors and proposed and len(rejected) < _MAX_REWRITES:
        return "rewrite"
    if state.get("workflow") == "tracker_pulse":
        return "tracker"
    return "persist"


async def shutdown() -> None:
    global _compiled, _pool
    if _pool is not None:
        await _pool.close()
    _compiled = None
    _pool = None

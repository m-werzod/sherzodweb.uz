"""LangGraph state types for the growth-coach workflow.

The graph is one durable thread per (tenant, user, workflow). The state is
keyed reducers so nodes can append/merge without trampling on each other.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class NorthStar(TypedDict, total=False):
    niche: str
    niche_detail: str | None
    sub_niche: str | None
    target_audience: str
    brand_voice: str | None
    current_followers: int
    target_followers: int
    region: str
    deadline_iso: str | None
    embedding: list[float] | None
    roadmap_size: int
    # Goal taxonomy (Dizayn B) — structured objective drives the roadmap funnel
    # mix via goal_profiles.GOAL_PROFILES. GoalKey ∈ {reach, followers, views,
    # engagement, sales, authority}. None → roadmap_generator keeps the legacy
    # 60/30/10 funnel (pre-existing tenants unaffected).
    primary_goal: str | None
    secondary_goal: str | None
    goal_weight: float
    # Psychological profile (Dizayn A) — distilled OCEAN/motivation/archetype the
    # scriptwriter matches for tone. None when the psych interview never ran.
    psych_profile: dict[str, Any] | None


class AccountSnapshot(TypedDict, total=False):
    handle: str
    instagram_user_id: str | None
    follower_count: int
    following_count: int
    posts_count: int
    bio: str | None
    profile_url: str | None
    is_private: bool
    account_type: Literal["personal", "business", "creator", "unknown"]
    last_synced_at: str


class MarketSignal(TypedDict, total=False):
    kind: Literal["hook", "audio", "format", "hashtag"]
    region: str
    label: str
    score: float
    source: str
    captured_at: str
    payload: dict[str, Any]


class IndustrySignal(TypedDict, total=False):
    niche: str
    headline: str
    summary: str
    source_url: str
    captured_at: str


class TaskDraft(TypedDict, total=False):
    id: str | None
    parent_id: str | None
    title: str
    type: Literal["reel", "post", "carousel", "story", "live", "collab", "action"]
    hook: str
    script_md: str
    shot_list: list[dict[str, Any]]
    hashtags: list[str]
    audio_suggestion: str | None
    expected_metrics: dict[str, Any]
    drift_score: float | None
    predict_evidence: dict[str, Any] | None


class TrackerObservation(TypedDict, total=False):
    task_id: str
    instagram_post_id: str
    metrics: dict[str, Any]
    audience_reaction_summary: str
    observed_at: str
    # Stage 13 — deterministic performance classification (detectors.py).
    verdict: str  # underperform | watch | norm | breakout
    rates: dict[str, Any]  # reach_rate / er_reach / save_rate / send_rate


class CostLedger(TypedDict):
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float


def _merge_dict(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Reducer that shallow-merges dicts, with b winning on conflict."""
    return {**a, **b}


def _add_costs(a: CostLedger, b: CostLedger) -> CostLedger:
    # LangGraph initializes the channel value to `{}` before the first write,
    # so be defensive: missing keys count as zero.
    return CostLedger(
        input_tokens=a.get("input_tokens", 0) + b.get("input_tokens", 0),
        output_tokens=a.get("output_tokens", 0) + b.get("output_tokens", 0),
        cached_tokens=a.get("cached_tokens", 0) + b.get("cached_tokens", 0),
        cost_usd=a.get("cost_usd", 0.0) + b.get("cost_usd", 0.0),
    )


class GrowthCoachState(TypedDict, total=False):
    # Identity
    tenant_id: str
    user_id: str | None
    workflow: str
    run_id: str

    # Inputs
    north_star: NorthStar
    onboarding: dict[str, Any]

    # Content-review inputs (single-task script rewrite / brief fill). These
    # MUST be declared here — LangGraph filters the invocation state down to the
    # declared schema channels, so any key the dispatcher spreads in via
    # `**payload` that isn't listed gets dropped before nodes run. That was the
    # bug behind "regenerate does nothing" / brief stuck on "Scriptwriter
    # ishlamoqda": task_id never reached roadmap_generator's content_review
    # branch, so it produced 0 tasks.
    task_id: str | None
    regenerate: bool
    fill_brief: bool
    instructions: str | None
    # Faza D: the montage_generation input's "remove this element" instruction (rides input → state →
    # caption_stylist final_render meta.inpaintRemove → worker → inpaint). None = no inpaint.
    inpaint_remove: str | None
    # Faza C: scenario-matched background instruction (input → state → meta.decorBackground → worker
    # → matte + generated bg). None = no decor.
    decor_background: str | None
    # The task's status before regenerate flipped it to 'revising', so the
    # persister can restore it instead of force-promoting to 'in_progress'.
    prev_status: str | None
    # tracker_pulse single-task input — set by /publish so account_tracker
    # knows which IG post to refresh. Without this channel declared,
    # LangGraph drops the dispatcher's `**payload` keys before account_tracker
    # runs and the tracker falls back to the (slower) tenant-wide batch query.
    instagram_post_id: str | None

    # Latest snapshots
    account: AccountSnapshot
    analysis_summary: str
    # Topics the user has ALREADY published (from the onboarding IG post
    # analysis) — roadmap_generator avoids repeating them.
    existing_post_topics: list[str]
    # Faza 3 — weaknesses from the post-audit (instagram_accounts.deepAnalysis):
    # roadmap_generator is told to SOLVE them; groq_scorer rewards tasks that do.
    detected_weaknesses: list[str]

    # Cooperating agent outputs — appended, not overwritten
    market_signals: Annotated[list[MarketSignal], operator.add]
    industry_signals: Annotated[list[IndustrySignal], operator.add]
    tracker_observations: Annotated[list[TrackerObservation], operator.add]

    # Per-cycle LLM synthesis — REPLACED per pass (one dict, not accumulated).
    # Market/Industry analysts turn raw signals into a single actionable
    # insight; performance_review turns tracker observations into pivot
    # recommendations the dashboard surfaces for the user to approve.
    market_analysis: dict[str, Any]
    industry_analysis: dict[str, Any]
    # Competitor + trend + niche intel, folded into analysis_summary before the
    # roadmap is generated (REPLACED per pass, not accumulated).
    competitor_intel: dict[str, Any]
    performance_synthesis: dict[str, Any]

    # Roadmap / current proposal — these channels are REPLACED on each pass,
    # not accumulated. The cycle scriptwriter → drift_detector → validator
    # → scriptwriter would otherwise grow these lists without bound and the
    # graph would hit recursion limit.
    proposed_tasks: list[TaskDraft]
    approved_tasks: list[TaskDraft]

    # Rejected tasks DO accumulate — they're the rewrite-attempt counter
    # `_after_validator` reads to break out of the loop after N tries.
    rejected_tasks: Annotated[list[TaskDraft], operator.add]

    # Guard outputs — REPLACED per pass so old warnings don't stick around.
    drift_warnings: list[dict[str, Any]]
    validation_errors: list[dict[str, Any]]

    # Creative sub-agent outputs (content_review only). REPLACED per pass —
    # the hashtag/hook/caption nodes enrich proposed_tasks[0] in place and
    # also surface their result here so the persister + SSE feed can read it
    # without re-parsing the task dict. Onboarding (topics-only) skips these.
    caption_uz: str  # caption_translator → IG-ready caption (uz)
    hook_variants: list[dict[str, Any]]  # hook_optimizer → [{variant, hook, score}]

    # profile_audit_pulse input — the web route fetches the IG profile (it has
    # the OAuth token) and passes {profile, niche, goal} so the backend node
    # never has to decrypt a token or scrape. Declared so LangGraph keeps it.
    audit_input: dict[str, Any]
    # profile_audit_pulse output — the profile_auditor node's checklist of
    # 5-8 concrete profile improvements. Accumulating reducer so a re-audit
    # appends rather than racing (the node itself replaces the DB row).
    audit_items: Annotated[list[dict[str, Any]], operator.add]

    # comment_sentinel_pulse output — per-post comment sentiment summary.
    # REPLACED per pass (one post per pulse).
    comment_sentiment: dict[str, Any]

    # onboarding_post_audit output — post_analyzer's cross-post synthesis
    # (weaknesses + visual patterns + audience insights). REPLACED per pass.
    # Mirrored to instagram_accounts.deepAnalysis; read by initial_analysis.
    deep_analysis: dict[str, Any]

    # OpenAI critic feedback — REPLACED per pass. Persister can read this to
    # save the roadmap-level grade so the UI surfaces "GPT-4o said: B+ · ..."
    critic_summary: dict[str, Any]

    # Bookkeeping
    cost: Annotated[CostLedger, _add_costs]
    notes: Annotated[list[str], operator.add]


def empty_cost() -> CostLedger:
    return CostLedger(input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0)

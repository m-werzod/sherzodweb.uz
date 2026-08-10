"""Goal taxonomy — the single source of truth for how a user's Instagram
objective shapes the roadmap (Dizayn B).

This is the `agent_catalog.py`-style declarative source for the 6 goal
categories. `roadmap_generator` turns a tenant's `primary_goal` (+ optional
`secondary_goal`, blended by `goal_weight`) and current follower count into a
deterministic funnel mix, format/hook/CTA emphasis, and the KPI set the
tracker/performance-review loop should later measure.

Pure stdlib (dataclasses) so it stays trivially unit-testable in isolation,
with no LangGraph / DB imports.

GoalKey ∈ {reach, followers, views, engagement, sales, authority}.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# When a tenant has no structured goal yet (the 3 pre-existing tenants), the
# roadmap keeps the EXACT legacy funnel guidance (60/30/10) — see
# LEGACY_DIRECTIVE — so their output is byte-for-byte unchanged. DEFAULT_GOAL is
# only used as the fallback for KPI selection.
DEFAULT_GOAL = "followers"

FUNNEL_STAGES = ("awareness", "consideration", "conversion")


@dataclass(frozen=True)
class GoalProfile:
    key: str
    label_uz: str
    # Funnel distribution across the existing `funnelStage` enum. Sums to 1.0.
    funnel_mix: dict[str, float]
    # ContentTaskType distribution emphasis. Sums to ~1.0.
    type_mix: dict[str, float]
    # The Instagram ranking signal this goal optimises for (prompt + scorer).
    primary_signal: str
    hook_kinds: list[str]
    # Bias over the existing `ctaType` enum.
    cta_bias: list[str]
    cadence: str  # 'low' | 'medium' | 'high'
    length_s: tuple[int, int]
    kpi: list[str] = field(default_factory=list)


GOAL_PROFILES: dict[str, GoalProfile] = {
    "reach": GoalProfile(
        key="reach",
        label_uz="Tanilish / Qamrov",
        funnel_mix={"awareness": 0.70, "consideration": 0.25, "conversion": 0.05},
        type_mix={"reel": 0.85, "carousel": 0.10, "post": 0.05},
        primary_signal="sends (DM ulashish) + 3-soniya hold",
        hook_kinds=["contrarian", "question", "pattern_interrupt", "curiosity_gap"],
        cta_bias=["share", "save"],
        cadence="high",
        length_s=(7, 15),
        kpi=["shares_per_reach", "hold_3s", "non_follower_reach_pct"],
    ),
    "followers": GoalProfile(
        key="followers",
        label_uz="Obunachi o'sishi",
        funnel_mix={"awareness": 0.55, "consideration": 0.40, "conversion": 0.05},
        type_mix={"reel": 0.70, "carousel": 0.25, "post": 0.05},
        primary_signal="profil tashriflari + follow rate",
        hook_kinds=["mistake", "time_based", "i_wish_i_knew"],
        cta_bias=["follow", "comment"],
        cadence="high",
        length_s=(15, 30),
        kpi=["follow_rate", "profile_visits", "net_follower_growth"],
    ),
    "views": GoalProfile(
        key="views",
        label_uz="Ko'rishlar",
        funnel_mix={"awareness": 0.65, "consideration": 0.30, "conversion": 0.05},
        type_mix={"reel": 0.90, "carousel": 0.05, "post": 0.05},
        primary_signal="watch time + completion",
        hook_kinds=["mid_action_drop", "curiosity_gap", "time_based"],
        cta_bias=["save"],
        cadence="medium",
        length_s=(7, 15),
        kpi=["avg_watch_time", "completion_pct", "re_watch"],
    ),
    "engagement": GoalProfile(
        key="engagement",
        label_uz="Engagement / Jalb",
        funnel_mix={"awareness": 0.35, "consideration": 0.55, "conversion": 0.10},
        type_mix={"carousel": 0.45, "reel": 0.40, "story": 0.15},
        primary_signal="saves + shares",
        hook_kinds=["numbered_list", "question", "mistake"],
        cta_bias=["save", "comment"],
        cadence="medium",
        length_s=(15, 30),
        kpi=["engagement_rate", "save_rate"],
    ),
    "sales": GoalProfile(
        key="sales",
        label_uz="Sotuv / Lid",
        funnel_mix={"awareness": 0.25, "consideration": 0.35, "conversion": 0.40},
        type_mix={"reel": 0.55, "carousel": 0.25, "post": 0.20},
        primary_signal="link clicks / DM keyword",
        hook_kinds=["transformation", "mistake_then_solution", "curiosity_gap"],
        # UZ nuance: leads/sales usually close in DM/Telegram → dm before link.
        cta_bias=["dm", "link"],
        cadence="low",
        length_s=(15, 40),
        kpi=["dm_requests", "link_clicks", "conversion_rate"],
    ),
    "authority": GoalProfile(
        key="authority",
        label_uz="Ekspert / Taniqlilik",
        funnel_mix={"awareness": 0.35, "consideration": 0.55, "conversion": 0.10},
        type_mix={"reel": 0.65, "carousel": 0.30, "post": 0.05},
        primary_signal="reach + saves",
        hook_kinds=["contrarian", "authority_social_proof", "myth_busting"],
        cta_bias=["comment", "save"],
        cadence="medium",
        length_s=(15, 30),
        kpi=["saves", "branded_mentions", "dm_question_quality"],
    ),
}

VALID_GOALS = frozenset(GOAL_PROFILES)

# Exact legacy funnel guidance for tenants with no structured goal — keeps the
# pre-existing tenants' roadmaps unchanged (was hardcoded as SYSTEM_PROMPT 5b).
LEGACY_DIRECTIVE = (
    "--- KONTENT VORONKASI ---\n"
    "FUNNEL TAQSIMOTI (shu nisbatga AMAL QIL): awareness 60% · consideration 30% · conversion 10%\n"
    "awareness: keng auditoriya, viral hook, ulashiladigan/saqlanadigan.\n"
    "consideration: ishonch, 'qanday qilib', qiymat, case/natija.\n"
    "conversion: DM/link/taklif — obunachini mijozga aylantiradi.\n"
    "Boshida awareness ko'proq, oxiriga borib conversion ko'payadi. "
    "Har vazifaga funnelStage + mos ctaType ber."
)


def _clamp_weight(w: float | None) -> float:
    if w is None:
        return 0.7
    return max(0.6, min(0.8, float(w)))


def blend(
    primary: dict[str, float],
    secondary: dict[str, float] | None,
    weight: float,
) -> dict[str, float]:
    """primary*weight + secondary*(1-weight); primary-only when no secondary."""
    if not secondary:
        return dict(primary)
    return {
        stage: primary.get(stage, 0.0) * weight
        + secondary.get(stage, 0.0) * (1.0 - weight)
        for stage in FUNNEL_STAGES
    }


def modulate_by_followers(mix: dict[str, float], current_followers: int) -> dict[str, float]:
    """Bend the funnel by account maturity: a 0→1K account needs reach before
    conversion can work; a 10K+ account is ready to monetise. Renormalised to 1.
    """
    m = {stage: mix.get(stage, 0.0) for stage in FUNNEL_STAGES}
    if current_followers < 1000:
        m["awareness"] += 0.10
        m["conversion"] = max(0.0, m["conversion"] - 0.05)
    elif current_followers >= 10000:
        m["conversion"] += 0.05
        m["awareness"] = max(0.0, m["awareness"] - 0.05)
    total = sum(m.values()) or 1.0
    return {stage: v / total for stage, v in m.items()}


def resolve_funnel(north: dict) -> dict[str, float] | None:
    """The effective funnel mix for this tenant, or None if no structured goal."""
    primary = north.get("primary_goal")
    if not primary or primary not in GOAL_PROFILES:
        return None
    secondary_key = north.get("secondary_goal")
    secondary = (
        GOAL_PROFILES[secondary_key].funnel_mix
        if secondary_key in GOAL_PROFILES
        else None
    )
    weight = _clamp_weight(north.get("goal_weight"))
    mixed = blend(GOAL_PROFILES[primary].funnel_mix, secondary, weight)
    return modulate_by_followers(mixed, int(north.get("current_followers") or 0))


def funnel_percentages(north: dict) -> tuple[int, int, int]:
    """(awareness, consideration, conversion) integer % summing to exactly 100."""
    mix = resolve_funnel(north)
    if mix is None:
        return (60, 30, 10)
    a = round(mix["awareness"] * 100)
    c = round(mix["consideration"] * 100)
    v = round(mix["conversion"] * 100)
    # Force the sum to 100 by absorbing the rounding remainder into awareness.
    a += 100 - (a + c + v)
    return (a, c, v)


def goal_kpi(north: dict) -> list[str]:
    """The KPI set the tracker/performance-review loop should measure."""
    primary = north.get("primary_goal")
    if primary not in GOAL_PROFILES:
        primary = DEFAULT_GOAL
    return list(GOAL_PROFILES[primary].kpi)


def _fmt_mix(mix: dict[str, float]) -> str:
    return " · ".join(f"{k} {round(v * 100)}%" for k, v in mix.items())


def goal_directive_uz(north: dict) -> str:
    """The goal-specific instruction block injected into the roadmap prompt.

    Falls back to the EXACT legacy 60/30/10 guidance when the tenant has no
    structured goal, so pre-existing tenants are unaffected.
    """
    primary = north.get("primary_goal")
    if not primary or primary not in GOAL_PROFILES:
        return LEGACY_DIRECTIVE

    prof = GOAL_PROFILES[primary]
    a, c, v = funnel_percentages(north)
    secondary_key = north.get("secondary_goal")
    weight = _clamp_weight(north.get("goal_weight"))

    header = f"MAQSAD: {prof.label_uz}"
    if secondary_key in GOAL_PROFILES:
        header += (
            f" (+ {GOAL_PROFILES[secondary_key].label_uz}, "
            f"asosiy ulush {round(weight * 100)}%)"
        )

    return (
        f"--- {header} ---\n"
        f"FUNNEL TAQSIMOTI (shu nisbatga AMAL QIL): "
        f"awareness {a}% · consideration {c}% · conversion {v}%\n"
        f"ASOSIY ALGORITM SIGNALI: {prof.primary_signal} — har task shu signalni kuchaytirsin.\n"
        f"FORMAT URG'USI: {_fmt_mix(prof.type_mix)}\n"
        f"HOOK TURLARI (shulardan tanla): {', '.join(prof.hook_kinds)}\n"
        f"CTA URG'USI (ctaType): {', '.join(prof.cta_bias)}\n"
        f"Boshida awareness ko'proq, oxiriga borib conversion ko'payadi. "
        f"Har taskka mos funnelStage + ctaType ber."
    )

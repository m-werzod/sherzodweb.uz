"""Groq Llama 3.3 — fast task quality scorer.

Runs between roadmap_generator and scriptwriter. Takes each proposed task
and scores it on 4 dimensions in a single batch call:

  - viral_potential (1-10) — likelihood of high reach/saves
  - audience_fit (1-10)    — match with the user's stated target audience
  - difficulty (1-10)      — how hard to execute for a small creator
  - clarity (1-10)         — title + goal are concrete enough to act on

Tasks scoring < 5 on audience_fit or clarity get flagged for rewrite.
The full prompt + response is persisted to llm_calls so the user can
see exactly how Groq scored each task in the AI Inspector drawer.

Groq Llama 3.3 70B at 700 tok/s makes this a sub-2-second pass even
for 20 tasks. Cost ~$0.005 per onboarding.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.agents.messaging import emit_message
from app.graphs.goal_profiles import GOAL_PROFILES, funnel_percentages
from app.graphs.prompt_store import resolve_prompt
from app.integrations.llm.anthropic_client import call_claude

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)


SYSTEM_PROMPT = """Sen Instagram kontent strategiyasi bo'yicha **tezkor baholovchi**sisan. Senga taqdim etilgan roadmap'dagi har bir vazifani 6 ta o'lchovda baholaysan.

QOIDA — har vazifa uchun JSON ob'ekt qaytarasan:
{
  "title": "<vazifa nomi to'liq nusxasi>",
  "viral_potential": 1-10,    // Instagram'da yuqori reach/save olish ehtimoli
  "audience_fit": 1-10,       // target_audience bilan moslik
  "difficulty": 1-10,         // kichik creator uchun bajarish qiyinligi (10 = qiyin)
  "clarity": 1-10,            // title va goal_description aniqligi (10 = aniq)
  "addresses_weakness": 0-10, // akkauntning ANIQLANGAN kamchiligini qanchalik yechadi
  "goal_alignment": 0-10,     // task funnelStage+ctaType foydalanuvchi MAQSADIga (goal_context) mosligi
  "reasoning": "1-2 jumla — nima uchun shu ballar"
}

Ballar haqida:
- viral_potential 8+: kuchli hook + universal tema + Reels formati
- audience_fit 8+: target_audience'ning aynan og'riq nuqtasiga tegadi
- difficulty 3-: soatlardan emas, daqiqalardan oladi (oddiy, kamera tutib aytish)
- clarity 8+: title o'qiganda "men nima qilishimni bilaman" hissi
- addresses_weakness 8+: vazifa `detected_weaknesses`dagi aniq bir kamchilikni
  bevosita bartaraf etadi. Agar `detected_weaknesses` bo'sh bo'lsa — hammasiga 0 ber.
- goal_alignment 8+: task `funnelStage` `goal_context.funnel`dagi yuqori ulushli bosqichga
  to'g'ri keladi VA `ctaType` `goal_context.cta_bias` ichida. Agar
  `goal_context.primary_goal_label` null bo'lsa — `goal_alignment`ni `audience_fit` bilan
  bir xil (neytral) qo'y.

Chiqish FORMATI:
{"scores": [<har task uchun obyekt>...]}

Markdown blok yo'q. Tushuntirish matni yo'q. Faqat JSON."""


async def run(state: GrowthCoachState) -> dict:
    proposals = state.get("proposed_tasks") or []
    if not proposals:
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    north = state.get("north_star") or {}

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="market",  # use existing agent kind so UI knows the color
        content=(
            f"Claude Haiku bilan {len(proposals)} ta vazifaning sifat ballarini hisoblayman "
            "(viral, auditoriya mosligi, qiyinligi, aniqligi)."
        ),
        run_id=run_id,
    )

    # Compact payload — title + goal_description + type only. We don't want
    # to send 12 full scripts to Groq; it's a strategy-level grader.
    compact = [
        {
            "title": t.get("title", ""),
            "type": t.get("type", "reel"),
            "goal_description": t.get("goal_description") or t.get("hook") or "",
            "funnelStage": t.get("funnelStage") or t.get("funnel_stage"),
            "ctaType": t.get("ctaType") or t.get("cta_type"),
        }
        for t in proposals
    ]

    # Faza 3 — hand the post-audit weaknesses to the scorer so it can rate how
    # well each task solves them (addresses_weakness). Empty when no audit ran.
    weaknesses = state.get("detected_weaknesses") or []

    # Goal context (Dizayn B) — lets the scorer rate how well each task's
    # funnelStage + ctaType serve the user's chosen objective. None when the
    # tenant has no structured goal (legacy) → scorer keeps goal_alignment neutral.
    primary_goal = north.get("primary_goal")
    if primary_goal in GOAL_PROFILES:
        _prof = GOAL_PROFILES[primary_goal]
        _a, _c, _v = funnel_percentages(north)
        goal_context: dict = {
            "primary_goal_label": _prof.label_uz,
            "funnel": {"awareness": _a, "consideration": _c, "conversion": _v},
            "cta_bias": _prof.cta_bias,
        }
    else:
        goal_context = {"primary_goal_label": None}

    user_payload = json.dumps(
        {
            "north_star": {
                "soha": north.get("niche", ""),
                "soha_detail": north.get("niche_detail", ""),
                "target_audience": north.get("target_audience", ""),
                "current_followers": north.get("current_followers", 0),
                "target_followers": north.get("target_followers", 0),
            },
            "goal_context": goal_context,
            "detected_weaknesses": weaknesses,
            "tasks": compact,
        },
        ensure_ascii=False,
    )

    max_tokens = min(8000, 800 + len(compact) * 60)
    system_prompt = await resolve_prompt("groq_scorer", SYSTEM_PROMPT)
    # Score with Claude Haiku — reliable + cheap. The previous Gemini-based path
    # 503'd constantly in our region; call_claude has its own provider fallback
    # chain underneath. Scoring is non-critical, so on any failure we pass the
    # tasks through unscored (the roadmap is unaffected). max_tokens scales with
    # the task count so a cadence-sized roadmap (60-180 topics) doesn't truncate.
    try:
        resp, _usage = await call_claude(
            model="claude-haiku-4-5",
            system=system_prompt,
            messages=[{"role": "user", "content": user_payload}],
            max_tokens=max_tokens,
            response_format="json",
            agent_name="groq_scorer",
        )
        scored = json.loads(resp.get("text") or "{}")
    except Exception as exc:  # noqa: BLE001
        log.warning("groq_scorer.failed — passing through", error=str(exc)[:120])
        return {}

    scores_by_title: dict[str, dict] = {}
    for s in scored.get("scores", []) or []:
        title = (s.get("title") or "").strip().lower()
        if title:
            scores_by_title[title] = s

    enriched: list[dict] = []
    high_quality = 0
    needs_attention: list[str] = []
    for t in proposals:
        title_key = (t.get("title") or "").strip().lower()
        sc = scores_by_title.get(title_key) or {}
        if sc:
            t["groq_scores"] = {
                "viral_potential": sc.get("viral_potential"),
                "audience_fit": sc.get("audience_fit"),
                "difficulty": sc.get("difficulty"),
                "clarity": sc.get("clarity"),
                "addresses_weakness": sc.get("addresses_weakness"),
                "goal_alignment": sc.get("goal_alignment"),
                "reasoning": sc.get("reasoning"),
            }
            fit = int(sc.get("audience_fit") or 0)
            clarity = int(sc.get("clarity") or 0)
            if fit >= 7 and clarity >= 7:
                high_quality += 1
            if fit < 5 or clarity < 5:
                needs_attention.append(t.get("title", "?"))
        enriched.append(t)

    log.info(
        "groq_scorer.done",
        scored=len(scores_by_title),
        total=len(proposals),
        high_quality=high_quality,
        needs_attention=len(needs_attention),
    )

    if needs_attention:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="market",
            content=(
                f"Groq tahlili: {high_quality} ta yuqori sifatli vazifa. "
                f"{len(needs_attention)} ta vazifa aniqligi past — scriptwriter "
                "ularga ko'proq diqqat beradi."
            ),
            run_id=run_id,
            important=True,
        )
    else:
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="market",
            content=f"Groq tahlili: barcha {len(proposals)} ta vazifa o'tdi · sifat yaxshi.",
            run_id=run_id,
        )

    return {
        "proposed_tasks": enriched,
        "notes": [f"groq_scorer: scored {len(scores_by_title)}/{len(proposals)} tasks"],
    }

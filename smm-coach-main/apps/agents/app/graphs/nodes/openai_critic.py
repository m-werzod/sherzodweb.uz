"""OpenAI GPT-4o — adversarial roadmap critic.

Runs AFTER groq_scorer, BEFORE scriptwriter. Takes the complete roadmap
(plus Groq's per-task scores) and answers two pointed questions:

  1. What's MISSING from this roadmap? (formats, topics, ramps)
  2. Which 3 tasks are the WEAKEST and should be replaced?

GPT-4o has different training data and writing instincts than Claude —
the disagreement between the two models is the value. If both Claude
(roadmap_generator) and GPT-4o (critic) agree a task is good, we trust
it more. If GPT-4o flags a task as weak, scriptwriter pays extra
attention when fleshing it out.

Cost: ~$0.02 per onboarding (GPT-4o, ~1500 input + 800 output tokens).
Full prompt + response captured in llm_calls for the AI Inspector.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.agents.messaging import emit_message
from app.graphs.prompt_store import resolve_prompt
from app.integrations.llm import openai_client

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)


SYSTEM_PROMPT = """Sen Instagram'da o'sish strategiyalari bo'yicha **tanqidchi** mutaxassissan. Senga taqdim etilgan roadmap'ni boshqa AI agent yaratgan — sening vazifang uni adolatli, lekin qattiq qo'l bilan tanqid qilish.

Sen JAVOB BERISH KERAK:

1. **missing_aspects** — roadmap'da yetishmayotgan narsalar. 2-5 ta aniq element:
   - Qaysi kontent format bo'lmagan (carousel? story? live?)
   - Qaysi mavzular yo'q (collab? testimonials? educational deep-dive?)
   - Difficulty ramp to'g'rimi yoki birdaniga sakraydi?

2. **weakest_tasks** — eng zaif 2-3 ta vazifaning nomi va sababi:
   - Title juda umumiy ("Yangi post" kabi)
   - Goal_description noaniq ("ko'p obunachi olish" kabi)
   - Audience'ga aloqasi yo'q

3. **strongest_tasks** — eng kuchli 2-3 ta vazifaning nomi va sababi:
   - Aniq, harakatga chorlovchi
   - Sohaga bog'liq
   - Virallik potentsiali yuqori

4. **overall_grade** — A/B/C/D harf bahosi + 1 jumla umumiy xulosa.

5. **weakness_coverage** — agar payload'da "detected_weaknesses" (akkauntning post-audit'dan aniqlangan REAL kamchiliklari) bo'lsa: roadmap shu kamchiliklarni yetarlicha yechadimi? `covered` (qaysi kamchilik yechilgan) va `ignored` (qaysi biri e'tiborsiz qolgan) ro'yxatlari. Bo'sh bo'lsa — bo'sh ro'yxatlar.

Chiqish FORMATI:
{
  "missing_aspects": [{"aspect": "...", "why_important": "..."}],
  "weakest_tasks": [{"title": "...", "issue": "..."}],
  "strongest_tasks": [{"title": "...", "why_strong": "..."}],
  "overall_grade": "A|B|C|D",
  "overall_summary": "...",
  "weakness_coverage": {"covered": ["..."], "ignored": ["..."]}
}

O'zbek tilida yoz. Faqat JSON, markdown blok yo'q."""


# The roadmap critic ("what's missing / weakest tasks") only makes sense while SHAPING a roadmap
# (onboarding / replan). It was also running on every content_review + tracker_pulse — 2 wasted
# GPT-4o calls per single-script regen / pulse. Gate it out (mirror competitor_intel._SKIP_WORKFLOWS).
_SKIP_WORKFLOWS = {"content_review", "tracker_pulse"}


async def run(state: GrowthCoachState) -> dict:
    if (state.get("workflow") or "") in _SKIP_WORKFLOWS:
        return {}
    proposals = state.get("proposed_tasks") or []
    if not proposals:
        return {}

    if not openai_client.is_configured():
        log.info("openai_critic.skipped — OPENAI_API_KEY not set")
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    north = state.get("north_star") or {}

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="industry",
        content=(
            "OpenAI GPT-4o roadmap'ni tanqidiy ko'rib chiqyapti — "
            "nimalar yetishmaydi va qaysi vazifalar zaif?"
        ),
        run_id=run_id,
    )

    # Compact: title + type + goal_description + groq_scores summary.
    compact_tasks = []
    for t in proposals:
        scores = t.get("groq_scores") or {}
        compact_tasks.append({
            "title": t.get("title", ""),
            "type": t.get("type", "reel"),
            "goal_description": t.get("goal_description") or t.get("hook") or "",
            "groq_scores": {
                "viral": scores.get("viral_potential"),
                "fit": scores.get("audience_fit"),
                "clarity": scores.get("clarity"),
            } if scores else None,
        })

    user_payload = json.dumps(
        {
            "north_star": {
                "soha": north.get("niche", ""),
                "target_audience": north.get("target_audience", ""),
                "current_followers": north.get("current_followers", 0),
                "target_followers": north.get("target_followers", 0),
            },
            # Single-brain: the account's REAL weaknesses from the post-audit
            # (post_analyzer → initial_analysis). The critic checks the roadmap
            # actually addresses them, not just generic best-practice.
            "detected_weaknesses": state.get("detected_weaknesses") or [],
            "roadmap": compact_tasks,
        },
        ensure_ascii=False,
    )

    try:
        critique = await openai_client.chat_json(
            model="gpt-4o-mini",  # mini is plenty for a critique pass; saves ~5x cost
            system=await resolve_prompt("openai_critic", SYSTEM_PROMPT),
            user=user_payload,
            max_tokens=1500,
            temperature=0.4,
            agent_name="openai_critic",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("openai_critic.failed — passing through", error=str(exc)[:120])
        return {}

    grade = critique.get("overall_grade", "?")
    summary = critique.get("overall_summary", "")
    weakest = critique.get("weakest_tasks") or []
    missing = critique.get("missing_aspects") or []

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="industry",
        content=(
            f"GPT-4o bahosi: {grade} · {summary}. "
            + (
                f"Yetishmaydi: {', '.join(m.get('aspect', '?') for m in missing[:2])}."
                if missing else "Hech narsa muhim yetishmaydi."
            )
        ),
        run_id=run_id,
        important=True,
    )

    # Annotate the proposed tasks with the critic's flag — scriptwriter
    # uses this signal to put extra effort into weak ones.
    weak_titles = {(w.get("title") or "").strip().lower() for w in weakest}
    for t in proposals:
        title_key = (t.get("title") or "").strip().lower()
        if title_key in weak_titles:
            t["critic_flag"] = "weak"

    log.info(
        "openai_critic.done",
        grade=grade,
        weakest=len(weakest),
        missing=len(missing),
    )

    return {
        "proposed_tasks": proposals,
        "critic_summary": {
            "grade": grade,
            "summary": summary,
            "weakest_tasks": weakest,
            "missing_aspects": missing,
            "strongest_tasks": critique.get("strongest_tasks") or [],
            "weakness_coverage": critique.get("weakness_coverage") or {},
        },
        "notes": [f"openai_critic: grade {grade}, {len(weakest)} weak, {len(missing)} missing"],
    }

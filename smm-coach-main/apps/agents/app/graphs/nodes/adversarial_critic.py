"""Adversarial critic — second-pass LLM review that catches the bullshit a
regex can't.

The existing `output_validator` only flags loud quantitative claims (e.g.
"100K obunachi 2 haftada", "5x reach", "kafolatlangan"). Real failure modes
in generated scripts are softer:

  - Empty platitudes ("Faqat o'zing bo'l", "Tirishqoq bo'l", "Trendlarni
    kuzating") that fill a script with nothing
  - Fake urgency ("Bu hafta qilmasangiz kech!", "Hozir yoki hech qachon!")
  - Quotes about specific people without grounding (the LLM invented
    "Madina @x.x 312K obunachi qildi" with no exemplar to back it)
  - Hook-vs-body contradictions (hook promises a secret, body delivers
    generic advice)

Cheap (~$0.02/task on Gemini 2.5 Flash) but high leverage. Runs after the
regex validator so we don't pay for LLM critique on scripts the cheap
checks already rejected.

Failure modes are SOFT — if Gemini is down or the response doesn't parse,
the node returns `{}` and the script passes through unchanged. We never
WORSEN reliability to catch quality issues.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from app.config import get_settings
from app.graphs.prompt_store import resolve_prompt
from app.integrations.llm.gemini_client import call_gemini

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)


SYSTEM_PROMPT = """Sen Instagram senariylarning adversarial muharririsan. Maqsading — yaxshi ko'rinadigan, lekin haqiqatda BO'SH bo'lgan senariylarni topib rad etish.

Senga JSON formatda 1 yoki bir nechta senariy beriladi. Har bittasini quyidagi 4 ta mezon bo'yicha tahlil qil:

1. **Bo'sh nasihat** — senariyda asosiy MA'NO bormi yoki "trendlarni kuzating", "tirishqoq bo'ling", "faqat o'zingiz bo'ling" kabi umumiy, qiymatsiz nasihatlardan iborat? Agar 60%+ bo'sh nasihat bo'lsa → REJECT.

2. **Soxta shoshilinch** — "Bu hafta qilmasangiz kech!", "Hozir yoki hech qachon!", "Cheklangan vaqt!" kabi manipulyatsiya ishlatilganmi? → REJECT.

3. **Tasdiqlanmagan RAQAMLI natija-da'vosi** — senariy aniq odam yoki akkaunt haqida ANIQ RAQAMLI natija da'vo qiladimi ("@madina.style 312K qildi", "@username 100K ga yetdi" va h.k.)? Agar shu raqamli natija-da'vosi `exemplars` ro'yxati bilan tasdiqlanmagan bo'lsa → REJECT. DIQQAT: shunchaki akkauntni ESLATISH yoki umumiy misol (raqamli natija-da'vosisiz) REJECT EMAS — faqat soxta/tasdiqlanmagan RAQAM muammo.

4. **Hook ↔ tana ziddiyati** — hook nimani va'da qiladi va tana shuni yetkazadimi? Hook "yashirin sir" va'da qiladi, tana esa umumiy maslahat berib qolsa → REJECT.

Har bir senariy uchun:
- `task_id`: kirgan ID
- `ok`: true (senariy yaxshi) yoki false
- `reasons`: faqat rad etilganda — qisqa o'zbekcha sabab(lar), har biri max 150 belgi

QAT'IY format — faqat JSON, markdown yo'q:
```
{"results": [{"task_id": "0", "ok": true, "reasons": []}, ...]}
```

Shubhada — ok: true qil. Rad etish faqat aniq muammo bo'lganda. Bu narx samaradorligi uchun: yaxshi senariy noto'g'ri rad etilsa, scriptwriter qayta yozadi va qimmat Opus tokenlari yana sarflanadi."""


# Word-count sanity bounds the critic ALSO checks (cheap heuristic — if the
# scriptMd is way out of the expected range, the critic flags it without
# even consulting the model). 30-60s video = ~75-180 spoken words; we allow
# a slightly wider band so short-form punchy scripts and longer storytelling
# both fit.
_MIN_WORDS = 60
_MAX_WORDS = 500


def _has_rich_script(t: dict[str, Any]) -> bool:
    script = (t.get("script_md") or t.get("scriptMd") or "").strip()
    return bool(script) and (t.get("type") or "").lower() != "action"


def _word_count(s: str) -> int:
    return len(s.split())


def _allowed_exemplars(t: dict[str, Any]) -> list[str]:
    """Sources the script MAY cite (criterion #3 allow-list). Reads BOTH the retrieved `similarPosts`
    AND `exemplarSource` — the scriptwriter grounds real exemplars under exemplarSource/exemplarReach
    (see scriptwriter prompt), NOT similarPosts, so keying only on similarPosts left the allow-list
    permanently EMPTY and every legit exemplar/handle citation got rejected (wasted Opus rewrites)."""
    pe = t.get("predict_evidence") or t.get("predictEvidence") or {}
    if not isinstance(pe, dict):
        return []
    out = [
        str(e.get("postId") or e.get("source") or "")
        for e in (pe.get("similarPosts") or [])
        if isinstance(e, dict)
    ]
    src = pe.get("exemplarSource")
    if src:
        out.append(str(src))
    return [s for s in out if s]


async def run(state: GrowthCoachState) -> dict:
    """Critique each rich-script task in the current pass.

    Returns a state delta that:
      - APPENDS any critic findings to `validation_errors`
      - DEMOTES critiqued-out tasks from `approved_tasks` to `rejected_tasks`
        + `proposed_tasks` so the rewrite loop picks them up
      - Returns `{}` if there's nothing to critique, the LLM failed, or the
        response didn't parse (graceful pass-through).
    """
    approved = state.get("approved_tasks") or []
    candidates = [t for t in approved if _has_rich_script(t)]
    if not candidates:
        # Roadmap_generation (topics only) or all action tasks → no work.
        return {}

    # First pass: cheap word-count guard. If a script is way too short or
    # way too long, reject WITHOUT spending an LLM call. Most of these are
    # truncated outputs from Gemini hitting max_tokens during JSON gen.
    cheap_errors: list[dict[str, Any]] = []
    cheap_rejects: list[dict[str, Any]] = []
    survivors: list[dict[str, Any]] = []
    for t in candidates:
        script = (t.get("script_md") or t.get("scriptMd") or "").strip()
        wc = _word_count(script)
        if wc < _MIN_WORDS:
            cheap_errors.append({
                "task_title": t.get("title"),
                "critic_reason": f"Script juda qisqa: {wc} so'z (min {_MIN_WORDS})",
                "phase": "word_count",
            })
            cheap_rejects.append(t)
        elif wc > _MAX_WORDS:
            cheap_errors.append({
                "task_title": t.get("title"),
                "critic_reason": f"Script juda uzun: {wc} so'z (max {_MAX_WORDS})",
                "phase": "word_count",
            })
            cheap_rejects.append(t)
        else:
            survivors.append(t)

    # Run the Gemini critic only on candidates that survived the cheap guard.
    llm_errors: list[dict[str, Any]] = []
    llm_rejects: list[dict[str, Any]] = []
    llm_keepers: list[dict[str, Any]] = list(survivors)

    if survivors:
        payload = {
            "tasks": [
                {
                    "task_id": str(i),
                    "title": t.get("title", ""),
                    "hook": t.get("hook", ""),
                    "scriptMd": (t.get("script_md") or t.get("scriptMd") or "")[:4000],
                    # Exemplar sources the LLM is allowed to cite. If a NUMERIC result-claim in the
                    # script references a source not in this list → reject (criterion #3).
                    "exemplars": _allowed_exemplars(t),
                }
                for i, t in enumerate(survivors)
            ]
        }
        try:
            response_text, _ledger = await call_gemini(
                model=get_settings().model_adversarial_critic,
                system=await resolve_prompt("adversarial_critic", SYSTEM_PROMPT),
                user_text=json.dumps(payload, ensure_ascii=False),
                max_output_tokens=1500,
                agent_name="adversarial_critic",
                response_format="json",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("critic.llm_failed — pass-through", error=str(exc)[:120])
            # Fall through: LLM down → only the cheap guard's verdict applies.
            response_text = ""

        if response_text:
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError as exc:
                log.warning("critic.json_parse_failed", error=str(exc)[:120])
                parsed = {}

            results = parsed.get("results") if isinstance(parsed, dict) else None
            if isinstance(results, list):
                by_id = {
                    str(r.get("task_id", "")): r
                    for r in results
                    if isinstance(r, dict)
                }
                llm_keepers = []
                for i, t in enumerate(survivors):
                    verdict = by_id.get(str(i)) or {}
                    if verdict.get("ok") is False:
                        reasons = verdict.get("reasons") or []
                        if not isinstance(reasons, list):
                            reasons = [str(reasons)]
                        llm_errors.append({
                            "task_title": t.get("title"),
                            "critic_reasons": [str(r)[:200] for r in reasons[:4]],
                            "phase": "adversarial",
                        })
                        llm_rejects.append(t)
                    else:
                        llm_keepers.append(t)

    all_rejects = cheap_rejects + llm_rejects
    if not all_rejects:
        log.info(
            "critic.passed",
            candidates=len(candidates),
            survivors=len(survivors),
            llm_called=bool(survivors),
        )
        return {}

    # Rebuild the approved list: everything that wasn't a candidate (action
    # tasks, topics-only) carries through unchanged; among candidates, keep
    # only the ones the critic approved.
    non_candidates = [t for t in approved if not _has_rich_script(t)]
    new_approved = non_candidates + llm_keepers

    existing_errors = state.get("validation_errors") or []
    existing_proposed = state.get("proposed_tasks") or []

    log.info(
        "critic.rejected",
        candidates=len(candidates),
        cheap_rejects=len(cheap_rejects),
        llm_rejects=len(llm_rejects),
        new_approved=len(new_approved),
    )

    return {
        # REPLACE channel — concat with whatever validator already wrote so
        # neither phase's findings are dropped.
        "validation_errors": existing_errors + cheap_errors + llm_errors,
        # REPLACE channel — overwrite approved with the post-critic survivors.
        "approved_tasks": new_approved,
        # ACCUMULATOR — appends. Each rejected task counts toward _MAX_REWRITES
        # in _after_validator so the loop is bounded.
        "rejected_tasks": all_rejects,
        # REPLACE channel — append to whatever's already there (e.g. tasks the
        # regex validator just rejected) so the scriptwriter rewrite step
        # sees the union.
        "proposed_tasks": existing_proposed + all_rejects,
    }

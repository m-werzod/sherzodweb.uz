"""Hook Optimizer — Claude Sonnet produces a distinct B-variant hook and a
0..1 score predicting which of A/B will retain better.

The scriptwriter already emits Variant A (the primary hook). This node adds
a genuinely DIFFERENT second take — a different angle (question vs fact vs
mini-story) grounded in the user's past hooks + market signals — so the
brief's A/B toggle has a real second option, not a paraphrase.

Runs in the content_review chain after scriptwriter. Enriches
`proposed_tasks[0]`:
  - `hookVariantB`  (str)   → persister packs into `scriptVariantB` jsonb
  - `hookVariantScore` (float) → persister writes to `content_tasks.hookVariantScore`

Fail-soft: if Sonnet errors, the task keeps Variant A only and the UI keeps
the toggle hidden (scriptVariantB stays null).
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.agents.messaging import emit_message
from app.config import get_settings
from app.graphs.prompt_store import resolve_prompt
from app.graphs.reach_forecast import calibration_from_ratios, forecast_reach
from app.integrations.llm.anthropic_client import call_claude
from app.memory.tenant_history import (
    account_reach_baseline,
    reach_prediction_ratios,
    tenant_top_hooks,
)
from app.memory.vault_context import load_vault_context

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """Sen Instagram hook (ochuvchi jumla) mutaxassisisan. Senga
senariyning A-variant hook'i + foydalanuvchining oldingi hook'lari + bozor
signallari beriladi.

VAZIFA: A'dan TUBDAN BOSHQACHA B-variant hook yoz. Boshqacha yondashuv ishlat:
- Agar A savol bo'lsa → B faktdan boshlasin
- Agar A faktdan boshlasa → B mini-voqea yoki shaxsiy daqiqadan boshlasin
- Foydalanuvchining tonal uslubini saqla (energetik/sokin), lekin angle'ni o'zgartir
- B ham 1 jumla, jonli, 8-14 so'z

Keyin A va B'ni solishtirib, qaysi biri RETENTION'ni yaxshiroq ushlashini
0.0-1.0 oralig'ida bahola (score = B variant qancha kuchli; 0.5 = teng).

FAQAT JSON: {"hookVariantB": "<B hook>", "score": <0.0-1.0>, "reason": "<1 jumla>"}"""


async def run(state: GrowthCoachState) -> dict:
    if state.get("workflow") != "content_review":
        return {}

    proposals = state.get("proposed_tasks") or []
    if not proposals:
        return {}
    task = proposals[0]

    # Action tasks have no real hook to A/B.
    if (task.get("type") or "").lower() == "action":
        return {}

    hook_a = task.get("hook") or ""
    if not hook_a.strip():
        return {}

    # If the scriptwriter already emitted a B hook, respect it — just score.
    existing_b = task.get("hookVariantB") or task.get("hook_variant_b")

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    north = state.get("north_star") or {}
    market = state.get("market_signals") or []

    past_hooks = await tenant_top_hooks(
        tenant_id=tenant_id,
        exclude_task_id=state.get("task_id") or task.get("id"),
        limit=5,
    )
    # Stage 6: ground the B-hook in the user's vault (voice, origin story, recurring facts) so it
    # sounds like THEM, not a generic angle. Best-effort → '' on empty/failure.
    vault = await load_vault_context(
        tenant_id,
        f"{task.get('title', '')} {hook_a}".strip(),
        "FOYDALANUVCHI OVOZI VA FAKTLARI (bilim markazi)",
    )

    payload = {
        "hook_a": hook_a,
        "existing_hook_b": existing_b or None,
        "title": task.get("title", ""),
        "target_audience": north.get("target_audience", ""),
        "past_hooks": past_hooks,
        "market_signals": market[:3],
        "vault_voice": vault or None,
    }

    s = get_settings()
    try:
        response, _usage = await call_claude(
            model=s.model_scriptwriter_revise,  # Sonnet — cheap, instruction-following
            system=await resolve_prompt("hook_optimizer", SYSTEM_PROMPT),
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            max_tokens=400,
            response_format="json",
            agent_name="hook_optimizer",
        )
        parsed = _parse(response.get("text") or "{}")
    except Exception as exc:  # noqa: BLE001
        log.warning("hook_optimizer.failed", error=str(exc)[:120])
        return {"notes": ["hook_optimizer: failed, kept variant A only"]}

    hook_b = (parsed.get("hookVariantB") or existing_b or "").strip()
    if not hook_b:
        return {"notes": ["hook_optimizer: no B variant produced"]}

    score = _clamp_score(parsed.get("score"))

    task["hookVariantB"] = hook_b
    task["hookVariantScore"] = score

    # Stage 5 — turn the script-quality signals (hook retention + viral/fit
    # scores) into a deterministic numeric reach forecast grounded in the user's
    # own post baseline. This is the first place ALL the signals coexist on the
    # task. Best-effort: a failure leaves the scriptwriter's predict_evidence as
    # is (qualitative band), never blocks persistence.
    try:
        await _attach_reach_forecast(task, tenant_id, score)
    except Exception:  # noqa: BLE001
        log.warning("hook_optimizer.forecast_failed", exc_info=True)

    proposals[0] = task

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=f"Hook B-variant tayyor · A/B prognoz balli {score:.0%}.",
        run_id=run_id,
    )

    return {
        "proposed_tasks": proposals,
        "hook_variants": [
            {"variant": "A", "hook": hook_a},
            {"variant": "B", "hook": hook_b, "score": score},
        ],
        "notes": [f"hook_optimizer: B variant, score {score:.2f}"],
    }


async def _attach_reach_forecast(task: dict, tenant_id: str, hook_score: float) -> None:
    """Compute + merge a deterministic reach diapazon into task['predict_evidence']
    from the user's baseline + this task's quality signals."""
    pred = dict(task.get("predict_evidence") or task.get("predictEvidence") or {})
    groq = task.get("groq_scores") or {}
    baseline = await account_reach_baseline(tenant_id)
    # Stage 5 feedback loop: calibrate against how our PAST reach predictions
    # actually resolved for this tenant (systematic over/under-prediction).
    calibration = calibration_from_ratios(await reach_prediction_ratios(tenant_id))

    fc = forecast_reach(
        median_reach=float(baseline.get("medianReach") or 0.0),
        followers=int(baseline.get("followers") or 0),
        viral_potential=_num(groq.get("viral_potential")),
        audience_fit=_num(groq.get("audience_fit")),
        hook_score=hook_score,
        exemplar_reach=_num(pred.get("exemplarReach")),
        impact_band=pred.get("impactBand") or task.get("expectedImpact"),
        calibration=calibration,
    )

    # Merge forecast numbers over the qualitative fallback, but keep any
    # exemplar grounding the scriptwriter already attached.
    pred.update(fc)
    task["predict_evidence"] = pred


def _num(val: object) -> float | None:
    try:
        f = float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def _clamp_score(val: object) -> float:
    try:
        f = float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, f))

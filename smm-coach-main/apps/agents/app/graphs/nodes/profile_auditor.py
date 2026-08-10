"""Profile Auditor — Claude Sonnet scores a connected Instagram Business
profile and surfaces 5-8 concrete improvements (bio CTA, link, highlights,
category, contact buttons) so the account feels "professional" before the
content loop starts.

Runs as the `profile_audit_pulse` workflow:
  - Onboarding: fired once after IG connect.
  - Weekly: tracker_scheduler can re-fire to re-grade the profile.

The web route (`/api/instagram/profile-audit`) already has the OAuth token,
so it fetches the GraphProfile and hands {profile, niche, goal} to us via
`state.audit_input`. We never decrypt a token or scrape here — just LLM +
DB write. Result lands in `instagram_accounts.profileAudit` (jsonb), the
column the dashboard + /onboarding/profile-review render.

This replaces the old web-side `runProfileAudit()` (apps/web/src/lib/
instagram/profile-audit.ts) so ALL LLM calls live in the agents service
(CLAUDE.md rule) and show up in the AI Inspector.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text

from app.agents.messaging import emit_message
from app.config import get_settings
from app.graphs.prompt_store import resolve_prompt
from app.integrations.llm.anthropic_client import call_claude
from app.memory.db import get_sessionmaker

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)


SYSTEM_PROMPT = """Sen o'zbek kreatorlar uchun katta tajribali Instagram brend
konsultantisan. Foydalanuvchi Business/Creator akkauntini ulagan — uni o'z sohasi
uchun professional standartlarga solishtirib baholaysan.

5-8 ta ANIQ, BAJARILADIGAN yaxshilanishni aniqla. Har biri uchun:
- field: qaysi Instagram profil maydoni (username, name, biography, profile_picture, external_link, category, highlights, contact_button)
- severity: "high" — o'sishni to'sadi, "medium" — cheklaydi, "low" — kosmetik
- title: 4-7 so'z o'zbekcha, muammo ("Bio'da CTA yo'q")
- detail: 1-2 jumla o'zbekcha — nega muhim
- suggestion: foydalanuvchi nusxalab qo'ya oladigan ANIQ matn/qiymat (imkon bo'lsa)

Profil qanchalik professional ekanini 0-100 ball bilan bahola.

FAQAT bitta JSON obyekt qaytar, izohsiz:
{
  "score": <int 0-100>,
  "items": [
    {"field": "biography", "severity": "high", "title": "<uz>", "detail": "<uz>", "suggestion": "<aniq uz matn>"}
  ]
}"""

_VALID_FIELDS = {
    "username",
    "name",
    "biography",
    "profile_picture",
    "external_link",
    "category",
    "highlights",
    "contact_button",
}
_VALID_SEVERITY = {"high", "medium", "low"}


async def run(state: GrowthCoachState) -> dict:
    if state.get("workflow") != "profile_audit_pulse":
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    audit_input = state.get("audit_input") or {}
    profile = audit_input.get("profile") or {}
    niche = audit_input.get("niche")
    goal = audit_input.get("goal")

    if not profile.get("username"):
        log.warning("profile_auditor.no_profile", tenant_id=tenant_id)
        return {"notes": ["profile_auditor: no profile in audit_input"]}

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="market",
        content="Profilingni professional standartlarga solishtirib tahlil qilyapman...",
        run_id=run_id,
    )

    s = get_settings()
    try:
        response, _usage = await call_claude(
            model=s.model_initial_analysis,
            system=await resolve_prompt("profile_auditor", SYSTEM_PROMPT),
            messages=[{"role": "user", "content": _build_user_prompt(profile, niche, goal)}],
            max_tokens=2000,
            response_format="json",
            agent_name="profile_auditor",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("profile_auditor.llm_failed", error=str(exc)[:160])
        return {"notes": ["profile_auditor: LLM failed"]}

    parsed = _parse(response.get("text") or "{}")
    score = max(0, min(100, int(parsed.get("score") or 0)))
    items = _normalize_items(parsed.get("items") or [])

    # Merge with the prior audit: keep items the user already marked done/skipped
    # (match by field), replace `open` items with the fresh AI output — so a
    # re-audit never resets the user's progress. This logic used to live in the
    # web route; it moves here with the LLM call.
    items = await _merge_prior(tenant_id, items)

    audit = {
        "score": score,
        "generatedAt": _now(),
        "niche": niche,
        "goal": _goal_str(goal),
        "items": items,
    }

    await _persist(tenant_id, profile.get("username", ""), audit)

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="market",
        content=f"Profil auditi tayyor · {score}/100 ball · {len(items)} ta tavsiya.",
        run_id=run_id,
        important=True,
    )

    return {
        "audit_items": items,
        "notes": [f"profile_auditor: score {score}, {len(items)} items"],
    }


def _build_user_prompt(profile: dict, niche: str | None, goal: dict | None) -> str:
    lines = [
        f"Niche: {niche or 'unknown'}",
    ]
    if goal:
        lines.append(
            f"Goal: {goal.get('current', 0)} → {goal.get('target', 0)} obunachi · "
            f"{goal.get('months', 0)} oy"
        )
    lines += [
        "",
        "Joriy Instagram profil:",
        f"- username: @{profile.get('username', '')}",
        f"- name: {profile.get('name') or '(not set)'}",
        f"- biography: {repr(profile.get('biography')) if profile.get('biography') else '(empty)'}",
        f"- profile_picture: {'set' if profile.get('profile_picture_url') else 'not set'}",
        f"- account_type: {profile.get('account_type') or 'unknown'}",
        f"- followers: {profile.get('followers_count') or 0}",
        f"- posts: {profile.get('media_count') or 0}",
        "",
        "Yuqoridagi soha uchun eng yaxshi amaliyotlarga solishtirib, schema bo'yicha JSON qaytar.",
    ]
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Salvage a fenced/embedded object.
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def _normalize_items(raw_items: list) -> list[dict]:
    out: list[dict] = []
    for it in raw_items[:10]:
        if not isinstance(it, dict):
            continue
        field = it.get("field")
        if field not in _VALID_FIELDS:
            continue
        severity = it.get("severity")
        if severity not in _VALID_SEVERITY:
            severity = "medium"
        title = (it.get("title") or "").strip()
        if not title:
            continue
        out.append(
            {
                "id": uuid.uuid4().hex[:8],
                "field": field,
                "severity": severity,
                "title": title,
                "detail": (it.get("detail") or "").strip(),
                "suggestion": (it.get("suggestion") or "").strip() or None,
                "status": "open",
            }
        )
    return out


async def _merge_prior(tenant_id: str, fresh_items: list[dict]) -> list[dict]:
    """Carry forward done/skipped status from the prior audit (match by field)."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = await session.execute(
                text(
                    'SELECT "profileAudit" FROM instagram_accounts '
                    'WHERE "tenantId" = :tid ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"tid": tenant_id},
            )
            prior = row.scalar()
    except Exception:  # noqa: BLE001
        return fresh_items

    if not prior or not isinstance(prior, dict):
        return fresh_items

    prior_by_field = {
        it.get("field"): it
        for it in (prior.get("items") or [])
        if isinstance(it, dict) and it.get("status") in {"done", "skipped"}
    }
    for it in fresh_items:
        old = prior_by_field.get(it.get("field"))
        if old:
            it["status"] = old["status"]
            if old.get("fixedAt"):
                it["fixedAt"] = old["fixedAt"]
    return fresh_items


async def _persist(tenant_id: str, username: str, audit: dict) -> None:
    """Write the audit onto the tenant's IG account row. Best-effort —
    the SSE message already informed the user, so a DB hiccup just means
    the dashboard checklist won't refresh until the next audit."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text(
                    """
                    UPDATE instagram_accounts
                    SET "profileAudit" = CAST(:audit AS jsonb),
                        "updatedAt" = NOW()
                    WHERE "tenantId" = :tid
                    """
                ),
                {"tid": tenant_id, "audit": json.dumps(audit, ensure_ascii=False)},
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        log.exception("profile_auditor.persist_failed", tenant_id=tenant_id)


def _goal_str(goal: dict | None) -> str | None:
    if not goal:
        return None
    return f"{goal.get('current', 0)}→{goal.get('target', 0)} · {goal.get('months', 0)}m"


def _now() -> str:
    return datetime.now(UTC).isoformat()

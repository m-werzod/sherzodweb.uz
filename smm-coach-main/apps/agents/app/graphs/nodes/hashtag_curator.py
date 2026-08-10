"""Hashtag Curator — Groq Llama picks 10-12 hashtags for a finished script:
a mix of 3-4 niche, 3-4 broad, 3-4 local (#uzbekistan, #toshkent, #reelsuz).

Runs in the content_review chain, right after scriptwriter writes the rich
script. Enriches `proposed_tasks[0]["hashtags"]` in place so the persister's
`_update_single_task` writes it to `content_tasks.hashtags` (it already reads
`task.get("hashtags")`).

Fail-soft: if Groq errors or returns junk, we leave whatever hashtags the
scriptwriter already produced and emit a soft note. A missing hashtag list
must never block the (already-written) script from persisting.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.agents.messaging import emit_message
from app.graphs.prompt_store import resolve_prompt
from app.integrations.llm import groq_client
from app.memory.vault_context import load_vault_context

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """Sen Instagram hashtag strategi mutaxassisisan. Senga senariy
(yoki mavzu) + soha + region beriladi. 10-12 ta hashtag tanla:
- 3-4 ta SOHA hashtag (aniq, niche-specific)
- 3-4 ta UMUMIY hashtag (keng qamrovli, lekin spam emas)
- 3-4 ta LOKAL hashtag (#uzbekistan, #toshkent, #reelsuz, #ozbekiston kabi)

Qoidalar:
- # belgisi bilan, bo'shliqsiz, kichik harflarda
- 50M+ postli ulkan generic taglardan (#love #instagood) qoch — ko'rinmay ketadi
- Soha + lokal aralashmasi eng yaxshi reach beradi

FAQAT JSON: {"hashtags": ["#tag1", "#tag2", ...]}"""

_MIN = 6
_MAX = 14


async def run(state: GrowthCoachState) -> dict:
    # Only the content_review chain writes a real script worth tagging.
    # Onboarding (topics-only) walks past untouched.
    if state.get("workflow") != "content_review":
        return {}

    proposals = state.get("proposed_tasks") or []
    if not proposals:
        return {}
    task = proposals[0]

    # Action tasks (profile setup) aren't posts — no hashtags.
    if (task.get("type") or "").lower() == "action":
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    north = state.get("north_star") or {}

    # Stage 6 — consult the vault so tags reflect the user's real niche terms +
    # recurring local audience facts, not just the generic niche label.
    vault = await load_vault_context(
        tenant_id,
        f"{task.get('title', '')} {task.get('hook', '')} {north.get('niche', '')}",
        "BILIM VAULT (foydalanuvchining soha/lokal kontekstidan hashtag uchun)",
    )

    payload = {
        "title": task.get("title", ""),
        "hook": task.get("hook", ""),
        "script": (task.get("script_md") or task.get("scriptMd") or "")[:1200],
        "niche": north.get("niche", "general"),
        "region": north.get("region", "Uzbekistan"),
    }
    if vault:
        payload["vault_context"] = vault

    try:
        parsed = await groq_client.chat_json(
            system=await resolve_prompt("hashtag_curator", SYSTEM_PROMPT),
            user=json.dumps(payload, ensure_ascii=False),
            max_tokens=400,
            agent_name="hashtag_curator",
        )
        tags = _clean(parsed.get("hashtags") or [])
    except Exception as exc:  # noqa: BLE001
        log.warning("hashtag_curator.failed", error=str(exc)[:120])
        await emit_message(
            tenant_id=tenant_id,
            user_id=user_id,
            agent="writer",
            content="Hashtaglar avtomatik yaratilmadi — senariydagi mavjudlar saqlandi.",
            run_id=run_id,
        )
        return {"notes": ["hashtag_curator: failed, kept existing"]}

    if len(tags) < _MIN:
        # Too few to be useful — keep whatever the scriptwriter emitted.
        return {"notes": [f"hashtag_curator: only {len(tags)} tags, kept existing"]}

    # Enrich the task in place; the persister reads task["hashtags"].
    task["hashtags"] = tags
    proposals[0] = task

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=f"{len(tags)} ta hashtag tanlandi (soha + umumiy + lokal).",
        run_id=run_id,
    )

    return {
        "proposed_tasks": proposals,
        "notes": [f"hashtag_curator: {len(tags)} tags"],
    }


def _clean(raw: list) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        tag = item.strip().lower().replace(" ", "")
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        # Strip anything that isn't a hashtag char.
        tag = "#" + "".join(c for c in tag[1:] if c.isalnum() or c == "_")
        if len(tag) < 3 or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
        if len(out) >= _MAX:
            break
    return out

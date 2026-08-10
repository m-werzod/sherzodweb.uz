"""Caption Translator — Groq Llama turns a finished script into an IG-ready
caption (Uzbek, 200-2200 chars, hook up front, hashtags appended).

A reel script is shot instructions + voiceover; the IG *caption* is a
different artifact — a short written hook + value + CTA the viewer reads
under the video. This node produces it so the user can copy-paste straight
into Instagram.

Runs in the content_review chain after hashtag_curator (so it can append the
curated hashtags). Enriches `proposed_tasks[0]["igCaption"]`; the persister
writes it to `content_tasks.igCaption`.

Fail-soft: on any error we fall back to the script's first paragraph + the
hashtags, so the caption field is never empty.
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

SYSTEM_PROMPT = """Sen Instagram caption (post tagi ostidagi matn) mutaxassisisan.
Senga reel senariysi beriladi. Undan IG'ga TAYYOR caption yoz (o'zbekcha):

TUZILISH:
1. Birinchi qator — kuchli ochuvchi (hook), odam to'xtab o'qishi uchun
2. 2-4 qator — qiymat/voqea (qisqa, bo'sh qator bilan ajratilgan)
3. CTA — aniq harakat ("Saqlab qo'y", "Do'stingga yubor", "Izohda yoz")
4. Oxirida hashtaglar (berilgan bo'lsa)

QOIDALAR:
- 200-2200 belgi oralig'ida
- Jonli, suhbat ohangida — robotga o'xshamasin
- Emoji o'rinli ishlatilsin (haddan oshmasin)
- Senariydagi shaxsiy faktlarni saqla, yangi fakt O'YLAB TOPMA

FAQAT JSON: {"caption": "<to'liq caption matni>"}"""

_MIN_LEN = 60
_MAX_LEN = 2200


async def run(state: GrowthCoachState) -> dict:
    if state.get("workflow") != "content_review":
        return {}

    proposals = state.get("proposed_tasks") or []
    if not proposals:
        return {}
    task = proposals[0]

    # Action tasks aren't posts.
    if (task.get("type") or "").lower() == "action":
        return {}

    script_md = task.get("script_md") or task.get("scriptMd") or ""
    if not script_md.strip():
        return {}

    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    hashtags = task.get("hashtags") or []

    # Stage 6: consult the vault so the caption sounds like THIS user (their voice, recurring
    # facts) instead of a generic translation. Best-effort → '' for a fresh/empty vault.
    vault = await load_vault_context(
        tenant_id,
        f"{task.get('hook', '')} {task.get('title', '')}".strip(),
        "FOYDALANUVCHI OVOZI VA FAKTLARI (bilim markazi) — captionni shu ovoz/uslubda yoz, yangi fakt o'ylab topma",
    )

    payload = {
        "hook": task.get("hook", ""),
        "script": script_md[:2000],
        "hashtags": hashtags,
        "vault_voice": vault or None,
    }

    caption = ""
    try:
        parsed = await groq_client.chat_json(
            system=await resolve_prompt("caption_translator", SYSTEM_PROMPT),
            user=json.dumps(payload, ensure_ascii=False),
            max_tokens=900,
            agent_name="caption_translator",
        )
        caption = (parsed.get("caption") or "").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("caption_translator.failed", error=str(exc)[:120])

    # Fallback — never leave the caption empty.
    if len(caption) < _MIN_LEN:
        caption = _fallback(task.get("hook", ""), script_md, hashtags)

    caption = caption[:_MAX_LEN]

    task["igCaption"] = caption
    proposals[0] = task

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content="Instagram caption tayyor — nusxalab post'ga qo'yish mumkin.",
        run_id=run_id,
    )

    return {
        "proposed_tasks": proposals,
        "caption_uz": caption,
        "notes": [f"caption_translator: {len(caption)} chars"],
    }


def _fallback(hook: str, script_md: str, hashtags: list[str]) -> str:
    """First paragraph of the script + hook + hashtags — guarantees a caption."""
    first_para = ""
    for block in script_md.split("\n\n"):
        cleaned = block.strip().lstrip("#").strip()
        if len(cleaned) > 40:
            first_para = cleaned
            break
    parts = [p for p in [hook.strip(), first_para] if p]
    body = "\n\n".join(parts) or hook or "Yangi post 🎬"
    if hashtags:
        body += "\n\n" + " ".join(hashtags)
    return body.strip()

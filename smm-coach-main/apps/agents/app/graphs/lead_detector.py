"""Lead detector — Stage 12 (autonomous sales funnel).

Given a published post's comments, finds the ones that signal *buying / sales
intent* (price questions, "qayerdan olsa bo'ladi", "buyurtma", "hamkorlik",
"DM", …) and drafts a short, on-voice reply that nudges the commenter toward
the next step. Pure-ish helper: one `fast_llm` JSON call, no DB. The caller
(`comment_sentinel`) persists the results as `leads` rows.

Why a separate pass from sentiment: sentiment is an aggregate mood gauge over
the whole comment set; a lead is a *single actionable commenter* the user
should reply to. Different granularity, different output shape.
"""
from __future__ import annotations

import json

import structlog

from app.integrations.llm import groq_client

log = structlog.get_logger(__name__)

# Actionable kinds the funnel cares about. 'lead' = sales/interest, 'question'
# = a real question worth answering (also a soft lead). Everything else
# (praise/criticism/spam) is ignored here — sentiment already covers mood.
_ACTIONABLE = {"lead", "question"}

_SYS = """Sen SMM sotuv-voronkasi yordamchisisan (ChatPlace). Senga bitta Instagram
postning izohlari raqamlangan ro'yxat sifatida beriladi.

Vazifang — SOTUV/QIZIQISH signalini bergan izohlarni top:
- narx so'ragan ("narxi qancha?", "qancha turadi?")
- sotib olishni xohlagan ("qayerdan olsa bo'ladi?", "buyurtma", "olaman", "bor?")
- hamkorlik / xizmat so'ragan ("hamkorlik", "reklama", "buyurtma qabul qilasizmi?")
- DM/aloqa so'ragan ("DM yozing", "telefon raqam?")
- jiddiy savol bergan (mahsulot/xizmat haqida aniq savol)

Maqtov, oddiy emoji, tanqid yoki spam — LEAD EMAS, ularni tashlab ket.

Har bir aniqlangan lead uchun blogger nomidan QISQA (1-2 jumla), samimiy, o'zbekcha
javob/DM-ochuvchi yoz — muloyim qiziqtir va keyingi qadamga (DM, narx, link) yo'naltir.

JSON qaytar:
{"leads": [{"index": <izoh raqami>, "intent": "lead"|"question", "draftReply": "<javob matni>"}]}
Hech qanday lead bo'lmasa: {"leads": []}. Faqat JSON, markdown yo'q."""


async def detect_leads(texts: list[str], *, persona: str = "", max_comments: int = 30) -> list[dict]:
    """Classify a post's comments and return actionable leads.

    `texts` is the ordered list of raw comment strings (same order the caller
    holds the comment metadata in, so `index` maps back to a comment id/handle).
    `persona` (optional) is a short blogger-context block (niche + brand voice) so
    the drafted replies sound like the ACTUAL user in their niche, not a generic bot.
    Returns a list of `{"index", "intent", "draftReply"}` — indices are
    validated against `len(texts)` and intents clamped to the actionable set.
    """
    clean = [t for t in texts if t and t.strip()][:max_comments]
    if not clean:
        return []

    system = _SYS
    if persona.strip():
        system += (
            "\n\nBLOGGER KONTEKSTI (draftReply AYNAN shu ovozda va shu soha tilida bo'lsin — "
            "umumiy bot javobi emas):\n" + persona.strip()[:600]
        )
    numbered = [{"index": i, "text": t[:300]} for i, t in enumerate(clean)]
    try:
        parsed = await groq_client.chat_json(
            system=system,
            user=json.dumps({"comments": numbered}, ensure_ascii=False),
            max_tokens=900,
            agent_name="lead_detector",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("lead_detector.failed", error=str(exc)[:140])
        return []

    out: list[dict] = []
    seen: set[int] = set()
    for item in parsed.get("leads") or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(clean) or idx in seen:
            continue
        intent = str(item.get("intent") or "lead").strip().lower()
        if intent not in _ACTIONABLE:
            intent = "lead"
        reply = str(item.get("draftReply") or "").strip()[:600]
        seen.add(idx)
        out.append({"index": idx, "intent": intent, "draftReply": reply})
    return out

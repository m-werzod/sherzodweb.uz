"""POST /v1/script-interview — adaptive, one-question-at-a-time interview.

Before regenerating a script we run a short CHAT with the user: the AI asks one
topic-specific question, reads the answer, then asks the next question that
BUILDS ON it. After ~4-5 turns it signals `done`. The full transcript is handed
to the scriptwriter so the script is grounded in the user's REAL story instead
of a fabricated one ("2 yil oldin savdo botini yozdim..." was invented).

Stateless per turn: the web holds the conversation and posts the full history on
every call; this endpoint just returns the next question (or `done`). The
adaptivity comes from feeding the whole history back to the model each turn.
HMAC-protected by the global middleware like every /v1 route.
"""
from __future__ import annotations

import json

import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.graphs.text_quality import is_substantive_answer
from app.integrations import telegram
from app.integrations.llm import groq_client
from app.memory.db import get_sessionmaker
from app.memory.knowledge_vault import related_notes

router = APIRouter()
log = structlog.get_logger(__name__)

# Hard cap so the interview always terminates even if the model never says done.
# Adaptive: the model usually finishes at 3-5; 8 gives room for a richer dig.
_MAX_QUESTIONS = 8


class Turn(BaseModel):
    role: str  # "assistant" (AI question) | "user" (answer)
    content: str


class InterviewRequest(BaseModel):
    tenantId: str
    taskId: str
    history: list[Turn] = []


SYSTEM_PROMPT = """Sen Instagram stsenariy uchun tajribali, CHUQUR INTERVYU OLUVCHISAN. Maqsad — foydalanuvchini TO'LIQ tushunish: u nima demoqchi, NEGA, KIM uchun, qaysi HAQIQIY tajriba/dalil bilan. Keyin shu asosda AI o'ylab topilmagan, aynan uniki bo'lgan stsenariy yozadi.

QAMRAB OLINISHI KERAK (5 nuqta — suhbatda har birini och, to'liq bo'lmaganini so'ra):
1. Shaxsiy tajriba/fon — bu mavzu bilan qanday bog'liqligi
2. Turtki/sabab — nega muhim, nega aynan shu xabar
3. Aniq misol/dalil — raqam, voqea, natija, case (ENG MUHIM — usiz stsenariy bo'sh bo'ladi)
4. O'ziga xos burchak — boshqalardan farqi, qarama-qarshi fikr yoki yangi yondashuv
5. Auditoriya foydasi — tomoshabin nimani olib ketadi, qanday harakat qiladi

QOIDALAR:
- Har safar FAQAT BITTA savol — qisqa, og'zaki, do'stona.
- Oldingi javobni o'qib, KEYINGI eng muhim YETISHMAYDIGAN nuqtani so'ra (yuqoridagi 5 dan). Javob qiziq detal ochsa — chuqurlashtir.
- BIZ ALLAQACHON BILGAN narsani (payload "bilamiz") qayta SO'RAMA — uni tabiiy tasdiqlab, undan keyingi qadamga o't (tizim bitta miya kabi — eslab turadi).
- Savol shu vazifaning MAVZUSIGA aniq xos bo'lsin, umumiy emas. Takrorlama.
- KAMIDA #3 (aniq misol/dalil — raqam, voqea yoki natija) YIG'ILMAGUNCHA to'xtama. Foydalanuvchi javobi bo'sh, bir so'zli yoki "sen"/"bilmayman" kabi mazmunsiz bo'lsa — TO'XTAMA, aksincha savolni SODDALASHTIRIB, konkret misol so'rab QAYTA ber ("Masalan, bitta aniq holatni ayting: nima qildingiz va natija qanday bo'ldi?"). 3-5 mazmunli nuqta (ayniqsa #3) yig'ilgandagina to'xta.

JSON qaytar (faqat JSON, boshqa matn yo'q):
- Yana savol kerak: {"done": false, "question": "<keyingi savol>", "hint": "<javob misoli yoki bo'sh satr>"}
- Yetarli: {"done": true}

O'zbek tilida."""


@router.post("/script-interview")
async def script_interview(req: InterviewRequest) -> dict:
    history = [{"role": t.role, "content": t.content} for t in req.history]
    asked = sum(1 for m in history if m["role"] == "assistant")

    # How many of the user's answers so far are actually substantive (not filler
    # like "sen"/"ok")? Used to refuse a premature finish on junk input.
    substantive = sum(
        1
        for m in history
        if m["role"] == "user" and is_substantive_answer(m["content"], min_words=4)
    )

    # Terminate once we've asked enough — don't even spend an LLM call.
    if asked >= _MAX_QUESTIONS:
        telegram.send("🏁 Stsenariy intervyusi yakunlandi (savollar tugadi)")
        return {"done": True, "question": None, "hint": None}

    telegram.send(f"🎤 Stsenariy intervyusi · {asked + 1}-savol tayyorlanmoqda")

    sm = get_sessionmaker()
    async with sm() as session:
        task = (
            await session.execute(
                text(
                    'SELECT title, hook, type FROM content_tasks '
                    'WHERE id = :id AND "tenantId" = :t'
                ),
                {"id": req.taskId, "t": req.tenantId},
            )
        ).mappings().first()
        onb = (
            await session.execute(
                text(
                    'SELECT niche, "nicheDetail", "targetAudience", "brandVoice" '
                    'FROM onboarding_profiles WHERE "tenantId" = :t '
                    'ORDER BY "createdAt" DESC LIMIT 1'
                ),
                {"t": req.tenantId},
            )
        ).mappings().first()

    # Single-brain: what we ALREADY know about this user (past interviews +
    # insights in the vault) so the interview builds on it instead of re-asking.
    known: list[str] = []
    try:
        task_title = (dict(task) if task else {}).get("title") or ""
        if task_title:
            notes = await related_notes(tenant_id=req.tenantId, query=task_title, limit=3)
            known = [str(n.get("body") or "")[:220] for n in notes if n.get("body")]
    except Exception as exc:  # noqa: BLE001
        log.warning("script_interview.vault_recall_failed", error=str(exc)[:120])

    payload = {
        "vazifa": dict(task) if task else {},
        "soha": (onb or {}).get("niche"),
        "soha_detail": (onb or {}).get("nicheDetail"),
        "auditoriya": (onb or {}).get("targetAudience"),
        "ovoz_uslubi": (onb or {}).get("brandVoice"),
        "bilamiz": known,
        "suhbat": history,
    }

    try:
        resp = await groq_client.chat_json(
            system=SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=False),
            max_tokens=400,
            temperature=0.6,
            agent_name="script_interview",
        )
        model_done = (isinstance(resp, dict) and resp.get("done")) or not str(
            (resp.get("question") if isinstance(resp, dict) else "") or ""
        ).strip()
        # Refuse to finish on thin grounding: if the model wants to stop (or gave
        # no question) but we still have fewer than 2 substantive answers and room
        # under the cap, force one more CONCRETE example question instead of
        # letting the scriptwriter run on junk it will pad with fabrication.
        if model_done:
            if substantive < 2 and asked < _MAX_QUESTIONS:
                return {
                    "done": False,
                    "question": (
                        "Bitta ANIQ misol bilan ayting: shu mavzuda o'zingiz nima "
                        "qildingiz va natija (raqam, voqea yoki o'zgarish) qanday bo'ldi?"
                    ),
                    "hint": "aniq holat + natija",
                }
            return {"done": True, "question": None, "hint": None}
        q = str(resp.get("question") or "").strip()
        hint = str((resp.get("hint") if isinstance(resp, dict) else "") or "").strip()
        return {"done": False, "question": q, "hint": hint}
    except Exception as exc:  # noqa: BLE001
        log.warning("script_interview.failed", error=str(exc)[:160], asked=asked)
        # Offline / first-turn fallback so the chat still opens with something.
        if asked == 0:
            return {
                "done": False,
                "question": "Bu mavzu bilan qachondan beri va qanday shug'ullanasiz?",
                "hint": "tajribangiz va qanday boshlaganingiz",
            }
        return {"done": True, "question": None, "hint": None}

"""POST /v1/psych-interview + /v1/psych-extract — deep psychological onboarding.

A warm, ADAPTIVE one-question-at-a-time interview (Dizayn A) that opens up the
user's personality, motivation, values, story and voice — a friendly chat, not a
boring test. Grounded in 3 validated frameworks only: Big Five/OCEAN (continuous),
Self-Determination Theory (motivation/retention), and StoryBrand + Sinek "Why".
Archetype + label are GENERATED from OCEAN, never a separate MBTI/DISC test.

Mirrors `questions.py`: stateless per turn (the web holds the conversation and
posts the full history each call); the model returns one question + a `dim` tag
(or `done`). `/psych-extract` distils the finished transcript into a
UserPsychProfile JSON the web persists onto OnboardingProfile.psychProfile and
hands to the agents (vault notes + state persona). HMAC-protected by the global
/v1 middleware. record_llm_call fires automatically inside the LLM clients.
"""
from __future__ import annotations

import json

import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.graphs.archetypes import match_archetype
from app.graphs.bfi10 import BFI_10_ITEMS, score_bfi10
from app.integrations import telegram
from app.integrations.llm import groq_client
from app.integrations.llm.anthropic_client import call_claude
from app.memory.db import get_sessionmaker
from app.memory.knowledge_vault import related_notes

router = APIRouter()
log = structlog.get_logger(__name__)

# Hard cap so the interview always terminates. ~12-13 covers the 10 dimensions
# (some via choice/slider); the model usually finishes a touch earlier.
_MAX_QUESTIONS = 13


class Turn(BaseModel):
    role: str  # "assistant" (AI question) | "user" (answer)
    content: str


class PsychInterviewRequest(BaseModel):
    tenantId: str
    history: list[Turn] = []
    # Dimensions already covered (the web accumulates these from prior `dim`
    # tags). The model also infers from history; this just makes it explicit.
    coveredDims: list[str] = []
    # Onboarding-time context (the profile row may not exist yet). The web passes
    # what it has; we fall back to the DB when these are absent.
    niche: str | None = None
    nicheDetail: str | None = None
    targetAudience: str | None = None


class PsychExtractRequest(BaseModel):
    tenantId: str
    history: list[Turn] = []
    # Optional validated BFI-10 answers (item id → 1-5). When present, OCEAN is
    # scored DETERMINISTICALLY from these and overrides the LLM's estimate.
    bfi10: dict[str, int] | None = None


ORCH_PROMPT = """Sen SMM Coach uchun ILIQ, ADAPTIV PSIXOLOGIK INTERVYU OLUVCHISAN. Maqsad — foydalanuvchining shaxsiyati, motivatsiyasi, qadriyatlari, hikoyasi va ovozini ZERIKARLI TEST emas, samimiy SUHBAT orqali ochish. O'zbek tilida, "sen" ohangida, qisqa va do'stona.

QAMRAB OL (10 dimension — payload "qoplangan"da yopilganlarini ko'rasan, ularni QAYTA so'rama):
D1 identitet/ekspertiza — nima bilan shug'ullanadi, atrofdagilar nimadan maslahat so'raydi
D2 energiya — qaysi ishda vaqt sezilmaydi (ochiqlik/ekstraversiya signali)
D3 origin — bu sohaga qanday kelib qolgan, boshlanish nuqtasi
D4 tone-tanlov — "Brending bazmda odam bo'lsa qanday gapirardi?" [kind=choice, options: jo'shqin do'st / tinch ekspert / hazilkash hikoyachi / to'g'ridan professional]
D5 OCEAN-mikro — 5 ta tez 1-5 baho, bittadan (O: yangi g'oya; C: ishni oxiriga yetkazish; E: odamlar orasida energiya; A: boshqalarga ishonch; N teskari: his-tuyg'u barqarorligi) [kind=slider]
D6 why/SDT — "Pul muammo bo'lmasa ham shu kontentni qilarmiding? Nega?"
D7 qadriyat — sohada eng achchiqlantiradigan, "shunday bo'lmasligi kerak" degan narsa
D8 transformatsiya — yo'ldagi eng katta to'siq va u nimaga o'rgatgani
D9 kamera/vulnerability — kamera oldida qulaymi, shaxsiy hikoya/zaiflikni ochishga tayyormi
D10 auditoriya — eng yaxshi izdoshini bitta aniq odam sifatida, u nimadan xavotirda

QOIDA (MI/OARS):
- Har safar FAQAT BITTA savol. Avval oldingi javobga 1 jumlali REFLECTION + AFFIRMATION (samimiy), keyin keyingi eng muhim YOPILMAGAN dimensiya savoli.
- 2 dan ortiq ketma-ket ochiq savol berma — orasiga tanlov (D4) yoki slayder (D5) qo'y.
- BIZ BILGAN narsani ("bilamiz"/"qoplangan") qayta SO'RAMA — tabiiy tasdiqlab o't (tizim bitta miya kabi eslab turadi).
- Yuza javobga 1 marta "biroz ochib ber", keyin o't.
- Savol shaxsiy, do'stona, umumiy emas. Takrorlama.
- Asosiy dimensiyalar yig'ilsa — to'xta.

JSON qaytar (faqat JSON, boshqa matn yo'q):
- Yana savol: {"done": false, "dim": "D6", "kind": "open"|"choice"|"slider", "reflection": "<1 jumla aks ettirish, bo'sh bo'lishi mumkin>", "question": "<savol>", "options": ["<faqat choice/slider uchun>"], "hint": "<misol yoki bo'sh satr>"}
- Yetarli: {"done": true}

O'zbek tilida."""


# The exact UserPsychProfile shape the extractor must emit (Dizayn A 4b).
_PROFILE_TEMPLATE = """{
  "version": 1,
  "ocean": { "O": 0-100, "C": 0-100, "E": 0-100, "A": 0-100, "N": 0-100, "confidence": "low|medium" },
  "motivation": { "primary": "autonomy|competence|relatedness|external", "secondary": "...", "retentionRisk": "low|medium|high", "whyStatement": "..." },
  "values": { "core": ["..."], "philosophicalProblem": "...", "redLines": ["..."] },
  "originStory": { "catalyst": "...", "challenge": "...", "transformation": "...", "impact": "..." },
  "voice": { "archetypePrimary": "...", "archetypeSecondary": "...", "archetypeConfidence": "suggested", "tone": { "formalCasual": 1-5, "funnySerious": 1-5, "respectfulIrreverent": 1-5, "enthusiasticMatter": 1-5 }, "antiVoice": ["..."], "label": "<ijobiy o'zbekcha yorliq>" },
  "audience": { "avatar": "...", "internalPain": "...", "desire": "..." },
  "comfort": { "onCamera": "low|medium|high", "vulnerability": "low|medium|high", "preferredFormat": "..." },
  "contentPillars": ["..."]
}"""

EXTRACT_PROMPT = (
    """Sen psixologik profil tahlilchisisan. Quyidagi intervyu transkriptidan UserPsychProfile JSON chiqar.

QAT'IY QOIDALAR:
- OCEAN: 0-100 UZLUKSIZ (kategoriya emas). Atigi bir nechta mikro-javob bor → "confidence":"medium", HECH QACHON "high". Dalil yetishmasa 50 (neytral) qo'y, o'ylab topma.
- Arxetip: OCEAN'dan KELIB CHIQIB tanla (yuqori O+past A→Creator; yuqori O+yuqori C→Sage; yuqori E+yuqori A→Everyman/Hero; yuqori C+past O→Ruler...). "archetypeConfidence":"suggested" — "diagnosed" YO'Q.
- tone (1-5): D4 tanlovi + OCEAN'dan hisobla. funnySerious←(O,N), formalCasual←(C teskari), enthusiasticMatter←(E), respectfulIrreverent←(A teskari).
- motivation.primary: D6 javobini autonomy/competence/relatedness/external ga maple. FAQAT external bo'lsa retentionRisk:"high".
- label: userga ko'rsatish uchun ijobiy, ko'taruvchi o'zbekcha yorliq (masalan "Iliq Donishmand-Murabbiy"). Kamsituvchi EMAS.
- Transkriptda BO'LMAGAN faktni TO'QIMA. Yetishmasa null yoki bo'sh qoldir.

Aynan shu JSON shaklda qaytar (faqat JSON, markdown blok yo'q):
"""
    + _PROFILE_TEMPLATE
)


async def _load_onboarding_ctx(tenant_id: str) -> dict:
    """Best-effort onboarding context from the DB (may be empty at onboarding)."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            row = (
                await session.execute(
                    text(
                        'SELECT niche, "nicheDetail", "targetAudience", "brandVoice" '
                        'FROM onboarding_profiles WHERE "tenantId" = :t '
                        'ORDER BY "createdAt" DESC LIMIT 1'
                    ),
                    {"t": tenant_id},
                )
            ).mappings().first()
            return dict(row) if row else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("psych_interview.ctx_load_failed", error=str(exc)[:120])
        return {}


@router.post("/psych-interview")
async def psych_interview(req: PsychInterviewRequest) -> dict:
    history = [{"role": t.role, "content": t.content} for t in req.history]
    asked = sum(1 for m in history if m["role"] == "assistant")

    # Terminate once we've asked enough — don't even spend an LLM call.
    if asked >= _MAX_QUESTIONS:
        telegram.send("🏁 Psixologik intervyu yakunlandi (savollar tugadi)")
        return {"done": True, "dim": None, "kind": None, "reflection": None,
                "question": None, "options": [], "hint": None}

    telegram.send(f"🧠 Psixologik intervyu · {asked + 1}-savol tayyorlanmoqda")

    ctx = await _load_onboarding_ctx(req.tenantId)
    niche = req.niche or ctx.get("niche")

    # Single-brain: pull anything we already know (prior insights) so the
    # interview builds on it instead of re-asking. Best-effort.
    known: list[str] = []
    try:
        if niche:
            notes = await related_notes(tenant_id=req.tenantId, query=str(niche), limit=3)
            known = [str(n.get("body") or "")[:220] for n in notes if n.get("body")]
    except Exception as exc:  # noqa: BLE001
        log.warning("psych_interview.vault_recall_failed", error=str(exc)[:120])

    payload = {
        "soha": niche,
        "soha_detail": req.nicheDetail or ctx.get("nicheDetail"),
        "auditoriya": req.targetAudience or ctx.get("targetAudience"),
        "ovoz_uslubi": ctx.get("brandVoice"),
        "qoplangan": req.coveredDims,
        "bilamiz": known,
        "suhbat": history,
    }

    try:
        resp = await groq_client.chat_json(
            system=ORCH_PROMPT,
            user=json.dumps(payload, ensure_ascii=False),
            max_tokens=500,
            temperature=0.6,
            agent_name="psych_interview",
        )
        if isinstance(resp, dict) and resp.get("done"):
            return {"done": True, "dim": None, "kind": None, "reflection": None,
                    "question": None, "options": [], "hint": None}
        q = str((resp.get("question") if isinstance(resp, dict) else "") or "").strip()
        if not q:
            return {"done": True, "dim": None, "kind": None, "reflection": None,
                    "question": None, "options": [], "hint": None}
        kind = str(resp.get("kind") or "open").strip() or "open"
        options = [str(o) for o in (resp.get("options") or []) if str(o).strip()]
        # A 'choice' turn with no usable options would render zero buttons on the
        # web and stall the interview (the answer promise never resolves) — so
        # degrade it to a free-text question. LLM output isn't guaranteed.
        if kind == "choice" and not options:
            kind = "open"
        return {
            "done": False,
            "dim": str(resp.get("dim") or "").strip() or None,
            "kind": kind,
            "reflection": str(resp.get("reflection") or "").strip(),
            "question": q,
            "options": options,
            "hint": str(resp.get("hint") or "").strip(),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("psych_interview.failed", error=str(exc)[:160], asked=asked)
        # Offline / first-turn fallback so the chat still opens warmly.
        if asked == 0:
            return {
                "done": False,
                "dim": "D1",
                "kind": "open",
                "reflection": "",
                "question": "O'zingni qisqacha tanishtir — nima bilan shug'ullanasan va "
                "atrofingdagilar sendan ko'pincha nima haqida maslahat so'rashadi?",
                "options": [],
                "hint": "kasbing va odamlar sendan so'raydigan mavzu",
            }
        return {"done": True, "dim": None, "kind": None, "reflection": None,
                "question": None, "options": [], "hint": None}


def _clamp_ocean(v: object) -> int:
    try:
        return max(0, min(100, int(round(float(v)))))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 50  # neutral — the prompt's own "no evidence → 50" rule, enforced


def _validate_profile(profile: object) -> dict | None:
    """Guard the LLM's psych profile before it persists: clamp OCEAN to 0-100, CAP confidence at
    'medium' (a few micro-answers can never justify 'high'), force the archetype to 'suggested'
    (never a clinical 'diagnosed'), and REJECT a hollow profile (just the empty template) so a failed
    extract doesn't silently save a profileless shell that downstream then treats as real."""
    if not isinstance(profile, dict) or not profile:
        return None
    ocean = profile.get("ocean")
    if isinstance(ocean, dict):
        for k in ("O", "C", "E", "A", "N"):
            if k in ocean:
                ocean[k] = _clamp_ocean(ocean.get(k))
        conf = str(ocean.get("confidence") or "").lower()
        ocean["confidence"] = conf if conf in ("low", "medium") else "medium"
    voice = profile.get("voice")
    if isinstance(voice, dict):
        voice["archetypeConfidence"] = "suggested"

    def _filled(x: object) -> bool:
        if isinstance(x, (list, dict, str)):
            return len(x) > 0
        return x is not None

    values = profile.get("values") if isinstance(profile.get("values"), dict) else {}
    origin = profile.get("originStory") if isinstance(profile.get("originStory"), dict) else {}
    substantive = any(
        [
            isinstance(voice, dict) and bool(str(voice.get("label") or "").strip()),
            _filled(values.get("core")),  # type: ignore[union-attr]
            _filled(profile.get("contentPillars")),
            _filled(origin.get("catalyst")),  # type: ignore[union-attr]
        ]
    )
    return profile if substantive else None


@router.post("/psych-extract")
async def psych_extract(req: PsychExtractRequest) -> dict:
    """Distil the finished transcript into a UserPsychProfile JSON.

    Returns {"profile": <dict> | None}. The web proxy persists it onto
    OnboardingProfile.psychProfile + PsychInterview.profile.
    """
    if not req.history:
        return {"profile": None}

    telegram.send("🧩 Psixologik profil intervyudan chiqarilmoqda (OCEAN + arxetip)")

    transcript = "\n".join(
        f"{'AI' if t.role == 'assistant' else 'User'}: {t.content}" for t in req.history
    )

    try:
        resp, _usage = await call_claude(
            model=get_settings().model_initial_analysis,
            system=EXTRACT_PROMPT,
            messages=[{"role": "user", "content": f"TRANSKRIPT:\n{transcript}"}],
            max_tokens=1500,
            response_format="json",
            agent_name="psych_extract",
        )
        profile = _validate_profile(json.loads(resp.get("text") or "{}"))
        # Validated OCEAN: when the user completed the BFI-10, override the LLM's
        # guessed scores with the deterministic instrument result (the LLM stays
        # responsible only for narrative/archetype/voice — "LLM faqat narrativ").
        if profile is not None and req.bfi10:
            scored = score_bfi10(req.bfi10)
            if scored:
                ocean = profile.get("ocean")
                profile["ocean"] = {**(ocean if isinstance(ocean, dict) else {}), **scored}
        # Ground the archetype on the FINAL OCEAN with a deterministic 12-archetype
        # taxonomy (replaces the LLM's ad-hoc pick → consistent brand voice). The
        # LLM still owns the narrative label/tone; we set archetype + antiVoice.
        if profile is not None:
            voice = profile.get("voice")
            if isinstance(voice, dict):
                m = match_archetype(profile.get("ocean"))
                voice["archetypePrimary"] = m["primary"]
                voice["archetypeSecondary"] = m["secondary"]
                voice["archetypeConfidence"] = "suggested"
                if not voice.get("antiVoice"):
                    voice["antiVoice"] = m["antiVoice"]
        label = ((profile or {}).get("voice") or {}).get("label") if profile else None
        telegram.send(
            f"✅ Psixologik profil tayyor · {label}" if label
            else "⚠️ Psixologik profil to'liq chiqmadi"
        )
        return {"profile": profile}
    except Exception as exc:  # noqa: BLE001
        log.warning("psych_extract.failed", error=str(exc)[:160])
        telegram.send("❌ Psixologik profil chiqarishda xato")
        return {"profile": None}


@router.get("/psych-bfi10-items")
async def psych_bfi10_items() -> dict:
    """The validated BFI-10 item bank for the onboarding to render as 10 sliders
    (1-5). Static — the scoring lives server-side in score_bfi10."""
    return {
        "scale": {"min": 1, "max": 5, "minLabel": "Mutlaqo qo'shilmayman", "maxLabel": "Mutlaqo qo'shilaman"},
        "items": [{"id": it["id"], "text": it["text"]} for it in BFI_10_ITEMS],
    }

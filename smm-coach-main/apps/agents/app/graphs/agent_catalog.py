"""Single source of truth describing every agent: which AI it uses, when it
runs, what it reads/writes, and (for the ones driven by a system prompt) the
prompt itself.

The web admin panel reads this via `GET /v1/admin/agent-catalog` to show — and
for the prompt-bearing agents, edit — exactly what each agent does. Editing
writes a row to `prompt_overrides`; `prompt_store.resolve_prompt()` picks it up.

`model` is resolved live from config.py so this never drifts from the real
routing. `default_prompt` is loaded lazily from the node modules.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.graphs.prompt_store import resolve_prompt

# Static metadata. `prompt_ref` points at (module_name, constant_name) for the
# editable agents; `model_attr` reads the live model id from settings, else a
# literal `model` is used (Groq/OpenAI ids are hardcoded at their call sites).
_META: list[dict[str, Any]] = [
    {
        "key": "initial_analysis",
        "agent": "initial_analysis",
        "label": "Boshlang'ich tahlil",
        "description": "Onboarding'da profilni o'qib, kuchli/zaif tomonlar, "
        "kontent ustunlari va north-star (soha, auditoriya, maqsad)ni aniqlaydi.",
        "provider": "anthropic",
        "model_attr": "model_initial_analysis",
        "when": "Onboarding — foydalanuvchi profilni ulagach, bir marta.",
        "inputs": "IG profil snapshot, onboarding javoblari",
        "outputs": "Strengths/weaknesses, content pillars, north-star",
        "prompt_ref": ("initial_analysis", "SYSTEM_PROMPT"),
    },
    {
        "key": "roadmap_generator",
        "agent": "roadmap_generator",
        "label": "Yo'l xaritasi strategi",
        "description": "Maqsadga yetish uchun 14-30 ta vazifadan iborat "
        "yo'l xaritasi tuzadi — har vazifaning NIMA va NIMA UCHUN qismi.",
        "provider": "anthropic",
        "model_attr": "model_roadmap_generator",
        "when": "Onboarding'dan keyin, boshlang'ich tahlil tugagach.",
        "inputs": "North-star, profil tahlili, bozor signallari",
        "outputs": "Vazifalar daraxti (draft)",
        "prompt_ref": ("roadmap_generator", "SYSTEM_PROMPT"),
    },
    {
        "key": "groq_scorer",
        "agent": "groq_scorer",
        "label": "Tezkor baholovchi (Cerebras)",
        "description": "Roadmap'dagi har bir vazifani 4 o'lchovda baholaydi: "
        "viral potensial, auditoriyaga moslik, qiyinlik, aniqlik.",
        "provider": "cerebras",
        "model": "llama-3.3-70b",
        "when": "Roadmap draft tayyor bo'lgach, persist'dan oldin.",
        "inputs": "Roadmap vazifalari, north-star",
        "outputs": "Har vazifaga ball (JSON)",
        "prompt_ref": ("groq_scorer", "SYSTEM_PROMPT"),
    },
    {
        "key": "openai_critic",
        "agent": "openai_critic",
        "label": "Tanqidchi (OpenAI)",
        "description": "Roadmap'ni mustaqil, qattiq qo'l bilan tanqid qiladi — "
        "zaif yoki sohaga mos kelmaydigan vazifalarni belgilaydi.",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "when": "Tezkor baholashdan keyin, persist'dan oldin.",
        "inputs": "Roadmap vazifalari, north-star",
        "outputs": "Tanqid + tuzatish takliflari (JSON)",
        "prompt_ref": ("openai_critic", "SYSTEM_PROMPT"),
    },
    {
        "key": "scriptwriter_rich",
        "agent": "scriptwriter",
        "label": "Stsenariy — to'liq (RICH)",
        "description": "Birinchi/asosiy video vazifasi uchun batafsil stsenariy: "
        "hook, kadrlar ro'yxati, hashtag, audio taklif.",
        "provider": "anthropic",
        "model_attr": "model_scriptwriter_primary",
        "when": "Roadmap'ning birinchi kontent vazifasi ochilganda.",
        "inputs": "Vazifa draft, north-star, o'xshash muvaffaqiyatli postlar",
        "outputs": "To'liq stsenariy (hook, shotList, hashtags)",
        "prompt_ref": ("scriptwriter", "SYSTEM_PROMPT_RICH"),
    },
    {
        "key": "scriptwriter_action",
        "agent": "scriptwriter",
        "label": "Stsenariy — amaliyot (ACTION)",
        "description": "Video EMAS, balki profil sozlash kabi amaliyot "
        "vazifasi uchun qadam-baqadam ko'rsatma.",
        "provider": "anthropic",
        "model_attr": "model_scriptwriter_primary",
        "when": "Ochilgan vazifa turi 'action' bo'lganda.",
        "inputs": "Vazifa draft, north-star",
        "outputs": "Bajariladigan qadamlar ko'rsatmasi",
        "prompt_ref": ("scriptwriter", "SYSTEM_PROMPT_ACTION"),
    },
    # ── Info-only agents (no single editable system prompt) ───────────────
    {
        "key": "market_analyst",
        "agent": "market_analyst",
        "label": "Bozor tahlilchisi",
        "description": "Region trendlari va viral hook'larni shared_knowledge'dan "
        "o'qib, sohaga mos signallarni chiqaradi (LLM prompt'siz, qoidaviy).",
        "provider": "gemini",
        "model_attr": "model_market_analyst",
        "when": "Doimiy loop — har bir roadmap/script bosqichida.",
        "inputs": "shared_knowledge (cross-tenant), north-star",
        "outputs": "Trending signallar, AgentMessage",
        "prompt_ref": None,
    },
    {
        "key": "industry_news",
        "agent": "industry_news",
        "label": "Soha yangiliklari",
        "description": "Foydalanuvchi sohasi bo'yicha so'nggi yangiliklarni "
        "shared_knowledge'dan o'qiydi.",
        "provider": "gemini",
        "model_attr": "model_industry_news",
        "when": "Kuniga 2 marta (per-user), va script bosqichida.",
        "inputs": "shared_knowledge (soha yangiliklari), north-star",
        "outputs": "Yangilik signallari",
        "prompt_ref": None,
    },
    {
        "key": "drift_detector",
        "agent": "drift_detector",
        "label": "Yo'ldan chetlash detektori",
        "description": "Har taklif qilingan vazifani north-star embedding bilan "
        "cosine o'xshashlik orqali tekshiradi; chegaradan pastlarini bloklaydi.",
        "provider": "voyage",
        "model_attr": "model_embeddings",
        "when": "Har vazifa taklif qilinganda (guard).",
        "inputs": "Vazifa matni, north-star embedding",
        "outputs": "Drift score, blok qarori",
        "prompt_ref": None,
    },
    {
        "key": "output_validator",
        "agent": "output_validator",
        "label": "Chiqish validatori",
        "description": "Stsenariy chiqishidagi har bir raqamli da'voni dalil "
        "(predict_evidence) bilan tekshiradi; asossizlarini rad etadi.",
        "provider": "anthropic",
        "model_attr": "model_output_validator",
        "when": "Scriptwriter chiqishidan keyin (guard).",
        "inputs": "Stsenariy, dalillar",
        "outputs": "Validatsiya qarori",
        "prompt_ref": None,
    },
    {
        "key": "account_tracker",
        "agent": "account_tracker",
        "label": "Akkaunt kuzatuvchisi",
        "description": "IG metrikalarini o'qib klassifikatsiya qiladi, follower "
        "deltalarini kuzatadi (Cerebras/OpenRouter, tez).",
        "provider": "cerebras",
        "model_attr": "model_account_tracker",
        "when": "Har 6 soatda (post chiqqanida tezroq).",
        "inputs": "IG post/profil metrikalari",
        "outputs": "Sentiment, delta, AgentMessage",
        "prompt_ref": None,
    },
    # ── Sprint 2 — yangi agentlar ────────────────────────────────────────
    {
        "key": "profile_auditor",
        "agent": "profile_auditor",
        "label": "Profil auditori",
        "description": "Ulangan IG Business profilni professional standartlarga "
        "solishtirib 5-8 ta aniq yaxshilanish (bio, link, highlights) chiqaradi.",
        "provider": "anthropic",
        "model_attr": "model_initial_analysis",
        "when": "Onboarding'da IG ulanganda + haftada 1 marta.",
        "inputs": "IG profil (Graph API), niche, goal",
        "outputs": "Audit checklist (instagram_accounts.profileAudit)",
        "prompt_ref": ("profile_auditor", "SYSTEM_PROMPT"),
    },
    {
        "key": "hashtag_curator",
        "agent": "hashtag_curator",
        "label": "Hashtag kuratori",
        "description": "Tayyor senariy uchun 10-12 ta hashtag tanlaydi — "
        "3-4 soha + 3-4 umumiy + 3-4 lokal (#uzbekistan, #toshkent).",
        "provider": "cerebras",
        "model": "llama-3.3-70b",
        "when": "content_review — scriptwriter'dan keyin.",
        "inputs": "Senariy, niche, region",
        "outputs": "Hashtag ro'yxati (content_tasks.hashtags)",
        "prompt_ref": ("hashtag_curator", "SYSTEM_PROMPT"),
    },
    {
        "key": "hook_optimizer",
        "agent": "hook_optimizer",
        "label": "Hook optimizatori",
        "description": "Scriptwriter A-variant hook'iga tubdan boshqacha B-variant "
        "yozadi + qaysi biri retention'ni yaxshiroq ushlashini baholaydi.",
        "provider": "anthropic",
        "model_attr": "model_scriptwriter_revise",
        "when": "content_review — hashtag'dan keyin.",
        "inputs": "Hook A, past hooks, market signals",
        "outputs": "Hook B + A/B score (scriptVariantB)",
        "prompt_ref": ("hook_optimizer", "SYSTEM_PROMPT"),
    },
    {
        "key": "caption_translator",
        "agent": "caption_translator",
        "label": "Caption yozuvchi",
        "description": "Senariydan IG'ga tayyor caption yozadi (o'zbekcha, "
        "200-2200 belgi, hook + qiymat + CTA + hashtag).",
        "provider": "cerebras",
        "model": "llama-3.3-70b",
        "when": "content_review — hook'dan keyin.",
        "inputs": "Senariy, hashtaglar",
        "outputs": "IG caption (content_tasks.igCaption)",
        "prompt_ref": ("caption_translator", "SYSTEM_PROMPT"),
    },
    {
        "key": "comment_sentinel",
        "agent": "comment_sentinel",
        "label": "Izoh kuzatuvchisi",
        "description": "Chop etilgan postning izohlarini o'qib sentiment "
        "(ijobiy/salbiy/neytral) + asosiy mavzularni umumlashtiradi.",
        "provider": "cerebras",
        "model": "llama-3.3-70b",
        "when": "Post chiqqach ~24 soat (comment_sentinel_pulse).",
        "inputs": "IG post izohlari",
        "outputs": "Sentiment xulosasi (instagram_posts.commentSentiment)",
        "prompt_ref": None,
    },
]


def _load_default_prompt(ref: tuple[str, str] | None) -> str | None:
    if ref is None:
        return None
    module_name, const_name = ref
    try:
        mod = __import__(f"app.graphs.nodes.{module_name}", fromlist=[const_name])
        val = getattr(mod, const_name, None)
        return str(val) if val is not None else None
    except Exception:  # noqa: BLE001
        return None


def _model_for(meta: dict[str, Any]) -> str:
    if "model" in meta:
        return str(meta["model"])
    attr = meta.get("model_attr")
    if attr:
        return str(getattr(get_settings(), attr, "?"))
    return "?"


async def get_agent_catalog() -> list[dict[str, Any]]:
    """Full catalog with the EFFECTIVE prompt (override or default) for each
    prompt-bearing agent, plus its code default so the UI can offer a reset.
    """
    out: list[dict[str, Any]] = []
    for meta in _META:
        editable = meta.get("prompt_ref") is not None
        default_prompt = _load_default_prompt(meta.get("prompt_ref"))
        effective = default_prompt
        is_overridden = False
        if editable and default_prompt is not None:
            effective = await resolve_prompt(meta["key"], default_prompt)
            is_overridden = effective != default_prompt
        out.append(
            {
                "key": meta["key"],
                "agent": meta["agent"],
                "label": meta["label"],
                "description": meta["description"],
                "provider": meta["provider"],
                "model": _model_for(meta),
                "when": meta["when"],
                "inputs": meta["inputs"],
                "outputs": meta["outputs"],
                "editable": editable,
                "defaultPrompt": default_prompt,
                "effectivePrompt": effective,
                "isOverridden": is_overridden,
            }
        )
    return out

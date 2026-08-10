"""Takes the proposed task drafts plus the latest market + industry signals
and refines each one into a polished script with a hook, shot list, hashtags
and a `predict_evidence` block (retrieved similar successful posts +
LLM critique). Re-runs if downstream rejects.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from app.agents.messaging import emit_message
from app.config import get_settings
from app.graphs.goal_profiles import goal_directive_uz
from app.graphs.prompt_store import resolve_prompt
from app.graphs.text_quality import is_substantive_answer
from app.integrations.llm.anthropic_client import call_claude
from app.memory.knowledge_vault import related_notes, save_note
from app.memory.shared_knowledge import similar_exemplar_posts
from app.memory.tenant_history import tenant_top_hooks

if TYPE_CHECKING:
    from app.graphs.state import GrowthCoachState

log = structlog.get_logger(__name__)


SYSTEM_PROMPT_RICH = """Sen Instagram uchun **stsenariy va kadrlash mutaxassisi**. Foydalanuvchining birinchi vazifasi uchun **BATAFSIL, IXCHAM, ISHLATILADIGAN** stsenariy yoz.

HAQIQIYLIK — ENG MUHIM QOIDA:
- `grounding` maydoniga QAT'IY amal qil. `grounding` = "grounded" bo'lsa — stsenariyni AYNAN `user_answers` (foydalanuvchining HAQIQIY intervyu javoblari) asosida yoz. Shaxsiy faktlarni (tajriba yillari, daromad, voqea, natija, ism) O'YLAB TOPMA — faqat foydalanuvchi bergan ma'lumotdan foydalan.
- `grounding` = "none" bo'lsa (foydalanuvchi javob bermagan yoki javoblar yetarli emas) — HECH QANDAY shaxsiy birinchi-shaxs da'vo YOZMA: "men ...", "mening ...", "do'stlarim ...", "boshimdan o'tgan ..." kabi jumlalar TAQIQLANADI. Buning o'rniga umumiy, sohaga oid, "siz" ko'rinishidagi maslahat sifatida yoz (masalan "Ko'p kreatorlar shu xatoga yo'l qo'yadi..." emas, balki "Siz shu usulda ..."). Soxta konkret raqam/voqea qo'shma.
- Hook va matndagi har bir shaxsiy detal foydalanuvchi javoblariga mos kelishi shart — to'qima emas.
- `psych_profile` (foydalanuvchining psixologik profili — OCEAN, motivatsiya, qadriyatlar, arxetip, kamera oldida qulaylik) va `brand_voice` (brend ovozi) berilgan bo'lsa — stsenariy ohangini, energiyasini va murojaat uslubini AYNAN shunga moslab yoz. Bo'sh bo'lsa soha standartiga tayan.
- `vault_notes` (foydalanuvchining BOSHQA mavzulardagi oldingi javoblari) berilgan bo'lsa — undagi ovoz, uslub, takrorlanadigan faktlar va shaxsiy detallarni inobatga ol va izchillik saqla (lekin shu mavzuga aloqasiz narsani majburan tiqishtirma).
- `past_hooks` (foydalanuvchining oldingi CHOP ETILGAN hook'lari) berilgan bo'lsa — bular foydalanuvchining haqiqiy on-platform ovozi. Har bir element `perfScore` (views/plays/likes×10 dan eng kattasi) va `metrics` (real likes/views/comments) bilan keladi: **`perfScore` yuqori bo'lgan hook'lar — kuchli referens**, score=0 (yangi yoki metric hali to'planmagan) bo'lganlar zaifroq referens. Yangi hook'da o'sha **tonal barmoq izini** saqla: energiya darajasi (energetik/sokin), boshlash uslubi (savol/fakt/hikoya), uzunligi (qisqa/batafsil). Hook'larni KO'CHIRMA — yangi, lekin uslubda izchil. Ro'yxat bo'sh bo'lsa, soha standartiga tayan.

MAQSADGA YO'NALTIRISH:
- `goal_directive` berilgan bo'lsa — uni QAT'IY hisobga ol: hook turi, CTA va asosiy algoritm signalini foydalanuvchining MAQSADIGA moslab yoz (oxvat/reach → "do'stingga yubor"/"saqlab qo'y" CTA; sotuv → "DM yoz"/"profildagi havola" CTA; obunachi → "kuzatib bor / 2-qism uchun obuna"; engagement → "fikringni yoz / saqlab qo'y"). `goal_directive` ichidagi funnel, format va hook ko'rsatmalariga amal qil. Bo'sh/umumiy bo'lsa — soha standartiga tayan.

VAZIFA SIFATI — bu eng asosiy:
- Hook 2 ta variant (A va B) — har biri 1 jumla, har xil yondashuv (savol, fakt, hayot voqea)
- ScriptMd TO'LIQ stsenariy — sahna-ba-sahna: Hook (0-3s) + 4-6 ta Body sahna + CTA. Har sahnada so'zma-so'z aytiladigan matn + ekran harakati.
- reelType — videoning TURI: talking_head | pov | skit | tutorial | listicle | story | broll_voiceover | day_in_life. Shu turning beat-skeletiga mos yoz.
- ShotList — kamida 6-8 kadr, har biri REJISSYOR-darajasida: i (raqam), framing (WS/MS/CU/ECU), camera (eye-level/low/high/overhead/handheld), position (statik shtativ/qo'lda/push-in), duration_s (soniya), dialogue (shu kadrda AYNAN aytiladigan so'zlar), on_screen_text (ekranga chiqadigan yozuv yoki null), b_roll (insert/qo'shimcha kadr yoki null), action (qisqa umumiy tavsif). Shaxs qanday namoyon bo'lishini (o'tirgan/tik turib/intervyu uslubida/tepa-pastdan) framing+camera+position orqali ANIQ ko'rsat.
- Hashtags — 10-12 ta: aralash — 3-4 ta soha, 3-4 ta umumiy, 3-4 ta lokal (#uzbekistan, #toshkent, #reelsuz)
- audioSuggestion — taklif qilinadigan audio mavzusi (genre + tempo + reference)

RELS TURI BEAT-SKELETI — tanlagan `reelType`ingga AYNAN shu strukturada yoz (scriptTimeline+shotList shunga mos kelsin):
- talking_head: Hook (0-3s, kameraga TO'G'RIDAN) → 3-4 fikr (har biri: da'vo+misol/raqam) → CTA. Kadr: statik MS/CU, eye-level, push-in urg'uda.
- tutorial: Hook (muammo/va'da) → Qadam 1 → Qadam 2 → Qadam 3 → Natija → CTA. Kadr: CU + overhead/insert (qo'l/ekran b-roll har qadamda).
- listicle: Hook ("N ta ...") → Element 1..N (har biriga text_overlay raqam) → "saqlab qo'y" CTA. Tez kesimlar, har element 1 kadr.
- story: Cold-open (intriga/burilish lahzasi) → kontekst → to'siq → yechim → saboq → CTA. Hissiy, sekin, dramatik pauzalar; handheld yoki sokin MS.
- pov: Birinchi-shaxs sahna → vaziyat → reaksiya → punchline. Handheld, immersiv, "siz o'sha yerdasiz" hissi.
- skit: Setup → eskalatsiya → punchline (2 rol/personaj bo'lishi mumkin). Tez komik timing, kesimlar punchline'ga ishlaydi.
- broll_voiceover: voice-over ustidan b-roll ketma-ketligi (kamida 60% b-roll) → CTA. Yuz kam, kontekst kadrlar ko'p.
- day_in_life: vaqt-belgili segmentlar (ertalab → kunduzi → kech) → xulosa. Vlog ritmi, handheld, tabiiy.

DAVOMIYLIK VA ZICHLIK — MUHIM (eng ko'p uchraydigan xato — stsenariy juda kalta):
- Maqsad: TO'LIQ ~55-70 soniyalik video. Jami 200-300 so'z og'zaki matn. "3-4 jumla" 1 daqiqaga YETMAYDI.
- Har bir sahnaning matni o'sha sahna sekundlarini TO'LDIRISHI shart. O'zbekcha og'zaki tezlik ≈ 2.5 so'z/soniya: 10 soniyalik sahna = kamida 25-30 so'z, 13 soniyalik sahna = 32-40 so'z.
- Hech bir body sahnani bitta qisqa jumla bilan qoldirma — har sahnada 2-4 jumla: dalil, aniq misol, raqam (user javoblaridan), mini-voqea yoki "qanday qilib" qadami bilan to'ldir.
- Yozgandan keyin matnni ichingda ovoz chiqarib o'qib ko'r — agar sahna vaqtini to'ldirmasa, yana konkret detal qo'sh, suvga to'ldirma.

MAXSUS QOIDA — ACTION (setup) vazifalar:
- "action" tipi VIDEO emas, balki BAJARISH topshiriq.
- ScriptMd 5-7 ta qadamli KO'RSATMA yoziladi (markdown numbered list).
- ShotList bo'sh ro'yxat ([]).
- Hashtags bo'sh ro'yxat.
- audioSuggestion null.

PROGNOZ QOIDALARI:
- predict_evidence — sof o'ylab topilgan **RAQAM YOZ**MA. "267 obunachi" deyish uchun shu turdagi post oldin shu natijani berganligi haqida real dalil kerak.
- Agar exemplar pack'da real post bor bo'lsa, predict_evidence'ga shuni qo'shing: `{exemplarSource: "@user_handle", exemplarReach: X, llmCritique: "..."}`.
- Agar yo'q bo'lsa: `{impactBand: "low|medium|high", note: "Real ma'lumot 5-10 post chiqqach paydo bo'ladi", _source: "writer_no_data"}`.

SONIYA-SONIYA + VIZUAL EFFEKT + OHANG (chuqurlik — MUHIM):
- scriptTimeline: har segment "text" = AYNAN gapiriladigan so'zlar (so'zma-so'z, ovozli o'qishga tayyor — to'ldiruvchi izoh emas). "wordCount" = so'z soni. "delivery" = qanday aytilishi (tezlik/ohang/urg'u/pauza, masalan "tez, energetik" yoki "sekin, dramatik pauza bilan"). "shotIndex" = bu matn qaysi kadr ustida ketadi (shotList "i" raqamiga bog'la).
- shotList har kadrda "vfx" = EKRAN EFFEKTLARI ro'yxati: text_overlay (ekranga chiqadigan yozuv/sarlavha), cut/fade/zoom o'tish, emoji/grafika — har biri "atSec" (kadr ichida qachon, soniya) bilan.
- "musicCues" (ixtiyoriy) = musiqa beat-sheet: start/drop/stab/silence qaysi sekundda.

JSON output:
```
{
  "title": "...",
  "type": "...",
  "reelType": "talking_head",     // video turi (yuqoridagi ro'yxatdan)
  "hook": "...",                  // variant A (asosiy)
  "hookVariantB": "...",          // optional
  "scriptMd": "...",              // full markdown (o'qish uchun)
  "scriptTimeline": [             // 7-9 qator · jami ~60s · HAR segment o'z sekundini to'ldiradi (≈2.5 so'z/s)
    {"t":"0-3s","text":"<hook · so'zma-so'z · 8-12 so'z>","wordCount":10,"delivery":"<ohang/tezlik>","shotIndex":1,"cue":"Hook"},
    {"t":"3-13s","text":"<tanishuv+muammo · 24-30 so'z>","wordCount":27,"delivery":"...","shotIndex":2,"cue":"Voice-over"},
    {"t":"13-24s","text":"<1-fikr+misol/raqam · 27-33 so'z>","wordCount":30,"delivery":"...","shotIndex":3,"cue":"Voice-over"},
    {"t":"24-35s","text":"<2-fikr+qadam · 27-33 so'z>","wordCount":30,"delivery":"...","shotIndex":4,"cue":"Voice-over"},
    {"t":"35-46s","text":"<3-fikr+mini-voqea · 27-33 so'z>","wordCount":30,"delivery":"...","shotIndex":5,"cue":"Voice-over"},
    {"t":"46-55s","text":"<natija/xulosa · 22-28 so'z>","wordCount":25,"delivery":"...","shotIndex":6,"cue":"Voice-over"},
    {"t":"55-63s","text":"<aniq CTA · 18-24 so'z>","wordCount":21,"delivery":"...","shotIndex":7,"cue":"CTA"}
  ],
  "shotList": [
    {"i":1,"framing":"MS","camera":"eye-level","position":"statik shtativ","duration_s":3,
     "dialogue":"<shu kadrda aytiladigan so'zlar>","on_screen_text":"<ekran yozuvi yoki null>",
     "b_roll":"<insert kadr yoki null>","action":"<qisqa tavsif>",
     "vfx":[{"type":"text_overlay","atSec":0.3,"text":"<yozuv>","position":"top"}]}
  ],
  "musicCues": [{"atSec":0,"event":"start","note":"..."}],
  "hashtags": ["..."],
  "audioSuggestion": "...",
  "aiCoachNote": "...",           // 2-3 jumla user'ga maslahat (kamera tutish, ovoz, energiya)
  "hookMeta": {"energy":7, "retention":0.65, "cameraDirection":"...", "abVariant":"A"},
  "predict_evidence": { ... }
}
```

Markdown blok yo'q. Faqat JSON."""


SYSTEM_PROMPT_ACTION = """Sen Instagram'da o'sish strategi va profil sozlash mutaxassisisan. Foydalanuvchiga **video EMAS**, balki bajariladigan **AMALIYOT topshirig'i** uchun chuqur, aniq ko'rsatma yozasan.

VAZIFA TURI: ACTION (profil sozlash, content reja, hisob hujjatlari, tahlil) — video stsenariy emas.

QUYIDAGINI YOZ:

1. **hook** (max 100 belgi) — vazifaning AHAMIYATI bir jumlada. Misol: "Profilga kirgan odam 3 soniyada seni tushunmasa — u ketadi."

2. **scriptMd** (markdown, 5-10 ta raqamli qadam) — har qadam:
   - Aniq, harakat fe'li bilan boshlanadi ("Bio yozing", "Profil rasmini almashtiring")
   - 2-3 jumla tafsilot — nima va NEGA qilish kerak
   - Mumkin bo'lsa misol ("Bio: 'Algoritmik trading o'rgataman · Toshkent · DM ochiq'")

3. **scriptTimeline** — scriptMd dan parse qilingan ro'yxat: [{t: "Qadam 1", text: "...", cue: "Bajarish"}]. Har qadam = bitta element.

4. **aiCoachNote** (2-3 jumla) — vazifa tugagandan keyin nima o'zgaradi. Bu user'ga maqsadni ko'rsatadi.

5. **predict_evidence** — sof o'ylab topilgan raqam YOZ**MA**. Action vazifalar bevosita obunachi keltirmaydi. Yoz:
   ```
   {
     "impactBand": "setup",
     "directFollowersExpected": 0,
     "note": "Bu vazifa bajarilganda keyingi videolar 2-3x ko'proq engagement oladi. Algoritm sozlangan profilni tezroq aniqlaydi.",
     "_source": "writer_action"
   }
   ```

6. **shotList**: bo'sh ro'yxat [] (video emas)
7. **hashtags**: bo'sh ro'yxat [] (post emas)
8. **audioSuggestion**: null
9. **hookMeta**: {"energy": 5, "retention": 0.0, "cameraDirection": "Profil sozlamalari · video emas", "abVariant": "A"}

NIMA QILMA: hook variant B, audio takliflar, hashtag — bularning hech qaysisi action vazifa uchun kerak emas.

JSON output. Markdown blok yo'q."""


async def run(state: GrowthCoachState) -> dict:
    """Two strategies based on workflow:

    1. **content_review** (single-task fill) — write the FULL rich script for
       this one task. Uses SYSTEM_PROMPT_RICH + Opus, max_tokens=2500.

    2. **roadmap_generation** (initial onboarding) — TOPICS ONLY. Pass the
       strategy drafts straight through with no script: the roadmap is a list
       of N bare topics (title + goal). The rich script for each topic is
       written lazily via content_review after the user opens it and answers
       the Q&A interview.
    """
    tenant_id = state["tenant_id"]
    user_id = state.get("user_id")
    run_id = state["run_id"]
    drafts = state.get("proposed_tasks") or []
    if not drafts:
        return {}

    workflow = state.get("workflow") or ""
    # content_review = user opened a task → fill it richly. Initial onboarding
    # = use light outlines (rich version generated per-task on demand).
    rich_mode = workflow == "content_review"

    market = state.get("market_signals") or []
    industry = state.get("industry_signals") or []
    rejected = state.get("rejected_tasks") or []

    if rich_mode:
        return await _run_rich_single(
            state=state,
            tenant_id=tenant_id,
            user_id=user_id,
            run_id=run_id,
            draft=drafts[0],
            market=market,
            industry=industry,
            rejected=rejected,
        )

    # Initial onboarding path — TOPICS ONLY. The roadmap is a list of N topics
    # (title + goal_description from roadmap_generator). NO script is written
    # here: the full script is generated lazily when the user opens a topic,
    # answers the Q&A interview, and unlocks "write script" (content_review
    # workflow). So we pass the strategy drafts straight through to
    # drift_detector + output_validator unchanged — no LLM call, no enrichment.
    from app.graphs.state import CostLedger

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=(
            f"{len(drafts)} ta mavzu yo'l xaritasiga joylandi. Senariy har bir "
            "mavzuni ochib, AI savollariga javob berganingizdan keyin yoziladi."
        ),
        run_id=run_id,
        important=True,
    )

    return {
        "proposed_tasks": drafts,
        "cost": CostLedger(input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0),
        "notes": [f"scriptwriter: {len(drafts)} topics (no script at onboarding)"],
    }


async def _run_rich_single(
    *,
    state: GrowthCoachState,
    tenant_id: str,
    user_id: str | None,
    run_id: str,
    draft: dict,
    market: list,
    industry: list,
    rejected: list,
) -> dict:
    """Generate the FULL rich script for one task (content_review workflow).

    This is where the real quality lives: ~2500 output tokens dedicated to
    a single task, with exemplars + market signals as grounding context.
    """
    title = draft.get("title", "Task")
    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=f"\"{title}\" uchun batafsil stsenariy yozyapman — hook, kadrlar, audio, hashtag.",
        run_id=run_id,
    )

    # Per-task exemplar — query by hook/title so we ground the LLM in
    # actual successful posts from the same niche.
    exemplars = await similar_exemplar_posts(
        query=draft.get("hook") or draft.get("title", ""),
        niche=(state.get("north_star") or {}).get("niche", "general"),
        limit=3,
    )

    # Per-user knowledge vault — this tenant's past Q&A answers + insights,
    # semantically matched to this topic + their current answers. Injecting them
    # makes the new script reuse the user's established voice, facts and stories
    # across topics (the interconnected "vault").
    vault = await related_notes(
        tenant_id=tenant_id,
        query=f"{draft.get('title', '')} {state.get('instructions') or ''}",
        limit=5,
        exclude_task_id=state.get("task_id") or draft.get("id"),
    )

    # Hook bank — the user's OWN past published hooks. Distinct from `vault`
    # (Q&A answers) and `exemplars` (cross-tenant winners): this is the
    # user's actual on-platform voice, the hooks they were willing to ship.
    # Injected so the LLM keeps their tonal signature (energetic vs calm,
    # question vs fact, terse vs storytelling) instead of drifting toward
    # a generic style on every new task.
    past_hooks = await tenant_top_hooks(
        tenant_id=tenant_id,
        exclude_task_id=state.get("task_id") or draft.get("id"),
        limit=5,
    )

    # Action tasks (profile setup, content planning) need a DIFFERENT prompt
    # than video scripts — we generate detailed step-by-step instructions,
    # not hooks/shot-lists/hashtags. Without this branch, action tasks got
    # video-script output (empty shotList, fake follower predictions) and
    # the UI had nothing to render.
    is_action = (draft.get("type") or "").lower() == "action"
    _prompt_key = "scriptwriter_action" if is_action else "scriptwriter_rich"
    system_prompt = SYSTEM_PROMPT_ACTION if is_action else SYSTEM_PROMPT_RICH

    # Anti-fabrication gate: only treat the interview transcript as grounding when
    # it actually carries real content. Filler like "sen" / "faqat sen borsan" /
    # empty turns must NOT be fed as user_answers — the model would pad the script
    # with invented first-person claims ("dasturlashchi do'stlarim shikoyat
    # qiladi") despite the anti-fabrication rule, which reads as "juda sayoz".
    raw_answers = (state.get("instructions") or "").strip()
    grounded = is_substantive_answer(raw_answers)
    north = state.get("north_star") or {}

    s = get_settings()
    try:
        response, usage = await call_claude(
            # Opus for rich scriptwriting — this is the user-facing creative
            # core. Revisions drop to Sonnet for cost.
            model=s.model_scriptwriter_primary if not rejected else s.model_scriptwriter_revise,
            system=await resolve_prompt(_prompt_key, system_prompt),
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": draft,
                            "north_star": north,
                            # Goal taxonomy (Dizayn B) — directs hook/CTA/signal
                            # to the user's objective (reach/sales/followers/...).
                            "goal_directive": goal_directive_uz(north),
                            # Psychological profile + brand voice (Dizayn A) —
                            # tone/energy/address style. Empty for tenants who
                            # never ran the psych interview → prompt falls back to
                            # the niche standard.
                            "psych_profile": north.get("psych_profile") or {},
                            "brand_voice": north.get("brand_voice") or "",
                            "market_signals": market[:5],
                            "industry_signals": industry[:3],
                            "exemplars": exemplars,
                            "rejection_history": rejected,
                            # Grounding flag drives the anti-fabrication rule: when
                            # "none", the model must NOT write first-person claims.
                            "grounding": "grounded" if grounded else "none",
                            # User's interview answers — only passed when they're
                            # substantive; junk is withheld so the model can't
                            # mistake "sen"/"faqat sen borsan" for real content.
                            "user_answers": raw_answers if grounded else "",
                            # The user's OWN past answers from other topics —
                            # reuse their voice/facts/stories for consistency.
                            "vault_notes": [
                                {"title": n["title"], "body": n["body"][:600]}
                                for n in vault
                            ],
                            # The user's OWN published hooks — tonal signature.
                            # See SYSTEM_PROMPT_RICH for how the model uses these.
                            "past_hooks": past_hooks,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            # 6000 (was 2500): the RICH JSON now carries a full scriptMd + a
            # 6-8 row scriptTimeline + shotList + hashtags + meta. At 2500 the
            # response truncated mid-JSON → parse failed → salvage recovered
            # only the hook, so scriptMd/scriptTimeline came back empty and the
            # persister kept the old thin script.
            max_tokens=6000,
            response_format="json",
            prompt_cache={"system": True},
            agent_name="scriptwriter" if not is_action else "scriptwriter_action",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "scriptwriter.rich_failed — keeping draft as-is",
            error=str(exc)[:120],
        )
        from app.graphs.state import CostLedger
        _enrich_task(draft)
        return {
            "proposed_tasks": [draft],
            "cost": CostLedger(input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0),
            "notes": ["scriptwriter: rich passthrough (LLM unavailable)"],
        }

    raw_text = response.get("text") or "{}"
    try:
        polished = json.loads(raw_text)
        if not isinstance(polished, dict):
            polished = {}
    except json.JSONDecodeError as exc:
        log.warning("scriptwriter.rich_json_parse_failed", error=str(exc),
                    raw_prefix=raw_text[:300])
        # Salvage path — try to extract the first {...} block
        salvaged = _salvage_tasks(raw_text)
        polished = salvaged[0] if salvaged else {}

    # Merge polished output over the draft (LLM wins on detail fields,
    # draft wins on id/parent/depth/order).
    merged = {**draft, **polished}
    _enrich_task(merged)

    # Quality-guarantee loop: a director-grade depth check. If the first pass
    # comes back shallow (thin timeline/shotList, undirected shots, missing
    # reelType/hookB/music), do ONE targeted re-ask that fixes ONLY the named
    # gaps — so a shallow script is deepened instead of silently shipped. Capped
    # at a single retry (cost + recursion safety) and we keep the retry only if
    # it actually reduced the gaps, so a worse rewrite can never degrade output.
    depth_gaps = _validate_rich(merged)
    if depth_gaps and not is_action:
        merged, depth_gaps = await _deepen_once(
            s=s,
            prompt_key=_prompt_key,
            system_prompt=system_prompt,
            draft=draft,
            prior=polished,
            merged=merged,
            gaps=depth_gaps,
        )
    if depth_gaps:
        log.info("scriptwriter.rich_depth_gaps_after_retry", task=title[:40], gaps=depth_gaps)

    await emit_message(
        tenant_id=tenant_id,
        user_id=user_id,
        agent="writer",
        content=(
            f"\"{title}\" batafsil stsenariysi tayyor. "
            f"Hook: \"{(merged.get('hook') or '')[:80]}\"."
        ),
        run_id=run_id,
        important=True,
    )

    # Persist this interview into the vault so it grounds FUTURE scripts — but
    # ONLY when it's substantive. Saving junk ("sen"/"faqat sen borsan") would
    # poison the cross-topic vault and degrade every later script.
    if grounded:
        niche = north.get("niche") or ""
        await save_note(
            tenant_id=tenant_id,
            title=title,
            body=raw_answers,
            kind="qa",
            tags=[niche] if niche else [],
            source_task_id=state.get("task_id") or draft.get("id"),
        )

    return {
        "proposed_tasks": [merged],
        "cost": usage,
        "notes": [
            f"scriptwriter: rich-wrote 1 task ({title[:30]})"
            + (f" · depth gaps: {', '.join(depth_gaps)}" if depth_gaps else " · depth ok")
        ],
    }


async def _deepen_once(
    *,
    s: Any,
    prompt_key: str,
    system_prompt: str,
    draft: dict[str, Any],
    prior: dict[str, Any],
    merged: dict[str, Any],
    gaps: list[str],
) -> tuple[dict[str, Any], list[str]]:
    """One targeted rewrite pass to fix director-grade depth gaps. Returns the
    (possibly) improved task + its remaining gaps. Best-effort: on any failure or
    a non-improving rewrite, returns the original (merged, gaps) unchanged."""
    try:
        retry_resp, _retry_usage = await call_claude(
            # Sonnet — a cheap, instruction-following fix pass (not the Opus
            # creative-core call).
            model=s.model_scriptwriter_revise,
            system=await resolve_prompt(prompt_key, system_prompt),
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": (
                                "Quyidagi stsenariy YETARLICHA CHUQUR EMAS. Sanab "
                                "o'tilgan kamchiliklarni (gaps) TO'G'IRLA: scriptTimeline "
                                "va shotList kamida 6 tadan bo'lsin, har kadrda framing + "
                                "camera/position bo'lsin, reelType/hookVariantB/musicCues "
                                "to'ldirilsin. Ovoz va faktlarni saqlab, TO'LIQ JSON'ni "
                                "(o'sha formatda) QAYTA qaytar."
                            ),
                            "gaps": gaps,
                            "current": prior,
                            "task": draft,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            max_tokens=6000,
            response_format="json",
            agent_name="scriptwriter_revise",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("scriptwriter.deepen_failed", error=str(exc)[:120])
        return merged, gaps

    raw = retry_resp.get("text") or "{}"
    try:
        retry_polished = json.loads(raw)
        if not isinstance(retry_polished, dict):
            retry_polished = {}
    except json.JSONDecodeError:
        salvaged = _salvage_tasks(raw)
        retry_polished = salvaged[0] if salvaged else {}
    if not retry_polished:
        return merged, gaps

    retry_merged = {**merged, **retry_polished}
    _enrich_task(retry_merged)
    retry_gaps = _validate_rich(retry_merged)
    # Keep the rewrite ONLY if it strictly reduced the gap count.
    if len(retry_gaps) < len(gaps):
        return retry_merged, retry_gaps
    return merged, gaps


def _count_broll(shots: list[Any]) -> int:
    """How many shots carry a b-roll insert (the `b_roll`/`bRoll` field, non-empty &
    not a literal null-string). Used by the tutorial / broll_voiceover beat checks."""
    n = 0
    for sh in shots:
        if not isinstance(sh, dict):
            continue
        v = str(sh.get("b_roll") or sh.get("bRoll") or "").strip().lower()
        if v and v not in ("null", "none", "yo'q", "-"):
            n += 1
    return n


def _validate_rich(task: dict[str, Any]) -> list[str]:
    """Report director-grade DEPTH gaps in a rich script (pure; observability only,
    does NOT re-ask). Empty list = deep enough. Action tasks are exempt (no video).
    """
    if (task.get("type") or "").lower() == "action":
        return []
    gaps: list[str] = []

    timeline = task.get("script_timeline") or task.get("scriptTimeline") or []
    if not isinstance(timeline, list) or len(timeline) < 6:
        n = len(timeline) if isinstance(timeline, list) else 0
        gaps.append(f"scriptTimeline qisqa ({n} < 6)")

    shots = task.get("shot_list") or task.get("shotList") or []
    if not isinstance(shots, list) or len(shots) < 6:
        n = len(shots) if isinstance(shots, list) else 0
        gaps.append(f"shotList qisqa ({n} < 6)")
    else:
        directed = sum(
            1
            for sh in shots
            if isinstance(sh, dict)
            and (sh.get("framing") or sh.get("frame"))
            and (sh.get("camera") or sh.get("position") or sh.get("cam"))
        )
        if directed < len(shots) * 0.6:
            gaps.append(f"kadr rejissyorligi sayoz ({directed}/{len(shots)})")

    reel_type = str(task.get("reel_type") or task.get("reelType") or "").strip().lower()
    if not reel_type:
        gaps.append("reelType yo'q")
    # Per-reelType beat check (conservative, high-signal): only flag where the prompt's
    # beat-skeleton imposes an UNAMBIGUOUS, machine-checkable requirement, so a re-ask
    # never fires on a legitimately-shaped script. Other types (story/pov/skit/talking_head/
    # day_in_life) are structure-checked adequately by the generic depth gaps above; their
    # beats are prose-shaped and text-matching them would be false-positive-prone.
    if isinstance(shots, list) and shots:
        if reel_type == "listicle":
            # A listicle MUST show its items as on-screen text overlays.
            with_text = sum(
                1 for sh in shots
                if isinstance(sh, dict) and str(sh.get("on_screen_text") or sh.get("onScreenText") or "").strip()
            )
            if with_text < 3:
                gaps.append(f"listicle ro'yxat bandlari ko'rinmaydi (on_screen_text {with_text} < 3)")
        elif reel_type == "tutorial":
            # Beat-skeleton: "har qadamda b-roll insert" (CU + overhead/insert). A tutorial
            # with no insert shots is just a talking-head — flag the missing step inserts.
            with_broll = _count_broll(shots)
            if with_broll < 2:
                gaps.append(f"tutorial qadam-insert (b-roll) yetishmaydi ({with_broll} < 2)")
        elif reel_type == "broll_voiceover":
            # Beat-skeleton: "kamida 60% b-roll". Use a 50% floor so a borderline-compliant
            # script isn't re-asked, but a mostly-talking-head one that promises faceless is.
            with_broll = _count_broll(shots)
            if with_broll * 2 < len(shots):
                gaps.append(f"broll_voiceover b-roll yetarli emas ({with_broll}/{len(shots)} < 50%)")
    if not (task.get("hookVariantB") or task.get("hook_variant_b")):
        gaps.append("hookVariantB yo'q")
    if not (task.get("music_cues") or task.get("musicCues")):
        gaps.append("musicCues yo'q")
    return gaps


def _enrich_task(task: dict[str, Any]) -> None:
    """Derive scriptTimeline + aiCoachNote from the LLM output.

    The LLM prompt only asks for hook, scriptMd, shotList, hashtags.
    The UI expects richer fields (scriptTimeline, aiCoachNote) that are
    expensive to generate in a second LLM call, so we synthesise them
    deterministically from what we already have.
    """
    task_type = task.get("type", "reel")

    # Action tasks are profile/setup tasks, not video content.
    # They get a checklist UI instead of storyboard + recording pipeline.
    if task_type == "action":
        _enrich_action_task(task)
        return

    script_md = task.get("script_md") or task.get("scriptMd") or ""
    shot_list = task.get("shot_list") or task.get("shotList") or []

    # Prefer the LLM's rich second-by-second timeline (word-for-word narration +
    # wordCount + delivery + shotIndex). Only fall back to the lossy markdown
    # regex parse when the model didn't emit one — the old code ALWAYS re-parsed,
    # throwing away the depth the prompt asks for.
    llm_timeline = task.get("script_timeline") or task.get("scriptTimeline")
    if isinstance(llm_timeline, list) and llm_timeline:
        task["script_timeline"] = _normalize_timeline(llm_timeline)
    elif task_type in ("carousel", "post"):
        # Carousels/posts are per-SLIDE, not a per-second video timeline. The
        # video regex (_parse_script_md_to_timeline) scraped "**Label:**" out of
        # the CAPTION block → nonsense rows ("feed uchun", leaked "**"). Parse
        # slide sections instead; empty is better than corrupted.
        task["script_timeline"] = _parse_carousel_md_to_timeline(script_md)
    else:
        task["script_timeline"] = _parse_script_md_to_timeline(script_md, shot_list)
    task["ai_coach_note"] = _generate_ai_coach_note(task)

    # predict_evidence — qualitative bands instead of hallucinated numbers.
    # If the LLM grounded the prediction in an exemplar post, keep its
    # numbers. Otherwise back-fill with an honest "impact band + note"
    # shape so the UI shows "Kichik o'sish · taxminiy" instead of "267 obunachi".
    pred = task.get("predict_evidence") or task.get("predictEvidence") or {}
    if not isinstance(pred, dict):
        pred = {}
    # Has the LLM provided a real exemplar? If yes, leave numbers alone.
    has_exemplar = bool(pred.get("exemplarSource") or pred.get("exemplarReach"))
    if not has_exemplar:
        # Strip any LLM-hallucinated specific numbers — replace with a
        # qualitative band the UI knows how to render.
        pred.pop("predictedFollowers", None)
        pred.pop("followersStd", None)
        pred.pop("predictedSaves", None)
        pred.pop("reachLow", None)
        pred.pop("reachMid", None)
        pred.pop("reachHigh", None)
        pred.setdefault("impactBand", task.get("expectedImpact") or task.get("expected_impact") or "medium")
        pred.setdefault(
            "note",
            (
                "Aniq raqamli prognoz yo'q — bu kontent turi sizning akkauntingiz uchun "
                "yangi. 3-5 ta post chiqqach AI real ma'lumotlardan o'rganadi va keyingi "
                "topshiriqlar uchun aniq prognoz beradi."
            ),
        )
        pred.setdefault("_source", "writer_no_data")
    pred.setdefault("variantA", "A")
    task["predict_evidence"] = pred

    # Derive format + publishWindow if missing
    if not task.get("format"):
        task["format"] = {
            "reel": "Reel · 9:16 · 60s",
            "post": "Post · 1:1",
            "carousel": "Karusel · 1:1 · 5 slayd",
            "story": "Story · 9:16 · 15s",
            "live": "Live · vertikal",
        }.get(task_type, "Reel · 9:16 · 60s")
    if not task.get("publish_window") and not task.get("publishWindow"):
        task["publish_window"] = "Hafta · ish vaqti"

    # Guarantee hook_meta has the keys the header row renders
    meta = task.get("hook_meta") or task.get("hookMeta") or {}
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("cameraDirection", "Kamera yo'naltirilgan")
    meta.setdefault("energy", 7)
    meta.setdefault("retention", 0.65)
    meta.setdefault("abVariant", "A")
    task["hook_meta"] = meta


def _enrich_action_task(task: dict[str, Any]) -> None:
    """Action tasks get a checklist UI instead of video brief panels."""
    script_md = task.get("script_md") or task.get("scriptMd") or ""

    # Convert scriptMd into a checklist-style timeline
    task["script_timeline"] = _parse_action_md_to_checklist(script_md)
    task["shot_list"] = []
    task["hashtags"] = []
    task["audio_suggestion"] = None
    task["format"] = "Amaliyot · topshiriq"
    task["publish_window"] = "Istalgan vaqt"
    task["ai_coach_note"] = _generate_action_coach_note(task)

    # Action tasks get text-based impact, not numeric predictions
    pred = task.get("predict_evidence") or task.get("predictEvidence") or {}
    if not isinstance(pred, dict):
        pred = {}
    pred.setdefault("reachLow", 0)
    pred.setdefault("reachMid", 0)
    pred.setdefault("reachHigh", 0)
    pred.setdefault("predictedSaves", 0)
    pred.setdefault("predictedFollowers", 0)
    pred.setdefault("followersStd", 0)
    pred.setdefault("variantA", "Amaliyot")
    pred.setdefault("llmCritique", "Bu profil sozlash vazifasi. Bajarilganda keyingi kontentlar ko'proq engagement oladi.")
    task["predict_evidence"] = pred

    meta = task.get("hook_meta") or task.get("hookMeta") or {}
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("cameraDirection", "Profil sozlamalari")
    meta.setdefault("energy", 5)
    meta.setdefault("retention", 0.0)
    meta.setdefault("abVariant", "A")
    task["hook_meta"] = meta


def _parse_action_md_to_checklist(script_md: str) -> list[dict[str, str]]:
    """Turn markdown instructions into a checklist-style timeline."""
    if not script_md:
        return []
    import re

    lines = [ln.strip() for ln in script_md.splitlines() if ln.strip()]
    checklist: list[dict[str, str]] = []
    step = 1
    for line in lines:
        # Skip markdown headers and code-fence delimiters (``` lines aren't steps —
        # they used to slip through as a literal "```" checklist item).
        if line.startswith("#") or line.startswith("```"):
            continue
        # Remove bold/italic markers
        clean = re.sub(r"\*\*?", "", line)
        # Try to extract numbered/bulleted items
        m = re.match(r"^(?:\d+[.):-]\s*|[-•]\s*)(.+)", clean)
        text = m.group(1).strip() if m else clean.strip()
        # Skip punctuation-only noise ("...", "—", "***") that isn't a real instruction.
        if text and not re.match(r"^[\s`.\-–—•*_~]+$", text):
            checklist.append({
                "t": f"Qadam {step}",
                "text": text,
                "cue": "Bajarish",
            })
            step += 1
    return checklist


def _generate_action_coach_note(task: dict[str, Any]) -> str:
    return (
        "Bu amaliyot topshiriqni bajarganingizda keyingi kontentlar "
        "yanada samarali ishlaydi. Har bir qadamni ehtiyotkorlik bilan bajaring."
    )


def _parse_carousel_md_to_timeline(script_md: str) -> list[dict[str, str]]:
    """Per-slide timeline for a carousel/post. Splits on 'SLAYD/Slide N' headings
    (what the model actually emits) and takes each slide's body text. Returns []
    when no slide structure is found — an empty timeline is far better than the
    caption-scraped garbage the video parser produced for carousels."""
    if not script_md:
        return []
    import re

    # Split into slide sections at "SLAYD 1", "Slide 2", "1-slayd", "### Slayd" ...
    slide_re = re.compile(
        r"(?im)^\s*(?:#{1,4}\s*)?(?:slayd|slide|slayd[- ]?)\s*[:#-]?\s*(\d+)\b[:.\-)]*\s*(.*)$"
    )
    # (heading_start, heading_end, slide_no, inline_rest). heading_end is the end
    # of the heading LINE (the regex's (.*)$ stops at the newline), so the slide
    # body = script_md[heading_end : next heading_start] never re-includes the
    # heading — even with a blank line before the heading, which MULTILINE ^\s*
    # would otherwise fold into this match and leak the "SLAYD N:" marker.
    marks: list[tuple[int, int, int, str]] = []
    for m in slide_re.finditer(script_md):
        marks.append((m.start(), m.end(), int(m.group(1)), (m.group(2) or "").strip()))
    if not marks:
        return []

    def _clean(s: str) -> str:
        s = re.sub(r"\*\*?|`", "", s)  # drop bold/italic/code markers
        return re.sub(r"\s+", " ", s).strip()

    timeline: list[dict[str, str]] = []
    for idx, (_start, heading_end, no, inline) in enumerate(marks):
        next_start = marks[idx + 1][0] if idx + 1 < len(marks) else len(script_md)
        body = script_md[heading_end:next_start]  # everything AFTER this heading line
        parts = [inline] + [ln.strip() for ln in body.splitlines()]
        text = _clean(" ".join(p for p in parts if p))
        text = re.sub(r"^[\s.\-–—•*_~:#]+", "", text)  # strip leading noise
        if not text:
            continue
        timeline.append({"t": f"Slayd {no}", "text": text[:400], "cue": "Slayd"})
    return timeline


def _parse_script_md_to_timeline(script_md: str, shot_list: list[dict]) -> list[dict]:
    """Convert markdown script into the [{t, text, cue}] timeline the UI consumes."""
    import re

    if not script_md:
        return []

    timeline: list[dict] = []
    # Pattern 1: **Label (time):** text
    pattern = r'\*\*([^*]+)\s*\(([^)]+)\)\s*:\s*\*\*\s*([^\n]+)'
    matches = re.findall(pattern, script_md)

    if matches:
        for label, time, text in matches:
            timeline.append({
                "t": time.strip(),
                "text": text.strip(),
                "cue": _label_to_cue(label.strip()),
            })
        return timeline

    # Pattern 2: **Label:** text (no time)
    pattern2 = r'\*\*([^*]+)\s*:\s*\*\*\s*([^\n]+)'
    matches2 = re.findall(pattern2, script_md)
    if matches2:
        total_sec = _estimate_duration(shot_list)
        seg = max(total_sec / max(len(matches2), 1), 5)
        for i, (label, text) in enumerate(matches2):
            start = i * seg
            end = (i + 1) * seg
            timeline.append({
                "t": f"{start:.0f}-{end:.0f}s",
                "text": text.strip(),
                "cue": _label_to_cue(label.strip()),
            })
        return timeline

    # Fallback: split by double newlines (skip headers, code-fence delimiters and
    # punctuation-only noise so a stray "```"/"..." doesn't become a timeline segment).
    paragraphs = [
        p.strip()
        for p in script_md.split("\n\n")
        if p.strip()
        and not p.strip().startswith("#")
        and not p.strip().startswith("```")
        and not re.fullmatch(r"[\s`.\-–—•*_~]+", p.strip())
    ]
    total_sec = _estimate_duration(shot_list)
    seg = max(total_sec / max(len(paragraphs), 1), 5)
    for i, para in enumerate(paragraphs):
        start = i * seg
        end = (i + 1) * seg
        timeline.append({
            "t": f"{start:.0f}-{end:.0f}s",
            "text": para,
            "cue": "Voice-over",
        })
    return timeline


def _segment_seconds(t: str) -> float:
    """Parse a '13-24s' time label → its duration in seconds (0 if not a range)."""
    import re

    nums = re.findall(r"(\d+(?:\.\d+)?)", t or "")
    if len(nums) >= 2:
        return max(0.0, float(nums[1]) - float(nums[0]))
    return 0.0


def _normalize_timeline(rows: list) -> list[dict]:
    """Keep the LLM's rich second-by-second timeline; fill wordCount if missing
    and flag segments that are too short to fill their time (≈2.5 words/sec Uzbek
    speaking rate). Extra fields (delivery, shotIndex, pacingNote) ride along for
    the brief + the future production timeline; the UI reads {t, text, cue}."""
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        text = str(r.get("text") or "").strip()
        if not text:
            continue
        wc = r.get("wordCount")
        if not isinstance(wc, int) or wc <= 0:
            wc = len(text.split())
        seg = _segment_seconds(str(r.get("t") or ""))
        row: dict[str, Any] = {
            "t": str(r.get("t") or ""),
            "text": text,
            "wordCount": wc,
            "cue": str(r.get("cue") or "Voice-over"),
        }
        if r.get("delivery"):
            row["delivery"] = str(r["delivery"])[:120]
        if isinstance(r.get("shotIndex"), int):
            row["shotIndex"] = r["shotIndex"]
        # Pacing guard: a 10s segment needs ~25 words; flag if well under.
        if seg >= 3 and wc < seg * 2.0:
            row["pacingNote"] = f"qisqa: {wc} so'z / {seg:.0f}s (~{int(seg * 2.2)} kerak)"
        out.append(row)
    return out


def _label_to_cue(label: str) -> str:
    label_l = label.lower()
    if "hook" in label_l:
        return "Kamera yo'naltirish"
    if "cta" in label_l or "call" in label_l:
        return "Call to action"
    if "body" in label_l or "main" in label_l or "asosiy" in label_l:
        return "Voice-over"
    if "intro" in label_l or "boshlash" in label_l:
        return "Intro"
    if "outro" in label_l or "yakun" in label_l:
        return "Outro"
    return "Scene"


def _estimate_duration(shot_list: list[dict]) -> float:
    total = 0.0
    for shot in shot_list:
        sec = shot.get("sec") or shot.get("duration") or 0
        total += sec
    return max(total, 30.0)


def _generate_ai_coach_note(task: dict) -> str:
    hook = task.get("hook", "")
    task_type = task.get("type", "reel")

    # Locale-aware coaching note in Uzbek
    return (
        f"Bu {task_type} uchun asosiy kuch — birinchi 3 soniyada diqqatni jalb qilish. "
        f"\"{hook[:70]}\" hook'i scroll to'xtatish ehtimolini oshiradi. "
        f"Kadrlar rejasiga rioya qiling, ovoz aniq va energik bo'lsin. "
        f"Video oxirida aniq CTA (izoh, saqlash yoki ulashish) qoldiring."
    )


def _salvage_tasks(raw: str) -> list[dict]:
    """Scan for any balanced `{...}` chunk with a `title` key — used when
    Gemini truncates the outer JSON wrapper at the token limit.
    """
    tasks: list[dict] = []
    n = len(raw)
    i = 0
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        depth = 0
        j = i
        in_string = False
        escape = False
        while j < n:
            ch = raw[j]
            if escape:
                escape = False
            elif ch == "\\" and in_string:
                escape = True
            elif ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        if depth == 0 and j < n:
            chunk = raw[i : j + 1]
            try:
                obj = json.loads(chunk)
                if isinstance(obj, dict) and obj.get("title"):
                    tasks.append(obj)
            except json.JSONDecodeError:
                pass
            i = j + 1
        else:
            i += 1
    return tasks

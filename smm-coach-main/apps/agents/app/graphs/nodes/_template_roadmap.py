"""Deterministic roadmap fallback when both LLM providers are unavailable.

Why: Anthropic monthly spend caps + Gemini free-tier 20-req/day means a
demo can be one API call away from breaking. This module produces a
plausible 15-22 task roadmap from just the north-star inputs so the user
always sees a complete experience. The LLM upgrade path is purely
additive — once credits return, scriptwriter overwrites these drafts.

Every output here carries `predict_evidence._source = "template_fallback"`
so the UI can render a "AI vaqtinchalik offline — namunaviy roadmap"
banner. Tasks are NICHE-AGNOSTIC: no hardcoded food blogger references.
"""
from __future__ import annotations

from typing import Any

# Niche-agnostic hook patterns. Concrete enough to be useful, generic
# enough to slot into any niche. The {niche} token gets replaced.
_HOOK_PATTERNS = [
    "Birinchi 3 soniyada eng kuchli gap — keyin scroll to'xtaydi",
    "{niche} sohasidagi eng ko'p qilinadigan xato",
    "Hech kim aytmaydigan {niche} siri",
    "{niche}ga kirish — boshlovchilar uchun 1-qadam",
    "Sen ham shu xato qilayapsanmi? {niche} bo'yicha",
    "Mening tajribam — {niche}dagi birinchi yilim",
    "{niche}da 30 kun: nimalar ishladi, nimalar yo'q",
    "Soddagina ko'rsatma: {niche} bo'yicha",
]


def _format_for(task_type: str) -> str:
    return {
        "reel": "Reel · 9:16 · 60s",
        "post": "Post · 1:1",
        "carousel": "Karusel · 1:1 · 5 slayd",
        "story": "Story · 9:16 · 15s",
        "live": "Live · vertikal",
    }.get(task_type, "Reel · 9:16 · 60s")


def _publish_window(idx: int) -> str:
    days = [
        "Dush, 18:00 — 20:00",
        "Sesh, 19:00 — 21:00",
        "Chor, 12:00 — 14:00",
        "Pay, 20:00 — 22:00",
        "Jum, 19:00 — 21:00",
        "Shan, 11:00 — 13:00",
        "Yak, 11:00 — 13:00",
    ]
    return days[idx % len(days)]


def _task_count_for_gap(current: int, target: int) -> int:
    """Smaller accounts need MORE small wins; large accounts need fewer
    high-leverage tasks. 0→1k = 20 tasks. 1k→10k = 16. 10k+ = 13.

    The previous flat count=12 made every task carry "+83 followers" which
    is unrealistic for tiny accounts and triggered the "267 followers from
    bio" complaint when LLM hallucinated similar numbers.
    """
    gap = max(target - current, 0)
    if current < 500 or gap >= 5000:
        return 20
    if current < 5000 or gap >= 2000:
        return 16
    return 13


def synthesize_analysis(*, niche: str, target_audience: str, current_followers: int) -> dict:
    """Return the same JSON shape the initial_analysis Claude call produces.

    Crucially the strengths/weaknesses are PHRASED conditionally based on
    follower count — "tanish auditoriya bilan ishlash imkonini beradi"
    makes no sense for a 0-follower account. Now reads honestly.
    """
    is_new = current_followers < 100
    is_small = current_followers < 1000

    strengths = [
        f"Aniq soha tanlangan: {niche}. UZ bozorida bu yo'nalish ko'tarilmoqda.",
        "O'zbek tilida kontent — bu yo'nalishda raqobat past, sadoqat yuqori.",
    ]
    if not is_new:
        strengths.append(
            f"{current_followers:,} obunachi bor — bu bilan AI auditoriya tahliliga real baza."
        )
    else:
        strengths.append(
            "Yangi akkaunt — algoritm sizni qaytadan baholaydi, hech qanday eski yuk yo'q."
        )

    weaknesses = []
    if is_new:
        weaknesses.append(
            "0 ga yaqin obunachi — birinchi 30-50 obunachi qattiq mehnat talab qiladi (organik tabiiy."
        )
        weaknesses.append(
            "Profil ko'rinishi (rasm, bio, highlight) hali to'liq sozlanmagan deb taxmin qilamiz."
        )
    if is_small:
        weaknesses.append(
            "Algoritm sizning sohangizni hali aniqlamagan — birinchi 10-15 post test bo'ladi."
        )
    weaknesses.append(
        "Posting cadence rejasi yo'q — algoritm o'rtacha 4-5 post/hafta talab qiladi."
    )

    opportunities = [
        f"{niche} sohasida 'oson kirib chiqish' formati bo'sh — egallash mumkin.",
        "UZ trending audio'lar bilan birinchi 24 soat ichida joylangan postlar 3-5x reach.",
        "Hamkorlik (collab) — boshqa creator bilan bitta video, ikkala auditoriyaga tushadi.",
    ]

    # Pillars are GENERIC — the LLM-generated version produces niche-specific
    # ones. These are fine as a fallback skeleton.
    pillars = [
        {"name": "Asosiy ko'rsatma", "sharePct": 40,
         "rationale": "Yadro auditoriya talabini qondiradi"},
        {"name": "Quick tips · 60 soniya", "sharePct": 25,
         "rationale": "Yuqori share-rate"},
        {"name": "Behind-the-scenes", "sharePct": 20,
         "rationale": "Sadoqatni oshiradi"},
        {"name": "Trend remix · UZ audio", "sharePct": 15,
         "rationale": "Yangi auditoriya"},
    ]

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "opportunities": opportunities,
        "recommendedNiche": niche,
        "audience": {
            "summary": target_audience,
            "inferredAgeBand": "25-34",
            "inferredLocations": ["Toshkent", "Samarqand", "Buxoro"],
            "activeHours": ["19:00", "20:00", "21:00", "12:00", "13:00"],
        },
        "pillars": pillars,
        "_source": "template_fallback",
    }


def _impact_band_for(current_followers: int, task_idx: int, is_action: bool) -> str:
    """Qualitative impact band — replaces the old fake `predictedFollowers`
    number. Action tasks: no direct growth. Content tasks: scaled by task
    index and current followers.

    User sees a colored badge ("Kichik / O'rta / Yuqori ta'sir") not a
    hallucinated specific number.
    """
    if is_action:
        return "setup"  # special band — UI renders "Tayyorgarlik · keyingi vazifalar uchun zamin"
    # First few content tasks: low impact (algorithm test phase)
    if task_idx < 3:
        return "low"
    # Mid content tasks: medium impact if account has some traction
    if current_followers < 200:
        return "low"
    if current_followers < 2000:
        return "medium"
    return "medium" if task_idx % 3 != 0 else "high"


def synthesize_roadmap(
    *,
    niche: str,
    target_audience: str,
    current_followers: int,
    target_followers: int,
    count: int | None = None,
) -> dict:
    """Return the same JSON shape that roadmap_generator's Claude call produces.

    Tasks are NICHE-AGNOSTIC. No hardcoded "azizakitchen", "tabletop", or
    food-blogger references — every {niche} placeholder gets replaced with
    the user's actual niche string.
    """
    if count is None:
        count = _task_count_for_gap(current_followers, target_followers)

    # First 3 tasks are action/setup tasks, the rest are content.
    action_titles = [
        "Profilni to'liq sozlash — bio, rasm, highlight",
        f"3 ta kontent ustunini aniqlash · {niche} bo'yicha",
        "5 ta hayotiy story mavzusini yozib olish",
    ]
    # Niche-agnostic content task titles. Most have {niche} placeholder.
    content_titles = [
        "Hook usulini sinash · A/B variant",
        "{niche} sohasidagi 3 ta eng katta xato",
        "Meni {niche}ga olib kelgan 1 ta voqea",
        "Behind-the-scenes · ish jarayoni",
        "Trend audio + {niche} maslahati",
        "Voice-over: nima xato qilyapsiz",
        "3 ta foydali tip · qisqa format",
        "{niche} uchun to'liq qo'llanma · longform",
        "Comparison: oldin va keyin · {niche}",
        "Q&A: izohlardan eng ko'p so'rovlar",
        "Bir kunlik ko'rsatma · {niche}",
        "Recap · oxirgi 30 kun nimalar o'zgardi",
        "Mini-tutorial · {niche}da 5 daqiqa",
        "Eng oddiy yo'l · {niche}ga kirish",
        "Mythbusting: {niche} haqida noto'g'ri fikrlar",
        "Tools / vositalar — nimadan boshlash",
        "Listen-and-learn · jonli izoh javobi",
    ]

    tasks: list[dict[str, Any]] = []
    n_to_make = count
    for i in range(n_to_make):
        is_action = i < 3
        impact_band = _impact_band_for(current_followers, i, is_action)
        if is_action:
            title = action_titles[i % len(action_titles)]
            task_type = "action"
            hook = (
                "Bu vazifa bajarilganda keyingi videolar yaxshiroq ishlaydi — "
                "algoritm sizni topishi osonlashadi"
            )
            # Each action task has its own checklist body
            script_md = _action_body(i)
            shot_list: list[dict] = []
            hashtags: list[str] = []
            pred_evidence: dict = {
                "impactBand": "setup",
                "directFollowersExpected": 0,  # honest: setup tasks don't bring followers
                "note": (
                    "Profil sozlash bevosita obunachi keltirmaydi — keyingi videolar "
                    "uchun zamin yaratadi. Algoritm yaxshi sozlangan profilni bilib oladi."
                ),
                "_source": "template_fallback",
            }
            hook_meta = {
                "energy": 5,
                "retention": 0.0,
                "cameraDirection": "Profil sozlamalari · video emas",
                "abVariant": "A",
            }
            fmt = "Amaliyot · topshiriq"
            pub_win = "Istalgan vaqt"
        else:
            content_idx = i - 3
            base_title = content_titles[content_idx % len(content_titles)]
            niche_clean = niche.replace("_", " ").strip() or "siz tanlagan soha"
            title = base_title.replace("{niche}", niche_clean)
            task_type = "reel" if content_idx % 4 != 3 else "carousel"
            pattern = _HOOK_PATTERNS[content_idx % len(_HOOK_PATTERNS)]
            hook = pattern.replace("{niche}", niche_clean).replace("{n}", "73")
            # Generic script body — NICHE-AGNOSTIC, no cooking references
            script_md = _content_body(title, hook, niche_clean, target_audience)
            # Generic shot list — works for any niche
            shot_list = [
                {"i": 1, "cam": "Statik", "frame": "Close-up", "sec": 3,
                 "action": "Hookni aniq aytish · diqqatni jalb qilish"},
                {"i": 2, "cam": "Statik", "frame": "Medium", "sec": 8,
                 "action": "Asosiy fikrning birinchi qismi"},
                {"i": 3, "cam": "Statik", "frame": "Close-up", "sec": 7,
                 "action": "Misol yoki ko'rsatma"},
                {"i": 4, "cam": "Statik", "frame": "Medium", "sec": 7,
                 "action": "Asosiy fikrning ikkinchi qismi"},
                {"i": 5, "cam": "Statik", "frame": "Close-up", "sec": 5,
                 "action": "CTA: izohga yozish, saqlash"},
            ]
            # Niche-aware hashtags — built from the actual niche string
            niche_tag = niche.replace("_", "").replace(" ", "").lower()
            hashtags = [
                f"#{niche_tag}" if niche_tag else "#kontent",
                f"#{niche_tag}uz" if niche_tag else "#uzkontent",
                "#uzbekistan",
                "#toshkent",
                "#reelsuz",
                "#trenduz",
                "#kontent",
                "#instagramuz",
            ]
            pred_evidence = {
                "impactBand": impact_band,
                "note": (
                    "Aniq obunachi soni emas — sifatli vazifa bajarilganda algoritm "
                    "sizni yangi auditoriyaga ko'rsatadi. Real ma'lumotlar 5-10 ta "
                    "post chiqqach paydo bo'ladi."
                ),
                "_source": "template_fallback",
            }
            hook_meta = {
                "energy": 7 + (content_idx % 4),
                "retention": round(0.55 + (content_idx % 5) * 0.05, 2),
                "cameraDirection": "Statik kamera · stabilizator",
                "abVariant": "A",
            }
            fmt = _format_for(task_type)
            pub_win = _publish_window(content_idx)

        # Flat roadmap: branching (parentId/depth>0) isn't rendered yet and the persister forces
        # depth=0 / parentId=NULL, while every web+voice consumer filters WHERE depth=0. Emitting a
        # depth=1 side-branch here only produced tasks that got counted but never shown. Keep it flat.
        depth = 0
        parent_id = None

        tasks.append(
            {
                "parentId": parent_id,
                "orderInBranch": i,
                "depth": depth,
                "title": title,
                "type": task_type,
                "hook": hook,
                "scriptMd": script_md,
                "shotList": shot_list,
                "hashtags": hashtags,
                "format": fmt,
                "publishWindow": pub_win,
                "predict_evidence": pred_evidence,
                "hook_meta": hook_meta,
                # Tag every fallback task so the UI can render the badge
                # and the scriptwriter knows to upgrade these on next pass.
                "_template_fallback": True,
            }
        )

    return {
        "summary": (
            f"{niche.replace('_', ' ').title()} · {len(tasks)} ta vazifa, "
            f"{current_followers:,} → {target_followers:,} obunachi yo'lida. "
            "AI vaqtinchalik offline — bu shablon. 'Qayta tuzish' tugmasini "
            "bosib to'liq AI versiyani oling."
        ),
        "projectedCompletion": "2026-08-01T00:00:00Z",
        "tasks": tasks,
        "_template_fallback": True,
    }


def _action_body(idx: int) -> str:
    """Per-action-task body — each gets its own steps, not the same text."""
    if idx == 0:
        return (
            "### Profilni to'liq sozlash\n\n"
            "1. **Bio yozing** — kim siz, nima qilasiz, kim uchun. 150 belgi.\n"
            "2. **Profil rasmini almashtiring** — yorqin, aniq, sohaga mos.\n"
            "3. **Highlights yarating** — 3 ta: 'Boshlash', 'Eng yaxshilari', 'FAQ'.\n"
            "4. **Kategoriya tanlang** — Settings → Account → Category.\n"
            "5. **Contact ma'lumotlari** — email yoki Telegram qo'shing.\n"
            "6. **Aloqa tugmalari** — DM, WhatsApp, agar tegishli bo'lsa."
        )
    if idx == 1:
        return (
            "### 3 ta kontent ustunini aniqlang\n\n"
            "Sizning hamma postingiz 3 ta katta mavzu atrofida bo'lishi kerak. "
            "Bu algoritmga sizni aniqlashga yordam beradi.\n\n"
            "1. **Asosiy ustun (40%)** — eng ko'p post qilasiz, yadro auditoriya keladi.\n"
            "2. **Tezkor tip ustuni (30%)** — short, qisqa, share-able.\n"
            "3. **Shaxsiy/BTS ustuni (30%)** — sodaqat ushlab turadi.\n\n"
            "Har birini bitta jumla bilan yozing va saqlab qo'ying."
        )
    return (
        "### 5 ta hayotiy story mavzusi\n\n"
        "Reels'dan tashqari, Stories'ni ham doimiy yuriting. Bu algoritmda "
        "doimiy faolligingizni ko'rsatadi.\n\n"
        "1. Kun davomida nimadir qilish jarayoni.\n"
        "2. Savol-javob (Question sticker).\n"
        "3. Tezkor maslahat (5-15 soniya).\n"
        "4. Audience'dan biror narsa so'rab ko'rish (Poll).\n"
        "5. Eng so'nggi post'ni eslatib o'tish.\n\n"
        "Har biri uchun mavzuni yozib qo'ying — keyin har kuni boshlash oson."
    )


def _content_body(title: str, hook: str, niche: str, target_audience: str) -> str:
    """Niche-agnostic content script body — works for fitness, tech,
    beauty, education, whatever.
    """
    return (
        f"### {title}\n\n"
        f"**Hook (0-3s):** {hook}\n\n"
        f"**Body (3-25s):** {target_audience or 'auditoriyangiz'} uchun aniq qadam-baqadam "
        f"ko'rsatma. Statik kamera, ovoz tinch va aniq. {niche} sohasiga oid bitta aniq fakt "
        f"yoki maslahat bilan boshlang.\n\n"
        f"**CTA (25-30s):** \"Saqlab qo'y va sinab ko'r — natijani izohlarga yoz.\""
    )

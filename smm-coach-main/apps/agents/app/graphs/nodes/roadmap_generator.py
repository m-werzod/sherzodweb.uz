"""One-shot Opus 4.7 call that turns the north-star + initial analysis into a
14-30 node tree of content tasks. Tasks are saved as `proposed_tasks` and
flow through scriptwriter, drift_detector, output_validator before becoming
`approved_tasks`.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from app.config import get_settings
from app.graphs.goal_profiles import goal_directive_uz
from app.graphs.nodes._template_roadmap import synthesize_roadmap
from app.graphs.prompt_store import resolve_prompt
from app.graphs.state import CostLedger, GrowthCoachState
from app.integrations.llm.anthropic_client import call_claude
from app.memory.db import get_sessionmaker
from app.memory.vault_context import load_vault_context
from app.streams.bus import publish

log = structlog.get_logger(__name__)

_VAULT_HEADER = "BILIM OMBORI (foydalanuvchi tarixi + o'tmish saboqlari — REJANI SHULARGA ASOSLA)"


async def _load_vault_context(tenant_id: str, north: dict) -> str:
    """The PLANNER grounds the roadmap in accumulated vault knowledge (past-cycle
    lessons, the user's story/psychology, niche insights) — closing the loop:
    performance_review writes lessons_learned → roadmap_generator reads them next."""
    query = " ".join(
        str(x)
        for x in (
            north.get("niche") or "",
            north.get("target_audience") or "",
            north.get("primary_goal") or "",
            "kontent strategiya o'tmish natija saboqlari",
        )
        if x
    ).strip()
    return await load_vault_context(tenant_id, query, _VAULT_HEADER)


async def _load_replan_pivots(tenant_id: str) -> tuple[list[str], list[str]]:
    """Latest OPEN underperform PerformanceReview's pivots + root causes for this
    tenant, injected into the prompt on a user-approved replan so the new roadmap
    learns from real results. Best-effort — returns ([], []) on any error.

    Stage 13: the table now also holds `breakout` / `negative_wave` alerts whose
    pivots are per-post nudges, NOT roadmap-level direction. Filter to
    `underperform` so a replan never learns from (or silently clears) those.
    """
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, "recommendedPivots", "rootCauses"
                    FROM performance_reviews
                    WHERE "tenantId" = :tid AND status = 'open'
                      AND kind = 'underperform'
                    ORDER BY "createdAt" DESC
                    LIMIT 1
                    """
                ),
                {"tid": tenant_id},
            )
            row = result.mappings().first()
            if not row:
                return [], []
            pivots = row["recommendedPivots"] or []
            causes = row["rootCauses"] or []
            # Consume it: mark applied so the dashboard banner clears and a later
            # replan doesn't re-inject the same stale recommendation.
            await session.execute(
                text("UPDATE performance_reviews SET status = 'applied' WHERE id = :id"),
                {"id": row["id"]},
            )
            await session.commit()
        return ([str(p) for p in pivots if p], [str(c) for c in causes if c])
    except Exception as exc:  # noqa: BLE001
        log.warning("roadmap_generator.replan_pivots_failed", error=str(exc)[:120])
        return [], []


SYSTEM_PROMPT = """Sen Instagram o'sish bo'yicha **STRATEG**isan. Sening vazifang yo'l xaritasi tuzish — har bir vazifaning **NIMA** va **NIMA UCHUN** qismini yozish. Stsenariyni keyin scriptwriter agent yozadi.

QAT'IY QOIDALAR:

1. **Vazifa soni** — follower gap'iga qarab:
   - 0 → 1K: **20 ta vazifa** (kichik qadamlar, har biri kuchli kontekstda)
   - 1K → 10K: **16 ta vazifa**
   - 10K+: **13 ta vazifa**
   Hech qachon 10 tadan kam emas. Hech qachon 25 tadan ko'p emas.

2. **Faqat 1 ta "action" vazifa** — birinchi vazifa: profilni to'liq sozlash (bio, avatar, highlight, kategoriya). Bu foydalanuvchi O'ZI bajaradigan yagona tayyorgarlik. Qolgan HAMMA vazifa KONTENT bo'lsin (reel/post/carousel/story), tayyor stsenariy bilan.

   **TAHLILNI O'ZING QIL — foydalanuvchiga uy vazifasi BERMA:** raqobatchilar tahlili, nisha tahlili, kontent strategiyasi, raqobatchi kamchiliklarini topish — bularni AI agentlar (Market Analyst, Industry News) o'zlari bajaradi va natijani stsenariylarga singdiradi. Hech qachon "raqiblaringizni tahlil qiling", "nisha tahlilini bajaring" yoki "strategiya ishlab chiqing" kabi TADQIQOT vazifasini foydalanuvchiga berma — bu sening (AI) ishing. Foydalanuvchi faqat profilni sozlaydi va KONTENT yaratadi.

3. **Asosiy yo'lni saqla** — sohadan chiqma. 1-2 "qo'shni mavzu" mumkin, lekin yadro aniq.

4. **Tree depth** — 0 dan boshlab maksimum 2 (yon shoxlari). Asosiy yo'l depth=0, qo'shimcha shoxlar depth=1.

5. **Har bir vazifa uchun QUYIDAGINI yoz** (boshqa narsa yoz**MA**):
   - `title`: 4-10 so'z, AKTIV, **shu vazifa nima ekanligini aniq aytadigan**
     ✅ "Birinchi viral hook formulasini sinash · A/B"
     ❌ "Birinchi post"
   - `type`: "reel" / "post" / "carousel" / "story" / "action"
   - `goal_description`: 2-3 jumla — **NIMA UCHUN aynan shu vazifa shu joyda**? Strategiyaga qanday bog'lanadi?
   - `expected_impact`: "low" / "medium" / "high" — **faqat band, raqam yoz**MA. Algoritm test fazasidagi tasklar low, mature kontent medium-high.
   - `parentId`: null yoki avvalgi task indeksi
   - `orderInBranch`: 0 dan boshlab
   - `depth`: 0 yoki 1
   - `funnelStage`: "awareness" | "consideration" | "conversion" — voronka bosqichi
   - `ctaType`: "follow" | "save" | "share" | "dm" | "link" | "comment" — asosiy harakatga chaqiriq

5b. **KONTENT VORONKASI — MUHIM**: yo'l xaritasi shunchaki mavzular ro'yxati emas, ATAYLAB qurilgan VORONKA bo'lsin. Foydalanuvchi xabaridagi **"MAQSAD / FUNNEL TAQSIMOTI"** blokiga qat'iy AMAL QIL — funnel nisbati (awareness/consideration/conversion), format urg'usi, hook turlari va cta(CTA) urg'usi o'sha blokdan keladi. Boshida awareness ko'proq, oxiriga borib conversion ko'payadi. Har vazifaga funnelStage + mos ctaType ber.

6. **MUHIM — RAQAM HALLUCINATE QILMA**:
   - `expectedMetrics`, `followersDelta`, `engagementRate` kabi raqamli da'volar yoz**MA**.
   - Sen STRATEGsan, bashoratchi emas. Real ma'lumotlar yig'ilganida tizim o'zi hisoblaydi.

7. **scriptMd, shotList, hashtags YOZ**MA — bularni scriptwriter agent har vazifa uchun alohida chuqur ishlab chiqadi. Sen faqat strategiyani ber.

JSON formatda chiqishni ber:
```
{
  "summary": "string (max 200 belgi, strategiyaning umumiy mantig'i)",
  "projectedCompletion": "ISO date",
  "tasks": [
    {
      "parentId": null | "task-N",
      "orderInBranch": 0,
      "depth": 0,
      "title": "...",
      "type": "action" | "reel" | "post" | "carousel" | "story",
      "goal_description": "...",
      "expected_impact": "low" | "medium" | "high",
      "funnelStage": "awareness" | "consideration" | "conversion",
      "ctaType": "follow" | "save" | "share" | "dm" | "link" | "comment",
      "is_setup": true   // faqat action tasklar uchun
    }
  ]
}
```

Output FAQAT JSON. Markdown blok yoki tushuntirish matni QO'SHMA."""


async def run(state: GrowthCoachState) -> dict:
    # tracker_pulse has nothing to do with roadmap generation — it just
    # refreshes metrics on already-published tasks. Skip the (expensive) Opus
    # call entirely. Before this short-circuit, every 6h scheduler tick fired
    # a fresh roadmap_generator call per active tenant (~$1.50/run × N tenants).
    if state.get("workflow") == "tracker_pulse":
        return {}

    # content_review loads a single existing task instead of generating a new
    # roadmap. The task flows through scriptwriter → drift_detector → validator
    # exactly like a draft, but roadmap_persister updates the row in-place.
    if state.get("workflow") == "content_review":
        return await _load_task_for_content_review(state)

    user_id = state.get("user_id") or "system"
    run_id = state["run_id"]

    await publish(user_id, {"type": "agent.thinking", "runId": run_id, "agent": "roadmap_generator",
                            "note": "Yo'l xaritasini chizmoqdaman", "at": _now()})

    north = state.get("north_star") or {}
    analysis = state.get("analysis_summary") or ""
    # Past-content dedup: append the topics the user already published (from the
    # onboarding IG analysis) to the analysis context so BOTH the regular and
    # the cadence-sized paths get told not to repeat them. (Folded into
    # `analysis` because that string flows into every prompt builder below.)
    _avoid = state.get("existing_post_topics") or []
    if _avoid:
        _joined = "\n".join(f"- {t}" for t in _avoid[:20])
        analysis += (
            "\n\n--- FOYDALANUVCHI ALLAQACHON CHOP ETGAN MAVZULAR (BULARNI TAKRORLAMA) ---\n"
            f"{_joined}\n"
            "Bu mavzularni qayta ishlatma — yangi, to'ldiruvchi mavzular ber."
        )

    # Vault grounding (Stage 6): inject the tenant's most relevant knowledge-vault
    # notes — past-cycle lessons (performance_review), the user's story/psychology
    # (initial_analysis), niche insights — so the PLANNER reuses accumulated
    # knowledge, not just the scriptwriter. Empty for pre-existing tenants with no
    # vault, so their roadmap output is unchanged. Runs for both onboarding and
    # replan (content_review/tracker_pulse already returned above).
    _vault = await _load_vault_context(state["tenant_id"], north)
    if _vault:
        analysis += _vault

    # Replan learning: on a user-approved replan, fold the latest OPEN
    # PerformanceReview's pivots into the prompt so the regenerated roadmap
    # reflects what actually worked / flopped last cycle (the closed loop).
    if (state.get("workflow") or "") == "replan":
        _pivots, _causes = await _load_replan_pivots(state["tenant_id"])
        if _pivots:
            _pj = "\n".join(f"- {p}" for p in _pivots[:6])
            analysis += (
                "\n\n--- O'TGAN SIKL NATIJALARIDAN O'RGAN (REPLAN) ---\n"
                f"Tavsiya etilgan yo'nalishlar (BULARNI KUCHAYTIR):\n{_pj}\n"
            )
            _cj = "; ".join(str(c) for c in _causes[:6])
            if _cj:
                analysis += f"Past natija sabablari (BULARDAN QOCH): {_cj}\n"

    # Cadence-driven sizing: when the user picked a posts-per-day cadence at
    # onboarding, initial_analysis put N in north_star.roadmap_size. Generate
    # exactly N topics (batched so a large N doesn't truncate one response).
    target_n = int(north.get("roadmap_size") or 0)
    if target_n > 0:
        return await _draft_sized_roadmap(north, analysis, target_n, run_id, user_id)

    try:
        response, usage = await call_claude(
            model=get_settings().model_roadmap_generator,
            system=await resolve_prompt("roadmap_generator", SYSTEM_PROMPT),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Soha: {north.get('niche')}\n"
                        f"Soha tafsiloti: {north.get('niche_detail', '')}\n"
                        f"Target audience: {north.get('target_audience')}\n"
                        f"Hozirgi obunachi: {north.get('current_followers')}\n"
                        f"Maqsad: {north.get('target_followers')}\n"
                        f"Region: {north.get('region', 'uz')}\n\n"
                        f"{goal_directive_uz(north)}\n\n"
                        f"--- Akkaunt tahlili ---\n{analysis}\n\n"
                        "Endi mukammal JSON roadmap ber."
                    ),
                }
            ],
            max_tokens=12000,
            response_format="json",
            agent_name="roadmap_generator",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "roadmap.llm_failed — using template fallback",
            error=str(exc)[:120],
        )
        parsed = synthesize_roadmap(
            niche=str(north.get("niche") or "general"),
            target_audience=str(north.get("target_audience") or ""),
            current_followers=int(north.get("current_followers") or 0),
            target_followers=int(north.get("target_followers") or 0),
        )
        return {
            "proposed_tasks": [_normalize(t) for t in parsed.get("tasks", [])],
            "cost": CostLedger(input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0),
            "notes": [f"roadmap_generator: template fallback drafted {len(parsed.get('tasks', []))} tasks"],
        }

    raw = response.get("text") or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning(
            "roadmap.json_parse_failed",
            error=str(exc),
            raw_len=len(raw),
            raw_prefix=raw[:300],
            raw_suffix=raw[-300:] if len(raw) > 300 else "",
            model=response.get("model"),
        )
        # Try a best-effort salvage: parse balanced `{...}` task objects.
        parsed = _salvage_tasks(raw)
        if not parsed.get("tasks"):
            log.info("roadmap.salvage_empty — using template fallback")
            parsed = synthesize_roadmap(
                niche=str(north.get("niche") or "general"),
                target_audience=str(north.get("target_audience") or ""),
                current_followers=int(north.get("current_followers") or 0),
                target_followers=int(north.get("target_followers") or 0),
            )

    tasks = parsed.get("tasks") or []

    # Guard: if the LLM returns too few tasks (< 10), the UX is poor — each
    # task carries too big a follower chunk and the user feels the system
    # is shallow. Fall back to the template which scales count by gap.
    if len(tasks) < 10:
        log.warning(
            "roadmap_generator.too_few_tasks",
            count=len(tasks),
            threshold=10,
            model=response.get("model"),
        )
        parsed = synthesize_roadmap(
            niche=str(north.get("niche") or "general"),
            target_audience=str(north.get("target_audience") or ""),
            current_followers=int(north.get("current_followers") or 0),
            target_followers=int(north.get("target_followers") or 0),
        )
        tasks = parsed.get("tasks", [])
        usage = CostLedger(input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0)

    # Tag whether the tasks came from the LLM or the deterministic template.
    # The UI uses this to show an "AI vaqtinchalik offline · namunaviy"
    # badge so users know to retry once credits return. Persister copies
    # this flag into predict_evidence._source.
    template_used = parsed.get("_template_fallback", False)

    return {
        "proposed_tasks": [_normalize(t) for t in tasks],
        "cost": usage,
        "notes": [
            f"roadmap_generator: drafted {len(tasks)} tasks"
            + (" (template fallback)" if template_used else "")
        ],
    }


_BATCH_SIZE = 30


def _add_cost(a: CostLedger, b: CostLedger) -> CostLedger:
    return CostLedger(
        input_tokens=a["input_tokens"] + b["input_tokens"],
        output_tokens=a["output_tokens"] + b["output_tokens"],
        cached_tokens=a["cached_tokens"] + b["cached_tokens"],
        cost_usd=a["cost_usd"] + b["cost_usd"],
    )


async def _draft_batch(
    north: dict,
    analysis: str,
    count: int,
    batch_idx: int,
    total_batches: int,
    existing_titles: list[str],
) -> tuple[list[dict], CostLedger]:
    """One Claude call producing up to `count` topic drafts (no scripts)."""
    size_rule = (
        f"MUHIM: aynan **{count} ta** vazifa yarat. "
        f"Tizim prompti #1-qoidasidagi follower-gap sonini E'TIBORGA OLMA — {count} ta ber.\n"
    )
    if total_batches > 1:
        joined = "\n".join(f"- {t}" for t in existing_titles[-40:])
        size_rule += (
            f"Bu yo'l xaritasining {batch_idx + 1}/{total_batches}-qismi. "
            f"Quyidagi mavzular ALLAQACHON bor — TAKRORLAMA, davomini ber:\n{joined}\n"
        )
        if batch_idx > 0:
            size_rule += (
                "Faqat KONTENT vazifalari (reel/post/carousel/story) ber — "
                "profil sozlash ('action') vazifasini QO'SHMA, u allaqachon bor.\n"
            )
    response, usage = await call_claude(
        model=get_settings().model_roadmap_generator,
        system=await resolve_prompt("roadmap_generator", SYSTEM_PROMPT),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Soha: {north.get('niche')}\n"
                    f"Soha tafsiloti: {north.get('niche_detail', '')}\n"
                    f"Target audience: {north.get('target_audience')}\n"
                    f"Hozirgi obunachi: {north.get('current_followers')}\n"
                    f"Maqsad: {north.get('target_followers')}\n"
                    f"Region: {north.get('region', 'uz')}\n\n"
                    f"{goal_directive_uz(north)}\n\n"
                    f"--- Akkaunt tahlili ---\n{analysis}\n\n"
                    + size_rule
                    + "Endi mukammal JSON roadmap ber."
                ),
            }
        ],
        max_tokens=12000,
        response_format="json",
        agent_name="roadmap_generator",
    )
    raw = response.get("text") or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = _salvage_tasks(raw)
    return parsed.get("tasks") or [], usage


async def _draft_sized_roadmap(
    north: dict,
    analysis: str,
    target_n: int,
    run_id: str,
    user_id: str,
) -> dict:
    """Generate exactly `target_n` topics, batching large N across calls.

    The persister flattens parentId to NULL and assigns order itself, so we
    only need a flat list of topic dicts (depth defaults to 0).
    """
    import math

    total_batches = max(1, math.ceil(target_n / _BATCH_SIZE))
    all_tasks: list[dict] = []
    total_usage = CostLedger(input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0)

    # Top up until target_n. A batch often truncates (the model emits fewer
    # than `count` well-formed objects under max_tokens), so a fixed
    # `total_batches` loop would silently under-deliver below the cadence
    # promise. Keep requesting the shortfall — with a hard attempt cap, and
    # stopping early if a batch returns nothing (model is dry) to avoid a hot
    # loop / runaway spend.
    max_attempts = total_batches + 3
    attempt = 0
    while len(all_tasks) < target_n and attempt < max_attempts:
        remaining = target_n - len(all_tasks)
        try:
            batch_tasks, usage = await _draft_batch(
                north,
                analysis,
                min(_BATCH_SIZE, remaining),
                attempt,
                max(total_batches, attempt + 1),
                [t.get("title", "") for t in all_tasks],
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("roadmap.batch_failed", batch=attempt, error=str(exc)[:120])
            break
        if not batch_tasks:
            log.info("roadmap.batch_empty — stopping top-up", attempt=attempt, got=len(all_tasks))
            break
        all_tasks.extend(batch_tasks)
        total_usage = _add_cost(total_usage, usage)
        attempt += 1
        if user_id:
            await publish(user_id, {
                "type": "agent.thinking", "runId": run_id, "agent": "roadmap_generator",
                "note": f"{len(all_tasks)}/{target_n} mavzu tayyor", "at": _now(),
            })

    # Total LLM failure → deterministic template so onboarding still completes.
    if not all_tasks:
        log.info("roadmap.sized_empty — using template fallback")
        parsed = synthesize_roadmap(
            niche=str(north.get("niche") or "general"),
            target_audience=str(north.get("target_audience") or ""),
            current_followers=int(north.get("current_followers") or 0),
            target_followers=int(north.get("target_followers") or 0),
            count=target_n,
        )
        all_tasks = parsed.get("tasks", [])

    normalized = [_normalize(t) for t in all_tasks[:target_n]]
    return {
        "proposed_tasks": normalized,
        "cost": total_usage,
        "notes": [f"roadmap_generator: sized roadmap {len(normalized)}/{target_n} topics"],
    }


def _normalize(task: dict) -> dict:
    task.setdefault("parent_id", task.get("parentId"))
    task.setdefault("hashtags", [])
    task.setdefault("shot_list", task.get("shotList") or [])
    # Preserve depth from the LLM output so the tree layout is correct.
    task.setdefault("depth", task.get("depth", 0))
    # Content funnel — carry the LLM's funnel tagging through to the persister.
    task.setdefault("funnel_stage", task.get("funnelStage"))
    task.setdefault("cta_type", task.get("ctaType"))
    return task


def _salvage_tasks(raw: str) -> dict:
    """Recover individual task objects from malformed/truncated JSON.

    Gemini Flash routinely cuts off the outer `{...}` wrapper when its
    output runs into max_tokens. The individual `{"title":...}` blocks
    inside `tasks: [...]` are usually still valid. We scan for every
    balanced `{...}` chunk at ANY depth and json.loads it; anything that
    looks like a task draft (has `title`) is kept. Better to ship 12
    partial tasks than fail the whole run.
    """
    tasks: list[dict] = []
    n = len(raw)
    i = 0
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        # Try to find a balanced `{...}` starting at i
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
    return {"tasks": tasks, "summary": "(recovered from partial JSON)"}


async def _load_task_for_content_review(state: GrowthCoachState) -> dict:
    """Fetch the existing task + onboarding north-star so the graph can run
    scriptwriter on a single task without regenerating the whole roadmap."""
    tenant_id = state["tenant_id"]
    task_id = state.get("task_id")
    run_id = state["run_id"]

    if not task_id:
        log.warning("roadmap_generator.content_review_missing_task_id", run_id=run_id)
        return {
            "validation_errors": [{"node": "roadmap_generator", "error": "missing task_id"}],
        }

    sm = get_sessionmaker()
    async with sm() as session:
        task_row = await session.execute(
            text(
                """
                SELECT id, title, type, hook, "scriptMd", "shotList", hashtags,
                       "audioSuggestion", "driftScore", "followerTarget", "hookMeta",
                       "predictEvidence", "nicheTag"
                FROM content_tasks
                WHERE id = :task_id AND "tenantId" = :tenant_id
                """
            ),
            {"task_id": task_id, "tenant_id": tenant_id},
        )
        task = task_row.mappings().first()
        if task is None:
            log.warning("roadmap_generator.content_review_task_not_found",
                        run_id=run_id, task_id=task_id)
            return {
                "validation_errors": [
                    {"node": "roadmap_generator", "error": f"task not found: {task_id}"}
                ],
            }

        # Load onboarding so drift_detector and market_analyst have a north_star
        onb_row = await session.execute(
            text(
                """
                SELECT niche, "nicheDetail", "targetAudience", "currentFollowers", "targetFollowers",
                       "primaryGoal", "secondaryGoal", "goalWeight", "brandVoice", "psychProfile"
                FROM onboarding_profiles
                WHERE "tenantId" = :tenant_id
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        onb = onb_row.mappings().first()

        # Rescue path: when state.instructions is empty (e.g. user opened the
        # task via /generate-brief retry rather than the Q&A unlock flow, or
        # the original unlock dispatch failed and the task is being retried),
        # load the persisted Q&A transcript from task_interviews so the
        # scriptwriter still grounds the script in the user's real answers
        # instead of inventing a generic script. Without this, a single
        # failed dispatch wastes the Q&A the user already completed.
        interview_row = await session.execute(
            text(
                """
                SELECT messages FROM task_interviews
                WHERE "taskId" = :task_id
                ORDER BY "createdAt" DESC LIMIT 1
                """
            ),
            {"task_id": task_id},
        )
        interview = interview_row.mappings().first()

    north_star: dict = {}
    if onb:
        north_star = {
            "niche": onb.get("niche", ""),
            "niche_detail": onb.get("nicheDetail", ""),
            "target_audience": onb.get("targetAudience", ""),
            "current_followers": int(onb.get("currentFollowers") or 0),
            "target_followers": int(onb.get("targetFollowers") or 0),
            "region": "uz",
            # Goal taxonomy (Dizayn B) — so the content_review scriptwriter can
            # align hook/CTA/signal to the user's objective via goal_directive_uz.
            "primary_goal": onb.get("primaryGoal"),
            "secondary_goal": onb.get("secondaryGoal"),
            "goal_weight": float(onb.get("goalWeight") or 0.7),
            # Psych profile + brand voice (Dizayn A) — tone/energy/archetype the
            # scriptwriter matches. Null for tenants who never ran the interview.
            "brand_voice": onb.get("brandVoice"),
            "psych_profile": onb.get("psychProfile") if isinstance(onb.get("psychProfile"), dict) else None,
        }

    # Normalise DB column names → TaskDraft keys
    draft: dict = dict(task)
    draft["script_md"] = draft.pop("scriptMd", None)
    shots = draft.pop("shotList", None)
    draft["shot_list"] = shots if isinstance(shots, list) else []
    draft["audio_suggestion"] = draft.pop("audioSuggestion", None)
    draft["drift_score"] = draft.pop("driftScore", None)
    draft["follower_target"] = draft.pop("followerTarget", None)
    meta = draft.pop("hookMeta", None)
    draft["hook_meta"] = meta if isinstance(meta, dict) else {}
    pred = draft.pop("predictEvidence", None)
    draft["predict_evidence"] = pred if isinstance(pred, dict) else {}
    draft["niche_tag"] = draft.pop("nicheTag", None)

    log.info("roadmap_generator.content_review_loaded",
             run_id=run_id, task_id=task_id, title=draft.get("title"))

    # Build instructions from the saved Q&A transcript only when the caller
    # didn't pass any (the dispatcher already populated state.instructions
    # when /unlock-script provided them). Format mirrors regen-questions-
    # dialog's buildInstructions so the scriptwriter prompt sees the same
    # "S: ... / J: ..." shape regardless of which path delivered it.
    rescue: dict[str, str] = {}
    if not state.get("instructions") and interview is not None:
        messages = interview.get("messages")
        if isinstance(messages, list) and messages:
            lines: list[str] = []
            i = 0
            while i < len(messages) - 1:
                q = messages[i]
                a = messages[i + 1]
                if (
                    isinstance(q, dict) and isinstance(a, dict)
                    and q.get("role") == "assistant" and a.get("role") == "user"
                ):
                    lines.append(f"S: {q.get('content', '')}")
                    lines.append(f"J: {a.get('content', '')}")
                    i += 2
                else:
                    i += 1
            if lines:
                rescue["instructions"] = (
                    "Stsenariyni quyidagi HAQIQIY suhbat asosida yoz "
                    "(shaxsiy faktlarni o'ylab topma, faqat shu javoblardan foydalan):\n"
                    + "\n".join(lines)
                )
                log.info(
                    "roadmap_generator.content_review_rescued_interview",
                    run_id=run_id, task_id=task_id, turns=len(lines) // 2,
                )

    return {
        "proposed_tasks": [draft],
        "north_star": north_star,
        "notes": [f"roadmap_generator: content_review loaded task {task_id}"],
        **rescue,
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()

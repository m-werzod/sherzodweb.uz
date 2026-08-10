# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**SMM Coach** — an AI Instagram growth coach SaaS. A user signs up, connects Instagram, declares current state + goal, and the system generates a personalized staged roadmap of content tasks (a linear timeline punctuated by milestone "stations" at follower thresholds — `parentId` is always NULL today; a real branching tree is a future enhancement). Cooperating LangGraph agents (Market Analyst, Industry News, Scriptwriter, Account Tracker, plus Groq scorer and GPT-4o critic) run in a continuous "expected → execute → actual → compare → adjust" loop.

Around that core loop the product has grown three more surfaces, each documented below: an in-app **video/montage pipeline** (raw clip → rendered 9:16 reel, with a deep-link into the STUDIO editor), **official-Graph competitor + hashtag-trend intelligence** (scrape-free), and an **autonomous sales funnel** that turns buying-intent comments into drafted-reply `leads`.

Primary market: Uzbekistan (Uzbek-language UI, Payme for payments). Multi-language + global expansion deferred to v0.2+.

Detailed plan: [`reactive-mixing-manatee.md`](../../.claude/plans/reactive-mixing-manatee.md).

## Architecture

Two-service hybrid:

- **`apps/web`** — Next.js 15 (App Router, RSC, Server Actions), Auth.js v5, Prisma, shadcn/ui, Tailwind v4, React Flow (xyflow v12), TanStack Query, Zustand, next-intl. User-facing surface.
- **`apps/agents`** — Python 3.12, FastAPI, LangGraph + Postgres checkpointer, Langfuse tracing, structlog. Owns the agent loop and ALL LLM calls.

Shared:
- **`packages/db`** — Prisma schema + tenant-scoped client.
- **`packages/shared-types`** — Zod schemas (mirrored to Pydantic on the agents side; hand-mirror, don't auto-convert).

Web ↔ agents communication:
- Commands (web → agents): REST + HMAC (`AGENTS_HMAC_SECRET`, replay window 5 min) — see `apps/web/src/lib/agents/client.ts` ↔ `apps/agents/app/security/hmac.py`.
- Cron callbacks (agents → web): agents schedulers POST web `/api/cron/*` (`autoqueue`, `publish-due`, `refresh-insights`), guarded by `x-cron-secret` (`CRON_SECRET`) — the web side owns the per-account OAuth tokens the agents can't hold, so token-bound work (publishing, official insights) is triggered from agents but executed in web.
- Browser events: SSE → Next.js route → upstream FastAPI SSE → Redis pub/sub fan-out.
- Media plane: rendered montages live in MinIO (S3-compatible); agents write, web serves presigned URLs.

## Conventions

### Multi-tenancy
Every domain table has `tenantId`. **Never** call `prisma.<model>` directly from feature code — always `prismaForTenant(session.user.tenantId)`. The middleware injects `tenantId` into every where clause and create payload, and refuses cross-tenant queries. Raw `prisma` is only for auth, webhooks, admin scripts, and the cross-tenant `instagramUserId` lookup pattern (see below).

**Critical:** when adding a new model with a `tenantId` column, you MUST add its name to `TENANT_SCOPED_MODELS` in `packages/db/src/tenant.ts`. Forgetting this means `prismaForTenant` silently bypasses scoping for that model — a real bypass, not a theoretical one.

### Multiple unique constraints — find-first, then update-or-create
Tables with both a tenant-scoped unique key AND a global unique key (e.g. `InstagramAccount` has `(tenantId, handle)` AND `instagramUserId`) cannot be upserted via Prisma's `upsert` — it only matches one constraint. The pattern:

```ts
// Find by the GLOBAL unique first, then route based on result.
const existing = await prisma.instagramAccount.findUnique({
  where: { instagramUserId: profile.id },
});
if (existing && existing.tenantId !== currentTenant) {
  return errorBack(/* already_linked */);  // refuse cross-tenant steal
}
const ig = existing
  ? await db.instagramAccount.update({ where: { id: existing.id }, ... })
  : await db.instagramAccount.create({ ... });
```

The old `upsert(where: tenantId_handle)` shape silently failed with "Unique constraint failed on instagramUserId" when stale rows existed (e.g. from prior test runs).

### LangGraph — growth_coach chain
The `growth_coach` graph wires nodes in a specific order. Onboarding flow (`workflow=roadmap_generation`):

```
initial_analysis        Claude Sonnet     — account audit + pillars
  → roadmap_generator   Claude Sonnet     — 14-30 task outline, cadence-sized*
    → groq_scorer       Llama 3.3 70B     — score each task (viral / fit / clarity)
      → openai_critic   GPT-4o-mini       — what's MISSING, weakest 3
        → market_analyst + industry_news  — Gemini Flash, parallel fan-out
          → scriptwriter (TOPICS-ONLY)    pass-through; NO LLM call in onboarding
            → drift_detector              Voyage cosine — cosine < 0.18 → reject
              → output_validator          regex — flag ungrounded numeric claims
                → adversarial_critic      Gemini Flash — soft-quality second pass
                  → roadmap_persister     — write topics to DB, END
```
\* Roadmap size is cadence-driven, not fixed: smaller-follower / higher-cadence accounts get more tasks (0→1K ⇒ 20, 10K+ ⇒ 13).

Two name traps: `groq_scorer` and `account_tracker` route through `groq_client → fast_llm` (Cerebras → OpenRouter, Haiku fallback) — **not** Groq. `agent_catalog.py` is the single source of truth for every agent (model, when it runs, I/O, editable prompt) and backs the admin panel's `GET /v1/admin/agent-catalog`; consult it before assuming what an agent does.

Onboarding ships **bare topics** (title + goal). Rich scripts are written **lazily** per topic via the content-review flow after the user answers a Q&A interview — there is no bulk enrichment pass and no `task_enricher` node.

Content-review flow (`workflow=content_review`, fired by "open task" / "regenerate"):
```
roadmap_generator (load single task) → ... → scriptwriter (RICH mode, Opus 4.7,
  per-task call, max_tokens 2500)
  → hashtag_curator     Cerebras   — 10-12 tags (soha + umumiy + lokal)
  → hook_optimizer      Sonnet     — alt B-hook + A/B retention score
  → caption_translator  Cerebras   — ready IG caption (uz, 200-2200 chars)
  → drift → validator → adversarial_critic → persister.update_single
```
The enrichment trio (`hashtag_curator → hook_optimizer → caption_translator`) is gated by `_after_scriptwriter`: only `content_review` runs it (there's a real script to enrich). Onboarding (topics-only) skips straight to the guards.

Tracker-pulse flow (`workflow=tracker_pulse`, fired by `tracker_scheduler`):
```
... validator → adversarial_critic → account_tracker → performance_review → END
```
`performance_review` writes a `PerformanceReview` row; the dashboard's `PerformanceBanner` surfaces it and the user opts in to a replan. We deliberately never auto-regenerate.

Pulse / single-node flows (`_entry_router` at START gives each its own path, skipping the whole roadmap chain):
```
workflow=profile_audit_pulse    → profile_auditor   → END   (Sonnet; onboarding IG-link + weekly; writes instagram_accounts.profileAudit)
workflow=comment_sentinel_pulse → comment_sentinel  → END   (Cerebras; enqueued by the IG webhook / daily scheduler ~24h post-publish; writes instagram_posts.commentSentiment AND drafts `leads` via lead_detector — see "Autonomous sales funnel")
workflow=onboarding_post_audit  → post_analyzer     → END   (Gemini vision + Cerebras sentiment + Claude aggregation; deep per-post audit → instagram_posts.deepAnalysis)
workflow=montage_generation     → footage_analyzer → broll_curator → montage_director → caption_stylist → END   (see "Video / montage generation")
workflow=higgsfield_generation  → higgsfield_director → END   (scenario storyboard → per-shot Higgsfield DoP clips → assemble; gated ENABLE_HIGGSFIELD + HF creds)
workflow=runway_restyle         → runway_director     → END   (restyle the UPLOADED clip via Runway Aleph video_to_video; gated ENABLE_RUNWAY_RESTYLE + credits)
```
`competitor_intel` (Cerebras/fast-LLM) also runs INSIDE the main roadmap chain, right before `roadmap_generator`, on onboarding/replan only — it's gated out of `content_review` + `tracker_pulse` (`_SKIP_WORKFLOWS`). It folds tracked-competitor + niche-trend + hashtag signals into the analysis before the roadmap is shaped.

Important rules:
- `thread_id = "{tenant_id}:{user_id}:{workflow}"` — one durable thread per user per workflow.
- State reducers (`Annotated[..., operator.add]`) prevent races between parallel nodes. Keep that pattern when adding fields.
- `_MAX_REWRITES = 2` cap in `_after_validator` — without it Claude can loop the recursion limit when it can't satisfy the validator.
- Every concrete numeric/timing claim in a generated script must have `predict_evidence` or an `@evidence:` marker. The `output_validator` regex-matches loud claims like "100K followers in 2 weeks" and rejects them.
- `drift_detector` uses Voyage-3 embeddings, NOT an LLM call. Threshold `0.18`. **85% floor:** if more than 15% of proposed tasks would be cut, rescue the highest-scoring rejects — embeddings degrade to deterministic stubs on Voyage timeout, and a stub-misfire must never silently shrink the roadmap below the user's cadence-promised N.
- `dispatch_workflow` (`apps/agents/app/graphs/dispatcher.py`) short-circuits when called twice with the same `idempotency_key` — protects against double-clicks and retry storms.
- **Runs are durable (T7.1).** `dispatch_workflow` no longer fire-and-forgets an `asyncio.create_task(_run(...))`. It INSERTs the run as `queued` and returns `(run_id, thread_id)` immediately; the `run_worker` background loop claims it (`FOR UPDATE SKIP LOCKED` + a visibility-timeout lease) and drives the graph to completion, resuming from the LangGraph checkpoint after a crash/restart. `run_reaper` fails runs that blow past the attempt cap. So enabling agent runs in any environment now REQUIRES `RUN_WORKERS=1` on some process (see workers list) — without a running `run_worker`, dispatched runs sit `queued` forever.

### Video / montage generation (`workflow=montage_generation`)
Turns a user's raw uploaded clip into a rendered 9:16 reel. Two layers:

- **Agent layer** — four graph nodes emit JSON specs onto the user-upload `TaskMedia.meta` (they never touch ffmpeg): `footage_analyzer` (Gemini vision — shot detection, matches footage to the storyboard → `footageMap`), `broll_curator` (fast-LLM — Uz action → EN Pexels queries for shots the user's footage doesn't cover → `brollPlan`), `montage_director` (F6: Gemini vision WATCHES the uploaded footage → content-matched `effectIntents` (zoom/vfx/text_pop/typed transition/sfx) + `directorNotes` {music_hint, unwanted[]}; falls back to the text-only fast-LLM pass, then heuristics; `ENABLE_AUTO_INPAINT` feeds unwanted[0] into void-inpainting), `caption_stylist` (Sonnet — tier + accent color + emphasis words + hook overlay → `captionStyle`; creates the `kind='final_render'` pending row). Every node is **fail-soft** — it logs a note and never blocks downstream.
- **Compiler + media plane** — `apps/agents/app/montage/` (~30 modules) is a deterministic Python→ffmpeg compiler (`compiler.py`) with a 4-tier degrade ladder (L0 full montage → L3 normalized-clip fallback) so it always emits *something*. **Critical invariant: two timebases** — `edl.py` distinguishes SOURCE seconds (into the raw clip) from OUTPUT seconds (into the final render); all captions/motion/overlays anchor to OUTPUT-time after cuts collapse the timeline. The `montage_worker` (see workers) polls `final_render` rows and renders **cloud-first via Shotstack** (`montage/shotstack_map.py`: EDL→timeline — typed content-matched transitions, rich-caption karaoke subtitles from our SRT (any language), Soul visual cards, b-roll, ducked music; gated `ENABLE_SHOTSTACK`+key, ~$0.105/reel, per-render costUsd+renderEngine persisted); ANY cloud failure falls back to the local ffmpeg ladder (encode gate now lives INSIDE the compiler around the real encodes only). The MP4 mirrors to MinIO.
- **fal.ai GPU plane (opt-in via env; NOTE: prod currently runs them ON — GEN_BROLL/INPAINT/DECOR/VIDEO_TRANSLATE=true, real per-clip cost)** — generative B-roll (`ENABLE_GEN_BROLL` + `FAL_KEY`, kling video), object-removal inpaint (`ENABLE_INPAINT`, void-video-inpainting), scenario decor (`ENABLE_DECOR`, bria matte + FLUX bg). Absent keys ⇒ montage silently uses stock/Pexels. Models are env-tunable in `config.py` (`FAL_*_MODEL`).
- **`source_variants` / `lang_variants` are STUDIO-only by design — NOT server-composited (audited 2026-07-05).** The inpaint/decor `source_variant`s (fal.ai) and the HeyGen `lang_variant` dubs that `compiler.py` produces (`_maybe_add_inpaint_variant`/`_maybe_add_decor_background`/`_maybe_add_translate_variants`) are only **appended to the EDL**; neither render engine reads them — both the local ffmpeg ladder (`render_edl`) and Shotstack (`render_via_shotstack`) always render from the base `normalized` clip + base captions. The enhancement takes effect ONLY when the user opens STUDIO, whose client-side `pickSourceVariant`/`pickLangVariant` base-swaps the variant for a client re-export. This is **intentional** (STUDIO is the refine layer on top of an already-delivered base reel) — do NOT "fix" the missing read as a bug. Known **cost trade-off**: on the auto path a qualifying task (a meta remove instruction / `decor_prompt` / `translateLangs`, or director `unwanted[]` under `ENABLE_AUTO_INPAINT`) spends real fal.ai/HeyGen GPU credits to build a variant the delivered `montage.mp4` then drops. Bounded: nothing fires without an explicit per-task instruction; `VIDEO_TRANSLATE_LANGS` defaults empty (no dub unless a task sets it); `eye_contact`/`cleaned` are contract-only placeholders (never produced). If the spend matters, gate `ENABLE_INPAINT`/`ENABLE_DECOR`/`ENABLE_VIDEO_TRANSLATE` OFF; server-compositing the precedence-winning aligned variant into both engines' render source is the deferred enhancement.
- **STUDIO round-trip** — the web Production hub (`components/traj/production-studio.tsx`, `task-studio.tsx`, route `(dashboard)/production`) can deep-link into STUDIO (the separate browser video editor) via `apps/web/src/lib/studio/link.ts`: a short-lived HMAC token (TTL 8h) + presigned clip URL + AI-generated EDL. STUDIO pre-loads the AI draft, the user refines, and export POSTs `studio-save` which atomically swaps the `final_render` row. STUDIO is a **separate origin** — pure token auth, no shared session/cookies. This is the same EDL contract documented in the container-root `CLAUDE.md`.

### Autonomous sales funnel — leads (Stage 12)
`apps/agents/app/graphs/lead_detector.py` (fast-LLM, one JSON call, no DB) scans a published post's comments for **buying/sales intent** ("narxi qancha?", "qayerdan olsa bo'ladi?", "buyurtma", DM requests) and drafts a short on-voice Uzbek reply. It runs as a second pass inside `comment_sentinel` (different granularity than sentiment: a lead is a single actionable commenter, sentiment is aggregate mood). Results persist as `leads` rows; surfaced at web route `(dashboard)/leads` + `/api/leads`. Cross-account DMing is still gated behind Meta `manage_messages` (Faza 2) — today the coach can only reply on the owner's own account with confirmation.

### LLM call accounting (AI Inspector UI retired 2026-07-03 — errors now flow 100% to the Telegram log channel; `llm_calls` table remains for /agents + voice)
Every LLM call is captured in two places:
- `token_usage` (aggregate cost/token counts, used by budget guard)
- `llm_calls` (full system prompt + user message + raw response, used by the in-app AI Inspector drawer)

`apps/agents/app/runs/llm_inspector.py::record_llm_call` is fire-and-forget — invoked by every LLM client (`anthropic_client`, `groq_client`, `openai_client`, `gemini_client`, `fast_llm`). Reads `RunContext` from contextvars to attribute the call to `tenantId` + `runId` + `taskId`. **If you add a new LLM client, you must call `record_llm_call` at the end of every code path** (success, error, fallback) or the Inspector silently misses those calls.

The UI is `apps/web/src/components/traj/ai-inspector.tsx` — a floating bottom drawer rendered globally from `(dashboard)/layout.tsx`. Polls `/api/llm-calls?limit=50` every 10s while open.

### Runtime prompt overrides
Each agent's system prompt is a module-level constant. The admin panel can override any of them at runtime via the `prompt_overrides` table. Reads go through `apps/agents/app/graphs/prompt_store.py::resolve_prompt(key, default)` — TTL-cached (30s) so the hot path doesn't hit Postgres on every call. After an edit the web app should call agents' `/v1/admin/prompt-cache` to purge.

### Layout guard — universal roadmap-ready gate
`apps/web/src/app/[locale]/(dashboard)/layout.tsx` enforces:
- session orphan check: tenant row missing (orphan_cleanup deleted it) → `/sign-in?stale=1`
- `!onboardingDone` → redirect `/onboarding`
- `onboardingDone && !roadmapReady` → redirect `/onboarding/loading`
- exemption: `/admin` (platform admins can reach the panel without an active roadmap)

Onboarding pages live in a separate route group `(onboarding)`, so this layout never renders them — no path exemption needed for them. The middleware writes the request path into the `x-pathname` header so the layout can read it via `headers()` (Next.js doesn't expose URL natively in layouts).

The layout also mounts three global floaters: `<AIInspector />` (LLM call drawer), `<PerformanceBanner />` (pivot recommendation from `performance_review`), and `<FloatingVoiceCoach />` (persistent voice session across navigation).

When adding a new page under `(dashboard)/`, you DO NOT need to check onboarding state yourself — the layout handles it.

### Voice coach + Q&A interview + knowledge vault
Three connected flows let the coach gather the user's real story and reuse it across topics.

**Voice coach** (`apps/web/src/lib/voice/`, `apps/web/src/app/api/voice/*`):
- Global floating UI mounted from the dashboard layout (persists across navigation).
- LiveKit room (`/api/voice/token`) → STT (`/api/voice/stt`, ElevenLabs by default) → orchestrator (`/api/voice/respond`, GPT-4o) → TTS (`/api/voice/tts`).
- `voice/tools.ts` defines OpenAI function-calling tools. The coach mutates the user's own data AND can act on the user's OWN Instagram with explicit confirmation: `publish_post` (auto-publish/queue a finished reel), `reply_to_comment`, `generate_media`. These run on the owner's own role-holding account under Standard Access (the single-person MVP), so no App Review is needed for them. Still **prohibited**: following/DMing arbitrary accounts and any cross-account action (DM to leads is Stage-12 Faza 2, pending `manage_messages`).
- `write_script` is the hand-off tool: when the coach has collected enough context in conversation, it calls `write_script` which dispatches the agents' `content_review` workflow with the gathered brief.

**Q&A script interview** (`/api/tasks/[id]/script-interview` ↔ agents `/v1/script-interview`):
- One-question-at-a-time chat (Groq llama 3.3) BEFORE regenerating a script. `_MAX_QUESTIONS = 6` hard cap.
- Stateless per turn: the web holds the conversation and posts the full history each call.
- Full transcript persists to `TaskInterview` (upsert by `taskId`, so reopening resumes mid-chat instead of restarting).
- Completed transcript is fed to `scriptwriter` as `user_answers` — the script then quotes the user's real facts instead of fabricating them.

**Knowledge vault** (`apps/agents/app/memory/knowledge_vault.py`, `KnowledgeNote` table):
- Every completed interview is embedded and upserted by `sourceTaskId` (one note per topic).
- `scriptwriter` retrieves semantically-related notes per tenant before writing a NEW script — so the user's voice, repeated facts and personal details carry across topics. This is the "Obsidian vault" the product promises.
- Browseable at `/vault` (`apps/web/src/app/[locale]/(dashboard)/vault/page.tsx`).

### Webhook idempotency
Pattern: every webhook handler does `prisma.webhookEvent.create({ data: { provider, externalId, ... } })` first. The `UNIQUE(provider, externalId)` constraint throws P2002 on the second call — catch that and return `200 {dedup:true}` so the upstream stops retrying. See `apps/web/src/app/api/webhooks/heygen/route.ts` for the canonical example.

### Budget guard — 3-tier degrade + emergency stop
`apps/agents/app/budget/guard.py`:
- `TENANT_MONTHLY_BUDGET_USD` (default $20) → over → degrade premium model to Haiku
- `TENANT_DAILY_BUDGET_USD` (default $3) → same
- `GLOBAL_DAILY_BUDGET_USD` (default $15) → same
- `EMERGENCY_DISABLE_LLM=1` → kill switch (still degrades to Haiku; not a hard stop yet)

Degrade map lives in `DEGRADE_MAP` — Opus → Sonnet → Haiku. The Anthropic client publishes a `budget.exceeded` SSE event when it fires so the UI can show a banner.

### Instagram data
- **Meta Graph API** (primary, for OAuth'd users) — `apps/web/src/lib/instagram/graph-api-client.ts`. Token exchange + profile + media + insights. The OAuth callback handles the full link flow with the find-by-instagramUserId-first pattern.
- **instagrapi** (Python, private mobile API) — needs `IG_SCRAPER_ACCOUNTS` JSON in env. Optional — without it, instagrapi paths are skipped.
- **Playwright** (fallback, login-less scraping) — Reels Explore, hashtag pages. Stealth plugin + mobile UA + locale `uz-UZ`. IG aggressively blocks anonymous scraping from datacenter IPs.
- **JSON `web_profile_info` endpoint** — `_fetch_via_json_api` in `playwright_scraper.py` calls IG's internal JSON endpoint with the `X-IG-App-ID: 936619743392459` header. Faster + more reliable than HTML parsing when not rate-limited. Tried before Playwright HTML fallback.
- **Cross-tenant seeding** — `app/workers/knowledge_seeder.py` populates `shared_knowledge` **on demand** (triggered per-niche by `initial_analysis` on first encounter); Market Analyst reads from there (no per-user scraping). To pre-warm before launch, invoke the module directly as `__main__`.
- **Official Graph API for competitor + trend data (scrape-free, preferred)** — `apps/agents/app/integrations/instagram/graph_api.py` (v25.0, `GRAPH_BASE`) uses `business_discovery` (competitor followers + recent public posts; engagement = likes+comments, no views exposed) and the two-step Hashtag Search (`ig_hashtag_search` → `{id}/top_media`). All fail-soft (return `None`/`[]`, never raise) and cached cross-tenant in `shared_knowledge` (competitor_snapshot 14d TTL; hashtag_trend 7d TTL, one row per tag). Needs `IG_GRAPH_SERVICE_TOKEN` + `IG_GRAPH_SERVICE_USER_ID` (a Facebook-Login service account); quotas are tight (~200 business_discovery calls/hr, ~30 unique hashtags/7d) so workers dedup per handle/tag and pace with jitter.
- **Own-post metrics migrated off the scraper (commit `ebc61b2`)** — instagrapi is blocked from datacenter IPs, so `account_tracker` no longer relies on it. Instead the agents `insights_scheduler` (6h) POSTs the web `/api/cron/refresh-insights`, which fetches official reach/views/saves/shares/likes/comments via `fetchMediaInsights`+`fetchMediaCounts` (only the web holds per-account OAuth tokens) and writes `ContentTask.actualMetrics` (never clobbering with all-zero transient failures). `account_tracker` reads `actualMetrics` first and only falls back to scraper if empty. New schema: `ContentTask.instagramMediaId` (persisted at publish) + `ContentTask.actualMetrics`.

### OAuth error preservation
The Instagram OAuth callback's `errorBack(reqUrl, isLoggedIn, code, detail?)` helper:
- If user has a session → redirect to `/dashboard?ig_error=X&ig_detail=Y` (preserves session)
- If anonymous → redirect to `/sign-in?ig_error=X`

Original behaviour ALWAYS routed failures to `/sign-in` which felt like a forced logout. The dashboard banner renders `ig_detail` (Meta's raw error message) in a monospace box so the user sees the literal cause.

### LLM models — pick from `apps/agents/app/config.py`
| Role | Model | Provider | Notes |
|---|---|---|---|
| `initial_analysis` | `claude-sonnet-4-6` | Anthropic | account audit + pillars |
| `roadmap_generator` | `claude-sonnet-4-6` | Anthropic | 14-30 task outline, cadence-sized |
| `profile_auditor` | `claude-sonnet-4-6` | Anthropic | IG-profile audit checklist (onboarding + weekly pulse) |
| `groq_scorer` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`, Haiku fallback) | per-task quality score — **not Groq** despite the module name |
| `openai_critic` | `gpt-4o-mini` | OpenAI | what's MISSING, weakest 3 (mini = ~5x cheaper, plenty for a critique) |
| `market_analyst` | `gemini-2.5-flash` | Gemini | DB-only synthesis, 1M context |
| `industry_news` | `gemini-2.5-flash` | Gemini | web-grounded research |
| `market_synthesis` | `claude-sonnet-4-6` | Anthropic | weekly nuanced writing |
| `scriptwriter` (TOPICS) | — | — | onboarding pass-through, NO LLM call |
| `scriptwriter` (RICH) | `claude-opus-4-7` | Anthropic | content_review, max_tokens 2500 |
| `scriptwriter` revisions | `claude-sonnet-4-6` | Anthropic | cheap, after rejection |
| `hashtag_curator` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`) | content_review: 10-12 tags (soha + umumiy + lokal) |
| `hook_optimizer` | `claude-sonnet-4-6` | Anthropic | content_review: alt B-hook + A/B retention score |
| `caption_translator` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`) | content_review: ready IG caption (uz, 200-2200 chars) |
| `drift_detector` | `voyage-3` embeddings | Voyage | NOT an LLM call (config has Haiku constant for a future swap, unused today) |
| `output_validator` | regex only | — | NOT an LLM call (same caveat as drift) |
| `adversarial_critic` | `gemini-2.5-flash` | Gemini | soft-quality second pass; ~$0.02/task |
| `account_tracker` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`, Haiku fallback) | root-cause classifier per post — **not Groq** |
| `comment_sentinel` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`) | post-comment sentiment pulse (~24h post-publish) |
| `lead_detector` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`) | sales-intent comments → drafted reply; second pass inside `comment_sentinel` |
| `competitor_intel` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`) | pre-roadmap competitor/trend synthesis (onboarding+replan only) |
| `footage_analyzer` | `gemini-2.5-flash` | Gemini (vision, Files API HQ / inline) | montage: shot detection + storyboard match |
| `broll_curator` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`) | montage: Uz action → EN Pexels queries for uncovered shots |
| `montage_director` | `llama-3.3-70b` | Cerebras → OpenRouter (via `fast_llm`) | montage: text-matched effect intents (heuristic fallback) |
| `caption_stylist` | `claude-sonnet-4-6` | Anthropic (`model_scriptwriter_revise`) | montage: caption tier/color/emphasis + creates `final_render` row |
| `post_analyzer` | `gemini-2.5-flash` (+ Cerebras sentiment, Claude aggregation) | Gemini / Cerebras / Anthropic | `onboarding_post_audit`: per-post visual/hook/brand audit → `deepAnalysis` |
| `performance_review` | `claude-sonnet-4-6` | Anthropic | pivot recommendation; user-opt-in |
| `vault_seeder` | `claude-haiku-4-5` | Anthropic | niche-foundation vault seeding |
| `vision` | `gemini-2.5-flash` | Gemini | multimodal post audit |
| Fast (volume) | `gpt-oss-120b` (Cerebras) → `llama-3.3-70b` (OpenRouter) | Cerebras → OpenRouter fallback | `fast_llm.py`; high-volume scoring/enrichment |
| Embeddings | `voyage-3` | Voyage | **1024-dim** (native), drift + retrieval |

`groq_client.py` is a **legacy-named thin wrapper over `fast_llm`** (Cerebras → OpenRouter, Claude Haiku fallback) — it does not call Groq. The module + function names are kept only so the many call sites don't churn. Never sprinkle model IDs across the code — change them centrally in `config.py`. Use prompt caching (`prompt_cache={'system': True}`) wherever the system prompt is heavy and reused.

**Fast-LLM fallback chain:** `apps/agents/app/integrations/llm/fast_llm.py` picks Cerebras if `CEREBRAS_API_KEY` is set, else OpenRouter. Both speak OpenAI's chat-completions API. Callers should catch and fall back to Claude Haiku — `fast_chat()` raises on transport errors. The deployed Cerebras key serves `gpt-oss-120b` (Production) + `zai-glm-4.7` (Preview) — `llama-3.3-70b` **404s** on it, so `model_fast` defaults to `gpt-oss-120b`; set `CEREBRAS_MODEL` to match whatever the account actually has.

### Languages
- App: TypeScript (web), Python 3.12 (agents).
- UI default: Uzbek. Translation keys live in `apps/web/src/i18n/messages/`. Don't hard-code strings (use `useTranslations()` / `getTranslations()`).
- User comms: Uzbek by default. Reply in Uzbek unless asked otherwise.

### Payments
- MVP: Payme only. Phase 2: Click, Stripe.
- All providers go through `PaymentProvider` interface in `apps/web/src/lib/payments/provider.ts`.
- Payme amounts are in **tiyin** (1 UZS = 100 tiyin). Centralized in `lib/payments/payme/plans.ts`.

### Diagnostic endpoints
Session-required, useful when debugging:
- `GET /api/debug/instagram` — masked env vars + expected redirect URI + Meta dashboard checklist
- `POST /api/debug/reset-ig` — wipes current tenant's IG account + posts + onboarding profile (lets user re-OAuth from scratch)
- `POST /api/admin/wipe?confirm=YES_WIPE_EVERYTHING` — nukes ALL tenant data globally. Delete this route file after use.

### Style
- Don't write tests "just in case". Write tests for guard nodes (drift, validator), HMAC, payment webhook idempotency, and any subtle multi-tenancy logic.
- Don't add WHAT comments. Add WHY comments only when a constraint, workaround, or non-obvious decision would surprise the next reader.
- Don't add backwards-compat shims, dead-code keeping, or "just-in-case" abstractions.
- Prefer `Edit` over `Write` on existing files; never create new files when an existing one fits.

## Common operations

```powershell
# Boot local infra (Postgres + pgvector, Redis, Langfuse, Mailpit)
pnpm infra:up

# Generate Prisma client + apply migrations
pnpm db:generate
pnpm db:migrate                     # prisma migrate dev — creates a migration file you MUST commit (prod applies it via `migrate deploy`; see Deployment)
psql $env:DATABASE_URL -f packages/db/prisma/manual/001_pgvector_indexes.sql

# Run the WEB app (Next.js, :3000). NOTE: turbo/pnpm dev runs web ONLY —
# apps/agents is a uv-managed Python pkg, deliberately NOT in pnpm workspaces.
pnpm dev

# Run the AGENTS service (FastAPI, :8000) — SEPARATE terminal, from apps/agents.
# run.py wires a SelectorEventLoop so psycopg-async works on Windows; prefer it.
cd apps/agents; uv sync; uv run python run.py     # set AGENTS_RELOAD=1 for hot reload
# Background workers (tracker_scheduler, daily_snapshot, …) are opt-in: RUN_WORKERS=1

# Type-check / lint / test
pnpm typecheck
pnpm lint
pnpm test
cd apps/agents; uv run pytest; uv run mypy app/; uv run ruff check .

# Run a SINGLE test
cd apps/web; pnpm vitest run src/lib/security/crypto.test.ts        # one web file
cd apps/web; pnpm vitest run -t "rejects tampered ciphertext"       # web, by name
cd apps/agents; uv run pytest tests/test_hmac.py::test_sign_roundtrip   # one agents test
cd apps/agents; uv run pytest -k drift                              # agents, by expr
```

## Deployment

Coolify auto-deploys `web` and `agents` services on push to `main`. The web Dockerfile runs **`prisma migrate deploy`** at startup (`infra/docker/web.Dockerfile`) — **NOT** `db push`. So editing `schema.prisma` is NOT enough: you MUST also commit a matching migration in `packages/db/prisma/migrations/`, otherwise the deploy applies nothing and the new columns/tables are missing in prod (→ runtime `column does not exist` / `relation does not exist` errors). Generate one with `prisma migrate dev --name <x>` locally, or for additive changes without a shadow DB: `cd packages/db && ./node_modules/.bin/prisma migrate diff --from-schema-datamodel <old-schema> --to-schema-datamodel prisma/schema.prisma --script > prisma/migrations/<ts>_<name>/migration.sql`. Additive (ADD COLUMN / new table) is safe for live data; renaming/dropping needs care. After pushing, the app must be re-deployed for `migrate deploy` to run.

## Pitfalls

- Tailwind v4 uses `@import 'tailwindcss'` + `@theme {}` blocks; do NOT add a `tailwind.config.ts` — config now lives in CSS.
- **UI / responsive convention:** the shipped design system is `apps/web/src/app/trajectory.css` (semantic classes) + inline `style={{}}` across `components/traj/*` + `components/studio/*` — NOT Tailwind utility classes. `components/ui/*` (shadcn) is legacy, used only by `billing` + `not-found`. Do responsive with the existing **semantic-class + `@media`** pattern in trajectory.css (and `<MobileShell>` for nav); do NOT introduce a parallel Tailwind `sm:`/`md:` prefix system. A mobile baseline already exists (100dvh, 44px tap targets, the "Mobile polish pass" block). When a grid must collapse on phones, give it an explicit class + an `@media` rule — don't lean on the brittle `[style*="grid-template-columns"] !important` catch-all (a known fragility, slated to be replaced under visual QA — remediation plan T7.x).
- next-intl is configured for `localePrefix: 'as-needed'`; the default locale (`uz`) is **not** prefixed. Use `Link` from `@/i18n/routing`, not `next/link`, for locale-aware routes.
- The middleware excludes `/api/*` and sets `x-pathname` for the dashboard layout. If you add a new top-level route group, double-check it's not caught by the middleware.
- LangGraph's `PostgresSaver` uses its own connection pool. Don't try to share the SQLAlchemy session pool with it.
- Embedding columns are `Json?` (jsonb) in the ACTIVE/deployed schema today — read/write as JSON and rank with a Python cosine scan (`knowledge_vault`, `shared_knowledge.similar_exemplar_posts`). The `Unsupported("vector(1024)")` + HNSW (`packages/db/prisma/manual/001_pgvector_indexes.sql`, `<=>` cosine) path is NOT yet applied — deferred to the remediation plan T7.6; `schema.prisma.full` holds the future vector schema. (Earlier docs claiming pgvector is live were stale.)
- BigInt fields (`amountUzs`) require careful JSON serialization (Prisma returns `BigInt`, JSON.stringify throws). Wrap in `Number()` only when ≤ 2^53.
- `RunContext` (Python contextvars) must be set by the dispatcher BEFORE invoking the graph. If it's missing, `record_llm_call` and `record_token_usage` silently skip. The dispatcher (`apps/agents/app/graphs/dispatcher.py::dispatch_workflow`) handles this — don't bypass it.
- Windows + psycopg async: `apps/agents/app/main.py:17-18` installs `WindowsSelectorEventLoopPolicy` BEFORE any import. Don't reorder.
- Background workers are opt-in: set `RUN_WORKERS=1` (registration list in `apps/agents/app/main.py`). The full roster today (17 loops): `run_worker` (~2s poll — durable LangGraph run driver, **required or dispatched runs never execute**), `run_reaper` (~2m — fails runs past the attempt cap), `tracker_scheduler` (6h — `tracker_pulse`), `comment_sentinel_scheduler` (daily — sentiment + leads), `autoqueue_scheduler` (hourly → web `/api/cron/autoqueue`), `publish_scheduler` (60s → web `/api/cron/publish-due`), `insights_scheduler` (6h → web `/api/cron/refresh-insights`), `knowledge_refresher` (daily), `hashtag_trend_refresher` (daily — official Hashtag Search), `competitor_tracker` (12h — business_discovery), `daily_snapshot` (daily — FollowerSnapshot/DailyActivity), `forecast` (daily 02:00 Asia/Tashkent — Monte Carlo P10/P50/P90), `prediction_resolver` (daily), `ig_token_refresh` (daily), `orphan_cleanup` (6h), `coach_supervisor` (daily — one reminder/tenant, never auto-acts), `montage_worker` (~15s — ffmpeg render, CPU-bound). Each runs under `_supervise()` with capped exponential backoff (5s → 300s cap, resets to 5s after 120s healthy). **Plane split:** `WORKER_SET` selects which run here — `all` (default), `brain` (everything except `montage_worker`), or `media` (only `montage_worker`, so a render OOM can't take the API/schedulers down). Several schedulers are no-ops without their env (`WEB_URL`+`CRON_SECRET`, `IG_GRAPH_SERVICE_TOKEN`, …).

## Critical path before launch

1. **Meta App Review** submission for Advanced Access (`instagram_business_manage_insights`, `instagram_business_manage_comments`). 2-6 weeks. Submit on day 1 — every other feature can proceed in parallel, but launch can't.
2. **shared_knowledge seeding is on-demand** — `knowledge_seeder` is no longer a perpetual job. The first time a niche is seen during onboarding, `initial_analysis` triggers a one-shot seed for that niche. To pre-warm the top UZ niches before launch run `uv run python -m app.workers.knowledge_seeder` manually (the module's `__main__` does a one-pass seed of `SEED_NICHES_UZ`).
3. **2-3 throwaway IG scraper accounts** + residential proxy (Smartproxy / BrightData proxy-only plan, ~$10-20/mo). Configure via `IG_SCRAPER_ACCOUNTS` env JSON. Only needed if you want competitor tracking + cross-tenant seeding without OAuth.
4. **SMTP env vars** for welcome email (`EMAIL_SMTP_HOST` etc.). Defaults to Mailpit on `localhost:1025` — fine for dev, silent in production without Resend / SendGrid / Mailgun.
5. **LiveKit Cloud** keys (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`) for the global voice coach. Without them `/api/voice/token` returns 503 and the floating coach renders a "not configured" hint instead of joining a room.

## Memory system

See `C:\Users\Azizbek\.claude\projects\C--Users-Azizbek-github-project-smm\memory\MEMORY.md` for user/project memories carried between sessions.

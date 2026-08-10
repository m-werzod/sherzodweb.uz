# SMM Coach — Architecture

> Versiya: 0.0.1 (skaffold) · Yangilangan: 2026-05-21
> Maqsadi: Lokal testdan oldin har bir komponentning roli, holati va o'zaro aloqasi aniq tushunilishi uchun bir manba.

---

## 1. Mahsulot loopi (umumiy ko'rinish)

Foydalanuvchi → Instagram'ni ulaydi → "hozir 100K, maqsad 1M" deydi → tizim:

1. **Tahlil** — akkauntning hozirgi holatini (post style, audutoriya, kuchli/zaif tomonlar)
2. **Yo'l xaritasi** — 14-30 kontent vazifasidan iborat bosqichli yo'l xaritasi (chiziqli, bekatlar bilan; daraxt emas)
3. **Stsenariy + ko'rsatma** — har bir tugun uchun (hook, script, kadrlar, hashtag, Rive personaj)
4. **Foydalanuvchi yozadi va joylaydi** — Instagram URL'ini qaytaradi
5. **Kuzatuv** — Account Tracker metrikalarni o'qiydi, kutilgan vs haqiqiy farqini hisoblaydi
6. **Qayta tuzish** — keyingi shoxni shu ma'lumotga qarab generatsiya qiladi

Loop **uzluksiz** (every 6h tracker pulse) va **drift-rezistentli** (north-star embedding bo'yicha cosine tekshiruvi).

---

## 2. Servis topologiyasi

```
┌────────────────────────────────┐    HMAC REST     ┌────────────────────────┐
│   apps/web  (Next.js 15)        │ ───────────────▶ │   apps/agents          │
│                                │                  │   (FastAPI + LangGraph) │
│   Auth.js · Prisma · React Flow │ ◀─── SSE ─────── │   PostgresSaver        │
│   shadcn · next-intl · TanStack │                  │   Workers (in-proc)     │
└──────────┬─────────────────────┘                  └──────────┬─────────────┘
           │                                                    │
           ▼                                                    ▼
    ┌────────────────────────────────────────────────────────────────┐
    │  PostgreSQL 16 + pgvector              Redis 7                  │
    │  - Prisma migrations                   - SSE pub/sub             │
    │  - LangGraph checkpoint schema         - Idempotency keys        │
    │  - agent_memory, shared_knowledge      - Streams (planned)       │
    └────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
              R2 (media)   ·   Mailpit/SMTP   ·   Langfuse
```

**Web** — foydalanuvchiga ko'rinadigan hamma narsa: marketing, auth, billing, dashboard, roadmap (bosqichli yo'l xaritasi), onboarding.

**Agents** — LangGraph orkestratsiyasi, LLM chaqiruvlari, Instagram ma'lumotlari, embedding hisoblash, davriy worker'lar.

Ikkala servis bir xil Postgres'ga yoziladi. LangGraph alohida `langgraph_checkpoints` schema yaratadi.

---

## 3. Agent xaritasi (kim nima qiladi)

`apps/agents/app/graphs/growth_coach.py` LangGraph quyidagi node'lardan iborat:

| Node | Vazifasi | Model | Qachon ishlaydi | Holati |
|---|---|---|---|---|
| `initial_analysis` | IG profilini olib, kuchli/zaif tomon JSON'ini chiqarish | Sonnet 4.6 | Birinchi onboarding | ✅ skaffold |
| `roadmap_generator` | 14-30 tugunli bosqichli yo'l xaritasi JSON'i (chiziqli) | Opus 4.7 | initial_analysis'dan keyin | ✅ skaffold |
| `market_analyst` | Region trending hooks/audio/format (shared_knowledge'dan) | Gemini 2.5 Flash | Roadmap + replan vaqtida | ✅ skaffold |
| `industry_news` | Niche yangiliklari (shared_knowledge'dan) | Sonnet 4.6 | Roadmap + replan vaqtida | ✅ skaffold |
| `scriptwriter` | Har bir draftni mukammal script'ga aylantirish + predict_evidence | Opus 4.7 → Sonnet 4.6 | Drafts kelganda | ✅ skaffold |
| `drift_detector` | Cosine < 0.45 bo'lsa task'ni rad etish | Haiku 4.5 (embeddings via Voyage) | scriptwriter'dan keyin | ✅ implementatsiya |
| `output_validator` | Dalilsiz raqamli da'volarni blok qilish (regex + evidence) | (kod, LLM emas) | drift'dan keyin | ✅ implementatsiya |
| `account_tracker` | Postlar metrikasini yangilash | Haiku 4.5 + Gemini Flash (vision) | Har 6 soatda, post-publish'da | ✅ skaffold |
| `performance_review` | Kutilgan vs haqiqiy farqi, replan signali | (kod) | Tracker'dan keyin | ✅ skaffold |

**Cooperatsiya pattern:** market_analyst va industry_news parallel ishlaydi → scriptwriter ikkala signal'ni o'qiydi → drift_detector → output_validator → HITL (user video yozadi). Holatlar `Annotated[..., operator.add]` reducer bilan birlashadi — race yo'q.

---

## 4. LangGraph state

`apps/agents/app/graphs/state.py`'da yagona `GrowthCoachState` TypedDict. Muhim maydonlar:

- **Identity**: tenant_id, user_id, workflow, run_id
- **Inputs**: north_star (niche, audience, goal, embedding), onboarding
- **Signal pools** (reducer = `operator.add`): market_signals, industry_signals, tracker_observations
- **Task lifecycle** (reducer = `operator.add`): proposed_tasks → approved_tasks → rejected_tasks
- **Guards**: drift_warnings, validation_errors
- **Bookkeeping**: cost (custom reducer summlaydigan), notes

Har bir node `dict` qaytaradi — LangGraph reducer'lar avtomatik birlashtiradi.

**Persistence:** `AsyncPostgresSaver` har step'dan keyin snapshot oladi. `thread_id = "{tenant_id}:{user_id}:{workflow}"`. Foydalanuvchi 3 kun keyin qaytsa, ish o'sha joydan davom etadi.

---

## 5. Instagram ma'lumotlar qatlami

Dispatcher (`app/integrations/instagram/dispatcher.py`) quyidagi tartibni qo'llaydi:

```
fetch_account_snapshot(handle, oauth_token=?):
   if oauth_token → graph_api.fetch_self_snapshot()    # rasmiy yo'l
                  except → instagrapi.fetch_profile()  # fallback
   else          → instagrapi.fetch_profile()           # MVP yo'li
```

**instagrapi** (`instagrapi_client.py`):
- 2-3 throwaway akkaunt orqali (session_pool.py round-robin)
- Tenacity retry: `feedback_required` / `challenge_required` → 30s-10min exponential
- Sessionlar `.smm-sessions/*.json`'da kesh — qayta login'dan saqlanish

**Playwright** (`playwright_scraper.py`):
- Faqat instagrapi yetib bormagan joylar: Reels Explore, hashtag pages (login'siz)
- `playwright-stealth` plugin, mobil viewport, `uz-UZ` locale, Tashkent timezone
- Brauzer global — har request'da yangi launch qilmaydi

**Meta Graph API** (`graph_api.py`):
- Advanced Access olgandan keyin (App Review 2-6 hafta)
- Faqat OAuth qilgan user'ning O'Z ma'lumoti uchun
- Metrika nomlari 2025-04 da migrated (`media_views`, `media_viewers`)

**Cross-tenant seeding:** `knowledge_seeder.py` 4 soatda bir marta 20 ta niche uchun hashtag top postlarini + Reels Explore'ni `shared_knowledge` jadvaliga yozadi. Bu — Market Analyst'ning yagona o'qish manbai (user'lararo umumiy resurs).

---

## 6. Memory qatlami

3 ta xotira darajasi, bittasi Postgres:

| Daraja | Joy | Mazmuni | Kim yozadi | Kim o'qiydi |
|---|---|---|---|---|
| Short-term | LangGraph checkpoint (Postgres) | Run state (scratchpad) | Har node | Keyingi node |
| Long-term per-tenant | `knowledge_notes` (jsonb embeddings, voyage-3 1024-dim; pgvector kelajakda) | Q&A vault — user ovozi, takror faktlar | `knowledge_vault.save_note()` | `knowledge_vault.related_notes()` (scriptwriter) |
| Cross-tenant shared | `shared_knowledge` (jsonb embeddings, 1024-dim; pgvector kelajakda) | Trending hooks/audio/news, exemplar posts | `knowledge_seeder` | Market Analyst, Industry News, scriptwriter (exemplars) |

**Multi-tenant izolatsiya:** `agent_memory` da `tenantId` filter har query'da. Cross-tenant **shared_knowledge** intentional umumiy — niche/region bo'yicha filter.

**Embeddings:** Voyage `voyage-3`, 1024 o'lcham (smoke test'da tasdiqlangan), cosine distance, HNSW index manual SQL'da (`packages/db/prisma/manual/001_pgvector_indexes.sql`).

---

## 7. Run lifecycle (POST'dan publish'gacha)

```
1. Web Server Action  →  POST /api/onboarding (web)
2.   prismaForTenant().instagramAccount.upsert + onboardingProfile.upsert
3.   invokeWorkflow({tenantId, workflow:'roadmap_generation', input})
        ⇒ HMAC SHA256(ts.body) → POST agents:/v1/runs
4. Agents:  api/runs.py  →  dispatcher.dispatch_workflow()
5.   create_run(agent_runs row, status='queued')
6.   asyncio.create_task(_run)
7.   _run:
        set RunContext (contextvar) → propagated to all LLM calls
        publish('run.started') → Redis pub/sub
        mark_running()
        graph.ainvoke(state, thread_id):
            initial_analysis → roadmap_generator → [market_analyst, industry_news] → scriptwriter
                  → drift_detector → output_validator
            (each LLM call writes a token_usage row with tenant_id, run_id, agent, model, cost)
        publish('run.completed', output, cost)
        mark_completed(output, cost)
8. Browser (EventSource /api/agents/sse/{userId}):
        web SSE proxy → agents SSE → Redis pubsub → browser
        Events: run.started, agent.thinking, drift.warning, run.completed, etc.
```

**Idempotency:** Agar `idempotencyKey` keladigan bo'lsa, run_id uni qo'llaydi. (Hozir create_run ON CONFLICT DO NOTHING — keyin chaqirilsa eski run qaytadi.) **TODO**: dispatcher'da pre-check qo'shish — agar mavjud bo'lsa, yangi task ochmasdan eski runni qaytarish.

---

## 8. Realtime layer

SSE zanjiri:

```
Agent node  →  bus.publish(user_id, event)  →  Redis PUBSUB user:{id}:agent-events
                                                  ↓
                                  Agents:/v1/streams/{user_id}  (HMAC-protected SSE)
                                                  ↓
                                  Web:/api/agents/sse/{user_id}  (server-side proxy)
                                                  ↓
                                  Browser EventSource → useAgentEvents hook
```

15 soniyada bir marta `{"type":"ping"}` yuboriladi — proxy'lar idle SSE'ni uzmasin.

Event'lar Zod schema'da (`packages/shared-types/src/agents.ts`) — discriminated union, brauzer side type-safe.

---

## 9. Cost va budget

**Tracking** (har LLM chaqiruvida):
- `record_token_usage()` — token_usage jadvaliga row yoziladi: tenant, run, agent, model, in/out/cached tokens, cost
- `agent_runs.costUsd` — run yakunida total cost (mark_completed'da yangilanadi)

**Budget enforcement** (TODO):
- `tenant_monthly_budget_usd` (default $50) `config.py`'da
- LLM client har chaqiruvdan oldin `monthly_cost_for_tenant()` o'qishi va cap oshsa Haiku'ga degrade qilishi kerak
- `budget.exceeded` event yuborilishi kerak

**Narx jadvali** — `pricing.py`'da markazlashtirilgan. Sotuvchi narxni o'zgartirsa shu yerda. Hozirgi taxmin: ~$14/user/oy 100 user × 5 task'da.

---

## 10. Multi-tenancy

| Tabaqa | Mexanizm |
|---|---|
| Web → Prisma | `prismaForTenant(session.user.tenantId)` $extends middleware — `tenantId` har query/insert'ga avtomatik |
| Cross-tenant guard | Agar `where.tenantId` boshqa qiymat bilan kelsa — exception |
| Agents → SQL | Raw SQL'da har query'da `WHERE "tenantId" = :tenant_id` mavjud |
| LangGraph thread | `thread_id` boshlanishi `tenant_id:` — bir user boshqa thread'ga kira olmaydi |
| Cost ledger | `token_usage."tenantId"` indekslangan — per-tenant aggregatsiya $50/oy cap uchun |

Postgres RLS — defense-in-depth. B2B paying user kelganda yoqamiz.

---

## 11. Xavfsizlik

- **HMAC** (web ↔ agents): SHA256(ts.body), 5 daq replay window. Test bilan qoplangan.
- **OAuth tokenlar at-rest**: schema'da `oauthAccessTokenEnc` / `oauthRefreshTokenEnc` Text. **TODO**: AES-256-GCM encryptor (key HKDF from `AUTH_SECRET`).
- **Scraper akkauntlar**: foydalanuvchining personal IG'idan ALOHIDA. `.smm-sessions/` `gitignore`'da.
- **Webhooks**: Payme JSON-RPC Basic auth + secret tekshiruvi. Instagram webhook X-Hub-Signature-256 verifikatsiya.
- **Secrets**: `.env` gitignored. Production'da Coolify secret store'ga.

---

## 12. Observability

- **Sentry** — error tracking, frontend + backend
- **Langfuse** (self-hosted) — har LLM call uchun trace; agent loop debugging
- **structlog** — JSON log, key-value contextvars
- **OpenTelemetry** — distributed tracing web → agents (planned)
- **token_usage + agent_runs jadvallari** — admin dashboarddan o'qiladi

---

## 13. Operatsiya

### Boot tartibi (lokal)
```
1. docker compose up -d (postgres+pgvector, redis, langfuse, mailpit)
2. pnpm db:generate && pnpm db:migrate
3. psql -f packages/db/prisma/manual/001_pgvector_indexes.sql
4. uv run playwright install chromium
5. pnpm dev (web on :3000, agents on :8000)
6. Optional: RUN_WORKERS=1 uv run uvicorn app.main:app  (tracker_scheduler + knowledge_seeder)
```

### Worker'lar
- `tracker_scheduler.py` — har 6 soatda barcha tenant'lar uchun `tracker_pulse` workflow'ni dispatch qiladi
- `knowledge_seeder.py` — har 4 soatda Reels Explore + 20 niche hashtag top postlarini scrape qiladi, `shared_knowledge`'ga yozadi
- `virale_refresher.py` — har 12 soatda (kuniga 2 marta) Virale gridlarini (per-tenant niche + shared region) qayta hisoblab Redis keshiga yozadi; sahifa ochilishi Redis GET, jonli scrape emas

Boshlash: `RUN_WORKERS=1` env. Dev'da odatda 1 proces, prod'da alohida Coolify scheduled service.

### Deploy (kelajak)
Coolify Frankfurt:
- `web-host` (4-8 vCPU, 16GB) — web + Postgres + Redis
- `agents-host` (8 vCPU, 32GB) — FastAPI + workers
- Backup: Contabo S3, daily pg_dump

---

## 14. Holatlar — bajarilgan vs qoldirilgan

### ✅ Bajarilgan (skaffold + integratsiya)
- Monorepo (pnpm + Turborepo + uv)
- Prisma schema v0 (12 model, multi-tenant, pgvector)
- LangGraph 9 node, persistence, parallel branches
- 4 cooperating agents + 2 guards + 2 orchestratorlar (skaffold)
- Instagrapi pool, Playwright stealth, Graph API stubs
- Knowledge seeder (Reels Explore + 20 niche)
- Tracker scheduler
- HMAC inter-service security
- AgentRun + TokenUsage persistence
- Retry/timeout on LLM clients
- SSE realtime: agent → Redis → SSE proxy → browser
- Payme provider stub + plans
- next-intl (uz/ru/en messages)
- Auth.js v5 + Credentials + Google
- shadcn UI primitivlari (faqat billing + not-found ishlatadi; asosiy UI custom CSS/Trajectory dizayn)
- Onboarding wizard form
- Roadmap — chiziqli bosqichli yo'l xaritasi (bekatlar bilan; React Flow EMAS — daraxt-kanvas T7.4 long-term)
- 4 API keys smoke-tested OK
- **Idempotency pre-check** — `dispatcher.dispatch_workflow` `idempotency_key` bilan mavjud `agent_runs`'ni avval o'qiydi
- **Budget enforcement** — `app/budget/guard.py`, 60s TTL cache, premium → Haiku/Flash degrade, SSE `budget.exceeded` event
- **OAuth token encryption** — `app/security/crypto.py` ↔ `apps/web/src/lib/security/crypto.ts` AES-256-GCM, byte-compatible, tests qoplangan

### ⏳ Qoldirilgan (kerakli)
- **Token revoke/refresh** — Instagram OAuth callback'ga yozish + 7 kunda bir yangilash ✅ (Python worker'da implementatsiya qilindi)
- **Test DB fixture** — repository.py va dispatcher uchun integration test
- **Production seed** — ilk admin user + Postgres RLS policy
- **End-to-end test** — fake user → onboarding → mock LLM → roadmap → DB tekshirish

### 🔜 Faza 2 (kelajak)
- Auto-publish (Meta App Review tasdiqlangach)
- Auto-comment-reply
- Auto-video-editing AI agent
- HeyGen avatar premium
- B2B/teams/seats, RBAC
- Click + Stripe payments
- RU/EN locales

---

## 15. Risk reyestri

1. **Meta App Review kechikishi (kritik yo'l)** — submit day 1, `bio_code` fallback ishlaydi
2. **Instagram ToS — scraping bani** — throwaway akkauntlar, residential proxy ($10-20/oy), instagrapi `feedback_required` retry, low volume
3. **LLM cost runaway** — budget cap + Haiku fallback (✅ done), prompt cache 90% tejash
4. **Hallucinated growth advice** — output_validator har raqamli da'voga `@evidence:` shart qiladi
5. **Roadmap drift** — drift_detector cosine < 0.45 → blok
6. **4-agent debugging nightmare** — Langfuse trace day 1, har node uchun unit test
7. **Cold-start** — knowledge_seeder ilk run, 20 niche × ~20 post = 400 row

---

## 16. Lokal test qilish (qisqa qo'llanma)

```powershell
# 1. Tool'lar
corepack enable; corepack prepare pnpm@9.15.0 --activate
winget install astral-sh.uv
# Docker Desktop yuklab oling

# 2. Dependencies
pnpm install
cd apps\agents; uv sync; uv run playwright install chromium; cd ..\..

# 3. Infra + DB
pnpm infra:up
pnpm db:generate
pnpm db:migrate
psql "$env:DATABASE_URL" -f packages\db\prisma\manual\001_pgvector_indexes.sql

# 4. Smoke test API keys
python apps\agents\scripts\smoke_test_apis.py

# 5. Run
pnpm dev

# 6. Tezkor end-to-end (browser):
#    http://localhost:3000 → sign-up → onboarding wizard
#    Agentlar log'i terminalda → "[stub response — set ANTHROPIC_API_KEY]" yo'q
#    Real LLM javobi kelsa → roadmap_generation thread Langfuse'da http://localhost:3001
```

Agar shu 6 qadam o'tib **agent_runs** jadvalida bitta `completed` status'idagi qator paydo bo'lsa — arxitektura ishlaydi, UI'ga o'tsa bo'ladi.

---

Bu hujjat **manba haqiqati**. Yangi node yoki integratsiya qo'shilsa, shu yerni yangilang.

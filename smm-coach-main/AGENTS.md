# SMM Coach — Agent Guide

> AI Instagram Growth Coach SaaS. Read this first before making any changes.

## Project Overview

**SMM Coach** is an AI-powered Instagram growth coaching platform. Users sign up, connect their Instagram account, declare their current state and goal, and the system generates a personalized tree-shaped roadmap of content tasks. Multiple cooperating LangGraph agents (Market Analyst, Industry News, Scriptwriter, Account Tracker, Drift Detector, Output Validator) run in a continuous "expected → execute → actual → compare → adjust" loop.

Primary market: **Uzbekistan** (Uzbek-language UI default, Payme for payments, timezone `Asia/Tashkent`). Multi-language and global expansion are deferred to v0.2+.

The repository is a **hybrid monorepo**: TypeScript/Next.js for the user-facing web app, Python/FastAPI/LangGraph for the AI agent orchestration backend.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Monorepo** | pnpm 9.15.0 workspaces + Turborepo 2.3.3 |
| **Node.js** | >=22.0.0 (`.nvmrc` provided) |
| **Python** | >=3.12 (managed by `uv`, not pnpm) |

### `apps/web` — User-Facing Next.js App
- **Framework:** Next.js 15.1.3 (App Router, RSC, Server Actions, `output: 'standalone'`)
- **Language:** TypeScript 5.7.2 with strict config (`noUncheckedIndexedAccess`, `noImplicitOverride`)
- **Styling:** Tailwind CSS v4.0.0-beta.8 (CSS-based config, no `tailwind.config.ts`), PostCSS, autoprefixer
- **UI:** shadcn/ui base (`components.json` present), Radix UI primitives, Framer Motion, Lucide icons, Rive animations
- **Auth:** Auth.js v5 (next-auth 5.0.0-beta.25) with Prisma adapter — Credentials + Google OAuth, JWT session strategy
- **Data:** Prisma 6.1.0 via `@smm/db` workspace package, TanStack React Query v5
- **State:** Zustand v5
- **Internationalization:** next-intl v3 (Uzbek default `uz`, `localePrefix: 'as-needed'`, timezone `Asia/Tashkent`)
- **Visualization:** React Flow (xyflow v12) + dagre for roadmap tree layout
- **Forms:** React Hook Form + Zod resolvers
- **Queue:** BullMQ + ioredis for background jobs
- **Observability:** Sentry Next.js SDK, PostHog
- **Testing:** Vitest v2 + happy-dom + Testing Library React
- **Fonts:** Geist

### `apps/agents` — AI Agent Orchestration Service (Python)
- **Framework:** FastAPI 0.115+ with Uvicorn, Pydantic v2, pydantic-settings
- **Agent Framework:** LangGraph 0.2.60+ with `langgraph-checkpoint-postgres` for persistence
- **LLM SDKs:** langchain-anthropic, langchain-google-genai, anthropic, google-genai
- **Database:** asyncpg, psycopg[binary,pool], SQLAlchemy[asyncio], pgvector
- **Cache:** redis[hiredis]
- **Scraping:** instagrapi (primary), Playwright + playwright-stealth + fake-useragent (fallback)
- **Observability:** Langfuse, structlog (JSON), Sentry SDK, OpenTelemetry API/SDK
- **Security:** cryptography (AES-256-GCM), custom HMAC middleware
- **Testing:** pytest, pytest-asyncio, pytest-cov, respx
- **Linting:** ruff (line length 100, py312 target, rules E/F/I/B/UP/ASYNC/S/RET/SIM/TCH), mypy (strict, pydantic plugin)

### `packages/db` — Shared Database Layer
- Prisma 6.1.0 with PostgreSQL generator output to `../generated/client`
- Preview feature: `postgresqlExtensions`
- Client singleton with global hot-reload in dev (`globalThis.__smmPrisma`)
- Tenant-scoped client extension (`prismaForTenant`) injects `tenantId` into all queries

### `packages/shared-types` — Cross-Language Contracts
- Zod schemas only (mirrored manually to Pydantic on the agents side)
- Exports: `common`, `onboarding`, `instagram`, `roadmap`, `agents`, `payments`

### `front/` — Static Design Prototype
- **Not part of the build.** A high-fidelity static HTML/CSS/JSX prototype built with React 18 (CDN) and Babel Standalone for in-browser transpilation.
- Contains `.html` pages (Landing, Login, Signup, Trajectory) and `.jsx` components (dashboard, roadmap, task, settings, agents, etc.)
- Serves as visual specification, clickable demo, and content reference (all UI copy in Uzbek).
- The real production app is `apps/web`.

---

## Project Structure

```
smm/
├── apps/
│   ├── web/                  # Next.js 15 — user-facing dashboard, auth, billing, onboarding
│   │   ├── src/app/          # App Router ([locale] prefix for i18n)
│   │   │   ├── [locale]/(auth)/      # sign-in, sign-up pages
│   │   │   ├── [locale]/(dashboard)/ # dashboard, roadmap, task, settings, trajectory
│   │   │   ├── [locale]/(marketing)/ # landing page
│   │   │   └── api/          # REST API routes (see list below)
│   │   ├── src/lib/          # Feature modules: agents, auth, dashboard, email, instagram,
│   │   │                     # media, onboarding, payments, roadmap, security, settings,
│   │   │                     # storage, task, transcribe, video, voice, avatar
│   │   ├── src/components/   # React components: ui (shadcn), auth, dashboard, roadmap-tree,
│   │   │                     # onboarding, agent-feed, brand, traj
│   │   ├── src/hooks/        # Custom React hooks
│   │   └── src/i18n/         # Uzbek/Russian/English messages + routing config
│   └── agents/               # FastAPI + LangGraph — NOT a pnpm workspace (uv-managed)
│       ├── app/
│       │   ├── api/          # health, runs, scrape, sse, admin, questions routers
│       │   ├── graphs/       # LangGraph: growth_coach.py, state.py, nodes/*, dispatcher.py
│       │   │   └── nodes/    # account_tracker, drift_detector, industry_news,
│       │   │                 # initial_analysis, market_analyst, output_validator,
│       │   │                 # performance_review, roadmap_generator, roadmap_persister,
│       │   │                 # scriptwriter, task_enricher, groq_scorer, openai_critic
│       │   ├── integrations/instagram/  # instagrapi, Playwright, Graph API, dispatcher, session_pool
│       │   ├── integrations/llm/        # anthropic, gemini, groq, openai clients + embeddings + pricing
│       │   ├── memory/       # vector store, shared knowledge, db adapters
│       │   ├── security/     # HMAC, crypto (AES-256-GCM)
│       │   ├── streams/      # Redis pub/sub SSE bus
│       │   ├── workers/      # tracker_scheduler, knowledge_seeder, daily_snapshot,
│       │   │                 # forecast, competitor_tracker, prediction_resolver,
│       │   │                 # ig_token_refresh, orphan_cleanup
│       │   ├── budget/       # LLM spend guard
│       │   ├── runs/         # run context, repository, LLM inspector
│       │   ├── telemetry/    # OpenTelemetry + Sentry setup
│       │   ├── config.py     # Centralized settings + model routing
│       │   └── main.py       # FastAPI entrypoint with lifespan workers
│       ├── tests/            # pytest suite
│       └── pyproject.toml
├── packages/
│   ├── db/                   # Prisma schema + tenant-scoped client
│   │   ├── prisma/schema.prisma
│   │   ├── prisma/manual/001_pgvector_indexes.sql
│   │   └── src/client.ts, tenant.ts, index.ts
│   └── shared-types/         # Zod schemas for cross-service contracts
├── infra/
│   ├── docker/
│   │   ├── web.Dockerfile    # Multi-stage Node 22 Alpine, standalone output, non-root smm user
│   │   └── agents.Dockerfile # Playwright Python base, uv, non-root pwuser, 2 uvicorn workers
│   ├── coolify/README.md     # Deployment guide for coolify.brotech.uz
│   ├── postgres/init.sql     # Dev init: creates pgvector, pgcrypto, pg_trgm extensions
│   └── docker-compose.dev.yml # Local dev: Postgres 16 + pgvector, Redis 7, Langfuse, Mailpit
├── front/                    # Static HTML/JSX prototypes (not part of build)
├── docker-compose.yaml       # Production Coolify compose (root-level): Postgres 17 + pgvector,
│                             # Redis 7, MinIO, web, agents + minio-bootstrap
└── Root configs: package.json, turbo.json, tsconfig.base.json, .prettierrc.json, etc.
```

**Important:** `apps/agents` is managed by `uv` (Python), not pnpm. `pnpm-workspace.yaml` explicitly notes it is excluded from Node workspaces.

---

## Database

**PostgreSQL 16+ with pgvector extension.** Every domain table has `tenantId` for multi-tenancy.

Key models:
- `Tenant` — B2C personal tenants now, B2B teams later. Has `monthlyBudgetUsd` override.
- `User` — linked to Tenant, has `role` (owner/admin/member/viewer), `locale`, `suspendedAt`
- `InstagramAccount` — handle, encrypted OAuth tokens, cached profile stats, profile audit JSON
- `OnboardingProfile` — niche, audience, goals, north-star embedding, posting cadence
- `Roadmap` + `ContentTask` — tree structure (parent/self-relation), task status lifecycle, script variants A/B, embeddings, format, publish window
- `AgentRun` + `TokenUsage` + `LLMCall` — cost tracking and full prompt/response audit per tenant, per run, per agent
- `AgentMemory` — pgvector-enabled long-term memory per tenant
- `SharedKnowledge` — cross-tenant trending hooks, audio, news, exemplar posts
- `Subscription` + `PaymentEvent` — Payme/Click/Stripe multi-provider
- `WebhookEvent` — global idempotency log for inbound webhooks (not tenant-scoped)
- `ScriptHistory` — per-task script version rollback timeline
- `TaskMedia` — generated media assets (voice, avatar_video, thumbnail, broll, etc.) with async provider tracking
- `TaskChecklistItem` / `TaskAgentInsight` — per-task UI helpers
- `PromptOverride` — runtime admin-editable agent system prompts (global, not tenant-scoped)
- v0.2 Trajectory tables: `FollowerSnapshot`, `DailyActivity`, `ContentPillar`, `CompetitorTrack`, `AudienceSnapshot`, `Forecast`, `AgentMessage`, `PredictionAudit`

**Prisma limitation:** pgvector columns use `Unsupported("vector(...)")`; read/write via raw SQL with `<=>` cosine operator. HNSW indexes in `packages/db/prisma/manual/001_pgvector_indexes.sql` must be applied manually.

**Multi-tenancy:** The `prismaForTenant(tenantId)` client extension injects `tenantId` into every `where` clause and `create` payload, and throws on cross-tenant queries. `TENANT_SCOPED_MODELS` in `packages/db/src/tenant.ts` must be kept in sync with every new tenant-scoped model. Raw `prisma` is only for auth, webhooks, and admin scripts.

---

## Build, Dev, and Test Commands

### Root scripts (`package.json`)
```bash
# Build all TypeScript packages
pnpm build

# Run web + packages in parallel (agents must be started separately)
pnpm dev

# Lint / typecheck / test
pnpm lint
pnpm typecheck
pnpm test

# Format
pnpm format            # prettier --write .
pnpm format:check      # prettier --check .

# Prisma operations
pnpm db:generate      # generate Prisma client
pnpm db:migrate       # apply migrations
pnpm db:studio        # open Prisma Studio

# Local infrastructure
pnpm infra:up         # docker compose up (postgres, redis, langfuse, mailpit)
pnpm infra:down
pnpm infra:logs

# Agents (Python) — these proxy through pnpm filters to the agents package
pnpm agents:dev       # uv run uvicorn app.main:app --reload --port 8000
pnpm agents:test      # uv run pytest
```

### Web (`apps/web`)
```bash
pnpm --filter @smm/web dev      # localhost:3000 with turbo
pnpm --filter @smm/web build
pnpm --filter @smm/web test     # vitest run
pnpm --filter @smm/web lint
pnpm --filter @smm/web typecheck
```

### Agents (`apps/agents`)
```bash
cd apps/agents
uv sync                           # install Python deps
uv run playwright install chromium  # install browser for scraping
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                     # run tests
uv run mypy app/                  # type check
uv run ruff check .               # lint
uv run ruff format .              # format
```

### Full local boot sequence
```bash
# 1. Install tools
corepack enable; corepack prepare pnpm@9.15.0 --activate
# Install uv for your OS (e.g. winget install astral-sh.uv)

# 2. Install dependencies
pnpm install
cd apps/agents && uv sync && uv run playwright install chromium && cd ../..

# 3. Boot infrastructure
pnpm infra:up

# 4. Set up database
pnpm db:generate
pnpm db:migrate
psql "$DATABASE_URL" -f packages/db/prisma/manual/001_pgvector_indexes.sql

# 5. Smoke test API keys
python apps/agents/scripts/smoke_test_apis.py

# 6. Run
pnpm dev                          # web on :3000
# In another terminal:
cd apps/agents && uv run uvicorn app.main:app --reload --port 8000
```

---

## Code Style Guidelines

### TypeScript / Next.js
- **Prettier:** semi: true, singleQuote: true, trailingComma: all, printWidth: 100, tabWidth: 2, LF EOL
  - Plugin: `prettier-plugin-tailwindcss` with `tailwindFunctions: ["cn", "clsx", "cva"]`
- **EditorConfig:** UTF-8, LF, 2-space indent (4 for Python), trailing whitespace trimmed
- **TypeScript base config:** Strict mode, `noUncheckedIndexedAccess`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, ES2022 target, Bundler module resolution, source maps + declarations
- **ESLint:** extends `next/core-web-vitals` + `next/typescript`; `@typescript-eslint/no-unused-vars` warn with `^_` ignore; `no-explicit-any` off

### Python
- **ruff:** line length 100, target py312
  - Lint rules: E, F, I, B, UP, ASYNC, S, RET, SIM, TCH
  - Ignores: E501 (formatter handles it), B008 (FastAPI Depends in defaults)
  - Per-file ignores for tests: S101, S105, S106
- **mypy:** strict mode, pydantic plugin, `warn_unused_ignores = true`

### General conventions
- Don't write tests "just in case". Write tests for guard nodes (drift, validator), HMAC, payment webhook idempotency, crypto round-trips, and any subtle multi-tenancy logic.
- Don't add WHAT comments. Add WHY comments only when a constraint, workaround, or non-obvious decision would surprise the next reader.
- Don't add backwards-compat shims, dead-code keeping, or "just-in-case" abstractions.
- Prefer `StrReplaceFile` over `WriteFile` on existing files; never create new files when an existing one fits.

---

## Testing Strategy

### TypeScript / Web
- **Framework:** Vitest v2 with happy-dom and Testing Library React
- **Config:** `apps/web/vitest.config.ts` — uses `@vitejs/plugin-react`, path alias `@/*`, includes `src/**/*.{test,spec}.{ts,tsx}`
- **Run:** `pnpm test` or `pnpm --filter @smm/web test`
- **Coverage:** outputs to `coverage/`
- **Current tests:** `lib/agents/client.test.ts`, `lib/security/crypto.test.ts`

### Python / Agents
- **Framework:** pytest with pytest-asyncio and pytest-cov
- **Config:** `pyproject.toml` — `asyncio_mode = auto`, testpaths `tests/`
- **Run:** `cd apps/agents && uv run pytest`
- **HTTP mocking:** respx for external API calls
- **Current tests:** `test_content_review_shortcuts.py`, `test_crypto.py`, `test_drift_detector.py`, `test_hmac.py`, `test_output_validator.py`

### What to test
- HMAC inter-service auth (replay protection)
- Payment webhook idempotency
- Multi-tenancy middleware / guards
- LangGraph guard nodes (drift_detector, output_validator)
- Crypto (AES-256-GCM encrypt/decrypt round-trip, byte-compatible TS ↔ Python)

---

## Security Considerations

- **HMAC** (web ↔ agents): SHA256(`${timestamp}.${body}`), 5-minute replay window. See `apps/web/src/lib/agents/client.ts` ↔ `apps/agents/app/security/hmac.py`. FastAPI middleware exempts `/health`, `/docs`, `/openapi.json`.
- **OAuth tokens at-rest:** AES-256-GCM encryption (byte-compatible TypeScript ↔ Python). Keys derived via HKDF from `AUTH_SECRET`.
- **Scraper accounts:** Instagram throwaway accounts only — NEVER personal handles. Configure via `IG_SCRAPER_ACCOUNTS` env JSON with 2-3 accounts for rotation. Sessions cached in `./.smm-sessions/` (gitignored).
- **Webhooks:** Payme JSON-RPC Basic auth + secret verification. Instagram webhook X-Hub-Signature-256 verification. HeyGen webhooks deduplicated via `WebhookEvent` table.
- **Secrets:** `.env` is gitignored. Production uses Coolify secret store.
- **Multi-tenancy:** Never call `prisma.<model>` directly from feature code — always `prismaForTenant(session.user.tenantId)`. Raw `prisma` only for auth, webhooks, and admin scripts.
- **Admin access:** Platform admin allowlist (`ADMIN_EMAILS` env) plus built-in founder emails. Admin routes under `/admin` and `/api/admin` guarded by `lib/auth/admin.ts`.
- **User suspension:** `User.suspendedAt` blocks sign-in across all providers (checked in `signIn` callback and Credentials `authorize`).

---

## Deployment

### Local Development
- `infra/docker-compose.dev.yml` spins up: Postgres 16 + pgvector, Redis 7, Langfuse (port 3001), Mailpit (ports 1025/8025)
- Web dev server: `localhost:3000` (Next.js turbo)
- Agents dev server: `localhost:8000` (FastAPI)

### Production — Coolify (Frankfurt)
- Domain: `smm.brotech.uz`
- `docker-compose.yaml` at repo root is read by Coolify
- Services: Postgres 17 + pgvector, Redis 7, MinIO (S3-compatible object storage), web (Next.js), agents (FastAPI)
- **Web Dockerfile** (`infra/docker/web.Dockerfile`): multi-stage (deps → build → runtime), Node 22 Alpine, standalone output, non-root `smm` user. On startup runs `prisma db push --accept-data-loss --skip-generate` then `node apps/web/server.js`.
- **Agents Dockerfile** (`infra/docker/agents.Dockerfile`): based on Playwright Python image (includes Chromium), uses `uv` for deps, non-root `pwuser`, 2 uvicorn workers.
- **MinIO bootstrap:** One-shot container creates the S3 bucket on first deploy and sets public download policy.
- Coolify auto-injects `SERVICE_URL_WEB`, `SERVICE_URL_MINIO`, and other service-discovery env vars.

---

## Key Conventions and Pitfalls

### Multi-tenancy
Every domain table has `tenantId`. The Prisma client extension injects `tenantId` into every `where` clause and `create` payload, and refuses cross-tenant queries. `TENANT_SCOPED_MODELS` in `packages/db/src/tenant.ts` must be updated for every new tenant-scoped model.

### LangGraph
- One graph per user, `thread_id = "{tenant_id}:{user_id}:{workflow}"`.
- State reducers (`Annotated[..., operator.add]`) prevent races between parallel nodes — keep that pattern when adding fields.
- Every concrete numeric/timing claim in a generated script must have `predict_evidence` or an `@evidence:` marker.

### Instagram Data
- **instagrapi** (primary) — private mobile API; needs `IG_SCRAPER_ACCOUNTS` JSON in env with 2-3 throwaway accounts.
- **Playwright** (fallback) — public Instagram profile probe + recent posts without login. Stealth plugin + mobile UA + locale `uz-UZ`.
- **Meta Graph API** (target end-state) — for OAuth'd users, after Advanced Access approval.
- Dispatcher auto-falls-back to scraping when Graph API errors.

### LLM Models — pick from `app/config.py`
| Use case | Model |
|---|---|
| Scriptwriter draft + critique | `claude-opus-4-7` |
| Scriptwriter revisions | `claude-sonnet-4-6` |
| Initial analysis, Roadmap generator | `claude-sonnet-4-6` |
| Drift detector, Output validator | `claude-haiku-4-5` |
| Industry News, Market Analyst (bulk), Vision | `gemini-2.5-flash` |
| Market synthesis (weekly) | `claude-sonnet-4-6` |
| Account Tracker (fast classification) | `llama-3.3-70b-versatile` (Groq) |
| Embeddings | `voyage-3` (1024-dim) |

Never sprinkle model IDs across the code — change them centrally in `config.py`.

### Payments
- MVP: Payme only. Phase 2: Click, Stripe.
- All providers go through `PaymentProvider` interface.
- Payme amounts are in **tiyin** (1 UZS = 100 tiyin). Centralized in `lib/payments/payme/plans.ts`.
- Webhooks always idempotent: dedupe on `(provider, providerEventId)` via `WebhookEvent` table.

### Media Generation
- **ElevenLabs** — voiceover TTS
- **HeyGen** — avatar video (soft-disabled by default via `ENABLE_HEYGEN_AVATAR`)
- **Runway** — B-roll generation
- **Imagen 3** (via Gemini) — thumbnail generation
- All media tracked in `TaskMedia` table with async polling for HeyGen/Runway.

### Common Pitfalls
- **Tailwind v4** uses `@import 'tailwindcss'` + `@theme {}` blocks; do NOT add a `tailwind.config.ts` — config now lives in CSS.
- **next-intl** default locale (`uz`) is **not** prefixed — use `Link` from `@/i18n/routing`, not `next/link`.
- **LangGraph's PostgresSaver** uses its own connection pool. Don't try to share the SQLAlchemy session pool with it.
- **pgvector columns** are `Unsupported(...)` in Prisma — query via raw SQL.
- **BigInt fields** (`amountUzs`, `sizeBytes`) require careful JSON serialization. Wrap in `Number()` only when ≤ 2^53.
- **Inter-service SSE:** Agents publish to Redis pub/sub → FastAPI SSE endpoint → Next.js proxy route → Browser EventSource. Ping every 15s to keep connections alive.
- **NextAuth JWT strategy:** The session is JWT-based, not database-based. `tenantId`, `role`, and `locale` are injected into the JWT in callbacks and surfaced on `session.user`.
- **Prisma on Windows dev:** The schema currently disables pgvector in the `extensions` array for Windows dev (see `schema.prisma` comment). Restore `pgvector` when running against Docker Postgres.
- **Agents background workers:** Only start when `RUN_WORKERS=1` is set. In local dev you typically run one agents process with workers enabled.

---

## Inter-Service Communication

**Web → Agents:**
- Commands: REST + HMAC SHA256 (5-minute replay window)
- Long jobs: Redis Streams (planned)
- Browser events: SSE → Next.js route → upstream FastAPI SSE → Redis pub/sub fan-out

**SSE Event types** (Zod discriminated union in `packages/shared-types/src/agents.ts`):
`run.started`, `agent.thinking`, `agent.tool_use`, `node.completed`, `drift.warning`, `budget.exceeded`, `run.completed`, `run.failed`

---

## Critical Path Before Launch

1. **Meta App Review** submission for Advanced Access (`instagram_business_manage_insights`, `instagram_business_manage_comments`). 2-6 weeks. Submit on day 1.
2. **Pre-seed shared_knowledge** — run `uv run python -m app.workers.knowledge_seeder` once to populate top 30 UZ niches with ~20 exemplar posts each (~400 rows).
3. **2-3 throwaway IG scraper accounts** + residential proxy (Smartproxy / BrightData proxy-only plan, ~$10-20/mo).

---

## Environment Variables

Copy `.env.example` to `.env` and fill in values. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` / `DIRECT_URL` | PostgreSQL connection |
| `REDIS_URL` | Redis connection |
| `AUTH_SECRET` / `AUTH_URL` | Auth.js v5 |
| `ADMIN_EMAILS` | Comma-separated platform admin emails |
| `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` | Bootstrap admin account (created on first boot) |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | LLM providers |
| `VOYAGE_API_KEY` | Embeddings |
| `AGENTS_BASE_URL` / `AGENTS_HMAC_SECRET` | Inter-service communication |
| `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET` | Meta Graph API |
| `IG_SCRAPER_ACCOUNTS` | JSON array of throwaway IG accounts |
| `IG_SCRAPER_PROXY_URL` | Residential proxy for scraping |
| `PAYME_MERCHANT_ID` / `PAYME_SECRET_KEY` | Payment provider |
| `PAYME_TEST_MODE` | Payme test mode toggle |
| `R2_*` or `S3_*` | Object storage (S3-compatible) |
| `SENTRY_DSN` / `POSTHOG_KEY` | Observability |
| `LANGFUSE_*` | LLM tracing (self-hosted) |
| `ENABLE_HEYGEN_AVATAR` / `ENABLE_AUTO_PUBLISH` | Feature flags |
| `HEYGEN_API_KEY` / `RUNWAY_API_KEY` / `ELEVENLABS_API_KEY` | Media generation |

See `.env.example` for the full list and format.

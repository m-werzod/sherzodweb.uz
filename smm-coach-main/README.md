# SMM — AI Instagram Growth Coach

Monorepo for an AI-powered Instagram growth coach platform. Users connect their Instagram, declare a goal, and the system generates a personalized roadmap of content tasks driven by four cooperating AI agents (Market Analyst, Industry News, Scriptwriter, Account Tracker) in a continuous feedback loop.

## Workspaces

| Path | Stack | Purpose |
|---|---|---|
| `apps/web` | Next.js 15 (App Router), TypeScript, Tailwind v4, shadcn/ui, Prisma, Auth.js v5, next-intl, React Flow | User-facing app, dashboard, roadmap UI, billing |
| `apps/agents` | Python 3.12, FastAPI, LangGraph, pgvector, Langfuse, uv | AI agent orchestration service |
| `packages/db` | Prisma | Shared DB schema + client |
| `packages/shared-types` | Zod | Cross-language contracts mirrored to Pydantic |
| `packages/ui` | shadcn/ui | Shared components |
| `packages/config` | ESLint/TS/Tailwind | Tooling presets |
| `infra/` | Docker, Coolify | Local & production infra |

## Prerequisites

- **Node.js >= 22** (`.nvmrc` provided)
- **pnpm >= 9** (`corepack enable && corepack prepare pnpm@9.15.0 --activate`)
- **Python 3.12+** with **uv** (`pip install uv` or `winget install astral-sh.uv`)
- **Docker Desktop** (for local Postgres + Redis + Langfuse)
- **Git**

## Quickstart

```powershell
# 1. Install JS dependencies
pnpm install

# 2. Install Python dependencies (apps/agents)
cd apps/agents
uv sync
cd ../..

# 3. Boot local infra (Postgres + Redis + Langfuse)
pnpm infra:up

# 4. Copy env template and fill in values
Copy-Item .env.example .env

# 5. Generate Prisma client and run migrations
pnpm db:generate
pnpm db:migrate

# 6. Run everything in dev mode
pnpm dev
```

Web app boots on http://localhost:3000, agents service on http://localhost:8000, Langfuse on http://localhost:3001.

## High-level architecture

See [reactive-mixing-manatee.md plan](../.claude/plans/reactive-mixing-manatee.md) for the full architecture and product roadmap.

## License

UNLICENSED — proprietary.

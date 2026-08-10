# @smm/web

User-facing Next.js 15 app: dashboard, roadmap tree, onboarding, billing, auth.

## Local dev

```powershell
# 1. Make sure @smm/db has been generated
pnpm --filter @smm/db generate

# 2. Run web + agents + infra
pnpm dev
```

## Routes

| Path | Purpose |
|---|---|
| `/[locale]/` | Landing |
| `/[locale]/sign-in` · `/sign-up` | Auth |
| `/[locale]/dashboard` | Home (after auth) |
| `/[locale]/roadmap` | React Flow tree view |
| `/[locale]/onboarding` | First-run wizard → triggers roadmap generation |
| `/[locale]/billing` | Plans + Payme checkout |
| `/[locale]/tasks` · `/analytics` · `/settings` | Placeholder pages |
| `/api/health` | Liveness probe |
| `/api/onboarding` | POST onboarding → kicks off agent workflow |
| `/api/agents/sse/[userId]` | SSE proxy to apps/agents |
| `/api/auth/[...nextauth]` | Auth.js v5 |
| `/api/sign-up` | Account creation (Credentials provider) |
| `/api/webhooks/payme` | Payme JSON-RPC webhook |
| `/api/webhooks/instagram` | Meta Graph webhook subscription |

## Architecture notes

- `@smm/db` is consumed directly (no separate build step) via `transpilePackages` and tsconfig path aliases.
- `lib/auth/auth.ts` is the source of truth for the Auth.js v5 config. JWT carries `tenantId`/`role`/`locale`.
- `lib/agents/client.ts` is the only place HMAC signing happens. Every call into apps/agents goes through `invokeWorkflow`.
- `lib/payments/provider.ts` defines `PaymentProvider`. New providers register themselves in `lib/payments/index.ts`.

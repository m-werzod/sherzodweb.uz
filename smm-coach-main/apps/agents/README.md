# @smm/agents

AI agent orchestration service for the SMM platform. FastAPI + LangGraph.

## Architecture

Four cooperating agents inside a single durable LangGraph per user:

1. **Market Analyst** — region-trending hooks/audio/formats (Gemini 2.5 Flash)
2. **Industry News** — niche-specific signals (Claude Sonnet 4.6)
3. **Scriptwriter** — task script + critique loop (Claude Opus 4.7 → Sonnet 4.6)
4. **Account Tracker** — actual IG metrics + audience sentiment (Claude Haiku 4.5 + Gemini Flash vision)

Plus guard nodes: `drift_detector` (Haiku) and `output_validator`. State persisted via LangGraph's Postgres checkpointer.

## Run locally

```powershell
uv sync                       # install deps
uv run uvicorn app.main:app --reload --port 8000

uv run pytest                 # tests
uv run mypy app/              # type-check
uv run ruff check .           # lint
uv run ruff format .          # format
```

## Endpoints

- `POST /v1/invoke` — fire-and-forget agent workflow invocation (auth via HMAC)
- `GET /v1/runs/{run_id}` — poll status
- `GET /v1/streams/{user_id}` — long-lived SSE of agent events for a user
- `GET /health` — liveness probe

All non-health endpoints require `X-Smm-Signature` HMAC header with `AGENTS_HMAC_SECRET`.

## Memory layout

| Where | What |
|---|---|
| LangGraph PostgresSaver | per-thread (per-user-per-workflow) checkpoints |
| `agent_memory` table | long-term per-tenant memory + embeddings |
| `shared_knowledge` table | cross-tenant trends/news/exemplars |
| Redis | rate limits, idempotency keys, SSE pub/sub |

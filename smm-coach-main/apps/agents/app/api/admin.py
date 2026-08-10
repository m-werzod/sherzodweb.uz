"""Admin-only endpoints consumed by the web admin panel. HMAC-protected by
the global middleware like every other /v1/* route — the web side adds an
extra platform-admin check (ADMIN_EMAILS) before calling these.

  GET  /v1/admin/agent-catalog      full agent catalog + effective prompts
  POST /v1/admin/prompt-cache/purge  drop the prompt-override cache after an edit
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.graphs import prompt_store
from app.graphs.agent_catalog import get_agent_catalog

log = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/agent-catalog")
async def agent_catalog() -> dict:
    """Every agent: provider, live model, when it runs, I/O, and (for the
    prompt-driven ones) the effective + default system prompt."""
    return {"agents": await get_agent_catalog()}


@router.get("/providers")
async def providers() -> dict:
    """Which AI provider keys are configured. The agents service is the
    authority here — most LLM keys live only in its env, not the web's."""
    s = get_settings()
    cfg = {
        "anthropic": s.anthropic_api_key is not None,
        "openai": s.openai_api_key is not None,
        # Fast OpenAI-compatible engines for the high-volume agents. Either
        # one satisfies the "fast LLM" tier; fast_llm tries them in order and
        # only falls back to Claude Haiku when both fail.
        "cerebras": s.cerebras_api_key is not None,
        "openrouter": s.openrouter_api_key is not None,
        "gemini": s.gemini_api_key is not None,
        "voyage": s.voyage_api_key is not None,
        "elevenlabs": s.elevenlabs_api_key is not None,
        "heygen": s.heygen_api_key is not None,
        "runway": s.runway_api_key is not None,
    }
    return {"providers": [{"provider": k, "configured": v} for k, v in cfg.items()]}


class PurgeRequest(BaseModel):
    agentKey: str | None = None


@router.post("/prompt-cache/purge")
async def purge_prompt_cache(req: PurgeRequest) -> dict:
    """Drop cached prompt override(s) so an admin edit takes effect now rather
    than after the TTL. `agentKey` omitted → purge all."""
    prompt_store.invalidate(req.agentKey)
    return {"ok": True, "purged": req.agentKey or "all"}

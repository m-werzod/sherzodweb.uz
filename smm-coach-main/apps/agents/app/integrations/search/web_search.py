"""web_search — the single web-grounding primitive for Stage 3a/3b.

Provider order:
  1. Tavily (TAVILY_API_KEY) — purpose-built search API, clean structured
     {title,url,snippet}. Preferred.
  2. Gemini google_search grounding (GEMINI_API_KEY) — reuses the key already
     configured in prod, so live grounding works the moment this ships, before
     a dedicated search key is provisioned.
  3. Neither configured → [] (callers degrade to DB-seeded knowledge).

Best-effort throughout: any provider error returns [] rather than raising into
the agent loop. Results are deduped by URL and capped at `limit`.
"""
from __future__ import annotations

from typing import TypedDict

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str


def web_search_enabled() -> bool:
    """True when at least one provider is configured (Tavily or Gemini)."""
    s = get_settings()
    return bool(s.tavily_api_key or s.gemini_api_key)


async def web_search(query: str, *, limit: int = 5) -> list[SearchResult]:
    query = (query or "").strip()
    if not query:
        return []

    settings = get_settings()
    results: list[SearchResult] = []

    tav = settings.tavily_api_key
    if tav:
        try:
            results = await _tavily(query, tav.get_secret_value(), limit)
        except Exception as exc:  # noqa: BLE001 — fall through to Gemini
            log.warning("web_search.tavily_failed", error=str(exc)[:160])
            results = []

    if not results and settings.gemini_api_key:
        # Lazy import: keeps the search package independent of the LLM stack and
        # avoids a circular import at module load.
        from app.integrations.llm.gemini_client import grounded_search

        try:
            raw = await grounded_search(query, max_results=limit)
            results = [
                SearchResult(
                    title=str(r.get("title") or "")[:200],
                    url=str(r.get("url") or ""),
                    snippet=str(r.get("snippet") or "")[:400],
                )
                for r in raw
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("web_search.gemini_failed", error=str(exc)[:160])
            results = []

    # Dedup by url (keep first), drop empty, cap.
    out: list[SearchResult] = []
    seen: set[str] = set()
    for r in results:
        key = r.get("url") or r.get("title") or ""
        if not (r.get("title") or r.get("snippet")):
            continue
        if key and key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


async def _tavily(query: str, api_key: str, limit: int) -> list[SearchResult]:
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max(1, min(limit, 10)),
        "search_depth": "basic",
        "include_answer": False,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(TAVILY_URL, json=payload)
        r.raise_for_status()
        data = r.json()
    out: list[SearchResult] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            SearchResult(
                title=str(item.get("title") or "")[:200],
                url=str(item.get("url") or ""),
                snippet=str(item.get("content") or item.get("snippet") or "")[:400],
            )
        )
    return out

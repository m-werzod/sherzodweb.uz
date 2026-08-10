"""Stage 3a/3b — web_search primitive: provider selection (Tavily preferred,
Gemini grounding fallback), dedup, empty-query + no-provider safety."""
from __future__ import annotations

import asyncio
import importlib

# Submodule name collides with the re-exported function in the package __init__,
# so `import app.integrations.search.web_search as ws` resolves to the function.
# import_module returns the actual module object.
ws = importlib.import_module("app.integrations.search.web_search")


class _FakeSecret:
    def __init__(self, v):
        self._v = v

    def get_secret_value(self):
        return self._v


class _Settings:
    def __init__(self, tavily=None, gemini=None):
        self.tavily_api_key = _FakeSecret(tavily) if tavily else None
        self.gemini_api_key = _FakeSecret(gemini) if gemini else None


def test_empty_query_returns_empty(monkeypatch):
    monkeypatch.setattr(ws, "get_settings", lambda: _Settings(tavily="k"))
    assert asyncio.run(ws.web_search("   ")) == []


def test_no_provider_returns_empty(monkeypatch):
    monkeypatch.setattr(ws, "get_settings", lambda: _Settings())
    assert asyncio.run(ws.web_search("fitness uz")) == []
    assert ws.web_search_enabled() is False


def test_tavily_preferred(monkeypatch):
    monkeypatch.setattr(ws, "get_settings", lambda: _Settings(tavily="k", gemini="g"))

    async def _fake_tavily(query, key, limit):
        return [
            ws.SearchResult(title="A", url="https://a.com", snippet="sa"),
            ws.SearchResult(title="B", url="https://b.com", snippet="sb"),
        ]

    monkeypatch.setattr(ws, "_tavily", _fake_tavily)
    out = asyncio.run(ws.web_search("fitness uz", limit=5))
    assert [r["url"] for r in out] == ["https://a.com", "https://b.com"]


def test_falls_back_to_gemini_when_no_tavily(monkeypatch):
    monkeypatch.setattr(ws, "get_settings", lambda: _Settings(gemini="g"))

    async def _fake_grounded(query, max_results=5):
        return [{"title": "G", "url": "https://g.com", "snippet": "sg"}]

    import app.integrations.llm.gemini_client as gc

    monkeypatch.setattr(gc, "grounded_search", _fake_grounded)
    out = asyncio.run(ws.web_search("fitness uz"))
    assert out and out[0]["url"] == "https://g.com"


def test_tavily_failure_falls_through_to_gemini(monkeypatch):
    monkeypatch.setattr(ws, "get_settings", lambda: _Settings(tavily="k", gemini="g"))

    async def _boom(query, key, limit):
        raise RuntimeError("tavily down")

    async def _fake_grounded(query, max_results=5):
        return [{"title": "G", "url": "https://g.com", "snippet": "sg"}]

    import app.integrations.llm.gemini_client as gc

    monkeypatch.setattr(ws, "_tavily", _boom)
    monkeypatch.setattr(gc, "grounded_search", _fake_grounded)
    out = asyncio.run(ws.web_search("x"))
    assert out and out[0]["url"] == "https://g.com"


def test_dedup_by_url_and_cap(monkeypatch):
    monkeypatch.setattr(ws, "get_settings", lambda: _Settings(tavily="k"))

    async def _fake_tavily(query, key, limit):
        return [
            ws.SearchResult(title="A", url="https://a.com", snippet="1"),
            ws.SearchResult(title="A2", url="https://a.com", snippet="2"),  # dup url
            ws.SearchResult(title="", url="", snippet=""),  # empty → dropped
            ws.SearchResult(title="C", url="https://c.com", snippet="3"),
        ]

    monkeypatch.setattr(ws, "_tavily", _fake_tavily)
    out = asyncio.run(ws.web_search("x", limit=10))
    assert [r["url"] for r in out] == ["https://a.com", "https://c.com"]

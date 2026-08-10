"""competitor_intel seeds web-discovered handles into competitor_tracks so
competitor_tracker (official business_discovery) can turn them into REAL
competitor_snapshot data. Verifies sanitization, dedup, cap, tenant scoping."""
from __future__ import annotations

import json

import pytest

from app.graphs.nodes import competitor_intel as ci


class _FakeSession:
    def __init__(self) -> None:
        self.executes: list[tuple[str, dict]] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, stmt: object, params: dict | None = None) -> None:
        self.executes.append((str(stmt), params or {}))

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_persist_discovered_guard_returns_zero() -> None:
    assert await ci._persist_discovered("t1", []) == 0
    assert await ci._persist_discovered("t1", [{"handle": ""}]) == 0


@pytest.mark.asyncio
async def test_persist_discovered_sanitizes_dedups_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSession()
    monkeypatch.setattr(ci, "get_sessionmaker", lambda: (lambda: fake))

    discovered = [
        {"handle": "@natgeo", "source_url": "u1"},
        {"handle": "natgeo", "source_url": "u2"},      # duplicate (case/@) → skipped
        {"handle": "nat!geo$2", "source_url": "u3"},   # sanitized → natgeo2
        *[{"handle": f"acc{i}"} for i in range(10)],    # over the cap
    ]
    n = await ci._persist_discovered("t1", discovered, limit=5)
    assert n == 5  # capped

    inserts = [e for e in fake.executes if "INSERT INTO competitor_tracks" in e[0]]
    assert len(inserts) == 5
    handles = [e[1]["h"] for e in inserts]
    assert handles.count("natgeo") == 1  # @-strip + case dedup
    assert "natgeo2" in handles  # non-charset stripped
    assert all(e[1]["t"] == "t1" for e in inserts)  # tenant-scoped
    assert "ON CONFLICT" in inserts[0][0]  # dedup at the DB layer too
    assert json.loads(inserts[0][1]["meta"])["source"] == "web_discovered"


def test_fold_surfaces_trend_content_even_without_llm() -> None:
    # Empty intel = the LLM synthesis degraded; the REAL live trend data (winning
    # content + hashtags) must still reach the roadmap via the deterministic fold.
    out = ci._fold(
        "BASE",
        {},  # no LLM intel
        [{"kind": "trend", "label": "#toshkent"}, {"kind": "format", "label": "Reels"}],
        [],
        None,
        [{"text": "Amerikaga qanday kelib qolganman", "engagement": 4187}],
    )
    assert out.startswith("BASE")
    assert "RAQOBATCHI VA TREND" in out
    assert "Trenddagi g'olib mavzular" in out
    assert "Amerikaga qanday" in out  # winning-post content surfaced
    assert "#toshkent" in out  # hashtag trend surfaced


def test_fold_empty_returns_existing_unchanged() -> None:
    assert ci._fold("BASE", {}, [], [], None, None) == "BASE"

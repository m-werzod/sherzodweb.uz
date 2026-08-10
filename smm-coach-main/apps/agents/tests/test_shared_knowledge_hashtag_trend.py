"""save_hashtag_trends — caches a hashtag's top posts as kind='hashtag_trend' (read by
top_signals_for_region → competitor_intel → roadmap). Verifies the guard +
top-N-by-engagement + refresh (delete-then-insert) + hashtag sanitization."""
from __future__ import annotations

import json

import pytest

from app.memory import shared_knowledge as sk


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
async def test_save_hashtag_trends_guard_returns_zero() -> None:
    assert await sk.save_hashtag_trends(hashtag="", region="uz", posts=[{"id": "1"}]) == 0
    assert await sk.save_hashtag_trends(hashtag="#x", region="uz", posts=[]) == 0


@pytest.mark.asyncio
async def test_save_hashtag_trends_keeps_top_and_sanitizes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSession()
    monkeypatch.setattr(sk, "get_sessionmaker", lambda: (lambda: fake))

    posts = [
        {"id": f"p{i}", "caption": f"c{i}", "like_count": i * 10, "comments_count": i}
        for i in range(8)  # engagement = 11*i → p7 highest, p0 lowest
    ]
    n = await sk.save_hashtag_trends(
        hashtag="#tosh! kent", region="uz", posts=posts, niche="travel", keep_top=5
    )
    assert n == 5

    # First statement is the refresh DELETE, keyed by the SANITIZED hashtag.
    assert "DELETE FROM shared_knowledge" in fake.executes[0][0]
    assert fake.executes[0][1]["tag"] == "toshkent"  # '#', '!', ' ' stripped

    inserts = [e for e in fake.executes if "INSERT INTO shared_knowledge" in e[0]]
    assert len(inserts) == 5
    # The 5 kept are the highest-engagement (11*i for i=3..7), NOT p0/p1/p2.
    scores = sorted(float(p[1]["score"]) for p in inserts)
    assert scores == [33.0, 44.0, 55.0, 66.0, 77.0]

    # metadata carries the sanitized hashtag + label + region for top_signals_for_region.
    meta = json.loads(inserts[0][1]["metadata"])
    assert meta["hashtag"] == "toshkent"
    assert meta["label"] == "#toshkent"
    assert meta["region"] == "uz"

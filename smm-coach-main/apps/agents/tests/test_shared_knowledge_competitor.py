"""save_competitor_posts — caches a competitor's top posts as competitor_snapshot
(the kind competitor_intel reads, which previously had a reader but no writer).
Verifies the guard + top-N-by-engagement selection + refresh (delete-then-insert)."""
from __future__ import annotations

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
async def test_save_competitor_posts_guard_returns_zero() -> None:
    assert await sk.save_competitor_posts(handle="", niche="fitness", posts=[{"id": "1"}]) == 0
    assert await sk.save_competitor_posts(handle="x", niche="", posts=[{"id": "1"}]) == 0
    assert await sk.save_competitor_posts(handle="x", niche="fitness", posts=[]) == 0


@pytest.mark.asyncio
async def test_save_competitor_posts_keeps_top_by_engagement(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeSession()
    monkeypatch.setattr(sk, "get_sessionmaker", lambda: (lambda: fake))

    posts = [
        {"id": f"p{i}", "caption": f"c{i}", "like_count": i * 10, "comments_count": i}
        for i in range(8)  # engagement = 11*i → p7 highest, p0 lowest
    ]
    n = await sk.save_competitor_posts(handle="@natgeo", niche="nature", posts=posts, keep_top=6)
    assert n == 6

    # First statement is the refresh DELETE, then 6 INSERTs.
    assert "DELETE FROM shared_knowledge" in fake.executes[0][0]
    inserts = [e for e in fake.executes if "INSERT INTO shared_knowledge" in e[0]]
    assert len(inserts) == 6
    # The 6 kept are the highest-engagement (p7..p2), NOT p0/p1.
    scores = sorted(float(p[1]["score"]) for p in inserts)
    assert scores == [22.0, 33.0, 44.0, 55.0, 66.0, 77.0]  # 11*i for i=2..7

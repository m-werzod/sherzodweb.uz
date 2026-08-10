"""Tests for the advisory-lock singleton gate — a periodic cron job runs on at
most one replica per tick (no double-fire / double-billing / duplicate rows)."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers import _singleton


class _R:
    def __init__(self, val: Any) -> None:
        self._v = val

    def scalar(self) -> Any:
        return self._v


def _patch(monkeypatch: pytest.MonkeyPatch, lock_got: bool) -> list[str]:
    calls: list[str] = []

    async def execute(q: Any, *a: Any, **k: Any) -> _R:
        calls.append(str(q))
        return _R(lock_got if "pg_try_advisory_lock" in str(q) else None)

    session = MagicMock()
    session.execute = execute
    session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(_singleton, "get_sessionmaker", lambda: MagicMock(return_value=cm))
    return calls


@pytest.mark.asyncio
async def test_runs_work_and_releases_when_lock_acquired(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch(monkeypatch, lock_got=True)
    ran: list[int] = []

    async def work() -> None:
        ran.append(1)

    out = await _singleton.run_as_singleton("job-a", work)
    assert out is True
    assert ran == [1]
    assert any("pg_try_advisory_lock" in c for c in calls)
    assert any("pg_advisory_unlock" in c for c in calls)  # always released


@pytest.mark.asyncio
async def test_skips_work_when_another_replica_holds_the_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch(monkeypatch, lock_got=False)
    ran: list[int] = []

    async def work() -> None:
        ran.append(1)

    out = await _singleton.run_as_singleton("job-b", work)
    assert out is False
    assert ran == []  # work never ran
    assert not any("pg_advisory_unlock" in c for c in calls)  # nothing to release


def test_lock_key_stable_distinct_and_in_range() -> None:
    assert _singleton.lock_key("tracker_scheduler") == _singleton.lock_key("tracker_scheduler")
    assert _singleton.lock_key("tracker_scheduler") != _singleton.lock_key("daily_snapshot")
    assert -(2**31) <= _singleton.lock_key("daily_snapshot") < 2**31

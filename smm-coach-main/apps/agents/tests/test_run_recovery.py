"""Tests for LLM-run crash recovery (heartbeat lease + dead-run reaper).

T7.1: a run is now durably claimed by run_worker with a visibility-timeout lease.
`heartbeat_run` extends the lease per node (a live run keeps its claim);
`reap_dead_runs` fails only runs that crashed past the attempt cap (the run_worker
reclaims everything below it).

Suite convention (see test_tenant_top_hooks.py): mock the sessionmaker, assert the
QUERY shape + PARAMS + result, no live DB.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.runs import repository


class _Mappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _Mappings:
        return _Mappings(self._rows)


def _patch_session(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> AsyncMock:
    execute_mock = AsyncMock(return_value=_Result(rows))
    session = MagicMock()
    session.execute = execute_mock
    session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    sm = MagicMock(return_value=cm)
    monkeypatch.setattr(repository, "get_sessionmaker", lambda: sm)
    return execute_mock


@pytest.mark.asyncio
async def test_reap_fails_only_over_cap_dead_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_mock = _patch_session(monkeypatch, [{"id": "r1"}, {"id": "r2"}])

    out = await repository.reap_dead_runs(3)

    assert out == ["r1", "r2"]
    clause, params = execute_mock.await_args.args
    sql = str(clause)
    assert "status = 'failed'" in sql
    assert "status IN ('queued', 'running')" in sql  # never touches completed/failed
    assert '"leaseExpiresAt" < NOW()' in sql  # expired-lease (dead-driver) runs
    assert "attempts >= :max_attempts" in sql  # only past the cap (rest get reclaimed)
    # legacy/transitional clause: a pre-T7.1 'running' orphan with no lease
    assert '"leaseExpiresAt" IS NULL' in sql
    assert "make_interval(secs => :legacy_stale)" in sql
    assert params["max_attempts"] == 3
    assert params["legacy_stale"] == 1800
    assert "qayta urin" in params["err"].lower()


@pytest.mark.asyncio
async def test_reap_returns_empty_when_nothing_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch, [])
    assert await repository.reap_dead_runs(3) == []


@pytest.mark.asyncio
async def test_heartbeat_extends_lease_on_running_row(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_mock = _patch_session(monkeypatch, [])

    await repository.heartbeat_run("run-1", lease_seconds=600)

    clause, params = execute_mock.await_args.args
    sql = str(clause)
    assert '"updatedAt" = NOW()' in sql
    assert "make_interval(secs => :lease)" in sql  # the lease extension
    assert "status = 'running'" in sql  # don't resurrect a completed/failed run
    assert params["id"] == "run-1"
    assert params["lease"] == 600


@pytest.mark.asyncio
async def test_mark_completed_only_transitions_a_running_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A terminal write must guard on status='running' so a late worker can't
    overwrite the reaper's 'failed' (or vice versa) — first terminal writer wins."""
    execute_mock = _patch_session(monkeypatch, [])
    await repository.mark_completed(
        "r1",
        output={},
        cost={"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "cost_usd": 0.0},
    )
    sql = str(execute_mock.await_args.args[0])
    assert "status = 'completed'" in sql
    assert "status = 'running'" in sql  # don't resurrect/overwrite a terminal run


@pytest.mark.asyncio
async def test_mark_failed_only_transitions_a_running_run(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_mock = _patch_session(monkeypatch, [])
    await repository.mark_failed("r1", error="boom")
    sql = str(execute_mock.await_args.args[0])
    assert "status = 'failed'" in sql
    assert "status = 'running'" in sql


@pytest.mark.asyncio
async def test_heartbeat_swallows_db_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """A heartbeat failure must never break the run it is reporting on."""
    def _boom() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(repository, "get_sessionmaker", _boom)
    await repository.heartbeat_run("run-1")  # must not raise


def test_reaper_defaults_are_sane() -> None:
    from app.workers import run_reaper

    assert run_reaper.MAX_ATTEMPTS >= 1
    assert run_reaper.INTERVAL > 0

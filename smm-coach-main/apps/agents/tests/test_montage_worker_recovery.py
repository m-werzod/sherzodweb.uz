"""Tests for the montage worker's crash-recovery (lease + reaper + attempt cap).

A crash / Coolify redeploy mid-render used to strand the row in 'processing'
forever, and the web dedup guard then permanently blocked re-rendering that task.
The fix: claim sets a visibility-timeout lease + bumps attempts, the claim SELECT
also reclaims expired-lease rows, and a reaper fails rows past the attempt cap.

Following the suite convention (see test_tenant_top_hooks.py): we don't spin up a
live DB — the logic is "run a SQL, shape the rows", so we mock the session and
assert the QUERY (reclaim clause, attempt bump, attempt cap) and the PARAMS +
result shape. A real Postgres integration test belongs in a separate suite.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers import montage_worker


class _Mappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _Mappings:
        return _Mappings(self._rows)


def _session(rows: list[dict[str, Any]]) -> tuple[MagicMock, AsyncMock]:
    execute_mock = AsyncMock(return_value=_Result(rows))
    session = MagicMock()
    session.execute = execute_mock
    session.commit = AsyncMock()
    return session, execute_mock


@pytest.mark.asyncio
async def test_claim_shapes_row_and_bumps_attempts_with_lease() -> None:
    row = {"id": "m1", "taskId": "t1", "tenantId": "tn1", "meta": {"x": 1}}
    session, execute_mock = _session([row])

    out = await montage_worker._claim_one(session)

    assert out == {"media_id": "m1", "task_id": "t1", "tenant_id": "tn1", "meta": {"x": 1}}
    clause, params = execute_mock.await_args.args
    sql = str(clause)
    # Bumps the attempt counter and sets the visibility-timeout lease on claim.
    assert "attempts=attempts+1" in sql
    assert "make_interval(secs => :lease_seconds)" in sql
    assert params["lease_seconds"] == montage_worker.LEASE_SECONDS
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_claim_reclaims_expired_lease_not_just_pending() -> None:
    """The claim SELECT must pick up a 'processing' row whose lease expired (its
    worker died) — otherwise a crash strands the row forever."""
    session, execute_mock = _session([])

    await montage_worker._claim_one(session)

    sql = str(execute_mock.await_args.args[0])
    params = execute_mock.await_args.args[1]
    assert "status='pending'" in sql
    assert "status='processing'" in sql
    assert '"leaseExpiresAt" < NOW()' in sql
    # Reclaim ONLY below the attempt cap — else an over-cap row loops forever and
    # the reaper (which fails attempts>=cap) never gets to it.
    assert "attempts < :max_attempts" in sql
    assert params["max_attempts"] == montage_worker.MAX_ATTEMPTS
    assert "FOR UPDATE SKIP LOCKED" in sql  # still race-safe across pollers


@pytest.mark.asyncio
async def test_claim_returns_none_when_nothing_to_do() -> None:
    session, _ = _session([])
    assert await montage_worker._claim_one(session) is None


@pytest.mark.asyncio
async def test_reaper_fails_only_rows_past_attempt_cap() -> None:
    session, execute_mock = _session([{"id": "dead1"}, {"id": "dead2"}])

    await montage_worker._reap_abandoned(session)

    clause, params = execute_mock.await_args.args
    sql = str(clause)
    assert "status='failed'" in sql
    assert "kind='final_render'" in sql
    assert "attempts >= :max_attempts" in sql
    assert '"leaseExpiresAt" < NOW()' in sql
    # Also reaps a legacy NULL-lease 'processing' orphan (pre-leasing rows that
    # neither the lease reclaim nor the cap-reap would otherwise touch).
    assert '"leaseExpiresAt" IS NULL' in sql
    assert "make_interval(secs => :legacy_stale)" in sql
    assert params["max_attempts"] == montage_worker.MAX_ATTEMPTS
    assert params["legacy_stale"] == montage_worker.LEGACY_STALE_SECONDS
    session.commit.assert_awaited()


def test_recovery_defaults_are_sane() -> None:
    # Lease must comfortably exceed a normal multi-minute render.
    assert montage_worker.LEASE_SECONDS >= 600
    assert montage_worker.MAX_ATTEMPTS >= 1


def test_concurrency_defaults_serial_and_clamps() -> None:
    # Default is 1 (single-process / brain plane); the media plane opts into more
    # via MONTAGE_CONCURRENCY. Never < 1, and the per-runner loop exists.
    assert montage_worker.MONTAGE_CONCURRENCY >= 1
    assert callable(montage_worker._run_one)

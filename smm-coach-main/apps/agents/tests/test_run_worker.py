"""Tests for the durable run-worker (T7.1): dispatch now QUEUES (no in-memory
task), the worker CLAIMS (FOR UPDATE SKIP LOCKED + lease + attempt cap) and
DRIVES, and a RECLAIM (attempts > 1) resumes from the checkpoint.

Convention: mock the sessionmaker / repository, assert SQL shape + behavior, no
live DB / no real graph.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.graphs import dispatcher
from app.runs import repository
from app.workers import run_worker


class _Result:
    def __init__(self, row: Any) -> None:
        self._row = row

    def mappings(self) -> _Result:
        return self

    def first(self) -> Any:
        return self._row


def _session(row: Any) -> tuple[MagicMock, AsyncMock]:
    execute = AsyncMock(return_value=_Result(row))
    session = MagicMock()
    session.execute = execute
    session.commit = AsyncMock()
    return session, execute


# ── claim_run ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_run_claims_bumps_attempts_and_leases() -> None:
    row = {
        "id": "r1",
        "tenantId": "t1",
        "userId": "u1",
        "workflow": "roadmap_generation",
        "threadId": "th1",
        "input": {"x": 1},
        "attempts": 1,
    }
    session, execute = _session(row)

    out = await repository.claim_run(session, lease_seconds=600, max_attempts=3)

    assert out == {
        "run_id": "r1",
        "tenant_id": "t1",
        "user_id": "u1",
        "workflow": "roadmap_generation",
        "thread_id": "th1",
        "payload": {"x": 1},
        "attempts": 1,
    }
    sql = str(execute.await_args.args[0])
    assert "status = 'running'" in sql
    assert "attempts = attempts + 1" in sql
    assert "make_interval(secs => :lease_seconds)" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql  # race-safe across pollers
    # Reclaims a fresh queued row OR an expired-lease running row BELOW the cap.
    assert "status = 'queued'" in sql
    assert '"leaseExpiresAt" < NOW()' in sql
    assert "attempts < :max_attempts" in sql
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_claim_run_returns_none_when_nothing_runnable() -> None:
    session, _ = _session(None)
    assert await repository.claim_run(session, lease_seconds=600, max_attempts=3) is None


# ── dispatch_workflow now only QUEUES ───────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_workflow_queues_without_running_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}

    async def fake_create_run(**kw: Any) -> None:
        created.update(kw)

    monkeypatch.setattr(dispatcher, "create_run", fake_create_run)
    monkeypatch.setattr(dispatcher, "fetch_run", AsyncMock(return_value=None))

    run_id, thread_id = await dispatcher.dispatch_workflow(
        tenant_id="t1", user_id="u1", workflow="wf", thread_id=None, payload={"a": 1}, idempotency_key=None
    )
    # It enqueues (create_run) and returns immediately — no graph compiled/run here
    # (that would need compile_graph; the run_worker drives it later).
    assert created["workflow"] == "wf"
    assert created["payload"] == {"a": 1}
    assert created["status"] != "running" if "status" in created else True
    # Per-run thread (run_id suffix) so a 2nd+ regenerate can't inherit prior operator.add state.
    assert run_id and thread_id == f"t1:u1:wf:{run_id}"


@pytest.mark.asyncio
async def test_dispatch_workflow_idempotent_returns_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    # A TRUE replay: same tenant AND same workflow → short-circuit to the existing run.
    monkeypatch.setattr(
        dispatcher,
        "fetch_run",
        AsyncMock(
            return_value={
                "runId": "k1", "threadId": "th", "status": "running",
                "tenantId": "t1", "workflow": "wf",
            }
        ),
    )
    create = AsyncMock()
    monkeypatch.setattr(dispatcher, "create_run", create)

    run_id, thread_id = await dispatcher.dispatch_workflow(
        tenant_id="t1", user_id="u1", workflow="wf", thread_id=None, payload={}, idempotency_key="k1"
    )
    assert (run_id, thread_id) == ("k1", "th")
    create.assert_not_called()  # idempotent hit → no second enqueue


@pytest.mark.asyncio
async def test_dispatch_workflow_idempotency_collision_does_not_leak_cross_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key collision across tenants MUST NOT return the foreign run. Tenant t2
    sends a key that already exists for tenant t1 — the dispatcher must fall
    through to a FRESH run (new id, enqueued), never hand back t1's run."""
    monkeypatch.setattr(
        dispatcher,
        "fetch_run",
        AsyncMock(
            return_value={
                "runId": "k1", "threadId": "t1:u1:wf", "status": "running",
                "tenantId": "t1", "workflow": "wf",  # owned by ANOTHER tenant
            }
        ),
    )
    created: dict[str, Any] = {}

    async def fake_create_run(**kw: Any) -> None:
        created.update(kw)

    monkeypatch.setattr(dispatcher, "create_run", fake_create_run)

    run_id, thread_id = await dispatcher.dispatch_workflow(
        tenant_id="t2", user_id="u2", workflow="wf", thread_id=None, payload={}, idempotency_key="k1"
    )
    # Did NOT return t1's run; minted a fresh id and enqueued under t2.
    assert run_id != "k1"
    assert created.get("run_id") == run_id
    assert created.get("tenant_id") == "t2"
    # thread_id is derived from the FINAL (post-collision) run_id, not the foreign one.
    assert thread_id == f"t2:u2:wf:{run_id}"


@pytest.mark.asyncio
async def test_dispatch_workflow_idempotency_collision_same_tenant_diff_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same tenant but a DIFFERENT workflow under the same key is also a collision
    (not a replay) — must mint a fresh run rather than returning the other run."""
    monkeypatch.setattr(
        dispatcher,
        "fetch_run",
        AsyncMock(
            return_value={
                "runId": "k1", "threadId": "t1:u1:roadmap_generation", "status": "running",
                "tenantId": "t1", "workflow": "roadmap_generation",
            }
        ),
    )
    create = AsyncMock()
    monkeypatch.setattr(dispatcher, "create_run", create)

    run_id, _ = await dispatcher.dispatch_workflow(
        tenant_id="t1", user_id="u1", workflow="content_review", thread_id=None, payload={}, idempotency_key="k1"
    )
    assert run_id != "k1"
    create.assert_called_once()


@pytest.mark.asyncio
async def test_two_dispatches_same_workflow_get_distinct_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    # Core of the per-run-thread fix: two runs of the SAME (tenant,user,workflow) must land on
    # DIFFERENT LangGraph checkpoint threads, so the 2nd regenerate never inherits the 1st run's
    # operator.add accumulators (summed cost / rejected_tasks >= _MAX_REWRITES / notes bloat).
    monkeypatch.setattr(dispatcher, "create_run", AsyncMock())
    monkeypatch.setattr(dispatcher, "fetch_run", AsyncMock(return_value=None))
    r1, t1 = await dispatcher.dispatch_workflow(
        tenant_id="t", user_id="u", workflow="content_review", thread_id=None, payload={}, idempotency_key=None
    )
    r2, t2 = await dispatcher.dispatch_workflow(
        tenant_id="t", user_id="u", workflow="content_review", thread_id=None, payload={}, idempotency_key=None
    )
    assert r1 != r2
    assert t1 != t2  # distinct threads → no shared checkpoint state
    assert t1.endswith(r1) and t2.endswith(r2)
    # An explicit caller thread_id still wins (crash-reclaim / deliberate resume).
    _, t3 = await dispatcher.dispatch_workflow(
        tenant_id="t", user_id="u", workflow="content_review", thread_id="explicit", payload={}, idempotency_key=None
    )
    assert t3 == "explicit"


# ── drive_run resume semantics ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_drive_run_fresh_vs_reclaim_resume_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    async def fake_run(state: Any, thread_id: str, *, resume: bool = False, lease_seconds: int = 600) -> None:
        calls.append((state["workflow"], resume))

    monkeypatch.setattr(dispatcher, "_run", fake_run)
    base = {"run_id": "r", "tenant_id": "t", "user_id": "u", "workflow": "wf", "thread_id": "th", "payload": {}}

    await dispatcher.drive_run({**base, "attempts": 1})  # fresh claim
    await dispatcher.drive_run({**base, "attempts": 2})  # reclaim

    assert calls == [("wf", False), ("wf", True)]


# ── run_worker._run_one ─────────────────────────────────────────────────────


class _CM:
    async def __aenter__(self) -> _CM:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None


@pytest.mark.asyncio
async def test_run_one_drives_a_claim_then_reports_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: list[Any] = [
        {"run_id": "r", "tenant_id": "t", "user_id": "u", "workflow": "wf", "thread_id": "th", "payload": {}, "attempts": 1},
        None,
    ]

    async def fake_claim(session: Any, **kw: Any) -> Any:
        return queue.pop(0)

    driven: list[str] = []

    async def fake_drive(claim: dict[str, Any], **kw: Any) -> None:
        driven.append(claim["run_id"])

    monkeypatch.setattr(run_worker, "get_sessionmaker", lambda: (lambda: _CM()))
    monkeypatch.setattr(run_worker, "claim_run", fake_claim)
    monkeypatch.setattr(run_worker, "drive_run", fake_drive)

    assert await run_worker._run_one() is True  # claimed + drove r
    assert driven == ["r"]
    assert await run_worker._run_one() is False  # queue empty → idle


def test_run_worker_defaults_are_sane() -> None:
    assert run_worker.LEASE_SECONDS >= 60
    assert run_worker.MAX_ATTEMPTS >= 1
    assert run_worker.CONCURRENCY >= 1

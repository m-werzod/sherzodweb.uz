"""Tests for `tenant_top_hooks` — the per-tenant hook bank used by the
scriptwriter to keep voice consistency across published content.

We don't spin up a real DB here; the helper's logic boils down to "run
a SQL, shape the rows". Patch the sessionmaker so the test asserts the
PARAMETERS we pass to the query (tenant scope, exclusion, limit) and
the SHAPE of what comes back. A real DB integration test would belong
in a separate suite.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.memory import tenant_history


class _MappingRows:
    """Stand-in for SQLAlchemy's `result.mappings()` so we don't need a live DB."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _MappingRows:
        return _MappingRows(self._rows)


def _patch_session(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> MagicMock:
    """Wire `get_sessionmaker()` to a context-manager that returns a session
    whose `execute` resolves to a result wrapping `rows`. Returns the
    execute mock so tests can assert on bound parameters.
    """
    execute_mock = AsyncMock(return_value=_Result(rows))
    session = MagicMock()
    session.execute = execute_mock
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    sm = MagicMock(return_value=cm)
    monkeypatch.setattr(tenant_history, "get_sessionmaker", lambda: sm)
    return execute_mock


@pytest.mark.asyncio
async def test_returns_empty_for_zero_limit() -> None:
    out = await tenant_history.tenant_top_hooks(tenant_id="t1", limit=0)
    assert out == []


@pytest.mark.asyncio
async def test_shape_and_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "title": "Reel 1",
            "hook": "Hook A",
            "type": "reel",
            "actualMetrics": {"views": 2500, "likes": 80, "comments": 5, "plays": 2200},
            "perf_score": 2500,
        },
        # Oversize fields — the helper must clip title at 160 and hook at 280.
        {
            "title": "X" * 300,
            "hook": "Y" * 400,
            "type": "post",
            "actualMetrics": None,
            "perf_score": 0,
        },
        # Rows with empty hooks are silently dropped (a published task with an
        # empty hook would just noise the LLM prompt).
        {"title": "Reel 3", "hook": "", "type": "reel", "actualMetrics": None, "perf_score": 0},
        {"title": "Reel 4", "hook": None, "type": "reel", "actualMetrics": None, "perf_score": 0},
    ]
    _patch_session(monkeypatch, rows)
    out = await tenant_history.tenant_top_hooks(tenant_id="t1", limit=10)
    assert len(out) == 2
    assert out[0]["title"] == "Reel 1"
    assert out[0]["hook"] == "Hook A"
    assert out[0]["type"] == "reel"
    assert out[0]["perfScore"] == 2500
    assert out[0]["metrics"] == {"likes": 80, "views": 2500, "plays": 2200, "comments": 5}
    # Truncation still kicks in regardless of perf score.
    assert len(out[1]["title"]) == 160
    assert len(out[1]["hook"]) == 280
    # actualMetrics=None → empty metrics dict, score 0 (recency tie-break).
    assert out[1]["metrics"] == {"likes": 0, "views": 0, "plays": 0, "comments": 0}
    assert out[1]["perfScore"] == 0


@pytest.mark.asyncio
async def test_passes_tenant_and_exclude_to_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_mock = _patch_session(monkeypatch, [])
    await tenant_history.tenant_top_hooks(
        tenant_id="tenant-abc",
        exclude_task_id="task-xyz",
        limit=3,
    )
    # SQLAlchemy text() params: positional (clause, params). Our helper passes
    # the params dict as the second arg.
    assert execute_mock.await_count == 1
    _clause, params = execute_mock.await_args.args
    assert params["tid"] == "tenant-abc"
    assert params["ex_id"] == "task-xyz"
    assert params["lim"] == 3


@pytest.mark.asyncio
async def test_db_failure_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A query exception must not propagate into the agent loop — the helper
    swallows + logs + returns ``[]`` so script generation continues without
    the hook bank."""
    def _boom() -> None:
        raise RuntimeError("db connection refused")

    monkeypatch.setattr(tenant_history, "get_sessionmaker", _boom)
    out = await tenant_history.tenant_top_hooks(tenant_id="t1", limit=3)
    assert out == []

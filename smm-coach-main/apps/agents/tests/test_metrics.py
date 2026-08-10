"""Tests for the Prometheus metrics module — exposition format, counter
increments, and the on-scrape gauge collection (mocked DB per convention)."""
from __future__ import annotations

from typing import Any

import pytest

from app import metrics


def test_render_exposes_all_metric_families() -> None:
    metrics.WORKER_RESTARTS.labels(worker="forecast").inc()
    metrics.RENDER_FAILURES.inc(2)
    metrics.RUNS_REAPED.inc()
    metrics.MONTAGE_QUEUE_DEPTH.set(5)
    body, content_type = metrics.render()
    text = body.decode()
    assert "smm_worker_restarts_total" in text
    assert 'worker="forecast"' in text
    assert "smm_montage_render_failures_total" in text
    assert "smm_agent_runs_reaped_total" in text
    assert "smm_montage_queue_depth" in text
    assert content_type.startswith("text/plain")


class _Result:
    def __init__(self, scalar: Any = None, first: Any = None) -> None:
        self._scalar = scalar
        self._first = first

    def scalar(self) -> Any:
        return self._scalar

    def first(self) -> Any:
        return self._first


class _Session:
    def __init__(self) -> None:
        self._calls = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, *a: object, **k: object) -> _Result:
        self._calls += 1
        # 1st query = montage queue depth (scalar); 2nd = (queued, running) tuple.
        return _Result(scalar=3) if self._calls == 1 else _Result(first=(7, 2))


@pytest.mark.asyncio
async def test_collect_gauges_sets_values_from_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics, "get_sessionmaker", lambda: (lambda: _Session()))
    await metrics.collect_gauges()
    assert metrics.MONTAGE_QUEUE_DEPTH._value.get() == 3
    assert metrics.AGENT_RUNS_QUEUED._value.get() == 7
    assert metrics.AGENT_RUNS_RUNNING._value.get() == 2


@pytest.mark.asyncio
async def test_collect_gauges_swallows_db_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise RuntimeError("db down")

    monkeypatch.setattr(metrics, "get_sessionmaker", boom)
    # A scrape must never fail because the DB hiccuped.
    await metrics.collect_gauges()

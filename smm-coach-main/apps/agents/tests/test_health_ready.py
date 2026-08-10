"""Tests for the /ready readiness probe: Postgres is the hard gate (503 pulls the
container from rotation), Redis is soft (a blip degrades SSE but the HMAC API still
serves, so it must not 503 the whole container)."""
from __future__ import annotations

import json
from typing import Any

import pytest

from app.api import health


class _Conn:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    async def __aenter__(self) -> _Conn:
        if self._fail:
            raise RuntimeError("db down")
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def execute(self, *_: Any) -> None:
        return None


class _Engine:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    def connect(self) -> _Conn:
        return _Conn(self._fail)


class _Redis:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    async def ping(self) -> bool:
        if self._fail:
            raise RuntimeError("redis down")
        return True


def _body(resp: Any) -> dict[str, Any]:
    return json.loads(resp.body)


@pytest.mark.asyncio
async def test_ready_ok_when_all_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "get_engine", lambda: _Engine())
    monkeypatch.setattr(health, "redis_client", lambda: _Redis())
    resp = await health.ready()
    assert resp.status_code == 200
    b = _body(resp)
    assert b["status"] == "ok"
    assert b["deps"]["postgres"] == "ok"
    assert b["deps"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_ready_503_when_postgres_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "get_engine", lambda: _Engine(fail=True))
    monkeypatch.setattr(health, "redis_client", lambda: _Redis())
    resp = await health.ready()
    assert resp.status_code == 503  # hard gate
    b = _body(resp)
    assert b["status"] == "unready"
    assert "down" in b["deps"]["postgres"]


@pytest.mark.asyncio
async def test_ready_stays_200_when_only_redis_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "get_engine", lambda: _Engine())
    monkeypatch.setattr(health, "redis_client", lambda: _Redis(fail=True))
    resp = await health.ready()
    assert resp.status_code == 200  # redis is soft — don't flap the container
    b = _body(resp)
    assert b["deps"]["redis"].startswith("degraded")


@pytest.mark.asyncio
async def test_liveness_is_static() -> None:
    assert await health.health() == {"status": "ok"}

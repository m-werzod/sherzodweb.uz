"""tracker_scheduler must dispatch each tenant's pulse with a DETERMINISTIC
idempotency key, so two agents replicas (or a rolling-deploy overlap) ticking in
the same window produce the same run id and the dispatcher dedups the duplicate
— instead of double-running every tenant's tracker_pulse and doubling LLM spend.

Suite convention: mock the sessionmaker + dispatch, assert the key, no live DB.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers import tracker_scheduler


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


def _patch_session(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_Result(rows))
    session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(tracker_scheduler, "get_sessionmaker", lambda: MagicMock(return_value=cm))


@pytest.mark.asyncio
async def test_pulse_uses_deterministic_idempotency_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(
        monkeypatch,
        [{"tenant_id": "tn1", "user_id": "u1"}, {"tenant_id": "tn2", "user_id": "u2"}],
    )
    calls: list[dict[str, Any]] = []

    async def fake_dispatch(**kw: Any) -> tuple[str, str]:
        calls.append(kw)
        return ("rid", "tid")

    monkeypatch.setattr(tracker_scheduler, "dispatch_workflow", fake_dispatch)
    monkeypatch.setattr(tracker_scheduler.telegram, "send", lambda *a, **k: None)

    await tracker_scheduler._enqueue_pulses()
    await tracker_scheduler._enqueue_pulses()  # same window → identical keys

    assert len(calls) == 4
    keys = [c["idempotency_key"] for c in calls]
    assert all(k is not None for k in keys)  # never None (the double-fire bug)
    assert keys[0].startswith("tracker-pulse:tn1:")
    assert keys[1].startswith("tracker-pulse:tn2:")
    # Two ticks in the same 6h window produce the same key per tenant → deduped.
    assert keys[0] == keys[2]
    assert keys[1] == keys[3]
    # Distinct tenants get distinct keys.
    assert keys[0] != keys[1]

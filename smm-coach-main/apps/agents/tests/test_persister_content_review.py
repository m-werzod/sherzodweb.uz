"""content_review UPDATE must WRITE the enriched JSON columns even when empty.

The bug (caught by the remediation review): `validated_json(...) if shot_list else
None` treated a legit empty []/{} as falsy → None → SQL COALESCE kept STALE data
(e.g. a reel→action change left the old shots in place). These four fields are
ALWAYS produced by the enrichment (defaulted to []/{}), so they must be written
unconditionally — matching the INSERT path.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.graphs.nodes import roadmap_persister


class _Result:
    def mappings(self) -> _Result:
        return self

    def first(self) -> Any:
        return None


class _Session:
    def __init__(self, calls: list) -> None:
        self._calls = calls

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, q: object, params: object = None) -> _Result:
        self._calls.append((str(q), params))
        return _Result()

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_update_writes_empty_json_columns_not_null(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    monkeypatch.setattr(roadmap_persister, "get_sessionmaker", lambda: (lambda: _Session(calls)))
    monkeypatch.setattr(roadmap_persister, "emit_message", AsyncMock())

    state = {
        "tenant_id": "t1",
        "user_id": "u1",
        "run_id": "r1",
        "task_id": "task1",
        "workflow": "content_review",
        "prev_status": "in_progress",
    }
    # A reel whose enrichment produced EMPTY shots/timeline/predict/hookMeta — must
    # still overwrite the DB (not preserve stale values via COALESCE).
    task = {
        "type": "reel",
        "title": "X",
        "hook": "h",
        "script_md": "s",
        "shot_list": [],
        "script_timeline": [],
        "predict_evidence": {},
        "hook_meta": {},
    }

    await roadmap_persister._update_single_task(state, [task])  # type: ignore[arg-type]

    upd = next(p for (q, p) in calls if "UPDATE content_tasks" in q and p is not None)
    assert upd["shots"] == "[]"  # empty list WRITTEN, not None
    assert upd["timeline"] == "[]"
    assert upd["predict"] == "{}"
    assert upd["hook_meta"] == "{}"

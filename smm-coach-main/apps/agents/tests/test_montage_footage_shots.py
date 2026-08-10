"""AG-2 — the montage worker threads the footage_analyzer's VISION-detected scene boundaries
(meta.footageMap.shots[].src_start) into build_edl, so cuts land on the same shots the Gemini pass
saw instead of a redundant second detect_shots on the normalized clip. Lock the loader's parsing."""
from __future__ import annotations

from typing import Any

from app.workers.montage_worker import _footage_shot_times


class _Result:
    def __init__(self, val: Any) -> None:
        self._val = val

    def scalar_one_or_none(self) -> Any:
        return self._val


class _Session:
    """Minimal stand-in: returns a canned meta->footageMap->shots payload from execute()."""

    def __init__(self, val: Any) -> None:
        self._val = val

    async def execute(self, *_a: Any, **_k: Any) -> _Result:
        return _Result(self._val)


async def test_extracts_boundaries_excluding_leading_zero() -> None:
    shots = [
        {"index": 0, "src_start": 0.0, "src_end": 3.2},
        {"index": 1, "src_start": 3.2, "src_end": 7.5},
        {"index": 2, "src_start": 7.5, "src_end": 12.0},
    ]
    out = await _footage_shot_times(_Session(shots), "t1")
    assert out == [3.2, 7.5]  # the first shot starts at 0 — not a scene boundary


async def test_parses_jsonb_returned_as_string() -> None:
    # psycopg may hand back jsonb as a str depending on the adapter — the loader must json.loads it.
    raw = '[{"index":0,"src_start":0.0,"src_end":4.0},{"index":1,"src_start":4.0,"src_end":9.0}]'
    out = await _footage_shot_times(_Session(raw), "t1")
    assert out == [4.0]


async def test_dedupes_and_sorts() -> None:
    shots = [
        {"index": 0, "src_start": 0.0, "src_end": 6.0},
        {"index": 1, "src_start": 6.0, "src_end": 3.0},  # malformed order — still extract starts
        {"index": 2, "src_start": 3.0, "src_end": 9.0},
    ]
    out = await _footage_shot_times(_Session(shots), "t1")
    assert out == [3.0, 6.0]


async def test_empty_when_no_footage_map() -> None:
    assert await _footage_shot_times(_Session(None), "t1") == []
    assert await _footage_shot_times(_Session("not-json"), "t1") == []
    assert await _footage_shot_times(_Session({"unexpected": "shape"}), "t1") == []

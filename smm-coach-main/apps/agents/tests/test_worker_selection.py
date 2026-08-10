"""Tests for WORKER_SET plane selection — the montage render runs on its own
deployable (media plane) so its OOM can't take the API down, while the cron
singletons run on exactly one plane (no double-fire)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.main import _select_workers

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_NAMES = ["tracker_scheduler", "daily_snapshot", "coach_supervisor", "montage_worker", "run_reaper"]


def _noop() -> Awaitable[None]:  # pragma: no cover - never awaited
    raise NotImplementedError


_ALL: list[tuple[str, Callable[[], Awaitable[None]]]] = [(n, _noop) for n in _NAMES]


def _names(ws: list[tuple[str, Callable[[], Awaitable[None]]]]) -> list[str]:
    return [w[0] for w in ws]


def test_all_runs_everything() -> None:
    assert _names(_select_workers(_ALL, "all")) == _NAMES


def test_unknown_value_defaults_to_all() -> None:
    assert _names(_select_workers(_ALL, "weird")) == _NAMES


def test_media_runs_only_montage() -> None:
    assert _names(_select_workers(_ALL, "media")) == ["montage_worker"]


def test_brain_runs_everything_except_montage() -> None:
    got = _names(_select_workers(_ALL, "brain"))
    assert "montage_worker" not in got
    # the cron singletons + the LLM-run reaper stay on the brain plane
    assert "tracker_scheduler" in got
    assert "run_reaper" in got
    assert "coach_supervisor" in got


def test_media_and_brain_partition_the_set() -> None:
    media = set(_names(_select_workers(_ALL, "media")))
    brain = set(_names(_select_workers(_ALL, "brain")))
    assert media.isdisjoint(brain)
    assert media | brain == set(_NAMES)

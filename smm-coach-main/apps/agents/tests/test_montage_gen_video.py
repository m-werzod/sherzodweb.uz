"""Faza B — gen_video.generate_broll_url: empty-prompt + no-key inertness (no network)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.montage.gen_video import generate_broll_url

if TYPE_CHECKING:
    import pytest


def test_generate_empty_prompt_returns_none() -> None:
    assert generate_broll_url("") is None
    assert generate_broll_url("   ") is None


def test_generate_without_key_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    # No FAL_KEY → run_queue_video short-circuits, returns None (montage falls back to stock).
    monkeypatch.setattr("app.montage.fal_client.fal_api_key", lambda: None)
    assert generate_broll_url("a vivid neon city at night") is None

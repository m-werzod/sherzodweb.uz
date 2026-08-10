"""Faza C — decor: matte_subject + generate_background required-args + no-key inertness (no network)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.montage.decor import generate_background, matte_subject

if TYPE_CHECKING:
    import pytest


def test_requires_input() -> None:
    assert matte_subject("") is None
    assert matte_subject("   ") is None
    assert generate_background("") is None
    assert generate_background("   ") is None


def test_without_key_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.montage.fal_client.fal_api_key", lambda: None)
    assert matte_subject("https://x/v.mp4") is None
    assert generate_background("a cozy neon studio backdrop") is None

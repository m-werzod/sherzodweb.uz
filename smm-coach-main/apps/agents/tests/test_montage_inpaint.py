"""Faza D — inpaint.inpaint_video: required-args + no-key inertness (no network)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.montage.inpaint import inpaint_local, inpaint_video

if TYPE_CHECKING:
    import pytest


def test_inpaint_requires_url_and_remove() -> None:
    assert inpaint_video("", remove="person") is None
    assert inpaint_video("https://x/v.mp4", remove="") is None
    assert inpaint_video("   ", remove="   ") is None


def test_inpaint_without_key_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.montage.fal_client.fal_api_key", lambda: None)
    assert inpaint_video("https://x/v.mp4", remove="person in the background") is None


def test_inpaint_local_requires_remove() -> None:
    assert inpaint_local("no_such_clip.mp4", remove="") is None


def test_inpaint_local_without_key_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    # No key → upload_file short-circuits before any network/upload → None.
    monkeypatch.setattr("app.montage.fal_client.fal_api_key", lambda: None)
    assert inpaint_local("no_such_clip.mp4", remove="person") is None

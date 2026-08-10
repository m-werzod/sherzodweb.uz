"""Faza B/D — fal_client: result-URL extraction (pure) + inert-without-key gating (no network)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.montage.fal_client import extract_image_url, extract_video_url, run_queue_video

if TYPE_CHECKING:
    import pytest


def test_extract_video_url_common_shapes() -> None:
    assert extract_video_url({"video": {"url": "u1"}}) == "u1"
    assert extract_video_url({"video_url": "u2"}) == "u2"
    assert extract_video_url({"videos": [{"url": "u3"}]}) == "u3"
    assert extract_video_url({"url": "u4"}) == "u4"


def test_extract_image_url_common_shapes() -> None:
    assert extract_image_url({"images": [{"url": "i1"}]}) == "i1"
    assert extract_image_url({"image": {"url": "i2"}}) == "i2"
    assert extract_image_url({"image_url": "i3"}) == "i3"
    assert extract_image_url({"url": "i4"}) == "i4"
    assert extract_image_url({"images": []}) is None
    assert extract_image_url("bad") is None


def test_extract_video_url_rejects_bad_shapes() -> None:
    assert extract_video_url({"nope": 1}) is None
    assert extract_video_url("not a dict") is None
    assert extract_video_url({"video": {"no_url": 1}}) is None
    assert extract_video_url({"videos": []}) is None
    assert extract_video_url({"video_url": 123}) is None


def test_run_queue_video_without_key_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    # No FAL_KEY → no network call, returns None.
    monkeypatch.setattr("app.montage.fal_client.fal_api_key", lambda: None)
    assert run_queue_video("fal-ai/whatever", {"prompt": "x"}) is None

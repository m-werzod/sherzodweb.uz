"""HeyGen client — pure helpers + fail-soft gating (no network; mirrors test_montage_fal_client)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.montage.heygen_client import (
    build_avatar_body,
    build_translate_body,
    dimensions_for,
    extract_status,
    extract_translate_status,
    extract_translate_url,
    extract_video_url,
    generate_avatar_video,
    translate_video,
)

if TYPE_CHECKING:
    import pytest


def test_dimensions_for_aspects() -> None:
    assert dimensions_for("vertical") == {"width": 1080, "height": 1920}
    assert dimensions_for("horizontal") == {"width": 1920, "height": 1080}
    assert dimensions_for("square") == {"width": 1080, "height": 1080}
    # unknown / empty → vertical 9:16 (reels default)
    assert dimensions_for("bogus") == {"width": 1080, "height": 1920}
    assert dimensions_for("") == {"width": 1080, "height": 1920}


def test_extract_status_shapes() -> None:
    assert extract_status({"data": {"status": "completed"}}) == "completed"
    assert extract_status({"status": "processing"}) == "processing"  # flat fallback
    assert extract_status({"data": {}}) is None
    assert extract_status({}) is None
    assert extract_status(None) is None
    assert extract_status("nope") is None


def test_extract_video_url_shapes() -> None:
    assert extract_video_url({"data": {"video_url": "https://x/v.mp4"}}) == "https://x/v.mp4"
    assert extract_video_url({"video_url": "https://x/y.mp4"}) == "https://x/y.mp4"  # flat fallback
    assert extract_video_url({"data": {"status": "processing"}}) is None  # not ready yet
    assert extract_video_url({}) is None
    assert extract_video_url(None) is None


def test_build_avatar_body_audio_mode() -> None:
    body = build_avatar_body("av_1", audio_url="https://x/a.mp3", aspect="vertical")
    inp = body["video_inputs"][0]
    assert inp["character"] == {"type": "avatar", "avatar_id": "av_1", "avatar_style": "normal"}
    assert inp["voice"] == {"type": "audio", "audio_url": "https://x/a.mp3"}
    assert body["dimension"] == {"width": 1080, "height": 1920}


def test_build_avatar_body_text_mode_with_voice_id() -> None:
    body = build_avatar_body("av_2", script_text="Salom dunyo", voice_id="vc_9", aspect="square")
    voice = body["video_inputs"][0]["voice"]
    assert voice["type"] == "text"
    assert voice["input_text"] == "Salom dunyo"
    assert voice["voice_id"] == "vc_9"
    assert body["dimension"] == {"width": 1080, "height": 1080}


def test_build_avatar_body_audio_wins_over_text() -> None:
    # audio_url is the preferred lip-sync source; when present, text is ignored.
    body = build_avatar_body("av_3", audio_url="https://x/a.mp3", script_text="ignored")
    assert body["video_inputs"][0]["voice"]["type"] == "audio"


def test_build_avatar_body_caps_long_script() -> None:
    body = build_avatar_body("av_4", script_text="x" * 6000)
    assert len(body["video_inputs"][0]["voice"]["input_text"]) == 4900


def test_generate_avatar_video_fail_soft_gating(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force no key → fully offline + deterministic regardless of .env (conftest loads HEYGEN_API_KEY).
    monkeypatch.setattr("app.montage.heygen_client.heygen_api_key", lambda: None)
    assert generate_avatar_video(avatar_id="av_1", audio_url="https://x/a.mp3") is None
    # Missing avatar_id / no voice source → None before any request (key-independent guard).
    assert generate_avatar_video(avatar_id="", audio_url="https://x/a.mp3") is None
    assert generate_avatar_video(avatar_id="av_1") is None  # no audio_url and no script_text


# ── Video Translation (localization) ──


def test_extract_translate_status_shapes() -> None:
    assert extract_translate_status({"data": {"status": "success"}}) == "success"
    assert extract_translate_status({"status": "running"}) == "running"
    assert extract_translate_status({"data": {}}) is None
    assert extract_translate_status(None) is None


def test_extract_translate_url_shapes() -> None:
    assert extract_translate_url({"data": {"url": "https://x/ru.mp4"}}) == "https://x/ru.mp4"
    assert extract_translate_url({"data": {"video_url": "https://x/v.mp4"}}) == "https://x/v.mp4"
    assert extract_translate_url({"url": "https://x/flat.mp4"}) == "https://x/flat.mp4"
    assert extract_translate_url({"data": {"status": "running"}}) is None  # not ready
    assert extract_translate_url({}) is None
    assert extract_translate_url("bad") is None


def test_build_translate_body_keeps_duration_locked() -> None:
    body = build_translate_body("https://x/src.mp4", "Russian")
    assert body["video_url"] == "https://x/src.mp4"
    assert body["output_language"] == "Russian"
    assert body["translate_audio_only"] is False
    # CRITICAL: default dynamic_duration=False keeps the translated clip 1:1 with the source.
    assert body["enable_dynamic_duration"] is False
    assert build_translate_body("u", "English", dynamic_duration=True)["enable_dynamic_duration"] is True


def test_translate_video_fail_soft_gating(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.montage.heygen_client.heygen_api_key", lambda: None)
    assert translate_video("https://x/src.mp4", "Russian") is None  # no key → offline, None
    # missing video_url / output_language → None before any request (key-independent guard).
    assert translate_video("", "Russian") is None
    assert translate_video("https://x/src.mp4", "") is None

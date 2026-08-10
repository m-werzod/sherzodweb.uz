"""Stage 9c music generation — fal.ai audio URL extraction + energy→prompt mapping.
Pure pieces; the network call + download are fail-soft and exercised in prod."""
from __future__ import annotations

import pytest

from app.montage.fal_client import extract_audio_url
from app.montage.music import music_gen_enabled, music_prompt


@pytest.fixture
def _clean_env(monkeypatch):
    monkeypatch.delenv("MONTAGE_MUSIC_GEN", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)


def test_music_gen_default_on_when_fal_key_present(_clean_env, monkeypatch):
    # Core promise: background music by default once a fal key exists (was silent before).
    monkeypatch.setenv("FAL_KEY", "k")
    assert music_gen_enabled() is True


def test_music_gen_off_without_fal_key(_clean_env):
    assert music_gen_enabled() is False


def test_explicit_flag_overrides_key_default(_clean_env, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    monkeypatch.setenv("MONTAGE_MUSIC_GEN", "0")
    assert music_gen_enabled() is False  # explicit off beats the key default
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.setenv("MONTAGE_MUSIC_GEN", "1")
    assert music_gen_enabled() is True  # explicit on even without key (gen stays fail-soft)


def test_extract_audio_file_shape():
    # The shape stable-audio actually returns (confirmed live): {"audio_file":{"url":...}}.
    assert extract_audio_url({"audio_file": {"url": "https://x/a.wav"}}) == "https://x/a.wav"


def test_extract_audio_shape_and_url_fallbacks():
    assert extract_audio_url({"audio": {"url": "https://x/b.wav"}}) == "https://x/b.wav"
    assert extract_audio_url({"audio_url": "https://x/c.wav"}) == "https://x/c.wav"
    assert extract_audio_url({"url": "https://x/d.wav"}) == "https://x/d.wav"


def test_extract_audio_none_on_garbage():
    assert extract_audio_url(None) is None
    assert extract_audio_url({}) is None
    assert extract_audio_url({"video": {"url": "x"}}) is None


def test_music_prompt_is_instrumental_no_vocals():
    for e in (None, 0.0, 0.5, 1.0):
        p = music_prompt(e)
        assert "instrumental" in p and "no vocals" in p


def test_music_prompt_varies_by_energy():
    assert "energetic" in music_prompt(0.9)
    assert "calm" in music_prompt(0.1) or "lo-fi" in music_prompt(0.1)

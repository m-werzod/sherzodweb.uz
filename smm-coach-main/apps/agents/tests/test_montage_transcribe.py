"""Transcript cache + rich retention (palmier #5). The Whisper API call is mocked; what's pinned
is the cache-by-upload-identity behaviour (skip Whisper on re-render) + the END-time derivation."""
from __future__ import annotations

from typing import Any

import pytest

from app.montage import transcribe

_WORDS = [
    {"text": "bir", "start": 0.0, "end": 0.5},
    {"text": "ikki", "start": 0.5, "end": 1.0},
    {"text": "uch", "start": 1.0, "end": 1.5},
]


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    transcribe._CACHE.clear()
    yield
    transcribe._CACHE.clear()


def test_word_times_derives_sorted_end_times(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcribe, "_run_whisper", lambda _p, **_k: list(_WORDS))
    assert transcribe.word_times("x", cache_key=None) == [0.5, 1.0, 1.5]


def test_transcribe_caches_by_upload_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake(_p: str, **_k: Any) -> list[dict[str, Any]]:
        calls["n"] += 1
        return list(_WORDS)

    monkeypatch.setattr(transcribe, "_run_whisper", fake)
    a = transcribe.transcribe_words("p1", cache_key="upload-1")
    b = transcribe.transcribe_words("p1", cache_key="upload-1")
    assert calls["n"] == 1  # second call served from cache — no Whisper
    assert a == b == _WORDS


def test_transient_failure_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake(_p: str, **_k: Any) -> None:
        calls["n"] += 1
        return  # transient API failure

    monkeypatch.setattr(transcribe, "_run_whisper", fake)
    transcribe.transcribe_words("p", cache_key="upload-2")
    transcribe.transcribe_words("p", cache_key="upload-2")
    assert calls["n"] == 2  # failure must retry, not stick


def test_no_cache_key_always_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake(_p: str, **_k: Any) -> list[dict[str, Any]]:
        calls["n"] += 1
        return list(_WORDS)

    monkeypatch.setattr(transcribe, "_run_whisper", fake)
    transcribe.transcribe_words("p", cache_key=None)
    transcribe.transcribe_words("p", cache_key=None)
    assert calls["n"] == 2


def test_cache_returns_a_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcribe, "_run_whisper", lambda _p, **_k: [dict(w) for w in _WORDS])
    a = transcribe.transcribe_words("p", cache_key="upload-3")
    assert a is not None
    a[0]["text"] = "MUTATED"
    b = transcribe.transcribe_words("p", cache_key="upload-3")
    assert b is not None and b[0]["text"] == "bir"  # cache was not mutated by the caller


def test_strict_missing_key_raises_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # vuc-06: the user-facing /transcript path must distinguish a config failure from "no speech".
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(transcribe.TranscriptError) as exc:
        transcribe.transcribe_words("p", cache_key=None, strict=True)
    assert exc.value.reason == "not_configured"
    # Non-strict (caption-timing fallback) must stay degrade-safe: None, never raise.
    assert transcribe.transcribe_words("p", cache_key=None, strict=False) is None

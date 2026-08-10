"""Word-level speech timing for caption sync — cached (palmier TranscriptCache idea).

Proportional caption timing ignores WHERE the speaker actually talks (pauses,
pace). Here the montage worker extracts a small audio track from the normalized
clip and asks OpenAI Whisper for word-level timestamps — the real speech rhythm.
We use the word *timings* (robust) not the *text* (Whisper mangles Uzbek), so
the script text stays the source of truth; only the cadence comes from here — but
the FULL transcript (text+start+end) is retained for future use (get_transcript).

Cached by the stable UPLOAD identity, so a re-montage / A-B-aspect render of the
same clip reuses the transcript instead of paying Whisper again (the montage
editor encourages exactly those re-renders).

Degrade-safe: no OPENAI_API_KEY, an over-size clip, or any API error → returns
None and the compiler falls back to proportional timing.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"
_MAX_AUDIO_BYTES = 24 * 1024 * 1024  # Whisper's 25 MB limit, with headroom


class TranscriptError(Exception):
    """Infrastructure failure (key missing, audio-extract or Whisper API error) — distinct from a
    genuinely silent clip (which is just None). Only raised on the strict, user-facing path so the
    coach can say WHY ('xizmat sozlanmagan' vs 'nutq topilmadi') instead of always 'no speech'."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message

# Process-lifetime transcript cache keyed by the stable upload identity. The montage worker is
# long-running, so a remontage of the same clip hits this and skips the (slow, paid) Whisper call.
_CACHE: dict[str, list[dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 16


def transcribe_words(
    normalized_path: str, *, cache_key: str | None = None, strict: bool = False
) -> list[dict[str, Any]] | None:
    """Full word-level transcript [{text, start, end}] in SOURCE seconds, or None. Cached by
    `cache_key` (the upload identity) — a re-render of the same clip reuses it (no Whisper call).

    strict=True (user-facing /transcript) raises TranscriptError on infrastructure failures so the
    caller can explain the cause; strict=False (caption-timing fallback) swallows everything to None.
    """
    if cache_key:
        with _CACHE_LOCK:
            hit = _CACHE.get(cache_key)
        if hit:
            return [dict(w) for w in hit]  # copy so a caller can't mutate the cache

    words = _run_whisper(normalized_path, strict=strict)
    # Cache only REAL results — a transient API failure (None) must retry next time, not stick.
    # Store a COPY so a caller mutating the returned list can never corrupt the cache.
    if cache_key and words:
        with _CACHE_LOCK:
            _CACHE[cache_key] = [dict(w) for w in words]
            while len(_CACHE) > _CACHE_MAX:
                _CACHE.pop(next(iter(_CACHE)))
    return words


def word_times(normalized_path: str, *, cache_key: str | None = None) -> list[float] | None:
    """Per-word END times (SOURCE seconds) of the speech, or None — the real cadence that
    build_caption_windows maps script words onto. Back-compat wrapper over the cached transcript."""
    words = transcribe_words(normalized_path, cache_key=cache_key)
    if not words:
        return None
    times = sorted(float(w["end"]) for w in words if isinstance(w.get("end"), (int, float)))
    return times if len(times) >= 3 else None


def _fail(strict: bool, reason: str, message: str) -> None:
    """Infrastructure failure: raise (strict path) so the cause surfaces, else None (caption path)."""
    if strict:
        raise TranscriptError(reason, message)
    return


def _run_whisper(normalized_path: str, *, strict: bool = False) -> list[dict[str, Any]] | None:
    """Extract a small audio track and ask Whisper for word timestamps. Returns the full word
    list [{text, start, end}] (>=3 words), or None on no-speech. With strict=True, infrastructure
    failures (no key / extract / API error) raise TranscriptError instead of collapsing to None."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return _fail(strict, "not_configured", "Transkripsiya xizmati sozlanmagan.")
    with tempfile.TemporaryDirectory(prefix="stt-") as wd:
        audio = os.path.join(wd, "a.mp3")
        try:
            # Small mono 16k mp3 — a 90s clip is well under the 25 MB cap.
            subprocess.run(  # noqa: S603
                ["ffmpeg", "-hide_banner", "-y", "-i", normalized_path,  # noqa: S607
                 "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", audio],
                capture_output=True, check=True, timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            log.warning("montage.stt.audio_extract_failed", error=str(exc)[:120])
            return _fail(strict, "audio_error", "Videodan audio ajratib bo'lmadi.")
        if not os.path.exists(audio):
            return _fail(strict, "audio_error", "Videodan audio ajratib bo'lmadi.")
        if os.path.getsize(audio) > _MAX_AUDIO_BYTES:
            return _fail(strict, "too_large", "Video juda uzun — transkripsiya cheklovidan oshdi.")
        try:
            # Pin the language (default uz — the market) so Whisper decodes Uzbek properly instead
            # of auto-detect mis-firing → the captions show the REAL spoken words. WHISPER_LANG=""
            # restores auto-detect (e.g. a heavily ru/en account).
            data = {
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            }
            lang = os.getenv("WHISPER_LANG", "uz").strip()
            if lang:
                data["language"] = lang
            def _post(body: dict[str, str]) -> httpx.Response:
                with open(audio, "rb") as fh:
                    return httpx.post(
                        _OPENAI_URL,
                        headers={"Authorization": f"Bearer {key}"},
                        files={"file": ("a.mp3", fh, "audio/mpeg")},
                        data=body,
                        timeout=120,
                    )

            resp = _post(data)
            if resp.status_code == 400 and "unsupported_language" in resp.text:
                # LIVE-VERIFIED 2026-07-03: OpenAI's whisper-1 endpoint REJECTS `language=uz`
                # ("Language 'uz' is not supported") even though the Whisper model handles it —
                # this silently killed real speech timing for every montage. We consume only the
                # word TIMINGS (script text stays the source of truth), and auto-detect (it picks
                # a close cousin like azerbaijani) yields equally good timestamps — retry without.
                log.info("montage.stt.language_fallback", lang=data.get("language", ""))
                data.pop("language", None)
                resp = _post(data)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            log.warning(
                "montage.stt.api_failed",
                status=exc.response.status_code,
                body=exc.response.text[:200],
            )
            return _fail(strict, "stt_error", "Transkripsiya xizmatida xatolik — keyinroq urinib ko'ring.")
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            log.warning("montage.stt.api_failed", error=str(exc)[:160])
            return _fail(strict, "stt_error", "Transkripsiya xizmatida xatolik — keyinroq urinib ko'ring.")

    raw = payload.get("words") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return None
    words: list[dict[str, Any]] = []
    for w in raw:
        if not isinstance(w, dict) or not isinstance(w.get("end"), (int, float)):
            continue
        end = float(w["end"])
        start = float(w["start"]) if isinstance(w.get("start"), (int, float)) else end
        words.append({"text": str(w.get("word") or w.get("text") or "").strip(), "start": start, "end": end})
    if len(words) < 3:
        return None
    log.info("montage.stt.ok", words=len(words))
    return words

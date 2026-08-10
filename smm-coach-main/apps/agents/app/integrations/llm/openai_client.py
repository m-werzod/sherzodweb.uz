"""OpenAI client — Whisper, GPT-4o fallback, DALL-E backup.

We use OpenAI for three narrow things; Anthropic/Gemini cover the rest:

  1. Whisper transcription of user-uploaded video. The Python agents-side
     transcribes long files server-side (web Next.js handles short ones
     via apps/web/src/lib/transcribe/whisper.ts).

  2. GPT-4o emergency fallback when both Anthropic AND Gemini are down.
     Same prompt schema; quality good enough to keep the pipeline alive.

  3. DALL-E 3 image generation when Imagen 3 (Gemini) rate-limits us.
     Faza 2 — currently unused.

Soft-disabled when OPENAI_API_KEY is missing.
"""
from __future__ import annotations

import json
import time
from io import BytesIO
from typing import Any

import httpx
import structlog

from app.budget.guard import kill_switch_on
from app.config import get_settings
from app.runs.llm_inspector import record_llm_call

log = structlog.get_logger(__name__)


def _kill_switch_guard() -> None:
    """HARD kill switch (EMERGENCY_DISABLE_LLM): raise BEFORE any OpenAI call so
    no money is spent. Callers already handle the no-key RuntimeError, so this
    degrades along the same well-exercised path."""
    if kill_switch_on():
        raise RuntimeError("EMERGENCY_DISABLE_LLM")

OPENAI_API = "https://api.openai.com/v1"

# GPT-4o-mini pricing per 1M tokens (text only; vision input adds extra).
_GPT4O_MINI_IN = 0.15
_GPT4O_MINI_OUT = 0.60
_GPT4O_IN = 2.50
_GPT4O_OUT = 10.00


def _price_for(model: str) -> tuple[float, float]:
    if model.startswith("gpt-4o-mini"):
        return _GPT4O_MINI_IN, _GPT4O_MINI_OUT
    if model.startswith("gpt-4o"):
        return _GPT4O_IN, _GPT4O_OUT
    return 0.0, 0.0


def is_configured() -> bool:
    return get_settings().openai_api_key is not None


# ── Whisper ──────────────────────────────────────────────────────────────


async def transcribe(
    audio_bytes: bytes,
    *,
    filename: str = "audio.mp4",
    language: str | None = None,
) -> dict[str, Any]:
    """Transcribe audio/video. Returns segments with timestamps.

    Whisper accepts up to 25 MB per request. For longer clips, chunk
    client-side and concatenate segments.
    """
    s = get_settings()
    _kill_switch_guard()
    if s.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY not configured")
    files = {"file": (filename, BytesIO(audio_bytes), "application/octet-stream")}
    data: dict[str, str] = {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "timestamp_granularities[]": "segment",
    }
    if language:
        data["language"] = language
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OPENAI_API}/audio/transcriptions",
            headers={"Authorization": f"Bearer {s.openai_api_key.get_secret_value()}"},
            data=data,
            files=files,
        )
        if resp.status_code != 200:
            log.warning("openai.whisper.error", status=resp.status_code, body=resp.text[:300])
            raise RuntimeError(f"Whisper {resp.status_code}: {resp.text[:200]}")
        return resp.json()


# ── GPT-4o (fallback) ────────────────────────────────────────────────────


async def chat_text(
    *,
    model: str = "gpt-4o-mini",
    system: str,
    user: str,
    max_tokens: int = 800,
    temperature: float = 0.4,
    agent_name: str = "unknown",
) -> str:
    """Emergency fallback chat. Default model is the $0.15/$0.60 mini.
    Persists every call to llm_calls for the AI Inspector.
    """
    s = get_settings()
    _kill_switch_guard()
    if s.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY not configured")
    started_at = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OPENAI_API}/chat/completions",
                headers={
                    "Authorization": f"Bearer {s.openai_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
        latency_ms = int((time.monotonic() - started_at) * 1000)
        if resp.status_code != 200:
            await record_llm_call(
                agent=agent_name, provider="openai", model=model,
                system_prompt=system, user_message=user, response_text="",
                latency_ms=latency_ms, status="error",
                error_message=f"{resp.status_code}: {resp.text[:300]}",
            )
            raise RuntimeError(f"OpenAI {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        p_in, p_out = _price_for(model)
        cost = (in_tok * p_in + out_tok * p_out) / 1_000_000
        await record_llm_call(
            agent=agent_name, provider="openai", model=model,
            system_prompt=system, user_message=user, response_text=content,
            input_tokens=in_tok, output_tokens=out_tok,
            cost_usd=cost, latency_ms=latency_ms, status="ok",
        )
        return content
    except Exception as exc:
        if not (isinstance(exc, RuntimeError) and "OpenAI" in str(exc)):
            await record_llm_call(
                agent=agent_name, provider="openai", model=model,
                system_prompt=system, user_message=user, response_text="",
                latency_ms=int((time.monotonic() - started_at) * 1000),
                status="error", error_message=str(exc)[:500],
            )
        raise


async def chat_json(
    *,
    model: str = "gpt-4o-mini",
    system: str,
    user: str,
    max_tokens: int = 1500,
    temperature: float = 0.3,
    agent_name: str = "unknown",
) -> dict[str, Any]:
    """JSON-forced chat. Used by the openai_critic node in the roadmap chain.
    Persists every call to llm_calls.
    """
    s = get_settings()
    _kill_switch_guard()
    if s.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY not configured")
    started_at = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OPENAI_API}/chat/completions",
                headers={
                    "Authorization": f"Bearer {s.openai_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                },
            )
        latency_ms = int((time.monotonic() - started_at) * 1000)
        if resp.status_code != 200:
            await record_llm_call(
                agent=agent_name, provider="openai", model=model,
                system_prompt=system, user_message=user, response_text="",
                latency_ms=latency_ms, status="error",
                error_message=f"{resp.status_code}: {resp.text[:300]}",
            )
            raise RuntimeError(f"OpenAI {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        p_in, p_out = _price_for(model)
        cost = (in_tok * p_in + out_tok * p_out) / 1_000_000
        await record_llm_call(
            agent=agent_name, provider="openai", model=model,
            system_prompt=system, user_message=user, response_text=content,
            input_tokens=in_tok, output_tokens=out_tok,
            cost_usd=cost, latency_ms=latency_ms, status="ok",
        )
        return json.loads(content)
    except Exception as exc:
        if not (isinstance(exc, RuntimeError) and "OpenAI" in str(exc)):
            await record_llm_call(
                agent=agent_name, provider="openai", model=model,
                system_prompt=system, user_message=user, response_text="",
                latency_ms=int((time.monotonic() - started_at) * 1000),
                status="error", error_message=str(exc)[:500],
            )
        raise


# ── DALL-E 3 (image backup) ──────────────────────────────────────────────


async def generate_image(prompt: str, *, size: str = "1024x1024") -> str:
    """Generate a single image. Returns the (temporary) OpenAI URL.

    Caller is responsible for mirroring the bytes into MinIO — DALL-E
    URLs expire after a couple of hours.
    """
    s = get_settings()
    _kill_switch_guard()
    if s.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY not configured")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{OPENAI_API}/images/generations",
            headers={
                "Authorization": f"Bearer {s.openai_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "size": size,
                "n": 1,
                "quality": "standard",
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"DALL-E {resp.status_code}: {resp.text[:200]}")
        return resp.json()["data"][0]["url"]

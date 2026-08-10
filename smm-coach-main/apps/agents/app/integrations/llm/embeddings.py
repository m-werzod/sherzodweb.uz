"""Embeddings — single entry point so we can swap providers centrally.

Default provider: Voyage `voyage-3` (1024-dim, normalized).
Fallback when no key OR 429 rate-limit: deterministic stub vector for dev.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"

# Warn ONCE per process when embeddings silently degrade to the hash stub — otherwise a prod box
# with no VOYAGE_API_KEY returns random-but-stable vectors and the vault "looks smart" while
# semantic retrieval is actually meaningless. (429 fallbacks already log per-occurrence.)
_stub_warned = False

# Queryable degradation status (Stage 6 monitoring). A single-person operator has no
# other signal that semantic memory silently fell back to the deterministic hash stub
# (no key / Voyage 429 / transport error) — `embedding_health()` is surfaced by /health
# so a degraded vault is visible instead of "looking smart" while retrieval is random.
_embed_stub_chunks = 0
_embed_real_chunks = 0
_embed_last_stub_at: str | None = None
_embed_last_stub_reason: str | None = None


def _record_stub(reason: str) -> None:
    global _embed_stub_chunks, _embed_last_stub_at, _embed_last_stub_reason
    _embed_stub_chunks += 1
    _embed_last_stub_at = datetime.now(UTC).isoformat()
    _embed_last_stub_reason = reason
    _warn_stub_once(reason)


def _record_real() -> None:
    global _embed_real_chunks
    _embed_real_chunks += 1


def embedding_health() -> dict:
    """Snapshot of embedding degradation — is semantic search on real Voyage vectors or
    the deterministic stub? `degraded=True` when there's no key (every call is a stub) or
    every chunk so far fell back. Surfaced by /health for the operator."""
    settings = get_settings()
    has_key = bool(settings.voyage_api_key)
    total = _embed_stub_chunks + _embed_real_chunks
    return {
        "has_voyage_key": has_key,
        "stub_chunks": _embed_stub_chunks,
        "real_chunks": _embed_real_chunks,
        "stub_ratio": (_embed_stub_chunks / total) if total else 0.0,
        "last_stub_at": _embed_last_stub_at,
        "last_stub_reason": _embed_last_stub_reason,
        # Degraded if no key at all, or if we've only ever produced stubs after some calls.
        "degraded": (not has_key) or (total > 0 and _embed_real_chunks == 0),
    }


def _warn_stub_once(reason: str) -> None:
    global _stub_warned
    if not _stub_warned:
        _stub_warned = True
        log.warning(
            "embeddings.stub_fallback — semantic search DEGRADED (deterministic hash stub, NOT real "
            "similarity); set VOYAGE_API_KEY in prod",
            reason=reason,
        )


async def embed_text(text: str) -> list[float]:
    """Single-text embedding. For multiple texts use `embed_batch` — it
    issues one Voyage call instead of N, which matters when drift_detector
    scores 16 tasks in one tick (16 sequential calls trip the free-tier
    rate limit).
    """
    out = await embed_batch([text])
    return out[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Batched embedding — sends all texts in one Voyage request.

    Voyage caps input batch at 128; we slice if needed. On 429 we sleep and
    retry once, then fall back to deterministic stubs so the agent loop
    never crashes on a rate-limited tick.
    """
    if not texts:
        return []
    settings = get_settings()
    voyage_key = (
        settings.voyage_api_key.get_secret_value()
        if settings.voyage_api_key
        else None
    )

    if not voyage_key:
        _record_stub("no_voyage_key")
        return [_stub_embedding(t, settings.embeddings_dim) for t in texts]

    out: list[list[float]] = []
    # Voyage limits input to 128 items per request.
    chunks = [texts[i : i + 128] for i in range(0, len(texts), 128)]
    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in chunks:
            for attempt in range(2):
                try:
                    r = await client.post(
                        VOYAGE_URL,
                        headers={"Authorization": f"Bearer {voyage_key}"},
                        json={"input": chunk, "model": settings.model_embeddings},
                    )
                    if r.status_code == 429:
                        if attempt == 0:
                            log.warning("voyage.rate_limit — sleeping 15s then retrying")
                            await asyncio.sleep(15)
                            continue
                        log.warning(
                            "voyage.rate_limit_after_retry — using stub embeddings for this chunk",
                            count=len(chunk),
                        )
                        _record_stub("rate_limit")
                        out.extend(_stub_embedding(t, settings.embeddings_dim) for t in chunk)
                        break
                    r.raise_for_status()
                    data = r.json()
                    out.extend(item["embedding"] for item in data["data"])
                    _record_real()
                    break
                except httpx.HTTPError:
                    # Broad on purpose: HTTPError covers raise_for_status AND
                    # timeouts/connection errors (TimeoutException, ConnectError,
                    # TransportError). The old `HTTPStatusError`-only catch let a
                    # Voyage timeout propagate out of embed_batch → drift_detector
                    # → the whole graph run crashed. Now any Voyage failure
                    # degrades to stubs (one retry first) so the run survives.
                    if attempt == 1:
                        log.exception("voyage.request_failed — fallback to stubs", count=len(chunk))
                        _record_stub("request_failed")
                        out.extend(_stub_embedding(t, settings.embeddings_dim) for t in chunk)
                        break
                    await asyncio.sleep(2)
    return out


def _stub_embedding(text: str, dim: int) -> list[float]:
    """Deterministic, normalized vector of length `dim` (1024 for voyage-3),
    seeded from the text hash. Used in dev/test only — gives stable similarity
    scores in unit tests.
    """
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    out: list[float] = []
    x = seed
    for _ in range(dim):
        x = (x * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        out.append(((x >> 33) / (1 << 31)) - 1.0)
    n = math.sqrt(sum(v * v for v in out)) or 1.0
    return [v / n for v in out]

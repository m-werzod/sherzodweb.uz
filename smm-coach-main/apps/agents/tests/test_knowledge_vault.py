"""Knowledge-vault retrieval guards. Locks in the fix that stops the vault from
injecting noise into scripts: when embeddings are degraded (no Voyage key /
all-stub), cosine ranking is random, so related_notes must return NOTHING rather
than feed a script arbitrary "facts". (The similarity floor is exercised
indirectly here; the degraded gate is the load-bearing safety.)
"""
from __future__ import annotations

import pytest

from app.memory import knowledge_vault


@pytest.mark.asyncio
async def test_related_notes_short_circuits_when_embeddings_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Degraded → random cosine → garbage matches. Must return [] BEFORE embedding
    # the query or touching the DB (so no stub note can reach a prompt).
    monkeypatch.setattr(knowledge_vault, "embedding_health", lambda: {"degraded": True})

    embed_called = False

    async def _spy_embed(_q: str) -> list[float]:
        nonlocal embed_called
        embed_called = True
        return [0.0] * 1024

    monkeypatch.setattr(knowledge_vault, "embed_text", _spy_embed)

    out = await knowledge_vault.related_notes(tenant_id="t1", query="qovurilgan tovuq retsepti")
    assert out == []
    assert embed_called is False  # short-circuited before any embedding / DB work


@pytest.mark.asyncio
async def test_related_notes_empty_query_returns_empty() -> None:
    assert await knowledge_vault.related_notes(tenant_id="t1", query="   ") == []


def test_min_similarity_floor_is_meaningful() -> None:
    # The floor must be a real threshold (not 0), else low-relevance noise still
    # fills the top-N slots and gets injected as the user's voice.
    assert 0.0 < knowledge_vault._MIN_SIMILARITY < 1.0

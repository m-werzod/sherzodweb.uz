"""Shared knowledge-vault retrieval for agents — the Stage 6 promise that EVERY
agent consults the vault before acting, not just the scriptwriter + planner.

format_vault_block is pure (unit-tested); load_vault_context wraps related_notes.
Best-effort: an empty vault or any failure returns '' so the caller's prompt is
unchanged (pre-existing tenants with no vault are byte-for-byte unaffected).
"""
from __future__ import annotations

import structlog

from app.memory.knowledge_vault import related_notes

log = structlog.get_logger(__name__)

_NOTE_CHARS = 240
_NOTE_LIMIT = 6


def format_vault_block(notes: list[dict], header: str) -> str:
    """Render retrieved notes as a compact prompt block under `header`. Empty
    string when nothing usable."""
    lines: list[str] = []
    for n in notes:
        body = (n.get("body") or "").strip().replace("\n", " ")
        if not body:
            continue
        kind = n.get("kind") or "note"
        title = (n.get("title") or "").strip()
        lines.append(f"- [{kind}] {title}: {body[:_NOTE_CHARS]}")
    if not lines:
        return ""
    return f"\n\n--- {header} ---\n" + "\n".join(lines[:_NOTE_LIMIT])


async def load_vault_context(
    tenant_id: str, query: str, header: str, limit: int = _NOTE_LIMIT
) -> str:
    """Semantically retrieve this tenant's most relevant vault notes for `query`
    and format them under `header`. Best-effort → '' on empty/failure."""
    query = (query or "").strip()
    if not query:
        return ""
    try:
        notes = await related_notes(tenant_id=tenant_id, query=query, limit=limit)
    except Exception as exc:  # noqa: BLE001
        log.warning("vault_context.failed", error=str(exc)[:120])
        return ""
    return format_vault_block(notes, header)

"""Cross-cutting helper for agent narration.

`emit_message()` writes a row to `agent_messages` AND publishes the same
payload onto the Redis pub/sub bus that the SSE proxy is subscribed to.
This is the only path agent nodes should use — bare `publish()` was for
ephemeral signals, not user-visible dialog.

Persisting these messages does two things:
1. The `/agents` page and dashboard FEED query `agent_messages` directly,
   so the dialog survives page reloads + lets us cap at the last N.
2. We can audit what each agent said about what task (`runId` link).
"""
from __future__ import annotations

import contextlib
import uuid
from datetime import UTC
from typing import Literal

import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.memory.db import get_sessionmaker
from app.streams.bus import publish

log = structlog.get_logger(__name__)

AgentKind = Literal["market", "industry", "writer", "audience"]

ROLE_LABELS: dict[str, str] = {
    "market": "Market Analyst",
    "industry": "Industry Scout",
    "writer": "Scriptwriter",
    "audience": "Audience Watcher",
}


async def emit_message(
    *,
    tenant_id: str,
    user_id: str | None,
    agent: AgentKind,
    content: str,
    role: str | None = None,
    run_id: str | None = None,
    important: bool = False,
) -> str:
    """Persist + broadcast a single narration message. Returns the row id.

    Fail-soft: if the DB write fails, we still publish to SSE (UX continues),
    log the error, and move on. If the publish fails, we keep the DB row.
    The agent workflow must never crash because of a narration issue.

    DEDUPE: an identical (tenant, agent, content) tuple inside the last
    10 minutes is treated as a duplicate and silently dropped. This is
    what stops Industry Scout from spamming the same "X sohasidagi
    yangiliklarni o'qiyapman" line 4-5 times when the orchestrator
    re-runs the node in close succession.
    """
    msg_id = uuid.uuid4().hex
    role_label = role or ROLE_LABELS.get(agent, agent)

    try:
        sm = get_sessionmaker()
        async with sm() as session:
            # Cheap pre-check: identical recent row exists?
            dup = await session.execute(
                text(
                    """
                    SELECT id FROM agent_messages
                    WHERE "tenantId" = :tenant_id
                      AND agent = :agent
                      AND content = :content
                      AND "createdAt" > NOW() - INTERVAL '10 minutes'
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "agent": agent, "content": content},
            )
            existing = dup.scalar()
            if existing:
                log.debug(
                    "agent_message.dedup_skip",
                    agent=agent,
                    tenant_id=tenant_id,
                    existing_id=existing,
                )
                return existing  # caller sees a real id; just not the new one

            # Live Telegram feed: only the IMPORTANT narration lines (key
            # insights, pivots) go here as polished prose. The per-node
            # technical report — which covers EVERY node, important or not —
            # is emitted by the dispatcher (`_report_node`), so sending every
            # narration here too would double up the feed.
            if important:
                with contextlib.suppress(Exception):
                    telegram.send(f"❗ {role_label}\n{content}")

            await session.execute(
                text(
                    """
                    INSERT INTO agent_messages
                      (id, "tenantId", "runId", agent, role, content, important, "createdAt")
                    VALUES (:id, :tenant_id, :run_id, :agent, :role, :content, :important, NOW())
                    """
                ),
                {
                    "id": msg_id,
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "agent": agent,
                    "role": role_label,
                    "content": content,
                    "important": important,
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("agent_message.persist_failed", error=repr(exc), agent=agent)

    try:
        await publish(
            user_id or "system",
            {
                "type": "agent.message",
                "id": msg_id,
                "runId": run_id,
                "agent": agent,
                "role": role_label,
                "content": content,
                "important": important,
                "at": _now(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("agent_message.publish_failed", error=repr(exc), agent=agent)

    return msg_id


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()

"""Per-user (per-tenant) knowledge vault.

Every Q&A interview the user completes is embedded and stored as a
KnowledgeNote. When the scriptwriter writes a NEW script it retrieves this
tenant's semantically-related notes and injects them — so the user's past
answers (their voice, their stories, their facts) carry across topics. This
is the "Obsidian vault" the product promises: interconnected, reusable.

pgvector isn't installed in local dev, so `embedding` is jsonb (list[float])
and we rank in Python — the same pattern as
`shared_knowledge.similar_exemplar_posts`. Production swaps in the `<=>`
operator + the HNSW index in packages/db/prisma/manual/001_pgvector_indexes.sql.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import uuid

import structlog
from sqlalchemy import text

from app.integrations.llm.embeddings import embed_text, embedding_health
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

# Below this cosine similarity a "match" is noise, not the user's voice. Injecting
# a 0.05-similarity note into a script as "the user's own fact" is worse than no
# note at all, so retrieval drops anything under the floor. Set BELOW
# drift_detector's 0.18 on-topic line on purpose: drift measures same-context
# (north-star↔task) similarity, but vault retrieval is CROSS-topic carryover
# (query↔note across different topics) — those cosines run systematically lower,
# so a floor at/above 0.18 would discard genuinely-useful cross-topic notes. 0.15
# kills the clear-noise case (~0.05) while keeping the 0.18-0.35 related band.
# Erring low on purpose: over-restriction just means less vault context (graceful,
# it's 1 of 3 grounding sources), while under-restriction fabricates the user's facts.
_MIN_SIMILARITY = 0.15

# Hold references to fire-and-forget telemetry tasks: the event loop keeps only a
# weak ref, so an un-referenced task can be GC'd before it runs (the hitCount bump
# would silently not happen). Discard on completion to avoid an unbounded set.
_pending_bump_tasks: set[asyncio.Task] = set()


async def save_note(
    *,
    tenant_id: str,
    title: str,
    body: str,
    kind: str = "qa",
    tags: list[str] | None = None,
    source_task_id: str | None = None,
) -> str | None:
    """Embed + persist a note. One note per source task (upsert by sourceTaskId)
    so re-interviewing a topic refreshes its note rather than duplicating it.

    Best-effort: returns the note id, or None on any failure. NEVER raises into
    the agent loop — a vault hiccup must not break script generation.
    """
    body = (body or "").strip()
    if not body:
        return None

    try:
        vec = await embed_text(f"{title}\n{body}")
    except Exception:  # noqa: BLE001
        vec = None

    # Obsidian-style graph: link this note to the tenant's most similar ones.
    related: list[dict] = []
    try:
        related = await related_notes(
            tenant_id=tenant_id, query=body, limit=3, exclude_task_id=source_task_id
        )
    except Exception:  # noqa: BLE001
        related = []

    # Dedup: auto-generated lesson notes use a per-run sourceTaskId
    # (breakout:/negwave:/perf:<run>), so without this each run would add a
    # near-identical row that dilutes retrieval. If a near-duplicate same-kind
    # lesson already exists, refresh THAT row instead of inserting a new one.
    # Only for accumulating lesson kinds — never merge the user's real qa/insight
    # notes (distinct facts must stay distinct).
    dedup_id = _dedup_target(related, kind)
    links = [r["id"] for r in related if r["id"] != dedup_id]

    emb_json = json.dumps(vec) if vec else None
    tags = tags or []
    sm = get_sessionmaker()
    try:
        async with sm() as session:
            existing_id: str | None = None
            if source_task_id:
                row = await session.execute(
                    text(
                        'SELECT id FROM knowledge_notes '
                        'WHERE "tenantId" = :tid AND "sourceTaskId" = :sid LIMIT 1'
                    ),
                    {"tid": tenant_id, "sid": source_task_id},
                )
                existing_id = row.scalar()
            # No same-source row → fold into a near-duplicate lesson if one exists.
            existing_id = existing_id or dedup_id

            if existing_id:
                await session.execute(
                    text(
                        """
                        UPDATE knowledge_notes
                        SET title = :title, body = :body, kind = :kind,
                            tags = CAST(:tags AS text[]), links = CAST(:links AS text[]),
                            embedding = CAST(:emb AS jsonb), "updatedAt" = NOW()
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": existing_id, "title": title[:200], "body": body,
                        "kind": kind, "tags": tags, "links": links, "emb": emb_json,
                    },
                )
                note_id = existing_id
            else:
                note_id = uuid.uuid4().hex
                await session.execute(
                    text(
                        """
                        INSERT INTO knowledge_notes
                          (id, "tenantId", title, body, kind, tags, links,
                           "sourceTaskId", embedding, "createdAt", "updatedAt")
                        VALUES
                          (:id, :tid, :title, :body, :kind, CAST(:tags AS text[]),
                           CAST(:links AS text[]), :sid, CAST(:emb AS jsonb), NOW(), NOW())
                        """
                    ),
                    {
                        "id": note_id, "tid": tenant_id, "title": title[:200],
                        "body": body, "kind": kind, "tags": tags, "links": links,
                        "sid": source_task_id, "emb": emb_json,
                    },
                )
            await session.commit()
        log.info("knowledge_vault.saved", tenant_id=tenant_id, kind=kind, links=len(links))
        return note_id
    except Exception:  # noqa: BLE001
        log.warning("knowledge_vault.save_failed", tenant_id=tenant_id, exc_info=True)
        return None


async def related_notes(
    *,
    tenant_id: str,
    query: str,
    limit: int = 5,
    exclude_task_id: str | None = None,
) -> list[dict]:
    """Semantic search over THIS tenant's notes only. dev: jsonb + Python cosine
    (a bounded 300-row candidate set, ranked in-process)."""
    query = (query or "").strip()
    if not query:
        return []

    # Degraded embeddings (no Voyage key / all-stub) → cosine is random noise, so
    # the "most relevant" notes would be arbitrary. Return nothing rather than feed
    # a script random personal "facts" — the vault stays silent instead of lying.
    if embedding_health().get("degraded"):
        return []

    sm = get_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT id, title, body, kind, "sourceTaskId", embedding
                FROM knowledge_notes
                WHERE "tenantId" = :tid AND embedding IS NOT NULL
                ORDER BY "updatedAt" DESC
                LIMIT 300
                """
            ),
            {"tid": tenant_id},
        )
        rows = result.mappings().all()
    if not rows:
        return []

    try:
        qv = await embed_text(query)
    except Exception:  # noqa: BLE001
        return []
    qnorm = _norm(qv)
    if qnorm == 0.0:
        return []

    scored: list[tuple[float, dict]] = []
    for row in rows:
        if exclude_task_id and row.get("sourceTaskId") == exclude_task_id:
            continue
        emb = row["embedding"]
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:  # noqa: BLE001, S112 — skip a malformed embedding row
                continue
        if not emb:
            continue
        sim = _cosine(qv, emb, qnorm)
        scored.append((sim, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = [
        {
            "id": r["id"],
            "title": r["title"],
            "body": r["body"],
            "kind": r["kind"],
            "similarity": sim,
        }
        for sim, r in scored[:limit]
        if sim >= _MIN_SIMILARITY  # floor: skip noise so we never inject an irrelevant note
    ]
    # Retrieval telemetry (Stage 6): bump hitCount on the notes that were pulled
    # into context — fire-and-forget so it never slows the hot retrieval path.
    ids = [n["id"] for n in out if n.get("id")]
    if ids:
        with contextlib.suppress(RuntimeError):
            t = asyncio.get_running_loop().create_task(_bump_hits(ids))
            _pending_bump_tasks.add(t)  # hold a ref so the task isn't GC'd mid-flight
            t.add_done_callback(_pending_bump_tasks.discard)
    return out


async def _bump_hits(ids: list[str]) -> None:
    """One batched UPDATE incrementing hitCount + lastRetrievedAt. Best-effort."""
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text(
                    'UPDATE knowledge_notes SET "hitCount" = "hitCount" + 1, '
                    '"lastRetrievedAt" = NOW() WHERE id = ANY(:ids)'
                ),
                {"ids": ids},
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — telemetry is best-effort
        log.warning("knowledge_vault.bump_hits_failed")


# Lesson kinds that the agent loop regenerates every cycle (one row per run via
# a unique sourceTaskId) — these are deduped. The user's own qa/insight/topic
# notes are NEVER deduped (distinct facts must stay distinct).
_DEDUP_KINDS = {"lessons_learned"}
# Cosine ≥ this ⇒ treat as the same lesson and refresh it. High on purpose so
# only genuinely near-identical lessons collapse, not merely related ones.
_DEDUP_THRESHOLD = 0.93


def _dedup_target(related: list[dict], kind: str) -> str | None:
    """Pick an existing note id to refresh instead of inserting, when this is an
    accumulating lesson kind and the most-similar existing note is the same kind
    and near-identical. Pure → returns the id or None. Used by save_note."""
    if kind not in _DEDUP_KINDS or not related:
        return None
    top = related[0]
    if top.get("kind") == kind and float(top.get("similarity") or 0.0) >= _DEDUP_THRESHOLD:
        return top.get("id")
    return None


def _norm(v: list[float]) -> float:
    return (sum(x * x for x in v)) ** 0.5


def _cosine(a: list[float], b: list[float], anorm: float) -> float:
    if len(a) != len(b):
        return 0.0
    bnorm = _norm(b)
    if bnorm == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False)) / (anorm * bnorm)

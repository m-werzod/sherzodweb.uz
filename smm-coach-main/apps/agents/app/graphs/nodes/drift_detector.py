"""Scores each proposed task against the user's north-star embedding and
flags tasks below the cosine-similarity threshold. Cheap (Haiku) — runs on
every iteration to keep the roadmap on the main growth path.
"""
from __future__ import annotations

import structlog

from app.graphs.state import GrowthCoachState
from app.integrations.llm.embeddings import embed_batch, embed_text
from app.streams.bus import publish

log = structlog.get_logger(__name__)

# Cosine similarity threshold against the north-star embedding. The original
# 0.45 was calibrated against deterministic stub embeddings; real Voyage
# vectors are much more discriminating, so even on-niche tasks routinely
# score in 0.20-0.35 range. 0.18 keeps the safety guard (clearly off-niche
# stuff still gets rejected) without nuking the whole roadmap on every run.
# Re-tune after Bosqich I once we have ~30 sessions of real telemetry.
THRESHOLD = 0.18


async def run(state: GrowthCoachState) -> dict:
    user_id = state.get("user_id") or "system"
    run_id = state["run_id"]
    north = state.get("north_star") or {}
    proposals = state.get("proposed_tasks") or []
    if not proposals:
        return {}

    north_vec = north.get("embedding")
    if north_vec is None:
        north_text = f"{north.get('niche', '')} | {north.get('target_audience', '')}"
        north_vec = await embed_text(north_text)

    # Batch the per-task embeddings into a single Voyage call. Scoring 16
    # tasks one-by-one used to trip the free-tier rate limit and crash the
    # whole roadmap_generation run.
    # Topics-only roadmaps carry no hook yet, so fall back to goal_description
    # for the semantic signal (title + why) instead of scoring on title alone.
    task_texts = [
        f"{t.get('title', '')} {t.get('hook') or t.get('goal_description') or ''}"
        for t in proposals
    ]
    task_vecs = await embed_batch(task_texts)

    scored: list[tuple[dict, float]] = []
    for task, vec in zip(proposals, task_vecs, strict=True):
        score = _cosine(north_vec, vec)
        scored.append(({**task, "drift_score": score}, score))

    kept = [t for t, s in scored if s >= THRESHOLD]
    rejected = [t for t, s in scored if s < THRESHOLD]

    # FLOOR — never silently shrink the roadmap below 85% of what was proposed.
    # Topics are LLM-generated FROM the north-star (already on-niche), and the
    # embedding path degrades to deterministic STUB vectors under a Voyage
    # rate-limit/timeout — both make the 0.18 gate over-reject and would quietly
    # drop the cadence-promised N below target. If we'd cut more than 15%,
    # rescue the highest-scoring rejects back up to the floor so drift removes
    # only clear outliers, never decimates the roadmap.
    # LOOP-2: anchor the floor on the cadence-promised N (north_star.roadmap_size), not just the
    # proposed count — else an earlier generator under-delivery (truncated/empty batch) compounds with
    # drift over-rejection and lands below the contract's 85% of the user's promised size. Can't
    # manufacture tasks that were never generated, but stops drift from shrinking BELOW that target.
    promised_n = int(north.get("roadmap_size") or 0)
    floor = max(1, int(max(len(proposals), promised_n) * 0.85))
    if len(kept) < floor and rejected:
        rejected.sort(key=lambda t: t.get("drift_score", 0.0), reverse=True)
        need = floor - len(kept)
        kept.extend(rejected[:need])
        rejected = rejected[need:]

    warnings = [
        {"task_title": t.get("title"), "drift_score": t.get("drift_score"), "threshold": THRESHOLD}
        for t in rejected
    ]
    for t in rejected:
        await publish(
            user_id,
            {
                "type": "drift.warning",
                "runId": run_id,
                "taskTitle": t.get("title", ""),
                "driftScore": t.get("drift_score"),
                "threshold": THRESHOLD,
                "at": _now(),
            },
        )

    log.info(
        "drift.scored",
        input=len(proposals),
        kept=len(kept),
        rejected=len(rejected),
        threshold=THRESHOLD,
        floor=floor,
        scores_sample=[round(t["drift_score"], 3) for t in kept[:6]],
    )
    return {
        "proposed_tasks": kept,
        "drift_warnings": warnings,
        "rejected_tasks": rejected,
    }


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()

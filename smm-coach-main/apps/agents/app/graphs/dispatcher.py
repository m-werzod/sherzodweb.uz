"""Maps a workflow name + payload to a graph invocation."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.config import get_settings
from app.graphs.growth_coach import compile_graph
from app.graphs.state import GrowthCoachState, empty_cost
from app.integrations import telegram
from app.runs.context import RunContext, reset_current, set_current
from app.runs.repository import (
    create_run,
    fetch_run,
    heartbeat_run,
    mark_completed,
    mark_failed,
    reset_revising_task,
)
from app.streams.bus import publish

log = structlog.get_logger(__name__)


async def dispatch_workflow(
    *,
    tenant_id: str,
    user_id: str | None,
    workflow: str,
    thread_id: str | None,
    payload: dict[str, Any],
    idempotency_key: str | None,
) -> tuple[str, str]:
    """Enqueue a workflow run. Returns (run_id, thread_id) immediately.

    T7.1: the run is now DURABLE — we INSERT it as `queued` and the run_worker
    claims + drives it (mirror of the montage worker), so a process restart can
    no longer strand an in-flight run (the worker reclaims its expired lease and
    resumes from the LangGraph checkpoint). The old fire-and-forget
    `asyncio.create_task(_run(...))` is gone.
    """
    run_id = idempotency_key or uuid.uuid4().hex

    # Idempotency: if the caller passed a key and we've already seen it, just
    # return the existing run. This protects against double-clicks and network
    # retries from kicking off two parallel workflows.
    if idempotency_key:
        try:
            existing = await fetch_run(run_id)
            if existing is not None:
                # Only a TRUE idempotent replay (same tenant AND workflow) may short-circuit.
                # A key collision across tenants/workflows must NOT return the foreign run
                # (cross-tenant leak) — fall through with a fresh id so create_run's
                # ON CONFLICT(id) DO NOTHING can't silently drop this caller's run.
                if existing["tenantId"] == tenant_id and existing["workflow"] == workflow:
                    log.info("dispatcher.idempotent_hit", run_id=run_id, status=existing["status"])
                    return existing["runId"], existing["threadId"]
                log.warning(
                    "dispatcher.idempotency_collision",
                    run_id=run_id, incoming_tenant=tenant_id, existing_tenant=existing["tenantId"],
                    incoming_workflow=workflow, existing_workflow=existing["workflow"],
                )
                run_id = uuid.uuid4().hex  # genuinely fresh run, no collision
        except Exception:  # noqa: BLE001 — non-fatal: fall through to create
            log.exception("dispatcher.fetch_existing_failed", run_id=run_id)

    # Default the checkpoint thread from the FINAL run_id (the collision path above may have
    # refreshed it) so each run gets a clean LangGraph state. An explicit caller thread_id wins.
    if thread_id is None:
        thread_id = _default_thread_id(tenant_id, user_id, workflow, run_id)

    # Durable enqueue — create_run writes status='queued' with the payload as
    # `input`, which the run_worker reads back to reconstruct the state. Must NOT
    # be swallowed: a failed insert means the run would never execute.
    await create_run(
        run_id=run_id,
        tenant_id=tenant_id,
        user_id=user_id,
        workflow=workflow,
        thread_id=thread_id,
        payload=payload,
    )
    return run_id, thread_id


def _build_state(
    *, tenant_id: str, user_id: str | None, workflow: str, run_id: str, payload: dict[str, Any]
) -> GrowthCoachState:
    """Reconstruct the initial graph state from the persisted run fields — used by
    the run_worker (the payload is stored as agent_runs.input)."""
    state: GrowthCoachState = GrowthCoachState(
        tenant_id=tenant_id,
        user_id=user_id,
        workflow=workflow,
        run_id=run_id,
        market_signals=[],
        industry_signals=[],
        tracker_observations=[],
        proposed_tasks=[],
        approved_tasks=[],
        rejected_tasks=[],
        drift_warnings=[],
        validation_errors=[],
        cost=empty_cost(),
        notes=[],
        **payload,
    )
    return state


async def drive_run(claim: dict[str, Any], *, lease_seconds: int = 600) -> None:
    """Drive a claimed run to completion. Called by the run_worker with the row
    returned from `claim_run`. A claim with attempts > 1 is a RECLAIM (the prior
    driver died) → resume from the LangGraph checkpoint instead of re-running from
    the start (which would duplicate persister writes). `lease_seconds` must match
    the value the worker claimed with so per-node heartbeats keep the lease ahead
    of the reclaim window."""
    state = _build_state(
        tenant_id=claim["tenant_id"],
        user_id=claim["user_id"],
        workflow=claim["workflow"],
        run_id=claim["run_id"],
        payload=claim["payload"] or {},
    )
    await _run(
        state,
        claim["thread_id"],
        resume=int(claim.get("attempts") or 1) > 1,
        lease_seconds=lease_seconds,
    )


_langfuse_client_ready = False


def _langfuse_callbacks(state: GrowthCoachState) -> list[Any]:
    """Langfuse tracing (opt-in): a per-run CallbackHandler when LANGFUSE_* keys are set —
    every LangGraph node/LLM step lands as a trace tree (session=run, user=tenant).
    Fail-soft: missing keys / import / init error → no callbacks, the run proceeds untouched.

    langfuse v3+ contract (installed: 4.x): the langchain CallbackHandler no longer takes
    keys/session/user — the CLIENT is initialized once (keyed by public_key) and
    session/user/metadata ride on the invoke config's metadata as langfuse_session_id /
    langfuse_user_id (see the config merge in _run)."""
    global _langfuse_client_ready
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return []
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        if not _langfuse_client_ready:
            Langfuse(
                public_key=s.langfuse_public_key.get_secret_value(),
                secret_key=s.langfuse_secret_key.get_secret_value(),
                host=s.langfuse_host or "https://cloud.langfuse.com",
            )
            _langfuse_client_ready = True
        return [CallbackHandler(public_key=s.langfuse_public_key.get_secret_value())]
    except Exception as exc:  # noqa: BLE001 — observability must never break a run
        # NO exc_info here: dict_tracebacks would serialize frame locals incl. Settings.
        log.warning("langfuse.init_failed", error=repr(exc)[:200])
        return []


def _default_thread_id(tenant_id: str, user_id: str | None, workflow: str, run_id: str) -> str:
    # Per-RUN thread (run_id suffix) — NOT one shared thread per (tenant,user,workflow). LangGraph's
    # PostgresSaver keys checkpoints by thread, and a fresh dispatch over an EXISTING thread applies
    # the input ONTO the prior run's operator.add channels — so the Nth regenerate would inherit
    # summed cost (agent_runs.costUsd inflation), a rejected_tasks list already >= _MAX_REWRITES (no
    # quality-rewrite pass → a worse persisted script), and unbounded notes. Regenerating a script /
    # re-pulsing / re-montaging is the COMMON path, so a shared thread silently degrades repeat output.
    # Crash-reclaim is unaffected: create_run persists this thread_id and drive_run reads it back.
    return f"{tenant_id}:{user_id or 'system'}:{workflow}:{run_id}"


# Per-node Telegram labels — emoji + Uzbek so the activity feed reads cleanly.
_NODE_LABELS: dict[str, str] = {
    "initial_analysis": "🔍 Boshlang'ich tahlil",
    "profile_auditor": "📋 Profil auditori",
    "roadmap_generator": "🗺 Yo'l xaritasi strategi",
    "groq_scorer": "⚖️ Tezkor baholovchi",
    "openai_critic": "🧐 Roadmap tanqidchisi",
    "market_analyst": "📈 Bozor tahlilchisi",
    "industry_news": "📰 Soha kuzatuvchisi",
    "scriptwriter": "✍️ Senariy yozuvchi",
    "hashtag_curator": "#️⃣ Hashtag kuratori",
    "hook_optimizer": "🎣 Hook optimizatori",
    "caption_translator": "📝 Caption yozuvchi",
    "drift_detector": "🧭 Drift detektori",
    "output_validator": "🛡 Chiqish validatori",
    "adversarial_critic": "💀 Soft-quality tanqidchi",
    "account_tracker": "👥 Akkaunt kuzatuvchisi",
    "performance_review": "📊 Natija sharhlovchi",
    "comment_sentinel": "💬 Izoh kuzatuvchisi",
    "caption_stylist": "🔤 Subtitr ustasi",
    "higgsfield_director": "🎥 Higgsfield rejissyori",
    "runway_director": "🎬 Runway rejissyori",
    "roadmap_persister": "💾 Saqlovchi",
}


def _report_node(node_name: str, delta: Any) -> None:
    """Push a one-line Telegram report for a node that just finished.

    A node that hit its workflow guard returns ``{}`` (it didn't really do
    anything) — we skip those to keep the feed signal-rich. Otherwise we use
    the node's own ``notes`` line (e.g. "hashtag_curator: 12 tags") when
    present, else a generic "bajarildi".
    """
    if not isinstance(delta, dict) or not delta:
        return
    label = _NODE_LABELS.get(node_name, f"⚙️ {node_name}")
    notes = delta.get("notes")
    summary = ""
    if isinstance(notes, list) and notes:
        summary = str(notes[-1])
    elif isinstance(notes, str):
        summary = notes
    telegram.send(f"{label}\n{summary}" if summary else f"{label} · bajarildi")


async def _record_node_runs(
    tenant_id: str, run_id: str, workflow: str, nodes: set[str]
) -> None:
    """Persist one row per graph node that ran, so the /agents page can show
    real execution (incl. non-LLM guards/persister). Best-effort — node-run
    logging must never break the actual run."""
    if not nodes:
        return
    try:
        from sqlalchemy import text

        from app.memory.db import get_sessionmaker

        sm = get_sessionmaker()
        async with sm() as session:
            for agent in nodes:
                await session.execute(
                    text(
                        'INSERT INTO agent_node_runs ("id", "tenantId", "runId", "agent", "workflow", "createdAt")'
                        " VALUES (:id, :t, :r, :a, :w, now())"
                    ),
                    {"id": uuid.uuid4().hex, "t": tenant_id, "r": run_id, "a": agent, "w": workflow},
                )
            await session.commit()
    except Exception:  # noqa: BLE001
        log.warning("dispatcher.record_node_runs_failed", run_id=run_id)


async def _run(
    state: GrowthCoachState, thread_id: str, *, resume: bool = False, lease_seconds: int = 600
) -> None:
    user_id = state.get("user_id") or "system"
    run_id = state["run_id"]
    workflow = state["workflow"]

    ctx_token = set_current(
        RunContext(
            tenant_id=state["tenant_id"],
            user_id=state.get("user_id"),
            run_id=run_id,
            workflow=workflow,
            task_id=state.get("task_id"),
        )
    )

    # claim_run already committed status='running' (+ startedAt via COALESCE, so a
    # RECLAIM keeps the original start) BEFORE drive_run called us — so we do NOT
    # mark_running again here: it was redundant (an extra round-trip), it RESET
    # startedAt to the reclaim time on retries, and it raced SSE (run.started was
    # published before the status commit). The DB already shows 'running', so this
    # publish is consistent with what a poller sees.
    await publish(
        user_id,
        {"type": "run.started", "runId": run_id, "workflow": workflow, "at": _now()},
    )
    telegram.send(f"🚀 Jarayon boshlandi · {workflow} · tenant {state['tenant_id'][:8]}")

    try:
        graph = await compile_graph()
        # Stream the run so every node's completion is reported to Telegram in
        # real time (the user asked for a per-agent activity feed). We consume
        # BOTH update + value chunks: "updates" tells us which node just ran
        # (+ its notes), "values" carries the accumulated state so we still
        # have the final result for cost/output after the stream ends.
        final: dict[str, Any] = {}
        ran_nodes: set[str] = set()
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50,
            "tags": [workflow, state["tenant_id"]],
        }
        lf_callbacks = _langfuse_callbacks(state)
        if lf_callbacks:
            config["callbacks"] = lf_callbacks
            # v3+ trace attribution: session/user/tags come from config metadata.
            config["metadata"] = {
                "langfuse_session_id": state["run_id"],
                "langfuse_user_id": state["tenant_id"],
                "workflow": workflow,
                "task_id": state.get("task_id"),
            }
        # On a RECLAIM, pass None so LangGraph resumes from the thread's last
        # checkpoint (the crashed run's progress) instead of re-running from START.
        # BUT if the first attempt crashed BEFORE any checkpoint was persisted,
        # resuming with None would run the graph with empty state (missing
        # tenant_id/workflow/...) — so only resume when a checkpoint actually
        # exists; otherwise fall back to the full input (a fresh start).
        graph_input: GrowthCoachState | None = state
        if resume:
            try:
                snapshot = await graph.aget_state(config)
                if snapshot is not None and snapshot.values:
                    graph_input = None
                else:
                    log.warning("dispatcher.resume_no_checkpoint", run_id=run_id)
            except Exception:  # noqa: BLE001 — fall back to a fresh start
                log.warning("dispatcher.resume_state_check_failed", run_id=run_id)
        async for mode, chunk in graph.astream(
            graph_input,
            config=config,
            stream_mode=["updates", "values"],
        ):
            if mode == "values":
                final = chunk  # last values chunk = final state
            elif mode == "updates" and isinstance(chunk, dict):
                for node_name, delta in chunk.items():
                    ran_nodes.add(node_name)
                    _report_node(node_name, delta)
                # Heartbeat after each node — EXTENDS the lease (same value the
                # worker claimed with) so a live run keeps its claim and isn't
                # reclaimed + double-driven by another worker.
                await heartbeat_run(run_id, lease_seconds)
        # Persist which nodes actually ran (incl. non-LLM guards/persister) so
        # the /agents page reflects real execution, not just billable calls.
        await _record_node_runs(state["tenant_id"], run_id, workflow, ran_nodes)
        cost = final.get("cost", empty_cost())
        output = _safe_output(final)

        await publish(
            user_id,
            {
                "type": "run.completed",
                "runId": run_id,
                "output": output,
                "inputTokens": cost["input_tokens"],
                "outputTokens": cost["output_tokens"],
                "cachedTokens": cost["cached_tokens"],
                "costUsd": cost["cost_usd"],
                "at": _now(),
            },
        )
        try:
            await mark_completed(run_id, output=output, cost=cost)
        except Exception:  # noqa: BLE001
            log.exception("dispatcher.mark_completed_failed", run_id=run_id)
        telegram.send(
            f"✅ Jarayon tugadi · {workflow} · "
            f"{int(cost['input_tokens'] + cost['output_tokens'])} tok · ${cost['cost_usd']:.4f}"
        )

    except Exception as exc:  # noqa: BLE001 — top-level dispatcher
        log.exception("run.failed", run_id=run_id)
        telegram.send(f"❌ Jarayon xato · {workflow}\n{repr(exc)[:300]}")
        await publish(
            user_id,
            {"type": "run.failed", "runId": run_id, "error": repr(exc), "at": _now()},
        )
        try:
            await mark_failed(run_id, error=repr(exc))
        except Exception:  # noqa: BLE001
            log.exception("dispatcher.mark_failed_failed", run_id=run_id)
        # If a task-scoped run (content_review / regenerate) crashed BEFORE the
        # persister could reset it, the task is stuck in 'revising' — the brief
        # would read as perpetually "being rewritten" and the client would poll to
        # timeout. Restore it to its prior status (guarded on status='revising').
        task_id = state.get("task_id")
        if task_id:
            try:
                await reset_revising_task(
                    state["tenant_id"], task_id, state.get("prev_status") or "in_progress"
                )
            except Exception:  # noqa: BLE001
                log.exception("dispatcher.reset_revising_failed", run_id=run_id, task_id=task_id)
    finally:
        reset_current(ctx_token)


def _safe_output(state: GrowthCoachState) -> dict[str, Any]:
    """Strip internal scratchpad before sending to clients."""
    keep = {"approved_tasks", "analysis_summary", "drift_warnings", "validation_errors"}
    return {k: v for k, v in state.items() if k in keep}


def _now() -> str:
    return datetime.now(UTC).isoformat()

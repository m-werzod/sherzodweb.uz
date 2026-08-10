"""Per-run context propagated via contextvars so deep call sites (LLM clients)
can attribute usage to the right tenant/run/agent without threading state
through every function signature.
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    tenant_id: str
    user_id: str | None
    run_id: str
    workflow: str
    # Optional: the content task this run operates on, so the AI Inspector can
    # attribute every LLM call to the right task (not just the run). None for
    # workflows that aren't task-scoped (e.g. roadmap_generation, seeding).
    task_id: str | None = None


_current: contextvars.ContextVar[RunContext | None] = contextvars.ContextVar(
    "smm_run_context", default=None
)


def set_current(ctx: RunContext) -> contextvars.Token:
    return _current.set(ctx)


def reset_current(token: contextvars.Token) -> None:
    _current.reset(token)


def current() -> RunContext | None:
    return _current.get()

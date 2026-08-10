"""Agent workflow invocation endpoints."""
from __future__ import annotations

from typing import Any, Literal

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.graphs.dispatcher import dispatch_workflow
from app.runs.repository import fetch_run

log = structlog.get_logger(__name__)

router = APIRouter()


class InvokeRequest(BaseModel):
    tenant_id: str = Field(..., alias="tenantId")
    user_id: str | None = Field(default=None, alias="userId")
    workflow: Literal[
        "initial_analysis",
        "roadmap_generation",
        "content_review",
        "tracker_pulse",
        "replan",
        "profile_audit_pulse",
        "comment_sentinel_pulse",
        "onboarding_post_audit",
        "montage_generation",
        "higgsfield_generation",
        "runway_restyle",
    ]
    thread_id: str | None = Field(default=None, alias="threadId")
    input: dict[str, Any]
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey")

    model_config = {"populate_by_name": True}


class InvokeResponse(BaseModel):
    run_id: str = Field(alias="runId")
    thread_id: str = Field(alias="threadId")
    status: Literal["queued", "running", "completed", "failed", "canceled"]

    model_config = {"populate_by_name": True}


@router.post("", response_model=InvokeResponse)
async def invoke(req: InvokeRequest) -> InvokeResponse:
    log.info(
        "run.invoke",
        tenant_id=req.tenant_id,
        workflow=req.workflow,
        thread_id=req.thread_id,
    )

    try:
        run_id, thread_id = await dispatch_workflow(
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            workflow=req.workflow,
            thread_id=req.thread_id,
            payload=req.input,
            idempotency_key=req.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return InvokeResponse(runId=run_id, threadId=thread_id, status="queued")


class AgentRunRequest(BaseModel):
    tenant_id: str = Field(..., alias="tenantId")
    user_id: str | None = Field(default=None, alias="userId")
    agent: str

    model_config = {"populate_by_name": True}


@router.post("/agent")
async def run_agent(req: AgentRunRequest) -> dict[str, Any]:
    """Run ONE agent node on the tenant's current roadmap, synchronously, and
    return its output — powers the voice coach's "give this agent a task and
    report back" capability."""
    from app.graphs.single_agent import run_single_agent

    return await run_single_agent(
        tenant_id=req.tenant_id, user_id=req.user_id, agent=req.agent
    )


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    row = await fetch_run(run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return row

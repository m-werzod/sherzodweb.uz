from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app import metrics
from app.integrations.llm.embeddings import embedding_health
from app.memory.db import get_engine
from app.streams.bus import _client as redis_client

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus exposition. Refreshes the queue-depth gauges on scrape (cheap
    COUNT queries) then renders all metrics. Exempt from HMAC (a scraper has no
    web signature) — see main.py exempt_paths."""
    await metrics.collect_gauges()
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness — is the process up. Static by design (no deps): a liveness probe
    must not flap on a transient dependency blip."""
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
async def ready() -> JSONResponse:
    """Readiness — can the process actually serve. The old static /health let a
    container with a dead DB keep reporting healthy while Traefik routed traffic
    to it. Postgres is the HARD gate (every request needs it → 503 pulls the
    container from rotation). Redis (SSE pub/sub) and MinIO (montage) are reported
    but NON-fatal — a blip degrades streaming/render but the HMAC API still serves,
    so we don't flap the whole container out for them.
    """
    deps: dict[str, str] = {}
    healthy = True

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        deps["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        deps["postgres"] = f"down: {str(exc)[:120]}"
        healthy = False

    try:
        await redis_client().ping()
        deps["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        deps["redis"] = f"degraded: {str(exc)[:120]}"

    # Embedding degradation — NON-fatal (semantic retrieval falls back to a deterministic
    # stub, the API still serves), but surfaced so the operator sees a dumbed-down vault.
    emb = embedding_health()
    deps["embeddings"] = "ok" if not emb["degraded"] else f"degraded: {emb['last_stub_reason'] or 'no_voyage_key'}"

    return JSONResponse(
        {"status": "ok" if healthy else "unready", "deps": deps, "embeddings": emb},
        status_code=200 if healthy else 503,
    )

"""Telemetry wiring: Sentry + Langfuse + OpenTelemetry."""
from __future__ import annotations

import structlog

from app.config import Settings

log = structlog.get_logger(__name__)


def setup_telemetry(settings: Settings) -> None:
    if settings.sentry_dsn:
        import sentry_sdk  # imported lazily so dev runs don't pay for it

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.env,
            traces_sample_rate=0.1 if settings.env == "production" else 1.0,
            profiles_sample_rate=0.1 if settings.env == "production" else 1.0,
            send_default_pii=False,
        )
        log.info("telemetry.sentry.enabled")

    if settings.langfuse_public_key and settings.langfuse_secret_key:
        log.info("telemetry.langfuse.enabled", host=settings.langfuse_host)
        # Langfuse is wired into LangGraph nodes via the callback handler — see
        # app/graphs/growth_coach.py:_make_langfuse_callback. No global init
        # required because Langfuse v2 reads env vars on first use.
    else:
        log.info("telemetry.langfuse.disabled")

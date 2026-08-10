"""Transactional email notifications (agents side) — a thin smtplib sender that
mirrors apps/web/src/lib/email/transport.ts so the two services use the SAME SMTP
config (EMAIL_SMTP_* + EMAIL_FROM). Used for owner alerts (e.g. a new sales lead)
as a second channel alongside Telegram.

Fire-and-forget + FAIL-SOFT: no-op when SMTP host or the recipient is missing, and
any send error is swallowed (an alert must never break the agent loop). smtplib is
blocking, so `send()` offloads to a thread — safe to await from the async pulse.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

import structlog

log = structlog.get_logger(__name__)


def _cfg() -> dict[str, str] | None:
    """Resolved SMTP config, or None when not deliverable (no real host)."""
    host = os.getenv("EMAIL_SMTP_HOST") or ""
    # localhost/mailpit = dev default → treat as "not configured" for prod alerts.
    if not host or host in ("localhost", "127.0.0.1"):
        return None
    return {
        "host": host,
        "port": os.getenv("EMAIL_SMTP_PORT") or "587",
        "user": os.getenv("EMAIL_SMTP_USER") or "",
        "pass": os.getenv("EMAIL_SMTP_PASS") or "",
        "secure": os.getenv("EMAIL_SMTP_SECURE") or "",
        "from": os.getenv("EMAIL_FROM") or "SMM Coach <hello@smm.brotech.uz>",
    }


def enabled() -> bool:
    return _cfg() is not None


def _send_sync(to_email: str, subject: str, body: str) -> bool:
    cfg = _cfg()
    if not cfg or not to_email:
        return False
    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    port = int(cfg["port"])
    secure = cfg["secure"] == "1"
    try:
        if secure:  # implicit TLS (465)
            with smtplib.SMTP_SSL(cfg["host"], port, timeout=15, context=ssl.create_default_context()) as s:
                if cfg["user"] and cfg["pass"]:
                    s.login(cfg["user"], cfg["pass"])
                s.send_message(msg)
        else:  # STARTTLS (587) when authenticating, else plain
            with smtplib.SMTP(cfg["host"], port, timeout=15) as s:
                if cfg["user"] and cfg["pass"]:
                    s.starttls(context=ssl.create_default_context())
                    s.login(cfg["user"], cfg["pass"])
                s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — an alert must never break the loop
        log.warning("email_notify.send_failed", error=str(exc)[:200])
        return False


async def send(to_email: str, subject: str, body: str) -> bool:
    """Send an alert email (offloaded to a thread; smtplib is blocking). Returns
    True on success. No-op (False) when SMTP isn't configured or `to_email` is empty."""
    import asyncio

    if not to_email or not enabled():
        return False
    return await asyncio.to_thread(_send_sync, to_email, subject, body)

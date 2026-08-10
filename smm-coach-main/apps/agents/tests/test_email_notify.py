"""Stage 12 — owner email alerts (second channel beside Telegram). Config gating +
no-op safety; the actual SMTP send is fail-soft and exercised against real SMTP."""
from __future__ import annotations

import app.integrations.email_notify as en


def test_disabled_when_no_host(monkeypatch):
    monkeypatch.delenv("EMAIL_SMTP_HOST", raising=False)
    assert en.enabled() is False
    assert en._cfg() is None


def test_localhost_treated_as_not_configured(monkeypatch):
    # Mailpit/dev default must not be treated as a deliverable prod alert sink.
    monkeypatch.setenv("EMAIL_SMTP_HOST", "localhost")
    assert en.enabled() is False


def test_enabled_with_real_host(monkeypatch):
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    cfg = en._cfg()
    assert cfg is not None
    assert cfg["host"] == "smtp.example.com"
    assert cfg["port"]  # defaulted when unset
    assert cfg["from"]  # defaulted when unset
    assert en.enabled() is True


async def test_send_noop_without_recipient(monkeypatch):
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    assert await en.send("", "subj", "body") is False  # no recipient → no-op


async def test_send_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("EMAIL_SMTP_HOST", raising=False)
    assert await en.send("x@y.com", "subj", "body") is False  # not configured → no-op

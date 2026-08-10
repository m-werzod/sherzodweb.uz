"""Test bootstrap — runs before any test module is imported.

Loads the repo-root `.env` so that `Settings` (pydantic-settings) can be
instantiated during tests that touch `get_settings()`. Also pins safe
defaults for required fields when the .env file is missing or incomplete.
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv_from_repo_root() -> None:
    here = Path(__file__).resolve().parent
    for candidate in (here / ".env", here.parent.parent / ".env"):
        if not candidate.exists():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            # Only set if not already in env, so a user override wins.
            if v and not os.environ.get(k):
                os.environ[k] = v
        break


_load_dotenv_from_repo_root()

# Hard fallbacks so tests never depend on a particular .env existing.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DIRECT_URL", os.environ["DATABASE_URL"])
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("AGENTS_HMAC_SECRET", "test-hmac-secret-32-bytes-min-please")
os.environ.setdefault("AUTH_SECRET", "test-auth-secret-do-not-use-in-prod")

# Force-disable external LLM / embedding keys during unit tests so we never
# hit the network. Each test that wants a real call must monkeypatch the key
# back in explicitly. Tests rely on the deterministic stub fallbacks.
for k in ("VOYAGE_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(k, None)

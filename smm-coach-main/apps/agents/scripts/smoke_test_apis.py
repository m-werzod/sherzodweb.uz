"""Quick smoke test for all configured external API keys.

Run from repo root:
    python apps/agents/scripts/smoke_test_apis.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Override blanks too — PowerShell sessions sometimes leave empty vars in env
        if v and not os.environ.get(k):
            os.environ[k] = v


def _post(url: str, body: dict[str, Any], headers: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str, headers: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_anthropic() -> tuple[bool, str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return False, "no key set"
    try:
        body = {
            "model": "claude-haiku-4-5",
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Reply with the single word OK"}],
        }
        result = _post(
            "https://api.anthropic.com/v1/messages",
            body,
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        text = "".join(b.get("text", "") for b in result.get("content", []))
        return True, f"OK ({text.strip()[:40]})"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def test_gemini() -> tuple[bool, str]:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return False, "no key set"
    try:
        body = {
            "contents": [{"parts": [{"text": "Reply OK"}]}],
            "generationConfig": {"maxOutputTokens": 16},
        }
        result = _post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
            body,
            {},
        )
        text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return True, f"OK ({text.strip()[:40]})"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def test_voyage() -> tuple[bool, str]:
    key = os.environ.get("VOYAGE_API_KEY")
    if not key:
        return False, "no key set"
    try:
        body = {"input": ["test"], "model": "voyage-3"}
        result = _post(
            "https://api.voyageai.com/v1/embeddings",
            body,
            {"Authorization": f"Bearer {key}"},
        )
        dim = len(result.get("data", [{}])[0].get("embedding", []))
        return True, f"OK (dim={dim})"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def test_elevenlabs() -> tuple[bool, str]:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return False, "no key set"
    try:
        result = _get("https://api.elevenlabs.io/v1/user", {"xi-api-key": key})
        sub = result.get("subscription", {})
        tier = sub.get("tier", "?")
        remaining = sub.get("character_count", 0)
        limit = sub.get("character_limit", 0)
        return True, f"OK (tier={tier}, used {remaining}/{limit} chars)"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    _load_env()
    checks = [
        ("Anthropic   ", test_anthropic),
        ("Gemini      ", test_gemini),
        ("Voyage      ", test_voyage),
        ("ElevenLabs  ", test_elevenlabs),
    ]
    bad = 0
    for name, fn in checks:
        ok, msg = fn()
        mark = " OK " if ok else "FAIL"
        print(f"[{mark}] {name} {msg}")
        if not ok:
            bad += 1
    if bad:
        print(f"\n{bad} provider(s) failed.")
    else:
        print("\nAll providers responded successfully.")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

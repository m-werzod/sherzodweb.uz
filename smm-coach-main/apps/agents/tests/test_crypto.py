from __future__ import annotations

import os

import pytest

from app.security.crypto import decrypt_token, encrypt_token


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-secret-do-not-use-in-production-1234567890")
    yield


def test_roundtrip_short() -> None:
    assert decrypt_token(encrypt_token("hello")) == "hello"


def test_roundtrip_oauth_token() -> None:
    plain = "IGAAJ_long_oauth_token_value_with_dashes-and_underscores_and_more"
    assert decrypt_token(encrypt_token(plain)) == plain


def test_decrypts_typescript_web_ciphertext() -> None:
    """Cross-language golden vector — the only guard against silent web<->agents
    drift. The web app (apps/web/src/lib/security/crypto.ts) encrypts every IG
    OAuth token at rest; the ig_token_refresh worker decrypts it HERE. The two
    wire formats must stay byte-for-byte identical or stored tokens become
    unreadable and every OAuth connection dies after 60 days. Every other test
    in this file is Python->Python and would stay green through such a drift.

    This blob was produced by the TS implementation (mirrored in
    tests/fixtures/ts_crypto_vector.js) under the autouse test AUTH_SECRET.
    Regenerate:
        AUTH_SECRET=test-secret-do-not-use-in-production-1234567890 \\
          node apps/agents/tests/fixtures/ts_crypto_vector.js enc \\
          "IGAAcrossLangGolden_vector-0123456789ABCdef"
    """
    golden = (
        "AbjEFAYuZvzvsA1cf4YEHR2kj1hNGqqPADXf3F-t4CrTBYgDMMXObQNa1n91woOim"
        "_qLoCkclyCPyCiLRQNq4TAzzkEOF1sN"
    )
    assert decrypt_token(golden) == "IGAAcrossLangGolden_vector-0123456789ABCdef"


def test_empty_string_passthrough() -> None:
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""


def test_ciphertext_is_random_per_call() -> None:
    """Same plaintext → different ciphertext (random nonce)."""
    a = encrypt_token("same")
    b = encrypt_token("same")
    assert a != b
    assert decrypt_token(a) == "same"
    assert decrypt_token(b) == "same"


def test_tamper_detection() -> None:
    """A flipped byte must cause decryption to fail (authenticated)."""
    ct = encrypt_token("important")
    # Flip a character in the middle of the base64 blob
    mid = len(ct) // 2
    tampered = ct[:mid] + ("A" if ct[mid] != "A" else "B") + ct[mid + 1 :]
    with pytest.raises(Exception):
        decrypt_token(tampered)


def test_missing_secret_raises(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    monkeypatch.delenv("NEXTAUTH_SECRET", raising=False)
    # Clear the module-level cache by reimporting — not needed since Python
    # impl doesn't cache, but kept for clarity.
    with pytest.raises(RuntimeError):
        encrypt_token("x")

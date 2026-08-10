"""AES-256-GCM helper for at-rest encryption of Instagram OAuth tokens.

Wire format (base64url, no padding):
    [1 byte version=0x01][12 bytes nonce][N bytes ciphertext+tag]

Key derivation:
    HKDF-SHA256(IKM=AUTH_SECRET, salt='smm-token-v1', info='oauth-token', L=32)

The TypeScript counterpart at apps/web/src/lib/security/crypto.ts MUST stay
byte-compatible — change both files together if the algorithm rotates.
"""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_VERSION = 0x01
_NONCE_LEN = 12
_SALT = b"smm-token-v1"
_INFO = b"oauth-token"


def _master_key() -> bytes:
    secret = os.environ.get("AUTH_SECRET") or os.environ.get("NEXTAUTH_SECRET")
    if not secret:
        raise RuntimeError(
            "AUTH_SECRET is not set — required for token encryption"
        )
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=_INFO)
    return hkdf.derive(secret.encode("utf-8"))


def encrypt_token(plaintext: str) -> str:
    if not plaintext:
        return ""
    nonce = secrets.token_bytes(_NONCE_LEN)
    aes = AESGCM(_master_key())
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = bytes([_VERSION]) + nonce + ct
    return base64.urlsafe_b64encode(blob).rstrip(b"=").decode("ascii")


def decrypt_token(ciphertext_b64: str) -> str:
    if not ciphertext_b64:
        return ""
    padded = ciphertext_b64 + "=" * (-len(ciphertext_b64) % 4)
    blob = base64.urlsafe_b64decode(padded.encode("ascii"))
    if not blob or blob[0] != _VERSION:
        raise ValueError(f"Unsupported token version: {blob[:1].hex() if blob else 'empty'}")
    nonce = blob[1 : 1 + _NONCE_LEN]
    ct = blob[1 + _NONCE_LEN :]
    aes = AESGCM(_master_key())
    return aes.decrypt(nonce, ct, None).decode("utf-8")

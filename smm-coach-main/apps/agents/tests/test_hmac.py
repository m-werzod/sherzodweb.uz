from __future__ import annotations

import time

import pytest

from app.security.hmac import REPLAY_WINDOW_SEC, sign


def test_sign_roundtrip() -> None:
    secret = b"supersecret"
    ts = int(time.time())
    body = b'{"hello":"world"}'
    assert sign(secret, ts, body) == sign(secret, ts, body)


def test_sign_changes_with_body() -> None:
    secret = b"supersecret"
    ts = int(time.time())
    assert sign(secret, ts, b"a") != sign(secret, ts, b"b")


def test_replay_window_is_five_minutes() -> None:
    assert REPLAY_WINDOW_SEC == 300


@pytest.mark.parametrize("body", [b"", b"x", b"x" * 1024])
def test_sign_is_hex(body: bytes) -> None:
    sig = sign(b"k", 1, body)
    assert len(sig) == 64
    int(sig, 16)  # validates hex

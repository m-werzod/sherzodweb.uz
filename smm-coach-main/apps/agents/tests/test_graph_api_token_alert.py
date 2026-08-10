from __future__ import annotations

from app.integrations.instagram import graph_api


def test_detects_expired_token_bodies() -> None:
    expired = [
        '{"error":{"message":"Error validating access token: Session has expired","code":190}}',
        '{"error":{"code":190,"type":"OAuthException"}}',
        '{"error":{"message":"The access token has expired","code":190}}',
    ]
    for body in expired:
        assert graph_api._is_token_expired(body), body


def test_ordinary_business_discovery_400_is_not_token_expiry() -> None:
    # A personal/typo'd handle 400s with code 100 — must NOT be read as token death.
    normal = '{"error":{"message":"Unsupported get request. Object does not exist","code":100}}'
    assert not graph_api._is_token_expired(normal)
    assert not graph_api._is_token_expired("")


def test_alert_is_throttled_and_fires_once(monkeypatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(graph_api.telegram, "send", lambda msg: sent.append(msg))
    monkeypatch.setattr(graph_api, "_TOKEN_ALERT_AT", 0.0)
    # Clock well past the throttle window so the first call fires.
    monkeypatch.setattr(graph_api.time, "monotonic", lambda: 100_000.0)

    body = '{"error":{"code":190}}'
    graph_api._maybe_alert_token_expired(body)
    graph_api._maybe_alert_token_expired(body)  # within throttle window → suppressed
    assert len(sent) == 1
    assert "190" in sent[0]

    # A normal 400 never alerts.
    graph_api._maybe_alert_token_expired('{"error":{"code":100}}')
    assert len(sent) == 1

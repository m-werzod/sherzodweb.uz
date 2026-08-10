"""Tests for the studio-source transcode routing decisions (which container needs
a remux, and that the probe carries the video codec so H.264 can be copied)."""
from __future__ import annotations

import threading

import pytest

from app.api import transcode
from app.montage.gate import ENCODE_GATE
from app.montage.probe import ClipInfo


def test_mp4_passthrough_no_transcode() -> None:
    assert transcode._needs_transcode("t/k/clip.mp4", None) is False
    assert transcode._needs_transcode("t/k/audio.m4a", None) is False
    assert transcode._needs_transcode("t/k/clip.MP4", None) is False  # case-insensitive


def test_mov_and_other_containers_need_transcode() -> None:
    for key in ("a.mov", "a.qt", "a.webm", "a.mkv", "a.avi", "a.m4v", "a.3gp"):
        assert transcode._needs_transcode(f"t/k/{key}", None) is True, key


def test_unknown_extension_falls_back_to_content_type() -> None:
    assert transcode._needs_transcode("t/k/blob", "video/mp4") is False
    assert transcode._needs_transcode("t/k/blob", "application/octet-stream") is True
    assert transcode._needs_transcode("t/k/blob", None) is True


def test_clipinfo_carries_codec_name_for_copy_decision() -> None:
    # codec_name defaults to "" and is what lets the transcoder `-c:v copy` H.264.
    assert ClipInfo(10.0, 30.0, 1080, 1920, 0, True).codec_name == ""
    assert ClipInfo(10.0, 30.0, 1080, 1920, 0, True, "h264").codec_name == "h264"


def test_encode_gate_is_a_single_permit_semaphore() -> None:
    assert isinstance(ENCODE_GATE, type(threading.Semaphore()))
    # one permit → acquirable once, second non-blocking acquire fails
    assert ENCODE_GATE.acquire(blocking=False) is True
    try:
        assert ENCODE_GATE.acquire(blocking=False) is False
    finally:
        ENCODE_GATE.release()


def test_pending_response_allows_null_keys() -> None:
    # The async endpoint returns status='pending' with null object_key/url.
    r = transcode.TranscodeResponse(status="pending")
    assert r.status == "pending"
    assert r.object_key is None and r.url is None


# ── ensure_source_mp4 route idempotency (mock the sessionmaker per convention) ──


class _Result:
    def __init__(self, row: object) -> None:
        self._row = row

    def first(self) -> object:
        return self._row


class _Session:
    def __init__(self, rows: list) -> None:
        self._rows = list(rows)
        self._i = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, *a: object, **k: object) -> _Result:
        row = self._rows[self._i]
        self._i += 1
        return _Result(row)


def _patch_sm(monkeypatch: pytest.MonkeyPatch, rows: list) -> None:
    monkeypatch.setattr(transcode, "get_sessionmaker", lambda: (lambda: _Session(rows)))


@pytest.mark.asyncio
async def test_cached_studio_source_returns_ready_without_reencode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A ready studio_source row → return it immediately; NO second transcode.
    _patch_sm(monkeypatch, [("tn1/t1/studio.mp4", "http://cdn/studio.mp4")])
    transcode._inflight.discard("t1")
    res = await transcode.ensure_source_mp4(transcode.TranscodeRequest(tenant_id="tn1", task_id="t1"))
    assert res.status == "ready"
    assert res.object_key == "tn1/t1/studio.mp4"
    assert "t1" not in transcode._inflight  # idempotent — no re-encode kicked off


@pytest.mark.asyncio
async def test_passthrough_for_mp4_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    # No cached source, but the upload is already mp4 → passthrough (no encode).
    _patch_sm(monkeypatch, [None, ("tn1/t1/clip.mp4", "video/mp4")])
    transcode._inflight.discard("t1")
    res = await transcode.ensure_source_mp4(transcode.TranscodeRequest(tenant_id="tn1", task_id="t1"))
    assert res.status == "passthrough"
    assert res.object_key == "tn1/t1/clip.mp4"


@pytest.mark.asyncio
async def test_no_upload_raises_404(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    _patch_sm(monkeypatch, [None, None])
    with pytest.raises(HTTPException) as ei:
        await transcode.ensure_source_mp4(transcode.TranscodeRequest(tenant_id="tn1", task_id="t1"))
    assert ei.value.status_code == 404

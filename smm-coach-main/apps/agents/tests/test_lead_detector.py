"""Tests for the Stage-12 lead detector — the autonomous sales-funnel classifier
that turns post comments into actionable `leads`."""
from __future__ import annotations

import asyncio

from app.graphs import lead_detector as ld


def _patch_chat(monkeypatch, payload=None, raise_llm=False):
    async def _chat(**_kwargs):
        if raise_llm:
            raise RuntimeError("llm down")
        return payload or {}

    monkeypatch.setattr(ld.groq_client, "chat_json", _chat)


def test_empty_comments_skips_llm(monkeypatch):
    called = {"n": 0}

    async def _chat(**_kwargs):
        called["n"] += 1
        return {"leads": []}

    monkeypatch.setattr(ld.groq_client, "chat_json", _chat)
    out = asyncio.run(ld.detect_leads([]))
    assert out == []
    assert called["n"] == 0  # no LLM call for an empty comment set


def test_blank_only_comments_skip_llm(monkeypatch):
    called = {"n": 0}

    async def _chat(**_kwargs):
        called["n"] += 1
        return {"leads": []}

    monkeypatch.setattr(ld.groq_client, "chat_json", _chat)
    out = asyncio.run(ld.detect_leads(["", "   ", "\n"]))
    assert out == []
    assert called["n"] == 0


def test_extracts_valid_leads(monkeypatch):
    _patch_chat(
        monkeypatch,
        payload={
            "leads": [
                {"index": 0, "intent": "lead", "draftReply": "Narxi DM'da, yozing!"},
                {"index": 2, "intent": "question", "draftReply": "Ha, bor."},
            ]
        },
    )
    out = asyncio.run(
        ld.detect_leads(["narxi qancha?", "zo'r!", "bormi hali?"])
    )
    assert [x["index"] for x in out] == [0, 2]
    assert out[0]["intent"] == "lead"
    assert out[1]["intent"] == "question"
    assert out[0]["draftReply"] == "Narxi DM'da, yozing!"


def test_drops_out_of_range_and_duplicate_indices(monkeypatch):
    _patch_chat(
        monkeypatch,
        payload={
            "leads": [
                {"index": 0, "intent": "lead"},
                {"index": 99, "intent": "lead"},   # out of range
                {"index": 0, "intent": "lead"},    # duplicate
                {"index": -1, "intent": "lead"},   # negative
            ]
        },
    )
    out = asyncio.run(ld.detect_leads(["narxi qancha?", "salom"]))
    assert [x["index"] for x in out] == [0]


def test_unknown_intent_clamped_to_lead(monkeypatch):
    _patch_chat(
        monkeypatch,
        payload={"leads": [{"index": 0, "intent": "spam", "draftReply": "x"}]},
    )
    out = asyncio.run(ld.detect_leads(["narxi qancha?"]))
    assert out[0]["intent"] == "lead"


def test_llm_failure_returns_empty(monkeypatch):
    _patch_chat(monkeypatch, raise_llm=True)
    out = asyncio.run(ld.detect_leads(["narxi qancha?"]))
    assert out == []


def test_malformed_payload_returns_empty(monkeypatch):
    _patch_chat(monkeypatch, payload={"leads": ["not-a-dict", {"index": "x"}, {}]})
    out = asyncio.run(ld.detect_leads(["narxi qancha?"]))
    assert out == []

"""Tests for the adversarial_critic node.

The cheap word-count guard runs without an LLM, so it's deterministic to
test. The Gemini critique path is exercised by monkey-patching `call_gemini`
to return canned JSON — we don't want CI dependent on a real Voyage/Gemini
key.
"""
from __future__ import annotations

import json

import pytest

from app.graphs.nodes import adversarial_critic
from app.graphs.state import CostLedger, GrowthCoachState, empty_cost


def _state(approved: list[dict]) -> GrowthCoachState:
    return GrowthCoachState(
        tenant_id="t",
        user_id="u",
        workflow="content_review",
        run_id="r",
        proposed_tasks=[],
        market_signals=[],
        industry_signals=[],
        tracker_observations=[],
        approved_tasks=approved,
        rejected_tasks=[],
        drift_warnings=[],
        validation_errors=[],
        cost=empty_cost(),
        notes=[],
    )


@pytest.mark.asyncio
async def test_critic_passes_through_when_no_rich_scripts() -> None:
    """Topics-only flow (roadmap_generation) → no candidates → no LLM call.

    Each task has only a title + goal, no script_md. The critic returns an
    empty dict so the graph carries on to persist unchanged.
    """
    out = await adversarial_critic.run(
        _state([{"title": "Mavzu 1", "type": "reel"}, {"title": "Mavzu 2", "type": "post"}])
    )
    assert out == {}


@pytest.mark.asyncio
async def test_critic_skips_action_tasks() -> None:
    """Action tasks have their own checklist format — out of scope for the
    script critic. Mixed with a content task, only the content one gets
    looked at (and here it has no script either, so still passthrough)."""
    out = await adversarial_critic.run(
        _state([
            {"title": "Profil sozlash", "type": "action", "script_md": "1. Bio yoz\n2. Avatar qo'y"},
            {"title": "Reel 1", "type": "reel"},
        ])
    )
    assert out == {}


@pytest.mark.asyncio
async def test_critic_word_count_rejects_too_short_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """30-word script trips the cheap min-words guard. The LLM is NEVER called
    in this path — we assert that by raising from any call_gemini invocation.
    """

    async def _explode(**_kwargs: object) -> tuple[str, CostLedger]:
        raise AssertionError("LLM should not be called for word-count rejects")

    monkeypatch.setattr(adversarial_critic, "call_gemini", _explode)

    too_short = "Salom obunachilar. Bugun kichik fikr. Yana ko'proq mavzular keladi."
    out = await adversarial_critic.run(
        _state([{"title": "Reel 1", "type": "reel", "script_md": too_short}])
    )
    assert len(out["rejected_tasks"]) == 1
    assert any("qisqa" in e.get("critic_reason", "") for e in out["validation_errors"])


@pytest.mark.asyncio
async def test_critic_word_count_rejects_too_long_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """600-word script trips the cheap max-words guard."""

    async def _explode(**_kwargs: object) -> tuple[str, CostLedger]:
        raise AssertionError("LLM should not be called for word-count rejects")

    monkeypatch.setattr(adversarial_critic, "call_gemini", _explode)

    too_long = " ".join(["so'z"] * 600)
    out = await adversarial_critic.run(
        _state([{"title": "Reel 1", "type": "reel", "script_md": too_long}])
    )
    assert len(out["rejected_tasks"]) == 1
    assert any("uzun" in e.get("critic_reason", "") for e in out["validation_errors"])


@pytest.mark.asyncio
async def test_critic_passthrough_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """If Gemini blows up (network, 5xx, quota), the script must pass through
    — reliability beats quality gating. A returned `{}` means "no opinion;
    don't change the state".
    """

    async def _boom(**_kwargs: object) -> tuple[str, CostLedger]:
        raise RuntimeError("simulated Gemini outage")

    monkeypatch.setattr(adversarial_critic, "call_gemini", _boom)

    good_length = " ".join(["so'z"] * 200)
    out = await adversarial_critic.run(
        _state([{"title": "Reel 1", "type": "reel", "script_md": good_length}])
    )
    # Cheap guard passed (200 words ∈ [60, 500]) and LLM raised → graceful
    # passthrough. No demotion, no validation errors written.
    assert out == {}


@pytest.mark.asyncio
async def test_critic_demotes_when_llm_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    """A canned Gemini response that flips ok=false demotes the approved task
    into rejected_tasks + proposed_tasks (for scriptwriter rewrite) and
    appends a critic_reasons entry to validation_errors.
    """

    canned = json.dumps({
        "results": [
            {
                "task_id": "0",
                "ok": False,
                "reasons": ["Bo'sh nasihat: faqat 'tirishqoq bo'l' deyilgan"],
            },
        ]
    })

    async def _ok(**_kwargs: object) -> tuple[str, CostLedger]:
        return canned, empty_cost()

    monkeypatch.setattr(adversarial_critic, "call_gemini", _ok)

    good_length = " ".join(["so'z"] * 200)
    out = await adversarial_critic.run(
        _state([{"title": "Reel 1", "type": "reel", "script_md": good_length}])
    )
    assert len(out["rejected_tasks"]) == 1
    assert out["rejected_tasks"][0]["title"] == "Reel 1"
    # Approved must NOT contain the demoted task anymore.
    assert all(t["title"] != "Reel 1" for t in out["approved_tasks"])
    assert any("nasihat" in r for e in out["validation_errors"] for r in e.get("critic_reasons", []))


@pytest.mark.asyncio
async def test_critic_keeps_when_llm_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the LLM returns ok=true for every candidate, the critic emits `{}`
    (no state changes — the script proceeds to persist)."""

    canned = json.dumps({"results": [{"task_id": "0", "ok": True, "reasons": []}]})

    async def _ok(**_kwargs: object) -> tuple[str, CostLedger]:
        return canned, empty_cost()

    monkeypatch.setattr(adversarial_critic, "call_gemini", _ok)

    good_length = " ".join(["so'z"] * 200)
    out = await adversarial_critic.run(
        _state([{"title": "Reel 1", "type": "reel", "script_md": good_length}])
    )
    assert out == {}


def test_allowed_exemplars_reads_both_similarposts_and_exemplarsource() -> None:
    # The scriptwriter grounds real exemplars under predict_evidence.exemplarSource (NOT similarPosts),
    # so criterion #3's allow-list must read exemplarSource too — else it's always empty and every
    # legit exemplar/handle citation gets rejected (wasted Opus rewrites).
    assert adversarial_critic._allowed_exemplars(
        {"predict_evidence": {"exemplarSource": "@madina.style", "exemplarReach": 312000}}
    ) == ["@madina.style"]
    assert adversarial_critic._allowed_exemplars(
        {"predict_evidence": {"similarPosts": [{"source": "@a", "postId": "p1"}, {"postId": "p2"}]}}
    ) == ["p1", "p2"]  # postId preferred over source
    both = adversarial_critic._allowed_exemplars(
        {"predict_evidence": {"similarPosts": [{"source": "@a"}], "exemplarSource": "@b"}}
    )
    assert both == ["@a", "@b"]
    # No grounding → empty (a numeric result-claim then has nothing to be grounded against).
    assert adversarial_critic._allowed_exemplars({}) == []
    assert adversarial_critic._allowed_exemplars({"predict_evidence": None}) == []

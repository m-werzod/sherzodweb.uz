from __future__ import annotations

import pytest

from app.graphs.nodes import output_validator
from app.graphs.state import GrowthCoachState, empty_cost


def _state(tasks: list[dict]) -> GrowthCoachState:
    return GrowthCoachState(
        tenant_id="t",
        user_id="u",
        workflow="content_review",
        run_id="r",
        proposed_tasks=tasks,
        market_signals=[],
        industry_signals=[],
        tracker_observations=[],
        approved_tasks=[],
        rejected_tasks=[],
        drift_warnings=[],
        validation_errors=[],
        cost=empty_cost(),
        notes=[],
    )


@pytest.mark.asyncio
async def test_validator_rejects_ungrounded_growth_claim() -> None:
    out = await output_validator.run(
        _state([{"title": "X", "script_md": "Bu post 10x ko'proq follower olib keladi."}])
    )
    assert out["validation_errors"]
    assert out["approved_tasks"] == []


@pytest.mark.asyncio
async def test_validator_accepts_claim_with_evidence_marker() -> None:
    out = await output_validator.run(
        _state(
            [
                {
                    "title": "X",
                    "script_md": "Bu post 10x reach olib keladi. @evidence: ...",
                    "predict_evidence": {"similarPosts": [{"postId": "abc"}]},
                }
            ]
        )
    )
    assert out["validation_errors"] == []
    assert len(out["approved_tasks"]) == 1


@pytest.mark.asyncio
async def test_validator_accepts_clean_script() -> None:
    out = await output_validator.run(
        _state([{"title": "X", "script_md": "Telefoningni ufq darajada ushlaб ol va boshla."}])
    )
    assert out["validation_errors"] == []
    assert len(out["approved_tasks"]) == 1

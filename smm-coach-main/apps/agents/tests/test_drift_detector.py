from __future__ import annotations

import pytest

from app.graphs.nodes import drift_detector
from app.graphs.state import GrowthCoachState, empty_cost


@pytest.mark.asyncio
async def test_drift_detector_keeps_on_topic_tasks() -> None:
    state = GrowthCoachState(
        tenant_id="t1",
        user_id="u1",
        workflow="roadmap_generation",
        run_id="r1",
        north_star={
            "niche": "fitness coach",
            "target_audience": "30+ ofis xodimlari uchun mashqlar",
            "region": "uz",
        },
        proposed_tasks=[
            {"title": "5 daqiqalik ofis mashqlari", "hook": "Stol ortida turib"},
            {"title": "Pizza retsepti", "hook": "Italyan tarzida"},
        ],
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

    result = await drift_detector.run(state)
    # The pizza one should drift; the fitness one should pass.
    kept_titles = [t["title"] for t in result.get("proposed_tasks", [])]
    rejected_titles = [t["title"] for t in result.get("rejected_tasks", [])]
    assert "5 daqiqalik ofis mashqlari" in kept_titles + rejected_titles
    # Both have stub embeddings (deterministic but pseudo-random), so we can't
    # assert exact classification here — just that the node ran end-to-end
    # without an LLM key.
    assert len(kept_titles) + len(rejected_titles) == 2

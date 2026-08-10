"""Regression lock — the template fallback roadmap must be FLAT (all tasks depth=0, parentId=None).

Branching isn't rendered yet: the persister forces depth=0 / parentId=NULL, and every web+voice
consumer (lib/roadmap/data.ts, voice tools, voice/respond) filters WHERE depth=0. The template used
to emit `depth = 0 if i < 6 else 1`, so on a 20-task roadmap 14 tasks were depth=1 → counted by the
coach ("20 ta vazifa") but never shown on the page — worst in exactly the degraded (LLM-down) mode
this fallback exists to protect. Pin it flat so a re-introduced side-branch can't silently hide tasks.
"""
from __future__ import annotations

import pytest

from app.graphs.nodes._template_roadmap import synthesize_roadmap


@pytest.mark.parametrize("count", [7, 13, 20])
def test_synthesized_roadmap_is_flat(count: int) -> None:
    r = synthesize_roadmap(
        niche="fitnes", target_audience="yoshlar",
        current_followers=200, target_followers=5000, count=count,
    )
    tasks = r["tasks"]
    assert len(tasks) == count
    # No hidden side-branch: every task is a visible, top-level (depth=0, no parent) node.
    assert all(t.get("depth", 0) == 0 for t in tasks), [t.get("depth") for t in tasks]
    assert all(t.get("parentId") is None for t in tasks)

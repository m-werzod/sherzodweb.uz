"""Stage 4 — goal-aware roadmap station subtitles. Followers keep the count
framing; sales/reach/etc. read as stages in THEIR metric, not a follower number."""
from __future__ import annotations

from app.graphs.nodes.roadmap_persister import _station_title


def test_followers_goal_keeps_count_framing():
    assert "K" in _station_title(10_000, "followers", 0.5)
    assert _station_title(1_500_000, "followers", 1.0).startswith("1.5M")


def test_no_goal_defaults_to_count():
    assert "K" in _station_title(5000)
    assert _station_title(0) == "Boshlang'ich · tayyorlanish"


def test_sales_goal_framed_in_sales():
    out = _station_title(10_000, "sales", 0.25)
    assert out.startswith("sotuv")
    assert "birinchi natijalar" in out
    # The follower number must NOT leak into a sales milestone.
    assert "10" not in out and "K" not in out


def test_reach_goal_framed_in_reach():
    assert _station_title(50_000, "reach", 1.0) == "qamrov · maqsad"


def test_engagement_and_authority():
    assert _station_title(0, "engagement", 0.0) == "faollik · tayyorlanish"
    assert _station_title(0, "authority", 0.5) == "nufuz · barqaror o'sish"


def test_unknown_goal_falls_back_to_count():
    # A goal we don't have a word for → follower-count framing.
    assert "K" in _station_title(20_000, "mystery", 0.5)

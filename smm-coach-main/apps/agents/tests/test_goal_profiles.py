from __future__ import annotations

import pytest

from app.graphs import goal_profiles as gp


def test_all_profiles_have_normalised_mixes():
    assert len(gp.GOAL_PROFILES) == 6
    for key, prof in gp.GOAL_PROFILES.items():
        assert prof.key == key
        assert set(prof.funnel_mix) == set(gp.FUNNEL_STAGES)
        assert sum(prof.funnel_mix.values()) == pytest.approx(1.0, abs=1e-9)
        assert sum(prof.type_mix.values()) == pytest.approx(1.0, abs=1e-9)
        assert prof.kpi  # non-empty


def test_blend_primary_only_returns_primary():
    primary = gp.GOAL_PROFILES["reach"].funnel_mix
    assert gp.blend(primary, None, 1.0) == primary


def test_blend_mixes_by_weight():
    primary = {"awareness": 1.0, "consideration": 0.0, "conversion": 0.0}
    secondary = {"awareness": 0.0, "consideration": 1.0, "conversion": 0.0}
    out = gp.blend(primary, secondary, 0.7)
    assert out["awareness"] == pytest.approx(0.7)
    assert out["consideration"] == pytest.approx(0.3)
    assert out["conversion"] == pytest.approx(0.0)


def test_modulate_small_account_favours_awareness_and_normalises():
    base = {"awareness": 0.5, "consideration": 0.3, "conversion": 0.2}
    out = gp.modulate_by_followers(base, current_followers=200)
    assert sum(out.values()) == pytest.approx(1.0)
    assert out["awareness"] > base["awareness"]
    assert out["conversion"] < base["conversion"]


def test_modulate_mature_account_favours_conversion():
    base = {"awareness": 0.5, "consideration": 0.3, "conversion": 0.2}
    out = gp.modulate_by_followers(base, current_followers=50_000)
    assert sum(out.values()) == pytest.approx(1.0)
    assert out["conversion"] > base["conversion"]


def test_modulate_midsize_account_unchanged_but_normalised():
    base = {"awareness": 0.6, "consideration": 0.3, "conversion": 0.1}
    out = gp.modulate_by_followers(base, current_followers=5_000)
    assert out == pytest.approx(base)


def test_funnel_percentages_sum_to_100():
    north = {"primary_goal": "sales", "secondary_goal": "authority",
             "goal_weight": 0.7, "current_followers": 2_000}
    a, c, v = gp.funnel_percentages(north)
    assert a + c + v == 100
    assert all(x >= 0 for x in (a, c, v))


def test_no_goal_keeps_legacy_60_30_10():
    # The 3 pre-existing tenants have no structured goal → unchanged behaviour.
    north = {"current_followers": 2_000}
    assert gp.funnel_percentages(north) == (60, 30, 10)
    directive = gp.goal_directive_uz(north)
    assert directive == gp.LEGACY_DIRECTIVE
    assert "60%" in directive and "30%" in directive and "10%" in directive


def test_directive_for_goal_mentions_label_and_funnel():
    north = {"primary_goal": "sales", "current_followers": 2_000}
    directive = gp.goal_directive_uz(north)
    assert gp.GOAL_PROFILES["sales"].label_uz in directive
    assert "FUNNEL TAQSIMOTI" in directive
    assert "dm" in directive  # sales CTA bias


def test_goal_kpi_falls_back_to_followers():
    assert gp.goal_kpi({"current_followers": 0}) == gp.GOAL_PROFILES["followers"].kpi
    assert gp.goal_kpi({"primary_goal": "sales"}) == gp.GOAL_PROFILES["sales"].kpi


def test_weight_clamped_to_band():
    # weight outside [0.6, 0.8] is clamped, never letting primary drop below 0.6.
    north_lo = {"primary_goal": "reach", "secondary_goal": "sales",
                "goal_weight": 0.1, "current_followers": 5_000}
    a1, c1, v1 = gp.funnel_percentages(north_lo)
    north_clamped = {"primary_goal": "reach", "secondary_goal": "sales",
                     "goal_weight": 0.6, "current_followers": 5_000}
    a2, c2, v2 = gp.funnel_percentages(north_clamped)
    assert (a1, c1, v1) == (a2, c2, v2)


def test_invalid_goal_key_falls_back_to_legacy():
    north = {"primary_goal": "nonsense", "current_followers": 5_000}
    assert gp.funnel_percentages(north) == (60, 30, 10)
    assert gp.goal_directive_uz(north) == gp.LEGACY_DIRECTIVE

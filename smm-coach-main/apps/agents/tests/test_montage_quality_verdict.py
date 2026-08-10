"""Stage 9b Faza-4 — deterministic post-render quality verdict. Pure, structural,
maps the degrade ladder + output stats to good/fair/poor + a remontage flag."""
from __future__ import annotations

from app.montage.compiler import quality_verdict


def test_full_montage_is_good():
    v = quality_verdict(degrade_level=0, cuts=12, duration_sec=42.0)
    assert v["level"] == "good"
    assert v["remontageRecommended"] is False
    assert v["reasons"] == []


def test_no_cuts_concat_fallback_is_fair():
    v = quality_verdict(degrade_level=1, cuts=0, duration_sec=40.0)
    assert v["level"] == "fair"
    assert v["remontageRecommended"] is False
    assert any("Kesimlarsiz" in r for r in v["reasons"])


def test_caption_drop_is_poor():
    v = quality_verdict(degrade_level=2, cuts=0, duration_sec=40.0)
    assert v["level"] == "poor"
    assert v["remontageRecommended"] is True


def test_raw_clip_passthrough_is_poor():
    v = quality_verdict(degrade_level=3, cuts=0, duration_sec=40.0)
    assert v["level"] == "poor"
    assert v["remontageRecommended"] is True
    assert any("xom klip" in r for r in v["reasons"])


def test_total_failure_is_poor():
    v = quality_verdict(degrade_level=4, cuts=0, duration_sec=0.0)
    assert v["level"] == "poor"
    assert v["remontageRecommended"] is True


def test_implausibly_short_output_is_poor_even_at_l0():
    v = quality_verdict(degrade_level=0, cuts=3, duration_sec=3.0)
    assert v["level"] == "poor"
    assert v["remontageRecommended"] is True
    assert any("qisqa" in r for r in v["reasons"])


def test_full_render_with_zero_cuts_on_long_clip_is_fair():
    # L0 but no cuts on a 30s clip → shallow edit heads-up, not a failure.
    v = quality_verdict(degrade_level=0, cuts=0, duration_sec=30.0)
    assert v["level"] == "fair"
    assert v["remontageRecommended"] is False
    assert any("kesim" in r.lower() for r in v["reasons"])


def test_single_cut_passthrough_on_short_clip_is_fair():
    # The real prod regression: a 10.7s clip rendered as ONE uncut segment scored
    # "good" (9/10). One cut = the whole clip = passthrough; the edit floor should
    # have subdivided it, so <=1 cut on an >=8s clip is a shallow-edit heads-up.
    v = quality_verdict(degrade_level=0, cuts=1, duration_sec=10.7)
    assert v["level"] == "fair"
    assert v["remontageRecommended"] is False
    assert any("sayoz" in r.lower() for r in v["reasons"])


def test_short_clip_no_cuts_stays_good():
    # A genuinely short clip (< the 8s edit-floor) needs no cuts → still good.
    v = quality_verdict(degrade_level=0, cuts=0, duration_sec=6.0)
    assert v["level"] == "good"

"""Baseline grade knob — every render inherits normalize_clip's vf, so a bad filter string
would break ALL montages. The ffmpeg filter validity is smoke-checked in the container; here
we pin the mode selection so `off` is truly a no-op and the default stays gentle."""
from __future__ import annotations

import pytest

from app.montage.normalize import _base_grade_vf


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("MONTAGE_BASE_GRADE", raising=False)


def test_default_is_a_gentle_light_grade():
    vf = _base_grade_vf()
    assert vf.startswith("eq=") and vf.endswith(",")  # slots into the vf chain
    assert "curves" not in vf  # light = no S-curve
    assert "contrast=1.05" in vf


def test_off_is_a_true_noop(monkeypatch):
    monkeypatch.setenv("MONTAGE_BASE_GRADE", "off")
    assert _base_grade_vf() == ""


def test_medium_adds_an_s_curve(monkeypatch):
    monkeypatch.setenv("MONTAGE_BASE_GRADE", "medium")
    vf = _base_grade_vf()
    assert "curves=preset=medium_contrast" in vf and vf.endswith(",")


def test_unknown_value_falls_back_to_light(monkeypatch):
    monkeypatch.setenv("MONTAGE_BASE_GRADE", "wild")
    vf = _base_grade_vf()
    assert vf.startswith("eq=") and "curves" not in vf  # unknown → the safe light default

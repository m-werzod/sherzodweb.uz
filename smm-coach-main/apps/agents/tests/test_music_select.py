"""Stage 9c — music selection: energy-match via manifest, deterministic seed
fallback. Pure (no filesystem), so it pins the logic before CC0 tracks land."""
from __future__ import annotations

from app.montage.music import select_track

TRACKS = [
    "/m/calm.mp3",
    "/m/mid.mp3",
    "/m/hype.mp3",
]
MANIFEST = {
    "calm.mp3": {"energy": 0.1, "mood": "calm", "bpm": 80},
    "mid.mp3": {"energy": 0.5, "mood": "neutral", "bpm": 110},
    "hype.mp3": {"energy": 0.9, "mood": "energetic", "bpm": 140},
}


def test_no_tracks_returns_none():
    assert select_track([], MANIFEST, seed=1, energy=0.5) is None


def test_high_energy_picks_hype():
    assert select_track(TRACKS, MANIFEST, seed=0, energy=0.85) == "/m/hype.mp3"


def test_low_energy_picks_calm():
    assert select_track(TRACKS, MANIFEST, seed=3, energy=0.05) == "/m/calm.mp3"


def test_mid_energy_picks_mid():
    assert select_track(TRACKS, MANIFEST, seed=7, energy=0.45) == "/m/mid.mp3"


def test_no_manifest_falls_back_to_seed():
    # seed=1 → index 1 of 3.
    assert select_track(TRACKS, {}, seed=1, energy=0.9) == "/m/mid.mp3"


def test_no_energy_uses_seed_even_with_manifest():
    assert select_track(TRACKS, MANIFEST, seed=2, energy=None) == "/m/hype.mp3"


def test_deterministic_for_same_inputs():
    a = select_track(TRACKS, MANIFEST, seed=5, energy=0.5)
    b = select_track(TRACKS, MANIFEST, seed=5, energy=0.5)
    assert a == b

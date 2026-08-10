"""Background-music selection. The repo bundles no tracks by default, so the
feature is dormant (voice-only) until CC0 mp3s are dropped into app/assets/music/."""
from __future__ import annotations

from app.montage.music import available_tracks, pick_track


def test_dormant_without_tracks() -> None:
    # No bundled tracks => pick_track returns None and the compiler stays voice-only.
    if not available_tracks():
        assert pick_track() is None
        assert pick_track(99) is None


def test_pick_is_deterministic_when_tracks_present() -> None:
    tracks = available_tracks()
    if tracks:
        assert pick_track(0) == tracks[0]
        assert pick_track(len(tracks)) == tracks[0]  # wraps by modulo

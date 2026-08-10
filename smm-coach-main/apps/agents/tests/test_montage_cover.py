"""Cover/thumbnail extraction (playbook: a reel without a cover shows a random grid frame).
The ffmpeg frame grab is smoke-tested in the container; here we pin the key format + fail-soft."""
from __future__ import annotations

from app.workers import montage_worker


def test_extract_cover_returns_key_and_url(tmp_path, monkeypatch):
    video = tmp_path / "montage.mp4"
    video.write_bytes(b"x")

    def fake_run_ff(cmd, **k):
        # simulate ffmpeg writing the cover jpg (last arg = output path)
        with open(cmd[-1], "wb") as f:
            f.write(b"jpeg")

    up = {}
    monkeypatch.setattr(montage_worker, "run_ff", fake_run_ff)
    monkeypatch.setattr(montage_worker, "upload_object", lambda key, path, **k: up.update(key=key))
    monkeypatch.setattr(montage_worker, "media_url", lambda key: f"/api/media/{key}")
    ck, cu = montage_worker._extract_cover(str(video), "tenant1", "task9", "med5", 20.0)
    assert ck == "tenant1/task9/cover-med5.jpg"
    assert cu == "/api/media/tenant1/task9/cover-med5.jpg"
    assert up["key"] == ck  # uploaded under the same key


def test_extract_cover_failsoft(tmp_path, monkeypatch):
    def boom(cmd, **k):
        raise RuntimeError("ffmpeg died")

    monkeypatch.setattr(montage_worker, "run_ff", boom)
    ck, cu = montage_worker._extract_cover(str(tmp_path / "v.mp4"), "t", "k", "m", 10.0)
    assert ck is None and cu is None  # a cover failure never breaks the render

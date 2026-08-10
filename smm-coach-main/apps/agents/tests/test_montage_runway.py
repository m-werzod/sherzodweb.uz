"""Runway restyle pipeline — pure-logic guards (output extraction, request body, caption timing)."""
from __future__ import annotations

import pytest

from app.montage import runway_client as rc
from app.montage import runway_restyle as rr


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"output": ["https://cdn/a.mp4"]}, "https://cdn/a.mp4"),
        ({"output": ["https://cdn/a.mp4", "https://cdn/b.mp4"]}, "https://cdn/a.mp4"),
        ({"output": "https://cdn/c.mp4"}, "https://cdn/c.mp4"),
        ({"output": [{"url": "https://cdn/d.mp4"}]}, "https://cdn/d.mp4"),
        ({"output": []}, None),
        ({"status": "SUCCEEDED"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_extract_output_url(payload, expected):
    assert rc.extract_output_url(payload) == expected


def test_build_body():
    body = rc.build_body(
        model="gen4_aleph", video_url="https://k/v.mp4", prompt="cinematic", ratio="720:1280", seed=42
    )
    assert body["model"] == "gen4_aleph"
    assert body["videoUri"] == "https://k/v.mp4"
    assert body["promptText"] == "cinematic"
    assert body["ratio"] == "720:1280"
    assert body["seed"] == 42


def test_build_body_omits_zero_seed():
    body = rc.build_body(model="gen4_aleph", video_url="https://k/v.mp4", prompt="p", ratio="720:1280", seed=0)
    assert "seed" not in body


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0-3s", (0.0, 3.0)),
        ("3-13s", (3.0, 13.0)),
        (" 10 - 12.5 s", (10.0, 12.5)),
        ("3-3s", None),   # zero-length
        ("bad", None),
        (None, None),
    ],
)
def test_parse_range(raw, expected):
    assert rr._parse_range(raw) == expected


def test_build_captions_clips_to_duration():
    st = [
        {"t": "0-3s", "text": "salom dunyo"},
        {"t": "3-13s", "text": "ikkinchi qism"},
        {"t": "20-25s", "text": "oxiri"},  # beyond max_dur → dropped
    ]
    caps = rr.build_captions(st, max_dur=15.0, style_spec={"font": "Anton"})
    assert caps.tier == "premium"
    assert caps.style.font == "Anton"
    assert len(caps.windows) == 2                       # third dropped (starts at 20 > 15)
    assert caps.windows[0].words[0].text == "salom"
    assert caps.windows[0].words[0].start == 0.0
    # second window end clipped to max_dur (13 < 15 so unchanged here)
    assert caps.windows[1].words[-1].end == pytest.approx(13.0)


def test_build_captions_bad_font_falls_back():
    caps = rr.build_captions([{"t": "0-2s", "text": "hi"}], max_dur=10.0, style_spec={"font": "ComicSans"})
    assert caps.style.font == "Montserrat"

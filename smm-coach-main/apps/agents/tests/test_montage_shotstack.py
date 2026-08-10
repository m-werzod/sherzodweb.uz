"""Shotstack cloud-render mapper — pure guards (SRT build + EDL→timeline translation)."""
from __future__ import annotations

from app.montage.edl import EDL, Broll, CaptionWindow, CaptionWord, Cut, Overlay, Source, Transition
from app.montage.shotstack_map import _ts, build_edit, srt_from_captions


def _edl():
    return EDL(task_id="t", tenant_id="x", source=Source(upload_key="k", duration_sec=30.0),
               cuts=[Cut(src_start=0.0, src_end=5.0), Cut(src_start=10.0, src_end=15.0),
                     Cut(src_start=20.0, src_end=22.0)])


def test_ts_format():
    assert _ts(0.0) == "00:00:00,000"
    assert _ts(83.5) == "00:01:23,500"


def test_srt_from_captions():
    e = _edl()
    e.captions.windows = [
        CaptionWindow(words=[CaptionWord(text="salom", start=0.0, end=0.5),
                             CaptionWord(text="dunyo", start=0.5, end=1.0)]),
        CaptionWindow(words=[CaptionWord(text="ikkinchi", start=2.0, end=2.8)]),
    ]
    srt = srt_from_captions(e.captions)
    assert "1\n00:00:00,000 --> 00:00:01,000\nsalom dunyo" in srt
    assert "2\n00:00:02,000 --> 00:00:02,800\nikkinchi" in srt


def test_srt_empty():
    assert srt_from_captions(_edl().captions) == ""


def test_build_edit_cuts_two_timebases():
    e = _edl()
    edit = build_edit(e, "https://cdn/src.mp4")
    base = edit["timeline"]["tracks"][-1]["clips"]  # base video = last visual track (no music)
    assert [c["asset"]["trim"] for c in base] == [0.0, 10.0, 20.0]   # SOURCE seconds
    assert [c["start"] for c in base] == [0.0, 5.0, 10.0]            # OUTPUT seconds
    assert [c["length"] for c in base] == [5.0, 5.0, 2.0]
    assert base[0]["effect"] == "zoomInSlow" and base[1]["effect"] == "zoomOutSlow"  # gentle push/pull, no slides
    assert edit["output"]["size"] == {"width": 1080, "height": 1920}


def test_build_edit_transitions_flank_boundary():
    e = _edl()
    e.transitions = [Transition(at_sec=5.0, type="fade", dur=0.3)]  # boundary after cut 0
    base = build_edit(e, "https://cdn/s.mp4")["timeline"]["tracks"][-1]["clips"]
    assert base[0].get("transition", {}).get("out") in ("zoom", "slideLeft", "fade", "slideUp")
    assert base[1].get("transition", {}).get("in") in ("zoom", "slideLeft", "fade", "slideUp")
    assert "transition" not in base[2]


def test_build_edit_layers():
    e = _edl()
    e.captions.windows = [CaptionWindow(words=[CaptionWord(text="x", start=0.0, end=1.0)])]
    e.hook.hook_text = "Kuchli hook"
    e.overlays = [Overlay(template="callout", at_sec=6.0, dur=2.0, text="50% chegirma")]
    e.broll = [Broll(shot_index=2, source="stock", at_sec=5.0, output_dur_sec=3.0, asset_url="https://p/b.mp4")]
    edit = build_edit(e, "https://cdn/s.mp4", srt_url="https://cdn/c.srt",
                      music_url="https://cdn/m.mp3", broll_urls={2: "https://p/b.mp4"})
    tracks = edit["timeline"]["tracks"]
    # Probe-proven: plain caption = per-cue subtitles; rich-caption merged all cues
    # into one center paragraph over the speaker's face.
    assert tracks[0]["clips"][0]["asset"]["type"] == "caption"
    assert tracks[0]["clips"][0]["asset"]["margin"]["top"] >= 0.6  # never on a face
    assert tracks[1]["clips"][0]["asset"]["type"] == "text"        # hook + overlays
    assert len(tracks[1]["clips"]) == 2
    assert tracks[2]["clips"][0]["asset"]["type"] == "video"       # b-roll
    assert tracks[2]["clips"][0]["asset"]["volume"] == 0
    assert tracks[-1]["clips"][0]["asset"]["type"] == "audio"      # music bottom
    assert tracks[-1]["clips"][0]["asset"]["volume"] == 0.15


def test_build_edit_no_optional_tracks():
    edit = build_edit(_edl(), "https://cdn/s.mp4")
    tracks = edit["timeline"]["tracks"]
    assert len(tracks) == 1  # only the base video track


def test_build_edit_card_under_text():
    e = _edl()
    e.overlays = [Overlay(template="callout", at_sec=6.0, dur=2.0, text="50%")]
    edit = build_edit(_edl_with(e), "https://cdn/s.mp4", card_urls={0: "https://img/card.png"})
    tracks = edit["timeline"]["tracks"]
    # text track first (top), card track right below it, then base video
    assert tracks[0]["clips"][0]["asset"]["type"] == "text"
    assert tracks[1]["clips"][0]["asset"]["type"] == "image"
    assert tracks[1]["clips"][0]["asset"]["src"] == "https://img/card.png"
    assert tracks[1]["clips"][0]["start"] == 6.0
    assert tracks[-1]["clips"][0]["asset"]["type"] == "video"


def _edl_with(e):
    return e


def test_card_prompt_forbids_text():
    from app.montage.visual_cards import card_prompt
    p = card_prompt("50% chegirma")
    assert "50% chegirma" in p
    assert "no text" in p


def test_generate_overlay_cards_disabled(monkeypatch):
    import app.montage.visual_cards as vc
    monkeypatch.setattr(vc, "higgsfield_enabled", lambda: False)
    e = _edl()
    e.overlays = [Overlay(template="callout", at_sec=1.0, dur=2.0, text="x")]
    assert vc.generate_overlay_cards(e) == {}


def test_generate_overlay_cards_callouts_only(monkeypatch):
    import app.montage.visual_cards as vc
    monkeypatch.setattr(vc, "higgsfield_enabled", lambda: True)
    monkeypatch.setattr(vc, "generate_image", lambda p, **k: "https://img/c.png")
    e = _edl()
    e.overlays = [
        Overlay(template="callout", at_sec=1.0, dur=2.0, text="10 daqiqa"),
        Overlay(template="title", at_sec=4.0, dur=2.0, text="oddiy sarlavha"),
    ]
    cards = vc.generate_overlay_cards(e)
    assert cards == {0: "https://img/c.png"}   # only the callout, keyed by overlay index


# --- _finish (post-Shotstack polish: denoise + duck + SFX + loudnorm + karaoke burn) --------


def _finish_edl(music_path=None):
    from app.montage.edl import EDL, Source
    edl = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k", duration_sec=6.0))
    edl.audio.music_path = music_path
    edl.audio.sfx = []  # empty → no lavfi synth in the unit test
    return edl


def test_finish_audio_ducks_music_and_loudnorms(tmp_path, monkeypatch):
    from app.montage import shotstack_map
    music = tmp_path / "m.wav"
    music.write_bytes(b"x")
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"x")
    out = tmp_path / "out.mp4"
    cap = {}

    def fake_run_ff(cmd, **k):
        cap["cmd"] = cmd
        out.write_bytes(b"y")

    monkeypatch.setattr(shotstack_map, "run_ff", fake_run_ff)
    assert shotstack_map._finish(str(raw), _finish_edl(str(music)), str(tmp_path), str(out))
    fc = " ".join(cap["cmd"])
    assert "sidechaincompress" in fc  # bed ducks under the voice
    assert "loudnorm=I=-14.0" in fc   # normalized to the -14 LUFS target
    assert "afftdn" in fc and "deesser" in fc  # voice denoise + de-ess
    assert "-c:v copy" in fc  # Shotstack video kept as-is (no re-encode)


def test_finish_audio_no_music_uses_voice_chain(tmp_path, monkeypatch):
    from app.montage import shotstack_map
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"x")
    out = tmp_path / "out.mp4"
    cap = {}
    monkeypatch.setattr(shotstack_map, "run_ff", lambda cmd, **k: (cap.__setitem__("cmd", cmd), out.write_bytes(b"y")))
    assert shotstack_map._finish(str(raw), _finish_edl(None), str(tmp_path), str(out))
    fc = " ".join(cap["cmd"])
    assert "sidechaincompress" not in fc  # no music → nothing to duck
    assert "loudnorm" in fc and "afftdn" in fc  # still cleaned + normalized


def test_finish_audio_failsoft(tmp_path, monkeypatch):
    from app.montage import shotstack_map

    def boom(cmd, **k):
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(shotstack_map, "run_ff", boom)
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"x")
    out = tmp_path / "out.mp4"
    assert shotstack_map._finish(str(raw), _finish_edl(None), str(tmp_path), str(out)) is False


def test_finish_burns_karaoke_ass_when_given(tmp_path, monkeypatch):
    from app.montage import shotstack_map
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"x")
    ass = tmp_path / "cap.ass"
    ass.write_text("[Events]\n", encoding="utf-8")
    out = tmp_path / "out.mp4"
    cap = {}

    def fake_run_ff(cmd, **k):
        cap["cmd"] = cmd
        out.write_bytes(b"y")

    monkeypatch.setattr(shotstack_map, "run_ff", fake_run_ff)
    assert shotstack_map._finish(str(raw), _finish_edl(None), str(tmp_path), str(out), caption_ass=str(ass))
    fc = " ".join(cap["cmd"])
    assert f"ass={ass}" in fc  # karaoke ASS burned
    assert "-c:v libx264" in fc  # video re-encoded (not copied) to bake the captions
    assert "-c:v copy" not in fc


def test_finish_copies_video_without_ass(tmp_path, monkeypatch):
    from app.montage import shotstack_map
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"x")
    out = tmp_path / "out.mp4"
    cap = {}
    monkeypatch.setattr(shotstack_map, "run_ff", lambda cmd, **k: (cap.__setitem__("cmd", cmd), out.write_bytes(b"y")))
    assert shotstack_map._finish(str(raw), _finish_edl(None), str(tmp_path), str(out), caption_ass=None)
    fc = " ".join(cap["cmd"])
    assert "-c:v copy" in fc and "ass=" not in fc  # no captions → keep Shotstack video as-is


def test_build_edit_punch_uses_stronger_zoom():
    from app.montage.edl import Motion
    e = _edl()
    # a planned emphasis punch inside cut 1's OUTPUT window [5,10)
    e.motion = [Motion(op="zoom_punch", at_sec=6.0, dur=0.5, to_scale=1.15)]
    base = build_edit(e, "https://cdn/s.mp4")["timeline"]["tracks"][-1]["clips"]
    assert base[1]["effect"] == "zoomIn"      # emphasized cut gets the pronounced push
    assert base[0]["effect"] == "zoomInSlow"  # ambient cut keeps the gentle drift
    assert "slide" not in base[0]["effect"] and "slide" not in base[2]["effect"]


# --- caption/overlay placement must NOT collide (burned caption vs Shotstack rows) ------------


def _frac_from_top_caption(align: int, margin_v: int, play_h: int = 1920) -> float:
    # ASS: align 2 = bottom-anchored (MarginV from bottom), 8 = top-anchored (from top).
    return (1.0 - margin_v / play_h) if align == 2 else (margin_v / play_h)


def _frac_from_top_layout(position: str, offset: float) -> float:
    # Shotstack: position 'top' + offset.y (negative moves DOWN); 'bottom' + offset.y (positive up).
    return (-offset) if position == "top" else (1.0 - offset)


def test_shotstack_rows_never_share_the_burned_caption_band():
    from app.montage.captions import _FACE_LAYOUT
    from app.montage.shotstack_map import _LAYOUTS
    for zone, lay in _LAYOUTS.items():
        cap_align, cap_mv = _FACE_LAYOUT[zone][0], _FACE_LAYOUT[zone][1]
        cap = _frac_from_top_caption(cap_align, cap_mv)
        for element, (pos, off) in lay.items():
            row = _frac_from_top_layout(pos, off)
            gap = abs(cap - row)
            # a burned caption on top of a Shotstack overlay/hook/card = text-on-text
            assert gap >= 0.12, f"{zone}/{element}: caption@{cap:.3f} vs row@{row:.3f} gap={gap:.3f}"


def test_finish_audio_honors_duck_volume(tmp_path, monkeypatch):
    # The music-bed gain is now READ from edl.audio.duck.volume (was a hardcoded 0.12), so STUDIO's
    # duckLevel (edlAudioSettings) and this renderer stay in sync. A custom volume must reach ffmpeg.
    from app.montage import shotstack_map

    music = tmp_path / "m.wav"; music.write_bytes(b"x")
    raw = tmp_path / "raw.mp4"; raw.write_bytes(b"x")
    out = tmp_path / "out.mp4"
    cap = {}
    monkeypatch.setattr(shotstack_map, "run_ff", lambda cmd, **k: (cap.__setitem__("cmd", cmd), out.write_bytes(b"y")))
    edl = _finish_edl(str(music))
    edl.audio.duck.volume = 0.3
    assert shotstack_map._finish(str(raw), edl, str(tmp_path), str(out))
    fc = " ".join(cap["cmd"])
    assert "volume=0.3" in fc and "volume=0.12" not in fc  # honors the field, not a hardcode


# --- render_via_shotstack: a _finish failure must NOT silently ship a caption-less cloud raw -----


def _render_edl():
    e = _edl()
    e.captions.windows = [CaptionWindow(words=[CaptionWord(text="Salom", start=0.5, end=1.0)])]
    return e


def _patch_cloud(monkeypatch, finish_result):
    """Wire render_via_shotstack's externals so ONLY _finish's success/failure drives the outcome."""
    from app.montage import shotstack_map
    import app.montage.visual_cards as vc

    monkeypatch.setattr(shotstack_map.shotstack_client, "shotstack_enabled", lambda: True)
    monkeypatch.setattr(shotstack_map, "upload_file", lambda p: "https://u/x.mp4")
    monkeypatch.setattr(shotstack_map.shotstack_client, "render", lambda edit: "https://r/out.mp4")
    monkeypatch.setattr(vc, "generate_overlay_cards", lambda edl: {})
    monkeypatch.setattr(shotstack_map, "_finish", lambda *a, **k: finish_result)

    class _Resp:
        status_code = 200
        content = b"rawvideobytes"

    class _Client:
        def __init__(self, *a, **k): ...
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def get(self, url):
            return _Resp()

    monkeypatch.setattr(shotstack_map.httpx, "Client", _Client)


def test_render_via_shotstack_finish_fail_with_ass_falls_back_local(tmp_path, monkeypatch):
    # Karaoke ASS requested → the cloud rendered caption-LESS; a _finish failure must return False so
    # compile_and_render drops to the local ladder (which burns captions) instead of shipping the raw
    # uncaptioned reel as degrade=0/'good'. The raw file must NOT be moved into place.
    from app.montage import shotstack_map

    _patch_cloud(monkeypatch, finish_result=False)
    ass = tmp_path / "captions_only.ass"; ass.write_text("[Script Info]\n", encoding="utf-8")
    out = tmp_path / "montage.mp4"
    ok = shotstack_map.render_via_shotstack(
        _render_edl(), str(tmp_path / "norm.mp4"), str(tmp_path), str(out), caption_ass=str(ass)
    )
    assert ok is False
    assert not out.exists()


def test_render_via_shotstack_finish_fail_without_ass_keeps_cloud_raw(tmp_path, monkeypatch):
    # Legacy no-ASS path: the cloud baked static SRT captions in, so an audio-only _finish failure may
    # still ship the captioned raw render rather than discarding a good cloud result.
    from app.montage import shotstack_map

    _patch_cloud(monkeypatch, finish_result=False)
    out = tmp_path / "montage.mp4"
    ok = shotstack_map.render_via_shotstack(
        _render_edl(), str(tmp_path / "norm.mp4"), str(tmp_path), str(out), caption_ass=None
    )
    assert ok is True
    assert out.exists()


def test_render_via_shotstack_finish_ok_returns_true(tmp_path, monkeypatch):
    # Sanity: when _finish succeeds it writes out_path and the call returns True (no fallback).
    from app.montage import shotstack_map

    out = tmp_path / "montage.mp4"

    def _ok_finish(raw, edl, wd, op, caption_ass=None):
        with open(op, "wb") as f:
            f.write(b"polished")
        return True

    _patch_cloud(monkeypatch, finish_result=True)
    monkeypatch.setattr(shotstack_map, "_finish", _ok_finish)
    ass = tmp_path / "captions_only.ass"; ass.write_text("[Script Info]\n", encoding="utf-8")
    ok = shotstack_map.render_via_shotstack(
        _render_edl(), str(tmp_path / "norm.mp4"), str(tmp_path), str(out), caption_ass=str(ass)
    )
    assert ok is True
    assert out.exists()

"""SFX sound-design — pure guards (derive floor + ffmpeg graph shape)."""
from __future__ import annotations

from app.montage.edl import EDL, Cut, Overlay, Sfx, Source, Transition
from app.montage.sfx import _MAX_SFX, derive_sfx_events, sfx_graph


def _edl(overlays=(), transitions=()):
    e = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"),
            cuts=[Cut(src_start=0.0, src_end=5.0)])
    e.overlays = list(overlays)
    e.transitions = list(transitions)
    return e


def test_derive_whoosh_on_overlays_glitch_on_transitions():
    e = _edl(
        overlays=[Overlay(template="callout", at_sec=1.0, dur=1.5, text="50%")],
        transitions=[Transition(at_sec=5.0, type="glitch", dur=0.3)],
    )
    ev = derive_sfx_events(e)
    assert [(x.at_sec, x.type) for x in ev] == [(1.0, "whoosh"), (5.0, "glitch")]


def test_derive_decrowds_and_caps():
    ovs = [Overlay(template="t", at_sec=i * 0.3, dur=1.0, text="x") for i in range(20)]
    ev = derive_sfx_events(_edl(overlays=ovs))
    assert len(ev) <= _MAX_SFX
    for a, b in zip(ev, ev[1:], strict=False):
        assert b.at_sec - a.at_sec >= 0.8


def test_derive_empty():
    assert derive_sfx_events(_edl()) == []


def test_sfx_graph_labels_and_delay(tmp_path, monkeypatch):
    # Stub synthesis — graph shape is what we lock here, not ffmpeg output.
    import app.montage.sfx as m
    monkeypatch.setattr(m, "synth_sfx", lambda t, d: str(tmp_path / f"{t}.wav"))
    inputs, parts = sfx_graph([Sfx(at_sec=1.25, type="whoosh"), Sfx(at_sec=4.0, type="glitch")],
                              str(tmp_path), first_input_idx=3)
    assert inputs == ["-i", str(tmp_path / "whoosh.wav"), "-i", str(tmp_path / "glitch.wav")]
    assert parts[0] == "[3:a]adelay=1250|1250[sd0]"
    assert parts[1] == "[4:a]adelay=4000|4000[sd1]"
    assert parts[-1].endswith("[sfxall]") and "normalize=0" in parts[-1]


def test_sfx_graph_empty_when_synth_fails(monkeypatch, tmp_path):
    import app.montage.sfx as m
    monkeypatch.setattr(m, "synth_sfx", lambda t, d: None)
    inputs, parts = sfx_graph([Sfx(at_sec=1.0, type="whoosh")], str(tmp_path), 2)
    assert inputs == [] and parts == []

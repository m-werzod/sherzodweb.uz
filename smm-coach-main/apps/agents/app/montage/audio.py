"""Deterministic voice audio chain.

Operates on the user's OWN voice (the clip's audio tracked through the same cuts,
so A/V stays in lockstep): denoise -> de-ess -> loudness-normalize to the -14 LUFS
IG/TikTok target. This module builds only the VOICE-side af chain (`build_voice_chain`).

Music ducking is live: the music bed is sidechain-compressed against the dry voice
where the mix happens — the local compiler filtergraph (`compiler.py`) and the
post-Shotstack `_finish` pass (`shotstack_map.py`) — driven by `edl.audio.duck`
(volume/threshold/ratio/attack/release). STUDIO mirrors the same duck via
`edlAudioSettings`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.montage.edl import Audio


def build_voice_chain(audio: Audio) -> str:
    """The af filter chain applied to the concatenated voice track."""
    ln = audio.loudnorm
    return ",".join(
        [
            "afftdn=nf=-25",  # FFT denoise — no external model needed (vs arnndn)
            "deesser",  # tame sibilance
            f"loudnorm=I={ln.i}:TP={ln.tp}:LRA={ln.lra}",  # single-pass to target
        ]
    )

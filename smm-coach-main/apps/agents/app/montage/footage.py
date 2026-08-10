"""The FootageMap — the montage system's structured UNDERSTANDING of an uploaded clip.

Faza 1 (G2 fix): before Faza 1 the montage was blind — it cut on silence alone and
never "saw" the footage. footage_analyzer now produces a FootageMap: deterministic shot
boundaries (ffmpeg scene-detection) enriched with Gemini vision (what's on screen per
shot, which storyboard shot it matches). Persisted to the user_upload TaskMedia.meta so
it's inspectable and so later faza (content-aware cuts / transitions / b-roll) can consume it.

All shot times are SOURCE seconds (positions in the uploaded clip) — the same timebase as
EDL.cuts — so nothing here touches the two-timebase offset table.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ShotBoundary(BaseModel):
    """One detected shot (a continuous run of footage between scene changes)."""

    index: int
    src_start: float  # SOURCE seconds
    src_end: float
    detected_by: str = "scene"  # 'scene' (ffmpeg scdet) | 'fallback' (whole clip, no cut found)
    # Gemini vision enrichment (empty when vision degraded — shots still carry scdet geometry):
    description: str = ""  # what is visible on screen this shot
    subject: str = ""  # dominant subject: person | product | text | screen | scene | hands | ...
    primary_action: str = ""  # talking | demo | reveal | gesturing | b_roll | ...
    # The scriptwriter storyboard shot (shotList[].i, 1-indexed; 0 = no confident match) this
    # footage shot best illustrates — the footage<->storyboard alignment ("shot match").
    matched_shot_index: int = 0
    motion_score: float = 0.5  # 0 = static, 1 = high motion (vision estimate)
    confidence: float = 1.0


class FootageMap(BaseModel):
    version: int = 1
    task_id: str
    tenant_id: str
    duration_sec: float = 0.0
    fps: float = 30.0
    width: int = 1080
    height: int = 1920
    shots: list[ShotBoundary] = Field(default_factory=list)
    vision_summary: str = ""  # 1-2 sentence what-is-this-clip
    detected_subjects: list[str] = Field(default_factory=list)
    # True when Gemini vision succeeded; False = shots are scdet-only (proxy too big, no key,
    # or vision error). The clip was still analysed structurally — just not described.
    vision_ok: bool = False

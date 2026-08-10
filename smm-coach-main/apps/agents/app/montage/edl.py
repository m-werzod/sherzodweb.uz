"""The Edit-Decision-List (EDL) — the contract between the montage planning agents
and the deterministic ffmpeg compiler.

Every montage node reads/writes ONE EDL object on GrowthCoachState (channel `edl`,
REPLACED per pass) and the final EDL is persisted to TaskMedia.meta so any montage
is reproducible/inspectable (mirrors the AI Inspector philosophy).

THE CRITICAL TWO-TIMEBASE RULE
==============================
There are two clocks and mixing them silently desyncs every overlay:

  * SOURCE seconds  — positions inside the user's uploaded clip.
                      Used by: `cuts`, `wordmap`, `hook.cold_open_src`,
                      `hook.frame1_override_src_sec`, `broll.ref_frame_src_sec`.
  * OUTPUT seconds  — positions on the FINAL post-cut timeline.
                      Used by: `motion`, `transitions`, `overlays`, `captions`,
                      `audio.beat_grid`, `audio.sfx`.

The compiler builds the source->output offset table from `cuts` ONCE (see
`EDL.output_duration` / `source_to_output` / `output_to_source`) and translates
centrally. `montage_director` bounds-validates every OUTPUT atSec against
`output_duration()` before QC. Get this wrong and every caption drifts.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# --- timebase = SOURCE seconds (positions in the uploaded clip) ----------


class Source(BaseModel):
    upload_key: str
    duration_sec: float = 0.0
    fps: float = 30.0  # set by normalize.py — every timebase assumes CFR
    w: int = 1080
    h: int = 1920
    # v2 (additiv): bu manba GPU-pass natijasi bo'lsa — reproduksiya/audit uchun.
    derived_from: str | None = None  # asl upload_key
    gpu_pass: str | None = None  # eye_contact | inpaint | cleaned | ...


# --- v2 (additiv) qatlamlar — GPU-plane (Faza B/C/D) to'ldiradi -----------
# INVARIANT: v1 maydon hech qachon o'chmaydi/qayta-ishlatilmaydi — faqat qo'shiladi.
# Hammasi IXTIYORIY + default, shuning uchun bo'sh EDL bayt-bir xil v1 bo'lib qoladi.
# STUDIO clipsFromEdl bularni hali o'qimaydi; kontrakt oldindan qulflanadi (montage.ts ko'zgu).


class AssetRef(BaseModel):
    """Yangi qatlam media havolasi. broll.asset_url bare-string yetarsiz edi — STUDIO
    MediaAsset'iga ro'yxatdan o'tkazish uchun kind/duration/o'lcham kerak."""

    asset_id: str
    url: str | None = None
    upload_key: str | None = None
    kind: str = "video"  # video | image | audio | matte
    duration_sec: float = 0.0
    w: int = 1080
    h: int = 1920
    fps: float = 30.0


class SourceVariant(BaseModel):
    """SOURCE-vaqtli 1:1 alternativ render (eye_contact/inpaint/cleaned/decor). Davomiylik saqlanadi,
    shuning uchun offset-jadval o'zgarmaydi — kompilyator faqat base assetni almashtiradi.
    decor = matli subjekt generatsiya fon ustiga kompozit qilingan to'liq-kadr variant."""

    kind: str  # cleaned | inpaint | eye_contact | decor
    asset: AssetRef
    aligned_to_source: bool = True


class LangVariant(BaseModel):
    """SOURCE-vaqtli 1:1 til-tarjima varianti (HeyGen Video Translation, lip-sync). Davomiylik saqlanadi
    (dynamic_duration=False), shuning uchun offset-jadval (cuts/captions/motion) o'zgarmaydi — STUDIO
    faqat base VIDEO assetni shu tilga almashtiradi (pickLangVariant, pickSourceVariant ko'zgusi).
    source_variants'dan FARQI: bular til-bo'yicha TANLANADI (precedence emas), shuning uchun alohida
    maydon. lang — qisqa kod (ru/en/uz); aligned_to_source=True 1:1 swap kafolati."""

    lang: str  # qisqa kod: uz | ru | en | ...
    asset: AssetRef  # tarjima qilingan video (lip-sync)
    aligned_to_source: bool = True
    lip_sync: str = "precision"  # precision | speed | audio
    # Tarjima qilingan ekran-subtitrlari (oyna-darajada, vaqt asl span'da qayta taqsimlanadi). None →
    # STUDIO til almashganda asl tildagi subtitrlarni saqlaydi. Captions keyin (modulda) aniqlanadi.
    captions: Captions | None = None


class BackgroundLayer(BaseModel):
    """Matli subjekt orqasiga generatsiya fon/dekor (OUTPUT seconds)."""

    at_sec: float  # OUTPUT seconds
    dur: float
    bg: AssetRef
    matte: AssetRef | None = None
    matte_mode: str = "alpha"  # alpha | luma | chroma | segment
    fit: str = "cover"
    intent: str = ""


class EffectIntent(BaseModel):
    """Ssenariy-segmentiga bog'langan effekt hinti (montage_director chiqaradi). shot_index —
    storyboard ulanish kaliti; at_sec/dur ixtiyoriy (kompilyator markazlaydi)."""

    shot_index: int = 0
    at_sec: float | None = None  # OUTPUT seconds (None = shot bo'yicha)
    dur: float | None = None
    intent: str = ""  # b_roll | decor | vfx | zoom | eye_contact | cleanup | text_pop | transition | sfx
    strength: str = "med"  # low | med | high
    params: dict[str, Any] = Field(default_factory=dict)


class Cut(BaseModel):
    """A kept segment of the source clip. The output timeline is the ordered
    concatenation of these, so order matters."""

    src_start: float
    src_end: float
    beat_index: int = 0
    # The scriptwriter STORYBOARD shot this cut speaks over: scriptTimeline[].shotIndex
    # -> shotList[].i (1-indexed; 0 = unassigned). NOT a cut-enumeration index — it is the
    # link that keeps the storyboard (cam/frame/action/vfx) reachable after the clip is cut.
    # Populated by timing.assign_shot_index; consumed by the render lanes (motion/broll) later.
    shot_index: int = 0
    script_text: str = ""  # narration this cut speaks (from the matched scriptTimeline segment)
    align_confidence: float = 1.0


class WordTiming(BaseModel):
    word: str
    start: float  # SOURCE seconds
    end: float
    conf: float = 1.0


class Hook(BaseModel):
    hook_text: str = ""
    display_dur: float = 2.0  # OUTPUT seconds the static hook stays up
    cold_open_src: float | None = None  # SOURCE sec of an optional 0.3s cold open
    frame1_override_src_sec: float | None = None  # SOURCE sec if frame-1 is dark
    tighten_silence_to_0: bool = True


# --- timebase = OUTPUT seconds (post-cut timeline) -----------------------


class Beat(BaseModel):
    at_sec: float  # OUTPUT seconds
    dur: float
    owner: str = ""  # which aspect agent owns this beat
    intent: str = ""
    priority: int = 0


class Hold(BaseModel):
    at_sec: float
    dur: float
    reason: str = ""


class OpsPlan(BaseModel):
    change_budget_per_window: list[int] = Field(default_factory=list)
    beats: list[Beat] = Field(default_factory=list)
    holds: list[Hold] = Field(default_factory=list)


class Motion(BaseModel):
    op: str  # zoom_punch | kenburns | shake | glitch
    at_sec: float  # OUTPUT seconds
    dur: float
    from_scale: float = 1.0
    to_scale: float = 1.1
    easing: str = "ease-out"
    center: list[float] = Field(default_factory=lambda: [0.5, 0.5])


class Transition(BaseModel):
    at_sec: float  # OUTPUT seconds
    type: str  # from a closed allowlist enforced by the compiler
    easing: str = "ease-out"
    dur: float = 0.3


class Overlay(BaseModel):
    template: str
    at_sec: float  # OUTPUT seconds
    dur: float
    text: str = ""
    position: str = "center"
    color: str = "#FFFFFF"


class Broll(BaseModel):
    shot_index: int  # storyboard shot (shotList[].i) this B-roll illustrates — same namespace as Cut.shot_index
    source: str = "skip"  # stock | generate | skip
    provider: str = ""
    query: str | None = None
    prompt: str | None = None
    ref_frame_src_sec: float | None = None  # SOURCE sec to seed image-to-video
    asset_url: str | None = None
    dur_sec: float = 2.0
    est_cost_usd: float = 0.0
    ai_flag: bool = False
    # Faza 3 render anchor (OUTPUT seconds): where the B-roll covers the post-cut timeline.
    # `placement='overlay'` = full-frame cover during [at_sec, at_sec+output_dur_sec] (cut-away
    # LOOK, voice continues underneath) — does NOT change output_duration, so the two-timebase
    # offset table stays intact. 'segment' (true cut-away that extends the timeline) is reserved.
    at_sec: float | None = None  # OUTPUT seconds; None = not placed (no render)
    output_dur_sec: float | None = None  # OUTPUT seconds the B-roll stays on screen
    placement: str = "overlay"  # overlay | segment
    # v2 (additiv): tipli asset + overlay qatlam turi/aralashish (STUDIO V2+ klip uchun).
    asset: AssetRef | None = None
    layer_kind: str = "broll"  # broll | vfx_overlay
    blend: str = "normal"  # normal | multiply | screen | overlay | lighten | darken
    opacity: float = 1.0


# --- captions (OUTPUT seconds) -------------------------------------------


class CaptionWord(BaseModel):
    text: str
    start: float  # OUTPUT seconds
    end: float
    pop: bool = False  # premium per-word emphasis
    emoji: str | None = None


class CaptionWindow(BaseModel):
    words: list[CaptionWord] = Field(default_factory=list)


# Trend display faces bundled in the agents image (infra/docker/fonts, OFL). The caption
# stylist picks one per mood; anything outside this set degrades to Montserrat so libass
# never silently falls back to a system serif. Names must match the font family fontconfig sees.
CAPTION_FONTS: tuple[str, ...] = ("Montserrat", "Anton", "Bebas Neue", "Oswald")


class CaptionStyle(BaseModel):
    font: str = "Montserrat"  # punchy heavy Reels/CapCut face (bundled in the agents image); Noto Sans read flat
    size: int = 104  # big, bold, single-line — the Submagic look
    primary: str = "&H00FFFFFF"  # ASS BGR — white
    active: str = "&H0000D7FF"  # active-word accent — amber
    outline_color: str = "&H00000000"  # ASS BGR — black border
    outline: int = 7  # thick border so the bold text reads on any footage
    shadow: int = 3
    alignment: int = 2  # ASS numpad — bottom-center
    margin_v: int = 320  # keep inside the 80% safe-zone on 1920h
    margin_lr: int = 80


class Captions(BaseModel):
    play_res: list[int] = Field(default_factory=lambda: [1080, 1920])
    tier: str = "cheap"  # cheap | premium
    style: CaptionStyle = Field(default_factory=CaptionStyle)
    windows: list[CaptionWindow] = Field(default_factory=list)


# --- audio (OUTPUT seconds) ----------------------------------------------


class Loudnorm(BaseModel):
    i: float = -14.0  # integrated LUFS — IG/TikTok target
    tp: float = -1.0  # true peak dBTP
    lra: float = 11.0  # loudness range


class Duck(BaseModel):
    # music bed gain (0..1) under the voice; the sidechain ducks it FURTHER while the speaker
    # talks. The renderers (compiler.py + shotstack_map.py) read this instead of a hardcode, and
    # STUDIO (editor-edl.ts edlAudioSettings) reads it as its `duckLevel` so client + server match.
    volume: float = 0.12
    threshold: float = 0.02
    ratio: float = 12.0
    attack: float = 15.0  # ms — snappy duck the moment speech starts (matches the renderers)
    release: float = 250.0  # ms — music recovers quickly in the gaps


class Sfx(BaseModel):
    at_sec: float  # OUTPUT seconds
    type: str


class Audio(BaseModel):
    voice_chain: list[str] = Field(default_factory=list)
    duck: Duck = Field(default_factory=Duck)
    loudnorm: Loudnorm = Field(default_factory=Loudnorm)
    beat_grid: list[float] = Field(default_factory=list)  # OUTPUT seconds
    sfx: list[Sfx] = Field(default_factory=list)
    music_track_id: str | None = None
    music_license: str | None = None
    # Pre-resolved LOCAL music file (a generated fal.ai track or a chosen CC0 file).
    # When set, the compiler beds it instead of running pick_track over bundled assets.
    music_path: str | None = None


class QcIssue(BaseModel):
    rule: str
    severity: str = "warn"  # warn | error
    at_sec: float | None = None


class Qc(BaseModel):
    passed: bool = True
    issues: list[QcIssue] = Field(default_factory=list)
    action: str = "publish"  # publish | replan


class EDL(BaseModel):
    version: int = 1
    task_id: str
    tenant_id: str
    source: Source
    cuts: list[Cut] = Field(default_factory=list)
    wordmap: list[WordTiming] = Field(default_factory=list)
    hook: Hook = Field(default_factory=Hook)
    ops_plan: OpsPlan = Field(default_factory=OpsPlan)
    motion: list[Motion] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    overlays: list[Overlay] = Field(default_factory=list)
    broll: list[Broll] = Field(default_factory=list)
    captions: Captions = Field(default_factory=Captions)
    audio: Audio = Field(default_factory=Audio)
    qc: Qc = Field(default_factory=Qc)
    # v2 (additiv) qatlamlar — GPU-plane to'ldiradi (Faza B/C/D). Bo'sh bo'lsa montaj v1.
    source_variants: list[SourceVariant] = Field(default_factory=list)
    backgrounds: list[BackgroundLayer] = Field(default_factory=list)
    effect_intents: list[EffectIntent] = Field(default_factory=list)
    # Lokalizatsiya: HeyGen Video Translation 1:1 til-variantlari (lip-sync). Bo'sh → bir til (UZ).
    lang_variants: list[LangVariant] = Field(default_factory=list)
    # F6 vision: where the speaker's FACE predominantly sits (top/center/bottom) — text/card
    # layers go to the OPPOSITE zone so captions never cover the face. Plain str (not
    # Literal): a foreign value in a round-tripped manual EDL degrades to the default
    # layout instead of failing validation.
    face_zone: str | None = None

    # --- the two-timebase offset table (built from `cuts`) ----------------

    def output_duration(self) -> float:
        """Total OUTPUT seconds = sum of kept source segments."""
        return sum(max(0.0, c.src_end - c.src_start) for c in self.cuts)

    def source_to_output(self, src_sec: float) -> float | None:
        """Map a SOURCE second to its OUTPUT position. Returns None if the
        source second falls in a removed (cut-out) gap and has no output home."""
        acc = 0.0
        for c in self.cuts:
            seg = max(0.0, c.src_end - c.src_start)
            if c.src_start <= src_sec <= c.src_end:
                return acc + (src_sec - c.src_start)
            acc += seg
        return None

    def output_to_source(self, out_sec: float) -> float:
        """Map an OUTPUT second back to the SOURCE second it was cut from.
        Clamps to the timeline bounds rather than raising."""
        if out_sec <= 0:
            return self.cuts[0].src_start if self.cuts else 0.0
        acc = 0.0
        for c in self.cuts:
            seg = max(0.0, c.src_end - c.src_start)
            if out_sec <= acc + seg:
                return c.src_start + (out_sec - acc)
            acc += seg
        return self.cuts[-1].src_end if self.cuts else 0.0

    def validate_output_atsec(self, at_sec: float) -> bool:
        """A 1e-3 tolerance guards float accumulation across many cuts."""
        return -1e-3 <= at_sec <= self.output_duration() + 1e-3


# LangVariant.captions Captions'ga oldinga-havola (u quyiroqda aniqlangan) — endi resolve qilamiz.
LangVariant.model_rebuild()

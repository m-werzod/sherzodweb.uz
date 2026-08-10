"""EDL kontrakt parity qulfi — EDL uchta qo'lda-ko'zgu shaklning simi (wire):

  * pydantic  app/montage/edl.py                       (HAQIQAT MANBAI — bu test)
  * zod       packages/shared-types/src/montage.ts     (web validator)
  * STUDIO    studio/src/store/editor-edl.ts           (brauzer iste'molchi: SmmEdl + clipsFromEdl)

Ular orasida codegen yo'q, shuning uchun bu yerga qo'shilgan, ammo ko'zgularga qo'shilmagan maydon
sim bo'ylab jim tushib qoladi. Bu test pydantic maydon-to'plamlarini aniq ro'yxatga qarshi qulflaydi:
u yiqilsa — edl.py ko'zgularini (montage.ts + STUDIO) O'SHA o'zgarishda yangilang, keyin bu yerdagi
kutilgan ro'yxatni yangilang. (Juftligi: apps/web/src/lib/production/edl-contract.test.ts.)
"""
from __future__ import annotations

from app.montage.edl import EDL, Broll, CaptionWord, Cut, Overlay, Source


def _fields(model: type) -> set[str]:
    return set(model.model_fields)  # type: ignore[attr-defined]


def test_edl_root_fields_are_locked() -> None:
    assert _fields(EDL) == {
        # v1
        "version",
        "task_id",
        "tenant_id",
        "source",
        "cuts",
        "wordmap",
        "hook",
        "ops_plan",
        "motion",
        "transitions",
        "overlays",
        "broll",
        "captions",
        "audio",
        "qc",
        # v2 (additiv) — Faza A2
        "source_variants",
        "backgrounds",
        "effect_intents",
        # lokalizatsiya (additiv) — HeyGen Video Translation
        "lang_variants",
        # F6 vision (additiv): yuz zonasi — matn/karta qatlamlari yuzdan qochadi.
        # STUDIO uni bilmasa ham buzilmaydi (optional, default None, round-trip str).
        "face_zone",
    }


def test_v2_layers_are_additive_and_default_empty() -> None:
    # Bo'sh EDL hali ham v1: yangi qatlamlar bo'sh ro'yxat, version 1.
    e = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))
    assert e.version == 1
    assert e.source_variants == []
    assert e.backgrounds == []
    assert e.effect_intents == []
    assert e.lang_variants == []


def test_edl_version_defaults_to_1() -> None:
    e = EDL(task_id="t", tenant_id="x", source=Source(upload_key="k"))
    assert e.version == 1


# --- STUDIO clipsFromEdl aynan o'qiydigan subset (editor-edl.ts bilan sinxron tut) -----------


def test_source_exposes_studio_consumed_fields() -> None:
    # editor-edl.ts SmmEdl.source: { w, h, duration_sec, fps }
    assert {"w", "h", "duration_sec", "fps"} <= _fields(Source)


def test_cut_exposes_studio_consumed_fields() -> None:
    # editor-edl.ts SmmEdlCut: { src_start, src_end }; shot_index — storyboard ulanish kaliti (v2).
    assert {"src_start", "src_end", "shot_index"} <= _fields(Cut)


def test_caption_word_exposes_studio_consumed_fields() -> None:
    # editor-edl.ts SmmEdlWord: { text, start, end }
    assert {"text", "start", "end"} <= _fields(CaptionWord)


def test_overlay_exposes_studio_consumed_fields() -> None:
    # editor-edl.ts overlays: { at_sec, dur, text }
    assert {"at_sec", "dur", "text"} <= _fields(Overlay)


def test_broll_shape_is_locked() -> None:
    # broll — eng katta kutilayotgan mahsulot teshigi (STUDIO uni hali import qilmaydi — Faza B).
    # Shaklini hozir qulflaymiz: STUDIO iste'mol qila boshlaganda sim barqaror bo'lsin.
    assert {
        "shot_index",
        "source",
        "asset_url",
        "at_sec",
        "output_dur_sec",
        "placement",
    } <= _fields(Broll)


def test_duck_defaults_lock() -> None:
    # STUDIO editor-edl.ts edlAudioSettings duck.volume ni duckLevel sifatida o'qiydi; montage.ts
    # ko'zgusi + shu raqamlar rozi bo'lishi shart. Bir-tomonli drift (montage.ts'da attack/release
    # 30/400 edi) shu qulf bilan tutiladi. Renderer'lar (compiler/shotstack) duck.volume'ni o'qiydi.
    from app.montage.edl import Duck

    d = Duck()
    assert d.volume == 0.12
    assert d.threshold == 0.02
    assert d.ratio == 12.0
    assert d.attack == 15.0
    assert d.release == 250.0

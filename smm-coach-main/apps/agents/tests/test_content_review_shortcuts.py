"""Unit tests for the content_review workflow short-circuit fixes.

These verify that:
1. initial_analysis skips when workflow == content_review
2. scriptwriter enriches tasks with script_timeline + ai_coach_note
3. roadmap_persister routes content_review to _update_single_task
"""
from __future__ import annotations

import pytest

from app.graphs.nodes import initial_analysis, scriptwriter

# ── initial_analysis ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initial_analysis_skips_for_content_review() -> None:
    state = {
        "tenant_id": "t1",
        "workflow": "content_review",
        "run_id": "r1",
    }
    result = await initial_analysis.run(state)  # type: ignore[arg-type]
    assert result == {}


# ── scriptwriter enrichment ────────────────────────────────────────────────


class TestEnrichTask:
    def test_enrich_task_generates_timeline_from_markdown(self) -> None:
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Hook text",
            "script_md": (
                "**Hook (0-3s):** Birinchi qator\n\n"
                "**Body (3-25s):** Ikkinchi qator\n\n"
                "**CTA (25-30s):** Uchinchi qator"
            ),
            "shot_list": [
                {"i": 1, "cam": "Front", "frame": "Close", "sec": 3, "action": "Hook"},
                {"i": 2, "cam": "Front", "frame": "Medium", "sec": 22, "action": "Body"},
                {"i": 3, "cam": "Front", "frame": "Wide", "sec": 5, "action": "CTA"},
            ],
        }
        scriptwriter._enrich_task(task)

        timeline = task["script_timeline"]
        assert len(timeline) == 3
        assert timeline[0]["t"] == "0-3s"
        assert timeline[0]["text"] == "Birinchi qator"
        assert timeline[0]["cue"] == "Kamera yo'naltirish"
        assert timeline[1]["t"] == "3-25s"
        assert timeline[1]["cue"] == "Voice-over"
        assert timeline[2]["t"] == "25-30s"
        assert timeline[2]["cue"] == "Call to action"

    def test_enrich_task_generates_timeline_without_time_labels(self) -> None:
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Hook",
            "script_md": "**Hook:** Birinchi qator\n\n**Body:** Ikkinchi qator",
            "shot_list": [{"i": 1, "sec": 15}, {"i": 2, "sec": 15}],
        }
        scriptwriter._enrich_task(task)

        timeline = task["script_timeline"]
        assert len(timeline) == 2
        assert "s" in timeline[0]["t"]  # e.g. "0-15s"
        assert timeline[0]["text"] == "Birinchi qator"

    def test_enrich_task_fallback_for_plain_text(self) -> None:
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Hook",
            "script_md": "Bu oddiy matn. Hech qanday belgi yo'q.",
            "shot_list": [],
        }
        scriptwriter._enrich_task(task)

        timeline = task["script_timeline"]
        assert len(timeline) == 1
        assert timeline[0]["text"] == "Bu oddiy matn. Hech qanday belgi yo'q."
        assert timeline[0]["cue"] == "Voice-over"

    def test_enrich_task_backfills_qualitative_band_when_no_exemplar(self) -> None:
        # No exemplar post → the writer must NOT hallucinate specific numbers; it
        # back-fills the honest {impactBand, note, _source} qualitative shape so
        # the UI renders "Kichik o'sish · taxminiy", not "267 obunachi".
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Hook",
            "script_md": "Text",
            "shot_list": [],
            "follower_target": 1000,
        }
        scriptwriter._enrich_task(task)

        pred = task["predict_evidence"]
        assert pred["impactBand"] == "medium"
        assert pred["note"]  # honest "no real numbers yet" note present
        assert pred["_source"] == "writer_no_data"
        assert pred["variantA"] == "A"
        # The hallucinated numeric keys must be stripped, not invented.
        assert "reachLow" not in pred
        assert "predictedFollowers" not in pred

    def test_enrich_task_strips_ungrounded_numbers_keeps_variant(self) -> None:
        # An LLM dict carrying ungrounded numbers (no exemplar) → numbers stripped,
        # qualitative band back-filled, but a caller-set variant is preserved.
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Hook",
            "script_md": "Text",
            "shot_list": [],
            "predict_evidence": {"reachMid": 9999, "variantA": "B"},
        }
        scriptwriter._enrich_task(task)

        pred = task["predict_evidence"]
        assert "reachMid" not in pred       # ungrounded number stripped
        assert pred["variantA"] == "B"      # caller's variant preserved
        assert pred["impactBand"]           # qualitative band back-filled

    def test_enrich_task_preserves_exemplar_grounded_numbers(self) -> None:
        # WITH a real exemplar post, the writer keeps the grounded numbers (this
        # is the only path where specific reach is honest).
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Hook",
            "script_md": "Text",
            "shot_list": [],
            "predict_evidence": {
                "exemplarSource": "@real_account",
                "exemplarReach": 5000,
                "reachMid": 9999,
                "variantA": "B",
            },
        }
        scriptwriter._enrich_task(task)

        pred = task["predict_evidence"]
        assert pred["reachMid"] == 9999       # preserved — exemplar-grounded
        assert pred["exemplarReach"] == 5000  # preserved
        assert pred["variantA"] == "B"

    def test_enrich_task_generates_ai_coach_note(self) -> None:
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Ajoyib hook",
            "script_md": "Text",
            "shot_list": [],
        }
        scriptwriter._enrich_task(task)

        note = task["ai_coach_note"]
        assert "reel" in note
        assert "Ajoyib hook" in note
        assert len(note) > 20

    def test_enrich_task_sets_format_and_publish_window(self) -> None:
        task = {
            "title": "Test",
            "type": "carousel",
            "hook": "Hook",
            "script_md": "Text",
            "shot_list": [],
        }
        scriptwriter._enrich_task(task)

        assert task["format"] == "Karusel · 1:1 · 5 slayd"
        assert task["publish_window"] == "Hafta · ish vaqti"

    def test_enrich_task_sets_hook_meta(self) -> None:
        task = {
            "title": "Test",
            "type": "reel",
            "hook": "Hook",
            "script_md": "Text",
            "shot_list": [],
        }
        scriptwriter._enrich_task(task)

        meta = task["hook_meta"]
        assert meta["cameraDirection"] == "Kamera yo'naltirilgan"
        assert meta["energy"] == 7
        assert meta["retention"] == 0.65
        assert meta["abVariant"] == "A"

    def test_enrich_action_task_clears_shots_and_sets_checklist(self) -> None:
        task = {
            "title": "Profilni sozlash",
            "type": "action",
            "hook": "Bio'ngizni yangilang",
            "script_md": "1. Bio'ni oching\n2. Nishni yozing\n3. Rasmini yangilang",
            "shot_list": [{"i": 1, "cam": "Front"}],
            "hashtags": ["#test"],
        }
        scriptwriter._enrich_task(task)

        assert task["type"] == "action"
        assert task["shot_list"] == []
        assert task["hashtags"] == []
        assert task["format"] == "Amaliyot · topshiriq"
        assert task["audio_suggestion"] is None
        # script_timeline should be parsed as checklist
        timeline = task["script_timeline"]
        assert len(timeline) == 3
        assert timeline[0]["text"] == "Bio'ni oching"
        assert timeline[0]["cue"] == "Bajarish"
        # predict_evidence should be zeroed with text critique
        pred = task["predict_evidence"]
        assert pred["reachMid"] == 0
        assert "llmCritique" in pred


# ── roadmap_persister routing ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_roadmap_persister_routes_content_review_to_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that when workflow == content_review, persister calls
    _update_single_task instead of the full roadmap upsert."""
    from app.graphs.nodes import roadmap_persister

    update_called = False

    async def fake_update_single_task(state: dict, approved: list) -> dict:
        nonlocal update_called
        update_called = True
        return {"updated": True}

    monkeypatch.setattr(
        roadmap_persister, "_update_single_task", fake_update_single_task
    )

    state = {
        "tenant_id": "t1",
        "workflow": "content_review",
        "run_id": "r1",
        "approved_tasks": [{"title": "T"}],
    }
    result = await roadmap_persister.run(state)  # type: ignore[arg-type]

    assert update_called is True
    assert result == {"updated": True}


@pytest.mark.asyncio
async def test_roadmap_persister_runs_full_roadmap_for_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that roadmap_generation still runs the full persist path."""
    from app.graphs.nodes import roadmap_persister

    update_called = False

    async def fake_update_single_task(state: dict, approved: list) -> dict:
        nonlocal update_called
        update_called = True
        return {}

    monkeypatch.setattr(
        roadmap_persister, "_update_single_task", fake_update_single_task
    )

    # Monkey-patch the full persist internals so we don't need a real DB
    monkeypatch.setattr(
        roadmap_persister, "_insert_task", lambda *a, **k: None
    )

    state = {
        "tenant_id": "t1",
        "workflow": "roadmap_generation",
        "run_id": "r1",
        "approved_tasks": [],
    }
    result = await roadmap_persister.run(state)  # type: ignore[arg-type]

    assert update_called is False
    assert result == {}

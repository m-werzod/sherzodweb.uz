from __future__ import annotations

import asyncio

import app.graphs.nodes.competitor_intel as ci


def _state(**kw):
    base = {
        "tenant_id": "t",
        "user_id": "u",
        "run_id": "r",
        "workflow": "roadmap_generation",
        "north_star": {"niche": "fitness", "region": "uz"},
        "analysis_summary": "BAZA TAHLIL.",
    }
    base.update(kw)
    return base


# ---- pure _fold ----

def test_fold_empty_returns_existing():
    assert ci._fold("X", {}, [], []) == "X"


def test_fold_adds_block_with_intel():
    out = ci._fold("BAZA", {"competitor_angles": ["A1"], "content_gaps": ["G1"]}, [], [])
    assert "RAQOBATCHI VA TREND TAHLILI" in out
    assert "A1" in out and "G1" in out
    assert out.startswith("BAZA")


def test_fold_falls_back_to_raw_signals_for_format_audio():
    signals = [{"kind": "format", "label": "POV"}, {"kind": "audio", "label": "TrendSong"}]
    out = ci._fold("", {}, signals, [])
    assert "POV" in out and "TrendSong" in out


def test_fold_lists_competitors():
    out = ci._fold("", {"content_gaps": ["g"]}, [], [{"handle": "rival1"}])
    assert "@rival1" in out


# ---- run() ----

def _patch(monkeypatch, *, signals=None, snaps=None, news=None, comps=None, intel=None, raise_llm=False, discovered=None):
    async def _sig(**k):
        return signals or []

    async def _discover(_niche, _region):
        return discovered or []

    async def _snap(**k):
        return snaps or []

    async def _news(**k):
        return news or []

    async def _comp(_tid):
        return comps or []

    async def _emit(**k):
        return None

    async def _chat(**k):
        if raise_llm:
            raise RuntimeError("llm down")
        return intel or {}

    monkeypatch.setattr(ci, "top_signals_for_region", _sig)
    monkeypatch.setattr(ci, "competitor_snapshots", _snap)
    monkeypatch.setattr(ci, "recent_niche_news", _news)
    monkeypatch.setattr(ci, "_load_competitors", _comp)
    async def _vault(*_a, **_k):
        return ""

    monkeypatch.setattr(ci, "_discover_competitors_web", _discover)
    monkeypatch.setattr(ci, "load_vault_context", _vault)
    monkeypatch.setattr(ci, "emit_message", _emit)
    monkeypatch.setattr(ci.groq_client, "chat_json", _chat)


def test_run_skips_content_review():
    assert asyncio.run(ci.run(_state(workflow="content_review"))) == {}


def test_run_empty_sources_returns_empty(monkeypatch):
    _patch(monkeypatch)
    assert asyncio.run(ci.run(_state())) == {}


def test_run_populates_intel_and_appends_analysis(monkeypatch):
    _patch(
        monkeypatch,
        signals=[{"kind": "format", "label": "POV"}],
        intel={"competitor_angles": ["transformatsiya hikoyasi"]},
    )
    out = asyncio.run(ci.run(_state()))
    assert out["competitor_intel"] == {"competitor_angles": ["transformatsiya hikoyasi"]}
    assert "RAQOBATCHI VA TREND TAHLILI" in out["analysis_summary"]
    # appended to initial_analysis's output, not replaced
    assert out["analysis_summary"].startswith("BAZA TAHLIL.")


def test_run_llm_failure_still_folds_raw_signals(monkeypatch):
    _patch(monkeypatch, signals=[{"kind": "audio", "label": "TrendSong"}], raise_llm=True)
    out = asyncio.run(ci.run(_state()))
    assert out["competitor_intel"] == {}
    assert "TrendSong" in out["analysis_summary"]


def test_extract_handles_basic():
    results = [
        {"title": "Top fitness blogger @fit_uz on Instagram", "snippet": "", "url": ""},
        {"title": "", "snippet": "follow", "url": "https://instagram.com/sportzona"},
    ]
    handles = ci._extract_handles(results)
    assert "fit_uz" in handles
    assert "sportzona" in handles


def test_extract_handles_filters_stopwords_and_dedups():
    results = [
        {"title": "instagram.com/explore and @reels", "snippet": "@fit_uz @fit_uz", "url": ""},
    ]
    handles = ci._extract_handles(results)
    assert "explore" not in handles
    assert "reels" not in handles
    assert handles.count("fit_uz") == 1


def test_extract_handles_rejects_dot_only_and_caps():
    results = [{"title": "@... @a_b", "snippet": "", "url": ""}]
    handles = ci._extract_handles(results, limit=1)
    assert handles == ["a_b"]


def test_run_folds_web_discovered_competitors(monkeypatch):
    _patch(monkeypatch, discovered=[{"handle": "fit_uz", "discovered": True}])
    out = asyncio.run(ci.run(_state()))
    assert "@fit_uz" in out["analysis_summary"]
    assert "web-discovered" in out["notes"][0]

from __future__ import annotations

from app.api import psych_interview as pi


def test_router_exposes_both_endpoints():
    paths = {r.path for r in pi.router.routes}
    assert "/psych-interview" in paths
    assert "/psych-extract" in paths


def test_request_models_have_defaults():
    req = pi.PsychInterviewRequest(tenantId="t")
    assert req.history == []
    assert req.coveredDims == []
    assert req.niche is None
    ext = pi.PsychExtractRequest(tenantId="t")
    assert ext.history == []


def test_max_questions_is_capped():
    assert 8 <= pi._MAX_QUESTIONS <= 16


def test_prompts_are_substantive():
    # Orchestrator must name the 10 dimensions and the JSON contract.
    assert "D10" in pi.ORCH_PROMPT and "done" in pi.ORCH_PROMPT
    # Extractor must carry the strict OCEAN/archetype honesty rules + template.
    assert "OCEAN" in pi.EXTRACT_PROMPT
    assert "archetypeConfidence" in pi.EXTRACT_PROMPT
    assert "contentPillars" in pi.EXTRACT_PROMPT


def test_validate_profile_clamps_and_caps():
    raw = {
        "ocean": {"O": 140, "C": -5, "E": "70", "A": 50, "N": 50, "confidence": "high"},
        "voice": {"label": "Iliq Murabbiy", "archetypeConfidence": "diagnosed"},
        "contentPillars": ["x"],
    }
    out = pi._validate_profile(raw)
    assert out is not None
    assert out["ocean"]["O"] == 100 and out["ocean"]["C"] == 0 and out["ocean"]["E"] == 70
    assert out["ocean"]["confidence"] == "medium"  # 'high' capped
    assert out["voice"]["archetypeConfidence"] == "suggested"  # never 'diagnosed'


def test_validate_profile_rejects_hollow_or_invalid():
    # Empty / non-dict / template-shell-with-no-substance → None (don't persist a profileless shell).
    assert pi._validate_profile(None) is None
    assert pi._validate_profile({}) is None
    assert pi._validate_profile({"ocean": {"O": 50}, "voice": {"label": ""}, "contentPillars": []}) is None


def test_validate_profile_keeps_substantive_with_origin_only():
    out = pi._validate_profile({"originStory": {"catalyst": "5 yil dasturchi bo'ldim"}})
    assert out is not None

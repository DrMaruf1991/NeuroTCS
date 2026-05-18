"""Tests for neurotcs.silent_deployment — Kwong 2022 silent-trial methodology."""

import pytest

from neurotcs.silent_deployment import (
    DECIDE_AI_CITATION,
    DECIDE_AI_DOI,
    DECIDE_AI_PMID,
    KWONG_2022_CITATION,
    KWONG_2022_DOI,
    KWONG_2022_PMID,
    SilentDeploymentEvidence,
    SilentTrialTheme,
    SilentTrialThemeFinding,
    make_silent_deployment_evidence,
)
from neurotcs.silent_deployment import KWONG_2022_THEME_QUESTIONS


# -----------------------------------------------------------------------------
# Citation locks
# -----------------------------------------------------------------------------

def test_kwong_2022_citation_locked():
    assert KWONG_2022_DOI == "10.3389/fdgth.2022.929508"
    assert KWONG_2022_PMID == "36052317"
    assert "Kwong JCC" in KWONG_2022_CITATION
    assert "Front Digit Health 2022;4:929508" in KWONG_2022_CITATION


def test_decide_ai_citation_locked():
    """DECIDE-AI is a separate primary source from Kwong 2022. The memory
    drift caught during framework verification was confusing the two."""
    assert DECIDE_AI_DOI == "10.1038/s41591-022-01772-9"
    assert DECIDE_AI_PMID == "35585196"
    assert "Vasey B" in DECIDE_AI_CITATION
    assert "Nat Med 2022;28(5):924-933" in DECIDE_AI_CITATION
    assert "DECIDE-AI" in DECIDE_AI_CITATION


def test_decide_ai_no_stage_labels():
    """DECIDE-AI does NOT have Stage A/B/C labels. This test documents the
    memory-drift correction caught during framework verification."""
    # The SilentTrialTheme enum belongs to Kwong 2022's silent-trial themes,
    # NOT to DECIDE-AI. There must be no "STAGE_A", "STAGE_B", "STAGE_C" in it.
    theme_names = {t.name for t in SilentTrialTheme}
    assert theme_names == {
        "DATASET_DRIFT",
        "BIAS",
        "FEASIBILITY",
        "STAKEHOLDER_ATTITUDES",
    }


# -----------------------------------------------------------------------------
# Kwong 2022 Table 1 themes (verified verbatim quotes under CC-BY)
# -----------------------------------------------------------------------------

def test_all_four_themes_have_questions():
    """All four Kwong 2022 themes must have at least one verbatim key question."""
    for theme in SilentTrialTheme:
        assert theme in KWONG_2022_THEME_QUESTIONS
        assert len(KWONG_2022_THEME_QUESTIONS[theme]) >= 1


def test_dataset_drift_questions_present():
    """Verify a specific Kwong 2022 Table 1 question is present verbatim."""
    questions = KWONG_2022_THEME_QUESTIONS[SilentTrialTheme.DATASET_DRIFT]
    # First question in the Dataset Drift theme (Kwong 2022 Table 1 verbatim)
    assert any(
        "how data are defined and collected" in q for q in questions
    ), "Kwong 2022 Table 1 dataset-drift Q1 not present"


def test_feasibility_questions_include_time_to_input():
    """The 'how much time' feasibility question is a key Kwong 2022 quote."""
    questions = KWONG_2022_THEME_QUESTIONS[SilentTrialTheme.FEASIBILITY]
    assert any(
        "How much time does it take for the end-user" in q for q in questions
    )


# -----------------------------------------------------------------------------
# Evidence record
# -----------------------------------------------------------------------------

def test_make_silent_deployment_evidence():
    ev = make_silent_deployment_evidence(
        model_name="adni_cnn_v3",
        model_hash="abc123",
        rulepack_id="ad/aa_2024",
        rulepack_version="1.2.0",
        audit_id="audit_001",
        silent_trial_start="2026-06-01",
        silent_trial_end="2026-09-01",
        n_patients=120,
        n_transitions=500,
        n_flagged=3,
    )
    assert isinstance(ev, SilentDeploymentEvidence)
    assert ev.model_name == "adni_cnn_v3"
    assert ev.kwong_2022_pmid == KWONG_2022_PMID
    assert ev.decide_ai_pmid == DECIDE_AI_PMID
    # Without findings, themes_covered is empty and is_complete is False
    assert ev.themes_covered() == set()
    assert not ev.is_complete()


def test_evidence_is_complete_when_all_four_themes_covered():
    findings = [
        SilentTrialThemeFinding(
            theme=t,
            question="placeholder",
            finding="placeholder",
            severity="info",
        )
        for t in SilentTrialTheme
    ]
    ev = make_silent_deployment_evidence(
        model_name="adni_cnn_v3",
        model_hash="abc123",
        rulepack_id="ad/aa_2024",
        rulepack_version="1.2.0",
        audit_id="audit_001",
        silent_trial_start="2026-06-01",
        silent_trial_end="2026-09-01",
        n_patients=120,
        n_transitions=500,
        n_flagged=3,
        findings=findings,
    )
    assert ev.is_complete()
    assert ev.themes_covered() == set(SilentTrialTheme)


def test_evidence_record_is_immutable():
    ev = make_silent_deployment_evidence(
        model_name="x",
        model_hash="x",
        rulepack_id="x",
        rulepack_version="x",
        audit_id="x",
        silent_trial_start="2026-01-01",
        silent_trial_end="2026-01-02",
        n_patients=1,
        n_transitions=1,
        n_flagged=0,
    )
    with pytest.raises((AttributeError, TypeError)):
        ev.n_flagged = 999  # type: ignore[misc]

"""Tests for neurotcs.fairness — FUTURE-AI Fairness + Robustness panels."""

import numpy as np
import pytest

from neurotcs.fairness import (
    FUTURE_AI_CITATION,
    FUTURE_AI_DOI,
    FUTURE_AI_FAIRNESS_ATTRIBUTES,
    FUTURE_AI_PMID,
    FUTURE_AI_ROBUSTNESS_ATTRIBUTES,
    FairnessAuditResult,
    RobustnessAuditResult,
    fairness_audit,
    robustness_audit,
)


# -----------------------------------------------------------------------------
# Citation lock
# -----------------------------------------------------------------------------

def test_future_ai_citation_locked():
    assert FUTURE_AI_DOI == "10.1136/bmj-2024-081554"
    assert FUTURE_AI_PMID == "39909534"
    assert "Lekadir K" in FUTURE_AI_CITATION
    assert "BMJ 2025;388:e081554" in FUTURE_AI_CITATION


def test_fairness_attributes_are_locked():
    """The canonical FUTURE-AI fairness stratification variables must be
    fixed and locked — the v1.7 spec depends on this exact set."""
    assert "sex" in FUTURE_AI_FAIRNESS_ATTRIBUTES
    assert "age_band" in FUTURE_AI_FAIRNESS_ATTRIBUTES
    assert "race_ethnicity" in FUTURE_AI_FAIRNESS_ATTRIBUTES
    assert "comorbidity" in FUTURE_AI_FAIRNESS_ATTRIBUTES
    assert "disease_stage" in FUTURE_AI_FAIRNESS_ATTRIBUTES
    assert "treatment_status" in FUTURE_AI_FAIRNESS_ATTRIBUTES


def test_robustness_attributes_are_locked():
    """The canonical FUTURE-AI robustness stratification variables must be
    distinct from fairness variables — this separation was a key memory-drift
    correction caught during framework verification."""
    assert "scanner_vendor" in FUTURE_AI_ROBUSTNESS_ATTRIBUTES
    assert "field_strength" in FUTURE_AI_ROBUSTNESS_ATTRIBUTES
    assert "acquisition_site" in FUTURE_AI_ROBUSTNESS_ATTRIBUTES
    # Robustness and fairness attributes MUST be disjoint
    assert set(FUTURE_AI_FAIRNESS_ATTRIBUTES).isdisjoint(
        set(FUTURE_AI_ROBUSTNESS_ATTRIBUTES)
    ), (
        "Fairness and Robustness panels must use disjoint attribute sets per "
        "FUTURE-AI BMJ 2025 (scanner vendor etc. are Robustness, not Fairness)"
    )


# -----------------------------------------------------------------------------
# Fairness audit panel B.4.4
# -----------------------------------------------------------------------------

def test_fairness_audit_basic_two_groups():
    flags = np.array([False, False, True, False, True, True])
    demo = {"sex": np.array(["M", "M", "F", "F", "F", "M"])}
    result = fairness_audit(flags, demo)
    assert isinstance(result, FairnessAuditResult)
    assert result.panel_id == "B.4.4_fairness"
    assert result.framework_doi == FUTURE_AI_DOI
    # Two unique sex values, so 2 strata
    sex_strata = [s for s in result.strata if s.stratum_name == "sex"]
    assert len(sex_strata) == 2


def test_fairness_audit_detects_disparity():
    """If one stratum has 100% flag rate and another 0%, max disparity must
    be exactly 0.5 (each is 0.5 away from the overall mean of 0.5)."""
    flags = np.array([True, True, True, False, False, False])
    demo = {"sex": np.array(["M", "M", "M", "F", "F", "F"])}
    result = fairness_audit(flags, demo)
    assert result.overall_flag_rate == 0.5
    assert abs(result.max_disparity - 0.5) < 1e-9


def test_fairness_audit_ignores_unknown_attributes():
    """If an attribute name is not in the FUTURE-AI canonical list, it should
    be silently skipped."""
    flags = np.array([False, True, False, True])
    demo = {"sex": np.array(["M", "F", "M", "F"]),
            "not_a_fairness_var": np.array(["a", "b", "a", "b"])}
    result = fairness_audit(flags, demo)
    stratum_names = {s.stratum_name for s in result.strata}
    assert "sex" in stratum_names
    assert "not_a_fairness_var" not in stratum_names


def test_fairness_audit_attribute_length_mismatch_raises():
    flags = np.array([False, True, False, True])
    demo = {"sex": np.array(["M", "F"])}  # wrong length
    with pytest.raises(ValueError, match="length"):
        fairness_audit(flags, demo)


def test_fairness_audit_empty_flags_yields_empty_result():
    result = fairness_audit(np.array([], dtype=bool), {})
    assert len(result.strata) == 0
    assert result.overall_flag_rate == 0.0


# -----------------------------------------------------------------------------
# Robustness audit panel B.4.5
# -----------------------------------------------------------------------------

def test_robustness_audit_basic():
    flags = np.array([False, True, False, True, False, True])
    tech = {"scanner_vendor": np.array(["GE", "GE", "Siemens", "Siemens",
                                         "Philips", "Philips"])}
    result = robustness_audit(flags, tech)
    assert isinstance(result, RobustnessAuditResult)
    assert result.panel_id == "B.4.5_robustness"
    assert result.framework_doi == FUTURE_AI_DOI
    vendor_strata = [s for s in result.strata if s.stratum_name == "scanner_vendor"]
    assert len(vendor_strata) == 3


def test_robustness_audit_separate_from_fairness():
    """A demographic-only attribute set should yield NO robustness strata."""
    flags = np.array([False, True, False, True])
    demo_only = {"sex": np.array(["M", "F", "M", "F"])}
    result = robustness_audit(flags, demo_only)
    assert len(result.strata) == 0


def test_fairness_audit_does_not_pick_up_scanner_vendor():
    """Scanner vendor must NOT be picked up by the fairness panel, even if
    passed in. This is the key separation between B.4.4 and B.4.5."""
    flags = np.array([False, True, False, True])
    mixed = {"scanner_vendor": np.array(["GE", "GE", "Siemens", "Siemens"])}
    result = fairness_audit(flags, mixed)
    assert len(result.strata) == 0, (
        "scanner_vendor must NOT appear in fairness panel (it belongs to "
        "Robustness per FUTURE-AI BMJ 2025)"
    )

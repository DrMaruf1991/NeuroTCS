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


# ============================================================
# v1.7.10 (AD-lock Step 2.2): cohort_fairness_audit helper
# ============================================================

def _three_demographic_trajectories():
    """Build three trajectories with distinct demographic metadata for
    end-to-end testing of cohort_fairness_audit."""
    from datetime import date

    from neurotcs import Trajectory
    return [
        Trajectory(
            patient_id="P1",
            states=("CN", "MCI", "AD-dementia"),
            dates=(date(2024, 1, 1), date(2024, 7, 1), date(2025, 1, 1)),
            metadata={"sex": "F", "age_band": "60-69"},
        ),
        Trajectory(
            patient_id="P2",
            states=("CN", "AD-dementia"),  # inadmissible: skips MCI
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "M", "age_band": "70-79"},
        ),
        Trajectory(
            patient_id="P3",
            states=("MCI", "MCI"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "F", "age_band": "70-79"},
        ),
    ]


def test_cohort_fairness_audit_basic():
    """cohort_fairness_audit must stratify cohort flag rate by sex and age_band
    after audit() is called with return_per_transition=True.

    Empirically verified flag pattern under ad/niaaa_2018:
      - P1 (F): CN -> MCI (admissible) and MCI -> AD-dementia at dt=184d
        FLAGGED (transition is too rapid under niaaa_2018 minimum delta_t).
      - P2 (M): CN -> AD-dementia direct skip FLAGGED (skips MCI stage).
      - P3 (F): MCI -> MCI self-loop (admissible).
    Total: 4 transitions, 2 flagged, overall_flag_rate = 0.5.
    """
    from neurotcs import audit, load_rulepack
    from neurotcs.fairness import cohort_fairness_audit

    pack = load_rulepack("ad/niaaa_2018")
    trajs = _three_demographic_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42,
                    return_per_transition=True)

    fairness = cohort_fairness_audit(result)
    assert fairness.panel_id == "B.4.4_fairness"
    assert result.n_transitions == 4
    assert result.n_flagged == 2
    assert fairness.overall_flag_rate == 0.5

    # Sex strata: P1 (F) contributes 2 transitions (1 flagged),
    # P2 (M) contributes 1 transition (1 flagged), P3 (F) contributes 1
    # transition (0 flagged). So F has n=3, n_flagged=1; M has n=1, n_flagged=1.
    sex_strata = {s.stratum_value: s for s in fairness.strata
                   if s.stratum_name == "sex"}
    assert sex_strata["F"].n == 3
    assert sex_strata["M"].n == 1
    assert sex_strata["F"].n_flagged == 1
    assert sex_strata["M"].n_flagged == 1
    # F flag rate = 1/3 ≈ 0.333; M flag rate = 1/1 = 1.0
    assert abs(sex_strata["F"].flag_rate - 1/3) < 1e-9
    assert sex_strata["M"].flag_rate == 1.0


def test_cohort_fairness_audit_raises_when_per_transition_missing():
    """cohort_fairness_audit must raise a clear error if per_transition
    is None (i.e. caller forgot return_per_transition=True)."""
    from neurotcs import audit, load_rulepack
    from neurotcs.fairness import cohort_fairness_audit
    import pytest

    pack = load_rulepack("ad/niaaa_2018")
    trajs = _three_demographic_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42)
    # Note: no return_per_transition=True

    with pytest.raises(ValueError, match="return_per_transition=True"):
        cohort_fairness_audit(result)


def test_cohort_fairness_audit_handles_missing_attribute():
    """If some trajectories lack a requested attribute, those transitions
    are bucketed into the 'unknown' stratum rather than crashing."""
    from datetime import date

    from neurotcs import Trajectory, audit, load_rulepack
    from neurotcs.fairness import cohort_fairness_audit

    pack = load_rulepack("ad/niaaa_2018")
    trajs = [
        Trajectory(
            patient_id="P1",
            states=("CN", "MCI"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "F"},  # no age_band
        ),
        Trajectory(
            patient_id="P2",
            states=("CN", "MCI"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "M", "age_band": "70-79"},
        ),
    ]
    result = audit(trajs, pack, bootstrap_B=100, seed=42,
                    return_per_transition=True)
    fairness = cohort_fairness_audit(result)
    age_strata = {s.stratum_value for s in fairness.strata
                    if s.stratum_name == "age_band"}
    # P1's transition has no age_band -> "unknown"
    # P2's transition has "70-79"
    assert "unknown" in age_strata
    assert "70-79" in age_strata

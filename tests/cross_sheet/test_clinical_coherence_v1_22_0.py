"""Tests for the v1.22.0 cross-sheet condition types and clinical coherence pack.

Covers the new declarative condition types added in v1.22.0 that the
ad_clinical_coherence pack uses for citation-locked CLINICAL coherence:
  - numeric_conflict (cross-modal biomarker discordance)
  - trajectory_monotonicity (incl. treatment gating)
  - categorical_implies_range_rowwise

The referential_integrity condition type also added in v1.22.0 is a general
data-integrity primitive; it is exercised by the input-contract layer (orphan
detection), not by this clinical pack, so it is tested in tests/input_contract/.

This file confirms the ad_clinical_coherence production pack loads and evaluates.
"""
from __future__ import annotations

from neurotcs.cross_sheet import audit_cross_sheet, load_invariantpack


def _run(pack_name, submission):
    lp = load_invariantpack(pack_name)
    return audit_cross_sheet(submission, [lp], dry_run=False)


# ---- pack loads ----

def test_ad_clinical_coherence_pack_loads():
    lp = load_invariantpack("cross_sheet/ad_clinical_coherence")
    assert lp.status.value == "production"
    assert len(lp.invariantpack.invariants) == 6
    types = {inv.condition.type for inv in lp.invariantpack.invariants}
    assert "numeric_conflict" in types
    assert "trajectory_monotonicity" in types
    assert "categorical_implies_range_rowwise" in types


# ---- numeric_conflict ----

def test_numeric_conflict_flags_discordant_pair():
    sub = {
        "biomarkers": [
            {"patient_id": "P1", "visit_id": 0, "plasma_ptau217_pgml": 1.2, "amyloid_centiloid": 5.0},
            {"patient_id": "P2", "visit_id": 0, "plasma_ptau217_pgml": 0.1, "amyloid_centiloid": 5.0},
            {"patient_id": "P3", "visit_id": 0, "plasma_ptau217_pgml": 1.2, "amyloid_centiloid": 90.0},
        ],
    }
    res = _run("cross_sheet/ad_clinical_coherence", sub)
    fired = {f.join_key_values.get("patient_id")
             for f in res.flags
             if f.invariant_name == "elevated_ptau217_with_negative_amyloid_pet_discordance"}
    assert fired == {"P1"}  # P2 low tau, P3 positive amyloid -> not discordant


# ---- trajectory_monotonicity ----

def test_monotonicity_flags_increasing_hippocampus():
    sub = {
        "biomarkers": [
            {"patient_id": "P1", "visit_id": 0, "hippocampus_total_cm3": 2.5},
            {"patient_id": "P1", "visit_id": 1, "hippocampus_total_cm3": 3.5},  # grows -> violation
            {"patient_id": "P2", "visit_id": 0, "hippocampus_total_cm3": 3.5},
            {"patient_id": "P2", "visit_id": 1, "hippocampus_total_cm3": 3.3},  # shrinks -> ok
        ],
    }
    res = _run("cross_sheet/ad_clinical_coherence", sub)
    fired = {f.join_key_values.get("patient_id")
             for f in res.flags
             if f.invariant_name == "hippocampal_volume_must_not_increase_over_follow_up"}
    assert fired == {"P1"}


def test_monotonicity_treatment_gate_exempts_on_treatment_clearance():
    # amyloid drops under treatment -> exempt; drops untreated -> flagged
    sub = {
        "biomarkers": [
            {"patient_id": "TREATED", "visit_id": 0, "amyloid_centiloid": 90.0, "treatment_flags": ""},
            {"patient_id": "TREATED", "visit_id": 1, "amyloid_centiloid": 20.0, "treatment_flags": "lecanemab"},
            {"patient_id": "UNTREATED", "visit_id": 0, "amyloid_centiloid": 90.0, "treatment_flags": ""},
            {"patient_id": "UNTREATED", "visit_id": 1, "amyloid_centiloid": 20.0, "treatment_flags": ""},
        ],
    }
    res = _run("cross_sheet/ad_clinical_coherence", sub)
    fired = {f.join_key_values.get("patient_id")
             for f in res.flags
             if f.invariant_name == "amyloid_centiloid_must_not_spontaneously_clear_untreated"}
    assert fired == {"UNTREATED"}


# ---- categorical_implies_range_rowwise ----

def test_rowwise_flags_status_value_discordance():
    sub = {
        "biomarkers": [
            {"patient_id": "P1", "visit_id": 0, "amyloid_status": "negative", "amyloid_centiloid": 88.0},  # discordant
            {"patient_id": "P2", "visit_id": 0, "amyloid_status": "negative", "amyloid_centiloid": 5.0},   # ok
            {"patient_id": "P3", "visit_id": 0, "amyloid_status": "positive", "amyloid_centiloid": 88.0},  # not triggered
        ],
    }
    res = _run("cross_sheet/ad_clinical_coherence", sub)
    fired = {f.join_key_values.get("patient_id")
             for f in res.flags
             if f.invariant_name == "amyloid_negative_status_requires_negative_centiloid"}
    assert fired == {"P1"}




# ---- value_range_conditional cognitive consistency ----

def test_cognitive_consistency_flags_cn_with_dementia_scores():
    sub = {
        "predictions": [
            {"patient_id": "P1", "visit_id": 0, "predicted_state": "CN"},
            {"patient_id": "P2", "visit_id": 0, "predicted_state": "CN"},
            {"patient_id": "P3", "visit_id": 0, "predicted_state": "AD"},
        ],
        "biomarkers": [
            {"patient_id": "P1", "visit_id": 0, "cdr_global": 2.0, "mmse_total": 12.0},  # both inconsistent
            {"patient_id": "P2", "visit_id": 0, "cdr_global": 0.0, "mmse_total": 29.0},  # consistent
            {"patient_id": "P3", "visit_id": 0, "cdr_global": 2.0, "mmse_total": 12.0},  # AD, not triggered
        ],
    }
    res = _run("cross_sheet/ad_clinical_coherence", sub)
    cdr = {f.join_key_values.get("patient_id") for f in res.flags
           if f.invariant_name == "cn_state_requires_non_dementia_cdr"}
    mmse = {f.join_key_values.get("patient_id") for f in res.flags
            if f.invariant_name == "cn_state_requires_non_demented_mmse"}
    assert cdr == {"P1"}
    assert mmse == {"P1"}


# ---- determinism: same input -> same flag_ids ----

def test_new_condition_flag_ids_deterministic():
    sub = {
        "biomarkers": [
            {"patient_id": "P1", "visit_id": 0, "plasma_ptau217_pgml": 1.2, "amyloid_centiloid": 5.0},
        ],
    }
    r1 = _run("cross_sheet/ad_clinical_coherence", sub)
    r2 = _run("cross_sheet/ad_clinical_coherence", sub)
    ids1 = sorted(f.flag_id for f in r1.flags)
    ids2 = sorted(f.flag_id for f in r2.flags)
    assert ids1 == ids2

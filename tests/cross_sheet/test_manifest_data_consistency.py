"""
Tests for cross_sheet/manifest_data_consistency@1.0.0 (v1.18.0 NEW).

Closes the v1.11.0-design.2 §9.3 gap: tool_declaration_consistency and
genotype_phenotype_consistency were the first two Layer 3 production
packs; manifest_data_consistency is the third, shipped in v1.18.0.

Three invariants:
  1. L3_conformance_requires_complete_attribution
  2. continuous_biomarkers_declared_then_biomarkers_sheet_required
  3. rulepack_reference_consistency
"""
from __future__ import annotations

import pytest

from neurotcs.cross_sheet.audit import audit_cross_sheet
from neurotcs.cross_sheet.loader import load_invariantpack


@pytest.fixture(scope="module")
def pack():
    return load_invariantpack("cross_sheet/manifest_data_consistency")


def test_pack_loads_at_production_status(pack):
    ip = pack.invariantpack
    assert ip.invariantpack_id == "cross_sheet/manifest_data_consistency@1.0.0"
    assert ip.status.value == "production"
    assert len(ip.invariants) == 3


def test_pack_yaml_sha256_locked(pack):
    """yaml_sha256 lock: any content change must bump pack_version."""
    EXPECTED = "8eac54ef8aca2edde99b8fbc3cb3960b040f0a07fba6187dc2dbb5686cbdcc4c"
    assert pack.yaml_sha256 == EXPECTED, (
        f"yaml_sha256 changed: expected {EXPECTED}, got {pack.yaml_sha256}. "
        "If the pack was intentionally modified, update this golden value AND "
        "bump pack_version in CHANGELOG."
    )


def test_invariant_names_and_severities(pack):
    by_name = {inv.name: inv for inv in pack.invariantpack.invariants}
    assert "L3_conformance_requires_complete_attribution" in by_name
    assert "continuous_biomarkers_declared_then_biomarkers_sheet_required" in by_name
    assert "rulepack_reference_consistency" in by_name

    # severities per LAYER_3_DESIGN §9.3
    assert by_name["L3_conformance_requires_complete_attribution"].flag_severity == "error"
    assert by_name["continuous_biomarkers_declared_then_biomarkers_sheet_required"].flag_severity == "error"
    assert by_name["rulepack_reference_consistency"].flag_severity == "info"


def test_invariant_1_l3_missing_attribution_fires(pack):
    """L3 declared, predictions present, attribution missing → 1 error flag."""
    submission = {
        "manifest": {
            "conformance_level": "L3",
            "declares_continuous_biomarkers": False,
            "rule_pack": {"id": "ad/aa_2024"},
        },
        "predictions": [
            {"patient_id": "P1", "visit_id": "V1", "predicted_state": "MCI"},
            {"patient_id": "P1", "visit_id": "V2", "predicted_state": "MCI"},
        ],
    }
    result = audit_cross_sheet(submission, [pack])
    fired = [f for f in result.flags if f.invariant_name == "L3_conformance_requires_complete_attribution"]
    assert len(fired) == 1
    assert fired[0].severity == "error"


def test_invariant_1_l3_with_full_attribution_silent(pack):
    """L3 declared, attribution present for every (patient, visit) → no flag."""
    submission = {
        "manifest": {
            "conformance_level": "L3",
            "declares_continuous_biomarkers": False,
            "rule_pack": {"id": "ad/aa_2024"},
        },
        "predictions": [
            {"patient_id": "P1", "visit_id": "V1", "predicted_state": "MCI"},
            {"patient_id": "P1", "visit_id": "V2", "predicted_state": "MCI"},
        ],
        "attribution": [
            {"patient_id": "P1", "visit_id": "V1", "assay": "test"},
            {"patient_id": "P1", "visit_id": "V2", "assay": "test"},
        ],
    }
    result = audit_cross_sheet(submission, [pack])
    fired = [f for f in result.flags if f.invariant_name == "L3_conformance_requires_complete_attribution"]
    assert len(fired) == 0


def test_invariant_1_l1_no_trigger(pack):
    """L1 conformance does not trigger the L3 attribution invariant."""
    submission = {
        "manifest": {
            "conformance_level": "L1",
            "declares_continuous_biomarkers": False,
            "rule_pack": {"id": "ad/aa_2024"},
        },
        "predictions": [{"patient_id": "P1", "visit_id": "V1"}],
    }
    result = audit_cross_sheet(submission, [pack])
    fired = [f for f in result.flags if f.invariant_name == "L3_conformance_requires_complete_attribution"]
    assert len(fired) == 0


def test_invariant_2_biomarkers_declared_missing_sheet_fires(pack):
    """declares_continuous_biomarkers=True but no biomarkers sheet → 1 error flag.

    Verifies the v1.18.0 engine extension that coerces boolean True →
    string "true" so the YAML source_value: "true" matches.
    """
    submission = {
        "manifest": {
            "conformance_level": "L2",
            "declares_continuous_biomarkers": True,
            "rule_pack": {"id": "ad/aa_2024"},
        },
        "predictions": [{"patient_id": "P1", "visit_id": "V1"}],
        "patients": [{"patient_id": "P1", "apoe_genotype": "e3/e3"}],
    }
    result = audit_cross_sheet(submission, [pack])
    fired = [
        f for f in result.flags
        if f.invariant_name == "continuous_biomarkers_declared_then_biomarkers_sheet_required"
    ]
    assert len(fired) == 1
    assert fired[0].severity == "error"


def test_invariant_2_biomarkers_declared_with_sheet_silent(pack):
    submission = {
        "manifest": {
            "conformance_level": "L2",
            "declares_continuous_biomarkers": True,
            "rule_pack": {"id": "ad/aa_2024"},
        },
        "predictions": [{"patient_id": "P1", "visit_id": "V1"}],
        "biomarkers": [
            {"patient_id": "P1", "visit_id": "V1", "biomarker": "hippo_vol",
             "value": 3.4, "unit": "cm3"}
        ],
    }
    result = audit_cross_sheet(submission, [pack])
    fired = [
        f for f in result.flags
        if f.invariant_name == "continuous_biomarkers_declared_then_biomarkers_sheet_required"
    ]
    assert len(fired) == 0


def test_invariant_2_biomarkers_not_declared_silent(pack):
    """declares_continuous_biomarkers=False → invariant does not fire."""
    submission = {
        "manifest": {
            "conformance_level": "L2",
            "declares_continuous_biomarkers": False,
            "rule_pack": {"id": "ad/aa_2024"},
        },
        "predictions": [{"patient_id": "P1", "visit_id": "V1"}],
    }
    result = audit_cross_sheet(submission, [pack])
    fired = [
        f for f in result.flags
        if f.invariant_name == "continuous_biomarkers_declared_then_biomarkers_sheet_required"
    ]
    assert len(fired) == 0


def test_invariant_3_unknown_rulepack_fires(pack):
    """Unknown rule_pack.id → info flag (coverage-gap semantics).

    Verifies the v1.18.0 engine extension that supports dotted paths
    (rule_pack.id) on nested manifest objects.
    """
    submission = {
        "manifest": {
            "conformance_level": "L2",
            "declares_continuous_biomarkers": False,
            "rule_pack": {"id": "ad/totally_made_up_pack"},
        },
        "predictions": [{"patient_id": "P1", "visit_id": "V1"}],
    }
    result = audit_cross_sheet(submission, [pack])
    fired = [f for f in result.flags if f.invariant_name == "rulepack_reference_consistency"]
    assert len(fired) == 1
    assert fired[0].severity == "info"


def test_invariant_3_known_rulepacks_silent(pack):
    """Each of the 3 known rulepack IDs → no flag."""
    for known in ("ad/aa_2024", "ad/aa_2024_trac", "ad/niaaa_2018"):
        submission = {
            "manifest": {
                "conformance_level": "L1",
                "declares_continuous_biomarkers": False,
                "rule_pack": {"id": known},
            },
            "predictions": [{"patient_id": "P1", "visit_id": "V1"}],
        }
        result = audit_cross_sheet(submission, [pack])
        fired = [f for f in result.flags if f.invariant_name == "rulepack_reference_consistency"]
        assert len(fired) == 0, f"unexpected flag for known rulepack {known}"


def test_clean_l1_submission_zero_flags(pack):
    """L1 submission, no continuous biomarkers declared, known rulepack → 0 flags."""
    submission = {
        "manifest": {
            "conformance_level": "L1",
            "declares_continuous_biomarkers": False,
            "rule_pack": {"id": "ad/aa_2024"},
        },
        "predictions": [{"patient_id": "P1", "visit_id": "V1"}],
    }
    result = audit_cross_sheet(submission, [pack])
    assert len(result.flags) == 0


def test_all_invariants_have_5plus_endorsing_bodies(pack):
    """Production gate: every invariant carries >=5 endorsing bodies."""
    for inv in pack.invariantpack.invariants:
        assert inv.citation is not None
        bodies = inv.citation.endorsing_bodies
        assert len(bodies) >= 5, (
            f"{inv.name}: {len(bodies)} endorsing bodies "
            f"(production gate requires >=5)"
        )


def test_anchor_citation_5plus_endorsing_bodies(pack):
    """Pack-level anchor must also carry >=5 endorsing bodies."""
    bodies = pack.invariantpack.anchor_citation.endorsing_bodies
    assert len(bodies) >= 5

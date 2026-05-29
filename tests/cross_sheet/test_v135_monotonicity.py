"""
v1.35.0 -- biomarker_longitudinal_monotonicity invariant pack tests.

Mirrors the v1.34 discipline: every value_field referenced by the new
invariants must exist as an actual measurement in the corresponding
range pack, OR the invariant is silently broken at runtime. Cross-pack
consistency is CI-enforced.

Aligned with NeuroTCS's auditor identity: these tests verify the pack
AUDITS tool-produced trajectories (never measures), is citation-locked
(every invariant has a verified PMID or DOI), and is fail-closed
(research_preview refuses production audit).
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.cross_sheet.loader import load_invariantpack
from neurotcs.cross_sheet.schema import InvariantPackStatus


@pytest.fixture(scope="module")
def pack():
    return load_invariantpack("cross_sheet/biomarker_longitudinal_monotonicity").invariantpack


@pytest.fixture(scope="module")
def by_name(pack):
    return {i.name: i for i in pack.invariants}


# ---------- pack-level ----------
def test_pack_loads_research_preview_with_thirteen_invariants(pack):
    # v0.1.0 shipped 9 invariants (v1.35.0); v0.2.0 (v1.36.0) added 4 GFAP/NfL
    assert pack.invariantpack_id == "cross_sheet/biomarker_longitudinal_monotonicity@0.2.0"
    assert pack.status == InvariantPackStatus.RESEARCH_PREVIEW
    assert len(pack.invariants) == 13


def test_all_invariants_use_trajectory_monotonicity_condition(by_name):
    for inv in by_name.values():
        assert inv.condition.type == "trajectory_monotonicity"


def test_all_invariants_are_warning_severity_not_error(by_name):
    """Auditor discipline: flag for review, do not diagnose. Severity = warning, not error."""
    for inv in by_name.values():
        assert inv.flag_severity == "warning"


def test_all_invariants_have_verified_citation_pmid_or_doi(by_name):
    """No fabricated citations: every invariant must carry a verified PMID or DOI."""
    for inv in by_name.values():
        cit = inv.citation
        assert cit.citation_pmid or cit.citation_doi, (
            f"Invariant {inv.name} has no verified PMID/DOI anchor"
        )


# ---------- direction-correctness (the biology) ----------
def test_imaging_neurodegen_markers_are_non_increasing(by_name):
    """Retinal thinning, synapse loss, CBF decline, FA reduction -- all non_increasing."""
    non_increasing = [
        "rnfl_peripapillary_thickness_must_not_increase_over_follow_up",
        "gc_ipl_macular_thickness_must_not_increase_over_follow_up",
        "ucbj_dvr_hippocampus_must_not_increase_over_follow_up",
        "ucbj_dvr_neocortical_must_not_increase_over_follow_up",
        "asl_cbf_global_must_not_increase_over_follow_up",
        "dti_fa_fornix_must_not_increase_over_follow_up",
    ]
    for name in non_increasing:
        assert by_name[name].condition.direction == "non_increasing", (
            f"{name} should be non_increasing (biomarker DECREASES with AD progression)"
        )


def test_md_and_ptau217_are_non_decreasing(by_name):
    """DTI MD rises with WM degeneration; p-tau217 rises along AD continuum."""
    non_decreasing = [
        "dti_md_fornix_must_not_decrease_over_follow_up",
        "csf_ptau217_must_not_spontaneously_decrease_untreated",
        "plasma_ptau217_must_not_spontaneously_decrease_untreated",
    ]
    for name in non_decreasing:
        assert by_name[name].condition.direction == "non_decreasing"


def test_fluid_biomarker_invariants_are_treatment_gated(by_name):
    """Anti-amyloid therapy attenuates p-tau217, GFAP, NfL (TRAILBLAZER, Clarity AD);
    structural imaging biomarkers (OCT, SV2A, ASL, DTI) are not treatment-reversible at
    present and should not have a treatment_gate_field. Updated in v1.36.0 when GFAP/NfL
    invariants joined the pack.

    Uses an explicit enumeration (not substring matching) because 'nfl' is a substring of
    'rnfl' (RNFL = peripapillary retinal nerve fiber layer thickness, which is a STRUCTURAL
    optical-coherence biomarker, NOT a fluid neurofilament-light marker). Substring matching
    on 'nfl' would wrongly require the RNFL invariant to be treatment-gated."""
    TREATMENT_GATED = {
        "csf_ptau217_must_not_spontaneously_decrease_untreated",
        "plasma_ptau217_must_not_spontaneously_decrease_untreated",
        "plasma_gfap_must_not_spontaneously_decrease_untreated",
        "csf_gfap_must_not_spontaneously_decrease_untreated",
        "plasma_nfl_must_not_spontaneously_decrease_untreated",
        "csf_nfl_must_not_spontaneously_decrease_untreated",
    }
    for name, inv in by_name.items():
        if name in TREATMENT_GATED:
            assert inv.condition.treatment_gate_field == "treatment_flags", (
                f"{name} (fluid biomarker, attenuated by anti-amyloid therapy) "
                f"must be treatment-gated"
            )
        else:
            assert inv.condition.treatment_gate_field is None, (
                f"{name} (structural imaging biomarker) must NOT be treatment-gated"
            )


# ---------- tolerance values are positive and biomarker-appropriate ----------
def test_tolerances_are_positive(by_name):
    for inv in by_name.values():
        assert inv.condition.tolerance > 0.0, (
            f"{inv.name} tolerance must be > 0 (otherwise no noise floor)"
        )


def test_min_visits_at_least_two(by_name):
    """A monotonicity check on <2 visits is trivially satisfied; require >= 2."""
    for inv in by_name.values():
        assert inv.condition.min_visits >= 2


# ---------- cross-pack integration (the v1.34 discipline) ----------
RANGE_PACK_OF_FIELD = {
    "rnfl_peripapillary_thickness_um":     "retinal_biomarkers/oct_research_preview",
    "gc_ipl_macular_thickness_um":         "retinal_biomarkers/oct_research_preview",
    "ucbj_dvr_hippocampus":                "synaptic_pet/sv2a_research_preview",
    "ucbj_dvr_neocortical_meta":           "synaptic_pet/sv2a_research_preview",
    "asl_cbf_global_ml_per_100g_min":      "perfusion/asl_cbf_research_preview",
    "fa_fornix":                           "dti/microstructure_research_preview",
    "md_fornix":                           "dti/microstructure_research_preview",
    "csf_ptau217_pgml":                    "csf_biomarkers/csf_ptau217_consensus",
    "plasma_ptau217_pgml":                 "plasma_biomarkers/plasma_amyloid_consensus",
    # v1.36.0 additions:
    "plasma_gfap_pgml":                    "plasma_biomarkers/plasma_gfap_research_preview",
    "csf_gfap_pgml":                       "csf_biomarkers/csf_gfap_research_preview",
    "plasma_nfl_pgml":                     "plasma_biomarkers/nfl_consensus",
    "csf_nfl_pgml":                        "csf_biomarkers/csf_nfl_research_preview",
}


def test_every_value_field_exists_in_a_range_pack(by_name):
    """Every value_field the invariants reference must exist as a measurement in some
    range pack. Without this, the invariants would silently never fire at runtime."""
    for inv in by_name.values():
        vf = inv.condition.value_field
        assert vf in RANGE_PACK_OF_FIELD, (
            f"value_field {vf!r} (in {inv.name}) is not mapped to a known range pack -- "
            f"either fix the value_field name or extend RANGE_PACK_OF_FIELD"
        )
        pack_id = RANGE_PACK_OF_FIELD[vf]
        lp = load_rangepack(pack_id)
        range_fields = {m.name for m in lp.rangepack.measurements}
        assert vf in range_fields, (
            f"value_field {vf!r} in invariant {inv.name} is not present in {pack_id} "
            f"(available measurements: {sorted(range_fields)})"
        )


# ---------- determinism / reproducibility ----------
def test_canonical_sha256_reproducible():
    """NeuroTCS load-bearing property: deterministic audit_id requires deterministic pack hash."""
    a = load_invariantpack("cross_sheet/biomarker_longitudinal_monotonicity").canonical_sha256
    b = load_invariantpack("cross_sheet/biomarker_longitudinal_monotonicity").canonical_sha256
    assert a == b


# ---------- alignment with v1.33.0 roadmap promise ----------
def test_closes_v133_longitudinal_monotonicity_roadmap_item(by_name):
    """v1.33.0 CHANGELOG promised: 'longitudinal monotonicity on the new biomarker classes'.
    Verify coverage spans the v1.30-v1.33 biomarker classes."""
    fields = {inv.condition.value_field for inv in by_name.values()}
    coverage_classes = {
        "OCT (RNFL or GC-IPL)":        any("rnfl" in f or "gc_ipl" in f for f in fields),
        "SV2A UCB-J":                  any("ucbj" in f for f in fields),
        "ASL CBF":                     any("asl_cbf" in f for f in fields),
        "DTI (FA and MD)":             any("fa_" in f for f in fields) and any("md_" in f for f in fields),
        "CSF p-tau217 (v1.30)":        any("csf_ptau217" in f for f in fields),
        "Plasma p-tau217":             any("plasma_ptau217" in f for f in fields),
    }
    missing = [k for k, v in coverage_classes.items() if not v]
    assert not missing, f"v1.35.0 should cover all major new classes; missing: {missing}"

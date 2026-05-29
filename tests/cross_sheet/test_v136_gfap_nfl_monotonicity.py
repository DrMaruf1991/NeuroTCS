"""
v1.36.0 -- extends biomarker_longitudinal_monotonicity from v0.1.0 to v0.2.0.

Adds 4 fluid-biomarker monotonicity invariants for the v1.30 GFAP/NfL classes:
  - plasma_gfap_pgml non_decreasing (treatment-gated; Benedet 2021)
  - csf_gfap_pgml    non_decreasing (treatment-gated; Benedet 2021)
  - plasma_nfl_pgml  non_decreasing (treatment-gated; Mattsson 2017)
  - csf_nfl_pgml     non_decreasing (treatment-gated; Mattsson 2017)

NeuroTCS auditor discipline: these tests verify the new invariants AUDIT
tool-produced trajectories (never measure), are citation-locked to verified
primary literature, and are fail-closed (research_preview).
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


# ---------- pack version bump ----------
def test_pack_bumped_to_v0_2_0(pack):
    assert pack.invariantpack_id == "cross_sheet/biomarker_longitudinal_monotonicity@0.2.0"
    assert pack.pack_version == "0.2.0"


def test_pack_extended_from_nine_to_thirteen_invariants(pack):
    assert len(pack.invariants) == 13


def test_pack_remains_research_preview_warning_severity(pack, by_name):
    """Pack remains research_preview (matches research_preview status of underlying
    range packs) and all invariants remain warning severity (flag for review)."""
    assert pack.status == InvariantPackStatus.RESEARCH_PREVIEW
    for inv in by_name.values():
        assert inv.flag_severity == "warning"


# ---------- four new invariants exist ----------
NEW_INVARIANT_NAMES = {
    "plasma_gfap_must_not_spontaneously_decrease_untreated",
    "csf_gfap_must_not_spontaneously_decrease_untreated",
    "plasma_nfl_must_not_spontaneously_decrease_untreated",
    "csf_nfl_must_not_spontaneously_decrease_untreated",
}


def test_all_four_new_invariants_present(by_name):
    missing = NEW_INVARIANT_NAMES - set(by_name)
    assert not missing, f"v1.36.0 should add {NEW_INVARIANT_NAMES}; missing: {missing}"


def test_all_four_use_non_decreasing_direction(by_name):
    """GFAP and NfL rise with disease progression -- direction is non_decreasing."""
    for name in NEW_INVARIANT_NAMES:
        assert by_name[name].condition.direction == "non_decreasing", (
            f"{name} should be non_decreasing (GFAP/NfL RISE with AD progression)"
        )


def test_all_four_are_treatment_gated(by_name):
    """Anti-amyloid therapy attenuates plasma/CSF GFAP (TRAILBLAZER-ALZ 2 / Clarity AD
    biomarker substudies clearly document GFAP reduction); NfL effects under anti-
    amyloid therapy are more modest but documented, so treatment-gated conservatively."""
    for name in NEW_INVARIANT_NAMES:
        assert by_name[name].condition.treatment_gate_field == "treatment_flags", (
            f"{name} should have treatment_gate_field=treatment_flags"
        )


# ---------- citation anchors verified from primary literature ----------
def test_gfap_invariants_cite_benedet_2021(by_name):
    """Verified primary literature: Benedet AL et al. JAMA Neurol 2021;78(12):1471-1483,
    DOI 10.1001/jamaneurol.2021.3671."""
    for name in (
        "plasma_gfap_must_not_spontaneously_decrease_untreated",
        "csf_gfap_must_not_spontaneously_decrease_untreated",
    ):
        cit = by_name[name].citation
        assert cit.citation_doi == "10.1001/jamaneurol.2021.3671", (
            f"{name} must cite Benedet 2021 by verified DOI"
        )


def test_nfl_invariants_cite_mattsson_2017(by_name):
    """Verified primary literature: Mattsson N et al. JAMA Neurol 2017;74(5):557-566,
    DOI 10.1001/jamaneurol.2016.6117."""
    for name in (
        "plasma_nfl_must_not_spontaneously_decrease_untreated",
        "csf_nfl_must_not_spontaneously_decrease_untreated",
    ):
        cit = by_name[name].citation
        assert cit.citation_doi == "10.1001/jamaneurol.2016.6117", (
            f"{name} must cite Mattsson 2017 by verified DOI"
        )


# ---------- cross-pack integration: every value_field exists in a range pack ----------
def test_new_gfap_nfl_value_fields_exist_in_their_range_packs(by_name):
    """v1.34 / v1.35 discipline: invariants cannot silently reference non-existent
    columns. Each value_field must be present in the corresponding range pack."""
    field_to_pack = {
        "plasma_gfap_pgml": "plasma_biomarkers/plasma_gfap_research_preview",
        "csf_gfap_pgml":    "csf_biomarkers/csf_gfap_research_preview",
        "plasma_nfl_pgml":  "plasma_biomarkers/nfl_consensus",
        "csf_nfl_pgml":     "csf_biomarkers/csf_nfl_research_preview",
    }
    for name in NEW_INVARIANT_NAMES:
        vf = by_name[name].condition.value_field
        pack_id = field_to_pack[vf]
        lp = load_rangepack(pack_id)
        range_fields = {m.name for m in lp.rangepack.measurements}
        assert vf in range_fields, (
            f"value_field {vf!r} (in {name}) is not in {pack_id} "
            f"(measurements: {sorted(range_fields)})"
        )


# ---------- conservative-tolerance discipline ----------
def test_tolerances_are_conservative_and_positive(by_name):
    """Tolerance values are derived from published Simoa/Lumipulse coefficient-of-variation
    literature. Each should be positive (a noise floor exists)."""
    EXPECTED_TOLERANCES = {
        "plasma_gfap_must_not_spontaneously_decrease_untreated": 30.0,   # pg/mL, ~15% CV on AD-range 150-400 pg/mL
        "csf_gfap_must_not_spontaneously_decrease_untreated":    1500.0, # pg/mL, ~10% CV on 5000-15000 pg/mL
        "plasma_nfl_must_not_spontaneously_decrease_untreated":  5.0,    # pg/mL, ~10% CV on 20-50 pg/mL
        "csf_nfl_must_not_spontaneously_decrease_untreated":     200.0,  # pg/mL, ~10% CV on 800-2000 pg/mL
    }
    for name, expected in EXPECTED_TOLERANCES.items():
        actual = by_name[name].condition.tolerance
        assert actual == expected, f"{name}: expected tolerance {expected}, got {actual}"
        assert actual > 0


# ---------- auditor discipline reflected in descriptions ----------
def test_descriptions_say_audits_not_measures(by_name):
    """NeuroTCS load-bearing identity: AUDITS tool-produced trajectories, does not measure.
    Each new invariant's description must literally say 'AUDITS' (capital A) and 'does NOT
    measure' / 'does not measure'."""
    for name in NEW_INVARIANT_NAMES:
        desc = by_name[name].description
        assert "AUDITS" in desc, f"{name} description must lead with 'AUDITS'"
        assert "does NOT measure" in desc or "does not measure" in desc, (
            f"{name} description must state NeuroTCS does not measure the biomarker"
        )


# ---------- deterministic audit_id property ----------
def test_canonical_sha256_reproducible():
    """v0.2.0 pack must remain deterministic (load-bearing property of NeuroTCS)."""
    a = load_invariantpack("cross_sheet/biomarker_longitudinal_monotonicity").canonical_sha256
    b = load_invariantpack("cross_sheet/biomarker_longitudinal_monotonicity").canonical_sha256
    assert a == b

"""
Behavior tests for plasma_biomarkers/plasma_amyloid_consensus@1.0.0.

Verifies AA CPG 2025 thresholds, Giacomucci 2025 two-cutoff approach,
and FDA-cleared Lumipulse pTau217/Aβ42 plasma ratio.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack
from neurotcs.clinical_ranges.schema import CitationStrength


@pytest.fixture(scope="module")
def plasma_pack():
    return load_rangepack("plasma_biomarkers/plasma_amyloid_consensus")


class TestPlasmaAmyloidPackStructure:

    def test_pack_is_production(self, plasma_pack):
        from neurotcs.clinical_ranges.schema import RangePackStatus
        assert plasma_pack.rangepack.status == RangePackStatus.PRODUCTION

    def test_pack_has_five_measurements(self, plasma_pack):
        assert len(plasma_pack.rangepack.measurements) == 5

    def test_every_bound_is_international_consensus(self, plasma_pack):
        for m in plasma_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_every_bound_has_5plus_bodies(self, plasma_pack):
        for m in plasma_pack.rangepack.measurements:
            for b in m.bounds:
                assert len(b.citation.endorsing_bodies) >= 5

    def test_aa_cpg_2025_in_anchor(self, plasma_pack):
        """The Palmqvist 2025 CPG DOI should anchor the pack."""
        anchor = plasma_pack.rangepack.anchor_citation
        assert "alz.70535" in (anchor.citation_doi or "")


class TestPlasmaPtau217:
    """Giacomucci 2025 two-cutoff approach: 0.229-0.516 pg/mL."""

    def test_low_value_below_cutoff_passes_rule_out(self, plasma_pack):
        """Below 0.229 pg/mL = amyloid-negative (passes plausible_min check)."""
        df = pd.DataFrame({
            "patient_id": ["P_low"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau217_pgml"],
            "value": [0.15],
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        # Below plausible_min=0.229 → flagged plausible_min (clinically: rule-out)
        assert any(f.bound_type == "plausible_min" for f in r.flags)

    def test_intermediate_value_passes_both_bounds(self, plasma_pack):
        """Between 0.229 and 0.516 = intermediate zone."""
        df = pd.DataFrame({
            "patient_id": ["P_intermediate"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau217_pgml"],
            "value": [0.4],
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        # Between plausible_min=0.229 and plausible_max=0.516 → no flag
        assert r.n_flagged == 0

    def test_high_value_flagged_plausible_max(self, plasma_pack):
        """Above 0.516 = amyloid-positive (rule-in zone, plausible_max crossed)."""
        df = pd.DataFrame({
            "patient_id": ["P_high"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau217_pgml"],
            "value": [0.8],
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert any(f.bound_type == "plausible_max" for f in r.flags)

    def test_implausibly_high_flagged_hard_max(self, plasma_pack):
        """Above 5.0 pg/mL is biologically implausible."""
        df = pd.DataFrame({
            "patient_id": ["P_err"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau217_pgml"],
            "value": [10.0],
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert any(f.bound_type == "hard_max" for f in r.flags)


class TestPlasmaAmyloidStatus:

    def test_three_zones_pass(self, plasma_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["plasma_amyloid_status"] * 3,
            "value": ["negative", "intermediate", "positive"],
            "unit": ["categorical"] * 3,
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert r.n_flagged == 0

    def test_invalid_zone_flagged(self, plasma_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_amyloid_status"],
            "value": ["high"],  # not in the three-tier set
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert r.n_flagged == 1


class TestBiomarkerPerformanceTier:

    def test_three_tiers_pass(self, plasma_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["biomarker_performance_tier"] * 3,
            "value": ["triaging", "confirmatory", "research_only"],
            "unit": ["categorical"] * 3,
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert r.n_flagged == 0

    def test_invalid_tier_flagged(self, plasma_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["biomarker_performance_tier"],
            "value": ["preferred"],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert r.n_flagged == 1


class TestPlasmaDeterminism:

    def test_same_input_same_flag_id(self, plasma_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau217_pgml"],
            "value": [0.4],
            "unit": ["pg/mL"],
        })
        r1 = audit_clinical_ranges(df, plasma_pack)
        r2 = audit_clinical_ranges(df, plasma_pack)
        assert r1.flag_id == r2.flag_id

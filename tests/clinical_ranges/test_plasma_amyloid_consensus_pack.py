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

    def test_pack_has_six_measurements(self, plasma_pack):
        """v1.14.0 added plasma_ptau181_pgml_elecsys (FDA-cleared Oct 2025)
        as the 6th measurement (was 5 in v1.10.x-v1.13.x)."""
        assert len(plasma_pack.rangepack.measurements) == 6

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


class TestPlasmaPtau181Elecsys:
    """Roche Elecsys pTau181 plasma — FDA 510(k) K252163 cleared Oct 13, 2025.

    FDA-cleared rule-out cutoff: 0.722 pg/mL (verbatim from K252163 Decision
    Summary). Values below this cutoff are consistent with amyloid-PET-
    negative AD pathology (97.9% NPV in primary-care 312-participant cohort).
    """

    def test_low_value_below_cutoff_passes_rule_out(self, plasma_pack):
        """Below 0.722 pg/mL = consistent with amyloid-negative; should not flag."""
        df = pd.DataFrame({
            "patient_id": ["P_low_ptau181"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau181_pgml_elecsys"],
            "value": [0.5],  # Well below 0.722 cutoff
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        # 0.5 is between hard_min (0.0) and plausible_max (0.722) and hard_max (50.0) — no flags
        assert r.n_flagged == 0

    def test_value_at_fda_cutoff_flagged_plausible_max(self, plasma_pack):
        """At/above 0.722 pg/mL = FDA rule-out cutoff exceeded; should flag plausible_max."""
        df = pd.DataFrame({
            "patient_id": ["P_at_cutoff"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau181_pgml_elecsys"],
            "value": [1.5],  # Above 0.722 FDA cutoff
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert r.n_flagged == 1
        assert any(f.bound_type == "plausible_max" for f in r.flags)

    def test_implausibly_high_flagged_hard_max(self, plasma_pack):
        """Above 50.0 pg/mL = biologically implausible (CSF-as-plasma or contamination);
        should flag both plausible_max AND hard_max."""
        df = pd.DataFrame({
            "patient_id": ["P_implausible"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau181_pgml_elecsys"],
            "value": [100.0],  # Way above hard_max=50.0
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        # Both plausible_max AND hard_max flag (100 > 0.722 AND 100 > 50.0)
        assert r.n_flagged >= 1
        assert any(f.bound_type == "hard_max" for f in r.flags)

    def test_negative_value_flagged_hard_min(self, plasma_pack):
        """Negative pg/mL is biologically impossible; should flag hard_min."""
        df = pd.DataFrame({
            "patient_id": ["P_negative"],
            "visit_id": ["V0"],
            "measurement_name": ["plasma_ptau181_pgml_elecsys"],
            "value": [-1.0],
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, plasma_pack)
        assert r.n_flagged == 1
        assert any(f.bound_type == "hard_min" for f in r.flags)

    def test_fda_cutoff_exact_value(self, plasma_pack):
        """The 0.722 cutoff must match FDA 510(k) K252163 verbatim."""
        ptau181 = next(
            m for m in plasma_pack.rangepack.measurements
            if m.name == "plasma_ptau181_pgml_elecsys"
        )
        plausible_max_bound = next(
            b for b in ptau181.bounds if b.bound_type.value == "plausible_max"
        )
        assert plausible_max_bound.value == 0.722, (
            f"FDA-cleared cutoff must be exactly 0.722 pg/mL per K252163 "
            f"Decision Summary; got {plausible_max_bound.value}"
        )

    def test_fda_endorser_present(self, plasma_pack):
        """FDA must be among the endorsing bodies for the cutoff."""
        ptau181 = next(
            m for m in plasma_pack.rangepack.measurements
            if m.name == "plasma_ptau181_pgml_elecsys"
        )
        plausible_max_bound = next(
            b for b in ptau181.bounds if b.bound_type.value == "plausible_max"
        )
        endorsers = plausible_max_bound.citation.endorsing_bodies
        assert any("FDA" in e for e in endorsers), (
            f"FDA must be among endorsers for the 0.722 cutoff; got: {endorsers}"
        )

    def test_roche_endorser_present(self, plasma_pack):
        """Roche Diagnostics (manufacturer) must be among endorsers."""
        ptau181 = next(
            m for m in plasma_pack.rangepack.measurements
            if m.name == "plasma_ptau181_pgml_elecsys"
        )
        plausible_max_bound = next(
            b for b in ptau181.bounds if b.bound_type.value == "plausible_max"
        )
        endorsers = plausible_max_bound.citation.endorsing_bodies
        assert any("Roche" in e for e in endorsers)

    def test_lilly_codeveloper_endorser_present(self, plasma_pack):
        """Eli Lilly (co-developer) must be among endorsers."""
        ptau181 = next(
            m for m in plasma_pack.rangepack.measurements
            if m.name == "plasma_ptau181_pgml_elecsys"
        )
        plausible_max_bound = next(
            b for b in ptau181.bounds if b.bound_type.value == "plausible_max"
        )
        endorsers = plausible_max_bound.citation.endorsing_bodies
        assert any("Lilly" in e for e in endorsers)

    def test_aa_endorser_present(self, plasma_pack):
        """Alzheimer's Association must be among endorsers."""
        ptau181 = next(
            m for m in plasma_pack.rangepack.measurements
            if m.name == "plasma_ptau181_pgml_elecsys"
        )
        plausible_max_bound = next(
            b for b in ptau181.bounds if b.bound_type.value == "plausible_max"
        )
        endorsers = plausible_max_bound.citation.endorsing_bodies
        assert any("Alzheimer" in e for e in endorsers)

    def test_three_bounds_total(self, plasma_pack):
        """Measurement should have exactly 3 bounds: hard_min, plausible_max, hard_max."""
        ptau181 = next(
            m for m in plasma_pack.rangepack.measurements
            if m.name == "plasma_ptau181_pgml_elecsys"
        )
        assert len(ptau181.bounds) == 3
        bound_types = {b.bound_type.value for b in ptau181.bounds}
        assert bound_types == {"hard_min", "plausible_max", "hard_max"}

    def test_pack_version_bumped_to_1_1_0(self, plasma_pack):
        """v1.14.0 bumps plasma_amyloid_consensus from @1.0.0 to @1.1.0."""
        assert plasma_pack.rangepack.pack_version == "1.1.0"
        assert "1.1.0" in plasma_pack.rangepack.rangepack_id


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

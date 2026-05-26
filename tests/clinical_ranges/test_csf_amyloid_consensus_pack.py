"""
Behavior tests for csf_biomarkers/csf_amyloid_consensus@1.0.0.

Verifies FDA Lumipulse 510(k) K212622 cutoffs and AA AUR three-zone framework.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack
from neurotcs.clinical_ranges.schema import CitationStrength


@pytest.fixture(scope="module")
def csf_pack():
    return load_rangepack("csf_biomarkers/csf_amyloid_consensus")


class TestCsfAmyloidPackStructure:

    def test_pack_is_production(self, csf_pack):
        from neurotcs.clinical_ranges.schema import RangePackStatus
        assert csf_pack.rangepack.status == RangePackStatus.PRODUCTION

    def test_pack_has_four_measurements(self, csf_pack):
        assert len(csf_pack.rangepack.measurements) == 4

    def test_every_bound_is_international_consensus(self, csf_pack):
        for m in csf_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_every_bound_has_5plus_bodies(self, csf_pack):
        for m in csf_pack.rangepack.measurements:
            for b in m.bounds:
                assert len(b.citation.endorsing_bodies) >= 5

    def test_fda_510k_url_present(self, csf_pack):
        """Lumipulse FDA 510(k) K212622 URL should appear in citations."""
        urls = [b.citation.public_url
                for m in csf_pack.rangepack.measurements
                for b in m.bounds]
        assert any("K212622" in (u or "") or "510k" in (u or "").lower() for u in urls)


class TestLumipulseRatio:

    def test_clearly_positive_value_flags_below_058(self, csf_pack):
        """Ratio of 0.040 is well below the 0.058 FDA cutoff — amyloid positive."""
        df = pd.DataFrame({
            "patient_id": ["P_positive"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.040],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        # value=0.040 is BELOW plausible_max=0.058 → passes (it's a valid "positive" reading)
        assert r.n_flagged == 0

    def test_clearly_negative_value_flagged_above_072(self, csf_pack):
        """Ratio of 0.10 is well above the 0.072 cutoff — exceeds hard_max."""
        df = pd.DataFrame({
            "patient_id": ["P_neg"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.10],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        # crosses BOTH plausible_max=0.058 AND hard_max=0.072
        assert r.n_flagged == 2

    def test_intermediate_zone_flags_plausible_only(self, csf_pack):
        """Ratio of 0.065 is in the intermediate zone (0.058-0.072)."""
        df = pd.DataFrame({
            "patient_id": ["P_intermediate"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.065],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        # crosses plausible_max=0.058 but NOT hard_max=0.072
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "plausible_max"


class TestCsfAbeta42:

    def test_normal_range_passes(self, csf_pack):
        """500-1500 pg/mL is the typical range in clinical CSF."""
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["csf_abeta42_pgml"] * 3,
            "value": [500.0, 1000.0, 1500.0],
            "unit": ["pg/mL"] * 3,
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 0

    def test_implausibly_high_flagged(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P_err"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_pgml"],
            "value": [6000.0],  # exceeds hard_max=5000
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert any(f.bound_type == "hard_max" for f in r.flags)


class TestCsfAmyloidStatus:

    def test_three_zones_pass(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["csf_amyloid_status"] * 3,
            "value": ["negative", "intermediate", "positive"],
            "unit": ["categorical"] * 3,
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 0

    def test_invalid_zone_flagged(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_amyloid_status"],
            "value": ["likely_positive"],  # not in this pack's set
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 1


class TestCsfDeterminism:

    def test_same_input_same_flag_id(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.065],
            "unit": ["ratio"],
        })
        r1 = audit_clinical_ranges(df, csf_pack)
        r2 = audit_clinical_ranges(df, csf_pack)
        assert r1.flag_id == r2.flag_id

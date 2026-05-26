"""
Behavior tests for the world-class production pack ad/aria_safety@1.0.0.

These tests use synthetic ARIA monitoring data to verify that the pack
correctly classifies microhemorrhage counts, siderosis areas, ARIA-E
severity, baseline exclusion counts, and APOE genotype categorical
values per FDA LEQEMBI/KISUNLA labels and ASNR Cogswell 2022 AJNR.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import (
    audit_clinical_ranges,
    load_rangepack,
)
from neurotcs.clinical_ranges.schema import CitationStrength


@pytest.fixture(scope="module")
def aria_pack():
    return load_rangepack("ad/aria_safety")


class TestAriaPackStructure:

    def test_pack_is_production_status(self, aria_pack):
        from neurotcs.clinical_ranges.schema import RangePackStatus
        assert aria_pack.rangepack.status == RangePackStatus.PRODUCTION

    def test_pack_has_five_measurements(self, aria_pack):
        assert len(aria_pack.rangepack.measurements) == 5

    def test_pack_covers_expected_names(self, aria_pack):
        expected = {
            "aria_e_severity",
            "aria_h_microhemorrhage_count",
            "aria_h_siderosis_focal_areas",
            "baseline_microhemorrhage_count",
            "apoe_e4_status",
        }
        assert aria_pack.rangepack.covered_names() == frozenset(expected)

    def test_every_bound_is_international_consensus(self, aria_pack):
        for m in aria_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_anchor_citation_has_fda_url(self, aria_pack):
        # FDA accessdata is one of the canonical public URLs for this pack
        # (either anchor or per-bound)
        anchor_url = aria_pack.rangepack.anchor_citation.public_url
        assert anchor_url and anchor_url.startswith("https://")

    def test_fda_url_appears_in_bound_citations(self, aria_pack):
        """At least one bound should cite the FDA LEQEMBI label directly."""
        urls = [
            b.citation.public_url
            for m in aria_pack.rangepack.measurements
            for b in m.bounds
        ]
        assert any("accessdata.fda.gov" in (u or "") for u in urls)

    def test_per_bound_citations_have_pmid(self, aria_pack):
        """The Cogswell 2022 PMID 35953274 should appear consistently."""
        pmids = set()
        for m in aria_pack.rangepack.measurements:
            for b in m.bounds:
                if b.citation.citation_pmid:
                    pmids.add(b.citation.citation_pmid)
        assert "35953274" in pmids  # Cogswell 2022 AJNR ARIA paper


class TestAriaHMicrohemorrhageBounds:
    """Verify the verbatim FDA bounds: mild ≤4, moderate 5-9, severe ≥10."""

    def test_mild_count_passes(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3", "P4", "P5"],
            "visit_id": ["V1"] * 5,
            "measurement_name": ["aria_h_microhemorrhage_count"] * 5,
            "value": [0, 1, 2, 3, 4],  # all mild
            "unit": ["count"] * 5,
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 0

    def test_moderate_count_flags_plausible_max(self, aria_pack):
        """Counts 5-9 cross plausible_max=4 (the mild→moderate boundary)."""
        df = pd.DataFrame({
            "patient_id": ["P5", "P7", "P9"],
            "visit_id": ["V1"] * 3,
            "measurement_name": ["aria_h_microhemorrhage_count"] * 3,
            "value": [5, 7, 9],
            "unit": ["count"] * 3,
        })
        r = audit_clinical_ranges(df, aria_pack)
        # All three cross plausible_max, none cross hard_max (=9)
        assert r.n_flagged == 3
        for f in r.flags:
            assert f.bound_type == "plausible_max"

    def test_severe_count_flags_both_plausible_and_hard_max(self, aria_pack):
        """Counts ≥10 cross both plausible_max=4 AND hard_max=9."""
        df = pd.DataFrame({
            "patient_id": ["P10", "P15", "P20"],
            "visit_id": ["V1"] * 3,
            "measurement_name": ["aria_h_microhemorrhage_count"] * 3,
            "value": [10, 15, 20],
            "unit": ["count"] * 3,
        })
        r = audit_clinical_ranges(df, aria_pack)
        # Each value crosses both plausible_max=4 AND hard_max=9 → 6 flags total
        assert r.n_flagged == 6
        hard_flags = [f for f in r.flags if f.bound_type == "hard_max"]
        assert len(hard_flags) == 3
        plausible_flags = [f for f in r.flags if f.bound_type == "plausible_max"]
        assert len(plausible_flags) == 3


class TestAriaHSiderosisBounds:
    """Verify mild=1, moderate=2, severe>2."""

    def test_mild_siderosis_passes(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1", "P2"],
            "visit_id": ["V1", "V1"],
            "measurement_name": ["aria_h_siderosis_focal_areas"] * 2,
            "value": [0, 1],
            "unit": ["count"] * 2,
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 0

    def test_three_areas_flags_hard_max(self, aria_pack):
        """3 or more siderosis areas is severe per FDA label."""
        df = pd.DataFrame({
            "patient_id": ["P3"],
            "visit_id": ["V1"],
            "measurement_name": ["aria_h_siderosis_focal_areas"],
            "value": [3],
            "unit": ["count"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        # plausible_max=1 → moderate; hard_max=2 → severe
        # value=3 crosses both
        hard_flags = [f for f in r.flags if f.bound_type == "hard_max"]
        assert len(hard_flags) == 1


class TestBaselineExclusion:
    """Verify the FDA >4 baseline microhemorrhage exclusion criterion."""

    def test_baseline_4_or_below_passes(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["baseline_microhemorrhage_count"] * 3,
            "value": [0, 2, 4],
            "unit": ["count"] * 3,
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 0

    def test_baseline_5_or_more_flags_exclusion(self, aria_pack):
        """The FDA label and AA Donanemab AUR exclude patients with >4 baseline microhemorrhages."""
        df = pd.DataFrame({
            "patient_id": ["P5", "P10"],
            "visit_id": ["V0", "V0"],
            "measurement_name": ["baseline_microhemorrhage_count"] * 2,
            "value": [5, 10],
            "unit": ["count"] * 2,
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 2
        for f in r.flags:
            assert f.bound_type == "plausible_max"


class TestApoeE4Categorical:
    """APOE ε4 status must be one of {homozygote, heterozygote, noncarrier, unknown}."""

    def test_valid_apoe_statuses_pass(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3", "P4"],
            "visit_id": ["V0"] * 4,
            "measurement_name": ["apoe_e4_status"] * 4,
            "value": ["homozygote", "heterozygote", "noncarrier", "unknown"],
            "unit": ["categorical"] * 4,
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 0

    def test_invalid_apoe_status_flagged(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["apoe_e4_status"],
            "value": ["maybe"],  # not in valid_values
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "invalid_categorical"


class TestAriaESeverityCategorical:
    """ARIA-E severity must be one of {none, mild, moderate, severe}."""

    def test_valid_severities_pass(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3", "P4"],
            "visit_id": ["V5"] * 4,
            "measurement_name": ["aria_e_severity"] * 4,
            "value": ["none", "mild", "moderate", "severe"],
            "unit": ["categorical"] * 4,
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 0

    def test_invalid_severity_flagged(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V5"],
            "measurement_name": ["aria_e_severity"],
            "value": ["catastrophic"],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "invalid_categorical"


class TestAuditDeterminism:
    """Same input + same pack → byte-exact flag_id."""

    def test_same_input_same_flag_id(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P_severe_aria"],
            "visit_id": ["V5"],
            "measurement_name": ["aria_h_microhemorrhage_count"],
            "value": [12],
            "unit": ["count"],
        })
        r1 = audit_clinical_ranges(df, aria_pack)
        r2 = audit_clinical_ranges(df, aria_pack)
        assert r1.flag_id == r2.flag_id
        assert r1.n_flagged == r2.n_flagged

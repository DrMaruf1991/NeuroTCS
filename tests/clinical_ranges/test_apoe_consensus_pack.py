"""
Behavior tests for the world-class production pack
genetics/apoe_consensus@1.0.0.

Verifies:
  - 6 canonical APOE 2-locus genotypes accepted
  - ε4 allele count bounded 0-2
  - 3-tier risk classification (noncarrier/heterozygote/homozygote)
  - rs429358 and rs7412 SNP genotype constraints
  - All bounds at citation_strength=international_consensus
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack
from neurotcs.clinical_ranges.schema import CitationStrength


@pytest.fixture(scope="module")
def apoe_pack():
    return load_rangepack("genetics/apoe_consensus")


class TestApoePackStructure:

    def test_pack_is_production(self, apoe_pack):
        from neurotcs.clinical_ranges.schema import RangePackStatus
        assert apoe_pack.rangepack.status == RangePackStatus.PRODUCTION

    def test_pack_has_six_measurements(self, apoe_pack):
        assert len(apoe_pack.rangepack.measurements) == 6

    def test_pack_covers_expected_names(self, apoe_pack):
        expected = {
            "apoe_genotype",
            "apoe_e4_allele_count",
            "apoe_e4_risk_classification",
            "apoe_e2_allele_count",
            "rs429358_genotype",
            "rs7412_genotype",
        }
        assert apoe_pack.rangepack.covered_names() == frozenset(expected)

    def test_every_bound_is_international_consensus(self, apoe_pack):
        for m in apoe_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_every_bound_has_5plus_bodies(self, apoe_pack):
        for m in apoe_pack.rangepack.measurements:
            for b in m.bounds:
                assert len(b.citation.endorsing_bodies) >= 5

    def test_anchor_is_farrer_1997(self, apoe_pack):
        assert apoe_pack.rangepack.anchor_citation.citation_pmid == "9343467"


class TestApoeGenotype:

    def test_all_six_canonical_genotypes_pass(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": [f"P{i}" for i in range(6)],
            "visit_id": ["V0"] * 6,
            "measurement_name": ["apoe_genotype"] * 6,
            "value": ["e2/e2", "e2/e3", "e2/e4", "e3/e3", "e3/e4", "e4/e4"],
            "unit": ["categorical"] * 6,
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 0

    def test_invalid_genotype_flagged(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["apoe_genotype"],
            "value": ["e1/e4"],  # ε1 is excluded from clinical reporting
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "invalid_categorical"


class TestApoeE4AlleleCount:

    def test_valid_counts_pass(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["apoe_e4_allele_count"] * 3,
            "value": [0, 1, 2],
            "unit": ["count"] * 3,
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 0

    def test_negative_flagged(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P_neg"],
            "visit_id": ["V0"],
            "measurement_name": ["apoe_e4_allele_count"],
            "value": [-1],
            "unit": ["count"],
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged >= 1
        assert any(f.bound_type == "hard_min" for f in r.flags)

    def test_above_two_flagged(self, apoe_pack):
        """A diploid genome cannot have 3 ε4 alleles."""
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["apoe_e4_allele_count"],
            "value": [3],
            "unit": ["count"],
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged >= 1
        assert any(f.bound_type == "hard_max" for f in r.flags)


class TestRiskClassification:

    def test_three_tiers_pass(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["apoe_e4_risk_classification"] * 3,
            "value": ["noncarrier", "heterozygote", "homozygote"],
            "unit": ["categorical"] * 3,
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 0

    def test_invalid_tier_flagged(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["apoe_e4_risk_classification"],
            "value": ["unknown"],  # not in this pack's set
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 1


class TestSnpGenotypes:

    def test_rs429358_valid_calls_pass(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["rs429358_genotype"] * 3,
            "value": ["T/T", "C/T", "C/C"],
            "unit": ["categorical"] * 3,
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 0

    def test_rs7412_valid_calls_pass(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["rs7412_genotype"] * 3,
            "value": ["C/C", "C/T", "T/T"],
            "unit": ["categorical"] * 3,
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 0

    def test_rs429358_invalid_call_flagged(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["rs429358_genotype"],
            "value": ["A/T"],  # impossible SNP call
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, apoe_pack)
        assert r.n_flagged == 1


class TestApoeAuditDeterminism:

    def test_same_input_same_flag_id(self, apoe_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["apoe_genotype"],
            "value": ["e4/e4"],
            "unit": ["categorical"],
        })
        r1 = audit_clinical_ranges(df, apoe_pack)
        r2 = audit_clinical_ranges(df, apoe_pack)
        assert r1.flag_id == r2.flag_id

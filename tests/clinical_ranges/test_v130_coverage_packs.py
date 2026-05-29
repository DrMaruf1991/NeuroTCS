"""
v1.30.0 coverage batch (under the revised >=2-endorser production gate).

Production:
- genetics/monogenic_ad_consensus  -- PSEN1/PSEN2/APP ACMG variant status
- csf_biomarkers/csf_ptau217_consensus -- CSF p-tau217 ANALYTICAL plausibility
Research preview (no consensus cutoff exists -> must refuse production audit):
- csf_biomarkers/csf_gfap_research_preview
- csf_biomarkers/csf_nfl_research_preview
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.audit import audit_clinical_ranges
from neurotcs.clinical_ranges.schema import RangePackStatus


# ---------- production: monogenic AD genetics ----------
def test_monogenic_is_production():
    lp = load_rangepack("genetics/monogenic_ad_consensus")
    assert lp.rangepack.status == RangePackStatus.PRODUCTION


def test_monogenic_three_adad_genes():
    lp = load_rangepack("genetics/monogenic_ad_consensus")
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {
        "psen1_mutation_status",
        "psen2_mutation_status",
        "app_mutation_status",
    }


def test_monogenic_acmg_five_tier_plus_status():
    lp = load_rangepack("genetics/monogenic_ad_consensus")
    m = lp.rangepack.measurements[0]
    assert m.measurement_kind == "categorical_set"
    assert set(m.valid_values) == {
        "pathogenic", "likely_pathogenic", "uncertain_significance",
        "likely_benign", "benign", "not_detected", "unknown",
    }


def test_monogenic_meets_revised_gate():
    lp = load_rangepack("genetics/monogenic_ad_consensus")
    for m in lp.rangepack.measurements:
        for b in m.bounds:
            assert len(b.citation.endorsing_bodies) >= 2
            assert b.citation.public_url


# ---------- production: CSF p-tau217 (analytical plausibility, NOT a cutoff) ----------
def test_csf_ptau217_is_production():
    lp = load_rangepack("csf_biomarkers/csf_ptau217_consensus")
    assert lp.rangepack.status == RangePackStatus.PRODUCTION


def test_csf_ptau217_is_plausibility_envelope_not_cutoff():
    lp = load_rangepack("csf_biomarkers/csf_ptau217_consensus")
    m = lp.rangepack.measurements[0]
    assert m.name == "csf_ptau217_pgml"
    vals = {b.bound_type.value: b.value for b in m.bounds}
    assert vals["hard_min"] == 0.0
    assert vals["hard_max"] == 2000.0  # generous analytical ceiling, not a diagnostic threshold


def test_csf_ptau217_meets_revised_gate():
    lp = load_rangepack("csf_biomarkers/csf_ptau217_consensus")
    for m in lp.rangepack.measurements:
        for b in m.bounds:
            assert len(b.citation.endorsing_bodies) >= 2
            assert b.citation.public_url


# ---------- research_preview: CSF GFAP / CSF NfL ----------
@pytest.mark.parametrize(
    "pack,meas",
    [
        ("csf_biomarkers/csf_gfap_research_preview", "csf_gfap_pgml"),
        ("csf_biomarkers/csf_nfl_research_preview", "csf_nfl_pgml"),
    ],
)
def test_csf_rp_packs_refuse_production_audit(pack, meas):
    lp = load_rangepack(pack)
    assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW
    assert lp.rangepack.measurements[0].name == meas
    with pytest.raises(ValueError, match="research_preview"):
        audit_clinical_ranges(pd.DataFrame([{meas: 100.0}]), lp)


@pytest.mark.parametrize(
    "pack",
    [
        "genetics/monogenic_ad_consensus",
        "csf_biomarkers/csf_ptau217_consensus",
        "csf_biomarkers/csf_gfap_research_preview",
        "csf_biomarkers/csf_nfl_research_preview",
    ],
)
def test_yaml_sha256_reproducible(pack):
    assert load_rangepack(pack).yaml_sha256 == load_rangepack(pack).yaml_sha256

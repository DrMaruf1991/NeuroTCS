"""
v1.31.0 coverage batch: 3 research_preview range packs + 1 architectural edit.

All ship research_preview (no consensus diagnostic cutoffs exist) and
audit_clinical_ranges() must refuse them for production audit.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.audit import audit_clinical_ranges
from neurotcs.clinical_ranges.schema import RangePackStatus


# ---------- 1. plasma p-tau231 split ----------
def test_plasma_ptau231_split_pack_is_research_preview():
    lp = load_rangepack("plasma_biomarkers/plasma_ptau231_research_preview")
    assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW
    assert [m.name for m in lp.rangepack.measurements] == ["plasma_ptau231_pgml"]


def test_plasma_ptau231_anchor_is_mila_aloma_2022():
    lp = load_rangepack("plasma_biomarkers/plasma_ptau231_research_preview")
    assert lp.rangepack.anchor_citation.citation_pmid == "35158308"


def test_csf_ptau231_no_longer_contains_plasma_measurement():
    """v1.31.0 architectural split: csf_ptau231 keeps only the CSF measurement."""
    lp = load_rangepack("csf_biomarkers/csf_ptau231_research_preview")
    names = {m.name for m in lp.rangepack.measurements}
    assert "csf_ptau231_pgml" in names
    assert "plasma_ptau231_pgml" not in names  # split out to plasma pack


# ---------- 2. AD-PRS ----------
def test_ad_prs_pack_is_research_preview():
    lp = load_rangepack("genetics/ad_prs_research_preview")
    assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW


def test_ad_prs_decile_range_is_definitional_1_to_10():
    lp = load_rangepack("genetics/ad_prs_research_preview")
    m = next(x for x in lp.rangepack.measurements if x.name == "prs_alzheimer_decile")
    vals = {b.bound_type.value: b.value for b in m.bounds}
    assert vals["hard_min"] == 1.0
    assert vals["hard_max"] == 10.0


def test_ad_prs_zscore_envelope_is_six_sd():
    lp = load_rangepack("genetics/ad_prs_research_preview")
    m = next(x for x in lp.rangepack.measurements if x.name == "prs_alzheimer_zscore")
    vals = {b.bound_type.value: b.value for b in m.bounds}
    assert vals["hard_min"] == -6.0
    assert vals["hard_max"] == 6.0


def test_ad_prs_anchor_is_bellenguez_2022():
    lp = load_rangepack("genetics/ad_prs_research_preview")
    assert lp.rangepack.anchor_citation.citation_doi == "10.1038/s41588-022-01024-z"


# ---------- 3. CSF synaptic panel ----------
def test_csf_synaptic_pack_is_research_preview():
    lp = load_rangepack("csf_biomarkers/csf_synaptic_research_preview")
    assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW


def test_csf_synaptic_panel_five_measurements():
    lp = load_rangepack("csf_biomarkers/csf_synaptic_research_preview")
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {
        "csf_snap25_pgml", "csf_neurogranin_pgml", "csf_gap43_pgml",
        "csf_ykl40_ngml", "csf_strem2_pgml",
    }


def test_csf_synaptic_anchor_is_ma_2020():
    lp = load_rangepack("csf_biomarkers/csf_synaptic_research_preview")
    assert lp.rangepack.anchor_citation.citation_doi == "10.1186/s13024-020-00374-8"


# ---------- all three refuse production audit ----------
@pytest.mark.parametrize(
    "pack,meas",
    [
        ("plasma_biomarkers/plasma_ptau231_research_preview", "plasma_ptau231_pgml"),
        ("genetics/ad_prs_research_preview", "prs_alzheimer_decile"),
        ("csf_biomarkers/csf_synaptic_research_preview", "csf_strem2_pgml"),
    ],
)
def test_research_preview_packs_refuse_production_audit(pack, meas):
    lp = load_rangepack(pack)
    with pytest.raises(ValueError, match="research_preview"):
        audit_clinical_ranges(pd.DataFrame([{meas: 1.0}]), lp)

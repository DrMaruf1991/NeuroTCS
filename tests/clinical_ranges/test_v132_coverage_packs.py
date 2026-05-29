"""v1.32.0 research_preview plausibility packs: OCT, next-gen tau PET, plasma p-tau205, ASL CBF."""
from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.audit import audit_clinical_ranges
from neurotcs.clinical_ranges.schema import RangePackStatus


# OCT
def test_oct_pack_loads_research_preview():
    lp = load_rangepack("retinal_biomarkers/oct_research_preview")
    assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {
        "rnfl_peripapillary_thickness_um", "gc_ipl_macular_thickness_um",
        "macular_total_thickness_um"}

def test_oct_anchor_is_mutlu_2018():
    lp = load_rangepack("retinal_biomarkers/oct_research_preview")
    assert lp.rangepack.anchor_citation.citation_pmid == "29946702"
    assert lp.rangepack.anchor_citation.citation_doi == "10.1001/jamaneurol.2018.1563"

# next-gen tau PET
def test_nextgen_tau_pack_three_tracers():
    lp = load_rangepack("tau_pet/next_gen_tau_research_preview")
    assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {
        "mk6240_suvr_meta_temporal", "pi2620_suvr_neocortical",
        "florzolotau_suvr_neocortical"}

def test_nextgen_tau_anchor_is_betthauser_2018():
    lp = load_rangepack("tau_pet/next_gen_tau_research_preview")
    assert lp.rangepack.anchor_citation.citation_pmid == "29777006"

# plasma p-tau205
def test_plasma_ptau205_anchor_is_teunissen_2025():
    lp = load_rangepack("plasma_biomarkers/plasma_ptau205_research_preview")
    assert lp.rangepack.anchor_citation.citation_doi == "10.1002/alz.14397"

# ASL CBF
def test_asl_cbf_pack_two_measurements():
    lp = load_rangepack("perfusion/asl_cbf_research_preview")
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {"asl_cbf_global_ml_per_100g_min","asl_cbf_gray_matter_ml_per_100g_min"}

def test_asl_anchor_is_alsop_2015_ismrm_consensus():
    lp = load_rangepack("perfusion/asl_cbf_research_preview")
    assert lp.rangepack.anchor_citation.citation_pmid == "24715426"
    assert lp.rangepack.anchor_citation.citation_doi == "10.1002/mrm.25197"

@pytest.mark.parametrize("pack,meas",[
    ("retinal_biomarkers/oct_research_preview","rnfl_peripapillary_thickness_um"),
    ("tau_pet/next_gen_tau_research_preview","mk6240_suvr_meta_temporal"),
    ("plasma_biomarkers/plasma_ptau205_research_preview","plasma_ptau205_pgml"),
    ("perfusion/asl_cbf_research_preview","asl_cbf_global_ml_per_100g_min"),
])
def test_v132_packs_refuse_production_audit(pack,meas):
    lp=load_rangepack(pack)
    with pytest.raises(ValueError, match="research_preview"):
        audit_clinical_ranges(pd.DataFrame([{meas: 1.0}]), lp)

# four new domains (no plausibility-bound out-of-range tests; just verify domain registration)
@pytest.mark.parametrize("pack,domain",[
    ("retinal_biomarkers/oct_research_preview","retinal_biomarkers"),
    ("perfusion/asl_cbf_research_preview","perfusion"),
])
def test_v132_introduces_new_domains(pack,domain):
    lp=load_rangepack(pack)
    assert lp.rangepack.domain == domain

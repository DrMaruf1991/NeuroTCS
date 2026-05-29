"""v1.33.0 research_preview plausibility packs: DTI per-tract, SV2A UCB-J PET, sleep."""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.audit import audit_clinical_ranges
from neurotcs.clinical_ranges.schema import RangePackStatus


# ---------- DTI ----------
def test_dti_pack_loads_research_preview():
    lp = load_rangepack("dti/microstructure_research_preview")
    assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {
        "fa_uncinate_fasciculus", "md_uncinate_fasciculus",
        "fa_cingulum_bundle", "md_cingulum_bundle",
        "fa_fornix", "md_fornix",
    }


def test_dti_fa_bounded_zero_to_one_definitionally():
    lp = load_rangepack("dti/microstructure_research_preview")
    for name in ["fa_uncinate_fasciculus", "fa_cingulum_bundle", "fa_fornix"]:
        m = next(x for x in lp.rangepack.measurements if x.name == name)
        vals = {b.bound_type.value: b.value for b in m.bounds}
        assert vals["hard_min"] == 0.0
        assert vals["hard_max"] == 1.0


def test_dti_md_capped_at_free_water_diffusion():
    lp = load_rangepack("dti/microstructure_research_preview")
    for name in ["md_uncinate_fasciculus", "md_cingulum_bundle", "md_fornix"]:
        m = next(x for x in lp.rangepack.measurements if x.name == name)
        vals = {b.bound_type.value: b.value for b in m.bounds}
        assert vals["hard_min"] == 0.0
        assert vals["hard_max"] == 3.0  # free water diffusion at body temperature


def test_dti_anchor_is_acosta_cabronero_2012():
    lp = load_rangepack("dti/microstructure_research_preview")
    assert lp.rangepack.anchor_citation.citation_doi == "10.1371/journal.pone.0049072"


# ---------- SV2A UCB-J ----------
def test_sv2a_pack_three_rois():
    lp = load_rangepack("synaptic_pet/sv2a_research_preview")
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {
        "ucbj_dvr_hippocampus", "ucbj_dvr_neocortical_meta", "ucbj_dvr_entorhinal_cortex",
    }


def test_sv2a_anchor_is_chen_2018_jama_neurol():
    lp = load_rangepack("synaptic_pet/sv2a_research_preview")
    assert lp.rangepack.anchor_citation.citation_doi == "10.1001/jamaneurol.2018.1836"


# ---------- sleep ----------
def test_sleep_pack_four_measurements():
    lp = load_rangepack("sleep/macro_architecture_research_preview")
    names = {m.name for m in lp.rangepack.measurements}
    assert names == {
        "nrem_sws_duration_minutes", "rem_sleep_duration_minutes",
        "ahi_events_per_hour", "sleep_efficiency_percent",
    }


def test_sleep_efficiency_definitionally_0_to_100():
    lp = load_rangepack("sleep/macro_architecture_research_preview")
    m = next(x for x in lp.rangepack.measurements if x.name == "sleep_efficiency_percent")
    vals = {b.bound_type.value: b.value for b in m.bounds}
    assert vals["hard_min"] == 0.0
    assert vals["hard_max"] == 100.0


def test_sleep_anchor_is_mander_2013_nat_neurosci():
    lp = load_rangepack("sleep/macro_architecture_research_preview")
    assert lp.rangepack.anchor_citation.citation_doi == "10.1038/nn.3324"


@pytest.mark.parametrize(
    "pack,meas",
    [
        ("dti/microstructure_research_preview", "fa_fornix"),
        ("synaptic_pet/sv2a_research_preview", "ucbj_dvr_hippocampus"),
        ("sleep/macro_architecture_research_preview", "nrem_sws_duration_minutes"),
    ],
)
def test_v133_packs_refuse_production_audit(pack, meas):
    lp = load_rangepack(pack)
    with pytest.raises(ValueError, match="research_preview"):
        audit_clinical_ranges(pd.DataFrame([{meas: 1.0}]), lp)


@pytest.mark.parametrize(
    "pack,domain",
    [
        ("dti/microstructure_research_preview", "dti"),
        ("synaptic_pet/sv2a_research_preview", "synaptic_pet"),
        ("sleep/macro_architecture_research_preview", "sleep"),
    ],
)
def test_v133_introduces_three_new_domains(pack, domain):
    lp = load_rangepack(pack)
    assert lp.rangepack.domain == domain

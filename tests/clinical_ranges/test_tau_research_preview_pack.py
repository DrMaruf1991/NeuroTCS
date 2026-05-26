"""
Tests for tau_pet/tau_research_preview rangepack (v1.15.0).

Research-grade Tau PET cutoffs from foundational cohort studies:
  - Maass 2017 meta-temporal SUVR ~1.23 (NeuroImage, PMID 28587897)
  - Schöll 2016 entorhinal SUVR ~1.20 (Neuron, PMID 26938442)
  - PET-Braak staging (0-VI ordinal)
  - CenTauR universal scale (Villemagne 2023, PMID 37953337)

NOTE: research_preview packs cannot be used directly in audit_clinical_ranges()
(by design — only production packs can audit). These tests validate
structure and bounds; downstream audit usage requires conversion to a
production pack in a future release.
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK_NAME = "tau_pet/tau_research_preview"


@pytest.fixture(scope="module")
def tau_preview_pack():
    return load_rangepack(PACK_NAME)


def test_pack_loads(tau_preview_pack):
    assert tau_preview_pack.rangepack.rangepack_id == "tau_pet/tau_research_preview@1.0.0"


def test_pack_is_research_preview(tau_preview_pack):
    assert tau_preview_pack.rangepack.status == RangePackStatus.RESEARCH_PREVIEW


def test_pack_has_six_measurements(tau_preview_pack):
    assert len(tau_preview_pack.rangepack.measurements) == 6


def test_pack_measurement_names_complete(tau_preview_pack):
    names = {m.name for m in tau_preview_pack.rangepack.measurements}
    expected = {
        "tau_pet_meta_temporal_suvr_flortaucipir",
        "tau_pet_entorhinal_suvr_flortaucipir",
        "tau_pet_temporal_neocortical_suvr_flortaucipir",
        "tau_pet_extra_temporal_suvr_flortaucipir",
        "tau_pet_braak_stage_pet",
        "tau_pet_centaur_score",
    }
    assert names == expected


def test_anchor_pmid_is_scholl_2016(tau_preview_pack):
    assert tau_preview_pack.rangepack.anchor_citation.citation_pmid == "26938442"


def test_every_bound_has_5plus_bodies(tau_preview_pack):
    for m in tau_preview_pack.rangepack.measurements:
        for b in m.bounds:
            n = len(b.citation.endorsing_bodies)
            assert n >= 5, f"{m.name}.{b.bound_type.value} has {n} endorsers"


def test_every_bound_is_derived_or_consensus(tau_preview_pack):
    for m in tau_preview_pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation_strength in (
                CitationStrength.DERIVED,
                CitationStrength.INTERNATIONAL_CONSENSUS,
            )


def test_maass_2017_meta_temporal_cutoff_123(tau_preview_pack):
    """Maass 2017 NeuroImage meta-temporal composite SUVR ~1.23."""
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_meta_temporal_suvr_flortaucipir")
    plausible_max = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert plausible_max.value == 1.23


def test_maass_2017_citation_pmid(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_meta_temporal_suvr_flortaucipir")
    plausible_max = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert plausible_max.citation.citation_pmid == "28587897"


def test_scholl_2016_entorhinal_cutoff_120(tau_preview_pack):
    """Schöll 2016 entorhinal SUVR ~1.20 (PET-Braak I)."""
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_entorhinal_suvr_flortaucipir")
    plausible_max = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert plausible_max.value == 1.20


def test_scholl_2016_citation_pmid(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_entorhinal_suvr_flortaucipir")
    plausible_max = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert plausible_max.citation.citation_pmid == "26938442"


def test_temporal_neocortical_cutoff_130(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_temporal_neocortical_suvr_flortaucipir")
    plausible_max = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert plausible_max.value == 1.30


def test_extra_temporal_cutoff_140(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_extra_temporal_suvr_flortaucipir")
    plausible_max = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert plausible_max.value == 1.40


def test_braak_stage_bounds_0_to_6(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_braak_stage_pet")
    hard_min = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    hard_max = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert hard_min.value == 0
    assert hard_max.value == 6


def test_centaur_lower_bound_negative_50(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_centaur_score")
    hard_min = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    assert hard_min.value == -50.0


def test_centaur_upper_bound_300(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_centaur_score")
    hard_max = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert hard_max.value == 300.0


def test_centaur_citation_villemagne_2023(tau_preview_pack):
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_centaur_score")
    for b in m.bounds:
        assert b.citation.citation_pmid == "37953337"


def test_adni_cohort_endorser_present(tau_preview_pack):
    """ADNI cohort must be among endorsers (foundational longitudinal data)."""
    m = next(m for m in tau_preview_pack.rangepack.measurements
             if m.name == "tau_pet_meta_temporal_suvr_flortaucipir")
    for b in m.bounds:
        assert any("ADNI" in e for e in b.citation.endorsing_bodies)


def test_pack_yaml_sha256_reproducible(tau_preview_pack):
    pack2 = load_rangepack(PACK_NAME)
    assert tau_preview_pack.yaml_sha256 == pack2.yaml_sha256

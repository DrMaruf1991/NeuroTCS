"""
Tests for neuropathology/copathology_consensus (production).

LATE-NC stage 0-3 (Nelson PT et al. Brain 2019;142(6):1503-1527, DOI
10.1093/brain/awz099) and Lewy-related alpha-synuclein category (modified
McKeith, per NIA-AA 2012 / McKeith 2017). AD co-pathology occurs in a
majority of autopsy-confirmed AD; bounds are defined consensus ranges.
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK = "neuropathology/copathology_consensus"


@pytest.fixture(scope="module")
def pack():
    return load_rangepack(PACK)


def test_is_production(pack):
    assert pack.rangepack.status == RangePackStatus.PRODUCTION


def test_measurement_names(pack):
    names = {m.name for m in pack.rangepack.measurements}
    assert names == {"late_nc_stage", "lewy_alpha_synuclein_category"}


def test_late_nc_stage_range_0_to_3(pack):
    m = next(m for m in pack.rangepack.measurements if m.name == "late_nc_stage")
    hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert (hmin.value, hmax.value) == (0, 3)


def test_late_anchor_is_nelson_2019(pack):
    assert pack.rangepack.anchor_citation.citation_doi == "10.1093/brain/awz099"


def test_lewy_category_modified_mckeith(pack):
    m = next(
        m for m in pack.rangepack.measurements
        if m.name == "lewy_alpha_synuclein_category"
    )
    assert m.measurement_kind == "categorical_set"
    assert set(m.valid_values) == {
        "none",
        "brainstem_predominant",
        "limbic_transitional",
        "neocortical",
        "amygdala_predominant",
    }


def test_every_bound_meets_production_evidence_bar(pack):
    for m in pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS
            assert len(b.citation.endorsing_bodies) >= 5
            assert b.citation.public_url


def test_yaml_sha256_reproducible(pack):
    assert pack.yaml_sha256 == load_rangepack(PACK).yaml_sha256

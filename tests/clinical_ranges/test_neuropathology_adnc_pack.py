"""
Tests for neuropathology/adnc_abc_consensus (production).

NIA-AA 2012 'ABC' score and integrated ADNC level (Hyman BT et al.
Alzheimer's & Dementia 2012;8(1):1-13, PMID 22265587, DOI
10.1016/j.jalz.2011.10.007), integrating Thal phase (0-5), CERAD neuritic
plaque score (0-3), and Braak NFT stage (0-VI). The autopsy gold standard
the biological staging rule packs are grounded in. Bounds are the defined
consensus scale ranges, not derived thresholds.
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK = "neuropathology/adnc_abc_consensus"


@pytest.fixture(scope="module")
def pack():
    return load_rangepack(PACK)


def test_is_production(pack):
    assert pack.rangepack.status == RangePackStatus.PRODUCTION


def test_domain_is_neuropathology(pack):
    assert pack.rangepack.domain == "neuropathology"


def test_measurement_names(pack):
    names = {m.name for m in pack.rangepack.measurements}
    assert names == {
        "thal_amyloid_phase",
        "cerad_neuritic_plaque_score",
        "braak_nft_stage",
        "adnc_level",
    }


def test_anchor_is_hyman_2012(pack):
    a = pack.rangepack.anchor_citation
    assert a.citation_pmid == "22265587"
    assert a.citation_doi == "10.1016/j.jalz.2011.10.007"


@pytest.mark.parametrize(
    "name,lo,hi",
    [
        ("thal_amyloid_phase", 0, 5),
        ("cerad_neuritic_plaque_score", 0, 3),
        ("braak_nft_stage", 0, 6),
    ],
)
def test_ordinal_scale_ranges_are_definitional(pack, name, lo, hi):
    m = next(m for m in pack.rangepack.measurements if m.name == name)
    hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert hmin.value == lo
    assert hmax.value == hi


def test_adnc_level_is_categorical_with_four_values(pack):
    m = next(m for m in pack.rangepack.measurements if m.name == "adnc_level")
    assert m.measurement_kind == "categorical_set"
    assert set(m.valid_values) == {"none", "low", "intermediate", "high"}


def test_every_bound_meets_production_evidence_bar(pack):
    for m in pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS
            assert len(b.citation.endorsing_bodies) >= 5
            assert b.citation.public_url


def test_yaml_sha256_reproducible(pack):
    assert pack.yaml_sha256 == load_rangepack(PACK).yaml_sha256

"""
Tests for cognitive_scales/functional_affective_consensus (production).

Pfeffer Functional Activities Questionnaire (FAQ total 0-30; Pfeffer RI et
al. J Gerontol 1982;37(3):323-329, DOI 10.1093/geronj/37.3.323) and the
15-item Geriatric Depression Scale (GDS-15 total 0-15; Sheikh & Yesavage
1986, DOI 10.1300/J018v05n01_09). Defined-range instruments universal to
ADNI/NACC.
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK = "cognitive_scales/functional_affective_consensus"


@pytest.fixture(scope="module")
def pack():
    return load_rangepack(PACK)


def test_is_production(pack):
    assert pack.rangepack.status == RangePackStatus.PRODUCTION


def test_measurement_names(pack):
    names = {m.name for m in pack.rangepack.measurements}
    assert names == {"faq_total", "gds15_total"}


def test_faq_range_0_to_30(pack):
    m = next(m for m in pack.rangepack.measurements if m.name == "faq_total")
    hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert (hmin.value, hmax.value) == (0, 30)


def test_gds15_range_0_to_15(pack):
    m = next(m for m in pack.rangepack.measurements if m.name == "gds15_total")
    hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert (hmin.value, hmax.value) == (0, 15)


def test_faq_anchor_is_pfeffer_1982(pack):
    assert pack.rangepack.anchor_citation.citation_doi == "10.1093/geronj/37.3.323"


def test_gds15_cites_sheikh_yesavage_1986(pack):
    m = next(m for m in pack.rangepack.measurements if m.name == "gds15_total")
    for b in m.bounds:
        assert b.citation.citation_doi == "10.1300/J018v05n01_09"


def test_every_bound_meets_production_evidence_bar(pack):
    for m in pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS
            assert len(b.citation.endorsing_bodies) >= 5
            assert b.citation.public_url


def test_yaml_sha256_reproducible(pack):
    assert pack.yaml_sha256 == load_rangepack(PACK).yaml_sha256

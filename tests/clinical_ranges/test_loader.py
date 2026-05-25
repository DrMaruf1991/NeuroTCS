"""Tests for neurotcs.clinical_ranges.loader."""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges.loader import (
    LoadedRangePack,
    list_rangepacks,
    load_rangepack,
)
from neurotcs.clinical_ranges.schema import RangePack, RangePackStatus

# v1.10.0-rc1: the only pack shipping at status=production is ad/aria_safety,
# which meets the world-class international-consensus citation-lock bar.
# The 6 v1.10.0-draft packs are demoted to research_preview pending
# their own citation-trace upgrade to international_consensus standard.
EXPECTED_PRODUCTION_PACKS = {
    "ad/aria_safety",
}

EXPECTED_RESEARCH_PREVIEW_PACKS = {
    "vital_signs/standard",
    "csf_biomarkers/aa_2024",
    "plasma_biomarkers/aa_2024",
    "mri_volumetrics/freesurfer",
    "pet_amyloid/centiloid",
    "genetics/apoe_valid_genotypes",
}

# All packs on disk (production + research_preview)
EXPECTED_PACKS = EXPECTED_PRODUCTION_PACKS | EXPECTED_RESEARCH_PREVIEW_PACKS


class TestLoadRangepack:
    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_each_production_pack_loads(self, name: str):
        """Production packs must load and have production status."""
        lp = load_rangepack(name)
        assert isinstance(lp, LoadedRangePack)
        assert isinstance(lp.rangepack, RangePack)
        assert lp.status == RangePackStatus.PRODUCTION
        assert len(lp.canonical_sha256) == 64
        assert all(c in "0123456789abcdef" for c in lp.canonical_sha256)

    @pytest.mark.parametrize("name", sorted(EXPECTED_RESEARCH_PREVIEW_PACKS))
    def test_each_research_preview_pack_loads(self, name: str):
        """Research preview packs must load with research_preview status."""
        lp = load_rangepack(name)
        assert isinstance(lp, LoadedRangePack)
        assert lp.status == RangePackStatus.RESEARCH_PREVIEW

    @pytest.mark.parametrize("name", sorted(EXPECTED_PACKS))
    def test_each_pack_has_anchor_citation(self, name: str):
        lp = load_rangepack(name)
        anchor = lp.rangepack.anchor_citation
        assert (anchor.citation_pmid or anchor.citation_doi or anchor.pmid_pending)
        assert len(anchor.citation_text) >= 20

    @pytest.mark.parametrize("name", sorted(EXPECTED_PACKS))
    def test_each_pack_has_measurements(self, name: str):
        lp = load_rangepack(name)
        assert len(lp.rangepack.measurements) >= 1

    @pytest.mark.parametrize("name", sorted(EXPECTED_PACKS))
    def test_each_measurement_has_per_bound_citation(self, name: str):
        """Per-bound citations are non-negotiable for audit-trail integrity."""
        lp = load_rangepack(name)
        for m in lp.rangepack.measurements:
            for b in m.bounds:
                assert b.citation is not None
                assert b.guideline_section
                assert (
                    b.citation.citation_pmid
                    or b.citation.citation_doi
                    or b.citation.pmid_pending
                )

    def test_load_nonexistent_pack_raises(self):
        with pytest.raises(FileNotFoundError):
            load_rangepack("does_not_exist/nope")


class TestProductionPackWorldClassGate:
    """The world-class evidence bar: every production pack must have every
    bound at citation_strength=international_consensus, with ≥5 endorsing
    bodies and a public URL per bound."""

    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_every_bound_is_international_consensus(self, name: str):
        from neurotcs.clinical_ranges.schema import CitationStrength
        lp = load_rangepack(name)
        for m in lp.rangepack.measurements:
            for b in m.bounds:
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS, (
                    f"Production pack {name} measurement {m.name} bound "
                    f"{b.bound_type.value} has citation_strength="
                    f"{b.citation_strength.value!r}, expected international_consensus."
                )

    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_every_bound_has_5plus_endorsing_bodies(self, name: str):
        lp = load_rangepack(name)
        for m in lp.rangepack.measurements:
            for b in m.bounds:
                assert len(b.citation.endorsing_bodies) >= 5, (
                    f"Production pack {name} measurement {m.name} bound "
                    f"{b.bound_type.value} has only "
                    f"{len(b.citation.endorsing_bodies)} endorsing bodies; "
                    f"world-class standard requires ≥5."
                )

    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_every_bound_has_public_url(self, name: str):
        lp = load_rangepack(name)
        for m in lp.rangepack.measurements:
            for b in m.bounds:
                assert b.citation.public_url, (
                    f"Production pack {name} measurement {m.name} bound "
                    f"{b.bound_type.value} has no public_url; world-class "
                    f"standard requires every bound to be independently "
                    f"verifiable via a public URL."
                )

    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_anchor_citation_has_public_url(self, name: str):
        lp = load_rangepack(name)
        assert lp.rangepack.anchor_citation.public_url, (
            f"Production pack {name} anchor_citation has no public_url."
        )


class TestListRangepacks:
    def test_lists_all_expected_packs(self):
        packs = list_rangepacks()
        names = {p["name"] for p in packs}
        assert EXPECTED_PACKS.issubset(names)

    def test_production_packs_are_production(self):
        packs = list_rangepacks()
        for p in packs:
            if p["name"] in EXPECTED_PRODUCTION_PACKS:
                assert p["status"] == "production"

    def test_research_preview_packs_are_research_preview(self):
        packs = list_rangepacks()
        for p in packs:
            if p["name"] in EXPECTED_RESEARCH_PREVIEW_PACKS:
                assert p["status"] == "research_preview"

    def test_no_invalid_packs(self):
        packs = list_rangepacks()
        invalid = [p for p in packs if p["status"] == "INVALID"]
        assert invalid == [], f"Invalid packs found: {invalid}"

    def test_pack_metadata_present(self):
        packs = list_rangepacks()
        for p in packs:
            if p["status"] != "INVALID":
                assert "schema_version" in p
                assert "pack_version" in p
                assert "n_measurements" in p
                assert "sha256" in p
                assert len(p["sha256"]) == 16  # truncated


class TestLoaderDeterminism:
    def test_same_pack_same_sha_across_loads(self):
        """Repeated loads of the same pack file produce identical SHAs."""
        lp1 = load_rangepack("ad/aria_safety")
        lp2 = load_rangepack("ad/aria_safety")
        assert lp1.canonical_sha256 == lp2.canonical_sha256

    def test_different_packs_different_shas(self):
        sha_set = set()
        for name in EXPECTED_PACKS:
            sha_set.add(load_rangepack(name).canonical_sha256)
        assert len(sha_set) == len(EXPECTED_PACKS), \
            "Distinct packs should produce distinct SHAs"

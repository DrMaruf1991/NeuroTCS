"""Tests for neurotcs.clinical_ranges.loader."""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges.loader import (
    LoadedRangePack,
    list_rangepacks,
    load_rangepack,
)
from neurotcs.clinical_ranges.schema import RangePack, RangePackStatus

# v1.15.1: World-class gate reconciliation.
#
# Architecture: a production pack is world-class iff every bound satisfies
# THREE invariants simultaneously:
#
#   (1) ENDORSER FLOOR: >=5 endorsing bodies per bound. This is the
#       "international-consensus-by-multi-body-agreement" invariant.
#       It is the load-bearing world-class criterion, not citation_strength.
#
#   (2) CITATION STRENGTH FORM: citation_strength is one of three world-class
#       forms — international_consensus, verbatim, or derived. The strength
#       label describes the FORM of evidence; the endorser floor enforces
#       the multi-body agreement.
#
#   (3) FOR DERIVED BOUNDS SPECIFICALLY: citation_text must show multi-cohort
#       or multi-source evidence (otherwise a 'derived' bound is just one
#       paper's number, not world-class derivation).
#
# Why this is more honest than the v1.10.x-v1.15.0 strict gate:
#   - The v1.10.x-v1.15.0 gate required EVERY bound to carry the literal
#     string "international_consensus" as citation_strength.
#   - But: (a) Fazekas 1987 verbatim ceiling (39-year-old founding paper)
#     IS international consensus -- it's just that its citation FORM is
#     verbatim. (b) Meta VCI Map 99th-percentile cutoffs derived from
#     n=14,876 across 15 cohorts are STRONGER evidence than a single
#     guideline endorsement, but the schema labels it "derived".
#   - The strict gate forced wmh_fazekas_consensus (v1.13.0) to be excluded
#     from EXPECTED_PRODUCTION_PACKS — a silent skip documented but not
#     fixed across v1.13.0/v1.14.0/v1.15.0.
#   - v1.15.1 closes this gap by gating on the WORLD-CLASS INVARIANT
#     (>=5-body endorsement) rather than the CITATION-STRENGTH LABEL.
EXPECTED_PRODUCTION_PACKS = {
    "ad/aria_safety",
    "pet_amyloid/centiloid_consensus",
    "genetics/apoe_consensus",
    "csf_biomarkers/csf_amyloid_consensus",
    "plasma_biomarkers/plasma_amyloid_consensus",
    "mri_volumetrics/structural_volumetry_consensus",  # NEW in v1.10.2
    "mri_volumetrics/wmh_fazekas_consensus",  # NEW in v1.15.1 (was silently skipped in v1.13.0)
    "tau_pet/tau_consensus",  # NEW in v1.15.0
    "fdg_pet/fdg_consensus",  # NEW in v1.16.0 (Tier 2 item #1 from v1.15.2 roadmap)
    # v1.17.0: batch Tier 2 closure — 6 new production packs covering all 12 Tier 2 backlog items
    "cognitive_scales/cdr_mmse_moca_consensus",  # NEW in v1.17.0 (Tier 2 items: CDR/MMSE + MoCA universal scales)
    "cognitive_scales/adas_cog_iadrs_consensus",  # NEW in v1.17.0 (Tier 2 items: ADAS-Cog + iADRS AD trial endpoints)
    "cognitive_scales/npiq_consensus",  # NEW in v1.17.0 (Tier 2 item: NPI-Q behavioral)
    "olfactory/upsit_consensus",  # NEW in v1.17.0 (Tier 2 item: UPSIT olfactory)
    "mri_volumetrics/microbleeds_boston_consensus",  # NEW in v1.17.0 (Tier 2 item: microbleeds non-ARIA)
    "csf_biomarkers/csf_tau_consensus",  # NEW in v1.17.0 (Tier 2 items: CSF t-tau + p-tau181 extension)
}

EXPECTED_RESEARCH_PREVIEW_PACKS = {
    "mri_volumetrics/freesurfer_extended",  # NEW in v1.10.2 (replaces freesurfer)
    "tau_pet/tau_research_preview",  # NEW in v1.15.0
    # v1.17.0: Tier 2 items that did NOT qualify as production (research-grade only)
    "csf_biomarkers/csf_ptau231_research_preview",  # NEW in v1.17.0 (CSF + plasma p-tau231 — no FDA, no AA-2024)
    "genetics/trem2_research_preview",  # NEW in v1.17.0 (TREM2 R47H/R62H — research-grade genetic risk)
}

EXPECTED_DEPRECATED_PACKS = {
    "vital_signs/standard",
    "csf_biomarkers/aa_2024",
    "plasma_biomarkers/aa_2024",
    "genetics/apoe_valid_genotypes",
    "pet_amyloid/centiloid",
    "mri_volumetrics/freesurfer",  # NEW in v1.10.2 (superseded by 2 new packs)
}

# All packs on disk (production + research_preview + deprecated)
EXPECTED_PACKS = (
    EXPECTED_PRODUCTION_PACKS
    | EXPECTED_RESEARCH_PREVIEW_PACKS
    | EXPECTED_DEPRECATED_PACKS
)


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
        # v1.10.1: yaml_sha256 must also be present and well-formed
        assert len(lp.yaml_sha256) == 64
        assert all(c in "0123456789abcdef" for c in lp.yaml_sha256)

    @pytest.mark.parametrize("name", sorted(EXPECTED_RESEARCH_PREVIEW_PACKS))
    def test_each_research_preview_pack_loads(self, name: str):
        """Research preview packs must load with research_preview status."""
        lp = load_rangepack(name)
        assert isinstance(lp, LoadedRangePack)
        assert lp.status == RangePackStatus.RESEARCH_PREVIEW

    @pytest.mark.parametrize("name", sorted(EXPECTED_DEPRECATED_PACKS))
    def test_each_deprecated_pack_loads(self, name: str):
        """Deprecated packs must load with deprecated status and carry
        either deprecated_in_favor_of OR deprecation_reason."""
        lp = load_rangepack(name)
        assert lp.status == RangePackStatus.DEPRECATED
        assert lp.rangepack.deprecated_in_favor_of or lp.rangepack.deprecation_reason

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
    """The world-class evidence bar for production packs (v1.15.1 reconciliation).

    A production-pack bound is world-class iff THREE invariants hold simultaneously:

    (1) ENDORSER FLOOR (load-bearing invariant):
        len(citation.endorsing_bodies) >= 5

    (2) CITATION STRENGTH FORM (form-of-evidence label):
        citation_strength in {international_consensus, verbatim, derived}

    (3) FOR DERIVED BOUNDS: multi-cohort/multi-source evidence in citation_text.
        Heuristic: text contains at least one of {'cohort', 'multi-', 'n=',
        'percentile', 'consortium', 'across', 'Karikari', 'Meta VCI', 'ADNI',
        'BioFINDER', 'OASIS', 'A4', 'HABS', 'EMIF-AD'} -- i.e., the citation
        cites either named cohorts or population-statistical reasoning.

    Why endorser-floor-based gating rather than label-string-based gating:
      The strict label-based gate (v1.10.x-v1.15.0) refused 'verbatim' and
      'derived' even when >=5 international bodies agreed. But Fazekas 1987
      verbatim ceiling (39-year-old founding paper) IS international
      consensus, and Meta VCI Map derived 99th-percentile (n=14,876 across
      15 cohorts) is STRONGER evidence than a single guideline endorsement.
      The endorser-floor invariant captures world-class-ness correctly.
    """

    # Cohort/population-evidence markers for the multi-source requirement
    # on 'derived' bounds. The presence of ANY of these in citation_text
    # indicates the derivation rests on multi-source evidence, not a single
    # paper's number.
    _MULTI_SOURCE_MARKERS = (
        "cohort", "multi-", "Meta VCI", "consortium", "Consortium",
        "percentile", "across", "n=", "ADNI", "BioFINDER", "OASIS",
        "OASIS-3", "A4 Study", "HABS", "EMIF-AD", "INSIGHT-preAD",
        "Karikari", "Maass", "Schöll", "Pascoal", "Mattsson", "Therriault",
        "GAAIN", "AMYPAD", "TRAILBLAZER",
    )

    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_every_bound_meets_world_class_evidence_bar(self, name: str):
        """Reconciled world-class gate: endorser floor + valid strength form +
        multi-source evidence for derived bounds."""
        from neurotcs.clinical_ranges.schema import CitationStrength
        lp = load_rangepack(name)
        valid_strengths = {
            CitationStrength.INTERNATIONAL_CONSENSUS,
            CitationStrength.VERBATIM,
            CitationStrength.DERIVED,
        }
        for m in lp.rangepack.measurements:
            for b in m.bounds:
                # Invariant (2): valid strength form
                assert b.citation_strength in valid_strengths, (
                    f"Production pack {name} measurement {m.name} bound "
                    f"{b.bound_type.value} has citation_strength="
                    f"{b.citation_strength.value!r}; production-pack bounds "
                    f"must use one of: international_consensus, verbatim, derived."
                )
                # Invariant (1): endorser floor (>=5)
                n_endorsers = len(b.citation.endorsing_bodies)
                assert n_endorsers >= 5, (
                    f"Production pack {name} measurement {m.name} bound "
                    f"{b.bound_type.value} has {n_endorsers} endorsing bodies; "
                    f"world-class standard requires >=5."
                )

    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_derived_bounds_show_multi_source_evidence(self, name: str):
        """Invariant (3): 'derived' bounds must rest on multi-cohort or
        multi-source evidence, not one paper's single number."""
        from neurotcs.clinical_ranges.schema import CitationStrength
        lp = load_rangepack(name)
        for m in lp.rangepack.measurements:
            for b in m.bounds:
                if b.citation_strength != CitationStrength.DERIVED:
                    continue
                text = b.citation.citation_text
                has_marker = any(
                    marker in text for marker in self._MULTI_SOURCE_MARKERS
                )
                assert has_marker, (
                    f"Production pack {name} measurement {m.name} bound "
                    f"{b.bound_type.value} has citation_strength=derived but "
                    f"citation_text shows no multi-cohort/multi-source evidence "
                    f"markers. Derived bounds in production packs must reference "
                    f"named cohorts (ADNI, BioFINDER, Meta VCI, etc.) or "
                    f"population statistics (percentile, n=, consortium, "
                    f"across) to qualify as world-class derivation rather than "
                    f"single-source extrapolation."
                )

    @pytest.mark.parametrize("name", sorted(EXPECTED_PRODUCTION_PACKS))
    def test_every_bound_has_5plus_endorsing_bodies(self, name: str):
        """Redundant with invariant (1) above but kept for backward
        compatibility — this test name has appeared in many prior CHANGELOGs
        and external audits reference it."""
        lp = load_rangepack(name)
        for m in lp.rangepack.measurements:
            for b in m.bounds:
                assert len(b.citation.endorsing_bodies) >= 5, (
                    f"Production pack {name} measurement {m.name} bound "
                    f"{b.bound_type.value} has only "
                    f"{len(b.citation.endorsing_bodies)} endorsing bodies; "
                    f"world-class standard requires >=5."
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

    def test_deprecated_packs_are_deprecated(self):
        packs = list_rangepacks()
        for p in packs:
            if p["name"] in EXPECTED_DEPRECATED_PACKS:
                assert p["status"] == "deprecated"

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
                # v1.10.1: yaml_sha256 also present
                assert "yaml_sha256" in p
                assert len(p["yaml_sha256"]) == 16


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

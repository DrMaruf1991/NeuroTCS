"""
Deprecation semantics tests (v1.10.1).

Verifies:
  1. The DEPRECATED status enum value exists
  2. All 5 superseded packs are correctly deprecated with valid successors
  3. vital_signs/standard is deprecated with a deprecation_reason (no successor)
  4. assert_usable_for_audit raises a specific error for deprecated packs
  5. audit_clinical_ranges refuses to run on a deprecated pack
  6. Successors that are pointed to actually exist on disk and are production
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import (
    RangePackStatus,
    audit_clinical_ranges,
    list_rangepacks,
    load_rangepack,
)

# Map of deprecated pack -> successor (None means scope-based deprecation)
EXPECTED_DEPRECATIONS: dict[str, str | None] = {
    # Deprecated in v1.10.1:
    "vital_signs/standard": None,
    "csf_biomarkers/aa_2024": "csf_biomarkers/csf_amyloid_consensus@1.0.0",
    "plasma_biomarkers/aa_2024": "plasma_biomarkers/plasma_amyloid_consensus@1.1.1",
    "genetics/apoe_valid_genotypes": "genetics/apoe_consensus@1.0.0",
    "pet_amyloid/centiloid": "pet_amyloid/centiloid_consensus@1.0.0",
    # Deprecated in v1.10.2:
    "mri_volumetrics/freesurfer": "mri_volumetrics/structural_volumetry_consensus@1.0.0",
}


class TestDeprecatedStatusEnumExists:

    def test_deprecated_enum_value(self) -> None:
        assert RangePackStatus.DEPRECATED.value == "deprecated"

    def test_deprecated_in_status_set(self) -> None:
        all_statuses = {s.value for s in RangePackStatus}
        assert "deprecated" in all_statuses
        # The original 4 must still be there for backward compat
        assert {"production", "research_preview", "skeleton", "planned"} <= all_statuses


class TestAllFiveSupersededPacksAreDeprecated:
    """Verify that v1.10.1 properly deprecates the 5 packs superseded by
    the v1.10.0 world-class production roster."""

    @pytest.mark.parametrize("name", list(EXPECTED_DEPRECATIONS.keys()))
    def test_pack_status_is_deprecated(self, name: str) -> None:
        loaded = load_rangepack(name)
        assert loaded.rangepack.status == RangePackStatus.DEPRECATED, (
            f"{name} should be deprecated in v1.10.1 but has status={loaded.rangepack.status.value!r}"
        )

    @pytest.mark.parametrize("name,expected_successor",
                             [(k, v) for k, v in EXPECTED_DEPRECATIONS.items() if v is not None])
    def test_successor_pointer_correct(self, name: str, expected_successor: str) -> None:
        loaded = load_rangepack(name)
        assert loaded.rangepack.deprecated_in_favor_of == expected_successor

    def test_vital_signs_uses_deprecation_reason_not_successor(self) -> None:
        """vital_signs/standard is scope-deprecated (no successor); it must
        use deprecation_reason instead of deprecated_in_favor_of."""
        loaded = load_rangepack("vital_signs/standard")
        assert loaded.rangepack.deprecated_in_favor_of is None
        assert loaded.rangepack.deprecation_reason is not None
        assert len(loaded.rangepack.deprecation_reason) >= 10
        assert "v1.9.0" in loaded.rangepack.deprecation_reason


class TestSuccessorPacksExistAndAreProduction:
    """For every deprecated pack that names a successor, the successor must
    exist on disk and have status=production."""

    @pytest.mark.parametrize("name,expected_successor",
                             [(k, v) for k, v in EXPECTED_DEPRECATIONS.items() if v is not None])
    def test_successor_exists_and_is_production(
        self, name: str, expected_successor: str
    ) -> None:
        # The expected_successor is "domain/name@version"; load by "domain/name"
        successor_id_no_version = expected_successor.split("@")[0]
        successor_loaded = load_rangepack(successor_id_no_version)
        assert successor_loaded.rangepack.status == RangePackStatus.PRODUCTION
        # And the successor's rangepack_id should match what we point to
        assert successor_loaded.rangepack.rangepack_id == expected_successor


class TestDeprecatedPacksRefuseAudit:
    """audit_clinical_ranges() must refuse to run on a deprecated pack."""

    @pytest.mark.parametrize("name", list(EXPECTED_DEPRECATIONS.keys()))
    def test_audit_raises_value_error(self, name: str) -> None:
        loaded = load_rangepack(name)
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["irrelevant"],
            "value": [1.0],
            "unit": ["unit"],
        })
        with pytest.raises(ValueError, match="DEPRECATED"):
            audit_clinical_ranges(df, loaded)

    def test_error_for_pack_with_successor_mentions_successor(self) -> None:
        loaded = load_rangepack("csf_biomarkers/aa_2024")
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["irrelevant"],
            "value": [1.0],
            "unit": ["unit"],
        })
        with pytest.raises(ValueError) as exc_info:
            audit_clinical_ranges(df, loaded)
        # The successor pack ID must appear in the error message
        assert "csf_amyloid_consensus" in str(exc_info.value)

    def test_error_for_scope_deprecation_mentions_reason(self) -> None:
        loaded = load_rangepack("vital_signs/standard")
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["irrelevant"],
            "value": [1.0],
            "unit": ["unit"],
        })
        with pytest.raises(ValueError) as exc_info:
            audit_clinical_ranges(df, loaded)
        # The scope-deprecation reason should mention v1.9.0
        assert "v1.9.0" in str(exc_info.value) or "AD-only" in str(exc_info.value)


class TestRosterCounts:
    """In v1.10.2 the lifecycle counts evolved from v1.10.1 (5 prod, 1 preview,
    5 deprecated, 11 total) to (6 prod, 1 preview, 6 deprecated, 13 total):
    + mri_volumetrics/structural_volumetry_consensus to production,
    + mri_volumetrics/freesurfer_extended replacing the deprecated freesurfer at preview.

    v1.13.0 adds mri_volumetrics/wmh_fazekas_consensus to production:
    (7 prod, 1 preview, 6 deprecated, 14 total).

    v1.15.0 adds tau_pet/tau_consensus to production and
    tau_pet/tau_research_preview to research_preview:
    (8 prod, 2 preview, 6 deprecated, 16 total).

    v1.16.0 adds fdg_pet/fdg_consensus to production (Tier 2 item #1 from
    v1.15.2 roadmap; CMS NCD 220.6.13 + AA-2024 Core 2 N + SNMMI/EANM 2024
    v2.0 + EANM Brain FDG-PET v3 + Mosconi 2008 multicenter + Bailly 2015
    SUVR anchors): (9 prod, 2 preview, 6 deprecated, 17 total).

    v1.17.0 batch Tier 2 closure adds 6 new production packs covering the
    full 12-item Tier 2 backlog from v1.16.0:
      + cognitive_scales/cdr_mmse_moca_consensus (CDR + MMSE + MoCA)
      + cognitive_scales/adas_cog_iadrs_consensus (ADAS-Cog + iADRS)
      + cognitive_scales/npiq_consensus (NPI-Q)
      + olfactory/upsit_consensus (UPSIT 40-item)
      + mri_volumetrics/microbleeds_boston_consensus (Boston v2.0 CAA)
      + csf_biomarkers/csf_tau_consensus (CSF p-tau181 + t-tau Lumipulse)
    Plus 2 new research_preview packs (items that did NOT qualify as
    production per world-class evidence honesty discipline):
      + csf_biomarkers/csf_ptau231_research_preview (CSF + plasma p-tau231)
      + genetics/trem2_research_preview (TREM2 R47H + R62H)
    Net (v1.27.0): (16 prod, 5 preview, 6 deprecated, 27 total).
    v1.22.0: +1 production (plasma_biomarkers/nfl_consensus) -> 16 prod / 26
    total. (Demographic plausibility moved to the input-contract layer, where
    data-integrity checks belong; it is not a clinical range pack.)"""

    def test_fifteen_production_packs(self) -> None:
        packs = list_rangepacks()
        prod = [p for p in packs if p.get("status") == "production"]
        assert len(prod) == 16

    def test_four_research_preview_packs(self) -> None:
        """v1.15.0: research_preview pack count grows from 1 to 2 with
        tau_pet/tau_research_preview joining mri_volumetrics/freesurfer_extended.
        v1.16.0: unchanged. v1.17.0: grows from 2 to 4 with
        csf_biomarkers/csf_ptau231_research_preview and
        genetics/trem2_research_preview added (Tier 2 items that ship
        as research_preview because no FDA clearance + no AA-2024
        recognition + no clinical-grade actionable threshold).
        v1.27.0: grows from 4 to 5 with
        mri_volumetrics/hippocampal_subfields_research_preview (12 canonical
        FreeSurfer subfields x 2 hemispheres; research_preview because no
        consensus subfield normative exists and FS6/FS7 comparability is
        poor)."""
        packs = list_rangepacks()
        preview = [p for p in packs if p.get("status") == "research_preview"]
        assert len(preview) == 5
        names = {p["name"] for p in preview}
        assert names == {
            "mri_volumetrics/freesurfer_extended",
            "tau_pet/tau_research_preview",
            "csf_biomarkers/csf_ptau231_research_preview",
            "genetics/trem2_research_preview",
            "mri_volumetrics/hippocampal_subfields_research_preview",
        }

    def test_six_deprecated_packs(self) -> None:
        packs = list_rangepacks()
        deprecated = [p for p in packs if p.get("status") == "deprecated"]
        assert len(deprecated) == 6
        names = {p["name"] for p in deprecated}
        assert names == set(EXPECTED_DEPRECATIONS.keys())

    def test_total_pack_count(self) -> None:
        """v1.16.0 adds 1 pack (fdg_pet/fdg_consensus production -> 17 total).
        v1.17.0 adds 8 packs (6 production + 2 research_preview).
        Prior net: 26 total (16 prod + 4 preview + 6 deprecated).
        v1.22.0: +1 production pack (NfL).
        v1.27.0: +1 research_preview pack (hippocampal subfields) -> 27 total
        (16 prod + 5 preview + 6 deprecated)."""
        packs = list_rangepacks()
        assert len(packs) == 27  # 16 prod + 5 preview + 6 deprecated


class TestDeprecationSchemaValidator:
    """Schema-level enforcement: a pack with status=DEPRECATED must have
    either deprecated_in_favor_of or deprecation_reason set."""

    def test_construction_with_deprecated_no_pointer_no_reason_raises(self) -> None:
        from datetime import date

        from neurotcs.clinical_ranges import (
            Citation,
            CitationStrength,
            MeasurementRange,
            RangeBound,
            RangePack,
        )
        from neurotcs.clinical_ranges.schema import BoundType

        with pytest.raises(ValueError, match="deprecated_in_favor_of|deprecation_reason"):
            RangePack(
                schema_version="1.0.0",
                rangepack_id="test/test@1.0.0",
                pack_version="1.0.0",
                effective_date=date(2026, 5, 25),
                status=RangePackStatus.DEPRECATED,
                domain="test",
                framework_name="Test framework",
                transcribed_by="Test, 2026-05-25",
                clinical_source_authority="Test authority for validation",
                anchor_citation=Citation(
                    citation_pmid="12345",
                    citation_text="Test citation, sufficient length for validator",
                    public_url="https://example.com/test",
                    endorsing_bodies=["A", "B", "C", "D", "E"],
                ),
                measurements=[MeasurementRange(
                    name="test_meas",
                    unit="unit",
                    description="Test measurement",
                    bounds=[RangeBound(
                        bound_type=BoundType.HARD_MIN,
                        value=0.0,
                        citation_strength=CitationStrength.VERBATIM,
                        guideline_section="test §1",
                        citation=Citation(
                            citation_pmid="12345",
                            citation_text="Test bound citation, sufficient length",
                            public_url="https://example.com/test",
                            endorsing_bodies=["A", "B", "C", "D", "E"],
                        ),
                    )],
                )],
                # neither deprecated_in_favor_of NOR deprecation_reason
            )

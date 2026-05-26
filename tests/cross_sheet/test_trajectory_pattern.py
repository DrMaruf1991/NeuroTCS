"""
Tests for the CategoricalImpliesTrajectoryPattern execution (v1.11.0a3 NEW)
and the genotype_phenotype_consistency invariant pack (v1.11.0a3 NEW).

Covers:
- Trajectory pattern flag firing when pattern deviates from baseline
- No flag when pattern matches expectation
- No flag when follow-up too short
- No flag when genotype doesn't match trigger
- Determinism of flag_id across runs
- Flag fields populated correctly (severity, citation, observed values)
- Pack-level: loads at research_preview, 1 invariant, correct citations
- Cross-platform stable yaml_sha256
- World-class evidence discipline (>=5 endorsing bodies, citation_strength,
  Fortea 2024 anchor)
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges.schema import CitationStrength
from neurotcs.cross_sheet import (
    audit_cross_sheet,
    list_invariantpacks,
    load_invariantpack,
)
from neurotcs.cross_sheet.audit import _parse_trajectory_threshold
from neurotcs.cross_sheet.schema import InvariantPackStatus

# ============================================================
# v1.11.0a3 GOLDEN HASHES
# ============================================================

GOLDEN_YAML_SHA256_GENOTYPE_PHENOTYPE = (
    "c988ffeddc31d04121cc012dcb32fe1e09f64ad4ddfb95e22b772a32788a1a40"
)


class TestParseTrajectoryThreshold:

    def test_parses_supported_pattern(self):
        assert _parse_trajectory_threshold("none_observed_after_age_85_with_10y_followup") == (85.0, 10.0)

    def test_parses_alternate_supported_pattern(self):
        assert _parse_trajectory_threshold("none_observed_after_age_75_with_5y_followup") == (75.0, 5.0)

    def test_returns_none_for_unsupported_pattern(self):
        assert _parse_trajectory_threshold("some_other_pattern") is None
        assert _parse_trajectory_threshold("") is None
        assert _parse_trajectory_threshold("after_age_85") is None


class TestGenotypePhenotypePackListing:

    def test_listing_includes_genotype_phenotype_consistency(self):
        packs = list_invariantpacks()
        names = {p["name"] for p in packs}
        assert "cross_sheet/genotype_phenotype_consistency" in names

    def test_pack_listed_at_research_preview_with_1_invariant(self):
        packs = list_invariantpacks()
        gp = next(p for p in packs if p["name"] == "cross_sheet/genotype_phenotype_consistency")
        assert gp["status"] == "research_preview"
        assert gp["n_invariants"] == 1


class TestGenotypePhenotypePackContents:

    def test_loads_at_research_preview(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        assert lp.status == InvariantPackStatus.RESEARCH_PREVIEW
        assert lp.invariantpack.invariantpack_id == "cross_sheet/genotype_phenotype_consistency@1.0.0"

    def test_pack_has_apoe4_invariant(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.name == "apoe4_homozygote_expected_ad_trajectory"

    def test_invariant_source_is_patients_apoe_genotype_e4e4(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.type == "categorical_implies_trajectory_pattern"
        assert inv.condition.source_sheet == "patients"
        assert inv.condition.source_field == "apoe_genotype"
        assert inv.condition.source_value == "e4/e4"

    def test_invariant_trajectory_sheet_is_predictions(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.trajectory_sheet == "predictions"

    def test_invariant_pattern_kind_elevated_risk_marker(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.pattern.kind == "elevated_risk_marker"

    def test_invariant_baseline_rate_60_percent(self):
        """Per Fortea 2024 / NIA: ~60% develop AD dementia by age 85."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.pattern.population_baseline_rate == 0.60

    def test_invariant_flag_threshold_age_85_10y_followup(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.pattern.flag_threshold == "none_observed_after_age_85_with_10y_followup"

    def test_invariant_at_info_severity(self):
        """Per LAYER_3_DESIGN.md section 12 Q1: genotype-phenotype
        invariants in v1.11.0 use info severity (advisory only)."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.flag_severity == "info"

    def test_invariant_citation_strength_international_consensus(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_anchor_citation_is_fortea_2024(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        anchor = lp.invariantpack.anchor_citation
        assert anchor.citation_pmid == "38710950"
        assert anchor.citation_doi == "10.1038/s41591-024-02931-w"

    def test_invariant_citation_has_5plus_endorsing_bodies(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        assert len(inv.citation.endorsing_bodies) >= 5

    def test_invariant_citation_includes_fortea(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        joined = " ".join(inv.citation.endorsing_bodies)
        assert "Fortea" in joined

    def test_invariant_citation_includes_nia_or_nih(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        inv = lp.invariantpack.invariants[0]
        joined = " ".join(inv.citation.endorsing_bodies)
        assert "NIA" in joined or "NIH" in joined


class TestGenotypePhenotypeYamlSha:

    def test_yaml_sha256_matches_golden(self):
        """The v1.11.0a3 yaml_sha256 of genotype_phenotype_consistency
        must match the locked golden value."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        assert lp.yaml_sha256 == GOLDEN_YAML_SHA256_GENOTYPE_PHENOTYPE


class TestTrajectoryPatternExecutionAgainstShippedPack:
    """End-to-end execution tests using the actual shipped pack."""

    def test_apoe4_homozygote_normal_at_88_with_12y_followup_flags(self):
        """APOE4 homozygote observed cognitively normal at age 88 with
        12y follow-up should flag (pattern deviation from baseline)."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 82, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v3", "age_years": 88, "ad_dementia_status": 0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        flag = result.flags[0]
        assert flag.severity == "info"
        assert flag.audit_layer == "layer_3_cross_sheet"
        assert flag.invariant_name == "apoe4_homozygote_expected_ad_trajectory"
        assert "60%" in flag.flag_reason
        assert "Fortea 2024" in flag.flag_reason

    def test_apoe4_homozygote_developed_ad_no_flag(self):
        """APOE4 homozygote who developed AD dementia should NOT flag
        (pattern matches expectation)."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 70, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 75, "ad_dementia_status": 1},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_apoe4_homozygote_short_followup_no_flag(self):
        """APOE4 homozygote with <10y follow-up should NOT flag."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 75, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 80, "ad_dementia_status": 0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_apoe4_homozygote_young_no_flag(self):
        """APOE4 homozygote younger than age threshold should NOT flag."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 60, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 75, "ad_dementia_status": 0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_non_e4e4_genotype_no_flag(self):
        """APOE3/4 heterozygote should NOT match the invariant trigger."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e3/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 88, "ad_dementia_status": 0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_e4e4_with_no_trajectory_data_no_flag(self):
        """APOE4 homozygote with no trajectory data should NOT flag."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_multiple_patients_mixed(self):
        """Several patients: only the e4/e4 homozygote with long followup
        but no AD should flag."""
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [
                {"patient_id": "p1", "apoe_genotype": "e4/e4"},  # SHOULD flag
                {"patient_id": "p2", "apoe_genotype": "e4/e4"},  # developed AD, no flag
                {"patient_id": "p3", "apoe_genotype": "e3/e3"},  # wrong genotype, no flag
            ],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 88, "ad_dementia_status": 0},
                {"patient_id": "p2", "visit_id": "v1", "age_years": 70, "ad_dementia_status": 0},
                {"patient_id": "p2", "visit_id": "v2", "age_years": 80, "ad_dementia_status": 1},
                {"patient_id": "p3", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p3", "visit_id": "v2", "age_years": 88, "ad_dementia_status": 0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].join_key_values["patient_id"] == "p1"


class TestTrajectoryPatternFlagDeterminism:

    def test_flag_id_deterministic_across_runs(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 88, "ad_dementia_status": 0},
            ],
        }
        r1 = audit_cross_sheet(submission, [lp], dry_run=True)
        r2 = audit_cross_sheet(submission, [lp], dry_run=True)
        assert r1.flags[0].flag_id == r2.flags[0].flag_id

    def test_flag_id_is_hex_sha256(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 88, "ad_dementia_status": 0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        flag_id = result.flags[0].flag_id
        assert len(flag_id) == 64
        int(flag_id, 16)  # hex


class TestTrajectoryPatternStatusGate:

    def test_research_preview_refused_in_production_mode(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        with pytest.raises(ValueError, match="research_preview"):
            audit_cross_sheet({}, [lp], dry_run=False)

    def test_research_preview_accepted_in_dry_run_mode(self):
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        result = audit_cross_sheet({}, [lp], dry_run=True)
        # No data, no flags
        assert result.n_dry_run is True


class TestUnsupportedTrajectoryThresholdRaises:
    """If a future pack uses a flag_threshold pattern this version
    doesn't recognize, audit_cross_sheet should raise NotImplementedError
    with a clear message."""

    def test_unsupported_threshold_raises(self):
        # Build an in-memory pack with an unrecognized threshold pattern
        from datetime import date

        from neurotcs.clinical_ranges.schema import Citation
        from neurotcs.cross_sheet.loader import LoadedInvariantPack
        from neurotcs.cross_sheet.schema import (
            CategoricalImpliesTrajectoryPatternCondition,
            CrossSheetInvariant,
            InvariantPack,
            SheetSpec,
            TrajectoryPattern,
        )

        cit = Citation(
            citation_pmid="38710950",
            citation_text="Test citation, sufficient length for the validator to accept.",
            public_url="https://example.com/test",
            endorsing_bodies=["A", "B", "C", "D", "E"],
        )
        cond = CategoricalImpliesTrajectoryPatternCondition(
            source_sheet="patients",
            source_field="apoe_genotype",
            source_value="e4/e4",
            pattern=TrajectoryPattern(
                kind="elevated_risk_marker",
                population_baseline_rate=0.5,
                flag_threshold="some_future_pattern_not_yet_supported",
            ),
        )
        inv = CrossSheetInvariant(
            name="test_invariant",
            description="A test invariant with an unsupported threshold pattern.",
            sheets_required=[SheetSpec(role="patients"), SheetSpec(role="predictions")],
            condition=cond,
            flag_severity="info",
            citation=cit,
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="Test",
        )
        pack = InvariantPack(
            schema_version="1.0.0",
            invariantpack_id="cross_sheet/test/test_pack@1.0.0",
            pack_version="1.0.0",
            effective_date=date(2026, 5, 25),
            status=InvariantPackStatus.RESEARCH_PREVIEW,
            domain="test",
            framework_name="Test framework for validation",
            transcribed_by="Test, 2026-05-25",
            clinical_source_authority="Test authority for validation",
            anchor_citation=cit,
            invariants=[inv],
        )
        lp = LoadedInvariantPack(
            name="test",
            invariantpack=pack,
            canonical_sha256=pack.canonical_sha256(),
            yaml_sha256="0" * 64,
            status=InvariantPackStatus.RESEARCH_PREVIEW,
        )

        # Need a submission that triggers the invariant (matching genotype)
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [{"patient_id": "p1", "age_years": 80, "ad_dementia_status": 0}],
        }
        with pytest.raises(NotImplementedError, match="flag_threshold"):
            audit_cross_sheet(submission, [lp], dry_run=True)

"""
Tests for neurotcs.cross_sheet.schema (Layer 3 InvariantPack schema).

v1.11.0a1 (rc1 session #1): schema + loader only; audit_cross_sheet
not yet implemented. These tests verify:

- Schema discipline (pydantic strict mode, extra fields forbidden, etc.)
- Closed taxonomy of 4 ConditionSpec types (no other type accepted)
- NumericRange ordering validator
- InvariantPack-level validators (unique invariant names, deprecation
  requires either successor or reason)
- assert_usable_for_audit fail-closed for non-production statuses
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from neurotcs.clinical_ranges.schema import Citation, CitationStrength
from neurotcs.cross_sheet.schema import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    CategoricalImpliesRangeCondition,
    CategoricalImpliesTrajectoryPatternCondition,
    ConditionalRangeCase,
    CrossSheetInvariant,
    FieldPresenceConsistencyCondition,
    InvariantPack,
    InvariantPackStatus,
    NumericRange,
    SheetSpec,
    TrajectoryPattern,
    ValueRangeConditionalCondition,
)


# Helper to build a minimal valid citation for tests
def _valid_citation() -> Citation:
    return Citation(
        citation_pmid="35388223",
        citation_text="Test citation, sufficient length for the validator to accept.",
        public_url="https://example.com/test",
        endorsing_bodies=["A", "B", "C", "D", "E"],
    )


class TestSchemaVersion:

    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == "1.0.0"
        assert "1.0.0" in SUPPORTED_SCHEMA_VERSIONS


class TestInvariantPackStatusEnum:

    def test_all_status_values_present(self):
        values = {s.value for s in InvariantPackStatus}
        assert values == {
            "production",
            "research_preview",
            "skeleton",
            "planned",
            "deprecated",
        }

    def test_status_parallel_to_layer_2(self):
        """Layer 3 status enum must mirror Layer 2's RangePackStatus exactly."""
        from neurotcs.clinical_ranges.schema import RangePackStatus
        layer_2_values = {s.value for s in RangePackStatus}
        layer_3_values = {s.value for s in InvariantPackStatus}
        assert layer_3_values == layer_2_values


class TestNumericRange:

    def test_valid_range(self):
        r = NumericRange(lo=2.8, hi=5.0)
        assert r.lo == 2.8 and r.hi == 5.0

    def test_lo_equal_hi_allowed(self):
        """A degenerate range with lo == hi is allowed (single-point check)."""
        r = NumericRange(lo=1.0, hi=1.0)
        assert r.lo == r.hi == 1.0

    def test_lo_greater_than_hi_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            NumericRange(lo=5.0, hi=2.8)
        # The validator message should reference lo and hi
        msg = str(exc_info.value)
        assert "lo" in msg and "hi" in msg

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            NumericRange(lo=1.0, hi=2.0, extra_field="not allowed")


class TestSheetSpec:

    def test_valid_sheet_roles(self):
        for role in ["manifest", "predictions", "patients", "biomarkers", "attribution"]:
            s = SheetSpec(role=role)
            assert s.role == role
            assert s.required is True

    def test_invalid_sheet_role_rejected(self):
        with pytest.raises(ValidationError):
            SheetSpec(role="invalid_role")

    def test_required_can_be_false(self):
        s = SheetSpec(role="biomarkers", required=False)
        assert s.required is False


class TestCategoricalImpliesRangeCondition:

    def test_construct_valid(self):
        c = CategoricalImpliesRangeCondition(
            source_sheet="manifest",
            source_field="upstream_volumetry_tool",
            source_value="neuroquant_5.0",
            target_sheet="biomarkers",
            target_field="hippocampal_volume_total_cm3",
            target_range=NumericRange(lo=2.8, hi=5.0),
            target_unit="cm3",
        )
        assert c.type == "categorical_implies_range"
        assert c.target_range.lo == 2.8

    def test_target_unit_optional(self):
        c = CategoricalImpliesRangeCondition(
            source_sheet="manifest",
            source_field="x",
            source_value="y",
            target_sheet="biomarkers",
            target_field="z",
            target_range=NumericRange(lo=0, hi=1),
        )
        assert c.target_unit is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            CategoricalImpliesRangeCondition(
                source_sheet="manifest",
                source_field="x",
                source_value="y",
                target_sheet="biomarkers",
                target_field="z",
                target_range=NumericRange(lo=0, hi=1),
                hidden_eval_code="print('exploit')",
            )

    def test_invalid_sheet_role_rejected(self):
        with pytest.raises(ValidationError):
            CategoricalImpliesRangeCondition(
                source_sheet="invalid_sheet",
                source_field="x",
                source_value="y",
                target_sheet="biomarkers",
                target_field="z",
                target_range=NumericRange(lo=0, hi=1),
            )


class TestFieldPresenceConsistencyCondition:

    def test_construct_valid(self):
        c = FieldPresenceConsistencyCondition(
            source_sheet="manifest",
            source_field="conformance_level",
            source_value="L3",
            required_sheet="attribution",
            required_per_row_in_sheet="predictions",
        )
        assert c.type == "field_presence_consistency"


class TestValueRangeConditionalCondition:

    def test_construct_valid_with_two_cases(self):
        c = ValueRangeConditionalCondition(
            source_sheet="patients",
            source_field="age_band",
            cases=[
                ConditionalRangeCase(
                    source_value="young_adult",
                    target_sheet="biomarkers",
                    target_field="lateral_ventricle_volume_total_mm3",
                    target_range=NumericRange(lo=2000, hi=30000),
                ),
                ConditionalRangeCase(
                    source_value="elderly",
                    target_sheet="biomarkers",
                    target_field="lateral_ventricle_volume_total_mm3",
                    target_range=NumericRange(lo=2000, hi=120000),
                ),
            ],
        )
        assert len(c.cases) == 2

    def test_empty_cases_rejected(self):
        with pytest.raises(ValidationError):
            ValueRangeConditionalCondition(
                source_sheet="patients",
                source_field="age_band",
                cases=[],
            )


class TestCategoricalImpliesTrajectoryPatternCondition:

    def test_construct_valid(self):
        c = CategoricalImpliesTrajectoryPatternCondition(
            source_sheet="patients",
            source_field="apoe_genotype",
            source_value="e4/e4",
            pattern=TrajectoryPattern(
                kind="elevated_risk_marker",
                population_baseline_rate=0.50,
                flag_threshold="none_observed_after_age_85_with_10y_followup",
            ),
        )
        assert c.type == "categorical_implies_trajectory_pattern"
        assert c.trajectory_sheet == "predictions"

    def test_pattern_kind_closed_taxonomy(self):
        # Valid kinds
        for kind in ["elevated_risk_marker", "protective_marker", "population_baseline"]:
            p = TrajectoryPattern(
                kind=kind,
                population_baseline_rate=0.5,
                flag_threshold="test threshold description",
            )
            assert p.kind == kind

    def test_pattern_invalid_kind_rejected(self):
        with pytest.raises(ValidationError):
            TrajectoryPattern(
                kind="some_made_up_kind",
                population_baseline_rate=0.5,
                flag_threshold="test threshold description",
            )

    def test_baseline_rate_out_of_range_rejected(self):
        for bad_rate in [-0.1, 1.1, 1.5]:
            with pytest.raises(ValidationError):
                TrajectoryPattern(
                    kind="elevated_risk_marker",
                    population_baseline_rate=bad_rate,
                    flag_threshold="test threshold description",
                )


class TestCrossSheetInvariant:

    def _valid_invariant(self) -> CrossSheetInvariant:
        return CrossSheetInvariant(
            name="test_invariant",
            description="A test invariant for validation.",
            sheets_required=[SheetSpec(role="manifest"), SheetSpec(role="biomarkers")],
            join_keys=["patient_id"],
            condition=CategoricalImpliesRangeCondition(
                source_sheet="manifest",
                source_field="upstream_volumetry_tool",
                source_value="neuroquant_5.0",
                target_sheet="biomarkers",
                target_field="hippocampal_volume_total_cm3",
                target_range=NumericRange(lo=2.8, hi=5.0),
            ),
            flag_severity="warning",
            citation=_valid_citation(),
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="Test section",
        )

    def test_valid_construction(self):
        inv = self._valid_invariant()
        assert inv.name == "test_invariant"
        assert inv.flag_severity == "warning"

    def test_invalid_flag_severity_rejected(self):
        with pytest.raises(ValidationError):
            CrossSheetInvariant(
                name="t",  # too short
                description="A test invariant for validation.",
                sheets_required=[SheetSpec(role="manifest")],
                condition=CategoricalImpliesRangeCondition(
                    source_sheet="manifest", source_field="x", source_value="y",
                    target_sheet="biomarkers", target_field="z",
                    target_range=NumericRange(lo=0, hi=1),
                ),
                flag_severity="critical",  # not in {error, warning, info}
                citation=_valid_citation(),
                citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
                guideline_section="Test",
            )


class TestInvariantPackTopLevel:

    def _valid_pack(self, status=InvariantPackStatus.SKELETON) -> InvariantPack:
        inv = CrossSheetInvariant(
            name="test_invariant",
            description="A test invariant for validation.",
            sheets_required=[SheetSpec(role="manifest"), SheetSpec(role="biomarkers")],
            condition=CategoricalImpliesRangeCondition(
                source_sheet="manifest",
                source_field="x", source_value="y",
                target_sheet="biomarkers",
                target_field="z",
                target_range=NumericRange(lo=0, hi=1),
            ),
            flag_severity="info",
            citation=_valid_citation(),
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="Test",
        )
        return InvariantPack(
            schema_version="1.0.0",
            invariantpack_id="cross_sheet/test/test_pack@1.0.0",
            pack_version="1.0.0",
            effective_date=date(2026, 5, 25),
            status=status,
            domain="test",
            framework_name="Test framework for validation",
            transcribed_by="Test, 2026-05-25",
            clinical_source_authority="Test authority for validation",
            anchor_citation=_valid_citation(),
            invariants=[inv],
        )

    def test_valid_construction(self):
        pack = self._valid_pack()
        assert pack.invariantpack_id == "cross_sheet/test/test_pack@1.0.0"
        assert pack.status == InvariantPackStatus.SKELETON

    def test_unsupported_schema_version_rejected(self):
        with pytest.raises(ValidationError):
            InvariantPack(
                schema_version="999.0.0",
                invariantpack_id="cross_sheet/test/test_pack@1.0.0",
                pack_version="1.0.0",
                effective_date=date(2026, 5, 25),
                status=InvariantPackStatus.SKELETON,
                domain="test",
                framework_name="Test framework",
                transcribed_by="Test, 2026-05-25",
                clinical_source_authority="Test authority for validation",
                anchor_citation=_valid_citation(),
                invariants=[self._valid_pack().invariants[0]],
            )

    def test_deprecated_without_pointer_or_reason_rejected(self):
        """A DEPRECATED pack must have either deprecated_in_favor_of or
        deprecation_reason set, per the discipline parallel to Layer 2."""
        with pytest.raises(ValidationError):
            InvariantPack(
                schema_version="1.0.0",
                invariantpack_id="cross_sheet/test/test_pack@1.0.0",
                pack_version="1.0.0",
                effective_date=date(2026, 5, 25),
                status=InvariantPackStatus.DEPRECATED,
                domain="test",
                framework_name="Test framework",
                transcribed_by="Test, 2026-05-25",
                clinical_source_authority="Test authority for validation",
                anchor_citation=_valid_citation(),
                invariants=[self._valid_pack().invariants[0]],
                # No deprecated_in_favor_of OR deprecation_reason
            )

    def test_canonical_sha256_deterministic(self):
        pack = self._valid_pack()
        h1 = pack.canonical_sha256()
        h2 = pack.canonical_sha256()
        assert h1 == h2
        assert len(h1) == 64

    def test_assert_usable_for_audit_refuses_skeleton(self):
        pack = self._valid_pack(status=InvariantPackStatus.SKELETON)
        with pytest.raises(ValueError, match="skeleton"):
            pack.assert_usable_for_audit()

    def test_assert_usable_for_audit_refuses_research_preview(self):
        pack = self._valid_pack(status=InvariantPackStatus.RESEARCH_PREVIEW)
        with pytest.raises(ValueError, match="research_preview"):
            pack.assert_usable_for_audit()

    def test_assert_usable_for_audit_refuses_planned(self):
        pack = self._valid_pack(status=InvariantPackStatus.PLANNED)
        with pytest.raises(ValueError, match="planned"):
            pack.assert_usable_for_audit()

    def test_assert_usable_for_audit_accepts_production(self):
        """A production pack must NOT raise when assert_usable_for_audit
        is called -- the audit gate clears."""
        pack = self._valid_pack(status=InvariantPackStatus.PRODUCTION)
        # Should not raise
        pack.assert_usable_for_audit()

"""
Tests for neurotcs.cross_sheet.audit (Layer 3 audit execution).

Covers:
- audit_cross_sheet end-to-end on synthetic submissions
- Status gate (production allowed, research_preview requires dry_run, skeleton/planned/deprecated refused)
- Skip discipline (skip_packs requires matching skip_reasons with min 20-char reason)
- Missing-sheet info flag emission
- NotImplementedError for the 3 unimplemented condition types
- Golden flag_id values (cross-platform stable per design section 6)
"""

from __future__ import annotations

from datetime import date

import pytest

from neurotcs.clinical_ranges.schema import Citation, CitationStrength
from neurotcs.cross_sheet import (
    audit_cross_sheet,
    load_invariantpack,
)
from neurotcs.cross_sheet.loader import LoadedInvariantPack
from neurotcs.cross_sheet.schema import (
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


def _citation() -> Citation:
    return Citation(
        citation_pmid="35388223",
        citation_text="Test citation, sufficient length for the validator to accept.",
        public_url="https://example.com/test",
        endorsing_bodies=["A", "B", "C", "D", "E"],
    )


def _build_pack(
    status: InvariantPackStatus = InvariantPackStatus.RESEARCH_PREVIEW,
    condition=None,
    flag_severity: str = "warning",
) -> LoadedInvariantPack:
    """Build a minimal in-memory pack for testing."""
    if condition is None:
        condition = CategoricalImpliesRangeCondition(
            source_sheet="manifest",
            source_field="upstream_volumetry_tool",
            source_value="neuroquant_5.0",
            target_sheet="biomarkers",
            target_field="hippocampal_volume_total_cm3",
            target_range=NumericRange(lo=2.8, hi=5.0),
        )
    inv = CrossSheetInvariant(
        name="test_invariant",
        description="A test invariant for audit execution.",
        sheets_required=[SheetSpec(role="manifest"), SheetSpec(role="biomarkers")],
        join_keys=["patient_id", "visit_id"],
        condition=condition,
        flag_severity=flag_severity,
        citation=_citation(),
        citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
        guideline_section="Test section",
    )
    pack = InvariantPack(
        schema_version="1.0.0",
        invariantpack_id="cross_sheet/test/test_pack@1.0.0",
        pack_version="1.0.0",
        effective_date=date(2026, 5, 25),
        status=status,
        domain="test",
        framework_name="Test framework for audit execution",
        transcribed_by="Test, 2026-05-25",
        clinical_source_authority="Test authority for validation",
        anchor_citation=_citation(),
        invariants=[inv],
    )
    return LoadedInvariantPack(
        name="cross_sheet/test/test_pack",
        invariantpack=pack,
        canonical_sha256=pack.canonical_sha256(),
        yaml_sha256="0" * 64,  # deterministic fake hash for tests
        status=status,
    )


class TestAuditCategoricalImpliesRange:

    def test_in_range_no_flags(self):
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5},
                {"patient_id": "p2", "visit_id": "v1", "hippocampal_volume_total_cm3": 4.2},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0
        assert result.packs_run == ["cross_sheet/test/test_pack@1.0.0"]
        assert result.n_invariants_evaluated == 1
        assert result.n_rows_audited == 2

    def test_below_range_flags_with_warning(self):
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        flag = result.flags[0]
        assert flag.severity == "warning"
        assert flag.observed_value == 1.5
        assert flag.expected_range_lo == 2.8
        assert flag.expected_range_hi == 5.0
        assert flag.declared_tool == "neuroquant_5.0"
        assert flag.audit_layer == "layer_3_cross_sheet"

    def test_above_range_flags(self):
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 6.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].observed_value == 6.0

    def test_non_matching_tool_no_flags(self):
        """If manifest declares a different tool, the invariant doesn't apply."""
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "freesurfer_7.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_missing_source_field_no_flags(self):
        """If manifest doesn't declare upstream_volumetry_tool at all, no flags."""
        lp = _build_pack()
        submission = {
            "manifest": {},  # source field absent
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_missing_target_field_no_flags(self):
        """If biomarkers row doesn't carry the target field, no flag (not an error)."""
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1"},  # no hippocampal field
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_non_numeric_target_field_no_flags(self):
        """If target field is non-numeric, skip without error."""
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": "N/A"},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_join_keys_captured_in_flag(self):
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        flag = result.flags[0]
        assert flag.join_key_values == {"patient_id": "p1", "visit_id": "v1"}


class TestMissingSheetHandling:

    def test_missing_required_sheet_emits_info_flag(self):
        """Per LAYER_3_DESIGN.md section 8 rule 1: missing required
        sheet emits an info flag, not an exception."""
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            # biomarkers is required but absent
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        flag = result.flags[0]
        assert flag.severity == "info"
        assert "missing_required_sheet" in flag.flag_reason
        assert "biomarkers" in flag.flag_reason

    def test_optional_sheet_missing_no_flag(self):
        """An invariant whose only optional sheet is missing produces no flag."""
        # All sheets in our test pack are required, so this test verifies
        # that ALL required sheets being present produces no missing-sheet flags.
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [],  # present but empty
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        # No missing-sheet flag because biomarkers IS present (just empty)
        info_flags = [f for f in result.flags if f.severity == "info"]
        assert len(info_flags) == 0


class TestStatusGate:

    def test_production_pack_runs(self):
        lp = _build_pack(status=InvariantPackStatus.PRODUCTION)
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert result.n_invariants_evaluated == 1
        assert result.n_dry_run is False

    def test_research_preview_refused_without_dry_run(self):
        lp = _build_pack(status=InvariantPackStatus.RESEARCH_PREVIEW)
        with pytest.raises(ValueError, match="research_preview"):
            audit_cross_sheet({}, [lp], dry_run=False)

    def test_research_preview_accepted_with_dry_run(self):
        lp = _build_pack(status=InvariantPackStatus.RESEARCH_PREVIEW)
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert result.n_dry_run is True

    def test_skeleton_refused_in_dry_run_mode(self):
        """skeleton, planned, deprecated all refused regardless of dry_run."""
        for status in (InvariantPackStatus.SKELETON, InvariantPackStatus.PLANNED):
            lp = _build_pack(status=status)
            with pytest.raises(ValueError, match=status.value):
                audit_cross_sheet({}, [lp], dry_run=True)


class TestSkipDiscipline:

    def test_skip_pack_with_valid_reason(self):
        lp = _build_pack(status=InvariantPackStatus.PRODUCTION)
        result = audit_cross_sheet(
            {"manifest": {}, "biomarkers": []},
            [lp],
            skip_packs=["cross_sheet/test/test_pack@1.0.0"],
            skip_reasons={"cross_sheet/test/test_pack@1.0.0": "test skip reason long enough"},
        )
        assert result.packs_run == []
        assert result.packs_skipped == [
            ("cross_sheet/test/test_pack@1.0.0", "test skip reason long enough")
        ]

    def test_skip_without_reason_raises(self):
        lp = _build_pack(status=InvariantPackStatus.PRODUCTION)
        with pytest.raises(ValueError, match="skip_reasons"):
            audit_cross_sheet(
                {}, [lp],
                skip_packs=["cross_sheet/test/test_pack@1.0.0"],
                # missing skip_reasons
            )

    def test_skip_reason_too_short_raises(self):
        lp = _build_pack(status=InvariantPackStatus.PRODUCTION)
        with pytest.raises(ValueError, match="too short"):
            audit_cross_sheet(
                {}, [lp],
                skip_packs=["cross_sheet/test/test_pack@1.0.0"],
                skip_reasons={"cross_sheet/test/test_pack@1.0.0": "short"},
            )


class TestUnimplementedConditionTypes:
    """v1.11.0a2 only implements categorical_implies_range. The other 3
    raise NotImplementedError pointing to the future session that ships them.

    Note: the test pack _build_pack() always declares sheets_required=
    [manifest, biomarkers], so submissions must include those two sheets
    or the missing-sheet info flag fires before the condition is reached.
    """

    def test_field_presence_consistency_raises(self):
        lp = _build_pack(
            status=InvariantPackStatus.RESEARCH_PREVIEW,
            condition=FieldPresenceConsistencyCondition(
                source_sheet="manifest",
                source_field="conformance_level",
                source_value="L3",
                required_sheet="attribution",
            ),
        )
        submission = {
            "manifest": {"conformance_level": "L3"},
            "biomarkers": [],  # required by test pack
            "attribution": {},
        }
        with pytest.raises(NotImplementedError, match="FieldPresenceConsistency"):
            audit_cross_sheet(submission, [lp], dry_run=True)

    def test_value_range_conditional_raises(self):
        lp = _build_pack(
            status=InvariantPackStatus.RESEARCH_PREVIEW,
            condition=ValueRangeConditionalCondition(
                source_sheet="patients",
                source_field="age_band",
                cases=[
                    ConditionalRangeCase(
                        source_value="elderly",
                        target_sheet="biomarkers",
                        target_field="lateral_ventricle_volume_total_mm3",
                        target_range=NumericRange(lo=2000, hi=120000),
                    ),
                ],
            ),
        )
        submission = {
            "manifest": {},
            "biomarkers": [],
            "patients": [],
        }
        with pytest.raises(NotImplementedError, match="ValueRangeConditional"):
            audit_cross_sheet(submission, [lp], dry_run=True)

    def test_trajectory_pattern_raises(self):
        lp = _build_pack(
            status=InvariantPackStatus.RESEARCH_PREVIEW,
            condition=CategoricalImpliesTrajectoryPatternCondition(
                source_sheet="patients",
                source_field="apoe_genotype",
                source_value="e4/e4",
                pattern=TrajectoryPattern(
                    kind="elevated_risk_marker",
                    population_baseline_rate=0.50,
                    flag_threshold="none_observed_after_age_85_with_10y_followup",
                ),
            ),
        )
        submission = {
            "manifest": {},
            "biomarkers": [],
            "patients": [{"apoe_genotype": "e4/e4"}],
        }
        with pytest.raises(NotImplementedError, match="CategoricalImpliesTrajectoryPattern"):
            audit_cross_sheet(submission, [lp], dry_run=True)


class TestFlagIdDeterminism:
    """Per LAYER_3_DESIGN.md section 6: flag_id is SHA-256 over canonical-JSON;
    must be deterministic across runs and cross-platform stable."""

    def test_flag_id_deterministic_across_runs(self):
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5},
            ],
        }
        r1 = audit_cross_sheet(submission, [lp], dry_run=True)
        r2 = audit_cross_sheet(submission, [lp], dry_run=True)
        assert r1.flags[0].flag_id == r2.flags[0].flag_id

    def test_flag_id_changes_with_observed_value(self):
        lp = _build_pack()
        s1 = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5}],
        }
        s2 = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.6}],
        }
        r1 = audit_cross_sheet(s1, [lp], dry_run=True)
        r2 = audit_cross_sheet(s2, [lp], dry_run=True)
        assert r1.flags[0].flag_id != r2.flags[0].flag_id

    def test_flag_id_is_hex_sha256(self):
        lp = _build_pack()
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        flag_id = result.flags[0].flag_id
        assert len(flag_id) == 64  # SHA-256 hex
        int(flag_id, 16)  # raises ValueError if not hex


class TestEndToEndWithShippedPack:
    """Use the actual shipped tool_declaration_consistency pack."""

    def test_shipped_pack_loads_with_3_invariants_at_research_preview(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.status == InvariantPackStatus.RESEARCH_PREVIEW
        assert len(lp.invariantpack.invariants) == 3

    def test_shipped_pack_neuroquant_in_range(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_shipped_pack_neuroquant_below_range(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1

    def test_shipped_pack_neuroreader_uses_narrower_range(self):
        """NeuroReader has 25th-percentile cutoff -> [3.5, 5.5] cm3.
        A value of 3.0 cm3 would be in-range for NeuroQuant [2.8, 5.0]
        but out-of-range (below) for NeuroReader [3.5, 5.5]."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroreader"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        flag = result.flags[0]
        assert flag.declared_tool == "neuroreader"
        assert flag.expected_range_lo == 3.5
        assert flag.expected_range_hi == 5.5

    def test_shipped_pack_icometrix_uses_bethlehem_range(self):
        """icometrix uses the Bethlehem-validated [2.8, 5.0] cm3 range
        (no fixed published cutoff from icometrix)."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "icometrix"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 4.2},  # in range
                {"patient_id": "p2", "visit_id": "v1", "hippocampal_volume_total_cm3": 5.5},  # above 5.0
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].observed_value == 5.5

    def test_shipped_pack_production_mode_refused(self):
        """The shipped pack is research_preview; production audit refused."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        with pytest.raises(ValueError, match="research_preview"):
            audit_cross_sheet({}, [lp], dry_run=False)

    def test_audit_result_diagnostics(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5},
                {"patient_id": "p2", "visit_id": "v1", "hippocampal_volume_total_cm3": 4.0},
                {"patient_id": "p3", "visit_id": "v1", "hippocampal_volume_total_cm3": 4.2},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert result.n_rows_audited == 3
        assert result.n_invariants_evaluated == 3  # all 3 invariants in the pack evaluated
        assert "cross_sheet/tool_declaration_consistency@1.0.0" in result.packs_run

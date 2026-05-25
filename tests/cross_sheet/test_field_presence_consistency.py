"""
Tests for the FieldPresenceConsistency execution (v1.11.0a6 NEW).

The condition type was schema-validated since v1.11.0a1 but raised
NotImplementedError on execution. v1.11.0a6 implements
_evaluate_field_presence_consistency() in audit.py.

Two modes covered:

  MODE A (sheet-presence only): if source field matches source value,
    required_sheet must be present and non-empty.

  MODE B (per-row matching): if source field matches source value,
    each row in required_per_row_in_sheet must have a matching entry
    in required_sheet, keyed on the invariant's join_keys.

No invariant pack uses this condition type yet in v1.11.0a6; the
manifest_data_consistency pack lands in a future session. These tests
verify the execution function works correctly so that future packs
have a stable runtime to rely on.
"""

from __future__ import annotations

from datetime import date

import pytest

from neurotcs.clinical_ranges.schema import Citation, CitationStrength
from neurotcs.cross_sheet import audit_cross_sheet
from neurotcs.cross_sheet.audit import (
    _extract_source_field_value,
    _is_empty_sheet,
)
from neurotcs.cross_sheet.loader import LoadedInvariantPack
from neurotcs.cross_sheet.schema import (
    CrossSheetInvariant,
    FieldPresenceConsistencyCondition,
    InvariantPack,
    InvariantPackStatus,
    SheetSpec,
)

# ============================================================
# Helpers for building synthetic invariants
# ============================================================

def _make_citation():
    return Citation(
        citation_pmid="38710950",
        citation_text="Synthetic test citation, long enough for the validator to accept.",
        public_url="https://example.com/test",
        endorsing_bodies=["A", "B", "C", "D", "E"],
    )


def _make_mode_a_invariant(flag_severity="error"):
    """Mode A: if manifest.conformance_level == 'L3', attribution must be present."""
    cit = _make_citation()
    cond = FieldPresenceConsistencyCondition(
        source_sheet="manifest",
        source_field="conformance_level",
        source_value="L3",
        required_sheet="attribution",
    )
    return CrossSheetInvariant(
        name="mode_a_attribution_present",
        description="If manifest declares L3 conformance, attribution sheet must be present.",
        sheets_required=[SheetSpec(role="manifest")],
        condition=cond,
        flag_severity=flag_severity,
        citation=cit,
        citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
        guideline_section="Mode A guideline section",
    )


def _make_mode_b_invariant(flag_severity="error"):
    """Mode B: each prediction row needs a matching attribution entry."""
    _make_citation()
    cond = FieldPresenceConsistencyCondition(
        source_sheet="manifest",
        source_field="conformance_level",
        source_value="L3",
        required_sheet="attribution",
        required_per_row_in_sheet="predictions",
    )
    return CrossSheetInvariant(
        name="mode_b_attribution_per_prediction",
        description="Each prediction row must have a matching attribution entry.",
        sheets_required=[SheetSpec(role="manifest"), SheetSpec(role="predictions")],
        condition=cond,
        flag_severity=flag_severity,
        citation=_make_citation(),
        citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
        guideline_section="Mode B guideline section",
        join_keys=["patient_id", "visit_id"],
    )


def _make_pack(invariants, name):
    cit = _make_citation()
    pack = InvariantPack(
        schema_version="1.0.0",
        invariantpack_id=f"cross_sheet/test/{name}@1.0.0",
        pack_version="1.0.0",
        effective_date=date(2026, 5, 25),
        status=InvariantPackStatus.RESEARCH_PREVIEW,
        domain="test",
        framework_name="Test framework for v1.11.0a6 field_presence",
        transcribed_by="Test transcribed_by for v1.11.0a6 tests",
        clinical_source_authority="Test authority for v1.11.0a6 field_presence",
        anchor_citation=cit,
        invariants=invariants,
    )
    return LoadedInvariantPack(
        name=f"test/{name}",
        invariantpack=pack,
        canonical_sha256=pack.canonical_sha256(),
        yaml_sha256="0" * 64,
        status=InvariantPackStatus.RESEARCH_PREVIEW,
    )


# ============================================================
# Helper function tests
# ============================================================

class TestExtractSourceFieldValue:

    def test_dict_source_field_present(self):
        assert _extract_source_field_value({"a": "b"}, "a") == "b"

    def test_dict_source_field_missing(self):
        assert _extract_source_field_value({"a": "b"}, "missing") is None

    def test_list_source_takes_first_row(self):
        assert _extract_source_field_value([{"a": "b"}, {"a": "c"}], "a") == "b"

    def test_empty_list_returns_none(self):
        assert _extract_source_field_value([], "a") is None

    def test_none_source_returns_none(self):
        assert _extract_source_field_value(None, "a") is None


class TestIsEmptySheet:

    def test_none_is_empty(self):
        assert _is_empty_sheet(None) is True

    def test_empty_dict_is_empty(self):
        assert _is_empty_sheet({}) is True

    def test_empty_list_is_empty(self):
        assert _is_empty_sheet([]) is True

    def test_dict_with_one_key_not_empty(self):
        assert _is_empty_sheet({"k": "v"}) is False

    def test_list_with_one_row_not_empty(self):
        assert _is_empty_sheet([{}]) is False


# ============================================================
# Mode A: sheet-presence-only invariant
# ============================================================

class TestFieldPresenceModeA:

    def test_trigger_not_matched_no_flag(self):
        """Trigger condition false (L2 not L3) -> no flag."""
        lp = _make_pack([_make_mode_a_invariant()], "mode_a_1")
        submission = {"manifest": {"conformance_level": "L2"}, "attribution": []}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_trigger_matched_required_sheet_missing_flags(self):
        """Trigger true, required_sheet not in submission -> 1 error flag."""
        lp = _make_pack([_make_mode_a_invariant()], "mode_a_2")
        submission = {"manifest": {"conformance_level": "L3"}}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].severity == "error"

    def test_trigger_matched_required_sheet_empty_flags(self):
        """Trigger true, required_sheet is empty list -> 1 error flag."""
        lp = _make_pack([_make_mode_a_invariant()], "mode_a_3")
        submission = {"manifest": {"conformance_level": "L3"}, "attribution": []}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].severity == "error"

    def test_trigger_matched_required_sheet_present_no_flag(self):
        """Trigger true, required_sheet present and non-empty -> no flag."""
        lp = _make_pack([_make_mode_a_invariant()], "mode_a_4")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "attribution": [{"patient_id": "p1", "visit_id": "v1", "url": "s3://..."}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_trigger_field_missing_no_flag(self):
        """Source field missing from manifest -> no flag (trigger doesn't fire)."""
        lp = _make_pack([_make_mode_a_invariant()], "mode_a_5")
        submission = {"manifest": {}, "attribution": []}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_flag_reason_describes_missing_sheet(self):
        lp = _make_pack([_make_mode_a_invariant()], "mode_a_6")
        submission = {"manifest": {"conformance_level": "L3"}}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert "attribution" in result.flags[0].flag_reason
        assert "L3" in result.flags[0].flag_reason

    def test_severity_respects_invariant_declaration_warning(self):
        """If invariant declares flag_severity='warning', flag must be warning."""
        lp = _make_pack([_make_mode_a_invariant(flag_severity="warning")], "mode_a_7")
        submission = {"manifest": {"conformance_level": "L3"}}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert result.flags[0].severity == "warning"

    def test_severity_respects_invariant_declaration_info(self):
        lp = _make_pack([_make_mode_a_invariant(flag_severity="info")], "mode_a_8")
        submission = {"manifest": {"conformance_level": "L3"}}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert result.flags[0].severity == "info"


# ============================================================
# Mode B: per-row matching invariant
# ============================================================

class TestFieldPresenceModeB:

    def test_all_rows_matched_no_flag(self):
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_1")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1"},
                {"patient_id": "p2", "visit_id": "v1"},
            ],
            "attribution": [
                {"patient_id": "p1", "visit_id": "v1"},
                {"patient_id": "p2", "visit_id": "v1"},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_one_unmatched_prediction_flags(self):
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_2")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1"},
                {"patient_id": "p2", "visit_id": "v1"},
            ],
            "attribution": [{"patient_id": "p1", "visit_id": "v1"}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].severity == "error"
        assert result.flags[0].join_key_values == {"patient_id": "p2", "visit_id": "v1"}

    def test_multiple_unmatched_predictions_flag_each(self):
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_3")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1"},
                {"patient_id": "p2", "visit_id": "v1"},
                {"patient_id": "p3", "visit_id": "v1"},
            ],
            "attribution": [{"patient_id": "p2", "visit_id": "v1"}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 2
        unmatched_ids = sorted(f.join_key_values["patient_id"] for f in result.flags)
        assert unmatched_ids == ["p1", "p3"]

    def test_required_sheet_entirely_missing_emits_sheet_level_flag(self):
        """If attribution sheet is missing entirely, emit ONE missing-sheet flag,
        not one-per-prediction-row."""
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_4")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1"},
                {"patient_id": "p2", "visit_id": "v1"},
                {"patient_id": "p3", "visit_id": "v1"},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].join_key_values == {}  # sheet-level flag has empty join

    def test_trigger_not_matched_no_flags(self):
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_5")
        submission = {
            "manifest": {"conformance_level": "L2"},
            "predictions": [{"patient_id": "p1", "visit_id": "v1"}],
            "attribution": [],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_prediction_row_missing_join_key_is_skipped(self):
        """A row in required_per_row_in_sheet that lacks a complete join key
        is skipped (not flagged)."""
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_6")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [
                {"patient_id": "p1"},  # missing visit_id
                {"patient_id": "p2", "visit_id": "v1"},
            ],
            "attribution": [{"patient_id": "p2", "visit_id": "v1"}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        # p1 has incomplete key (skipped); p2 matches -> no flags
        assert len(result.flags) == 0

    def test_attribution_with_missing_join_key_not_indexed(self):
        """An attribution row lacking a complete join key is not added to
        the matching index; predictions matching that incomplete entry
        will fail to match."""
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_7")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [{"patient_id": "p1", "visit_id": "v1"}],
            "attribution": [{"patient_id": "p1"}],  # missing visit_id
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        # p1's attribution is not indexed (incomplete key); p1 prediction unmatched -> 1 flag
        assert len(result.flags) == 1
        assert result.flags[0].join_key_values == {"patient_id": "p1", "visit_id": "v1"}

    def test_per_row_sheet_missing_no_flags(self):
        """If required_per_row_in_sheet (predictions) is missing entirely,
        emit no per-row flags (sheet-level pre-check handles this case)."""
        # Note: predictions IS in sheets_required, so the missing-sheet pre-check
        # fires an info flag from the audit layer. Use a submission with
        # predictions present but empty.
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_8")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [],
            "attribution": [{"patient_id": "p1", "visit_id": "v1"}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        # No predictions to match -> no flags
        assert len(result.flags) == 0

    def test_flag_reason_describes_unmatched_row(self):
        lp = _make_pack([_make_mode_b_invariant()], "mode_b_9")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [{"patient_id": "p1", "visit_id": "v1"}],
            "attribution": [],
        }
        # Empty attribution sheet -> sheet-level flag, NOT per-row
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert "attribution" in result.flags[0].flag_reason


# ============================================================
# Determinism
# ============================================================

class TestFieldPresenceDeterminism:

    def test_mode_a_flag_id_deterministic(self):
        lp = _make_pack([_make_mode_a_invariant()], "det_a")
        submission = {"manifest": {"conformance_level": "L3"}}
        r1 = audit_cross_sheet(submission, [lp], dry_run=True)
        r2 = audit_cross_sheet(submission, [lp], dry_run=True)
        assert r1.flags[0].flag_id == r2.flags[0].flag_id

    def test_mode_b_unmatched_flag_id_deterministic(self):
        lp = _make_pack([_make_mode_b_invariant()], "det_b")
        submission = {
            "manifest": {"conformance_level": "L3"},
            "predictions": [{"patient_id": "p1", "visit_id": "v1"}],
            "attribution": [{"patient_id": "p2", "visit_id": "v1"}],
        }
        r1 = audit_cross_sheet(submission, [lp], dry_run=True)
        r2 = audit_cross_sheet(submission, [lp], dry_run=True)
        assert r1.flags[0].flag_id == r2.flags[0].flag_id

    def test_flag_id_is_hex_sha256(self):
        lp = _make_pack([_make_mode_a_invariant()], "hex_test")
        submission = {"manifest": {"conformance_level": "L3"}}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        flag_id = result.flags[0].flag_id
        assert len(flag_id) == 64
        int(flag_id, 16)


# ============================================================
# Regression: prior condition types still work
# ============================================================

class TestNoRegressionsFromFieldPresenceImplementation:
    """Adding FieldPresenceConsistency execution must not change
    behavior of CategoricalImpliesRange or CategoricalImpliesTrajectoryPattern.
    These tests rely on the shipped invariant packs."""

    def test_tool_declaration_pack_still_works(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "quantib_nd"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 2.0}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=False)
        assert len(result.flags) == 1
        assert result.flags[0].severity == "warning"

    def test_genotype_phenotype_pack_still_works(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        submission = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 88, "ad_dementia_status": 0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].severity == "info"


# ============================================================
# ValueRangeConditional NOT yet implemented (still raises)
# ============================================================

class TestValueRangeConditionalStillRaises:
    """ValueRangeConditional execution lands in v1.11.0a7 (next session).
    For now it must still raise NotImplementedError."""

    def test_value_range_conditional_raises(self):
        from neurotcs.cross_sheet.schema import (
            ConditionalRangeCase,
            ValueRangeConditionalCondition,
        )
        cit = _make_citation()
        case = ConditionalRangeCase(
            source_value="adult",
            target_sheet="biomarkers",
            target_field="age_years",
            target_range={"lo": 18, "hi": 120},
        )
        cond = ValueRangeConditionalCondition(
            source_sheet="patients",
            source_field="age_band",
            cases=[case],
        )
        inv = CrossSheetInvariant(
            name="test_value_range_conditional",
            description="A test invariant for value range conditional.",
            sheets_required=[SheetSpec(role="patients"), SheetSpec(role="biomarkers")],
            condition=cond,
            flag_severity="info",
            citation=cit,
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="Test guideline",
        )
        lp = _make_pack([inv], "value_range_test")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "age_years": 35}],
        }
        with pytest.raises(NotImplementedError, match="ValueRangeConditional"):
            audit_cross_sheet(submission, [lp], dry_run=True)

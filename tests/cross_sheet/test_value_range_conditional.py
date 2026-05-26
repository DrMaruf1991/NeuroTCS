"""
Tests for the ValueRangeConditional execution (v1.11.0a7 NEW).

The condition type was schema-validated since v1.11.0a1 but raised
NotImplementedError on execution. v1.11.0a7 implements
_evaluate_value_range_conditional() in audit.py.

Canonical use case (per v1.11.0-design.2 section 4.4.3): age-conditional
normative ranges. E.g., patients.age_band determines biomarkers.X bound.

Two execution patterns supported:

  CROSS-SHEET: source_sheet != target_sheet. Source rows joined to
    target rows via the invariant's join_keys; each (source, target)
    pair checked against the case matched by source_value.

  SAME-SHEET: source_sheet == target_sheet. Each source row also has
    the target_field; the range check applies in place (no join).

Explicitly NOT supported in v1.11.0a7:
  - source_sheet == "manifest": raises NotImplementedError pointing
    to categorical_implies_range, which handles whole-submission triggers.
  - Cases with mixed target_sheets: raises NotImplementedError.

No invariant pack uses this condition type yet in v1.11.0a7; the
runtime is now ready for future packs to use it.
"""

from __future__ import annotations

from datetime import date

import pytest

from neurotcs.clinical_ranges.schema import Citation, CitationStrength
from neurotcs.cross_sheet import audit_cross_sheet
from neurotcs.cross_sheet.loader import LoadedInvariantPack
from neurotcs.cross_sheet.schema import (
    ConditionalRangeCase,
    CrossSheetInvariant,
    InvariantPack,
    InvariantPackStatus,
    NumericRange,
    SheetSpec,
    ValueRangeConditionalCondition,
)


def _make_citation():
    return Citation(
        citation_pmid="38710950",
        citation_text="Synthetic test citation, long enough for the validator.",
        public_url="https://example.com/test",
        endorsing_bodies=["A", "B", "C", "D", "E"],
    )


def _make_cross_sheet_invariant(flag_severity="warning"):
    """Cross-sheet: patients.age_band determines biomarkers.hippocampal_volume_total_cm3."""
    cit = _make_citation()
    cond = ValueRangeConditionalCondition(
        source_sheet="patients",
        source_field="age_band",
        cases=[
            ConditionalRangeCase(
                source_value="pediatric", target_sheet="biomarkers",
                target_field="hippocampal_volume_total_cm3",
                target_range=NumericRange(lo=1.5, hi=3.5),
            ),
            ConditionalRangeCase(
                source_value="adult", target_sheet="biomarkers",
                target_field="hippocampal_volume_total_cm3",
                target_range=NumericRange(lo=2.8, hi=5.0),
            ),
            ConditionalRangeCase(
                source_value="geriatric", target_sheet="biomarkers",
                target_field="hippocampal_volume_total_cm3",
                target_range=NumericRange(lo=2.2, hi=4.5),
            ),
        ],
    )
    return CrossSheetInvariant(
        name="cross_sheet_age_conditional",
        description="Cross-sheet age-conditional hippocampal volume.",
        sheets_required=[SheetSpec(role="patients"), SheetSpec(role="biomarkers")],
        condition=cond,
        flag_severity=flag_severity,
        citation=cit,
        citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
        guideline_section="Cross-sheet test guideline",
        join_keys=["patient_id"],
    )


def _make_same_sheet_invariant(flag_severity="warning"):
    """Same-sheet: patients.age_band determines patients.height_cm."""
    cit = _make_citation()
    cond = ValueRangeConditionalCondition(
        source_sheet="patients",
        source_field="age_band",
        cases=[
            ConditionalRangeCase(
                source_value="pediatric", target_sheet="patients",
                target_field="height_cm",
                target_range=NumericRange(lo=80, hi=160),
            ),
            ConditionalRangeCase(
                source_value="adult", target_sheet="patients",
                target_field="height_cm",
                target_range=NumericRange(lo=140, hi=210),
            ),
        ],
    )
    return CrossSheetInvariant(
        name="same_sheet_age_height",
        description="Same-sheet age-conditional height.",
        sheets_required=[SheetSpec(role="patients")],
        condition=cond,
        flag_severity=flag_severity,
        citation=cit,
        citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
        guideline_section="Same-sheet test guideline",
        join_keys=["patient_id"],
    )


def _make_pack(inv, name):
    cit = _make_citation()
    pack = InvariantPack(
        schema_version="1.0.0",
        invariantpack_id=f"cross_sheet/test/{name}@1.0.0",
        pack_version="1.0.0",
        effective_date=date(2026, 5, 26),
        status=InvariantPackStatus.RESEARCH_PREVIEW,
        domain="test",
        framework_name="v1.11.0a7 value_range_conditional test framework",
        transcribed_by="Test transcribed_by attribution for v1.11.0a7",
        clinical_source_authority="Test authority for v1.11.0a7 VRC execution",
        anchor_citation=cit,
        invariants=[inv],
    )
    return LoadedInvariantPack(
        name=f"test/{name}",
        invariantpack=pack,
        canonical_sha256=pack.canonical_sha256(),
        yaml_sha256="0" * 64,
        status=InvariantPackStatus.RESEARCH_PREVIEW,
    )


# ============================================================
# Cross-sheet pattern (the canonical use case)
# ============================================================

class TestCrossSheetValueRangeConditional:

    def test_in_range_no_flag(self):
        """Adult patient with hippocampal volume in [2.8, 5.0] -> no flag."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_1")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_below_range_flags(self):
        """Pediatric patient with volume below pediatric range -> 1 flag."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_2")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "pediatric"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 0.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].severity == "warning"
        assert result.flags[0].observed_value == 0.5
        assert result.flags[0].expected_range_lo == 1.5
        assert result.flags[0].expected_range_hi == 3.5

    def test_above_range_flags(self):
        """Pediatric patient with adult-sized volume -> 1 flag."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_3")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "pediatric"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 4.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].observed_value == 4.5

    def test_geriatric_in_range_no_flag(self):
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_4")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "geriatric"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.0}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_geriatric_below_range_flags(self):
        """Geriatric range is [2.2, 4.5]; 2.0 is below."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_5")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "geriatric"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 2.0}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].expected_range_lo == 2.2

    def test_unknown_age_band_silent(self):
        """An age_band value with no matching case -> no flag (silent)."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_6")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "neonate"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 0.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_missing_source_field_silent(self):
        """Source row missing age_band -> no flag."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_7")
        submission = {
            "patients": [{"patient_id": "p1"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 10}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_missing_target_field_silent(self):
        """Target row missing hippocampal_volume_total_cm3 -> no flag."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_8")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1"}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_no_join_key_match_silent(self):
        """Patient with no matching biomarker row -> no flag."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_9")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p_other", "visit_id": "v1", "hippocampal_volume_total_cm3": 0.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_incomplete_join_key_skipped(self):
        """Source row missing one of the join keys -> skipped."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_10")
        submission = {
            "patients": [{"age_band": "adult"}],  # missing patient_id
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 0.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_multiple_patients_mixed(self):
        """3 patients, 1 violation -> 1 flag for the right patient."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_11")
        submission = {
            "patients": [
                {"patient_id": "p1", "age_band": "pediatric"},
                {"patient_id": "p2", "age_band": "adult"},
                {"patient_id": "p3", "age_band": "geriatric"},
            ],
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.0},  # in pediatric
                {"patient_id": "p2", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5},  # below adult
                {"patient_id": "p3", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.0},  # in geriatric
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].join_key_values == {"patient_id": "p2"}

    def test_multiple_violations_emit_per_target_row(self):
        """One source row, multiple matching target rows: each violating
        target row produces a flag."""
        lp = _make_pack(_make_cross_sheet_invariant(), "cs_12")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.0},  # below
                {"patient_id": "p1", "visit_id": "v2", "hippocampal_volume_total_cm3": 6.0},  # above
                {"patient_id": "p1", "visit_id": "v3", "hippocampal_volume_total_cm3": 3.5},  # in
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 2

    def test_severity_respects_invariant_declaration_error(self):
        lp = _make_pack(_make_cross_sheet_invariant(flag_severity="error"), "cs_13")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 10}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert result.flags[0].severity == "error"

    def test_severity_respects_invariant_declaration_info(self):
        lp = _make_pack(_make_cross_sheet_invariant(flag_severity="info"), "cs_14")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 10}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert result.flags[0].severity == "info"


# ============================================================
# Same-sheet pattern
# ============================================================

class TestSameSheetValueRangeConditional:

    def test_adult_in_range_no_flag(self):
        lp = _make_pack(_make_same_sheet_invariant(), "ss_1")
        submission = {"patients": [{"patient_id": "p1", "age_band": "adult", "height_cm": 175}]}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_pediatric_too_tall_flags(self):
        lp = _make_pack(_make_same_sheet_invariant(), "ss_2")
        submission = {"patients": [{"patient_id": "p1", "age_band": "pediatric", "height_cm": 200}]}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].observed_value == 200
        assert result.flags[0].expected_range_hi == 160

    def test_adult_too_short_flags(self):
        lp = _make_pack(_make_same_sheet_invariant(), "ss_3")
        submission = {"patients": [{"patient_id": "p1", "age_band": "adult", "height_cm": 100}]}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].observed_value == 100

    def test_unknown_age_band_silent(self):
        lp = _make_pack(_make_same_sheet_invariant(), "ss_4")
        submission = {"patients": [{"patient_id": "p1", "age_band": "geriatric", "height_cm": 50}]}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_missing_target_field_silent(self):
        lp = _make_pack(_make_same_sheet_invariant(), "ss_5")
        submission = {"patients": [{"patient_id": "p1", "age_band": "adult"}]}
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0


# ============================================================
# Boundary semantics (inclusive range)
# ============================================================

class TestValueRangeConditionalBoundaries:

    def test_exact_lo_is_in_range(self):
        """The range is inclusive; lo=2.8 for adult."""
        lp = _make_pack(_make_cross_sheet_invariant(), "bn_1")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 2.8}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_exact_hi_is_in_range(self):
        """The range is inclusive; hi=5.0 for adult."""
        lp = _make_pack(_make_cross_sheet_invariant(), "bn_2")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 5.0}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_just_below_lo_flags(self):
        lp = _make_pack(_make_cross_sheet_invariant(), "bn_3")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 2.79}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1

    def test_just_above_hi_flags(self):
        lp = _make_pack(_make_cross_sheet_invariant(), "bn_4")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 5.01}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1


# ============================================================
# Manifest source raises (deferred to a future condition type design)
# ============================================================

class TestValueRangeConditionalManifestSourceRaises:

    def test_manifest_source_raises_with_helpful_message(self):
        """v1.11.0a7 does not support manifest as source_sheet for VRC.
        Use categorical_implies_range instead for whole-submission triggers."""
        cit = _make_citation()
        cond = ValueRangeConditionalCondition(
            source_sheet="manifest",
            source_field="cohort_type",
            cases=[
                ConditionalRangeCase(
                    source_value="trial", target_sheet="biomarkers",
                    target_field="some_value",
                    target_range=NumericRange(lo=0, hi=10),
                ),
            ],
        )
        inv = CrossSheetInvariant(
            name="manifest_source",
            description="Manifest as source (should raise).",
            sheets_required=[SheetSpec(role="manifest"), SheetSpec(role="biomarkers")],
            condition=cond,
            flag_severity="warning",
            citation=cit,
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="Test guideline",
        )
        lp = _make_pack(inv, "manifest_src")
        submission = {
            "manifest": {"cohort_type": "trial"},
            "biomarkers": [{"patient_id": "p1", "some_value": 5}],
        }
        with pytest.raises(NotImplementedError, match="manifest"):
            audit_cross_sheet(submission, [lp], dry_run=True)

    def test_mixed_target_sheets_raises(self):
        """All cases must point at the same target_sheet."""
        cit = _make_citation()
        cond = ValueRangeConditionalCondition(
            source_sheet="patients",
            source_field="age_band",
            cases=[
                ConditionalRangeCase(
                    source_value="adult", target_sheet="biomarkers",
                    target_field="x",
                    target_range=NumericRange(lo=0, hi=10),
                ),
                ConditionalRangeCase(
                    source_value="pediatric", target_sheet="predictions",
                    target_field="y",
                    target_range=NumericRange(lo=0, hi=10),
                ),
            ],
        )
        inv = CrossSheetInvariant(
            name="mixed_targets",
            description="Mixed target sheets (should raise).",
            sheets_required=[SheetSpec(role="patients"), SheetSpec(role="biomarkers"), SheetSpec(role="predictions")],
            condition=cond,
            flag_severity="warning",
            citation=cit,
            citation_strength=CitationStrength.INTERNATIONAL_CONSENSUS,
            guideline_section="Test guideline",
            join_keys=["patient_id"],
        )
        lp = _make_pack(inv, "mixed_targets")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "x": 5}],
            "predictions": [{"patient_id": "p1", "y": 5}],
        }
        with pytest.raises(NotImplementedError, match="multiple"):
            audit_cross_sheet(submission, [lp], dry_run=True)


# ============================================================
# Determinism
# ============================================================

class TestValueRangeConditionalDeterminism:

    def test_flag_id_deterministic(self):
        lp = _make_pack(_make_cross_sheet_invariant(), "det_1")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 10}],
        }
        r1 = audit_cross_sheet(submission, [lp], dry_run=True)
        r2 = audit_cross_sheet(submission, [lp], dry_run=True)
        assert r1.flags[0].flag_id == r2.flags[0].flag_id

    def test_flag_id_is_hex_sha256(self):
        lp = _make_pack(_make_cross_sheet_invariant(), "det_2")
        submission = {
            "patients": [{"patient_id": "p1", "age_band": "adult"}],
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 10}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        flag_id = result.flags[0].flag_id
        assert len(flag_id) == 64
        int(flag_id, 16)


# ============================================================
# Regression: prior condition types still work
# ============================================================

class TestNoRegressionsFromValueRangeConditional:

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

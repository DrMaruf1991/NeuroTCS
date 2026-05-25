"""Tests for neurotcs.clinical_ranges.audit (engine behavior).

These tests verify the audit engine itself (input validation, flag generation,
NaN handling, unit mismatch detection, determinism, multi-pack handling)
using the only production pack in v1.10.0-rc1, ad/aria_safety.

Engine semantics are pack-agnostic — these tests use the production pack
because (a) only production packs may be audited, and (b) the engine
behavior is identical across packs.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges.audit import (
    REQUIRED_COLUMNS,
    ClinicalRangeAuditResult,
    MultiPackResult,
    audit_clinical_ranges,
    audit_clinical_ranges_multi,
)
from neurotcs.clinical_ranges.loader import load_rangepack

# ============================================================
# Input validation
# ============================================================

class TestInputValidation:
    def test_missing_column_rejected(self):
        rp = load_rangepack("ad/aria_safety")
        df = pd.DataFrame({"patient_id": ["A"], "value": [120.0]})
        with pytest.raises(ValueError, match="missing required column"):
            audit_clinical_ranges(df, rp)

    def test_all_required_columns_listed(self):
        assert REQUIRED_COLUMNS == ("patient_id", "visit_id", "measurement_name", "value", "unit")


# ============================================================
# Single-pack audit using ad/aria_safety (the v1.10.0-rc1 production pack)
# ============================================================

class TestAuditClinicalRanges:
    @pytest.fixture
    def aria_pack(self):
        return load_rangepack("ad/aria_safety")

    def test_in_range_yields_no_flags(self, aria_pack):
        """Below all thresholds: no flags."""
        df = pd.DataFrame({
            "patient_id": ["P1", "P1", "P1"],
            "visit_id": ["V1", "V1", "V1"],
            "measurement_name": [
                "aria_h_microhemorrhage_count",
                "aria_h_siderosis_focal_areas",
                "baseline_microhemorrhage_count",
            ],
            "value": [2, 1, 3],  # mild / mild / below exclusion
            "unit": ["count", "count", "count"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert isinstance(r, ClinicalRangeAuditResult)
        assert r.n_flagged == 0
        assert r.n_measurements_checked == 3
        assert r.n_measurements_covered == 3

    def test_hard_max_violation_flagged(self, aria_pack):
        """Severe ARIA-H: 15 microhemorrhages crosses hard_max=9."""
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["aria_h_microhemorrhage_count"],
            "value": [15], "unit": ["count"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged >= 1
        assert any(f.bound_type == "hard_max" for f in r.flags)
        assert any(f.flag_severity == "hard" for f in r.flags)

    def test_plausible_max_violation_flagged(self, aria_pack):
        """Moderate ARIA-H: 7 microhemorrhages crosses plausible_max=4 only."""
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["aria_h_microhemorrhage_count"],
            "value": [7], "unit": ["count"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "plausible_max"
        assert r.flags[0].flag_severity == "plausible"

    def test_uncovered_measurement_no_flag(self, aria_pack):
        """Measurement not in pack: goes into uncovered, not flagged."""
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["not_a_real_measurement"], "value": [42.0],
            "unit": ["units"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 0
        assert r.n_measurements_uncovered == 1
        assert "not_a_real_measurement" in r.uncovered_measurement_names

    def test_nan_values_dropped_by_default(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1", "P2"], "visit_id": ["V1", "V1"],
            "measurement_name": ["aria_h_microhemorrhage_count"] * 2,
            "value": [float("nan"), 3], "unit": ["count", "count"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_measurements_checked == 1  # NaN row dropped

    def test_nan_values_raise_when_drop_disabled(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["aria_h_microhemorrhage_count"],
            "value": [float("nan")], "unit": ["count"],
        })
        with pytest.raises(ValueError, match="NaN values present"):
            audit_clinical_ranges(df, aria_pack, drop_nan_values=False)

    def test_unit_mismatch_flagged(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["aria_h_microhemorrhage_count"],
            "value": [3], "unit": ["pg/mL"],  # wrong unit
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged >= 1
        assert any(f.bound_type == "unit_mismatch" for f in r.flags)


class TestCategoricalAudit:
    @pytest.fixture
    def aria_pack(self):
        return load_rangepack("ad/aria_safety")

    def test_valid_apoe_passes(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V0"],
            "measurement_name": ["apoe_e4_status"],
            "value": ["heterozygote"], "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 0

    def test_invalid_apoe_flagged(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V0"],
            "measurement_name": ["apoe_e4_status"],
            "value": ["invalid_status"], "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, aria_pack)
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "invalid_categorical"


# ============================================================
# Determinism
# ============================================================

class TestDeterminism:
    @pytest.fixture
    def aria_pack(self):
        return load_rangepack("ad/aria_safety")

    def test_same_input_same_flag_id(self, aria_pack):
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"], "visit_id": ["V1"] * 3,
            "measurement_name": ["aria_h_microhemorrhage_count"] * 3,
            "value": [3, 7, 15],  # 1 ok + 1 moderate + 1 severe
            "unit": ["count"] * 3,
        })
        r1 = audit_clinical_ranges(df, aria_pack)
        r2 = audit_clinical_ranges(df, aria_pack)
        assert r1.flag_id == r2.flag_id
        assert r1.n_flagged == r2.n_flagged

    def test_row_reorder_same_flag_id(self, aria_pack):
        df1 = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"],
            "visit_id": ["V1"] * 3,
            "measurement_name": ["aria_h_microhemorrhage_count"] * 3,
            "value": [5, 12, 8],
            "unit": ["count"] * 3,
        })
        df2 = df1.iloc[::-1].reset_index(drop=True)
        r1 = audit_clinical_ranges(df1, aria_pack)
        r2 = audit_clinical_ranges(df2, aria_pack)
        assert r1.flag_id == r2.flag_id

    def test_value_change_changes_flag_id(self, aria_pack):
        df1 = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["aria_h_microhemorrhage_count"],
            "value": [3], "unit": ["count"],
        })
        df2 = df1.copy()
        df2.loc[0, "value"] = 15  # crosses both plausible_max and hard_max
        r1 = audit_clinical_ranges(df1, aria_pack)
        r2 = audit_clinical_ranges(df2, aria_pack)
        assert r1.flag_id != r2.flag_id


# ============================================================
# Multi-pack audit
# ============================================================

class TestMultiPackAudit:
    def test_multipack_with_single_production_pack(self):
        """v1.10.0-rc1 has only one production pack; multi-pack mode should
        still work cleanly."""
        aria = load_rangepack("ad/aria_safety")
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["aria_h_microhemorrhage_count"],
            "value": [3], "unit": ["count"],
        })
        r = audit_clinical_ranges_multi(df, [aria])
        assert isinstance(r, MultiPackResult)
        assert r.total_flagged == 0
        assert len(r.per_pack) == 1

    def test_multipack_overlap_rejected(self):
        """If two packs cover the same measurement_name, multi-pack refuses."""
        from neurotcs.clinical_ranges.loader import LoadedRangePack
        from neurotcs.clinical_ranges.schema import (
            BoundType,
            Citation,
            MeasurementRange,
            RangeBound,
            RangePack,
            RangePackStatus,
        )
        cit = Citation(
            citation_pmid="29133356",
            citation_text="Long enough anchor quote for tests.",
        )
        # Build two packs covering 'overlap_meas' — should reject
        pack_a = RangePack(
            schema_version="1.0.0",
            rangepack_id="a/test@1.0.0",
            pack_version="1.0.0",
            effective_date="2026-05-25",
            status=RangePackStatus.PRODUCTION,
            domain="test_a",
            framework_name="Test framework A",
            transcribed_by="Test transcriber",
            clinical_source_authority="Test authority for pack A",
            anchor_citation=cit,
            measurements=[
                MeasurementRange(
                    name="overlap_meas", unit="x", description="Overlap measurement",
                    bounds=[RangeBound(
                        bound_type=BoundType.HARD_MIN, value=0.0,
                        citation=cit, guideline_section="A.1.1",
                    )],
                ),
            ],
        )
        pack_b = RangePack(
            schema_version="1.0.0",
            rangepack_id="b/test@1.0.0",
            pack_version="1.0.0",
            effective_date="2026-05-25",
            status=RangePackStatus.PRODUCTION,
            domain="test_b",
            framework_name="Test framework B",
            transcribed_by="Test transcriber",
            clinical_source_authority="Test authority for pack B",
            anchor_citation=cit,
            measurements=[
                MeasurementRange(
                    name="overlap_meas", unit="x", description="Overlap measurement",
                    bounds=[RangeBound(
                        bound_type=BoundType.HARD_MIN, value=0.0,
                        citation=cit, guideline_section="A.1.1",
                    )],
                ),
            ],
        )
        lpa = LoadedRangePack(name="a/test", rangepack=pack_a,
                              canonical_sha256=pack_a.canonical_sha256(),
                              yaml_sha256="a" * 64,
                              status=pack_a.status)
        lpb = LoadedRangePack(name="b/test", rangepack=pack_b,
                              canonical_sha256=pack_b.canonical_sha256(),
                              yaml_sha256="b" * 64,
                              status=pack_b.status)
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["overlap_meas"], "value": [1.0], "unit": ["x"],
        })
        with pytest.raises(ValueError, match="covered by both"):
            audit_clinical_ranges_multi(df, [lpa, lpb])


# ============================================================
# Fail-closed semantics
# ============================================================

class TestFailClosed:
    def test_skeleton_pack_blocks_audit(self):
        from neurotcs.clinical_ranges.loader import LoadedRangePack
        from neurotcs.clinical_ranges.schema import (
            BoundType,
            Citation,
            MeasurementRange,
            RangeBound,
            RangePack,
            RangePackStatus,
        )
        cit = Citation(
            citation_pmid="29133356",
            citation_text="Long enough anchor quote for tests.",
        )
        pack = RangePack(
            schema_version="1.0.0",
            rangepack_id="x/test@0.1.0",
            pack_version="0.1.0",
            effective_date="2026-05-25",
            status=RangePackStatus.SKELETON,
            domain="test",
            framework_name="Test framework",
            transcribed_by="Test transcriber",
            clinical_source_authority="Test authority for skeleton pack",
            anchor_citation=cit,
            measurements=[
                MeasurementRange(
                    name="x", unit="x", description="X measurement",
                    bounds=[RangeBound(
                        bound_type=BoundType.HARD_MIN, value=0.0,
                        citation=cit, guideline_section="A.1.1",
                    )],
                ),
            ],
        )
        lp = LoadedRangePack(name="x/test", rangepack=pack,
                             canonical_sha256=pack.canonical_sha256(),
                             yaml_sha256="0" * 64,
                             status=pack.status)
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["x"], "value": [5.0], "unit": ["x"],
        })
        with pytest.raises(ValueError, match="status="):
            audit_clinical_ranges(df, lp)

    def test_non_production_pack_blocks_audit(self):
        """All non-production packs must refuse audit.
        In v1.10.1: 1 research_preview (FreeSurfer) + 5 deprecated."""
        for name in [
            # Deprecated in v1.10.1 (superseded by world-class production packs)
            "vital_signs/standard",
            "csf_biomarkers/aa_2024",
            "plasma_biomarkers/aa_2024",
            "pet_amyloid/centiloid",
            "genetics/apoe_valid_genotypes",
            # Still research_preview, candidate for v1.10.2 upgrade
            "mri_volumetrics/freesurfer",
        ]:
            lp = load_rangepack(name)
            df = pd.DataFrame({
                "patient_id": ["P1"], "visit_id": ["V1"],
                "measurement_name": ["sbp"], "value": [120.0], "unit": ["mmHg"],
            })
            # ValueError raised either with "status=" (research_preview path)
            # or "DEPRECATED" (deprecated path); both are acceptable.
            with pytest.raises(ValueError, match="status=|DEPRECATED"):
                audit_clinical_ranges(df, lp)

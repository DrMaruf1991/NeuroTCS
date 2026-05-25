"""
Tests for the CategoricalNotInKnownSet condition type (v1.11.0a8 NEW).

Per v1.11.0a8 schema extension: adds a 5th condition type to the
Layer 3 audit, encoding coverage-gap semantics. The invariant author
declares a closed taxonomy of values they can validate (known_values),
and the audit flags submissions declaring values outside that taxonomy.

Canonical use case: manifest.upstream_volumetry_tool is declared but
is not one of the tools whose normative ranges are encoded in this
pack. The audit cannot validate the values; it emits an info flag
so reviewers know the declaration is outside the audit's known
taxonomy.

Severity discipline: flag_severity should typically be 'info' for
coverage-gap signals. The audit is not asserting the value is wrong;
it is asserting the audit cannot validate it.
"""

from __future__ import annotations

from datetime import date

import pytest

from neurotcs.clinical_ranges.schema import Citation, CitationStrength
from neurotcs.cross_sheet import audit_cross_sheet
from neurotcs.cross_sheet.loader import LoadedInvariantPack
from neurotcs.cross_sheet.schema import (
    CategoricalNotInKnownSetCondition,
    CrossSheetInvariant,
    InvariantPack,
    InvariantPackStatus,
    SheetSpec,
)


def _make_citation():
    return Citation(
        citation_pmid="38710950",
        citation_text="Synthetic test citation, long enough for validator.",
        public_url="https://example.com/test",
        endorsing_bodies=["A", "B", "C", "D", "E"],
    )


def _make_manifest_invariant(known_values=None, flag_severity="info"):
    if known_values is None:
        known_values = ["neuroquant_5.0", "neuroreader", "icometrix", "quantib_nd"]
    cit = _make_citation()
    cond = CategoricalNotInKnownSetCondition(
        source_sheet="manifest",
        source_field="upstream_volumetry_tool",
        known_values=known_values,
    )
    return CrossSheetInvariant(
        name="unknown_tool_check",
        description="If upstream_volumetry_tool is not in known set, info flag.",
        sheets_required=[SheetSpec(role="manifest")],
        condition=cond,
        flag_severity=flag_severity,
        citation=cit,
        citation_strength=CitationStrength.DERIVED,
        guideline_section="v1.11.0a8 unknown-tool check",
    )


def _make_row_shaped_invariant(known_values=None, flag_severity="info"):
    """Row-shaped invariant: check patients.age_band against a known taxonomy."""
    if known_values is None:
        known_values = ["pediatric", "adult", "geriatric"]
    cit = _make_citation()
    cond = CategoricalNotInKnownSetCondition(
        source_sheet="patients",
        source_field="age_band",
        known_values=known_values,
    )
    return CrossSheetInvariant(
        name="unknown_age_band_check",
        description="If age_band is not in known taxonomy, info flag.",
        sheets_required=[SheetSpec(role="patients")],
        condition=cond,
        flag_severity=flag_severity,
        citation=cit,
        citation_strength=CitationStrength.DERIVED,
        guideline_section="v1.11.0a8 row-shaped unknown-set check",
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
        framework_name="v1.11.0a8 categorical_not_in_known_set test framework",
        transcribed_by="Test transcribed_by attribution for v1.11.0a8",
        clinical_source_authority="Test authority for v1.11.0a8 NIKS condition",
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
# Schema validation
# ============================================================

class TestCategoricalNotInKnownSetSchemaValidation:

    def test_valid_construction(self):
        cond = CategoricalNotInKnownSetCondition(
            source_sheet="manifest",
            source_field="x",
            known_values=["a", "b", "c"],
        )
        assert cond.type == "categorical_not_in_known_set"
        assert cond.known_values == ["a", "b", "c"]

    def test_empty_known_values_rejected(self):
        with pytest.raises(ValueError):
            CategoricalNotInKnownSetCondition(
                source_sheet="manifest", source_field="x", known_values=[],
            )

    def test_duplicate_known_values_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            CategoricalNotInKnownSetCondition(
                source_sheet="manifest", source_field="x",
                known_values=["a", "b", "a"],
            )

    def test_empty_string_in_known_values_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            CategoricalNotInKnownSetCondition(
                source_sheet="manifest", source_field="x",
                known_values=["a", "", "b"],
            )

    def test_whitespace_only_in_known_values_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            CategoricalNotInKnownSetCondition(
                source_sheet="manifest", source_field="x",
                known_values=["a", "   ", "b"],
            )

    def test_single_known_value_allowed(self):
        cond = CategoricalNotInKnownSetCondition(
            source_sheet="manifest", source_field="x",
            known_values=["only_one"],
        )
        assert cond.known_values == ["only_one"]


# ============================================================
# Manifest-source execution
# ============================================================

class TestCategoricalNotInKnownSetManifestExecution:

    def test_known_tool_no_flag(self):
        lp = _make_pack(_make_manifest_invariant(), "m_1")
        sub = {"manifest": {"upstream_volumetry_tool": "neuroquant_5.0"}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_unknown_tool_emits_info_flag(self):
        lp = _make_pack(_make_manifest_invariant(), "m_2")
        sub = {"manifest": {"upstream_volumetry_tool": "freesurfer"}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 1
        assert r.flags[0].severity == "info"
        assert r.flags[0].declared_tool == "freesurfer"

    def test_unknown_tool_flag_reason_mentions_known_set(self):
        lp = _make_pack(_make_manifest_invariant(), "m_3")
        sub = {"manifest": {"upstream_volumetry_tool": "vuno_med_deepbrain"}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert "vuno_med_deepbrain" in r.flags[0].flag_reason
        assert "neuroquant_5.0" in r.flags[0].flag_reason  # known set listed

    def test_field_missing_silent(self):
        lp = _make_pack(_make_manifest_invariant(), "m_4")
        sub = {"manifest": {}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_field_null_silent(self):
        lp = _make_pack(_make_manifest_invariant(), "m_5")
        sub = {"manifest": {"upstream_volumetry_tool": None}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_field_empty_string_silent(self):
        lp = _make_pack(_make_manifest_invariant(), "m_6")
        sub = {"manifest": {"upstream_volumetry_tool": ""}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_field_whitespace_silent(self):
        lp = _make_pack(_make_manifest_invariant(), "m_7")
        sub = {"manifest": {"upstream_volumetry_tool": "   "}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_source_sheet_missing_silent(self):
        lp = _make_pack(_make_manifest_invariant(), "m_8")
        sub = {}  # no manifest
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        # The audit pre-check will emit a missing-sheet info flag for the
        # missing manifest (it's in sheets_required), but the NIKS invariant
        # itself should add no further flags.
        niks_flags = [f for f in r.flags if f.invariant_name == "unknown_tool_check"
                      and "not in" in f.flag_reason]
        assert len(niks_flags) == 0

    def test_severity_respects_invariant_declaration(self):
        lp_warning = _make_pack(_make_manifest_invariant(flag_severity="warning"), "m_sev_1")
        lp_error = _make_pack(_make_manifest_invariant(flag_severity="error"), "m_sev_2")
        sub = {"manifest": {"upstream_volumetry_tool": "unknown"}}

        r_warning = audit_cross_sheet(sub, [lp_warning], dry_run=True)
        assert r_warning.flags[0].severity == "warning"

        r_error = audit_cross_sheet(sub, [lp_error], dry_run=True)
        assert r_error.flags[0].severity == "error"

    def test_each_of_four_known_tools_silent(self):
        lp = _make_pack(_make_manifest_invariant(), "m_known")
        for tool in ["neuroquant_5.0", "neuroreader", "icometrix", "quantib_nd"]:
            sub = {"manifest": {"upstream_volumetry_tool": tool}}
            r = audit_cross_sheet(sub, [lp], dry_run=True)
            assert len(r.flags) == 0, f"Tool {tool!r} should be silent"


# ============================================================
# Row-shaped sheet execution
# ============================================================

class TestCategoricalNotInKnownSetRowShapedExecution:

    def test_all_known_no_flag(self):
        lp = _make_pack(_make_row_shaped_invariant(), "r_1")
        sub = {"patients": [
            {"patient_id": "p1", "age_band": "pediatric"},
            {"patient_id": "p2", "age_band": "adult"},
            {"patient_id": "p3", "age_band": "geriatric"},
        ]}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_one_unknown_one_flag(self):
        lp = _make_pack(_make_row_shaped_invariant(), "r_2")
        sub = {"patients": [
            {"patient_id": "p1", "age_band": "pediatric"},
            {"patient_id": "p2", "age_band": "neonate"},  # unknown
            {"patient_id": "p3", "age_band": "adult"},
        ]}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 1
        assert r.flags[0].join_key_values == {"patient_id": "p2"}
        assert r.flags[0].declared_tool == "neonate"

    def test_multiple_unknowns_flagged_each(self):
        lp = _make_pack(_make_row_shaped_invariant(), "r_3")
        sub = {"patients": [
            {"patient_id": "p1", "age_band": "neonate"},      # unknown
            {"patient_id": "p2", "age_band": "fetal"},        # unknown
            {"patient_id": "p3", "age_band": "adult"},
            {"patient_id": "p4", "age_band": "centenarian"},  # unknown
        ]}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 3
        flagged_patients = sorted(f.join_key_values["patient_id"] for f in r.flags)
        assert flagged_patients == ["p1", "p2", "p4"]

    def test_row_missing_field_silent(self):
        lp = _make_pack(_make_row_shaped_invariant(), "r_4")
        sub = {"patients": [
            {"patient_id": "p1", "age_band": "adult"},
            {"patient_id": "p2"},  # no age_band
        ]}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_row_field_null_silent(self):
        lp = _make_pack(_make_row_shaped_invariant(), "r_5")
        sub = {"patients": [{"patient_id": "p1", "age_band": None}]}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_empty_sheet_silent(self):
        lp = _make_pack(_make_row_shaped_invariant(), "r_6")
        sub = {"patients": []}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 0

    def test_row_with_missing_join_key_still_flagged_with_partial_key(self):
        """If a row has the source field but missing some join keys, the flag
        is still emitted -- the row's source value is what matters."""
        lp = _make_pack(_make_row_shaped_invariant(), "r_7")
        sub = {"patients": [{"age_band": "neonate"}]}  # missing patient_id
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 1
        # join_key_values dict drops None values
        assert r.flags[0].join_key_values == {}


# ============================================================
# Determinism
# ============================================================

class TestCategoricalNotInKnownSetDeterminism:

    def test_flag_id_deterministic(self):
        lp = _make_pack(_make_manifest_invariant(), "d_1")
        sub = {"manifest": {"upstream_volumetry_tool": "freesurfer"}}
        r1 = audit_cross_sheet(sub, [lp], dry_run=True)
        r2 = audit_cross_sheet(sub, [lp], dry_run=True)
        assert r1.flags[0].flag_id == r2.flags[0].flag_id

    def test_distinct_unknown_values_produce_distinct_flag_ids(self):
        lp = _make_pack(_make_manifest_invariant(), "d_2")
        r_a = audit_cross_sheet(
            {"manifest": {"upstream_volumetry_tool": "freesurfer"}}, [lp], dry_run=True,
        )
        r_b = audit_cross_sheet(
            {"manifest": {"upstream_volumetry_tool": "vuno"}}, [lp], dry_run=True,
        )
        assert r_a.flags[0].flag_id != r_b.flags[0].flag_id

    def test_flag_id_is_hex_sha256(self):
        lp = _make_pack(_make_manifest_invariant(), "d_3")
        sub = {"manifest": {"upstream_volumetry_tool": "unknown_tool"}}
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        flag_id = r.flags[0].flag_id
        assert len(flag_id) == 64
        int(flag_id, 16)

    def test_known_values_ordering_does_not_affect_flag_id(self):
        """The payload hashes sorted(known_values) so order in YAML is
        documentation-only and doesn't change flag_ids."""
        lp_a = _make_pack(_make_manifest_invariant(known_values=["a", "b", "c"]), "d_4a")
        lp_b = _make_pack(_make_manifest_invariant(known_values=["c", "b", "a"]), "d_4b")
        # Same unknown value -> same flag_id (because pack_id encoded in flag, but
        # we use yaml_sha256='0'*64 for both test packs so they're comparable on the
        # invariant content)
        sub = {"manifest": {"upstream_volumetry_tool": "x"}}
        r_a = audit_cross_sheet(sub, [lp_a], dry_run=True)
        r_b = audit_cross_sheet(sub, [lp_b], dry_run=True)
        # Same flag_id because sorted(known_values) is identical
        assert r_a.flags[0].flag_id == r_b.flags[0].flag_id


# ============================================================
# Integration with shipped tool_declaration_consistency v1.1.0
# ============================================================

class TestShippedPackV1_1_0:
    """Integration tests against the actual shipped pack (post-v1.11.0a8)."""

    def test_shipped_pack_has_5_invariants(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert len(lp.invariantpack.invariants) == 5
        names = [inv.name for inv in lp.invariantpack.invariants]
        assert "upstream_volumetry_tool_in_known_set" in names

    def test_shipped_pack_known_tool_audit_clean(self):
        """A submission declaring a known tool with in-range values should
        produce ZERO flags from the shipped pack."""
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        sub = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [{
                "patient_id": "p1", "visit_id": "v1",
                "hippocampal_volume_total_cm3": 4.0,  # interior of 2.8-5.0
            }],
        }
        r = audit_cross_sheet(sub, [lp], dry_run=False)
        assert len(r.flags) == 0

    def test_shipped_pack_unknown_tool_emits_info(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        sub = {
            "manifest": {"upstream_volumetry_tool": "freesurfer"},
            "biomarkers": [{
                "patient_id": "p1", "visit_id": "v1",
                "hippocampal_volume_total_cm3": 3.5,
            }],
        }
        r = audit_cross_sheet(sub, [lp], dry_run=False)
        info_flags = [f for f in r.flags if f.severity == "info"]
        assert len(info_flags) == 1
        assert info_flags[0].invariant_name == "upstream_volumetry_tool_in_known_set"
        assert info_flags[0].declared_tool == "freesurfer"

    def test_shipped_pack_yaml_sha256_locked(self):
        """v1.11.0a8 pack version 1.1.0 yaml_sha256 lock."""
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.yaml_sha256 == (
            "cf148e31edce12e9b856a226bd598970431013ebd72d2c05897360dc4b9edba4"
        )

    def test_shipped_pack_version_is_1_1_0(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.invariantpack.pack_version == "1.1.0"

    def test_shipped_pack_status_is_production(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.status == InvariantPackStatus.PRODUCTION


# ============================================================
# Regression: prior packs and condition types still work
# ============================================================

class TestNoRegressionsFromNotInKnownSet:

    def test_genotype_phenotype_pack_yaml_sha256_unchanged(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        assert lp.yaml_sha256 == (
            "c988ffeddc31d04121cc012dcb32fe1e09f64ad4ddfb95e22b772a32788a1a40"
        )

    def test_genotype_phenotype_pack_still_works(self):
        from neurotcs.cross_sheet import load_invariantpack
        lp = load_invariantpack("cross_sheet/genotype_phenotype_consistency")
        sub = {
            "patients": [{"patient_id": "p1", "apoe_genotype": "e4/e4"}],
            "predictions": [
                {"patient_id": "p1", "visit_id": "v1", "age_years": 76, "ad_dementia_status": 0},
                {"patient_id": "p1", "visit_id": "v2", "age_years": 88, "ad_dementia_status": 0},
            ],
        }
        r = audit_cross_sheet(sub, [lp], dry_run=True)
        assert len(r.flags) == 1
        assert r.flags[0].severity == "info"

"""
Tests for the Quantib ND invariant (v1.11.0a4 NEW).

Verifies:
- Quantib ND invariant loads as the 4th invariant in tool_declaration_consistency
- Execution: in-range / below-range / above-range scenarios
- Discipline: >=5 endorsing bodies, international_consensus, Rotterdam cited, K213737 cited
- Does NOT regress NeuroQuant / NeuroReader / icometrix behavior
"""

from __future__ import annotations

from neurotcs.clinical_ranges.schema import CitationStrength
from neurotcs.cross_sheet import audit_cross_sheet, load_invariantpack


class TestQuantibNdInvariantInPack:

    def test_pack_now_has_4_invariants(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert len(lp.invariantpack.invariants) == 4

    def test_quantib_invariant_is_4th(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.name == "quantib_nd_implies_hippocampal_volume_in_normative_range"

    def test_quantib_invariant_source_trigger(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.condition.source_sheet == "manifest"
        assert inv.condition.source_field == "upstream_volumetry_tool"
        assert inv.condition.source_value == "quantib_nd"

    def test_quantib_invariant_target(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.condition.target_sheet == "biomarkers"
        assert inv.condition.target_field == "hippocampal_volume_total_cm3"

    def test_quantib_invariant_range_2_8_to_5_0_cm3(self):
        """Quantib ND uses 5th-percentile cutoff on Rotterdam Scan Study
        normative; matches NeuroQuant range structurally (both 5th-percentile)."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.condition.target_range.lo == 2.8
        assert inv.condition.target_range.hi == 5.0
        assert inv.condition.target_unit == "cm3"

    def test_quantib_invariant_severity_warning(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.flag_severity == "warning"

    def test_quantib_invariant_citation_strength(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_quantib_invariant_has_5plus_endorsing_bodies(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert len(inv.citation.endorsing_bodies) >= 5

    def test_quantib_invariant_cites_rotterdam_scan_study(self):
        """The Rotterdam Scan Study is Quantib ND's normative database
        (~5,000 subjects, population-based, distinct from NeuroQuant's
        Cortechs database and NeuroReader's ADNI database)."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        joined = inv.citation.citation_text + " ".join(inv.citation.endorsing_bodies)
        assert "Rotterdam" in joined

    def test_quantib_invariant_cites_fda_k213737(self):
        """K213737 is the FDA 510(k) clearance number for Quantib ND."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        joined = inv.citation.citation_text + " ".join(inv.citation.endorsing_bodies)
        assert "K213737" in joined

    def test_quantib_invariant_public_url_is_fda(self):
        """The public URL should point to the FDA accessdata 510(k) PDF."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[3]
        assert inv.citation.public_url is not None
        assert "accessdata.fda.gov" in inv.citation.public_url
        assert "K213737" in inv.citation.public_url


class TestQuantibNdExecution:

    def test_in_range_no_flag(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "quantib_nd"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 0

    def test_below_range_flags(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "quantib_nd"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 2.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        flag = result.flags[0]
        assert flag.severity == "warning"
        assert flag.declared_tool == "quantib_nd"
        assert flag.observed_value == 2.0
        assert flag.expected_range_lo == 2.8
        assert flag.expected_range_hi == 5.0

    def test_above_range_flags(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "quantib_nd"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 6.5},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].observed_value == 6.5

    def test_quantib_invariant_does_not_trigger_for_other_tools(self):
        """Quantib invariant must only match manifest.upstream_volumetry_tool == 'quantib_nd'."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "freesurfer_7.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        # No invariant should match freesurfer_7.0
        assert len(result.flags) == 0


class TestRegressionNoOtherInvariantsBroken:
    """Adding Quantib ND must NOT regress NeuroQuant / NeuroReader / icometrix behavior."""

    def test_neuroquant_still_works(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroquant_5.0"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 1.5},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].expected_range_lo == 2.8
        assert result.flags[0].expected_range_hi == 5.0

    def test_neuroreader_still_uses_narrower_range(self):
        """NeuroReader uses 25th-percentile cutoff (range [3.5, 5.5]).
        Must not be overridden by the new Quantib invariant having a
        different range."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroreader"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].expected_range_lo == 3.5
        assert result.flags[0].expected_range_hi == 5.5

    def test_icometrix_still_works(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "icometrix"},
            "biomarkers": [
                {"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 4.0},
            ],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        # 4.0 is in range [2.8, 5.0] -> no flag
        assert len(result.flags) == 0


class TestAllFourToolsSimultaneously:
    """A single audit run should evaluate all 4 invariants but only emit
    flags for the invariant whose tool matches manifest.upstream_volumetry_tool."""

    def test_audit_evaluates_all_4_invariants(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        submission = {
            "manifest": {"upstream_volumetry_tool": "quantib_nd"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.5}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert result.n_invariants_evaluated == 4

    def test_only_matching_tool_emits_flags(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        # An out-of-range value, but manifest declares neuroreader
        # -> only the neuroreader invariant matches; the other 3 don't
        submission = {
            "manifest": {"upstream_volumetry_tool": "neuroreader"},
            "biomarkers": [{"patient_id": "p1", "visit_id": "v1", "hippocampal_volume_total_cm3": 3.0}],
        }
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        assert len(result.flags) == 1
        assert result.flags[0].declared_tool == "neuroreader"

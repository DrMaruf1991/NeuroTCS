"""
Tests for neurotcs.cross_sheet.loader (Layer 3 pack loading).

Verifies:
- list_invariantpacks() enumerates the shipped pack
- load_invariantpack() loads tool_declaration_consistency
- The yaml_sha256 is locked to its v1.11.0a1 golden value
  (cross-platform stability check, parallel to Layer 2's v1.10.1
  yaml_sha256 mechanism)
- The shipped pack ships at SKELETON status, refusing audit
- All world-class discipline gates hold:
  * citation_strength == international_consensus for the single shipped invariant
  * citation has >=5 endorsing_bodies
  * citation has a public URL
  * the anchor citation points to Bethlehem 2022 (PMID 35388223)
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges.schema import CitationStrength
from neurotcs.cross_sheet import (
    InvariantPackStatus,
    list_invariantpacks,
    load_invariantpack,
)

# ============================================================
# v1.11.0a1 GOLDEN HASHES (DO NOT change without bumping pack_version)
# ============================================================

GOLDEN_YAML_SHA256_TOOL_DECL = (
    "a1dff4f5f110221f425e27e888fb0d65586f33ae9e871bb50a540cbc217fec9f"
)


class TestListInvariantPacks:

    def test_listing_includes_tool_declaration_consistency(self):
        packs = list_invariantpacks()
        names = {p["name"] for p in packs}
        assert "cross_sheet/tool_declaration_consistency" in names

    def test_listing_returns_dict_per_pack(self):
        packs = list_invariantpacks()
        assert len(packs) >= 1
        for p in packs:
            assert "name" in p
            assert "status" in p

    def test_tool_declaration_pack_listed_at_research_preview(self):
        packs = list_invariantpacks()
        td = next(p for p in packs if p["name"] == "cross_sheet/tool_declaration_consistency")
        assert td["status"] == "research_preview"
        assert td["schema_version"] == "1.0.0"
        assert td["pack_version"] == "1.0.0"
        assert td["n_invariants"] == 3


class TestLoadInvariantPack:

    def test_loads_tool_declaration_consistency(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.invariantpack.invariantpack_id == "cross_sheet/tool_declaration_consistency@1.0.0"
        assert lp.status == InvariantPackStatus.RESEARCH_PREVIEW

    def test_canonical_sha256_present(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert len(lp.canonical_sha256) == 64
        # Hex-only string
        int(lp.canonical_sha256, 16)  # raises ValueError if not hex

    def test_yaml_sha256_matches_golden(self):
        """The v1.11.0a1 yaml_sha256 of the tool_declaration_consistency
        pack must match the locked golden value. Any change in the
        normalized YAML bytes will change this hash and the test will
        fail -- enforcing that the pack contents are not silently mutated.

        Cross-platform stability is verified by Layer 2's v1.10.1
        yaml_sha256 mechanism (CRLF/CR -> LF normalization, single
        trailing newline, UTF-8) which we reuse here.
        """
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp.yaml_sha256 == GOLDEN_YAML_SHA256_TOOL_DECL, (
            f"yaml_sha256 drift: expected {GOLDEN_YAML_SHA256_TOOL_DECL}, "
            f"got {lp.yaml_sha256}. The pack YAML has changed since v1.11.0a1."
        )

    def test_missing_pack_raises_FileNotFoundError(self):
        with pytest.raises(FileNotFoundError):
            load_invariantpack("cross_sheet/does_not_exist")


class TestShippedPackContents:
    """Verify the v1.11.0a2 shipped pack contents in detail (3 invariants)."""

    def test_pack_has_exactly_three_invariants_in_v1_11_0a2(self):
        """v1.11.0a2 ships exactly 3 invariants: NeuroQuant 5.0, NeuroReader,
        icometrix icobrain. Session #3 adds the remaining 2 (Quantib ND + catch-all)."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert len(lp.invariantpack.invariants) == 3

    def test_shipped_invariants_names(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        names = [inv.name for inv in lp.invariantpack.invariants]
        assert names == [
            "neuroquant_5_0_implies_hippocampal_volume_in_normative_range",
            "neuroreader_implies_hippocampal_volume_in_normative_range",
            "icometrix_icobrain_implies_hippocampal_volume_in_plausible_range",
        ]

    def test_neuroquant_invariant_range_2_8_to_5_0(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.source_value == "neuroquant_5.0"
        assert inv.condition.target_range.lo == 2.8
        assert inv.condition.target_range.hi == 5.0

    def test_neuroreader_invariant_range_3_5_to_5_5(self):
        """NeuroReader uses 25th-percentile cutoff (more conservative than
        NeuroQuant's 5th); higher lower bound."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[1]
        assert inv.condition.source_value == "neuroreader"
        assert inv.condition.target_range.lo == 3.5
        assert inv.condition.target_range.hi == 5.5

    def test_icometrix_invariant_range_2_8_to_5_0(self):
        """icometrix icobrain has no fixed cutoff; uses Bethlehem
        plausibility range."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[2]
        assert inv.condition.source_value == "icometrix"
        assert inv.condition.target_range.lo == 2.8
        assert inv.condition.target_range.hi == 5.0

    def test_all_shipped_invariants_are_categorical_implies_range(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        for inv in lp.invariantpack.invariants:
            assert inv.condition.type == "categorical_implies_range"

    def test_all_shipped_invariants_target_hippocampal_volume(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        for inv in lp.invariantpack.invariants:
            assert inv.condition.target_sheet == "biomarkers"
            assert inv.condition.target_field == "hippocampal_volume_total_cm3"
            assert inv.condition.target_unit == "cm3"

    def test_all_shipped_invariants_at_warning_severity(self):
        """Tier 1 (within Bethlehem +/-10%) uses warning severity."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        for inv in lp.invariantpack.invariants:
            assert inv.flag_severity == "warning"
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.type == "categorical_implies_range"

    def test_shipped_invariant_source_is_manifest_upstream_volumetry_tool(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.source_sheet == "manifest"
        assert inv.condition.source_field == "upstream_volumetry_tool"
        assert inv.condition.source_value == "neuroquant_5.0"

    def test_shipped_invariant_target_is_biomarkers_hippocampal_volume(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.target_sheet == "biomarkers"
        assert inv.condition.target_field == "hippocampal_volume_total_cm3"

    def test_shipped_invariant_target_range_is_2_8_to_5_0_cm3(self):
        """Per Cortechs.ai NeuroQuant 5.0 normative database white paper
        + Bethlehem 2022 cross-validation: 5th-95th percentile bilateral
        hippocampal volume in adults is approximately 2.8-5.0 cm^3."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.condition.target_range.lo == 2.8
        assert inv.condition.target_range.hi == 5.0
        assert inv.condition.target_unit == "cm3"

    def test_shipped_invariant_flag_severity_is_warning(self):
        """Per LAYER_3_DESIGN.md section 12 Q2 resolution: Tier 1
        flagging (within Bethlehem +/-10% but outside declared tool's
        range) uses warning severity."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.flag_severity == "warning"


class TestWorldClassDiscipline:
    """v1.11.0a1 world-class evidence-bar checks for the shipped invariant.

    The pack ships at SKELETON, but the invariants already shipped must
    meet the same evidence bar that will be required at production
    promotion -- so we test the discipline gates now."""

    def test_shipped_invariant_at_international_consensus(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_shipped_invariant_has_5plus_endorsing_bodies(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert len(inv.citation.endorsing_bodies) >= 5, (
            f"v1.11.0a1 world-class bar: every shipped invariant requires "
            f">=5 endorsing bodies; got {len(inv.citation.endorsing_bodies)}"
        )

    def test_shipped_invariant_has_public_url(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        inv = lp.invariantpack.invariants[0]
        assert inv.citation.public_url, "Shipped invariant must cite a public URL"

    def test_anchor_citation_is_bethlehem_2022(self):
        """The anchor citation must point to Bethlehem 2022 Nature
        lifespan brain charts (PMID 35388223), which is the Tier 2
        tool-agnostic fallback range per the two-tier flagging design."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        anchor = lp.invariantpack.anchor_citation
        assert anchor.citation_pmid == "35388223"
        assert anchor.citation_doi == "10.1038/s41586-022-04554-y"

    def test_anchor_endorsing_bodies_include_fda(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        anchor = lp.invariantpack.anchor_citation
        joined = " ".join(anchor.endorsing_bodies)
        assert "FDA" in joined
        assert "Bethlehem" in joined or "Brain Chart" in joined
        assert "Cortechs.ai" in joined or "NeuroQuant" in joined


class TestResearchPreviewFailClosedGate:
    """Layer 3 fail-closed discipline parallel to Layer 2: a non-production
    pack must refuse audit. In v1.11.0a2, the shipped pack is RESEARCH_PREVIEW,
    so the pack-level assert_usable_for_audit() must still refuse (only
    audit_cross_sheet() in dry_run mode accepts research_preview)."""

    def test_load_succeeds_for_research_preview(self):
        """A research_preview pack must load and validate."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        assert lp is not None
        assert lp.status == InvariantPackStatus.RESEARCH_PREVIEW

    def test_assert_usable_for_audit_refuses_research_preview(self):
        """The fail-closed gate on the loaded pack must refuse."""
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        with pytest.raises(ValueError, match="research_preview"):
            lp.assert_usable_for_audit()

    def test_assert_usable_for_audit_message_mentions_production_requirement(self):
        lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
        try:
            lp.assert_usable_for_audit()
            pytest.fail("expected ValueError")
        except ValueError as e:
            msg = str(e)
            assert "production" in msg.lower()
            assert "research_preview" in msg.lower()

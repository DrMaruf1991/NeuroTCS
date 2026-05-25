"""
Behavior tests for the world-class production pack
mri_volumetrics/structural_volumetry_consensus@1.0.0.

Verifies that the pack correctly encodes:
  - Bethlehem 2022 lifespan brain charts (n=101,457, PMID 35388223) as anchor
  - Desikan 2006 atlas (PMID 16530430) and Potvin 2017 normative (PMID 28412442)
  - ENIGMA + Rosen 2018 Euler number QC thresholds (PMID 29278793)
  - Bakkour 2009 AD cortical signature (PMID 19261208)
  - FDA 510(k) cleared volumetric AI tools as endorsing bodies
  - All Tier-1 bounds at citation_strength=international_consensus per the
    world-class evidence bar (>=5 endorsing bodies, public URL each).
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import CitationStrength, RangePackStatus


@pytest.fixture(scope="module")
def vol_pack():
    return load_rangepack("mri_volumetrics/structural_volumetry_consensus")


class TestStructuralVolumetryPackStructure:

    def test_pack_is_production_status(self, vol_pack):
        assert vol_pack.rangepack.status == RangePackStatus.PRODUCTION

    def test_pack_has_twelve_measurements(self, vol_pack):
        assert len(vol_pack.rangepack.measurements) == 12

    def test_pack_covers_expected_names(self, vol_pack):
        expected = {
            "hippocampal_volume_total_mm3",
            "hippocampal_volume_left_mm3",
            "hippocampal_volume_right_mm3",
            "amygdala_volume_total_mm3",
            "lateral_ventricle_volume_total_mm3",
            "total_intracranial_volume_eTIV_cm3",
            "mean_cortical_thickness_mm",
            "entorhinal_cortex_thickness_left_mm",
            "entorhinal_cortex_thickness_right_mm",
            "euler_number_left_hemisphere",
            "euler_number_right_hemisphere",
            "upstream_volumetry_tool",
        }
        assert vol_pack.rangepack.covered_names() == frozenset(expected)

    def test_every_bound_is_international_consensus(self, vol_pack):
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS, (
                    f"Production pack structural_volumetry_consensus measurement "
                    f"{m.name} bound {b.bound_type.value} has citation_strength="
                    f"{b.citation_strength.value!r}, expected international_consensus."
                )

    def test_every_bound_has_5plus_endorsing_bodies(self, vol_pack):
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                assert len(b.citation.endorsing_bodies) >= 5, (
                    f"Bound {m.name}/{b.bound_type.value} has only "
                    f"{len(b.citation.endorsing_bodies)} endorsing bodies"
                )

    def test_every_bound_has_public_url(self, vol_pack):
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation.public_url, (
                    f"Bound {m.name}/{b.bound_type.value} has no public_url"
                )


class TestAnchorAndPrimaryCitations:

    def test_anchor_citation_is_bethlehem_2022(self, vol_pack):
        """The anchor citation must be Bethlehem 2022 Nature lifespan brain charts."""
        anchor = vol_pack.rangepack.anchor_citation
        assert anchor.citation_pmid == "35388223"
        assert anchor.citation_doi == "10.1038/s41586-022-04554-y"
        assert "nature.com" in (anchor.public_url or "")

    def test_anchor_endorsing_bodies_include_bethlehem_and_fda(self, vol_pack):
        bodies = vol_pack.rangepack.anchor_citation.endorsing_bodies
        joined = " ".join(bodies)
        assert "Bethlehem" in joined
        assert "FDA" in joined
        assert "Desikan" in joined
        assert "ENIGMA" in joined
        assert "FreeSurfer" in joined

    def test_bethlehem_pmid_anchors_multiple_bounds(self, vol_pack):
        """PMID 35388223 (Bethlehem 2022) should anchor many bounds."""
        bethlehem_count = 0
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                if b.citation.citation_pmid == "35388223":
                    bethlehem_count += 1
        assert bethlehem_count >= 20, (
            f"Bethlehem 2022 should anchor many bounds; got {bethlehem_count}"
        )

    def test_potvin_pmid_anchors_cortical_thickness_bounds(self, vol_pack):
        """PMID 28412442 (Potvin 2017) should appear in cortical thickness bounds."""
        potvin_count = 0
        for m in vol_pack.rangepack.measurements:
            if "thickness" not in m.name and "cortical" not in m.name:
                continue
            for b in m.bounds:
                if b.citation.citation_pmid == "28412442":
                    potvin_count += 1
        assert potvin_count >= 4

    def test_rosen_pmid_anchors_euler_bounds(self, vol_pack):
        """PMID 29278793 (Rosen 2018) should anchor every Euler number bound."""
        for m in vol_pack.rangepack.measurements:
            if "euler" not in m.name:
                continue
            for b in m.bounds:
                assert b.citation.citation_pmid == "29278793", (
                    f"Euler bound {m.name}/{b.bound_type.value} should cite Rosen 2018"
                )

    def test_bakkour_pmid_anchors_entorhinal_bounds(self, vol_pack):
        """PMID 19261208 (Bakkour 2009) should appear in entorhinal cortex bounds."""
        bakkour_count = 0
        for m in vol_pack.rangepack.measurements:
            if "entorhinal" not in m.name:
                continue
            for b in m.bounds:
                if b.citation.citation_pmid == "19261208":
                    bakkour_count += 1
        assert bakkour_count >= 2


class TestEndorsingBodies:

    def test_bethlehem_consortium_in_endorsing_bodies(self, vol_pack):
        """The Bethlehem 2022 Brain Chart Consortium should endorse many bounds."""
        found = False
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                if any("Bethlehem" in body for body in b.citation.endorsing_bodies):
                    found = True
                    break
        assert found, "Bethlehem 2022 Brain Chart Consortium not found in endorsing bodies"

    def test_fda_cleared_tools_in_endorsing_bodies(self, vol_pack):
        """FDA-cleared volumetric AI tools should appear as endorsing bodies."""
        tools_found = {
            "NeuroQuant": False,
            "NeuroReader": False,
        }
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                joined = " ".join(b.citation.endorsing_bodies)
                if "NeuroQuant" in joined:
                    tools_found["NeuroQuant"] = True
                if "NeuroReader" in joined:
                    tools_found["NeuroReader"] = True
        for tool, found in tools_found.items():
            assert found, f"{tool} not found in any endorsing_bodies list"

    def test_enigma_consortium_in_endorsing_bodies(self, vol_pack):
        """ENIGMA Consortium should endorse many bounds."""
        found = False
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                if any("ENIGMA" in body for body in b.citation.endorsing_bodies):
                    found = True
                    break
        assert found

    def test_adni_in_endorsing_bodies(self, vol_pack):
        """ADNI should appear as endorsing body in many bounds."""
        count = 0
        for m in vol_pack.rangepack.measurements:
            for b in m.bounds:
                if any("ADNI" in body for body in b.citation.endorsing_bodies):
                    count += 1
        assert count >= 10


class TestSpecificMeasurementBounds:
    """Verify specific numeric bounds against the evidence."""

    def test_hippocampal_total_bounds(self, vol_pack):
        """Hippocampal total: hard_min=2000, plausible_min=2800, plausible_max=5000, hard_max=6000."""
        m = vol_pack.rangepack.get_measurement("hippocampal_volume_total_mm3")
        assert m is not None
        bound_map = {b.bound_type.value: b.value for b in m.bounds}
        assert bound_map["hard_min"] == 2000.0
        assert bound_map["plausible_min"] == 2800.0
        assert bound_map["plausible_max"] == 5000.0
        assert bound_map["hard_max"] == 6000.0

    def test_etiv_bounds(self, vol_pack):
        """eTIV: hard_min=1100, plausible_min=1300, plausible_max=1900, hard_max=2100."""
        m = vol_pack.rangepack.get_measurement("total_intracranial_volume_eTIV_cm3")
        assert m is not None
        bound_map = {b.bound_type.value: b.value for b in m.bounds}
        assert bound_map["hard_min"] == 1100.0
        assert bound_map["plausible_min"] == 1300.0
        assert bound_map["plausible_max"] == 1900.0
        assert bound_map["hard_max"] == 2100.0

    def test_euler_threshold_is_rosen_2018_negative_217(self, vol_pack):
        """The ENIGMA Euler exclusion threshold of -217 must be encoded verbatim
        per Rosen 2018 (PMID 29278793)."""
        for hemi in ["left", "right"]:
            m = vol_pack.rangepack.get_measurement(f"euler_number_{hemi}_hemisphere")
            assert m is not None
            bound_map = {b.bound_type.value: b.value for b in m.bounds}
            assert bound_map["plausible_min"] == -217.0, (
                f"Euler {hemi} plausible_min must be -217 per Rosen 2018"
            )

    def test_entorhinal_thickness_bounds(self, vol_pack):
        """Entorhinal cortex thickness: hard_min=2.0, plausible_min=2.8, plausible_max=4.5, hard_max=5.5."""
        for hemi in ["left", "right"]:
            m = vol_pack.rangepack.get_measurement(f"entorhinal_cortex_thickness_{hemi}_mm")
            assert m is not None
            bound_map = {b.bound_type.value: b.value for b in m.bounds}
            assert bound_map["hard_min"] == 2.0
            assert bound_map["plausible_min"] == 2.8
            assert bound_map["plausible_max"] == 4.5
            assert bound_map["hard_max"] == 5.5


class TestToolDeclarationField:
    """The upstream_volumetry_tool field anticipates Layer 3 cross-sheet rules."""

    def test_tool_field_present(self, vol_pack):
        m = vol_pack.rangepack.get_measurement("upstream_volumetry_tool")
        assert m is not None

    def test_tool_field_lists_fda_tools(self, vol_pack):
        """The tool field's valid_values should enumerate FDA-cleared tools."""
        m = vol_pack.rangepack.get_measurement("upstream_volumetry_tool")
        # The valid_values is documented in description and listed via
        # citation.endorsing_bodies. Verify endorsers cover the FDA-cleared set:
        joined_bodies = " ".join(m.bounds[0].citation.endorsing_bodies)
        for tool in ["NeuroQuant", "NeuroReader", "Cortechs",
                     "icometrix", "Quantib", "VUNO", "Pixyl", "FreeSurfer"]:
            assert tool in joined_bodies, f"{tool} missing from tool-field endorsements"


class TestFreeSurferExtendedPack:
    """The companion research_preview pack must be loadable and refuse audit."""

    def test_pack_loads_at_research_preview(self):
        lp = load_rangepack("mri_volumetrics/freesurfer_extended")
        assert lp.rangepack.status == RangePackStatus.RESEARCH_PREVIEW

    def test_pack_has_at_least_15_measurements(self):
        lp = load_rangepack("mri_volumetrics/freesurfer_extended")
        assert len(lp.rangepack.measurements) >= 15

    def test_pack_refuses_audit(self):
        """research_preview packs must refuse audit_clinical_ranges."""
        import pandas as pd

        from neurotcs.clinical_ranges import audit_clinical_ranges
        lp = load_rangepack("mri_volumetrics/freesurfer_extended")
        df = pd.DataFrame({
            "patient_id": ["P1"], "visit_id": ["V1"],
            "measurement_name": ["thalamus_volume_left_mm3"],
            "value": [7000.0], "unit": ["mm^3"],
        })
        with pytest.raises(ValueError, match="status="):
            audit_clinical_ranges(df, lp)


class TestOldFreesurferPackDeprecated:
    """The v1.10.0-era mri_volumetrics/freesurfer pack must be deprecated
    with proper successor pointer in v1.10.2."""

    def test_old_pack_status_deprecated(self):
        lp = load_rangepack("mri_volumetrics/freesurfer")
        assert lp.rangepack.status == RangePackStatus.DEPRECATED

    def test_successor_points_to_new_production_pack(self):
        lp = load_rangepack("mri_volumetrics/freesurfer")
        assert lp.rangepack.deprecated_in_favor_of == (
            "mri_volumetrics/structural_volumetry_consensus@1.0.0"
        )

    def test_deprecation_reason_mentions_v1_10_2(self):
        lp = load_rangepack("mri_volumetrics/freesurfer")
        assert "v1.10.2" in (lp.rangepack.deprecation_reason or "")

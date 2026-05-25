"""
Behavior tests for the world-class production pack
pet_amyloid/centiloid_consensus@1.0.0.

Verifies that the pack correctly encodes:
  - Klunk 2015 0/100 CL anchor points (via hard_min/hard_max)
  - Doré/Rowe 2020 5-tier Centiloid categorization
  - TRAILBLAZER-ALZ 4 amyloid clearance threshold (<24.1 CL)
  - All bounds at citation_strength=international_consensus per the
    world-class evidence bar (≥5 endorsing bodies, public URL each).
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack
from neurotcs.clinical_ranges.schema import CitationStrength


@pytest.fixture(scope="module")
def cl_pack():
    return load_rangepack("pet_amyloid/centiloid_consensus")


class TestCentiloidPackStructure:

    def test_pack_is_production_status(self, cl_pack):
        from neurotcs.clinical_ranges.schema import RangePackStatus
        assert cl_pack.rangepack.status == RangePackStatus.PRODUCTION

    def test_pack_has_three_measurements(self, cl_pack):
        assert len(cl_pack.rangepack.measurements) == 3

    def test_pack_covers_expected_names(self, cl_pack):
        expected = {
            "centiloid_value",
            "centiloid_category",
            "centiloid_clearance_threshold",
        }
        assert cl_pack.rangepack.covered_names() == frozenset(expected)

    def test_every_bound_is_international_consensus(self, cl_pack):
        for m in cl_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS, (
                    f"Production pack centiloid_consensus measurement {m.name} bound "
                    f"{b.bound_type.value} has citation_strength="
                    f"{b.citation_strength.value!r}, expected international_consensus."
                )

    def test_every_bound_has_5plus_endorsing_bodies(self, cl_pack):
        for m in cl_pack.rangepack.measurements:
            for b in m.bounds:
                assert len(b.citation.endorsing_bodies) >= 5, (
                    f"Bound {m.name}/{b.bound_type.value} has only "
                    f"{len(b.citation.endorsing_bodies)} endorsing bodies"
                )

    def test_every_bound_has_public_url(self, cl_pack):
        for m in cl_pack.rangepack.measurements:
            for b in m.bounds:
                assert b.citation.public_url, (
                    f"Bound {m.name}/{b.bound_type.value} has no public_url"
                )

    def test_anchor_citation_is_klunk_2015(self, cl_pack):
        """The anchor citation must be Klunk et al. 2015 PMID 25443857."""
        anchor = cl_pack.rangepack.anchor_citation
        assert anchor.citation_pmid == "25443857"
        assert "PMC4300247" in (anchor.public_url or "")

    def test_klunk_pmid_appears_in_bound_citations(self, cl_pack):
        """The Klunk 2015 PMID should appear across multiple bound citations."""
        klunk_count = 0
        for m in cl_pack.rangepack.measurements:
            for b in m.bounds:
                if b.citation.citation_pmid == "25443857":
                    klunk_count += 1
        assert klunk_count >= 4, f"Klunk 2015 should anchor multiple bounds; got {klunk_count}"

    def test_endorsing_bodies_include_centiloid_working_group(self, cl_pack):
        """The Centiloid Working Group should endorse multiple bounds."""
        found = False
        for m in cl_pack.rangepack.measurements:
            for b in m.bounds:
                if any("Centiloid Working Group" in body for body in b.citation.endorsing_bodies):
                    found = True
                    break
        assert found

    def test_endorsing_bodies_include_eanm_and_snmmi(self, cl_pack):
        """Nuclear medicine societies must be endorsing bodies."""
        has_eanm = False
        has_snmmi = False
        for m in cl_pack.rangepack.measurements:
            for b in m.bounds:
                if any("EANM" in body for body in b.citation.endorsing_bodies):
                    has_eanm = True
                if any("SNMMI" in body for body in b.citation.endorsing_bodies):
                    has_snmmi = True
        assert has_eanm and has_snmmi

    def test_endorsing_bodies_include_amypad(self, cl_pack):
        """AMYPAD Consortium 2024 endorsement is required."""
        found = False
        for m in cl_pack.rangepack.measurements:
            for b in m.bounds:
                if any("AMYPAD" in body for body in b.citation.endorsing_bodies):
                    found = True
                    break
        assert found


class TestCentiloidValueBounds:
    """Verify the Klunk 2015 anchor-based bounds on centiloid_value."""

    def test_typical_negative_passes(self, cl_pack):
        """Young controls at 0 CL pass, slightly negative passes."""
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["centiloid_value"] * 3,
            "value": [0.0, -5.0, -8.0],
            "unit": ["CL"] * 3,
        })
        r = audit_clinical_ranges(df, cl_pack)
        assert r.n_flagged == 0

    def test_typical_ad_passes(self, cl_pack):
        """Values around 100 CL (typical AD) pass."""
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["centiloid_value"] * 3,
            "value": [80.0, 100.0, 150.0],
            "unit": ["CL"] * 3,
        })
        r = audit_clinical_ranges(df, cl_pack)
        assert r.n_flagged == 0

    def test_extreme_negative_flagged(self, cl_pack):
        """Values <-50 CL (hard_min) are biologically implausible."""
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["centiloid_value"],
            "value": [-80.0],
            "unit": ["CL"],
        })
        r = audit_clinical_ranges(df, cl_pack)
        # Crosses BOTH plausible_min (-10) AND hard_min (-50)
        assert r.n_flagged == 2
        assert any(f.bound_type == "hard_min" for f in r.flags)

    def test_extreme_positive_flagged(self, cl_pack):
        """Values >300 CL (hard_max) are biologically implausible."""
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["centiloid_value"],
            "value": [400.0],
            "unit": ["CL"],
        })
        r = audit_clinical_ranges(df, cl_pack)
        # Crosses BOTH plausible_max (200) AND hard_max (300)
        assert r.n_flagged == 2
        assert any(f.bound_type == "hard_max" for f in r.flags)


class TestCentiloidCategoryValidValues:
    """Verify the Doré/Rowe 2020 five-tier categorical set."""

    def test_all_five_tiers_pass(self, cl_pack):
        df = pd.DataFrame({
            "patient_id": [f"P{i}" for i in range(5)],
            "visit_id": ["V0"] * 5,
            "measurement_name": ["centiloid_category"] * 5,
            "value": ["negative", "uncertain", "moderate", "high", "very_high"],
            "unit": ["categorical"] * 5,
        })
        r = audit_clinical_ranges(df, cl_pack)
        assert r.n_flagged == 0

    def test_invalid_tier_flagged(self, cl_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["centiloid_category"],
            "value": ["positive"],  # not in the five-tier set
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, cl_pack)
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "invalid_categorical"


class TestCentiloidClearanceThreshold:
    """Verify the TRAILBLAZER-ALZ 4 clearance threshold and AMYPAD range."""

    def test_clearance_threshold_at_24_passes(self, cl_pack):
        """24 CL is the FDA-aligned donanemab clearance threshold."""
        df = pd.DataFrame({
            "patient_id": ["P1", "P2"],
            "visit_id": ["V0", "V0"],
            "measurement_name": ["centiloid_clearance_threshold"] * 2,
            "value": [24.0, 24.1],
            "unit": ["CL"] * 2,
        })
        r = audit_clinical_ranges(df, cl_pack)
        assert r.n_flagged == 0

    def test_clearance_threshold_below_amypad_lower_flagged(self, cl_pack):
        """Below ~20 CL crosses the AMYPAD 'reliably exclude' lower bound."""
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["centiloid_clearance_threshold"],
            "value": [10.0],  # below plausible_min=20
            "unit": ["CL"],
        })
        r = audit_clinical_ranges(df, cl_pack)
        # crosses plausible_min=20
        assert r.n_flagged == 1
        assert r.flags[0].bound_type == "plausible_min"

    def test_clearance_threshold_above_50_flagged(self, cl_pack):
        """Above 50 CL is beyond Doré 'moderate' tier — flagged as hard_max."""
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["centiloid_clearance_threshold"],
            "value": [60.0],
            "unit": ["CL"],
        })
        r = audit_clinical_ranges(df, cl_pack)
        # Crosses BOTH plausible_max (30) AND hard_max (50)
        assert r.n_flagged == 2
        assert any(f.bound_type == "hard_max" for f in r.flags)


class TestCentiloidAuditDeterminism:

    def test_same_input_same_flag_id(self, cl_pack):
        df = pd.DataFrame({
            "patient_id": ["P_extreme"],
            "visit_id": ["V0"],
            "measurement_name": ["centiloid_value"],
            "value": [500.0],
            "unit": ["CL"],
        })
        r1 = audit_clinical_ranges(df, cl_pack)
        r2 = audit_clinical_ranges(df, cl_pack)
        assert r1.flag_id == r2.flag_id
        assert r1.n_flagged == r2.n_flagged

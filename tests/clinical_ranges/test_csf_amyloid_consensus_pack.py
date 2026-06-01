"""
Behavior tests for csf_biomarkers/csf_amyloid_consensus@1.0.0.

Verifies FDA Lumipulse 510(k) K212622 cutoffs and AA AUR three-zone framework.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack
from neurotcs.clinical_ranges.schema import CitationStrength


@pytest.fixture(scope="module")
def csf_pack():
    return load_rangepack("csf_biomarkers/csf_amyloid_consensus")


class TestCsfAmyloidPackStructure:

    def test_pack_is_production(self, csf_pack):
        from neurotcs.clinical_ranges.schema import RangePackStatus
        assert csf_pack.rangepack.status == RangePackStatus.PRODUCTION

    def test_pack_has_four_measurements(self, csf_pack):
        assert len(csf_pack.rangepack.measurements) == 4

    def test_every_bound_is_international_consensus(self, csf_pack):
        """Primary (diagnostic / mathematical) bounds hold the international-
        consensus bar. v1.42.0 physiological_envelope bounds are a distinct,
        honestly-'derived' evidence class (derived from consensus cohort
        distributions, not a 5-body verbatim consensus) and are exempted."""
        for m in csf_pack.rangepack.measurements:
            for b in m.bounds:
                if getattr(b, "bound_semantic", "") == "physiological_envelope":
                    assert b.citation_strength == CitationStrength.DERIVED
                    continue
                assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS

    def test_every_bound_has_5plus_bodies(self, csf_pack):
        """Consensus bounds carry 5+ endorsing bodies; physiological_envelope
        bounds (a derived evidence class) carry the general >=2 minimum."""
        for m in csf_pack.rangepack.measurements:
            for b in m.bounds:
                if getattr(b, "bound_semantic", "") == "physiological_envelope":
                    assert len(b.citation.endorsing_bodies) >= 2
                else:
                    assert len(b.citation.endorsing_bodies) >= 5

    def test_fda_510k_url_present(self, csf_pack):
        """Lumipulse FDA 510(k) K212622 URL should appear in citations."""
        urls = [b.citation.public_url
                for m in csf_pack.rangepack.measurements
                for b in m.bounds]
        assert any("K212622" in (u or "") or "510k" in (u or "").lower() for u in urls)


class TestLumipulseRatio:

    def test_clearly_positive_value_flags_below_058(self, csf_pack):
        """Ratio of 0.040 is well below the 0.058 FDA cutoff — amyloid positive."""
        df = pd.DataFrame({
            "patient_id": ["P_positive"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.040],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        # value=0.040 is BELOW plausible_max=0.058 → passes (it's a valid "positive" reading)
        assert r.n_flagged == 0

    def test_amyloid_negative_value_not_flagged(self, csf_pack):
        """E-2026-011: a healthy amyloid-NEGATIVE ratio (0.10, above the old
        0.072 diagnostic cutoff) is biologically normal and must NOT be a range
        violation. The diagnostic cutoff is not a plausibility bound."""
        df = pd.DataFrame({
            "patient_id": ["P_neg"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.10],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        # within the mathematical [0, 1] envelope -> no flag
        assert r.n_flagged == 0

    def test_intermediate_zone_not_flagged(self, csf_pack):
        """E-2026-011: a ratio of 0.065 (former 0.058-0.072 'intermediate'
        zone) is within the physiological envelope and must NOT be flagged.
        Diagnostic-cutoff interpretation belongs to the cross-sheet
        amyloid-status concordance layer, not this range pack."""
        df = pd.DataFrame({
            "patient_id": ["P_intermediate"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.065],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 0

    def test_mathematically_impossible_ratio_flagged(self, csf_pack):
        """E-2026-011 regression: values OUTSIDE the mathematical [0, 1] bound
        are hard violations (ratios are bounded [0,1] per K212622). v1.42.0
        adds a physiological_envelope plausible_max at 0.16 (human CSF Aβ42/40
        lies well below 0.16); a value of 1.5 therefore trips BOTH the
        mathematical hard_max AND the physiological envelope, while -0.01 trips
        hard_min."""
        df = pd.DataFrame({
            "patient_id": ["P_lo", "P_hi"],
            "visit_id": ["V0", "V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"] * 2,
            "value": [-0.01, 1.5],
            "unit": ["ratio", "ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 3
        assert {f.bound_type for f in r.flags} == {"hard_min", "hard_max", "plausible_max"}

    def test_physiologically_impossible_ratio_flagged(self, csf_pack):
        """v1.42.0: a ratio inside the mathematical [0,1] bound but far above
        the physiological envelope (e.g. 0.95 -- a unit/transcription error)
        is flagged as an implausibility by the physiological_envelope
        plausible_max, even though it passes the [0,1] hard bound."""
        df = pd.DataFrame({
            "patient_id": ["P_err"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.95],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        envelope = [f for f in r.flags if f.bound_type == "plausible_max"]
        assert len(envelope) == 1
        assert envelope[0].bound_semantic == "physiological_envelope"


class TestCsfAbeta42:

    def test_normal_range_passes(self, csf_pack):
        """500-1500 pg/mL is the typical range in clinical CSF."""
        df = pd.DataFrame({
            "patient_id": ["P1", "P2", "P3"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["csf_abeta42_pgml"] * 3,
            "value": [500.0, 1000.0, 1500.0],
            "unit": ["pg/mL"] * 3,
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 0

    def test_implausibly_high_flagged(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P_err"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_pgml"],
            "value": [6000.0],  # exceeds hard_max=5000
            "unit": ["pg/mL"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert any(f.bound_type == "hard_max" for f in r.flags)


class TestCsfAmyloidStatus:

    def test_three_zones_pass(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P0", "P1", "P2"],
            "visit_id": ["V0"] * 3,
            "measurement_name": ["csf_amyloid_status"] * 3,
            "value": ["negative", "intermediate", "positive"],
            "unit": ["categorical"] * 3,
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 0

    def test_invalid_zone_flagged(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_amyloid_status"],
            "value": ["likely_positive"],  # not in this pack's set
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, csf_pack)
        assert r.n_flagged == 1


class TestCsfDeterminism:

    def test_same_input_same_flag_id(self, csf_pack):
        df = pd.DataFrame({
            "patient_id": ["P1"],
            "visit_id": ["V0"],
            "measurement_name": ["csf_abeta42_40_ratio_lumipulse"],
            "value": [0.065],
            "unit": ["ratio"],
        })
        r1 = audit_clinical_ranges(df, csf_pack)
        r2 = audit_clinical_ranges(df, csf_pack)
        assert r1.flag_id == r2.flag_id

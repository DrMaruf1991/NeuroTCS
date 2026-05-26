"""
Tests for tau_pet/tau_consensus rangepack (v1.15.0).

The Tau PET production pack encodes the FDA-approved visual interpretation
method for flortaucipir (Tauvid, FDA NDA approval May 28, 2020):
  - 1.65-fold cerebellar background threshold (Tauvid PI §2.4 verbatim)
  - positive/negative visual read categories
  - cerebellum reference region (FDA-specified)
  - 6 FDA-named target regions
  - 80-100 min post-injection imaging window
  - 370 MBq (10 mCi) recommended dose

All bounds at international_consensus citation_strength with >=5 endorsers.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK_NAME = "tau_pet/tau_consensus"


@pytest.fixture(scope="module")
def tau_pack():
    return load_rangepack(PACK_NAME)


# ============================================================
# Pack-level invariants
# ============================================================


def test_pack_loads(tau_pack):
    assert tau_pack.rangepack.rangepack_id == "tau_pet/tau_consensus@1.0.0"


def test_pack_is_production(tau_pack):
    assert tau_pack.rangepack.status == RangePackStatus.PRODUCTION


def test_pack_has_six_measurements(tau_pack):
    assert len(tau_pack.rangepack.measurements) == 6


def test_pack_measurement_names_complete(tau_pack):
    names = {m.name for m in tau_pack.rangepack.measurements}
    expected = {
        "tau_pet_neocortical_uptake_ratio_flortaucipir",
        "tau_pet_visual_read_status_flortaucipir",
        "tau_pet_reference_region",
        "tau_pet_target_region",
        "tau_pet_imaging_uptake_window_min",
        "tau_pet_dose_mbq",
    }
    assert names == expected


def test_pack_yaml_sha256_locked(tau_pack):
    """v1.15.0 ships this pack at locked sha256."""
    pack2 = load_rangepack(PACK_NAME)
    assert tau_pack.yaml_sha256 == pack2.yaml_sha256


def test_every_bound_is_international_consensus(tau_pack):
    for m in tau_pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS, (
                f"{m.name}.{b.bound_type.value} has citation_strength="
                f"{b.citation_strength.value!r}; production pack must be "
                f"international_consensus."
            )


def test_every_bound_has_5plus_bodies(tau_pack):
    for m in tau_pack.rangepack.measurements:
        for b in m.bounds:
            n = len(b.citation.endorsing_bodies)
            assert n >= 5, (
                f"{m.name}.{b.bound_type.value} has {n} endorsing bodies; "
                f">=5 required for production."
            )


def test_anchor_pmid_is_mattay_2020(tau_pack):
    """Anchor must point to Mattay 2020 FDA approval review (PMID 32709695)."""
    assert tau_pack.rangepack.anchor_citation.citation_pmid == "32709695"


# ============================================================
# FDA-verbatim 1.65× cerebellar threshold
# ============================================================


class TestNeocorticalUptakeRatio:
    """FDA Tauvid PI §2.4 verbatim 1.65-fold cerebellar background threshold."""

    def test_fda_165_threshold_exact(self, tau_pack):
        """The 1.65× cerebellar threshold must match FDA Tauvid PI §2.4 verbatim."""
        m = next(
            m for m in tau_pack.rangepack.measurements
            if m.name == "tau_pet_neocortical_uptake_ratio_flortaucipir"
        )
        plausible_max = next(
            b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX
        )
        assert plausible_max.value == 1.65, (
            f"FDA Tauvid PI §2.4 verbatim threshold is 1.65; got {plausible_max.value}"
        )

    def test_below_165_passes(self, tau_pack):
        """Ratio below 1.65× cerebellum is background activity; no flag."""
        df = pd.DataFrame({
            "patient_id": ["P_background"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_neocortical_uptake_ratio_flortaucipir"],
            "value": [1.2],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 0

    def test_above_165_flagged(self, tau_pack):
        """Ratio above 1.65× cerebellum triggers visual-positive interpretation."""
        df = pd.DataFrame({
            "patient_id": ["P_positive"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_neocortical_uptake_ratio_flortaucipir"],
            "value": [2.5],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1
        assert any(f.bound_type == "plausible_max" for f in r.flags)

    def test_extreme_value_flagged_hard_max(self, tau_pack):
        """Ratio above 20× indicates artifact; hard_max flag."""
        df = pd.DataFrame({
            "patient_id": ["P_artifact"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_neocortical_uptake_ratio_flortaucipir"],
            "value": [50.0],
            "unit": ["ratio"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged >= 1
        assert any(f.bound_type == "hard_max" for f in r.flags)

    def test_fda_endorser_present(self, tau_pack):
        """FDA must endorse the 1.65× threshold."""
        m = next(
            m for m in tau_pack.rangepack.measurements
            if m.name == "tau_pet_neocortical_uptake_ratio_flortaucipir"
        )
        plausible_max = next(
            b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX
        )
        assert any("FDA" in e for e in plausible_max.citation.endorsing_bodies)

    def test_lilly_endorser_present(self, tau_pack):
        """Eli Lilly (manufacturer) must endorse the 1.65× threshold."""
        m = next(
            m for m in tau_pack.rangepack.measurements
            if m.name == "tau_pet_neocortical_uptake_ratio_flortaucipir"
        )
        plausible_max = next(
            b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX
        )
        assert any("Lilly" in e for e in plausible_max.citation.endorsing_bodies)


# ============================================================
# Visual read status (categorical positive/negative)
# ============================================================


class TestVisualReadStatus:
    """FDA Tauvid PI §2.4 positive/negative visual interpretation."""

    def test_positive_passes(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_positive"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_visual_read_status_flortaucipir"],
            "value": ["positive"],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 0

    def test_negative_passes(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_negative"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_visual_read_status_flortaucipir"],
            "value": ["negative"],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 0

    def test_invalid_value_flagged(self, tau_pack):
        """Non-FDA category like 'equivocal' must be flagged."""
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_visual_read_status_flortaucipir"],
            "value": ["equivocal"],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1


# ============================================================
# Reference region (cerebellum / inferior_cerebellum / eroded_white_matter)
# ============================================================


class TestReferenceRegion:

    @pytest.mark.parametrize("region", [
        "cerebellum", "inferior_cerebellum", "eroded_white_matter",
    ])
    def test_all_three_regions_pass(self, tau_pack, region: str):
        df = pd.DataFrame({
            "patient_id": [f"P_{region}"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_reference_region"],
            "value": [region],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 0

    def test_invalid_region_flagged(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_reference_region"],
            "value": ["whole_brain"],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1


# ============================================================
# Target region (6 FDA-named neocortical regions)
# ============================================================


class TestTargetRegion:

    @pytest.mark.parametrize("region", [
        "posterolateral_temporal",
        "occipital",
        "parietal_precuneus",
        "frontal",
        "medial_temporal",
        "anterolateral_temporal",
    ])
    def test_all_fda_regions_pass(self, tau_pack, region: str):
        df = pd.DataFrame({
            "patient_id": [f"P_{region}"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_target_region"],
            "value": [region],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 0

    def test_invalid_region_flagged(self, tau_pack):
        """Non-FDA region like 'cerebellum' (which is reference, not target)."""
        df = pd.DataFrame({
            "patient_id": ["P_invalid"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_target_region"],
            "value": ["cerebellum"],
            "unit": ["categorical"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1


# ============================================================
# Imaging uptake window (80-100 min)
# ============================================================


class TestImagingUptakeWindow:
    """FDA Tauvid PI §2.2: 80 min post-injection start, 20 min acquisition."""

    def test_start_window_passes(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_start"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_imaging_uptake_window_min"],
            "value": [85.0],
            "unit": ["min"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 0

    def test_below_80_min_flagged(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_too_early"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_imaging_uptake_window_min"],
            "value": [60.0],
            "unit": ["min"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1
        assert any(f.bound_type == "hard_min" for f in r.flags)

    def test_above_100_min_flagged(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_too_late"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_imaging_uptake_window_min"],
            "value": [120.0],
            "unit": ["min"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1
        assert any(f.bound_type == "hard_max" for f in r.flags)


# ============================================================
# Dose (250-500 MBq)
# ============================================================


class TestDose:
    """FDA Tauvid PI §2.1: 370 MBq (10 mCi) recommended; SNMMI/EANM ±tolerance."""

    def test_recommended_dose_passes(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_normal"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_dose_mbq"],
            "value": [370.0],
            "unit": ["MBq"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 0

    def test_underdose_flagged(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_underdose"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_dose_mbq"],
            "value": [100.0],
            "unit": ["MBq"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1
        assert any(f.bound_type == "hard_min" for f in r.flags)

    def test_overdose_flagged(self, tau_pack):
        df = pd.DataFrame({
            "patient_id": ["P_overdose"],
            "visit_id": ["V0"],
            "measurement_name": ["tau_pet_dose_mbq"],
            "value": [800.0],
            "unit": ["MBq"],
        })
        r = audit_clinical_ranges(df, tau_pack)
        assert r.n_flagged == 1
        assert any(f.bound_type == "hard_max" for f in r.flags)


# ============================================================
# Determinism
# ============================================================


def test_same_input_same_flag_id(tau_pack):
    df = pd.DataFrame({
        "patient_id": ["P1"],
        "visit_id": ["V0"],
        "measurement_name": ["tau_pet_neocortical_uptake_ratio_flortaucipir"],
        "value": [2.5],
        "unit": ["ratio"],
    })
    r1 = audit_clinical_ranges(df, tau_pack)
    r2 = audit_clinical_ranges(df, tau_pack)
    assert r1.flag_id == r2.flag_id

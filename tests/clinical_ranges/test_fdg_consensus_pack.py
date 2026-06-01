"""
Tests for fdg_pet/fdg_consensus rangepack (v1.16.0).

The FDG PET production pack encodes brain [18F]FDG PET clinical-grade
parameters for AD differential diagnosis:
  - FDA Fludeoxyglucose F-18 Injection PI verbatim dose envelope (74-370 MBq)
  - EANM Brain FDG-PET Guideline v3 (2022) clinical-practice envelope (125-250 MBq)
  - EANM/SNMMI 2024 v2.0 + Mosconi 2008 multicenter reference-region enum
    (pons, cerebellum, whole_brain)
  - SNMMI/EANM 2024 v2.0 + CMS NCD 220.6.13 four-category visual interpretation
    pattern (AD-pattern, FTD-pattern, DLBD-pattern, vascular_or_normal_or_other)
  - Bailly 2015 (PMC4539420, n=47 multi-site French cohort) cerebellum-
    referenced precuneus and posterior cingulate SUVR anchors
    (precuneus HC=1.26 / MCI=1.09 / AD=1.02; PCC HC=1.22 / MCI=1.06 / AD=0.96)
  - CMS NCD 220.6.13 (Sept 15, 2004; reviewed Sept 10, 2024) regulatory-
    coverage indication status enum

Citation strengths mixed: verbatim (FDA + EANM dose envelopes),
international_consensus (CMS + SNMMI + EANM + Mosconi enums),
derived (multi-cohort SUVR cutoffs and uptake-time bounds).
All bounds clear the v1.15.1 reconciled world-class gate: >=5 endorsing bodies
per bound (in this pack: >=7), valid strength form, and for derived bounds,
citation_text references multi-cohort/multi-source evidence (ADNI, Bailly 2015
multi-site cohort, Mosconi 2008 multicenter 7-site standardization).
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK_NAME = "fdg_pet/fdg_consensus"


# ============================================================
# Pack-level invariants
# ============================================================


def test_pack_loads():
    pack = load_rangepack(PACK_NAME)
    assert pack is not None
    assert pack.rangepack.rangepack_id == "fdg_pet/fdg_consensus@1.0.0"


def test_pack_is_production_status():
    pack = load_rangepack(PACK_NAME)
    assert pack.status == RangePackStatus.PRODUCTION


def test_pack_has_seven_measurements():
    pack = load_rangepack(PACK_NAME)
    assert len(pack.rangepack.measurements) == 7


def test_pack_measurement_names_complete():
    pack = load_rangepack(PACK_NAME)
    names = {m.name for m in pack.rangepack.measurements}
    expected = {
        "fdg_pet_dose_mbq",
        "fdg_pet_uptake_time_min",
        "fdg_pet_reference_region",
        "fdg_pet_visual_read_pattern",
        "fdg_pet_precuneus_suvr_cerebellum",
        "fdg_pet_posterior_cingulate_suvr_cerebellum",
        "fdg_pet_cms_indication_status",
    }
    assert names == expected


def test_pack_anchor_citation_has_7plus_endorsers():
    """Anchor citation must list >=7 endorsing bodies (FDA + CMS + SNMMI +
    EANM + EAN + AA-2024 + ADNI + Mosconi 2008)."""
    pack = load_rangepack(PACK_NAME)
    n = len(pack.rangepack.anchor_citation.endorsing_bodies)
    assert n >= 7, f"Expected >=7 anchor endorsers; got {n}"


def test_pack_anchor_pmid_is_mosconi_2008():
    """Anchor citation must be Mosconi 2008 multicenter standardization
    (PMID 18287270)."""
    pack = load_rangepack(PACK_NAME)
    assert pack.rangepack.anchor_citation.citation_pmid == "18287270"


def test_pack_yaml_sha256_locked():
    """Locked golden yaml_sha256 for v1.16.0."""
    pack = load_rangepack(PACK_NAME)
    assert pack.yaml_sha256 == (
        "6c1fc1ec6183b7d19adb687332edd7e450844a85b1238e82d2af64f989e25599"
    )


# ============================================================
# FDG dose envelope (FDA + EANM v3)
# ============================================================


def test_fdg_dose_floor_at_zero():
    """Administered radioactivity is non-negative by definition."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_dose_mbq")
    floor = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    assert floor.value == 0.0


def test_fdg_dose_eanm_v3_plausible_max_at_250mbq():
    """EANM Brain FDG-PET v3 (2022, PMID 35094103) verbatim clinical-
    practice envelope upper bound: 250 MBq (typically 150 MBq)."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_dose_mbq")
    pmax = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert pmax.value == 250.0
    assert pmax.citation_strength == CitationStrength.VERBATIM


def test_fdg_dose_fda_hard_max_at_370mbq():
    """FDA Fludeoxyglucose F-18 Injection PI verbatim upper bound:
    370 MBq (10 mCi)."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_dose_mbq")
    hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert hmax.value == 370.0
    assert hmax.citation_strength == CitationStrength.VERBATIM


# ============================================================
# Uptake time (EANM v3 + multi-cohort derived)
# ============================================================


def test_uptake_time_clinical_practice_envelope_30_to_60():
    """EANM Brain FDG-PET v3 routine clinical-practice envelope: 30-60 min.
    Plausible_max at 60 min."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_uptake_time_min")
    pmax = next(b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    assert pmax.value == 60.0
    assert pmax.citation_strength == CitationStrength.DERIVED


def test_uptake_time_qc_floor_20min():
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_uptake_time_min")
    hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    assert hmin.value == 20.0


def test_uptake_time_pharmacokinetic_ceiling_120min():
    """F-18 half-life 109.7 min; >120 min uptake biologically unreliable."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_uptake_time_min")
    hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert hmax.value == 120.0


# ============================================================
# Reference region categorical enum
# ============================================================


def test_reference_region_three_value_enum():
    """Mosconi 2008 multicenter + SNMMI/EANM 2024 v2.0 reference region
    enum: pons, cerebellum, whole_brain."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_reference_region")
    assert set(m.valid_values) == {"pons", "cerebellum", "whole_brain"}


# ============================================================
# Visual read pattern categorical enum
# ============================================================


def test_visual_read_pattern_four_value_enum():
    """SNMMI/EANM 2024 v2.0 + CMS NCD 220.6.13 + Mosconi 2008 pattern enum:
    ad_pattern, ftd_pattern, dlbd_pattern, vascular_or_normal_or_other."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_visual_read_pattern")
    expected = {"ad_pattern", "ftd_pattern", "dlbd_pattern", "vascular_or_normal_or_other"}
    assert set(m.valid_values) == expected


# ============================================================
# Precuneus + PCC SUVR bounds (Bailly 2015 + multi-cohort derived)
# ============================================================


@pytest.mark.parametrize(
    "measurement_name",
    ["fdg_pet_precuneus_suvr_cerebellum", "fdg_pet_posterior_cingulate_suvr_cerebellum"],
)
def test_suvr_bounds_match_multi_cohort_envelope(measurement_name: str):
    """Both Bailly 2015-anchored SUVR measurements use the same multi-cohort
    envelope: hard_min=0.3, plausible_max=1.5, hard_max=3.0."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == measurement_name)
    bounds_by_type = {b.bound_type: b for b in m.bounds}
    assert bounds_by_type[BoundType.HARD_MIN].value == 0.3
    assert bounds_by_type[BoundType.PLAUSIBLE_MAX].value == 1.5
    assert bounds_by_type[BoundType.HARD_MAX].value == 3.0
    # All SUVR bounds are 'derived' from multi-cohort sources
    for b in m.bounds:
        assert b.citation_strength == CitationStrength.DERIVED


def test_bailly_2015_referenced_on_suvr_measurements():
    """Bailly 2015 (PMC4539420) must be cited on every SUVR measurement
    bound's citation_text."""
    pack = load_rangepack(PACK_NAME)
    for m in pack.rangepack.measurements:
        if "suvr_cerebellum" not in m.name:
            continue
        for b in m.bounds:
            assert "Bailly 2015" in b.citation.citation_text, (
                f"{m.name}.{b.bound_type.value} does not cite Bailly 2015"
            )


def test_mosconi_2008_referenced_on_suvr_measurements():
    """Mosconi 2008 multicenter standardization (PMID 18287270) must be
    referenced on every SUVR measurement bound (multi-cohort foundation)."""
    pack = load_rangepack(PACK_NAME)
    for m in pack.rangepack.measurements:
        if "suvr_cerebellum" not in m.name:
            continue
        for b in m.bounds:
            assert "Mosconi 2008" in b.citation.citation_text or \
                   "18287270" in b.citation.citation_text, (
                f"{m.name}.{b.bound_type.value} does not cite Mosconi 2008 multicenter"
            )


# ============================================================
# CMS NCD 220.6.13 indication status enum
# ============================================================


def test_cms_indication_three_value_enum():
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_cms_indication_status")
    expected = {
        "ncd_220_6_13_covered",
        "ncd_220_6_13_clinical_trial_only",
        "not_covered",
    }
    assert set(m.valid_values) == expected


def test_cms_ncd_220_6_13_referenced_in_indication_measurement():
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_cms_indication_status")
    for b in m.bounds:
        assert "NCD 220.6.13" in b.citation.citation_text or \
               "220.6.13" in b.citation.citation_text


# ============================================================
# Citation rigor (>=5 endorsing bodies on every bound; this pack >=7)
# ============================================================


def test_every_bound_has_5plus_endorsing_bodies():
    """Production pack invariant: every bound's citation must list >=5
    international specialty bodies, regulatory authorities, or named research
    consortia. This pack consistently has >=7."""
    pack = load_rangepack(PACK_NAME)
    failures = []
    for m in pack.rangepack.measurements:
        for i, b in enumerate(m.bounds):
            n = len(b.citation.endorsing_bodies) if b.citation.endorsing_bodies else 0
            if n < 5:
                failures.append(
                    f"{m.name}.bounds[{i}] ({b.bound_type.value}): {n} endorsers"
                )
    assert not failures, "Bounds with <5 endorsers:\n  " + "\n  ".join(failures)


def test_every_bound_meets_world_class_evidence_bar():
    """v1.15.1 reconciled world-class gate: every bound must satisfy
       (a) >=5 endorsing bodies (load-bearing invariant),
       (b) citation_strength in {international_consensus, verbatim, derived}, and
       (c) if derived: citation_text shows multi-cohort/multi-source evidence.

    This pack mixes citation_strength forms:
      - verbatim (FDA + EANM v3 dose envelopes)
      - international_consensus (CMS + SNMMI + EANM + Mosconi enums)
      - derived (multi-cohort SUVR + uptake-time bounds, anchored to
        Bailly 2015 multi-site + Mosconi 2008 7-site multicenter + ADNI)
    All bounds clear all three world-class invariants."""
    pack = load_rangepack(PACK_NAME)
    valid_strengths = {
        CitationStrength.INTERNATIONAL_CONSENSUS,
        CitationStrength.VERBATIM,
        CitationStrength.DERIVED,
    }
    multi_source_markers = (
        "cohort", "multi-", "Meta", "consortium", "Consortium", "Mosconi",
        "percentile", "across", "n=", "ADNI", "BioFINDER", "Bailly",
        "multicenter", "multi-site", "Minoshima",
    )
    for m in pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation_strength in valid_strengths, (
                f"{m.name}.{b.bound_type.value}: invalid strength {b.citation_strength.value}"
            )
            assert len(b.citation.endorsing_bodies) >= 5, (
                f"{m.name}.{b.bound_type.value}: only "
                f"{len(b.citation.endorsing_bodies)} endorsers"
            )
            if b.citation_strength == CitationStrength.DERIVED:
                text = b.citation.citation_text
                assert any(marker in text for marker in multi_source_markers), (
                    f"{m.name}.{b.bound_type.value}: derived bound without "
                    f"multi-source evidence markers in citation_text"
                )


# ============================================================
# Multi-body regulatory endorsement (FDA, CMS, SNMMI, EANM, AA-2024)
# ============================================================


def test_fda_endorsement_present_in_dose_bounds():
    """FDA Fludeoxyglucose F-18 Injection PI must be cited on dose bounds."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_dose_mbq")
    for b in m.bounds:
        endorsers_str = " ".join(b.citation.endorsing_bodies)
        assert "FDA" in endorsers_str, (
            f"FDA not in dose bound endorsers: {b.citation.endorsing_bodies}"
        )


def test_cms_endorsement_present_in_indication_bounds():
    """CMS NCD 220.6.13 must be cited on the regulatory indication status bounds."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == "fdg_pet_cms_indication_status")
    for b in m.bounds:
        endorsers_str = " ".join(b.citation.endorsing_bodies)
        assert "CMS" in endorsers_str, (
            f"CMS not in indication bound endorsers: {b.citation.endorsing_bodies}"
        )


def test_snmmi_eanm_endorsement_present_across_pack():
    """SNMMI and EANM must each appear in >=4 of 7 measurements (the joint
    SNMMI/EANM 2024 v2.0 procedure standard is the load-bearing endorsement
    for the operative AD differential-diagnosis framework)."""
    pack = load_rangepack(PACK_NAME)
    snmmi_count = 0
    eanm_count = 0
    for m in pack.rangepack.measurements:
        has_snmmi = any(
            "SNMMI" in " ".join(b.citation.endorsing_bodies) for b in m.bounds
        )
        has_eanm = any(
            "EANM" in " ".join(b.citation.endorsing_bodies) for b in m.bounds
        )
        if has_snmmi:
            snmmi_count += 1
        if has_eanm:
            eanm_count += 1
    assert snmmi_count >= 4, f"SNMMI cited in only {snmmi_count} measurements"
    assert eanm_count >= 4, f"EANM cited in only {eanm_count} measurements"


def test_aa_2024_core_2_n_marker_endorsement():
    """AA-2024 NIA-AA Revised Criteria (Jack 2024) classifies FDG-PET as
    Core 2 biomarker N (neurodegeneration). This classification must appear
    in pack endorsements."""
    pack = load_rangepack(PACK_NAME)
    aa_2024_count = 0
    for m in pack.rangepack.measurements:
        if any(
            "AA-2024" in " ".join(b.citation.endorsing_bodies)
            or "Jack" in " ".join(b.citation.endorsing_bodies)
            for b in m.bounds
        ):
            aa_2024_count += 1
    assert aa_2024_count >= 5, f"AA-2024 cited in only {aa_2024_count} measurements"

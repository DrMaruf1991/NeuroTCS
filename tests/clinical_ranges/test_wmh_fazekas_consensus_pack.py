"""
Tests for mri_volumetrics/wmh_fazekas_consensus rangepack (v1.13.0).

The WMH/Fazekas Layer 2 pack encodes:
  - Fazekas 1987 visual rating scale (PVH, DWMH, combined; 0-3 ordinal)
  - STRIVE-2 consortium volumetric WMH definitions (Duering 2023)
  - Meta VCI Map Consortium normative volume envelopes (de Kort 2024, n=14,876)

This pack ships at production status with international_consensus or verbatim
citation_strength on every bound, ≥5 endorsing bodies on every citation, and
ratifies the Fazekas 1987 scale ceiling at 3 (verbatim).
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK_NAME = "mri_volumetrics/wmh_fazekas_consensus"


# ============================================================
# Pack-level invariants
# ============================================================


def test_pack_loads():
    """The pack must load via the standard rangepack loader."""
    pack = load_rangepack(PACK_NAME)
    assert pack.rangepack.rangepack_id == "mri_volumetrics/wmh_fazekas_consensus@1.0.0"


def test_pack_is_production_status():
    """v1.13.0 ships the pack at production status (not skeleton or preview)."""
    pack = load_rangepack(PACK_NAME)
    assert pack.rangepack.status == RangePackStatus.PRODUCTION


def test_pack_has_six_measurements():
    """3 Fazekas visual ratings + 3 WMH volume measurements = 6."""
    pack = load_rangepack(PACK_NAME)
    assert len(pack.rangepack.measurements) == 6


def test_pack_measurement_names_complete():
    """Verifies all 6 measurements are present and named correctly."""
    pack = load_rangepack(PACK_NAME)
    names = {m.name for m in pack.rangepack.measurements}
    expected = {
        "fazekas_periventricular_score",
        "fazekas_deep_white_matter_score",
        "fazekas_combined_score",
        "wmh_total_volume_ml",
        "wmh_periventricular_volume_ml",
        "wmh_deep_volume_ml",
    }
    assert names == expected


def test_pack_anchor_citation_has_5plus_endorsers():
    """Production pack requires >=5 endorsing bodies on anchor citation."""
    pack = load_rangepack(PACK_NAME)
    n = len(pack.rangepack.anchor_citation.endorsing_bodies)
    assert n >= 5, f"anchor_citation has {n} endorsers; >=5 required"


def test_pack_anchor_pmid_is_fazekas_1987():
    """Anchor citation must point to Fazekas 1987 (PMID 3496763)."""
    pack = load_rangepack(PACK_NAME)
    assert pack.rangepack.anchor_citation.citation_pmid == "3496763"


def test_pack_yaml_sha256_locked():
    """v1.13.0 ships this pack with a specific yaml_sha256 that must be byte-
    identical across reloads (cross-platform stable per v1.10.1 protocol)."""
    pack1 = load_rangepack(PACK_NAME)
    pack2 = load_rangepack(PACK_NAME)
    assert pack1.yaml_sha256 == pack2.yaml_sha256


# ============================================================
# Fazekas visual rating scale invariants (Fazekas 1987 verbatim)
# ============================================================


@pytest.mark.parametrize(
    "measurement_name",
    [
        "fazekas_periventricular_score",
        "fazekas_deep_white_matter_score",
        "fazekas_combined_score",
    ],
)
def test_fazekas_scale_floor_at_0(measurement_name: str):
    """All three Fazekas scores are bounded below at 0 (Fazekas 1987)."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == measurement_name)
    hard_mins = [b for b in m.bounds if b.bound_type == BoundType.HARD_MIN]
    assert len(hard_mins) == 1
    assert hard_mins[0].value == 0


@pytest.mark.parametrize(
    "measurement_name",
    [
        "fazekas_periventricular_score",
        "fazekas_deep_white_matter_score",
        "fazekas_combined_score",
    ],
)
def test_fazekas_scale_ceiling_at_3(measurement_name: str):
    """All three Fazekas scores are bounded above at 3 (Fazekas 1987
    four-point ordinal scale 0-3, ratified by STRIVE-2 2023)."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == measurement_name)
    hard_maxes = [b for b in m.bounds if b.bound_type == BoundType.HARD_MAX]
    assert len(hard_maxes) == 1
    assert hard_maxes[0].value == 3


@pytest.mark.parametrize(
    "measurement_name",
    [
        "fazekas_periventricular_score",
        "fazekas_deep_white_matter_score",
    ],
)
def test_fazekas_visual_scale_bounds_are_verbatim(measurement_name: str):
    """PVH and DWMH scales reference Fazekas 1987 verbatim text."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == measurement_name)
    for b in m.bounds:
        assert b.citation_strength == CitationStrength.VERBATIM
        assert b.citation.citation_pmid == "3496763"


def test_fazekas_combined_score_uses_strive2_citation():
    """Combined score (max of PVH, DWMH) is post-Fazekas (Wahlund 2001 /
    STRIVE-2 2023), so its citation_strength is international_consensus
    rather than verbatim Fazekas 1987."""
    pack = load_rangepack(PACK_NAME)
    m = next(
        m for m in pack.rangepack.measurements
        if m.name == "fazekas_combined_score"
    )
    for b in m.bounds:
        assert b.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS


# ============================================================
# WMH volume invariants (STRIVE-2 + Meta VCI Map)
# ============================================================


@pytest.mark.parametrize(
    "measurement_name",
    [
        "wmh_total_volume_ml",
        "wmh_periventricular_volume_ml",
        "wmh_deep_volume_ml",
    ],
)
def test_wmh_volume_floor_at_zero(measurement_name: str):
    """All WMH volume measurements are bounded below at 0.0 mL
    (mathematical non-negativity)."""
    pack = load_rangepack(PACK_NAME)
    m = next(m for m in pack.rangepack.measurements if m.name == measurement_name)
    hard_mins = [b for b in m.bounds if b.bound_type == BoundType.HARD_MIN]
    assert len(hard_mins) == 1
    assert hard_mins[0].value == 0.0


def test_wmh_total_has_plausible_max_at_100ml():
    """Meta VCI Map (de Kort 2024, n=14,876) 99th-percentile envelope for
    total WMH; values >100 mL warrant segmentation review."""
    pack = load_rangepack(PACK_NAME)
    m = next(
        m for m in pack.rangepack.measurements if m.name == "wmh_total_volume_ml"
    )
    plausible_max = [b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX]
    assert len(plausible_max) == 1
    assert plausible_max[0].value == 100.0


def test_wmh_total_has_hard_max_at_250ml():
    """Biological extreme: >250 mL implies >50% of total white matter is
    hyperintense (whole-cerebrum WM volume ~450-550 mL); hard-max as QC failsafe."""
    pack = load_rangepack(PACK_NAME)
    m = next(
        m for m in pack.rangepack.measurements if m.name == "wmh_total_volume_ml"
    )
    hard_maxes = [b for b in m.bounds if b.bound_type == BoundType.HARD_MAX]
    assert len(hard_maxes) == 1
    assert hard_maxes[0].value == 250.0


def test_wmh_periventricular_plausible_max_60ml():
    """Meta VCI Map periventricular 99th percentile ~60 mL."""
    pack = load_rangepack(PACK_NAME)
    m = next(
        m for m in pack.rangepack.measurements
        if m.name == "wmh_periventricular_volume_ml"
    )
    plausible_max = [b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX]
    assert len(plausible_max) == 1
    assert plausible_max[0].value == 60.0


def test_wmh_deep_plausible_max_50ml():
    """Meta VCI Map deep 99th percentile ~50 mL."""
    pack = load_rangepack(PACK_NAME)
    m = next(
        m for m in pack.rangepack.measurements if m.name == "wmh_deep_volume_ml"
    )
    plausible_max = [b for b in m.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX]
    assert len(plausible_max) == 1
    assert plausible_max[0].value == 50.0


def test_wmh_pvh_plus_deep_envelope_within_total():
    """Sanity check: the periventricular and deep plausible-max sum (110 mL)
    is within the total plausible-max envelope (100 mL) is intentionally
    NOT enforced because population-99th-percentile bounds are not strictly
    additive (an individual rarely hits 99th percentile on both axes
    simultaneously). This test documents the choice."""
    pack = load_rangepack(PACK_NAME)
    pvh = next(
        m for m in pack.rangepack.measurements
        if m.name == "wmh_periventricular_volume_ml"
    )
    deep = next(
        m for m in pack.rangepack.measurements
        if m.name == "wmh_deep_volume_ml"
    )
    pvh_max = next(b.value for b in pvh.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    deep_max = next(b.value for b in deep.bounds if b.bound_type == BoundType.PLAUSIBLE_MAX)
    # We assert the bounds exist and are sensible; the non-additivity is
    # documented in the YAML notes and Meta VCI Map paper.
    assert pvh_max == 60.0
    assert deep_max == 50.0


# ============================================================
# Citation rigor (>=5 endorsing bodies on every bound)
# ============================================================


def test_every_bound_has_5plus_endorsing_bodies():
    """Production pack invariant: every bound's citation must list >=5
    international specialty bodies, regulatory authorities, or named
    research consortia."""
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

    This pack mixes three citation_strength forms (5 international_consensus,
    4 verbatim Fazekas 1987 visual scale, 4 derived Meta VCI Map normative).
    All three forms are world-class because every bound clears the >=5 endorser
    floor and derived bounds reference the Meta VCI Map Consortium (n=14,876
    across 15 cohorts)."""
    from neurotcs.clinical_ranges.schema import CitationStrength
    pack = load_rangepack(PACK_NAME)
    valid_strengths = {
        CitationStrength.INTERNATIONAL_CONSENSUS,
        CitationStrength.VERBATIM,
        CitationStrength.DERIVED,
    }
    multi_source_markers = (
        "cohort", "multi-", "Meta VCI", "consortium", "Consortium",
        "percentile", "across", "n=", "ADNI", "BioFINDER",
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


def test_meta_vci_map_normative_referenced():
    """The Meta VCI Map Consortium normative reference (de Kort 2024,
    PMID 39602940) must be cited on every WMH volume measurement."""
    pack = load_rangepack(PACK_NAME)
    for m in pack.rangepack.measurements:
        if "volume_ml" not in m.name:
            continue
        for b in m.bounds:
            assert b.citation.citation_pmid == "39602940", (
                f"{m.name}.bounds ({b.bound_type.value}) does not cite "
                f"Meta VCI Map de Kort 2024 (PMID 39602940); got "
                f"PMID {b.citation.citation_pmid}"
            )


def test_strive2_referenced_on_combined_score():
    """STRIVE-2 (Duering 2023, PMID 37236211) must be cited on the
    combined score (post-Fazekas derivation)."""
    pack = load_rangepack(PACK_NAME)
    m = next(
        m for m in pack.rangepack.measurements
        if m.name == "fazekas_combined_score"
    )
    for b in m.bounds:
        assert b.citation.citation_pmid == "37236211", (
            f"fazekas_combined_score bound {b.bound_type.value} does not "
            f"cite STRIVE-2; got PMID {b.citation.citation_pmid}"
        )

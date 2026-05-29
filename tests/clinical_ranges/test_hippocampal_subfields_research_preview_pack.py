"""
Tests for mri_volumetrics/hippocampal_subfields_research_preview rangepack.

The 12 canonical FreeSurfer hippocampal-subfield-module subregions per
hemisphere (Iglesias 2015 ex vivo atlas, PMID 25936807), with research-grade
biological-plausibility envelopes anchored on the ENIGMA subfield QC protocol
(Saemann 2022, DOI 10.1002/hbm.25326).

Ships at research_preview status BY DESIGN: no consensus subfield normative
database exists, FreeSurfer-version comparability is poor (FS6 vs FS7), and
several small subfields have low T1 reliability. audit_clinical_ranges()
refuses to run a research_preview pack -- these tests validate structure and
the fail-closed refusal, NOT production audit behavior. The pack deliberately
does NOT meet the production world-class bar (>=5 endorsers + multi-source
derived evidence); the loader's EXPECTED_PRODUCTION_PACKS gates would block
any premature promotion.
"""

from __future__ import annotations

import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    CitationStrength,
    RangePackStatus,
)

PACK_NAME = "mri_volumetrics/hippocampal_subfields_research_preview"

_SUBFIELDS = [
    "ca1", "ca3", "ca4", "subiculum", "presubiculum", "parasubiculum",
    "molecular_layer_hp", "gc_ml_dg", "hata", "fimbria",
    "hippocampal_fissure", "hippocampal_tail",
]
_LOW_RELIABILITY = {"parasubiculum", "fimbria", "hippocampal_fissure", "hata"}


@pytest.fixture(scope="module")
def pack():
    return load_rangepack(PACK_NAME)


def test_pack_loads(pack):
    assert pack.rangepack.rangepack_id == (
        "mri_volumetrics/hippocampal_subfields_research_preview@1.0.0"
    )


def test_pack_is_research_preview(pack):
    assert pack.rangepack.status == RangePackStatus.RESEARCH_PREVIEW


def test_pack_has_24_measurements(pack):
    assert len(pack.rangepack.measurements) == 24


def test_measurement_names_complete(pack):
    names = {m.name for m in pack.rangepack.measurements}
    expected = {
        f"{sf}_volume_{side}_mm3"
        for sf in _SUBFIELDS
        for side in ("left", "right")
    }
    assert names == expected


def test_anchor_is_iglesias_2015(pack):
    assert pack.rangepack.anchor_citation.citation_pmid == "25936807"
    assert pack.rangepack.anchor_citation.citation_doi == (
        "10.1016/j.neuroimage.2015.04.042"
    )


def test_every_measurement_is_numeric(pack):
    for m in pack.rangepack.measurements:
        assert m.measurement_kind == "numeric"


def test_every_bound_is_derived(pack):
    for m in pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation_strength == CitationStrength.DERIVED


def test_every_measurement_has_hard_min_and_hard_max(pack):
    for m in pack.rangepack.measurements:
        kinds = sorted(b.bound_type.value for b in m.bounds)
        assert kinds == ["hard_max", "hard_min"], f"{m.name}: {kinds}"


def test_hard_min_strictly_below_hard_max(pack):
    for m in pack.rangepack.measurements:
        hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
        hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
        assert hmin.value < hmax.value, f"{m.name}: {hmin.value} !< {hmax.value}"


def test_all_volumes_nonnegative_floor(pack):
    # A volume can never be negative; every hard_min must be >= 0.
    for m in pack.rangepack.measurements:
        hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
        assert hmin.value >= 0.0, f"{m.name} hard_min {hmin.value} < 0"


def test_ca1_present_both_sides(pack):
    names = {m.name for m in pack.rangepack.measurements}
    assert "ca1_volume_left_mm3" in names
    assert "ca1_volume_right_mm3" in names


def test_low_reliability_subfields_flagged(pack):
    # Low-reliability subfields must carry the reliability caveat in their
    # bound citation_text so a reader is warned (scope-honest property).
    for m in pack.rangepack.measurements:
        sf = m.name.rsplit("_volume_", 1)[0]
        if sf in _LOW_RELIABILITY:
            joined = " ".join(b.citation.citation_text for b in m.bounds)
            assert "reliability" in joined.lower(), (
                f"{m.name} is a low-reliability subfield but carries no "
                f"reliability caveat in its bound citations."
            )


def test_every_bound_cites_iglesias_pmid(pack):
    for m in pack.rangepack.measurements:
        for b in m.bounds:
            assert b.citation.citation_pmid == "25936807"


def test_bounds_explicitly_disclaim_normative_percentile(pack):
    # Honesty invariant: bounds must NOT be presented as normative percentiles.
    for m in pack.rangepack.measurements:
        for b in m.bounds:
            assert "NOT a validated normative percentile" in b.citation.citation_text


def test_audit_refuses_research_preview(pack):
    # Fail-closed / scope-honest: a research_preview pack must NOT be runnable
    # through audit_clinical_ranges(). It must refuse rather than silently
    # produce an audit against unconsolidated bounds.
    import pandas as pd

    from neurotcs.clinical_ranges.audit import audit_clinical_ranges

    # Valid long-format input, so the ONLY reason to refuse is the
    # research_preview status (not a malformed-frame error).
    df = pd.DataFrame(
        {
            "patient_id": ["p1", "p1"],
            "visit_id": ["v1", "v2"],
            "measurement_name": ["ca1_volume_left_mm3", "ca1_volume_left_mm3"],
            "value": [600.0, 650.0],
            "unit": ["mm^3", "mm^3"],
        }
    )
    with pytest.raises((ValueError, RuntimeError)) as exc:
        audit_clinical_ranges(df, pack)
    msg = str(exc.value).lower()
    assert any(
        w in msg for w in ("production", "research_preview", "status", "usable", "audit")
    ), f"refusal raised but message does not name the status reason: {exc.value!r}"


def test_yaml_sha256_reproducible(pack):
    pack2 = load_rangepack(PACK_NAME)
    assert pack.yaml_sha256 == pack2.yaml_sha256

"""
Tests for plasma_biomarkers/plasma_gfap_research_preview (research_preview).

Plasma GFAP (AA-2024 ATX(N) astrocytic marker). Shipped research_preview --
NOT production -- because no internationally agreed quantitative cutoff exists
as of 2026. Bounds are an analytical plausibility envelope, not a diagnostic
threshold; the auditor must REFUSE to run it for production audit.
"""

from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.clinical_ranges import load_rangepack
from neurotcs.clinical_ranges.audit import audit_clinical_ranges
from neurotcs.clinical_ranges.schema import BoundType, RangePackStatus

PACK = "plasma_biomarkers/plasma_gfap_research_preview"


@pytest.fixture(scope="module")
def pack():
    return load_rangepack(PACK)


def test_is_research_preview_not_production(pack):
    assert pack.rangepack.status == RangePackStatus.RESEARCH_PREVIEW


def test_single_plasma_gfap_measurement(pack):
    names = {m.name for m in pack.rangepack.measurements}
    assert names == {"plasma_gfap_pgml"}


def test_plausibility_envelope_bounds(pack):
    m = pack.rangepack.measurements[0]
    hmin = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MIN)
    hmax = next(b for b in m.bounds if b.bound_type == BoundType.HARD_MAX)
    assert hmin.value == 0.0
    assert hmax.value == 3000.0


def test_auditor_refuses_research_preview(pack):
    df = pd.DataFrame([{"plasma_gfap_pgml": 250.0}])
    with pytest.raises(ValueError, match="research_preview"):
        audit_clinical_ranges(df, pack)


def test_yaml_sha256_reproducible(pack):
    assert pack.yaml_sha256 == load_rangepack(PACK).yaml_sha256

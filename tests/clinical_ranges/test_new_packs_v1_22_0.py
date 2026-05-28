"""Tests for the v1.22.0 range packs: plasma NfL plausibility.

Note: demographic plausibility (age / education) is NOT a clinical range pack.
Impossible age / negative education are data-integrity errors, so those checks
live in the input-contract layer (DEMOGRAPHIC_IMPLAUSIBLE), tested in
tests/input_contract/. The NfL pack stays here because plasma NfL concentration
IS a biomarker physiological-plausibility range, squarely in clinical_ranges
scope.
"""
from __future__ import annotations

import pandas as pd

from neurotcs.clinical_ranges import audit_clinical_ranges, load_rangepack


def _long(rows):
    return pd.DataFrame(rows, columns=["patient_id", "visit_id", "measurement_name", "value", "unit"])


def _flags(pack, rows):
    r = audit_clinical_ranges(_long(rows), load_rangepack(pack))
    out = []
    for f in (r.flags or []):
        d = f if isinstance(f, dict) else {x: getattr(f, x) for x in dir(f)
                                           if not x.startswith("_") and not callable(getattr(f, x))}
        out.append((str(d["patient_id"]), d["measurement_name"], d["bound_type"], d["observed_value"]))
    return out


def test_nfl_pack_loads():
    lp = load_rangepack("plasma_biomarkers/nfl_consensus")
    assert lp.status.value == "production"
    assert {m.name for m in lp.rangepack.measurements} == {"plasma_nfl_pgml"}


def test_nfl_flags_implausible_high_value():
    rows = [
        ["P1", 0, "plasma_nfl_pgml", 9999.0, "pg/mL"],  # implausible + impossible
        ["P2", 0, "plasma_nfl_pgml", 25.0, "pg/mL"],    # normal adult
        ["P3", 0, "plasma_nfl_pgml", -1.0, "pg/mL"],    # negative -> hard_min
    ]
    fl = _flags("plasma_biomarkers/nfl_consensus", rows)
    bytype = {(s, b) for s, m, b, v in fl}
    assert ("P1", "hard_max") in bytype
    assert ("P1", "plausible_max") in bytype
    assert ("P3", "hard_min") in bytype
    assert not any(s == "P2" for s, m, b, v in fl)

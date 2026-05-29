"""v1.40.0 -- range-pack auto-wiring for wide-format measurement sheets.

Auto-wiring extends audit coverage from staging-only to biomarker VALUES, but
ONLY for assay-independent ordinal/cognitive scales (MMSE, Braak, ...). Assay-
calibrated biomarkers (fluid, PET quantitation, volumetry) are REFUSED, because
a generically-named column cannot certify the assay -- auto-wiring them produced
false positives on every row. These tests lock that boundary.
"""
from __future__ import annotations

import glob
import json

import pandas as pd
import pytest

from neurotcs.cli import main
from neurotcs.io.autowire import autowire_ranges

pytest.importorskip("openpyxl")


def test_safe_ordinal_scales_are_wired():
    tables = {
        "CG": pd.DataFrame({"subject_id": ["S1"], "visit": [0],
                            "mmse": [28], "moca": [25]}),
    }
    specs, extra, decisions, refusals, wired_src = autowire_ranges(tables, set())
    joined = " ".join(decisions)
    assert "mmse=mmse_total" in joined
    assert "moca=moca_total" in joined
    assert "CG" in wired_src


def test_assay_specific_biomarkers_are_refused_not_wired():
    tables = {
        "FL": pd.DataFrame({"subject_id": ["S1"], "visit": [0],
                            "csf_ptau181_pgml": [50.0], "plasma_nfl_pgml": [20.0]}),
    }
    specs, extra, decisions, refusals, wired_src = autowire_ranges(tables, set())
    # neither fluid biomarker is wired
    assert all("csf_ptau181" not in d for d in decisions)
    assert all("plasma_nfl" not in d for d in decisions)
    # both are explicitly refused with a calibration reason
    joined = " ".join(refusals)
    assert "csf_ptau181_pgml" in joined and "plasma_nfl_pgml" in joined
    assert "assay/scale-calibrated" in joined


def test_unit_mismatch_column_is_refused():
    """A cm3 hippocampus column must never be wired to an mm3 pack bound."""
    tables = {
        "MR": pd.DataFrame({"subject_id": ["S1"], "visit": [0],
                            "hippocampal_total_mm3": [3000.0]}),
    }
    # mm3 hippocampus is assay/volumetry -> refused regardless (not in safe set)
    specs, extra, decisions, refusals, wired_src = autowire_ranges(tables, set())
    assert all("hippocamp" not in d for d in decisions)


def test_autowire_catches_scale_violation_no_false_positives(tmp_path):
    """End-to-end: a cognitive sheet where ONE row breaks the scale (MMSE 35)
    must yield exactly one impossible flag for that measurement -- not a flag on
    every row (which would be a calibration false positive)."""
    f = tmp_path / "d.xlsx"
    n = 50
    mmse = [28] * n
    mmse[7] = 35  # the only out-of-scale value (>30)
    with pd.ExcelWriter(f, engine="openpyxl") as xw:
        pd.DataFrame({"subject_id": [f"S{i}" for i in range(n)],
                      "visit": [0] * n,
                      "clinical_state": ["MCI"] * n}).to_excel(
            xw, sheet_name="AUDIT_CLINICAL", index=False)
        pd.DataFrame({"subject_id": [f"S{i}" for i in range(n)],
                      "visit": [0] * n, "mmse": mmse}).to_excel(
            xw, sheet_name="CG", index=False)
    out = tmp_path / "out"
    main(["audit", str(f), "-o", str(out), "--allow-no-dates", "--quiet"])
    b = json.load(open(glob.glob(str(out / "*.bundle.json"))[0]))
    flags = b["neurotcs_bundle"]["deterministic_core"]["flags"]
    mmse_impossible = [x for x in flags["impossible"] if x["field"] == "mmse_total"]
    # exactly one impossible MMSE flag (the 35), NOT one per row
    assert len(mmse_impossible) == 1
    assert mmse_impossible[0]["observed_value"] == 35

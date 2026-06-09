"""End-to-end tests for v1.71.0 biological-axis support on a single-sheet file.

Guards the engine changes that let a one-CSV cohort with BOTH a numeric
clinical_stage column AND an A/B/C/D biological_stage column engage both staging
axes, and that thread a per-visit TRAC column so the biological pack's TRAC
carve-out fires through the full pipeline (mapper -> tables_to_submission ->
orchestrator -> pack).
"""
from __future__ import annotations

import pandas as pd

from neurotcs.cli import (
    _build_axis_spec,
    _detect_treatment_status_col,
    _scaffold_mapping,
)
from neurotcs.io.readers import tables_to_submission


def _desc(cols):
    return {"Trial_Dataset": {"columns": cols, "rows": 6}}


def test_single_sheet_maps_both_axes_to_distinct_columns():
    cols = ["subject_id", "visit", "visit_date",
            "clinical_stage", "biological_stage", "trac_status"]
    m = _scaffold_mapping(_desc(cols))
    assert m["clinical"]["state"] == "clinical_stage"
    assert m["biological"]["state"] == "biological_stage"
    # biological spec wires the treatment column
    assert m["biological"].get("treatment_status") == "trac_status"


def test_single_axis_file_unchanged_no_biological():
    # a clinical-only single sheet must NOT gain a biological axis
    cols = ["subject_id", "visit", "visit_date", "clinical_stage"]
    m = _scaffold_mapping(_desc(cols))
    assert m["clinical"]["state"] == "clinical_stage"
    assert "biological" not in m or not m.get("biological")


def test_biological_axis_spec_has_no_treatment_when_absent():
    cols = ["subject_id", "visit", "biological_stage"]
    spec = _build_axis_spec("S", {"columns": cols}, "biological")
    assert "treatment_status" not in spec


def test_treatment_column_retained_through_submission_and_normalized():
    df = pd.DataFrame([
        {"subject_id": "S2", "visit": 1, "visit_date": "2020-01-01",
         "clinical_stage": 3, "biological_stage": "C", "trac_status": ""},
        {"subject_id": "S2", "visit": 2, "visit_date": "2021-01-01",
         "clinical_stage": 3, "biological_stage": "B", "trac_status": "TRAC"},
    ])
    m = _scaffold_mapping(_desc(list(df.columns)))
    sub = tables_to_submission({"Trial_Dataset": df}, m, warnings=[])
    bio = sub["biological"]
    assert "treatment_status" in bio.columns  # retained through projection
    col = _detect_treatment_status_col(sub)
    assert col == "treatment_status"
    # the TRAC row reads as the literal marker the pack matches on
    assert "TRAC" in set(sub["biological"]["treatment_status"].astype(str))


def test_full_pipeline_flags_untreated_regression_not_trac(tmp_path):
    csv = tmp_path / "mini.csv"
    pd.DataFrame([
        # untreated C->B  => flagged
        {"subject_id": "S1", "visit": 1, "visit_date": "2020-01-01",
         "clinical_stage": 3, "biological_stage": "C", "trac_status": ""},
        {"subject_id": "S1", "visit": 2, "visit_date": "2021-01-01",
         "clinical_stage": 3, "biological_stage": "B", "trac_status": ""},
        # C->B on a TRAC row => NOT flagged
        {"subject_id": "S2", "visit": 1, "visit_date": "2020-01-01",
         "clinical_stage": 3, "biological_stage": "C", "trac_status": ""},
        {"subject_id": "S2", "visit": 2, "visit_date": "2021-01-01",
         "clinical_stage": 3, "biological_stage": "B", "trac_status": "TRAC"},
    ]).to_csv(csv, index=False)

    # Drive the same path the CLI uses via subprocess to keep this hermetic.
    import subprocess
    import sys
    out = tmp_path / "out"
    subprocess.run(
        [sys.executable, "-m", "neurotcs.cli", "audit", str(csv),
         "--allow-no-dates", "--csv", "-o", str(out)],
        capture_output=True, text=True, check=False)
    bundles = list(out.glob("*.bundle.json"))
    assert bundles, "audit produced no bundle"
    # collect biological staging flags from the flags.csv (row-addressable)
    import csv as _csv
    flag_csv = list(out.glob("*.flags.csv"))[0]
    bio = [r for r in _csv.DictReader(open(flag_csv))
           if r.get("layer") == "staging_biological"]
    subjects = {r["subject_id"] for r in bio}
    assert "S1" in subjects, "untreated biological regression must be flagged"
    assert "S2" not in subjects, "TRAC-row regression must NOT be flagged"

"""v1.39.3 -- unified coverage honesty (AD-only, domain-free).

NeuroTCS must never present a confident audit while leaving part of the input
un-audited and undeclared. ONE coverage statement names BOTH:
  (1) un-wired sheets   -- present in the file, no pack attached;
  (2) skipped layers    -- a wired axis the engine refused (e.g. staging
                           vocabulary matching no rule pack).
The statement is printed loudly (stderr) and recorded in the bundle. The logic
is domain-free: it reasons only about sheets/layers, never disease.
"""
from __future__ import annotations

import glob
import json

import pandas as pd
import pytest

from neurotcs.cli import main

pytest.importorskip("openpyxl")


def _make_multisheet(path):
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        pd.DataFrame({"Sheet": ["AUDIT_CLINICAL"], "Rows": [3],
                      "Description": ["c"]}).to_excel(xw, sheet_name="Index", index=False)
        pd.DataFrame({"subject_id": ["S1"] * 3, "visit": [0, 1, 2],
                      "clinical_state": ["CN", "MCI", "AD"]}).to_excel(
            xw, sheet_name="AUDIT_CLINICAL", index=False)
        # genuinely un-wireable sheets (columns resolve to no pack) ->
        # must be declared un-audited
        pd.DataFrame({"subject_id": ["S1"], "visit": [0],
                      "site_code": ["A1"]}).to_excel(
            xw, sheet_name="SITE", index=False)
        pd.DataFrame({"subject_id": ["S1"], "visit": [0],
                      "custom_lab_xyz": [1.0]}).to_excel(
            xw, sheet_name="LAB", index=False)


def test_unwired_sheets_declared_on_stderr(tmp_path, capsys):
    f = tmp_path / "multi.xlsx"
    _make_multisheet(f)
    rc = main(["audit", str(f), "-o", str(tmp_path / "out"), "--allow-no-dates"])
    assert rc in (0, 3)
    err = capsys.readouterr().err
    assert "COVERAGE" in err
    assert "SITE" in err and "LAB" in err       # un-wireable sheets named
    # the WIRED & audited sheet must NOT be listed among un-wired sheets
    cov = [ln for ln in err.splitlines() if "Un-wired sheet" in ln]
    assert cov and "AUDIT_CLINICAL" not in cov[0]


def test_unwired_sheets_recorded_in_bundle(tmp_path):
    f = tmp_path / "multi.xlsx"
    _make_multisheet(f)
    main(["audit", str(f), "-o", str(tmp_path / "out"), "--allow-no-dates", "--quiet"])
    b = json.load(open(glob.glob(str(tmp_path / "out" / "*.bundle.json"))[0]))
    warns = b["neurotcs_bundle"]["run_metadata"]["input_warnings"]
    assert any(w.startswith("coverage:") and "SITE" in w for w in warns)


def test_toc_sheet_never_listed_as_unwired(tmp_path, capsys):
    f = tmp_path / "multi.xlsx"
    _make_multisheet(f)
    main(["audit", str(f), "-o", str(tmp_path / "out"), "--allow-no-dates"])
    err = capsys.readouterr().err
    cov = [ln for ln in err.splitlines() if "Un-wired sheet" in ln]
    assert cov and "Index" not in cov[0]


def test_skipped_layer_named_in_coverage(tmp_path, capsys):
    """A wired biological axis whose vocabulary matches NO production
    rule pack is engine-skipped — the unified coverage line must name
    that skipped layer (not silently drop it).

    (v1.41.0 update: the Jack 2018 4-axis ATN vocabulary is now routable
    via ad/atn_2018, so this test uses deliberately-fabricated state
    names that no production pack recognizes, preserving the test's
    original intent: verify that engine-skip is surfaced in coverage.)
    """
    f = tmp_path / "bio.xlsx"
    with pd.ExcelWriter(f, engine="openpyxl") as xw:
        pd.DataFrame({"subject_id": ["S1"] * 3, "visit": [0, 1, 2],
                      "state": ["CN", "MCI", "AD"]}).to_excel(
            xw, sheet_name="AUDIT_CLINICAL", index=False)
        # Canonical 'state' column wires the sheet; fabricated state values
        # match no production pack -> vocabulary skip fires.
        pd.DataFrame({"subject_id": ["S1"] * 3, "visit": [0, 1, 2],
                      "state": ["FOO-BAR-", "FOO+BAR-", "FOO+BAR+"]}).to_excel(
            xw, sheet_name="AUDIT_BIOLOGICAL", index=False)
    main(["audit", str(f), "-o", str(tmp_path / "out"), "--allow-no-dates"])
    err = capsys.readouterr().err
    assert "COVERAGE" in err
    assert "staging_biological" in err          # the skipped layer is named
    assert "skipped" in err.lower()

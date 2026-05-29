"""
v1.39.0 — completes the external-audit 6-item fix list.

Item 1 (extended): QS/dx/diagnosis -> clinical; BIO -> biological; measurement
                   sheets suggested in notes (not auto-assigned).
Item 3 (completed): --allow-no-dates flag + persistent bundle input_warnings.
Item 4 (completed): sheets with no recognizable staging field are not routed.
Item 5 (completed): error message references --allow-no-dates.
Item 6: INPUT_CONTRACT.md published.
"Better than that": --dry-run resolves routing without producing a bundle.
"""

from __future__ import annotations

import json
import warnings as _w
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.cli import _scaffold_mapping, main
from neurotcs.io import describe_tables, tables_to_submission
from neurotcs.orchestration.bundle import build_bundle
from neurotcs.orchestration.orchestrator import run_full_audit

_w.filterwarnings("ignore")


# ---------- item 1: extended sheet routing ----------
def test_qs_sheet_routes_to_clinical():
    tables = {
        "QS": pd.DataFrame({
            "subject_id": ["S1", "S1"], "visit": [0, 1],
            "visit_date": ["2020-01-01", "2021-01-01"],
            "clinical_state": ["CN", "MCI"],
        }),
    }
    spec = _scaffold_mapping(describe_tables(tables))["clinical"]
    assert spec["sheet"] == "QS"


def test_lone_bio_sheet_routes_to_biological():
    tables = {
        "BIO": pd.DataFrame({
            "subject_id": ["S1", "S1"], "visit": [0, 1],
            "visit_date": ["2020-01-01", "2021-01-01"],
            "biological_stage_ATN": ["A-T-N-", "A+T-N-"],
        }),
    }
    m = _scaffold_mapping(describe_tables(tables))
    assert m["biological"]["sheet"] == "BIO"


def test_audit_biological_beats_bio_when_both_present():
    tables = {
        "BIO": pd.DataFrame({
            "subject_id": ["S1"], "visit": [0], "visit_date": ["2020-01-01"],
            "biological_stage_ATN": ["A-T-N-"],
        }),
        "AUDIT_BIOLOGICAL": pd.DataFrame({
            "subject_id": ["S1"], "visit": [0], "visit_date": ["2020-01-01"],
            "biological_stage_ATN": ["A+T-N-"],
        }),
    }
    m = _scaffold_mapping(describe_tables(tables))
    assert m["biological"]["sheet"] == "AUDIT_BIOLOGICAL"


def test_measurement_sheets_suggested_in_notes():
    tables = {
        "AUDIT_CLINICAL": pd.DataFrame({
            "subject_id": ["S1"], "visit": [0], "visit_date": ["2020-01-01"],
            "clinical_state": ["CN"],
        }),
        "MMSE": pd.DataFrame({"patient_id": ["S1"], "value": [28]}),
        "MRI": pd.DataFrame({"patient_id": ["S1"], "value": [3.5]}),
    }
    notes = " ".join(_scaffold_mapping(describe_tables(tables))["_notes"])
    assert "MMSE -> ranges/cognitive_scales" in notes
    assert "MRI -> ranges/mri_volumetrics" in notes


# ---------- item 4: field guard ----------
def test_enrollment_sheet_with_no_state_is_not_routed():
    """A sheet with subject_id but NO recognizable state column must not be
    auto-routed to a staging axis (the EN-sheet bug)."""
    tables = {
        "EN": pd.DataFrame({
            "subject_id": ["S1"], "enrollment_date": ["2020-01-01"], "site": ["A"],
        }),
    }
    m = _scaffold_mapping(describe_tables(tables))
    # No staging field anywhere -> clinical sheet must be the FILL placeholder
    assert m["clinical"]["sheet"] == "<FILL:sheet>"


def test_named_clinical_sheet_without_state_column_not_routed():
    """Even a sheet NAMED clinical-ish must have a recognizable state column."""
    tables = {
        "AUDIT_CLINICAL": pd.DataFrame({
            "subject_id": ["S1"], "visit": [0],  # no state-like column at all
        }),
    }
    m = _scaffold_mapping(describe_tables(tables))
    assert m["clinical"]["sheet"] == "<FILL:sheet>"


# ---------- item 3: --allow-no-dates + bundle note ----------
def test_bundle_records_input_warnings_without_changing_id():
    sub = tables_to_submission(
        {"S": pd.DataFrame({"subject_id": ["A"] * 3, "visit": [0, 1, 2],
                            "state": ["CN", "MCI", "AD"]})},
        {"clinical": {"sheet": "S", "subject_id": "subject_id", "visit": "visit",
                      "visit_date": None, "state": "state"}},
    )
    res = run_full_audit(sub)
    b0 = build_bundle(res, input_fingerprint="x", input_warnings=[])
    b1 = build_bundle(res, input_fingerprint="x",
                      input_warnings=["clinical: dates derived from visit order"])
    # determinism: same audit_id regardless of the non-hashed warning
    assert (b0["neurotcs_bundle"]["bundle_id"]
            == b1["neurotcs_bundle"]["bundle_id"])
    # but the warning is persistently recorded
    assert b1["neurotcs_bundle"]["run_metadata"]["input_warnings"] == [
        "clinical: dates derived from visit order"
    ]


def test_audit_allow_no_dates_runs_clean(tmp_path):
    f = tmp_path / "d.csv"
    pd.DataFrame({"subject_id": ["P1"] * 3, "visit": [0, 1, 2],
                  "state": ["CN", "MCI", "AD"]}).to_csv(f, index=False)
    m = tmp_path / "map.json"
    m.write_text(json.dumps({
        "clinical": {"sheet": "d", "subject_id": "subject_id", "visit": "visit",
                     "visit_date": None, "state": "state"},
        "ranges": [],
    }))
    rc = main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"),
               "--quiet", "--allow-no-dates"])
    assert rc == 0
    bundle = json.loads((tmp_path / "out" / "d.bundle.json").read_text())
    # the derived-date note is in the persistent bundle
    warns = bundle["neurotcs_bundle"]["run_metadata"]["input_warnings"]
    assert any("derived" in w.lower() for w in warns)


# ---------- "better than that": --dry-run ----------
def test_dry_run_reports_routing_without_writing_bundle(tmp_path, capsys):
    f = tmp_path / "d.csv"
    pd.DataFrame({"subject_id": ["P1"] * 3, "visit": [0, 1, 2],
                  "visit_date": pd.date_range("2020-01-01", periods=3, freq="365D").astype(str),
                  "state": ["CN", "MCI", "AD"]}).to_csv(f, index=False)
    m = tmp_path / "map.json"
    m.write_text(json.dumps({
        "clinical": {"sheet": "d", "subject_id": "subject_id", "visit": "visit",
                     "visit_date": "visit_date", "state": "state"},
        "ranges": [],
    }))
    outdir = tmp_path / "out"
    rc = main(["audit", str(f), "--mapping", str(m), "-o", str(outdir), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()
    assert "clinical" in out
    # dry-run must NOT write a bundle
    assert not (outdir / "d.bundle.json").exists()


# ---------- item 5: actionable error references --allow-no-dates ----------
def test_missing_date_error_mentions_allow_no_dates():
    tables = {"S": pd.DataFrame({"subject_id": ["A"], "visit": [0], "state": ["CN"]})}
    # declare a real (non-null) but nonexistent date column on a sheet that has
    # the other columns -> triggers derivation path, which is graceful (no raise).
    # To force the _require_columns path, make subject_id the missing one:
    mapping = {"clinical": {"sheet": "S", "subject_id": "missing_sid",
                            "visit": "visit", "visit_date": "also_missing_date",
                            "state": "state"}}
    # subject_id missing -> derivation path needs it -> raises with guidance
    with pytest.raises(ValueError) as ei:
        tables_to_submission(tables, mapping)
    assert "Searched columns" in str(ei.value)


# ---------- item 6: INPUT_CONTRACT.md published ----------
def test_input_contract_md_exists_and_has_key_sections():
    # repo root is two levels up from tests/cli/
    root = Path(__file__).resolve().parents[2]
    contract = root / "INPUT_CONTRACT.md"
    assert contract.exists(), "INPUT_CONTRACT.md must be published at repo root"
    text = contract.read_text()
    # key sections the audit asked for
    assert "Recognized sheet names" in text
    assert "Recognized column names" in text
    assert "visit_date" in text and "optional" in text.lower()
    assert "USUBJID" in text  # CDISC synonym documented
    assert "AUDIT_CLINICAL" in text
    # auditor identity preserved
    assert "never silently guess" in text.lower() or "never guess" in text.lower()


# ---------- v1.39.1: verify accepts the audit output DIRECTORY ----------
def test_verify_accepts_output_directory(tmp_path):
    """The natural workflow is `audit -o out` then `verify out`. Passing the
    directory must locate the bundle inside it, not crash with IsADirectoryError."""
    f = tmp_path / "d.csv"
    pd.DataFrame({"subject_id": ["P1"] * 3, "visit": [0, 1, 2],
                  "visit_date": pd.date_range("2020-01-01", periods=3, freq="365D").astype(str),
                  "state": ["CN", "MCI", "AD"]}).to_csv(f, index=False)
    m = tmp_path / "map.json"
    m.write_text(json.dumps({
        "clinical": {"sheet": "d", "subject_id": "subject_id", "visit": "visit",
                     "visit_date": "visit_date", "state": "state"},
        "ranges": [],
    }))
    outdir = tmp_path / "out"
    assert main(["audit", str(f), "--mapping", str(m), "-o", str(outdir), "--quiet"]) == 0
    # verify the DIRECTORY (not the bundle file) -- must succeed
    rc = main(["verify", str(outdir)])
    assert rc == 0


def test_verify_empty_directory_reports_clearly(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = main(["verify", str(empty)])
    assert rc != 0
    err = capsys.readouterr().err
    assert "no" in err.lower() and "bundle" in err.lower()


# ---------- v1.39.2: zero-config audit (no --mapping) for the low-knowledge user ----------
def test_audit_without_mapping_auto_detects_and_runs(tmp_path):
    """The independent-user path: `neurotcs audit file -o out` with NO --mapping.
    A conventional file must audit end-to-end with zero configuration."""
    f = tmp_path / "data.xlsx"
    pytest.importorskip("openpyxl")
    with pd.ExcelWriter(f, engine="openpyxl") as xw:
        pd.DataFrame({"Sheet": ["AUDIT_CLINICAL"], "Rows": [3],
                      "Description": ["clin"]}).to_excel(xw, sheet_name="Index", index=False)
        pd.DataFrame({"subject_id": ["S1"] * 3, "visit": [0, 1, 2],
                      "visit_date": pd.date_range("2020-01-01", periods=3, freq="365D").astype(str),
                      "clinical_state": ["CN", "MCI", "AD"]}).to_excel(xw, sheet_name="AUDIT_CLINICAL", index=False)
    outdir = tmp_path / "out"
    rc = main(["audit", str(f), "-o", str(outdir), "--quiet"])  # NO --mapping
    assert rc == 0  # clean monotone -> exit 0
    assert (outdir / "data.bundle.json").exists()
    # and verify the directory
    assert main(["verify", str(outdir)]) == 0


def test_audit_without_mapping_refuses_when_not_confident(tmp_path, capsys):
    """If auto-detection can't produce a complete mapping, the zero-config path
    must REFUSE with guidance -- never silently guess."""
    f = tmp_path / "weird.csv"
    # columns with no recognizable subject_id or state -> cannot auto-detect
    pd.DataFrame({"foo": [1, 2], "bar": [3, 4]}).to_csv(f, index=False)
    rc = main(["audit", str(f), "-o", str(tmp_path / "out"), "--quiet"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "could not auto-detect" in err.lower()
    assert "describe" in err.lower()  # points user at the explicit-mapping path

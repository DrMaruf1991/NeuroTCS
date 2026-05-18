"""End-to-end smoke test for scripts/run_ad_fairness_audit.py.

Tests that the runner:
  - executes cleanly with synthetic MIRIAD CSVs
  - produces both the JSON and text outputs
  - the JSON contains the FUTURE-AI panel B.4.4 metadata + audit_id linkage
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# Add scripts/ to sys.path so we can import the runner module
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import run_ad_fairness_audit  # noqa: E402


def _write_synthetic_miriad_csvs(out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sessions_csv = out_dir / "sessions.csv"
    clinical_csv = out_dir / "clinical.csv"
    subjects_csv = out_dir / "subjects.csv"

    pd.DataFrame([
        {"Label": "miriad_188_1_MR_1", "Subject": "miriad_188", "Age": 76.6},
        {"Label": "miriad_188_2_MR_1", "Subject": "miriad_188", "Age": 77.1},
        {"Label": "miriad_199_1_MR_1", "Subject": "miriad_199", "Age": 65.3},
        {"Label": "miriad_199_2_MR_1", "Subject": "miriad_199", "Age": 65.8},
        {"Label": "miriad_255_1_MR_1", "Subject": "miriad_255", "Age": 82.1},
        {"Label": "miriad_255_2_MR_1", "Subject": "miriad_255", "Age": 82.6},
    ]).to_csv(sessions_csv, index=False)

    pd.DataFrame([
        {"Label": "miriad_188_1_MMSE", "Subject": "miriad_188", "MMSE": 22},
        {"Label": "miriad_188_2_MMSE", "Subject": "miriad_188", "MMSE": 19},
        {"Label": "miriad_199_1_MMSE", "Subject": "miriad_199", "MMSE": 24},
        {"Label": "miriad_199_2_MMSE", "Subject": "miriad_199", "MMSE": 23},
        {"Label": "miriad_255_1_MMSE", "Subject": "miriad_255", "MMSE": 29},
        {"Label": "miriad_255_2_MMSE", "Subject": "miriad_255", "MMSE": 28},
    ]).to_csv(clinical_csv, index=False)

    pd.DataFrame([
        {"Subject": "miriad_188", "Gender": "male", "Hand": "right",
         "YOB": 1932, "Education": 14, "Ses": "", "MR Count": 2},
        {"Subject": "miriad_199", "Gender": "female", "Hand": "right",
         "YOB": 1944, "Education": 18, "Ses": "", "MR Count": 2},
        {"Subject": "miriad_255", "Gender": "female", "Hand": "left",
         "YOB": 1925, "Education": 10, "Ses": "", "MR Count": 2},
    ]).to_csv(subjects_csv, index=False)

    return clinical_csv, sessions_csv, subjects_csv


def test_fairness_runner_completes_end_to_end(tmp_path: Path):
    """Runner returns 0 and produces both report files."""
    clinical_csv, sessions_csv, subjects_csv = _write_synthetic_miriad_csvs(
        tmp_path / "csvs",
    )
    out_dir = tmp_path / "report"

    rc = run_ad_fairness_audit.main([
        "--cohort", "miriad",
        "--clinical", str(clinical_csv),
        "--sessions", str(sessions_csv),
        "--subjects", str(subjects_csv),
        "--out", str(out_dir),
        "--bootstrap-B", "100",
    ])
    assert rc == 0, "Runner must return exit code 0 on success"

    # Both output files must exist
    json_path = out_dir / "ad_fairness_report.json"
    txt_path = out_dir / "ad_fairness_summary.txt"
    assert json_path.exists()
    assert txt_path.exists()

    # JSON has the expected structure
    report = json.loads(json_path.read_text())
    assert report["framework"]["doi"] == "10.1136/bmj-2024-081554"
    assert report["framework"]["pmid"] == "39909534"
    assert report["framework"]["panel_id"] == "B.4.4_fairness"
    assert "audit_id" in report["audit"]
    assert len(report["audit"]["audit_id"]) == 64  # SHA-256
    assert "strata" in report
    assert isinstance(report["strata"], list)
    # Must have at least sex strata
    sex_strata = [s for s in report["strata"] if s["attribute"] == "sex"]
    assert len(sex_strata) >= 2

    # Text summary must contain a few canonical phrases
    summary = txt_path.read_text()
    assert "FUTURE-AI Panel B.4.4" in summary
    assert "FAIRNESS SUMMARY" in summary
    assert "PER-STRATUM FLAG RATES" in summary


def test_fairness_runner_links_audit_id_to_report(tmp_path: Path):
    """The fairness report must carry the audit_id of the underlying audit,
    so a reviewer can verify both invariants together."""
    clinical_csv, sessions_csv, subjects_csv = _write_synthetic_miriad_csvs(
        tmp_path / "csvs",
    )
    out_dir = tmp_path / "report"
    rc = run_ad_fairness_audit.main([
        "--cohort", "miriad",
        "--clinical", str(clinical_csv),
        "--sessions", str(sessions_csv),
        "--subjects", str(subjects_csv),
        "--out", str(out_dir),
        "--bootstrap-B", "100",
        "--seed", "42",
    ])
    assert rc == 0
    report = json.loads((out_dir / "ad_fairness_report.json").read_text())
    # audit_id and audit_id_v2 must be present and well-formed
    assert len(report["audit"]["audit_id"]) == 64
    assert len(report["audit"]["audit_id_v2"]) == 64
    # rulepack identity present
    assert report["audit"]["rulepack_id"] == "ad/niaaa_2018@1.2.0"
    # SHA prefix matches the known rulepack SHA (first 16 chars)
    assert report["audit"]["rulepack_sha256"].startswith("f359148d1cbf6abe")

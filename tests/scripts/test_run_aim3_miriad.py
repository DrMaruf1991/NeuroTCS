"""End-to-end smoke test for scripts/run_aim3_miriad.py.

v1.7.6 (R10): the runner script is what Maruf actually invokes against
real MIRIAD data. A regression that broke the runner (like the v1.7.3
BootstrapCI attribute name bug) would not be caught by unit tests of
the adapter alone. This module imports and calls the runner's main()
function with synthetic CSVs and verifies it returns exit code 0 and
writes the expected output files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

# Import the runner's main() via sys.path manipulation (scripts/ isn't
# a package — adding it to path lets us import the module directly).
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import run_aim3_miriad  # noqa: E402


def _write_minimal_miriad_csvs(out_dir: Path) -> tuple[Path, Path, Path]:
    """Produce a tiny but valid MIRIAD-shaped CSV triple."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sessions_csv = out_dir / "sessions.csv"
    clinical_csv = out_dir / "clinical.csv"
    subjects_csv = out_dir / "subjects.csv"

    rows_s = []
    rows_c = []
    for sid, mmse_series in [
        (188, [22, 19, 16]),   # AD subject: MCI -> MCI -> AD
        (255, [29, 28, 28]),   # control: CN -> CN -> CN
    ]:
        for visit_num, mmse in enumerate(mmse_series, start=1):
            rows_s.append({
                "Label": f"miriad_{sid}_{visit_num}_MR_1",
                "Subject": f"miriad_{sid}",
                "Age": 70.0 + (visit_num - 1) * 0.5,
            })
            rows_c.append({
                "Label": f"miriad_{sid}_{visit_num}_MMSE",
                "Subject": f"miriad_{sid}",
                "MMSE": mmse,
            })
    pd.DataFrame(rows_s).to_csv(sessions_csv, index=False)
    pd.DataFrame(rows_c).to_csv(clinical_csv, index=False)

    pd.DataFrame([
        {"Subject": "miriad_188", "Gender": "male",
         "Hand": "", "YOB": "", "Education": "", "Ses": "", "MR Count": 3},
        {"Subject": "miriad_255", "Gender": "female",
         "Hand": "", "YOB": "", "Education": "", "Ses": "", "MR Count": 3},
    ]).to_csv(subjects_csv, index=False)

    return clinical_csv, sessions_csv, subjects_csv


def test_runner_completes_end_to_end_with_subjects(tmp_path: Path):
    """Runner returns 0 and produces expected outputs with --subjects."""
    clinical_csv, sessions_csv, subjects_csv = _write_minimal_miriad_csvs(
        tmp_path / "csvs",
    )
    out_dir = tmp_path / "results"

    rc = run_aim3_miriad.main([
        "--clinical", str(clinical_csv),
        "--sessions", str(sessions_csv),
        "--subjects", str(subjects_csv),
        "--out", str(out_dir),
        "--bootstrap-B", "100",
    ])
    assert rc == 0, "Runner must return exit code 0 on success"

    # Required output files
    assert (out_dir / "aim3_summary.txt").exists()
    assert (out_dir / "aim3_longitudinal_audit.json").exists()
    assert (out_dir / "aim3_longitudinal_report.json").exists()
    assert (out_dir / "aim3_test_retest_report.json").exists()

    # Summary is parseable text containing the expected sections
    summary = (out_dir / "aim3_summary.txt").read_text()
    assert "AIM 3 (A)" in summary
    assert "audit_id" in summary
    # Version is shipped dynamically via neurotcs.__version__
    assert "NeuroTCS v" in summary

    # Longitudinal audit JSON contains an audit_id
    long_audit = json.loads(
        (out_dir / "aim3_longitudinal_audit.json").read_text()
    )
    assert "audit_id" in long_audit
    assert len(long_audit["audit_id"]) == 64  # SHA-256 hex


def test_runner_completes_end_to_end_without_subjects(tmp_path: Path):
    """Runner works when --subjects is omitted (ID-based group inference)."""
    clinical_csv, sessions_csv, _ = _write_minimal_miriad_csvs(
        tmp_path / "csvs",
    )
    out_dir = tmp_path / "results"

    rc = run_aim3_miriad.main([
        "--clinical", str(clinical_csv),
        "--sessions", str(sessions_csv),
        "--out", str(out_dir),
        "--bootstrap-B", "100",
    ])
    assert rc == 0


def test_runner_summary_includes_v1_7_6_or_later(tmp_path: Path):
    """The summary header must use a dynamic version string, not a
    hardcoded one. Catches the v1.7.3 bug where v1.7.4 outputs said
    'NeuroTCS v1.7.2'.
    """
    import neurotcs
    clinical_csv, sessions_csv, _ = _write_minimal_miriad_csvs(
        tmp_path / "csvs",
    )
    out_dir = tmp_path / "results"

    run_aim3_miriad.main([
        "--clinical", str(clinical_csv),
        "--sessions", str(sessions_csv),
        "--out", str(out_dir),
        "--bootstrap-B", "50",
    ])
    summary = (out_dir / "aim3_summary.txt").read_text()
    expected = f"NeuroTCS v{neurotcs.__version__}"
    assert expected in summary, (
        f"Summary must include current version '{expected}'; got:\n"
        f"{summary[:200]}"
    )

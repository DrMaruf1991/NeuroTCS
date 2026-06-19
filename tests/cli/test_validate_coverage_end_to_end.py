"""validate-coverage end-to-end through the CLI (audit round 4, P1 #9).

The Arm-B error injector corrupts biomarker fields (FL/AM/EN per the injector's
_NUMERIC_FIELDS), but a biomarker-only cohort produces no bundle to score against.
A valid validate-coverage cohort therefore needs BOTH:
  * a staging axis (clinical_stage) so the corrupt cohort still audits to a bundle, and
  * injectable biomarker fields (FL plasma/csf, EN apoe) so there are cells to inject.

This builds that known-good combined cohort and exercises the full CLI path,
asserting a real detection report -- closing the gap where the CLI validate-
coverage path was never proven end-to-end on a realistic workbook.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from neurotcs.cli import main as cli_main


def _write_known_good_cohort(path: Path) -> None:
    subj = [f"S{i:03d}" for i in range(1, 11)]
    clin_rows = []
    for i, s in enumerate(subj):
        seq = ["CN", "MCI", "MCI", "Dementia"] if i % 2 == 0 else ["CN", "CN", "MCI", "MCI"]
        for v in range(4):
            clin_rows.append({"subject_id": s, "visit": v,
                              "visit_date": f"20{20 + v}-01-01", "clinical_stage": seq[v]})
    en = pd.DataFrame({"subject_id": subj, "apoe_genotype": ["e3/e3"] * 10})
    fl_rows = []
    for i, s in enumerate(subj, start=1):
        for v in (0, 1):
            fl_rows.append({"subject_id": s, "visit": v,
                            "plasma_nfl_pgml": 50.0 + i, "plasma_ptau217_pgml": 0.4 + i / 100})
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame(clin_rows).to_excel(w, sheet_name="clinical", index=False)
        en.to_excel(w, sheet_name="EN", index=False)
        pd.DataFrame(fl_rows).to_excel(w, sheet_name="FL", index=False)


def test_validate_coverage_cli_end_to_end(tmp_path):
    wb = tmp_path / "known_good_cohort.xlsx"
    _write_known_good_cohort(wb)
    report = tmp_path / "coverage_report.json"
    rc = cli_main([
        "validate-coverage", str(wb),
        "--n-high", "2", "--n-unit", "2", "--n-sign", "1", "--n-categorical", "1",
        "--seed", "42", "-o", str(report),
    ])
    assert rc == 0, f"validate-coverage should run end-to-end (exit 0), got {rc}"
    assert report.exists(), "a coverage report JSON should be written"
    d = json.loads(report.read_text(encoding="utf-8"))
    # Real detection report shape.
    assert "overall_coverage" in d
    assert "specificity" in d
    assert d["total_injected"] >= 1
    # The injected errors are gross (unit x1000, sign flip, implausible_high) and
    # must be detected; specificity on clean coords must be perfect on this
    # well-formed cohort.
    assert d["total_detected"] == d["total_injected"], (
        f"all injected errors should be detected: {d['total_detected']}/{d['total_injected']}")
    assert d["specificity"] == 1.0, f"no false positives expected, got {d['specificity']}"

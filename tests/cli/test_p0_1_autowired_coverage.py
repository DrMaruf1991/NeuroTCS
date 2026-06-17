"""P0-1 regression: autowired SOURCE columns are recorded as consumed, never
'ignored'. Before the fix, wide measurement columns (mmse_total, cdr_sb) were
melted into __autowired__ range tables and AUDITED, but the coverage ledger
listed them under columns_ignored -- falsely implying the clinically central
columns were not examined. This test locks the corrected behavior.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from neurotcs.cli import main as cli_main


def _audit_wide(tmp_path: Path) -> dict:
    df = pd.DataFrame({
        "subject_id": ["S1", "S1", "S2"],
        "visit": [0, 1, 0],
        "visit_date": ["2020-01-01", "2021-01-01", "2020-06-01"],
        "clinical_stage": ["CN", "MCI", "CN"],
        "mmse_total": [29, 26, 30],
        "cdr_sb": [0.0, 2.5, 0.0],
    })
    src = tmp_path / "wide.csv"
    df.to_csv(src, index=False)
    out = tmp_path / "out"
    cli_main(["audit", str(src), "-o", str(out), "--quiet"])
    bundle_path = next(out.glob("*.bundle.json"))
    return json.loads(bundle_path.read_text(encoding="utf-8"))


def test_autowired_columns_are_consumed_not_ignored(tmp_path):
    bundle = _audit_wide(tmp_path)
    cov = bundle["neurotcs_bundle"]["deterministic_core"]["coverage"]
    consumed = cov["columns_consumed"].get("wide", [])
    ignored = cov.get("columns_ignored", {}).get("wide", [])
    # The autowired source columns must be recorded as consumed ...
    assert "mmse_total" in consumed, f"mmse_total not in consumed: {consumed}"
    assert "cdr_sb" in consumed, f"cdr_sb not in consumed: {consumed}"
    # ... and must NEVER appear under ignored.
    assert "mmse_total" not in ignored, "mmse_total wrongly under ignored"
    assert "cdr_sb" not in ignored, "cdr_sb wrongly under ignored"


def test_no_audited_column_lands_in_ignored(tmp_path):
    """Stronger: for this fully-wired file, ignored must be empty for the sheet."""
    bundle = _audit_wide(tmp_path)
    cov = bundle["neurotcs_bundle"]["deterministic_core"]["coverage"]
    ignored = cov.get("columns_ignored", {}).get("wide", [])
    assert ignored == [], f"expected no ignored columns, got: {ignored}"

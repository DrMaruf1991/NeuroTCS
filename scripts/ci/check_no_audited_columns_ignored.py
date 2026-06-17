#!/usr/bin/env python3
"""CI release gate (P0-1): fail if an autowired/audited column is reported under
columns_ignored. A precision auditor must never tell a reviewer that a column it
actually examined was 'ignored'. Runs a representative wide audit and inspects
the coverage ledger.

Exit 0 if clean; exit 1 if any audited column is mislabeled as ignored.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

from neurotcs.cli import main as cli_main


def main() -> int:
    df = pd.DataFrame({
        "subject_id": ["S1", "S1", "S2"],
        "visit": [0, 1, 0],
        "visit_date": ["2020-01-01", "2021-01-01", "2020-06-01"],
        "clinical_stage": ["CN", "MCI", "CN"],
        "mmse_total": [29, 26, 30],
        "cdr_sb": [0.0, 2.5, 0.0],
    })
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "wide.csv"
        df.to_csv(src, index=False)
        out = Path(td) / "out"
        cli_main(["audit", str(src), "-o", str(out), "--quiet"])
        bundle = json.loads(next(out.glob("*.bundle.json")).read_text("utf-8"))
    cov = bundle["neurotcs_bundle"]["deterministic_core"]["coverage"]
    ignored = cov.get("columns_ignored", {})
    # The audited autowired sources must NOT appear in ignored anywhere.
    offenders = []
    for sheet, cols in ignored.items():
        for c in cols:
            if c in ("mmse_total", "cdr_sb"):
                offenders.append(f"{sheet}.{c}")
    if offenders:
        print("RELEASE GATE FAILED (P0-1): audited columns reported as ignored: "
              + ", ".join(offenders))
        return 1
    print("OK: no audited/autowired column appears under columns_ignored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

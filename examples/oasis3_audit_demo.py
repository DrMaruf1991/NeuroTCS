"""
End-to-end NeuroTCS audit demo on real OASIS-3 clinical labels (Aim 2).

Reproduces the locked Aim 2 external replication finding:
    cTCS = 0.9942, ΔcTCS vs ADNI = 0.0004
    audit_id = 96d942e41e9f94a33718d9a107dedf443de728bdd16dcf36ade18ca1f3f4077a

Usage:
    # default: looks for the OASIS-3 UDSb4 CSV in standard locations
    python examples/oasis3_audit_demo.py

    # explicit path:
    python examples/oasis3_audit_demo.py /path/to/OASIS3_UDSb4_cdr.csv

The OASIS-3 data is NOT distributed with the NeuroTCS repository.
Access requires a Data Use Agreement with WUSTL Knight ADRC (request
at https://sites.wustl.edu/oasisbrains/). After approval, the
`OASIS3_data_files.zip` bundle from NITRC-IR contains
`OASIS3_UDSb4_cdr.csv` under `scans/UDSb4-.../resources/csv/files/`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
    load_oasis3_trajectories,
)

# Common locations to probe for the file
SEARCH_PATHS = [
    Path.cwd() / "OASIS3_UDSb4_cdr.csv",
    Path.home() / "Downloads" / "OASIS3_data_files" / "OASIS3_data_files"
    / "scans" / "UDSb4-Form_B4__Global_Staging__CDR__Standard_and_Supplemental"
    / "resources" / "csv" / "files" / "OASIS3_UDSb4_cdr.csv",
    Path("/home/claude/oasis3_work/OASIS3_UDSb4_cdr.csv"),
]


def find_udsb4(explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.exists():
            print(f"ERROR: file not found: {explicit}")
            sys.exit(1)
        return explicit
    for p in SEARCH_PATHS:
        if p.exists():
            return p
    print(
        "ERROR: OASIS-3 UDSb4 CSV not found in any standard location.\n"
        "Pass the explicit path:\n"
        "  python examples/oasis3_audit_demo.py /path/to/OASIS3_UDSb4_cdr.csv\n"
        "\n"
        "Download OASIS-3 from NITRC-IR after DUA approval at "
        "https://sites.wustl.edu/oasisbrains/."
    )
    sys.exit(1)


def run(udsb4_path: Path) -> None:
    print(f"Loading: {udsb4_path}")
    trajectories, report = load_oasis3_trajectories(udsb4_path)

    print()
    print("Load report:")
    print(f"  raw rows:               {report.raw_rows:,}")
    print(f"  raw subjects:           {report.raw_subjects:,}")
    print(f"  rows after dropna:      {report.rows_after_dropna:,}")
    print(f"  subjects after dropna:  {report.subjects_after_dropna:,}")
    print(f"  unmappable CDR:         {report.unmappable_cdr}")
    print(f"  trajectories built:     {report.n_trajectories:,}")
    print(f"  transitions:            {report.n_transitions:,}")
    print(f"  dx1 disagreements:      {report.dx1_disagreements}")

    pack = load_rulepack("ad/niaaa_2018")
    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42)

    print()
    print(result.summary())
    print()
    print(f"audit_id:        {result.audit_id}")
    print(f"timestamp_utc:   {result.timestamp_utc}")

    pp = result.per_patient
    print()
    print("Per-patient distribution:")
    print(f"  cTCS  median {float(np.median(pp.ctcs)):.4f}, "
          f"min {pp.ctcs.min():.4f}, max {pp.ctcs.max():.4f}")
    print(f"  uTCS  median {float(np.median(pp.utcs)):.4f}, "
          f"min {pp.utcs.min():.4f}, max {pp.utcs.max():.4f}")

    # Show example dx1 disagreements (diagnostic only)
    if report.dx1_disagreement_examples:
        print()
        print("dx1 disagreement examples (first 3):")
        for ex in report.dx1_disagreement_examples[:3]:
            print(f"  {ex['OASISID']} day {ex['days_to_visit']:>4}: "
                  f"CDR={ex['CDRTOT']} ({ex['cdr_state']}) "
                  f"vs dx1='{ex['dx1_raw']}' ({ex['dx1_state']})")


if __name__ == "__main__":
    explicit = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run(find_udsb4(explicit))

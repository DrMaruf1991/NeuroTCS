"""
Example: Apply the NeuroTCS AD rule pack to real ADNI clinical-label transitions.

Expected output:
    Rule pack:   ad/niaaa_2018@1.1.0
    SHA-256:     372cc128832bf693...
    Transitions: 12006 audited, 65 flagged (0.54%)

To run this end-to-end you need ADNIMERGE2 (.rda files) which is not committed
to the repo (PHI considerations). Apply for access at adni.loni.usc.edu.

Usage:
    python examples/adni_audit_demo.py /path/to/ADNIMERGE2/data/DXSUM.rda

This script doubles as the worked example for the cTCS audit pipeline: in
the absence of the audit_core library (Piece 4, planned), it shows the
minimal rule-based admissibility check that cTCS will operationalize.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import pyreadr
    import pandas as pd
except ImportError:
    print("This example requires `pyreadr` and `pandas`. Install with:")
    print("    pip install 'neurotcs[adni]'")
    sys.exit(1)

from neurotcs import load_rulepack


def run(dxsum_path: str | Path) -> None:
    pack = load_rulepack("ad/niaaa_2018")
    pack.assert_usable_for_audit()

    print(f"Rule pack:    {pack.rulepack_id}")
    print(f"SHA-256:      {pack.sha256[:16]}...")
    print(f"Schema:       v{pack.rulepack.schema_version}")
    print(f"Transitions:  {len(pack.rulepack.admissible_transitions)} admissible, "
          f"{len(pack.rulepack.inadmissible_transitions)} inadmissible")
    print()

    dx = pyreadr.read_r(str(dxsum_path))["DXSUM"]
    dx = dx[dx["DIAGNOSIS"].isin(["CN", "MCI", "Dementia"])].copy()
    dx["DIAGNOSIS"] = dx["DIAGNOSIS"].replace({"Dementia": "AD"})
    dx["EXAMDATE"] = pd.to_datetime(dx["EXAMDATE"], errors="coerce")
    dx = dx.dropna(subset=["EXAMDATE", "RID"]).sort_values(["RID", "EXAMDATE"])

    total, flagged, examples = 0, 0, []
    for rid, group in dx.groupby("RID"):
        states = group["DIAGNOSIS"].tolist()
        dates = group["EXAMDATE"].tolist()
        for i in range(len(states) - 1):
            delta = (dates[i+1] - dates[i]).days
            ok, _ = pack.rulepack.is_admissible(states[i], states[i+1], delta)
            total += 1
            if not ok:
                flagged += 1
                if len(examples) < 5:
                    examples.append((int(rid), states[i], states[i+1], delta))

    print(f"Transitions audited: {total:,}")
    print(f"Flagged:             {flagged:,} ({100*flagged/total:.2f}%)")
    print()
    print("First 5 flags (clinically interpretable):")
    for rid, s1, s2, dd in examples:
        print(f"  RID {rid}: {s1} -> {s2} over {dd} days")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Fall back to the working-dir location used during development
        default = Path("/home/claude/adni_work/ADNIMERGE2/data/DXSUM.rda")
        if default.exists():
            run(default)
        else:
            print(__doc__)
            sys.exit(1)
    else:
        run(sys.argv[1])

"""
End-to-end NeuroTCS audit demo on real ADNI clinical labels.

This is the worked example for the Nature Medicine supplement, the FDA
Q-Submission demonstration package, and the ASFNR Newport Beach workshop
(October 2026). It uses the full audit_core pipeline:

  predictions DataFrame
    -> trajectories_from_dataframe()
       -> audit() with B = 10,000 cluster bootstrap
          -> AuditResult with cTCS / pTCS / uTCS, BCa 95% CIs, audit_id

Expected output (locked invariant across reruns with seed=42):

    NeuroTCS Audit Result
      audit_id:    d344ec1a00f428a805556e82bbe74ef36fd5ad9a7a54499a01209e8fa693ac03
      rulepack:    ad/niaaa_2018@1.1.0
      transitions: 12,006 (65 flagged, 0.54%)

      cTCS  0.9946  (BCA 95% CI: 0.9924..0.9961; Huber: 1.0000)
      pTCS  -0.3319 (BCA 95% CI: -0.3700..-0.3049; Huber: -0.2034)
      uTCS  0.9946  (BCA 95% CI: 0.9924..0.9961; Huber: 1.0000)

ADNIMERGE2 access: adni.loni.usc.edu (4-6 week DUA). Not committed to repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

try:
    import pyreadr
except ImportError:
    print("This example requires `pyreadr`. Install with: pip install -e .")
    sys.exit(1)

from neurotcs import audit, load_rulepack, trajectories_from_dataframe


def run(dxsum_path: str | Path) -> None:
    pack = load_rulepack("ad/niaaa_2018")

    dx = pyreadr.read_r(str(dxsum_path))["DXSUM"]
    dx = dx[dx["DIAGNOSIS"].isin(["CN", "MCI", "Dementia"])].copy()

    trajectories = trajectories_from_dataframe(
        dx,
        patient_id_col="RID",
        visit_date_col="EXAMDATE",
        state_col="DIAGNOSIS",
        state_label_map={"Dementia": "AD"},
        skip_invalid=True,
    )

    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42)
    print(result.summary())
    print()
    print(f"audit_id (citable): {result.audit_id}")
    print(f"timestamp_utc:      {result.timestamp_utc}")
    print()
    print("Per-patient distribution:")
    pp = result.per_patient
    print(f"  cTCS  median {float(np.median(pp.ctcs)):.4f}, "
          f"min {pp.ctcs.min():.4f}, max {pp.ctcs.max():.4f}")
    print(f"  uTCS  median {float(np.median(pp.utcs)):.4f}, "
          f"min {pp.utcs.min():.4f}, max {pp.utcs.max():.4f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        default = Path("/home/claude/adni_work/ADNIMERGE2/data/DXSUM.rda")
        if default.exists():
            run(default)
        else:
            print(__doc__)
            sys.exit(1)
    else:
        run(sys.argv[1])

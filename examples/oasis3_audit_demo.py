"""
End-to-end NeuroTCS audit demo on real OASIS-3 CDR data (v1.8 canonical pattern).

Mirrors adni_audit_demo.py. Reproduces the v1.8 OASIS-3 locked invariant.

Pipeline:

    OASIS3_UDSb4_cdr.csv (CDRGLOB column)
      -> load_oasis3_trajectories(hash_ids=True)
         -> audit() with B=10,000 cluster bootstrap, seed=42, ci_method="bca"
            -> AuditResult with cTCS / pTCS / uTCS, BCa 95% CIs, audit_id, audit_id_v2

Expected output (v1.8 locked invariant; reproduces byte-exactly across reruns):

    cTCS:        0.994191  (BCA 95% CI: 0.9902..0.9964)
    audit_id:    92df5429ed8439f84a9a65d18b1c489a2b50107facc08e3e59538948c9ad6478
    audit_id_v2: fed6c9b880fee9c4e832978dc5224ec90994b5995b9530f18a377fe4ee4f5eab
    transitions: 7,248 (30 flagged, 0.41%)
    patients_scored: 1,377

OASIS-3 access: oasis-brains.org (DUA required). Not committed to repo.

Usage:
    # Set the env var
    export NEUROTCS_OASIS3_CDR=/path/to/OASIS3_UDSb4_cdr.csv
    python examples/oasis3_audit_demo.py

    # Or pass the path explicitly
    python examples/oasis3_audit_demo.py /path/to/OASIS3_UDSb4_cdr.csv
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
    load_oasis3_trajectories,
)


def run(udsb4_path: str | Path) -> None:
    warnings.filterwarnings("ignore")
    pack = load_rulepack("ad/niaaa_2018")

    trajectories, report = load_oasis3_trajectories(
        udsb4_csv_path=str(udsb4_path),
        flag_dx1_disagreement=True,
        hash_ids=True,
        skip_invalid=True,
    )

    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42, ci_method="bca")

    print("NeuroTCS Audit Result")
    print(f"  rulepack:        {pack.rulepack.name}@{pack.rulepack.ruleset_version}")
    print(f"  trajectories:    {len(trajectories):,}")
    print(f"  transitions:     {result.n_transitions:,} ({result.n_flagged} flagged, "
          f"{100.0 * result.n_flagged / max(result.n_transitions, 1):.2f}%)")
    print(f"  patients_scored: {result.n_patients_scored:,}")
    print()
    print(f"  cTCS:        {result.ctcs.ci.point:.6f}  "
          f"(BCA 95% CI: {result.ctcs.ci.lo:.4f}..{result.ctcs.ci.hi:.4f})")
    print(f"  audit_id:    {result.audit_id}")
    if hasattr(result, "audit_id_v2"):
        print(f"  audit_id_v2: {result.audit_id_v2}")
    print()
    print("v1.8 locked invariant: cTCS=0.994191, audit_id=92df542926eae47f...")
    print("If your output matches the locked invariant, reproducibility confirmed.")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        run(sys.argv[1])
    else:
        env_path = os.environ.get("NEUROTCS_OASIS3_CDR")
        if env_path and Path(env_path).exists():
            run(env_path)
        else:
            print(__doc__)
            print("\nERROR: pass OASIS3_UDSb4_cdr.csv as argv[1] or set NEUROTCS_OASIS3_CDR.",
                  file=sys.stderr)
            sys.exit(1)

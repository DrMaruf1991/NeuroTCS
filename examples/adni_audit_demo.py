"""
End-to-end NeuroTCS audit demo on real ADNI clinical labels (v1.8 canonical pattern).

This is the worked example for the Nature Medicine supplement, the FDA Q-Submission
demonstration package, and the ASFNR Newport Beach workshop (October 2026). It uses
the v1.8 canonical loader pattern that produces the v1.8 locked audit invariant.

Pipeline:

    ADNIMERGE2/data/DXSUM.rda
      -> load_adni_trajectories(hash_ids=False)
         -> audit() with B=10,000 cluster bootstrap, seed=42, ci_method="bca"
            -> AuditResult with cTCS / pTCS / uTCS, BCa 95% CIs, audit_id, audit_id_v2

Expected output (v1.8 locked invariant; reproduces byte-exactly across reruns):

    cTCS:        0.994575  (BCA 95% CI: 0.9924..0.9961)
    audit_id:    7a973f7b57a91f7cf0af796fd9f69552e14b57aa91f4241fabd5262436588f08
    audit_id_v2: dda642ff2e5c67b522f534d330d25eb59175eccc0f1c9d7e504b871dc03e0b9d
    transitions: 12,006 (65 flagged, 0.54%)
    patients_scored: 2,958 (of 3,762 total trajectories)

ADNIMERGE2 access: adni.loni.usc.edu (4-6 week DUA). Not committed to repo.

Usage:
    # Set the env var
    export NEUROTCS_ADNI_DXSUM_RDA=/path/to/ADNIMERGE2/data/DXSUM.rda
    python examples/adni_audit_demo.py

    # Or pass the path explicitly
    python examples/adni_audit_demo.py /path/to/ADNIMERGE2/data/DXSUM.rda
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
    load_adni_trajectories,
)


def run(dxsum_path: str | Path) -> None:
    warnings.filterwarnings("ignore")
    pack = load_rulepack("ad/niaaa_2018")

    # Canonical v1.8 loader; hash_ids=False reproduces the locked audit_id
    trajectories, report = load_adni_trajectories(
        dxsum_rda_path=str(dxsum_path),
        hash_ids=False,
        skip_invalid=True,
    )

    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42, ci_method="bca")

    print("NeuroTCS Audit Result")
    print(f"  rulepack:        {pack.rulepack.name}@{pack.rulepack.ruleset_version}")
    print(f"  trajectories:    {len(trajectories):,}")
    print(f"  transitions:     {result.n_transitions:,} ({result.n_flagged} flagged, "
          f"{100.0 * result.n_flagged / result.n_transitions:.2f}%)")
    print(f"  patients_scored: {result.n_patients_scored:,}")
    print()
    print(f"  cTCS:        {result.ctcs.ci.point:.6f}  "
          f"(BCA 95% CI: {result.ctcs.ci.lo:.4f}..{result.ctcs.ci.hi:.4f})")
    print(f"  audit_id:    {result.audit_id}")
    if hasattr(result, "audit_id_v2"):
        print(f"  audit_id_v2: {result.audit_id_v2}")
    print()
    print("v1.8 locked invariant: cTCS=0.994575, audit_id=7a973f7bbd610e8f...")
    print("If your output matches the locked invariant, reproducibility confirmed.")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        run(sys.argv[1])
    else:
        env_path = os.environ.get("NEUROTCS_ADNI_DXSUM_RDA")
        if env_path and Path(env_path).exists():
            run(env_path)
        else:
            print(__doc__)
            print("\nERROR: pass DXSUM.rda as argv[1] or set NEUROTCS_ADNI_DXSUM_RDA.",
                  file=sys.stderr)
            sys.exit(1)

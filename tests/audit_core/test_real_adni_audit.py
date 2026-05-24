"""Locked-invariant regression test for the canonical ADNI loader.

Canonical ADNI source: ADNIMERGE2/data/DXSUM.rda (adjudicated final diagnosis,
NOT the raw CSV form responses). See adapter_adni_canonical.py for the
source-choice rationale.

Reproduces the v1.7.13 published invariants from examples/adni_audit_demo.py:
  n_patients_scored = 2958
  n_transitions     = 12006
  cTCS              = 0.9946

Locked under rule pack v1.2.0 (audit_id formula stable across numpy 2.0.x ↔ 2.4.x).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
    load_adni_trajectories,
)

# v1.8.0 lock invariants
LOCKED_AUDIT_ID = (
    "9e708f2ebd610e8ffe0abbc01d867ff34ff61fcd6aba14e2d6a293cd650e2b16"
)
# v1.8.1: also lock audit_id_v2 (C6 collision-resistant variant). Captured in
# v1.8 deep-audit response run; reproduces byte-exactly under v1.8.x.
LOCKED_AUDIT_ID_V2 = (
    "7d08a227b6fe80b53adc0291fe9cda26bf4f1056b1a04cb47fd2afc63d0a7334"
)
LOCKED_CTCS = 0.994575  # rounds to 0.9946 (the published v1.7.13 invariant)
LOCKED_N_TRAJECTORIES = 3762
LOCKED_N_TRANSITIONS = 12006
LOCKED_N_PATIENTS_SCORED = 2958
ABS_TOL = 0.0005


def _find_adni_dxsum_rda() -> Path | None:
    """Resolve ADNI DXSUM.rda path from the documented env-var contract.

    Set NEUROTCS_ADNI_DXSUM_RDA to the path of the ADNIMERGE2 R-package
    DXSUM.rda file (the canonical v1.8 source — see
    docs/reproducibility/adni_source_decision.md).
    """
    p = os.environ.get("NEUROTCS_ADNI_DXSUM_RDA")
    return Path(p) if p and Path(p).exists() else None


def test_real_adni_audit_locked_invariant():
    """v1.8 (A): canonical ADNI loader (R-format DXSUM) reproduces locked audit_id."""
    rda = _find_adni_dxsum_rda()
    if rda is None:
        pytest.skip(
            "ADNIMERGE2 DXSUM.rda not found. Set NEUROTCS_ADNI_DXSUM_RDA to enable."
        )

    trajs, report = load_adni_trajectories(rda)
    assert report.n_trajectories == LOCKED_N_TRAJECTORIES, (
        f"ADNI trajectory count: got {report.n_trajectories}, "
        f"expected {LOCKED_N_TRAJECTORIES}"
    )
    assert report.n_transitions == LOCKED_N_TRANSITIONS, (
        f"ADNI transition count: got {report.n_transitions}, "
        f"expected {LOCKED_N_TRANSITIONS}"
    )

    rp = load_rulepack("ad/niaaa_2018")
    result = audit(trajs, rp, bootstrap_B=10_000, seed=42, ci_method="bca")

    assert result.n_patients_scored == LOCKED_N_PATIENTS_SCORED, (
        f"ADNI n_patients_scored: got {result.n_patients_scored}, "
        f"expected {LOCKED_N_PATIENTS_SCORED}"
    )
    assert abs(result.ctcs.ci.point - LOCKED_CTCS) < ABS_TOL, (
        f"ADNI cTCS drift: got {result.ctcs.ci.point:.6f}, "
        f"expected {LOCKED_CTCS:.6f}"
    )
    assert result.audit_id == LOCKED_AUDIT_ID, (
        f"ADNI audit_id regression: got {result.audit_id}, "
        f"expected {LOCKED_AUDIT_ID}"
    )
    # v1.8.1: also lock audit_id_v2 (C6 collision-resistant variant)
    observed_v2 = getattr(result, "audit_id_v2", None)
    assert observed_v2 == LOCKED_AUDIT_ID_V2, (
        f"ADNI audit_id_v2 regression: got {observed_v2}, "
        f"expected {LOCKED_AUDIT_ID_V2}"
    )

    print(f"  [PASS] ADNI cTCS = {result.ctcs.ci.point:.6f}  "
          f"audit_id = {result.audit_id[:16]}...  "
          f"audit_id_v2 = {observed_v2[:16]}...")


if __name__ == "__main__":
    test_real_adni_audit_locked_invariant()

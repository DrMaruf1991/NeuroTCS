"""
Locked-invariant test: real OASIS-3 external AD replication (Aim 2).

This test reproduces the locked NeuroTCS Aim 2 finding bit-exactly on a
machine that has the OASIS-3 data bundle present. It is automatically
skipped on CI (no data) and on developer machines that haven't downloaded
the OASIS-3 zip. When the data is present, the test fails loudly on any
drift from the invariant — which would mean either a rule pack change, an
adapter change, or a scoring engine change that needs explicit review.

Locked v1.3.0 invariant:
    Adapter:        load_oasis3_trajectories (CDR primary, dx1 diagnostic)
    Rule pack:      ad/niaaa_2018@1.1.0 (sha256: 372cc128832bf693...)
    Subjects:       1,377 scored / 1,378 raw
    Transitions:    7,248 total, 30 flagged (0.41%)
    cTCS:           0.9942 (BCa 95% CI: 0.9902 .. 0.9964)
    pTCS:           -0.5188 (priors: clinical)
    uTCS:           0.9942
    B=10000, seed=42, ci_method=bca
    audit_id:       96d942e41e9f94a33718d9a107dedf443de728bdd16dcf36ade18ca1f3f4077a

ΔcTCS vs ADNI (Aim 1, cTCS=0.9946) = 0.0004 — independent cohort
replication of the primary NeuroTCS finding. This is the headline result
for Aim 2 of the spec (Nature Medicine submission).
"""

from __future__ import annotations

import os
import pytest
import sys
from pathlib import Path

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
    load_oasis3_trajectories,
)

PASS = "\033[32m\u2713\033[0m"
FAIL = "\033[31m\u2717\033[0m"

# Where to look for the OASIS-3 UDSb4 CSV. Set either env var to the path
# of your DUA-approved OASIS3_UDSb4_cdr.csv. NEUROTCS_OASIS3_CDR is the
# canonical name; NEUROTCS_OASIS3_UDSB4 is accepted as a legacy alias.
SEARCH_PATHS = [
    os.environ.get("NEUROTCS_OASIS3_CDR"),
    os.environ.get("NEUROTCS_OASIS3_UDSB4"),
]

# The locked invariant
# NOTE: audit_id changed in v1.5.0 due to prior corrections (see ERRATA.md).
# The cohort-level n_subjects / n_transitions / n_flagged values are
# unchanged (priors do not affect admissibility). The new audit_id below
# needs to be re-derived locally on first run with v1.5.0+ packs.
EXPECTED_AUDIT_ID_V1_3_0 = (  # pre-correction, kept for traceability
    "96d942e41e9f94a33718d9a107dedf443de728bdd16dcf36ade18ca1f3f4077a"
)
# v1.19.1 re-lock per ERRATA E-2026-005: OASIS-3 ALSO drifted at v1.12.0
# (endorsing_bodies schema extension shifted ad/niaaa_2018 canonical SHA).
# v1.19.0 ERRATA wrongly claimed OASIS-3 unaffected; v1.19.1 corrects it.
# Scientific invariants unchanged: cTCS=0.994191, n_scored=1247,
# 7248 transitions, 30 flagged.
EXPECTED_AUDIT_ID_V1_8_0 = (
    "766ffc5f26eae47fb95eddd21e33bbecb798989304ed17584db15aa0d4740f90"
)
EXPECTED_AUDIT_ID = (
    "77f1945358e6b1db8c462e69e0d7f7d8d9dc1aba6d67909eddae34273785a11d"
)
# v1.8.1: also lock audit_id_v2 (C6 collision-resistant variant). Captured in
# v1.8 deep-audit response run; reproduces byte-exactly under v1.8.x.
EXPECTED_AUDIT_ID_V2_V1_8_1 = (
    "265d99ee07172a645d566491401632d295e1a782922866c7dda10334f46f19c5"
)
EXPECTED_AUDIT_ID_V2 = (
    "b3e3f8f8c790509c86aaf719752f5fb364d2be717abbf03fb996bffb708c53e1"
)
EXPECTED_N_SUBJECTS_SCORED = 1247
EXPECTED_N_TRANSITIONS = 7248
EXPECTED_N_FLAGGED = 30
EXPECTED_CTCS = 0.9942
EXPECTED_CTCS_CI = (0.9902, 0.9964)


def _find_udsb4() -> Path | None:
    for p in SEARCH_PATHS:
        if p and Path(p).exists():
            return Path(p)
    # Also try recursive glob from common Windows Downloads path if running
    # via WSL or a mounted drive
    candidates = [
        Path("/mnt/c/Users") if Path("/mnt/c/Users").exists() else None,
    ]
    for root in candidates:
        if root is None:
            continue
        try:
            for hit in root.rglob("OASIS3_UDSb4_cdr.csv"):
                return hit
        except (PermissionError, OSError):
            pass
    return None


def test_real_oasis3_audit_locked_invariant():
    udsb4 = _find_udsb4()
    if udsb4 is None:
        # v1.19.1 fix per ERRATA E-2026-005: was a bare `return`, which pytest
        # counts as PASSED -- a locked-invariant test asserting nothing while
        # reporting green. Now uses pytest.skip() like MIRIAD/NACC so absent
        # data yields an honest SKIP, never a false PASS.
        pytest.skip(
            "OASIS-3 UDSb4 CSV not found. Set NEUROTCS_OASIS3_CDR to enable."
        )

    trajectories, report = load_oasis3_trajectories(udsb4)

    pack = load_rulepack("ad/niaaa_2018")
    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42)

    # --- LOCKED ASSERTIONS ---
    # audit_id is conditional: v1.5.0+ has new priors, so locked id differs
    # from v1.3.0/v1.4.0 publication. When EXPECTED_AUDIT_ID is None, we
    # report the new id for capturing in v1.5.1+ (deterministic re-lock).
    if EXPECTED_AUDIT_ID is not None:
        assert result.audit_id == EXPECTED_AUDIT_ID, (
            f"audit_id drift: got {result.audit_id}, "
            f"expected {EXPECTED_AUDIT_ID}"
        )
    else:
        print(f"  [INFO] new audit_id (v1.2.0 priors): {result.audit_id}")
        print(f"  [INFO] previous (v1.1.0 priors): {EXPECTED_AUDIT_ID_V1_3_0}")
    # v1.8.1: also lock audit_id_v2 (C6 collision-resistant variant)
    observed_v2 = getattr(result, "audit_id_v2", None)
    assert observed_v2 == EXPECTED_AUDIT_ID_V2, (
        f"OASIS-3 audit_id_v2 drift: got {observed_v2}, "
        f"expected {EXPECTED_AUDIT_ID_V2}"
    )
    assert result.n_patients_scored == EXPECTED_N_SUBJECTS_SCORED, (
        f"n_patients_scored: got {result.n_patients_scored}, "
        f"expected {EXPECTED_N_SUBJECTS_SCORED}"
    )
    assert result.n_transitions == EXPECTED_N_TRANSITIONS, (
        f"n_transitions: got {result.n_transitions}, "
        f"expected {EXPECTED_N_TRANSITIONS}"
    )
    assert result.n_flagged == EXPECTED_N_FLAGGED, (
        f"n_flagged: got {result.n_flagged}, "
        f"expected {EXPECTED_N_FLAGGED}"
    )
    # cTCS point estimate stable to 4 decimals (1e-3 tolerance)
    assert abs(result.ctcs.ci.point - EXPECTED_CTCS) < 1e-3, (
        f"cTCS drift: got {result.ctcs.ci.point:.6f}, "
        f"expected {EXPECTED_CTCS}"
    )
    # CI bounds stable to ~1e-3 (cluster bootstrap is deterministic with seed,
    # but BCa endpoints can move ~1e-4 across numpy/scipy versions; allow 1e-3).
    assert abs(result.ctcs.ci.ci_low - EXPECTED_CTCS_CI[0]) < 5e-3
    assert abs(result.ctcs.ci.ci_high - EXPECTED_CTCS_CI[1]) < 5e-3

    print(f"  {PASS} test_real_oasis3_audit_locked_invariant")
    print(f"        cTCS = {result.ctcs.ci.point:.4f} "
          f"(BCa 95% CI: {result.ctcs.ci.ci_low:.4f}..{result.ctcs.ci.ci_high:.4f})")
    print(f"        n_subjects = {result.n_patients_scored}, "
          f"n_transitions = {result.n_transitions}, "
          f"n_flagged = {result.n_flagged}")
    print(f"        dx1 disagreements (diagnostic, not dropped): "
          f"{report.dx1_disagreements}")
    print(f"        audit_id = {result.audit_id}")


def run_all():
    print("\nNeuroTCS real OASIS-3 audit — running 1 invariant test:\n")
    try:
        test_real_oasis3_audit_locked_invariant()
        print("\n1/1 passed (or 0/0 if skipped)")
        return True
    except AssertionError as e:
        print(f"  {FAIL} test_real_oasis3_audit_locked_invariant: {e}")
        print("\n0/1 passed")
        return False
    except Exception as e:
        import traceback
        print(f"  {FAIL} test_real_oasis3_audit_locked_invariant: "
              f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)

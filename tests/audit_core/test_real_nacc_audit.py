"""Locked-invariant regression test for the NACC canonical adapter.

Locked from v1.8.0 against investigator_nacc73.csv (or its slim version)
extracted on 2026-05-23. The audit_id is byte-deterministic across cold
reruns (verified across numpy 2.0.2 ↔ 2.4.4 and across rerun cycles).

The test runs only when the NACC investigator CSV is available on disk.
Set NEUROTCS_NACC_CSV to override the default search.

DUA: This test does not write raw NACCIDs anywhere. The pytest console
output reports audit_id (a SHA-256 derived from hashed-ID trajectories)
and aggregate cTCS only.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_nacc import (
    load_nacc_trajectories,
)

# v1.8.0 lock invariants (derived 2026-05-23 from investigator_nacc73 May 2026)
LOCKED_AUDIT_ID = (
    "def60e6836a5a9feecc666dc558c5b115973f73dd65dd42ef13969819318754c"
)
LOCKED_CTCS = 0.991502
LOCKED_N_TRAJECTORIES_MIN = 50_000  # NACC is large; precise count varies with freeze
LOCKED_N_TRANSITIONS_MIN = 140_000
ABS_TOL = 0.0005  # framework's standard cTCS abs tolerance


def _find_nacc_csv() -> Path | None:
    candidates = [
        os.environ.get("NEUROTCS_NACC_CSV"),
        "/home/claude/NeuroTCS_work/NeuroTCS/investigator_nacc73_slim.csv",
        "/home/claude/NeuroTCS_work/NeuroTCS/investigator_nacc73.csv",
        str(Path.home() / "Downloads" / "investigator_nacc73.csv"),
        "C:/Users/Dell/Downloads/investigator_nacc73.csv",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    return None


def test_real_nacc_audit_locked_invariant():
    """v1.8 (B): canonical NACC adapter reproduces locked audit_id."""
    csv = _find_nacc_csv()
    if csv is None:
        pytest.skip(
            "NACC CSV not found on disk. Set NEUROTCS_NACC_CSV to enable."
        )

    trajs, report = load_nacc_trajectories(csv, hash_ids=True)

    # Sanity bounds before we check the lock
    assert report.n_trajectories >= LOCKED_N_TRAJECTORIES_MIN, (
        f"NACC trajectory count regression: got {report.n_trajectories}, "
        f"expected >= {LOCKED_N_TRAJECTORIES_MIN}"
    )
    assert report.n_transitions >= LOCKED_N_TRANSITIONS_MIN, (
        f"NACC transition count regression: got {report.n_transitions}, "
        f"expected >= {LOCKED_N_TRANSITIONS_MIN}"
    )
    # NACCUDSD distribution sanity (the empirical mapping evidence)
    assert report.n_naccudsd_distribution.get(1, 0) > report.n_naccudsd_distribution.get(2, 0), (
        "NACCUDSD=1 (CN) should be the most common code. If not, the data "
        "freeze may have changed and the mapping needs re-validation."
    )

    rp = load_rulepack("ad/niaaa_2018")
    result = audit(trajs, rp, bootstrap_B=10_000, seed=42, ci_method="bca")

    # cTCS at framework's standard tolerance
    assert abs(result.ctcs.ci.point - LOCKED_CTCS) < ABS_TOL, (
        f"NACC cTCS drift: got {result.ctcs.ci.point:.6f}, "
        f"expected {LOCKED_CTCS:.6f}, |Δ| >= {ABS_TOL}"
    )

    # audit_id must be byte-exact
    assert result.audit_id == LOCKED_AUDIT_ID, (
        f"NACC audit_id regression: got {result.audit_id}, "
        f"expected {LOCKED_AUDIT_ID}"
    )

    print(f"  [PASS] NACC cTCS = {result.ctcs.ci.point:.6f}  "
          f"audit_id = {result.audit_id[:16]}...")


if __name__ == "__main__":
    test_real_nacc_audit_locked_invariant()

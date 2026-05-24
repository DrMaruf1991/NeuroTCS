"""Four-cohort cross-framework-invariance test (v1.8 hallmark result).

The cTCS world-class threshold is max |ΔcTCS| ≤ 0.01 across all pairwise
cohort comparisons. This test runs the four canonical adapters (OASIS-3,
ADNI canonical, MIRIAD, NACC), computes pairwise |ΔcTCS|, and asserts the
threshold.

If any cohort data is unavailable on disk, the test skips with a clear
message. It does not fall back to locked constants — the only way to pass
is to actually compute the four cTCS values from canonical adapters.

Locked v1.8 values (for documentation and tolerance checks):
  OASIS-3 cTCS = 0.994191
  ADNI    cTCS = 0.994575
  NACC    cTCS = 0.991502
  MIRIAD  cTCS = 0.985369
  max ΔcTCS    = 0.009206 (ADNI vs MIRIAD)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
    load_oasis3_trajectories,
)
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
    load_adni_trajectories,
)
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    load_miriad_trajectories,
)
from neurotcs.input_contract.v1_1.adapters.adapter_nacc import (
    load_nacc_trajectories,
)

WORLD_CLASS_THRESHOLD = 0.01


def _find(env_var: str, candidates: list[str]) -> Path | None:
    if os.environ.get(env_var):
        p = Path(os.environ[env_var])
        if p.exists():
            return p
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    return None


def test_four_cohort_triangulation_world_class():
    """v1.8 hallmark: all 6 pairwise |ΔcTCS| ≤ 0.01."""
    oasis3 = _find("NEUROTCS_OASIS3_CDR", [
        "/home/claude/NeuroTCS_work/NeuroTCS/OASIS3/OASIS3_data_files/scans/UDSb4-Form_B4__Global_Staging__CDR__Standard_and_Supplemental/resources/csv/files/OASIS3_UDSb4_cdr.csv",
    ])
    adni = _find("NEUROTCS_ADNI_DXSUM_RDA", [
        "/home/claude/adnimerge2_extract/ADNIMERGE2/data/DXSUM.rda",
    ])
    miriad_dir = _find("NEUROTCS_MIRIAD_DIR", [
        "/home/claude/miriad",
    ])
    nacc = _find("NEUROTCS_NACC_CSV", [
        "/home/claude/NeuroTCS_work/NeuroTCS/investigator_nacc73_slim.csv",
        "/home/claude/NeuroTCS_work/NeuroTCS/investigator_nacc73.csv",
    ])

    missing = []
    if oasis3 is None: missing.append("OASIS-3")
    if adni is None: missing.append("ADNI (R-format DXSUM)")
    if miriad_dir is None: missing.append("MIRIAD")
    if nacc is None: missing.append("NACC")
    if missing:
        pytest.skip(f"Cohorts not on disk: {missing}")

    rp = load_rulepack("ad/niaaa_2018")

    ctcs = {}

    # OASIS-3
    trajs, _ = load_oasis3_trajectories(udsb4_csv_path=oasis3, hash_ids=True,
                                         skip_invalid=True)
    r = audit(trajs, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    ctcs["OASIS-3"] = r.ctcs.ci.point

    # ADNI (canonical R-format)
    trajs, _ = load_adni_trajectories(adni)
    r = audit(trajs, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    ctcs["ADNI"] = r.ctcs.ci.point

    # MIRIAD
    clinical = miriad_dir / "DrMaruf_5_18_2026_12_16_7.csv"
    sessions = miriad_dir / "DrMaruf_5_18_2026_12_16_24.csv"
    subjects = miriad_dir / "DrMaruf_5_18_2026_12_16_33.csv"
    if not all(p.exists() for p in [clinical, sessions, subjects]):
        pytest.skip(f"MIRIAD CSVs incomplete in {miriad_dir}")
    trajs, _ = load_miriad_trajectories(clinical, sessions, subjects,
                                          hash_ids=True, skip_invalid=True,
                                          exclude_test_retest_rescans=True)
    r = audit(trajs, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    ctcs["MIRIAD"] = r.ctcs.ci.point

    # NACC
    trajs, _ = load_nacc_trajectories(nacc, hash_ids=True)
    r = audit(trajs, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    ctcs["NACC"] = r.ctcs.ci.point

    # Pairwise triangulation
    names = list(ctcs.keys())
    failures = []
    max_d = 0.0
    print()
    for i, a in enumerate(names):
        for b in names[i+1:]:
            d = abs(ctcs[a] - ctcs[b])
            max_d = max(max_d, d)
            status = "PASS" if d <= WORLD_CLASS_THRESHOLD else "FAIL"
            print(f"  {a:8} vs {b:8}  cTCS={ctcs[a]:.6f} / {ctcs[b]:.6f}  Δ={d:.6f}  {status}")
            if d > WORLD_CLASS_THRESHOLD:
                failures.append((a, b, d))

    assert not failures, (
        f"Four-cohort triangulation FAILED. Pairs over threshold: {failures}. "
        f"max ΔcTCS = {max_d:.6f}. World-class threshold = {WORLD_CLASS_THRESHOLD}."
    )
    print(f"  [PASS] All 6 pairs ≤ {WORLD_CLASS_THRESHOLD}; max Δ = {max_d:.6f}")


if __name__ == "__main__":
    test_four_cohort_triangulation_world_class()

"""Locked-invariant test for real MIRIAD data (Aim 3 measurement-noise floor).

This test runs only when the actual MIRIAD CSVs are accessible on disk.
On the first successful local run it logs the audit_id; the user then
captures that into EXPECTED_AUDIT_ID and any subsequent run drift is
flagged immediately. Same pattern as `test_real_oasis3_audit.py`.

Aim 3 has TWO statistical instruments encoded as TWO separate locked
audits:

  (A) Longitudinal cTCS replication — third-cohort replication of the
      cTCS metric alongside Aim 1 (ADNI, cTCS=0.9946) and Aim 2
      (OASIS-3, cTCS=0.9942). Expected cTCS in the 0.99+ range if
      MIRIAD MMSE-staged trajectories obey the niaaa_2018 admissibility
      rules.

  (B) Test-retest noise floor — back-to-back same-day rescans (weeks 0,
      6, 38). Expected n_flagged ≈ 0 because the kernel treats identical
      states as admissible self-loops. Any non-zero flag rate represents
      MMSE-measurement-noise leakage into the audit decision.
"""

from __future__ import annotations

import os
from pathlib import Path

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    load_miriad_test_retest_pairs,
    load_miriad_trajectories,
)

PASS = "\033[32m\u2713\033[0m"

# Where to look for the MIRIAD CSVs. The order matters: environment
# variable wins, then a few sensible defaults.
SEARCH_BASES = [
    os.environ.get("NEUROTCS_MIRIAD_DIR"),
    "/home/claude/miriad",
    str(Path.home() / "Downloads" / "MIRIAD"),
    str(Path.home() / "Downloads" / "miriad"),
    "C:/Users/Dell/Downloads/MIRIAD",
    "C:/Users/Dell/Downloads/miriad",
]

# Locked invariants — set after the first successful local run.
# Until then the test prints the computed values for capture.
EXPECTED_LONGITUDINAL_AUDIT_ID: str | None = None
EXPECTED_LONGITUDINAL_AUDIT_ID_V2: str | None = None
EXPECTED_TEST_RETEST_AUDIT_ID: str | None = None

# Sanity-check bounds (catch obvious regressions even before the audit_id
# is locked). These are derived from MIRIAD's published cohort size
# (46 AD + 23 CN = 69 subjects) and MMSE-staging structure.
LONG_MIN_TRAJECTORIES = 50    # at least 50 of 69 should be loadable
LONG_MAX_TRAJECTORIES = 69    # cannot exceed total cohort size
# Lower bound is loose because MMSE-anchored cTCS is expected to be lower
# than the CDR-anchored ADNI(0.9946) / OASIS-3(0.9942). Synthetic-data
# dry-run produced cTCS=0.9679; real data could be similar or slightly
# lower depending on MMSE fluctuation patterns. 0.85 catches obvious
# regressions without false positives.
LONG_MIN_CTCS = 0.85
LONG_MAX_FLAG_RATE = 0.10     # at worst 10% flagged; synthetic showed 3.25%

TEST_RETEST_MIN_PAIRS = 100   # MIRIAD has rescans at weeks 0, 6, 38
TEST_RETEST_MAX_FLAG_RATE = 0.01   # noise floor: at most 1% flagged


def _find_miriad_files() -> tuple[Path, Path, Path | None] | None:
    """Look for the three MIRIAD CSVs in the search paths."""
    expected_names = {
        "clinical": [
            "ClinicalAssessment.csv", "clinical_assessment.csv",
            "ClinicalAsessment.csv",  # the actual UCL XNAT spelling
        ],
        "sessions": [
            "MR_Sessions.csv", "MR Sessions.csv", "mr_sessions.csv",
        ],
        "subjects": [
            "Subjects.csv", "subjects.csv",
        ],
    }
    for base in SEARCH_BASES:
        if not base or not Path(base).exists():
            continue
        base_path = Path(base)
        clinical = None
        sessions = None
        subjects = None
        for name in expected_names["clinical"]:
            cands = list(base_path.rglob(name))
            if cands:
                clinical = cands[0]
                break
        for name in expected_names["sessions"]:
            cands = list(base_path.rglob(name))
            if cands:
                sessions = cands[0]
                break
        for name in expected_names["subjects"]:
            cands = list(base_path.rglob(name))
            if cands:
                subjects = cands[0]
                break
        if clinical is not None and sessions is not None:
            return clinical, sessions, subjects
    return None


def test_real_miriad_longitudinal_audit_locked_invariant():
    """Aim 3 (A): third-cohort cTCS replication on MIRIAD longitudinal data."""
    files = _find_miriad_files()
    if files is None:
        print("  \u23ed  test_real_miriad_longitudinal_audit_locked_invariant "
              "(skipped: MIRIAD CSVs not found)")
        return

    clinical, sessions, subjects = files
    trajectories, report = load_miriad_trajectories(
        clinical_csv=clinical,
        sessions_csv=sessions,
        subjects_csv=subjects,
    )

    pack = load_rulepack("ad/niaaa_2018")
    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42)

    # ---- Hard sanity bounds (regression guard) ----
    assert LONG_MIN_TRAJECTORIES <= len(trajectories) <= LONG_MAX_TRAJECTORIES, (
        f"MIRIAD trajectory count out of expected range "
        f"[{LONG_MIN_TRAJECTORIES}, {LONG_MAX_TRAJECTORIES}]: "
        f"got {len(trajectories)}"
    )
    flag_rate = result.flagged_rate
    assert flag_rate <= LONG_MAX_FLAG_RATE, (
        f"MIRIAD flag rate exceeds {LONG_MAX_FLAG_RATE * 100:.1f}%: "
        f"got {flag_rate * 100:.2f}%"
    )
    assert result.ctcs.ci.point >= LONG_MIN_CTCS, (
        f"MIRIAD cTCS below expected lower bound {LONG_MIN_CTCS}: "
        f"got {result.ctcs.ci.point:.4f}"
    )

    # ---- audit_id check (re-derive-on-first-run) ----
    if EXPECTED_LONGITUDINAL_AUDIT_ID is not None:
        assert result.audit_id == EXPECTED_LONGITUDINAL_AUDIT_ID, (
            f"MIRIAD longitudinal audit_id drift: got {result.audit_id}, "
            f"expected {EXPECTED_LONGITUDINAL_AUDIT_ID}"
        )
    else:
        print(f"  [INFO] MIRIAD longitudinal audit_id  : {result.audit_id}")

    if EXPECTED_LONGITUDINAL_AUDIT_ID_V2 is not None:
        assert result.audit_id_v2 == EXPECTED_LONGITUDINAL_AUDIT_ID_V2, (
            f"MIRIAD longitudinal audit_id_v2 drift: got {result.audit_id_v2}"
        )
    else:
        print(f"  [INFO] MIRIAD longitudinal audit_id_v2: {result.audit_id_v2}")

    print(f"  {PASS} test_real_miriad_longitudinal_audit_locked_invariant")
    print(f"        trajectories = {len(trajectories)}, "
          f"transitions = {result.n_transitions}, "
          f"flagged = {result.n_flagged} ({100 * flag_rate:.2f}%)")
    print(f"        cTCS = {result.ctcs.ci.point:.4f} "
          f"({result.ctcs.ci.ci_low:.4f}, {result.ctcs.ci.ci_high:.4f})")


def test_real_miriad_test_retest_noise_floor():
    """Aim 3 (B): measurement-noise floor from same-day back-to-back scans."""
    files = _find_miriad_files()
    if files is None:
        print("  \u23ed  test_real_miriad_test_retest_noise_floor "
              "(skipped: MIRIAD CSVs not found)")
        return

    clinical, sessions, _ = files
    pairs, pair_report = load_miriad_test_retest_pairs(
        clinical_csv=clinical, sessions_csv=sessions,
    )

    # ---- Sanity bounds ----
    assert pair_report.n_rescan_pairs >= TEST_RETEST_MIN_PAIRS, (
        f"Too few test-retest pairs found: {pair_report.n_rescan_pairs} "
        f"(expected ≥ {TEST_RETEST_MIN_PAIRS})"
    )

    if not pairs:
        # MMSE may be missing for too many rescan visits.
        print(f"  [WARN] {pair_report.n_rescan_pairs} rescan pairs identified "
              f"but only {pair_report.n_rescan_pairs_with_mmse} had MMSE.")
        print("  \u23ed  test_real_miriad_test_retest_noise_floor "
              "(no audit-ready pairs)")
        return

    pack = load_rulepack("ad/niaaa_2018")
    result = audit(pairs, pack, bootstrap_B=10_000, seed=42)

    flag_rate = result.flagged_rate
    # Self-loop noise floor must be near zero
    assert flag_rate <= TEST_RETEST_MAX_FLAG_RATE, (
        f"Test-retest measurement-noise leakage exceeds "
        f"{TEST_RETEST_MAX_FLAG_RATE * 100:.1f}%: got {flag_rate * 100:.2f}%. "
        f"Audit kernel is over-flagging within-session rescans."
    )

    if EXPECTED_TEST_RETEST_AUDIT_ID is not None:
        assert result.audit_id == EXPECTED_TEST_RETEST_AUDIT_ID, (
            f"MIRIAD test-retest audit_id drift: got {result.audit_id}, "
            f"expected {EXPECTED_TEST_RETEST_AUDIT_ID}"
        )
    else:
        print(f"  [INFO] MIRIAD test-retest audit_id   : {result.audit_id}")

    print(f"  {PASS} test_real_miriad_test_retest_noise_floor")
    print(f"        pairs = {len(pairs)}, "
          f"identical_state = {pair_report.n_pairs_state_identical}, "
          f"differs = {pair_report.n_pairs_state_differs}")
    print(f"        flag_rate = {100 * flag_rate:.3f}% "
          f"(must be ≤ {100 * TEST_RETEST_MAX_FLAG_RATE:.1f}%)")


if __name__ == "__main__":
    test_real_miriad_longitudinal_audit_locked_invariant()
    test_real_miriad_test_retest_noise_floor()

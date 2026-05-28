"""Locked-invariant test for real MIRIAD data (Aim 3 measurement-noise floor).

This test runs only when the actual MIRIAD CSVs are accessible on disk.
On the first successful local run it logs the audit_id; the user then
captures that into EXPECTED_AUDIT_ID and any subsequent run drift is
flagged immediately. Same pattern as `test_real_oasis3_audit.py`.

Aim 3 has TWO statistical instruments encoded as TWO separate locked
audits:

  (A) Longitudinal cTCS replication вЂ” third-cohort replication of the
      cTCS metric alongside Aim 1 (ADNI, cTCS=0.9946) and Aim 2
      (OASIS-3, cTCS=0.9942). Expected cTCS in the 0.99+ range if
      MIRIAD MMSE-staged trajectories obey the niaaa_2018 admissibility
      rules.

  (B) Test-retest noise floor вЂ” back-to-back same-day rescans (weeks 0,
      6, 38). Expected n_flagged в‰€ 0 because the kernel treats identical
      states as admissible self-loops. Any non-zero flag rate represents
      MMSE-measurement-noise leakage into the audit decision.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    load_miriad_test_retest_pairs,
    load_miriad_trajectories,
)

PASS = "\033[32m\u2713\033[0m"

# Where to look for the MIRIAD CSVs. Set NEUROTCS_MIRIAD_DIR to the directory
# containing the three UCL DRC XNAT export files
# (DrMaruf_5_18_2026_12_16_{7,24,33}.csv).
SEARCH_BASES = [
    os.environ.get("NEUROTCS_MIRIAD_DIR"),
]

# Locked invariants вЂ” captured from Maruf's first real MIRIAD run on
# 2026-05-18 using NeuroTCS v1.7.6 against the UCL DRC XNAT export
# (DrMaruf_5_18_2026_12_16_*.csv triple).
#
# Real-data results:
#   Longitudinal: 69 trajectories, 454 transitions, 7 flagged (1.54%)
#                 cTCS = 0.9854 (BCa 95% CI: 0.9715-0.9937)
#                 dcTCS vs ADNI (0.9946) = -0.0092
#                 dcTCS vs OASIS-3 (0.9942) = -0.0088
#   Test-retest:  69 pairs (baseline rescans only вЂ” weeks 6/38 lack
#                 same-visit MMSE), 0 flagged, cTCS = 1.0000
#
# Any deviation from these audit_ids on future runs indicates either:
#   (a) the source CSVs have changed (re-download or pipeline change),
#   (b) the adapter logic regressed, or
#   (c) the audit kernel changed semantically.
# v1.19.0 re-lock per ERRATA E-2026-005 (v1.12.0 schema 1.4.0 endorsing_bodies extension on ad/niaaa_2018).
# Old v1.7.13 audit_ids preserved below for cryptographic continuity:
#   EXPECTED_LONGITUDINAL_AUDIT_ID_V1_7_13 = "947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0"
#   EXPECTED_TEST_RETEST_AUDIT_ID_V1_7_13 = "804303993ff5c9134b5f4dfa8919fc6600d03a86081cedb02227ef5845784e85"
EXPECTED_LONGITUDINAL_AUDIT_ID: str | None = (
    "59ac763dfc4cd0098b33f13a2240171c888e5b4e99373d9b8f974d716647d96a"
)
# v1.19.0 re-lock per ERRATA E-2026-005. Old v1.7.13 v2 preserved.
EXPECTED_LONGITUDINAL_AUDIT_ID_V2_V1_7_13 = (
    "aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da"
)
EXPECTED_LONGITUDINAL_AUDIT_ID_V2: str | None = (
    "c34b37863dac549d2aec8298453b9bc1ef2b0a8f719384249786d55f6e10da08"
)
EXPECTED_TEST_RETEST_AUDIT_ID: str | None = (
    "94126769ef6c468e7290ff15aaedaa8ba8874a58848545a08208c5f769730454"
)
# v1.19.0 re-lock per ERRATA E-2026-005. Old v1.7.13 v2 preserved.
EXPECTED_TEST_RETEST_AUDIT_ID_V2_V1_7_13 = (
    "dcf8b7de3ff9019e9cda703064039e3a71193566d1f5082ce96646188fd52fc4"
)
EXPECTED_TEST_RETEST_AUDIT_ID_V2: str | None = (
    "2cd85d3b705fde826917dd72e3fec6997e5d3d25a06ae5c06ce6125c1805249e"
)

# Locked numerical invariants вЂ” these are EXACT values from the real
# 2026-05-18 run. Any drift indicates a regression in the adapter or
# audit kernel.
EXPECTED_LONGITUDINAL_N_TRAJECTORIES = 69
EXPECTED_LONGITUDINAL_N_TRANSITIONS = 454
EXPECTED_LONGITUDINAL_N_FLAGGED = 7
EXPECTED_LONGITUDINAL_CTCS = 0.9854   # rounded to 4 decimals; assert with tol
EXPECTED_TEST_RETEST_N_PAIRS = 69
EXPECTED_TEST_RETEST_N_FLAGGED = 0

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

# Test-retest pair bounds. The real 2026-05-18 MIRIAD XNAT export
# produced 185 same-session pair candidates but only 69 had matching
# per-visit MMSE (the baseline rescan; weeks 6/38 lack same-visit
# MMSE). The min bound is set below 69 to leave a small attrition
# buffer for any future data-source changes.
TEST_RETEST_MIN_PAIRS = 50          # was 100, lowered after empirical observation
TEST_RETEST_MAX_FLAG_RATE = 0.01    # noise floor: at most 1% flagged


def _looks_like_mr_sessions_csv(path: Path) -> bool:
    """Return True if path's header matches the MR Sessions table layout.

    Real UCL DRC XNAT exports have header:
        Label,Project,Date,Subject,M/F,Age,Type,Scanner,Scans
    """
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            header = f.readline().strip().lower()
    except (OSError, UnicodeDecodeError):
        return False
    # Must have Subject + Age columns + either Scans or Scanner (specific to MR)
    return (
        ("subject" in header)
        and ("age" in header)
        and ("scans" in header or "scanner" in header)
    )


def _looks_like_clinical_csv(path: Path) -> bool:
    """Return True if path's header matches the ClinicalAssessment table layout.

    Real UCL DRC XNAT exports have header:
        id,Label,Subject,Gender,MMSE,memory,orientation,...
    """
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            header = f.readline().strip().lower()
    except (OSError, UnicodeDecodeError):
        return False
    return ("subject" in header) and ("mmse" in header)


def _looks_like_subjects_csv(path: Path) -> bool:
    """Return True if path's header matches the Subjects table layout.

    Real UCL DRC XNAT exports have header:
        Subject,Gender,Hand,YOB,Education,Ses,MR Count
    """
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            header = f.readline().strip().lower()
    except (OSError, UnicodeDecodeError):
        return False
    # Subjects has Subject + (YOB or Education or MR Count) and crucially
    # does NOT have MMSE (which would make it ClinicalAssessment) or Age
    # (which would make it MR Sessions; note: Subjects table has YOB
    # = year of birth, not Age).
    return (
        ("subject" in header)
        and ("mmse" not in header)
        and (("yob" in header) or ("mr count" in header) or ("education" in header))
    )


def _find_miriad_files() -> tuple[Path, Path, Path | None] | None:
    """Locate the three MIRIAD CSVs by inspecting CSV headers.

    Search strategy:
        1. Try canonical filenames first (back-compat).
        2. If not found, scan every *.csv in each SEARCH_BASE and identify
           each file by its header columns. This is content-aware and
           handles arbitrary filenames like `DrMaruf_5_18_2026_*.csv`.

    Returns (clinical, sessions, subjects_or_None) on success, None on miss.
    """
    canonical_names = {
        "clinical": [
            "ClinicalAssessment.csv", "clinical_assessment.csv",
            "ClinicalAsessment.csv",  # UCL XNAT spelling
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

        # ---- Strategy 1: canonical names by rglob ----
        clinical = None
        sessions = None
        subjects = None
        for name in canonical_names["clinical"]:
            cands = list(base_path.rglob(name))
            if cands:
                clinical = cands[0]
                break
        for name in canonical_names["sessions"]:
            cands = list(base_path.rglob(name))
            if cands:
                sessions = cands[0]
                break
        for name in canonical_names["subjects"]:
            cands = list(base_path.rglob(name))
            if cands:
                subjects = cands[0]
                break
        if clinical is not None and sessions is not None:
            return clinical, sessions, subjects

        # ---- Strategy 2: content-aware header inspection ----
        # Scan top-level *.csv files in the search base (no recursion to
        # avoid scanning unrelated downloads). If env var is set explicitly,
        # do limited rglob (max depth ~2) to find any MIRIAD-shaped CSVs.
        candidates = list(base_path.glob("*.csv"))
        if not candidates:
            # Try one level deeper
            candidates = list(base_path.glob("*/*.csv"))

        clinical = next((p for p in candidates
                         if _looks_like_clinical_csv(p)), None)
        sessions = next((p for p in candidates
                         if _looks_like_mr_sessions_csv(p)), None)
        subjects = next((p for p in candidates
                         if _looks_like_subjects_csv(p)), None)

        if clinical is not None and sessions is not None:
            return clinical, sessions, subjects
    return None


def test_real_miriad_longitudinal_audit_locked_invariant():
    """Aim 3 (A): third-cohort cTCS replication on MIRIAD longitudinal data."""
    files = _find_miriad_files()
    if files is None:
        pytest.skip(
            "MIRIAD CSVs not found in any of: "
            + ", ".join(b for b in SEARCH_BASES if b)
            + ". Set NEUROTCS_MIRIAD_DIR to the folder containing the three "
              "XNAT exports (ClinicalAssessment, MR Sessions, Subjects)."
        )

    clinical, sessions, subjects = files
    trajectories, report = load_miriad_trajectories(
        clinical_csv=clinical,
        sessions_csv=sessions,
        subjects_csv=subjects,
        exclude_test_retest_rescans=True,  # explicit: lock depends on this being True (default is True)
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

    # ---- Locked numerical invariants (real 2026-05-18 run) ----
    # These are EXACT values from Maruf's first MIRIAD run on v1.7.6.
    # Any deviation indicates either the source CSVs changed, the adapter
    # regressed, or the audit kernel changed semantically.
    assert len(trajectories) == EXPECTED_LONGITUDINAL_N_TRAJECTORIES, (
        f"MIRIAD trajectory count drift: got {len(trajectories)}, "
        f"expected {EXPECTED_LONGITUDINAL_N_TRAJECTORIES}"
    )
    assert result.n_transitions == EXPECTED_LONGITUDINAL_N_TRANSITIONS, (
        f"MIRIAD transition count drift: got {result.n_transitions}, "
        f"expected {EXPECTED_LONGITUDINAL_N_TRANSITIONS}"
    )
    assert result.n_flagged == EXPECTED_LONGITUDINAL_N_FLAGGED, (
        f"MIRIAD flagged count drift: got {result.n_flagged}, "
        f"expected {EXPECTED_LONGITUDINAL_N_FLAGGED}"
    )
    assert abs(result.ctcs.ci.point - EXPECTED_LONGITUDINAL_CTCS) < 0.0005, (
        f"MIRIAD cTCS drift: got {result.ctcs.ci.point:.4f}, "
        f"expected {EXPECTED_LONGITUDINAL_CTCS:.4f}"
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
        pytest.skip(
            "MIRIAD CSVs not found in any of: "
            + ", ".join(b for b in SEARCH_BASES if b)
            + ". Set NEUROTCS_MIRIAD_DIR to the folder containing the three "
              "XNAT exports."
        )

    clinical, sessions, _ = files
    pairs, pair_report = load_miriad_test_retest_pairs(
        clinical_csv=clinical, sessions_csv=sessions,
    )

    # ---- Sanity bounds ----
    assert pair_report.n_rescan_pairs >= TEST_RETEST_MIN_PAIRS, (
        f"Too few test-retest pairs found: {pair_report.n_rescan_pairs} "
        f"(expected в‰Ґ {TEST_RETEST_MIN_PAIRS})"
    )

    if not pairs:
        # MMSE may be missing for too many rescan visits.
        pytest.skip(
            f"{pair_report.n_rescan_pairs} rescan pairs identified but only "
            f"{pair_report.n_rescan_pairs_with_mmse} had matching MMSE. "
            f"No audit-ready pairs to score."
        )

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

    if EXPECTED_TEST_RETEST_AUDIT_ID_V2 is not None:
        assert result.audit_id_v2 == EXPECTED_TEST_RETEST_AUDIT_ID_V2, (
            f"MIRIAD test-retest audit_id_v2 drift: got {result.audit_id_v2}"
        )
    else:
        print(f"  [INFO] MIRIAD test-retest audit_id_v2: {result.audit_id_v2}")

    # ---- Locked numerical invariants ----
    assert len(pairs) == EXPECTED_TEST_RETEST_N_PAIRS, (
        f"MIRIAD test-retest pair count drift: got {len(pairs)}, "
        f"expected {EXPECTED_TEST_RETEST_N_PAIRS}"
    )
    assert result.n_flagged == EXPECTED_TEST_RETEST_N_FLAGGED, (
        f"MIRIAD test-retest flagged count drift: got {result.n_flagged}, "
        f"expected {EXPECTED_TEST_RETEST_N_FLAGGED}"
    )

    print(f"  {PASS} test_real_miriad_test_retest_noise_floor")
    print(f"        pairs = {len(pairs)}, "
          f"identical_state = {pair_report.n_pairs_state_identical}, "
          f"differs = {pair_report.n_pairs_state_differs}")
    print(f"        flag_rate = {100 * flag_rate:.3f}% "
          f"(must be в‰¤ {100 * TEST_RETEST_MAX_FLAG_RATE:.1f}%)")


if __name__ == "__main__":
    test_real_miriad_longitudinal_audit_locked_invariant()
    test_real_miriad_test_retest_noise_floor()

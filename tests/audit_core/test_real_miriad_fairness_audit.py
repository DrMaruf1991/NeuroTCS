"""Locked-invariant test for real MIRIAD fairness audit (AD-lock Step 2.2 +).

This test runs only when the actual MIRIAD CSVs are accessible on disk. It
locks the per-stratum fairness invariants captured from Maruf's first
real-data fairness audit on 2026-05-18 against the UCL DRC XNAT export
(DrMaruf_5_18_2026_12_16_*.csv triple). The numbers were captured under
NeuroTCS v1.7.12; this lock TEST ships in v1.7.13 and must reproduce them
bit-exactly under v1.7.13 and all future releases.

Real-data results (locked here, must reproduce bit-exactly):
  Cohort:  69 subjects, 454 transitions, 7 flagged (1.54%)
  cTCS:    0.9854 (BCa 95% CI: 0.9715-0.9937)
  audit_id:    59ac763dfc4cd0098b33f13a2240171c888e5b4e99373d9b8f974d716647d96a
  audit_id_v2: aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da

FUTURE-AI Panel B.4.4 stratification (Lekadir BMJ 2025;388:e081554):
  sex:                F (n=251, 3 flagged), M (n=203, 4 flagged)
  age_band:           <60 (n=31, 0), 60-69 (n=234, 6), 70-79 (n=161, 1),
                      80-89 (n=28, 0)
  race_ethnicity:     unknown (n=454, 7) вЂ” MIRIAD doesn't collect race
  comorbidity:        unknown (n=454, 7) вЂ” not extracted from cohort
  disease_stage:      unknown (n=454, 7) вЂ” not extracted
  treatment_status:   unknown (n=454, 7) вЂ” no anti-amyloid data

Max disparity: 1.542% at stratum 'age_band=80-89' (0% flag rate in this
stratum vs 1.542% overall, with n=28 вЂ” small-sample point estimate noise).

Any deviation from these per-stratum invariants indicates a regression in:
  (a) the demographic-extraction logic in adapter_miriad.py,
  (b) the audit kernel's per-transition flag emission, or
  (c) the fairness panel's stratification.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from neurotcs import audit, load_rulepack
from neurotcs.fairness import cohort_fairness_audit
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    load_miriad_trajectories,
)

PASS = "\033[32m\u2713\033[0m"

# Set NEUROTCS_MIRIAD_DIR to the directory containing the three MIRIAD CSVs
# (DrMaruf_5_18_2026_12_16_{7,24,33}.csv).
SEARCH_BASES = [
    os.environ.get("NEUROTCS_MIRIAD_DIR"),
]


# ============================================================
# Locked invariants (v1.7.13 вЂ” captured from 2026-05-18 real run)
# ============================================================

# v1.19.0 re-lock per ERRATA E-2026-005 (v1.12.0 schema 1.4.0 endorsing_bodies extension on ad/niaaa_2018).
# Fairness invariants are downstream of MIRIAD longitudinal audit_id; supersession traced via E-2026-005.
# Old v1.7.13 audit_id preserved for cryptographic continuity:
#   EXPECTED_AUDIT_ID_V1_7_13 = "947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0"
EXPECTED_AUDIT_ID = (
    "59ac763dfc4cd0098b33f13a2240171c888e5b4e99373d9b8f974d716647d96a"
)
# v1.19.0 re-lock per ERRATA E-2026-005. Old v1.7.13 v2 preserved.
EXPECTED_AUDIT_ID_V2_V1_7_13 = (
    "aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da"
)
EXPECTED_AUDIT_ID_V2 = (
    "c34b37863dac549d2aec8298453b9bc1ef2b0a8f719384249786d55f6e10da08"
)
EXPECTED_N_TRANSITIONS = 454
EXPECTED_N_FLAGGED = 7
EXPECTED_OVERALL_FLAG_RATE = 7 / 454  # 0.015418502202643172
EXPECTED_MAX_DISPARITY_STRATUM = "age_band=80-89"

# Per-stratum locked invariants. Format: (attribute, value) -> (n, n_flagged)
# Flag rate is derived deterministically as n_flagged / n.
EXPECTED_STRATA: dict[tuple[str, str], tuple[int, int]] = {
    ("sex", "F"):                   (251, 3),
    ("sex", "M"):                   (203, 4),
    ("age_band", "<60"):            (31,  0),
    ("age_band", "60-69"):          (234, 6),
    ("age_band", "70-79"):          (161, 1),
    ("age_band", "80-89"):          (28,  0),
    ("race_ethnicity", "unknown"):  (454, 7),
    ("comorbidity", "unknown"):     (454, 7),
    ("disease_stage", "unknown"):   (454, 7),
    ("treatment_status", "unknown"):(454, 7),
}


# ============================================================
# CSV discovery (same logic as test_real_miriad_audit.py)
# ============================================================

# Maruf's XNAT export naming: DrMaruf_5_18_2026_12_16_{7,24,33}.csv
# - _7 is the clinical assessment (MMSE)
# - _24 is the MR sessions (Age)
# - _33 is the subjects (Gender, YOB, Education, Hand)
# Content-aware discovery is in test_real_miriad_audit.py; we delegate to
# the same helper so both tests stay in lockstep.

def _find_miriad_files() -> tuple[Path, Path, Path | None] | None:
    """Locate the three MIRIAD CSVs on disk.

    Delegates to test_real_miriad_audit's content-aware discovery so the
    two locked-invariant test files agree on which files to read.
    """
    # Lazy import to keep this module standalone if the audit test moves
    from tests.audit_core.test_real_miriad_audit import _find_miriad_files as _f
    return _f()


# ============================================================
# Locked fairness audit test
# ============================================================

def test_real_miriad_fairness_audit_locked_invariants():
    """Run the AD fairness audit on real MIRIAD CSVs and assert every locked
    invariant bit-exactly. Skips cleanly when CSVs absent (sandbox / CI).

    This test is the canonical reproducibility certificate for the MIRIAD
    fairness numbers published in:
      - docs/datasheet/ad_neurotcs_datasheet.md Section A
      - docs/validation/ad_fairness_audit.md "Locking the MIRIAD fairness
        invariant" section
      - docs/reproducibility/ad_neurotcs_reproducibility.md Section 1
    """
    files = _find_miriad_files()
    if files is None:
        pytest.skip(
            "MIRIAD CSVs not found in any SEARCH_BASES. Set "
            "NEUROTCS_MIRIAD_DIR to engage this locked-invariant test."
        )

    clinical_csv, sessions_csv, subjects_csv = files

    # Load with demographic extraction (v1.7.10 pipeline)
    trajectories, _ = load_miriad_trajectories(
        clinical_csv=clinical_csv,
        sessions_csv=sessions_csv,
        subjects_csv=subjects_csv,
    )

    # Audit with per-transition flag capture
    pack = load_rulepack("ad/niaaa_2018")
    result = audit(
        trajectories, pack,
        bootstrap_B=10_000,
        seed=42,
        ci_method="bca",
        return_per_transition=True,
    )

    # First-tier: audit identity must match
    assert result.audit_id == EXPECTED_AUDIT_ID, (
        f"audit_id drift! expected {EXPECTED_AUDIT_ID}, got {result.audit_id}. "
        f"Fairness invariants are downstream of audit_id вЂ” investigate the "
        f"cTCS lock first via test_real_miriad_audit.py."
    )
    assert result.audit_id_v2 == EXPECTED_AUDIT_ID_V2
    assert result.n_transitions == EXPECTED_N_TRANSITIONS
    assert result.n_flagged == EXPECTED_N_FLAGGED

    # Run the FUTURE-AI Panel B.4.4 fairness audit
    fairness = cohort_fairness_audit(result)

    # Second-tier: overall fairness identity
    assert fairness.panel_id == "B.4.4_fairness"
    assert fairness.framework_doi == "10.1136/bmj-2024-081554"
    assert fairness.framework_pmid == "39909534"
    assert abs(fairness.overall_flag_rate - EXPECTED_OVERALL_FLAG_RATE) < 1e-12
    assert abs(fairness.max_disparity - EXPECTED_OVERALL_FLAG_RATE) < 1e-12
    assert fairness.max_disparity_stratum == EXPECTED_MAX_DISPARITY_STRATUM

    # Third-tier: per-stratum invariants must reproduce bit-exactly
    actual_strata = {
        (s.stratum_name, s.stratum_value): (s.n, s.n_flagged)
        for s in fairness.strata
    }

    # Every locked stratum must be present with exact counts
    for key, (expected_n, expected_n_flagged) in EXPECTED_STRATA.items():
        assert key in actual_strata, (
            f"Locked stratum {key} missing from fairness audit! "
            f"actual strata: {sorted(actual_strata.keys())}"
        )
        actual_n, actual_n_flagged = actual_strata[key]
        assert (actual_n, actual_n_flagged) == (expected_n, expected_n_flagged), (
            f"Stratum {key} drift: expected n={expected_n} "
            f"n_flagged={expected_n_flagged}, got n={actual_n} "
            f"n_flagged={actual_n_flagged}. Demographic extraction or "
            f"flag emission regressed; investigate adapter_miriad.py or "
            f"PerTransitionFlags emission."
        )

    # Reverse direction: every actual stratum must be locked
    # (catches NEW strata appearing вЂ” would also be a regression worth
    # explicit acknowledgement, not silent acceptance)
    for key in actual_strata:
        assert key in EXPECTED_STRATA, (
            f"NEW stratum {key} appeared in fairness audit that is not "
            f"in EXPECTED_STRATA. If this is intentional (e.g., a new "
            f"adapter feature added a stratum value), update "
            f"EXPECTED_STRATA in this test file and re-lock."
        )

    print(f"  {PASS} test_real_miriad_fairness_audit_locked_invariants "
          f"(10 strata, max_disparity={fairness.max_disparity:.6f} at "
          f"{fairness.max_disparity_stratum})")


def test_real_miriad_fairness_flag_rates_match_locked_per_stratum():
    """Independent of the count check: every per-stratum flag RATE
    (not count) must match the locked invariant to within 1e-12.

    This catches numerical drift even if the integer counts happen to
    coincide вЂ” defense in depth.
    """
    files = _find_miriad_files()
    if files is None:
        pytest.skip("MIRIAD CSVs not found; skipping locked-invariant test.")

    clinical_csv, sessions_csv, subjects_csv = files
    trajectories, _ = load_miriad_trajectories(
        clinical_csv=clinical_csv,
        sessions_csv=sessions_csv,
        subjects_csv=subjects_csv,
    )
    pack = load_rulepack("ad/niaaa_2018")
    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42,
                    ci_method="bca", return_per_transition=True)
    fairness = cohort_fairness_audit(result)

    actual_rates = {
        (s.stratum_name, s.stratum_value): s.flag_rate
        for s in fairness.strata
    }
    for key, (n, n_flagged) in EXPECTED_STRATA.items():
        expected_rate = n_flagged / n
        actual_rate = actual_rates[key]
        assert abs(actual_rate - expected_rate) < 1e-12, (
            f"Stratum {key} flag rate drift: expected "
            f"{expected_rate:.15f}, got {actual_rate:.15f}. "
            f"Numerical precision regression."
        )

    print(f"  {PASS} test_real_miriad_fairness_flag_rates_match_locked_per_stratum")

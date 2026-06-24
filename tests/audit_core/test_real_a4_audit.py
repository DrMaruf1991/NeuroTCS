"""Locked-invariant regression test for the A4/LEARN cohort recognizer.

Locked 2026-06-24 against the real A4 Raw Data CDR export (cdr.csv) via the
--cohort a4 recognizer path: the recognizer crosswalks CDGLOBAL (0->CN, 0.5->MCI,
>=1->AD), drops the -99 day-offset sentinel, derives visit order from
CDADTC_DAYS_T0, and feeds the existing tables_to_submission -> run_full_audit
path. A4 is preclinical (amyloid-positive cognitively-unimpaired), so most
subjects are CN with few admissible-state transitions; the cTCS is correspondingly
high but is a REAL audit of thousands of transitions, not a trivial perfect score.

The test runs only when the A4 CDR CSV is available on disk. Set NEUROTCS_A4_CDR
to the path of your DUA-approved A4 Raw Data/cdr.csv.

DUA: this test reports only aggregate cTCS / transition counts; no raw BIDs.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from neurotcs.cohorts.a4 import _build_a4_mapping, recognize_a4
from neurotcs.io import read_tables, tables_to_submission
from neurotcs.orchestration.orchestrator import run_full_audit

# Locked invariant (2026-06-24, real A4 Raw Data/cdr.csv, v1.85.x).
LOCKED_CTCS = 0.996374
LOCKED_N_TRANSITIONS = 8892
LOCKED_N_FLAGGED = 34
ABS_TOL = 0.0005  # framework standard cTCS tolerance


def _find_a4_cdr() -> Path | None:
    p = os.environ.get("NEUROTCS_A4_CDR")
    return Path(p) if p and Path(p).exists() else None


def test_real_a4_audit_locked_invariant():
    """A4/LEARN --cohort recognizer reproduces the locked real-data cTCS."""
    csv = _find_a4_cdr()
    if csv is None:
        pytest.skip(
            "A4 CDR CSV not found on disk. Set NEUROTCS_A4_CDR to the A4 "
            "Raw Data/cdr.csv to enable."
        )

    skipped: list[str] = []
    decisions: list[str] = []
    tables = read_tables(str(csv), allow_pdf=False, skipped=skipped,
                         decisions=decisions)

    # recognizer must identify A4 by signature
    match = recognize_a4(tables)
    assert match is not None, "A4 recognizer did not match the A4 CDR file"
    assert match.cohort_id == "a4"

    # build the A4 submission via the recognizer's mapping (reuses the canonical
    # CDGLOBAL crosswalk + sentinel handling), then audit through the standard path
    mapping = _build_a4_mapping(tables)
    sub = tables_to_submission(tables, mapping, warnings=[])
    result = run_full_audit(sub, expected_layers=["staging_clinical"])

    # locate the staging layer result
    staging = next(
        (lyr for lyr in result.layers if lyr.layer == "staging_clinical"
         and lyr.ran), None)
    assert staging is not None, "staging_clinical layer did not run"
    ctcs = staging.summary.get("ctcs")
    n_trans = staging.summary.get("n_transitions")
    n_flagged = staging.summary.get("n_flagged")

    assert ctcs is not None, "no cTCS emitted for A4"
    assert abs(ctcs - LOCKED_CTCS) < ABS_TOL, (
        f"A4 cTCS drift: got {ctcs:.6f}, expected {LOCKED_CTCS:.6f} "
        f"(|delta| >= {ABS_TOL})"
    )
    # transition / flag counts: exact regression guard
    assert n_trans == LOCKED_N_TRANSITIONS, (
        f"A4 transition count drift: got {n_trans}, "
        f"expected {LOCKED_N_TRANSITIONS}"
    )
    assert n_flagged == LOCKED_N_FLAGGED, (
        f"A4 flagged count drift: got {n_flagged}, "
        f"expected {LOCKED_N_FLAGGED}"
    )

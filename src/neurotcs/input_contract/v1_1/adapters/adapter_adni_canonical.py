"""
Canonical ADNI longitudinal loader for NeuroTCS cTCS audit.

This complements `adapter_adni.py` (which is a submission-builder for the
NeuroTCS input contract). This module provides the parallel of
`load_oasis3_trajectories` / `load_miriad_trajectories` so all four
cohorts in the v1.8 four-cohort triangulation are loaded by canonical
framework functions, not ad hoc scripts.

CANONICAL ADNI DATA SOURCE (Gap F resolution):
    The canonical source for ADNI NIA-AA 2018 audit is the adjudicated
    final diagnosis from ADNIMERGE2:

        ADNIMERGE2/data/DXSUM.rda

    NOT the raw CSV `All_Subjects_DXSUM_*.csv`, which contains raw clinical
    form responses prior to adjudication. Cross-validation on 28,352 matched
    (PTID, EXAMDATE) rows showed ~10-15% disagreement between the two
    sources because adjudication consolidates conflicting form entries.

    The R-format file is what `examples/adni_audit_demo.py` uses and what
    reproduces the v1.7.13 published cTCS=0.9946 invariant exactly
    (n_trajectories_scored=2958, n_transitions=12006).

Requires: pyreadr (already pinned in adapter_adni.py for the same reason).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from neurotcs.audit_core import Trajectory
from neurotcs.audit_core.trajectory import trajectories_from_dataframe

ADNI_SALT = "adni_demo_2026"
DIAGNOSIS_MAP = {"CN": "CN", "MCI": "MCI", "Dementia": "AD"}


@dataclass
class ADNILoadReport:
    raw_rows: int = 0
    raw_subjects: int = 0
    rows_after_diagnosis_filter: int = 0
    rows_after_date_filter: int = 0
    n_trajectories: int = 0
    n_transitions: int = 0

    def to_dict(self) -> dict:
        return {
            "raw_rows": self.raw_rows,
            "raw_subjects": self.raw_subjects,
            "rows_after_diagnosis_filter": self.rows_after_diagnosis_filter,
            "rows_after_date_filter": self.rows_after_date_filter,
            "n_trajectories": self.n_trajectories,
            "n_transitions": self.n_transitions,
        }


def hash_patient_id(rid: int | str) -> str:
    """SHA-256 hash ADNI RID with cohort salt."""
    return f"ADNI_{hashlib.sha256(f'{ADNI_SALT}_{int(rid)}'.encode()).hexdigest()[:16]}"


def load_adni_trajectories(
    dxsum_rda_path: str | Path,
    *,
    hash_ids: bool = False,
    skip_invalid: bool = True,
) -> tuple[list[Trajectory], ADNILoadReport]:
    """Load ADNI from the canonical R-format DXSUM into NeuroTCS trajectories.

    Args:
        dxsum_rda_path: Path to ADNIMERGE2/data/DXSUM.rda (extracted from
            the ADNIMERGE2 R package tarball).
        hash_ids: SHA-256-hash RIDs with cohort salt. DEFAULT FALSE to
            reproduce the v1.7.13 published audit_id (the example demo
            uses raw RIDs). Set True for DUA-style hygiene at the cost of
            a different audit_id.
        skip_invalid: Pass-through to Trajectory construction.

    Returns:
        (trajectories, report). Trajectories ready for `neurotcs.audit()`.
    """
    try:
        import pyreadr
    except ImportError as e:
        raise ImportError(
            "pyreadr is required to load ADNIMERGE2 .rda files. "
            "Install: pip install pyreadr"
        ) from e

    p = Path(dxsum_rda_path)
    if not p.exists():
        raise FileNotFoundError(f"ADNI DXSUM.rda not found: {p}")

    result = pyreadr.read_r(str(p))
    if "DXSUM" not in result:
        raise KeyError(
            f".rda did not contain expected DXSUM table; got: {list(result.keys())}"
        )
    df = result["DXSUM"]
    raw_rows = len(df)
    raw_subjects = int(df["RID"].nunique())

    # DIAGNOSIS in R is a string column with values CN / MCI / Dementia
    df["DIAGNOSIS_STR"] = df["DIAGNOSIS"].astype(str)
    df = df[df["DIAGNOSIS_STR"].isin(["CN", "MCI", "Dementia"])].copy()
    rows_after_dx = len(df)

    df["EXAMDATE"] = pd.to_datetime(df["EXAMDATE"], errors="coerce")
    df = df.dropna(subset=["EXAMDATE", "RID"])
    rows_after_date = len(df)

    # Build patient_id. Default (hash_ids=False) keeps RID as-is to match the
    # v1.7.13 published example demo (examples/adni_audit_demo.py).
    if hash_ids:
        df["NeuroTCS_patient_id"] = df["RID"].apply(hash_patient_id)
        pid_col = "NeuroTCS_patient_id"
    else:
        pid_col = "RID"

    trajectories = trajectories_from_dataframe(
        df,
        patient_id_col=pid_col,
        visit_date_col="EXAMDATE",
        state_col="DIAGNOSIS_STR",
        state_label_map=DIAGNOSIS_MAP,
        skip_invalid=skip_invalid,
    )
    n_transitions = sum(t.num_transitions for t in trajectories)

    report = ADNILoadReport(
        raw_rows=raw_rows,
        raw_subjects=raw_subjects,
        rows_after_diagnosis_filter=rows_after_dx,
        rows_after_date_filter=rows_after_date,
        n_trajectories=len(trajectories),
        n_transitions=n_transitions,
    )

    return trajectories, report

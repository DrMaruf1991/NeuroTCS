"""
Reference adapter: NACC → NeuroTCS trajectories.

This adapter loads the NACC Uniform Data Set (UDS) investigator file and
emits NeuroTCS Trajectory objects for cTCS auditing.

State derivation from NACCUDSD — empirically validated against CDRGLOB
(clinical gold standard, Morris 1993 PMID 8232972) on 214,976 NACC visits:

    NACCUDSD | modal CDRGLOB | n        | NeuroTCS state
    ---------|---------------|----------|--------------
       1     |   0.0 (91%)   | 106,475  | CN
       2     |   0.5 (66%)   |   9,575  | MCI (impaired-not-MCI, CDR=0.5)
       3     |   0.5 (87%)   |  37,957  | MCI
       4     |   ≥1.0 (76%)  |  60,945  | AD
       8     |   mixed       |      24  | dropped (rare/unknown)

Cross-tab evidence (run on investigator_nacc73 May 2026):
  NACCUDSD=2 modal CDRGLOB=0.5 (n=6,312 of 9,575 = 65.9%) → MCI
  NACCUDSD=3 modal CDRGLOB=0.5 (n=32,896 of 37,957 = 86.7%) → MCI

NACCUDSD=5 does NOT exist in the data (max code is 8). Earlier ad hoc
mappings claiming {1:CN, 3:CN, 4:MCI, 5:Dementia} are empirically wrong
and should not be used.

DUA compliance (Gap D / Gap AA):
  - All NACCIDs are SHA-256 hashed with salt 'nacc_dua_2026_v1_7_13' before
    output. Raw NACCIDs never appear in any framework artifact.
  - Cell counts < 10 must be suppressed by the caller per NACC DUA.
  - Acknowledgment line MUST appear in caller's outputs:
    "The NACC database is funded by NIA/NIH Grant U24 AG072122."

Usage:
    from neurotcs.input_contract.v1_1.adapters.adapter_nacc import (
        load_nacc_trajectories,
    )
    trajectories, report = load_nacc_trajectories(
        nacc_csv_path="investigator_nacc73.csv",
        hash_ids=True,
    )
"""
from __future__ import annotations

import gc
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from neurotcs.audit_core import Trajectory

NACC_SALT = "nacc_dua_2026_v1_7_13"

# Empirically-validated NACCUDSD → state map.
# DO NOT modify without re-running the NACCUDSD × CDRGLOB cross-tab and updating
# the docstring evidence. See module docstring for the cross-tab numbers.
NACCUDSD_TO_STATE: dict[int, str] = {
    1: "CN",
    2: "MCI",
    3: "MCI",
    4: "AD",
    # 8: dropped (n=24 across 214,976 visits; suppressed)
}

# Columns required to derive state + the minimum DUA-compliant fairness panel.
REQUIRED_COLS = ["NACCID", "VISITDATE", "NACCUDSD"]
FAIRNESS_COLS = ["NACCAGE", "NACCSEX", "NACCNIHR", "NACCHISP", "NACCEDULVL", "NACCNE4S"]
DEFAULT_USECOLS = REQUIRED_COLS + FAIRNESS_COLS + ["CDRGLOB", "CDRSUM"]


@dataclass
class NACCLoadReport:
    """Diagnostic report from load_nacc_trajectories."""

    raw_rows: int = 0
    raw_subjects: int = 0
    rows_after_date_filter: int = 0
    rows_after_state_map: int = 0
    subjects_after_state_map: int = 0
    n_trajectories: int = 0
    n_transitions: int = 0
    naccudsd_8_dropped: int = 0  # rare/unknown code
    n_naccudsd_distribution: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "raw_rows": self.raw_rows,
            "raw_subjects": self.raw_subjects,
            "rows_after_date_filter": self.rows_after_date_filter,
            "rows_after_state_map": self.rows_after_state_map,
            "subjects_after_state_map": self.subjects_after_state_map,
            "n_trajectories": self.n_trajectories,
            "n_transitions": self.n_transitions,
            "naccudsd_8_dropped": self.naccudsd_8_dropped,
            "n_naccudsd_distribution": self.n_naccudsd_distribution,
        }


def hash_patient_id(naccid: str) -> str:
    """SHA-256 hash NACCID with cohort salt. Cannot be reversed without salt."""
    return f"NACC_{hashlib.sha256(f'{NACC_SALT}_{naccid}'.encode()).hexdigest()[:16]}"


def naccudsd_to_state(code: int | float | None) -> str | None:
    """Convert a NACCUDSD code to NeuroTCS state. Returns None if unmappable."""
    if code is None or pd.isna(code):
        return None
    return NACCUDSD_TO_STATE.get(int(code))


def load_nacc_trajectories(
    nacc_csv_path: str | Path,
    *,
    hash_ids: bool = True,
    skip_invalid: bool = True,
    usecols: list[str] | None = None,
) -> tuple[list[Trajectory], NACCLoadReport]:
    """Load NACC investigator file into NeuroTCS trajectories.

    Args:
        nacc_csv_path: Path to investigator_nacc73*.csv (full or slim).
        hash_ids: SHA-256-hash NACCIDs (DUA requirement).
        skip_invalid: Pass through to Trajectory construction.
        usecols: Column whitelist. Defaults to DEFAULT_USECOLS. Pass a
            smaller list to reduce memory; fairness analysis will be
            restricted accordingly and the caller should log the restriction.

    Returns:
        (trajectories, report). Trajectories ready for `neurotcs.audit()`.
        Single-visit subjects are emitted as 1-state trajectories (parity
        with the OASIS-3 and MIRIAD adapters; they contribute 0 transitions).
    """
    nacc_csv_path = Path(nacc_csv_path)
    if not nacc_csv_path.exists():
        raise FileNotFoundError(f"NACC CSV not found: {nacc_csv_path}")

    # Sniff available cols, intersect with requested
    available = pd.read_csv(nacc_csv_path, nrows=0).columns.tolist()
    requested = usecols if usecols is not None else DEFAULT_USECOLS
    missing_required = set(REQUIRED_COLS) - set(available)
    if missing_required:
        raise KeyError(
            f"NACC CSV missing required columns: {sorted(missing_required)}. "
            f"Available (first 20): {available[:20]}..."
        )
    cols = [c for c in requested if c in available]

    df = pd.read_csv(nacc_csv_path, usecols=cols, low_memory=False)
    raw_rows = len(df)
    raw_subjects = df["NACCID"].nunique()

    # Date filtering
    df["VISITDATE"] = pd.to_datetime(df["VISITDATE"], errors="coerce")
    df = df.dropna(subset=["VISITDATE", "NACCID", "NACCUDSD"])
    rows_after_date = len(df)

    # NACCUDSD distribution diagnostic
    udsd_dist = {int(k): int(v) for k, v in df["NACCUDSD"].value_counts().items()}
    n_8_dropped = int((df["NACCUDSD"] == 8).sum())

    # State derivation (empirically-validated map)
    df["state"] = df["NACCUDSD"].apply(naccudsd_to_state)
    df = df.dropna(subset=["state"])
    rows_after_state = len(df)
    subjects_after_state = df["NACCID"].nunique()

    # Sort and emit trajectories
    df = df.sort_values(["NACCID", "VISITDATE"])
    trajectories: list[Trajectory] = []
    for sid, g in df.groupby("NACCID"):
        states = tuple(g["state"])
        dates = tuple(d.date() for d in g["VISITDATE"])
        pid = hash_patient_id(str(sid)) if hash_ids else str(sid)
        try:
            trajectories.append(Trajectory(
                patient_id=pid, states=states, dates=dates,
            ))
        except Exception:
            if not skip_invalid:
                raise

    n_transitions = sum(t.num_transitions for t in trajectories)

    # Free intermediate
    del df
    gc.collect()

    report = NACCLoadReport(
        raw_rows=raw_rows,
        raw_subjects=int(raw_subjects),
        rows_after_date_filter=rows_after_date,
        rows_after_state_map=rows_after_state,
        subjects_after_state_map=int(subjects_after_state),
        n_trajectories=len(trajectories),
        n_transitions=n_transitions,
        naccudsd_8_dropped=n_8_dropped,
        n_naccudsd_distribution=udsd_dist,
    )

    return trajectories, report

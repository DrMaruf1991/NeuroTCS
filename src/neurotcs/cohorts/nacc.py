"""NACC cohort recognizer (v1.84.0).

Recognizes the NACC Uniform Data Set investigator file by its column signature
(NACCID + VISITDATE + NACCUDSD) and builds a NeuroTCS staging submission that
REUSES the canonical adapter's exact transformations -- it does not re-implement
them:

  - state    <- naccudsd_to_state (the empirically-validated NACCUDSD crosswalk:
               1->CN, 2->MCI, 3->MCI, 4->AD; 8 and unmapped -> dropped)
  - subject  <- hash_patient_id (the DUA-required salted SHA-256 NACCID hash)
  - date     <- VISITDATE

Because the crosswalk + hashing are imported from the canonical adapter (the same
code that locks the cTCS=0.991502 invariant), the submission produces the same
trajectories -> the same audit -> the same cTCS, by construction. The recognizer
never re-derives clinical states itself.

DESIGN -- recognize-then-CONFIRM: recognition only SUGGESTS; the crosswalk is
applied to build the submission only on explicit --cohort nacc.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from neurotcs.cohorts.base import CohortMatch, register_recognizer
from neurotcs.input_contract.v1_1.adapters.adapter_nacc import (
    REQUIRED_COLS,
    hash_patient_id,
    naccudsd_to_state,
)

_NACC_SIGNATURE = set(REQUIRED_COLS)  # NACCID, VISITDATE, NACCUDSD


@register_recognizer
def recognize_nacc(tables: dict[str, pd.DataFrame]) -> CohortMatch | None:
    """Recognize a NACC investigator table by its column signature."""
    for sheet, df in tables.items():
        cols = set(map(str, df.columns))
        if not (_NACC_SIGNATURE <= cols):
            continue
        # confidence: exact required triple = strong; NACC-specific companions raise it
        companions = sum(1 for c in ("NACCAGE", "NACCSEX", "CDRGLOB", "NACCUDSD")
                         if c in cols)
        confidence = 0.85 + 0.0375 * min(companions, 4)
        notes = [
            f"Recognized NACC UDS signature in sheet '{sheet}' "
            f"(NACCID + VISITDATE + NACCUDSD).",
            "subject_id <- hash_patient_id(NACCID)  [DUA-required salted SHA-256]",
            "state <- naccudsd_to_state: 1->CN, 2->MCI, 3->MCI, 4->AD; "
            "8/unmapped dropped (canonical adapter crosswalk, reused not "
            "re-implemented).",
            "visit_date <- VISITDATE",
            "Reproduces the locked NACC cTCS=0.991502 by reusing the canonical "
            "adapter transformations.",
        ]
        return CohortMatch(
            cohort_id="nacc",
            display_name="NACC UDS",
            sheet=sheet,
            confidence=min(confidence, 1.0),
            notes=notes,
            build_mapping=_build_nacc_mapping,
        )
    return None


def _build_nacc_mapping(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Build a staging submission for a confirmed NACC cohort, reusing the
    canonical adapter's crosswalk + ID hashing. Fail-closed on malformed input."""
    match = recognize_nacc(tables)
    if match is None:
        raise ValueError("NACC mapping requested but NACC signature not present.")
    sheet = match.sheet
    df = tables[sheet].copy()
    # mirror the canonical loader's row filtering exactly
    df["VISITDATE"] = pd.to_datetime(df["VISITDATE"], errors="coerce")
    df = df.dropna(subset=["VISITDATE", "NACCID", "NACCUDSD"])
    df["__nacc_state__"] = df["NACCUDSD"].apply(naccudsd_to_state)
    df = df.dropna(subset=["__nacc_state__"])  # drops NACCUDSD=8 / unmapped
    if df.empty:
        raise ValueError(
            "NACC mapping: no rows with a mappable NACCUDSD state remain.")
    df["__nacc_subject__"] = df["NACCID"].astype(str).map(hash_patient_id)
    df["__nacc_date__"] = df["VISITDATE"].dt.strftime("%Y-%m-%d")
    tables[sheet] = df  # expose derived columns to the audit path
    return {
        "clinical": {
            "sheet": sheet,
            "subject_id": "__nacc_subject__",
            "visit_date": "__nacc_date__",
            "state": "__nacc_state__",
            # visit omitted -> derived from visit_date order (v1.83.0)
        },
        "ranges": [],
    }

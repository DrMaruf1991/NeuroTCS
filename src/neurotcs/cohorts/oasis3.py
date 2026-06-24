"""OASIS-3 cohort recognizer (v1.84.0).

Recognizes the OASIS-3 UDSb4 CDR table by its column signature
(OASISID + days_to_visit + CDRTOT) and builds a NeuroTCS staging submission that
REUSES the canonical adapter's exact transformations (cdr_to_state, hash_patient_id,
SYNTHETIC_BASELINE day-offset conversion) -- it does not re-implement them. So the
submission yields the same trajectories -> the same audit -> the locked
cTCS=0.9942, by construction.

Recognize-then-confirm: recognition SUGGESTS; the crosswalk applies only on
explicit --cohort oasis3.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd

from neurotcs.cohorts.base import CohortMatch, register_recognizer
from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
    SYNTHETIC_BASELINE,
    cdr_to_state,
    hash_patient_id,
)

_OASIS3_SIGNATURE = {"OASISID", "days_to_visit", "CDRTOT"}


@register_recognizer
def recognize_oasis3(tables: dict[str, pd.DataFrame]) -> CohortMatch | None:
    """Recognize an OASIS-3 UDSb4 CDR table by its column signature."""
    for sheet, df in tables.items():
        cols = set(map(str, df.columns))
        if not (_OASIS3_SIGNATURE <= cols):
            continue
        companions = sum(1 for c in ("dx1", "CDRSUM", "mmse") if c in cols)
        confidence = 0.85 + 0.05 * min(companions, 3)
        notes = [
            f"Recognized OASIS-3 UDSb4 CDR signature in sheet '{sheet}' "
            f"(OASISID + days_to_visit + CDRTOT).",
            "subject_id <- hash_patient_id(OASISID)  [salted SHA-256]",
            "state <- cdr_to_state(CDRTOT): 0->CN, 0.5->MCI, >=1->AD "
            "(canonical adapter crosswalk, reused not re-implemented).",
            "visit_date <- SYNTHETIC_BASELINE + days_to_visit (preserves "
            "inter-visit intervals).",
            "Reproduces the locked OASIS-3 cTCS=0.9942 by reusing the canonical "
            "adapter transformations.",
        ]
        return CohortMatch(
            cohort_id="oasis3",
            display_name="OASIS-3",
            sheet=sheet,
            confidence=min(confidence, 1.0),
            notes=notes,
            build_mapping=_build_oasis3_mapping,
        )
    return None


def _build_oasis3_mapping(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Build a staging submission for a confirmed OASIS-3 cohort, reusing the
    canonical adapter's crosswalk + date synthesis. Fail-closed on junk."""
    match = recognize_oasis3(tables)
    if match is None:
        raise ValueError("OASIS-3 mapping requested but signature not present.")
    sheet = match.sheet
    df = tables[sheet].copy()
    df = df.dropna(subset=["OASISID", "days_to_visit", "CDRTOT"]).copy()
    df["__o3_state__"] = df["CDRTOT"].apply(cdr_to_state)
    df = df.dropna(subset=["__o3_state__"]).copy()
    if df.empty:
        raise ValueError(
            "OASIS-3 mapping: no rows with a mappable CDRTOT state remain.")
    df["__o3_date__"] = df["days_to_visit"].astype(int).apply(
        lambda d: (SYNTHETIC_BASELINE + timedelta(days=d)).strftime("%Y-%m-%d"))
    df["__o3_subject__"] = df["OASISID"].astype(str).map(hash_patient_id)
    tables[sheet] = df
    return {
        "clinical": {
            "sheet": sheet,
            "subject_id": "__o3_subject__",
            "visit_date": "__o3_date__",
            "state": "__o3_state__",
        },
        "ranges": [],
    }

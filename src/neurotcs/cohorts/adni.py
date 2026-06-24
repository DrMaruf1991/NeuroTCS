"""ADNI cohort recognizer (v1.84.0).

Recognizes the canonical ADNI DXSUM table (from ADNIMERGE2/data/DXSUM.rda) by its
column signature (RID + DIAGNOSIS + EXAMDATE) and builds a NeuroTCS staging
submission that REUSES the canonical adapter's exact crosswalk (DIAGNOSIS_MAP:
CN->CN, MCI->MCI, Dementia->AD).

CRITICAL invariant detail: the canonical loader defaults to hash_ids=False and the
locked cTCS=0.994575 invariant is reproduced with RAW RID (the published v1.7.13
example uses raw RIDs). So this recognizer uses RID as-is -- it does NOT hash --
otherwise the audit_id/cTCS would differ.

Recognize-then-confirm: recognition SUGGESTS; the crosswalk applies only on
explicit --cohort adni. The .rda is read by the CLI's read_tables (pyreadr).
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from neurotcs.cohorts.base import CohortMatch, register_recognizer
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
    DIAGNOSIS_MAP,
)

_ADNI_SIGNATURE = {"RID", "DIAGNOSIS", "EXAMDATE"}
_VALID_DX = set(DIAGNOSIS_MAP)  # {"CN","MCI","Dementia"}


@register_recognizer
def recognize_adni(tables: dict[str, pd.DataFrame]) -> CohortMatch | None:
    """Recognize a canonical ADNI DXSUM table by its column signature."""
    for sheet, df in tables.items():
        cols = set(map(str, df.columns))
        if not (_ADNI_SIGNATURE <= cols):
            continue
        companions = sum(1 for c in ("VISCODE", "VISCODE2", "PTID", "PHASE")
                         if c in cols)
        confidence = 0.85 + 0.0375 * min(companions, 4)
        notes = [
            f"Recognized canonical ADNI DXSUM signature in sheet '{sheet}' "
            f"(RID + DIAGNOSIS + EXAMDATE).",
            "subject_id <- RID (raw, NOT hashed -- required to reproduce the "
            "locked v1.7.13 invariant).",
            "state <- DIAGNOSIS_MAP: CN->CN, MCI->MCI, Dementia->AD "
            "(canonical adapter crosswalk, reused not re-implemented).",
            "visit_date <- EXAMDATE",
            "Reproduces the locked ADNI cTCS=0.994575 by reusing the canonical "
            "adapter transformations.",
        ]
        return CohortMatch(
            cohort_id="adni",
            display_name="ADNI (canonical DXSUM)",
            sheet=sheet,
            confidence=min(confidence, 1.0),
            notes=notes,
            build_mapping=_build_adni_mapping,
        )
    return None


def _build_adni_mapping(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Build a staging submission for a confirmed ADNI cohort, reusing the
    canonical DIAGNOSIS_MAP crosswalk. RAW RID (no hash). Fail-closed on junk."""
    match = recognize_adni(tables)
    if match is None:
        raise ValueError("ADNI mapping requested but signature not present.")
    sheet = match.sheet
    df = tables[sheet].copy()
    df["__adni_dx__"] = df["DIAGNOSIS"].astype(str)
    df = df[df["__adni_dx__"].isin(_VALID_DX)].copy()
    df["EXAMDATE"] = pd.to_datetime(df["EXAMDATE"], errors="coerce")
    df = df.dropna(subset=["EXAMDATE", "RID"]).copy()
    if df.empty:
        raise ValueError(
            "ADNI mapping: no rows with a valid DIAGNOSIS + EXAMDATE remain.")
    # apply the canonical crosswalk to the state column
    df["__adni_state__"] = df["__adni_dx__"].map(DIAGNOSIS_MAP)
    df["__adni_date__"] = df["EXAMDATE"].dt.strftime("%Y-%m-%d")
    # RAW RID as subject id (string for the staging frame), NOT hashed
    df["__adni_subject__"] = df["RID"].astype(str)
    tables[sheet] = df
    return {
        "clinical": {
            "sheet": sheet,
            "subject_id": "__adni_subject__",
            "visit_date": "__adni_date__",
            "state": "__adni_state__",
        },
        "ranges": [],
    }

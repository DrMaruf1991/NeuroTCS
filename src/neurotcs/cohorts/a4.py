"""A4/LEARN CDR cohort recognizer (v1.83.0).

A4/LEARN is a preclinical AD prevention trial. Its CDR file (cdr.csv) has a
distinctive column signature verified from the real release:

    BID                -- subject id
    CDGLOBAL           -- CDR global score (0 / 0.5 / 1 / 2 / 3)
    CDADTC_DAYS_T0     -- days from T0 (visit ordering), with -99 = missing
    (plus VISCODE, AVISIT, CDRSB, CDSOB, EPOCH, ...)

Recognition keys on the (BID, CDGLOBAL, CDADTC_DAYS_T0) triple -- no other taught
cohort uses this exact combination.

The mapping this builds derives, from cdr.csv:
  - subject_id  <- BID
  - state       <- CDGLOBAL crosswalked 0->CN, 0.5->MCI, >=1->AD (standard CDR
                   global staging crosswalk; Morris 1993 ordinal scale)
  - visit_date  <- a synthetic date from CDADTC_DAYS_T0 (days from T0), with the
                   -99 sentinel treated as missing (rows with missing day dropped
                   from ordering, not silently set to day 0)

The crosswalk + sentinel handling are applied ONLY when the user confirms
--cohort a4 (recognize-then-confirm). The recognizer itself never mutates data.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from neurotcs.cohorts.base import CohortMatch, register_recognizer

# Verified A4 cdr.csv signature columns.
_A4_SUBJECT = "BID"
_A4_STATE = "CDGLOBAL"
_A4_DAYS = "CDADTC_DAYS_T0"
_A4_SENTINEL = -99
# Distinctive companions that raise confidence (present in real A4 cdr.csv).
_A4_COMPANIONS = ("VISCODE", "AVISIT", "CDRSB", "EPOCH")

# Standard CDR-global -> NeuroTCS state crosswalk.
_CDGLOBAL_TO_STATE = {0.0: "CN", 0.5: "MCI"}  # >=1.0 -> AD handled in code


def _cdglobal_to_state(value: Any) -> str | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v in _CDGLOBAL_TO_STATE:
        return _CDGLOBAL_TO_STATE[v]
    if v >= 1.0:
        return "AD"
    return None


@register_recognizer
def recognize_a4(tables: dict[str, pd.DataFrame]) -> CohortMatch | None:
    """Recognize an A4/LEARN CDR table by its column signature."""
    for sheet, df in tables.items():
        cols = set(map(str, df.columns))
        if not ({_A4_SUBJECT, _A4_STATE, _A4_DAYS} <= cols):
            continue
        companions = sum(1 for c in _A4_COMPANIONS if c in cols)
        # base 0.8 for the exact triple + up to 0.2 for companions
        confidence = 0.8 + 0.05 * min(companions, 4)
        notes = [
            f"Recognized A4/LEARN CDR signature in sheet '{sheet}' "
            f"(BID + CDGLOBAL + CDADTC_DAYS_T0).",
            "subject_id <- BID",
            "state <- CDGLOBAL crosswalk: 0->CN, 0.5->MCI, >=1->AD",
            "visit_date <- synthetic from CDADTC_DAYS_T0 (days from T0); "
            "-99 sentinel treated as MISSING (those rows dropped from ordering).",
            "A4 is preclinical: most subjects are CN; few transitions expected.",
        ]
        return CohortMatch(
            cohort_id="a4",
            display_name="A4/LEARN",
            sheet=sheet,
            confidence=confidence,
            notes=notes,
            build_mapping=_build_a4_mapping,
        )
    return None


def _build_a4_mapping(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Build a staging mapping (+ derived sheet) for a confirmed A4 cohort.

    Fail-closed: raises ValueError if the confirmed A4 sheet is malformed.
    Returns a mapping whose 'clinical' axis points at a DERIVED sheet
    '__a4_staging__' that the caller must add to `tables` (returned alongside).
    To keep this self-contained, we instead build the derived columns IN PLACE on
    a copy and return a mapping referencing the original sheet's derived columns.
    """
    match = recognize_a4(tables)
    if match is None:
        raise ValueError("A4 mapping requested but A4 signature not present.")
    sheet = match.sheet
    df = tables[sheet]
    if _A4_STATE not in df.columns or _A4_SUBJECT not in df.columns:
        raise ValueError(
            f"A4 sheet '{sheet}' missing required columns "
            f"{_A4_SUBJECT}/{_A4_STATE}."
        )
    # Derive state + a usable day column on a copy added back to tables.
    work = df.copy()
    work["__a4_state__"] = work[_A4_STATE].map(_cdglobal_to_state)
    days = pd.to_numeric(work[_A4_DAYS], errors="coerce")
    days = days.where(days != _A4_SENTINEL)  # -99 -> NaN (missing)
    work["__a4_day__"] = days
    # Drop rows with no derivable state or no usable day (fail-closed on junk).
    work = work[work["__a4_state__"].notna() & work["__a4_day__"].notna()].copy()
    if work.empty:
        raise ValueError(
            "A4 mapping: no rows with both a CDGLOBAL state and a non-sentinel "
            "CDADTC_DAYS_T0 remain -- nothing to audit."
        )
    # Synthetic ISO date from day-offset (T0 = 2000-01-01).
    work["__a4_visit_date__"] = (
        pd.Timestamp("2000-01-01")
        + pd.to_timedelta(work["__a4_day__"].astype(int), unit="D")
    ).dt.strftime("%Y-%m-%d")
    tables[sheet] = work  # caller sees the derived columns
    return {
        "clinical": {
            "sheet": sheet,
            "subject_id": _A4_SUBJECT,
            "visit_date": "__a4_visit_date__",
            "state": "__a4_state__",
            # visit omitted -> v1.83.0 derives index from visit_date order
        },
        "ranges": [],
    }

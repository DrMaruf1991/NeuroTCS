"""Cohort recognizer base types + registry (v1.83.0)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class CohortMatch:
    """A positive cohort recognition.

    Attributes:
        cohort_id: stable short id (e.g. "a4"), used as the --cohort value.
        display_name: human label (e.g. "A4/LEARN").
        sheet: the table name the staging mapping is built from.
        confidence: 0..1 -- how strongly the signature matched.
        notes: human-readable lines explaining what was recognized and what the
            mapping will do (crosswalks, sentinels, ordering). Surfaced by the CLI.
        build_mapping: callable(tables) -> mapping dict for tables_to_submission.
            May raise ValueError (fail-closed) if the confirmed cohort data is
            malformed; never silently guesses.
    """

    cohort_id: str
    display_name: str
    sheet: str
    confidence: float
    notes: list[str] = field(default_factory=list)
    build_mapping: Callable[[dict[str, pd.DataFrame]], dict[str, Any]] | None = None


# Each recognizer: tables -> CohortMatch | None. Registered in priority order.
_RECOGNIZERS: list[Callable[[dict[str, pd.DataFrame]], CohortMatch | None]] = []


def register_recognizer(
    fn: Callable[[dict[str, pd.DataFrame]], CohortMatch | None],
) -> Callable[[dict[str, pd.DataFrame]], CohortMatch | None]:
    """Register a recognizer. Idempotent by function identity."""
    if fn not in _RECOGNIZERS:
        _RECOGNIZERS.append(fn)
    return fn


def recognize_cohort(
    tables: dict[str, pd.DataFrame],
) -> CohortMatch | None:
    """Return the highest-confidence cohort match, or None if nothing matches.

    Fail-closed: a recognizer that raises is treated as a non-match (it must not
    break the audit path); the generic scaffold then handles the file.
    """
    best: CohortMatch | None = None
    for fn in _RECOGNIZERS:
        try:
            m = fn(tables)
        except Exception:
            m = None
        if m is None:
            continue
        if best is None or m.confidence > best.confidence:
            best = m
    return best

"""
neurotcs.cohorts -- column-signature cohort recognizers (v1.83.0).

A recognizer inspects loaded tables and, if their column signature matches a
known public cohort, returns a CohortMatch describing how to build the NeuroTCS
staging mapping for that cohort (sentinels, scale crosswalks, ordering key).

DESIGN -- recognize-then-CONFIRM, never silent:
  recognize_cohort(tables) returns a CohortMatch or None. The CLI SUGGESTS the
  match and applies it only when the user passes --cohort <id>. Recognition never
  silently rewrites clinical values; the user confirms. This preserves the
  fail-closed, no-silent-guess contract of the zero-config audit path.

SCOPE (honest): this layer recognizes cohorts whose signature is explicitly
taught here. It is NOT a universal file analyzer. An unrecognized file returns
None and the caller falls through to the generic scaffold / fail-closed template.

The recognizers here build MAPPINGS for the existing tables_to_submission path;
they do not touch the invariant-locked Trajectory loaders in
neurotcs.input_contract.*.adapters (those remain the canonical cohort loaders).
"""
from __future__ import annotations

from neurotcs.cohorts import a4 as _a4  # noqa: F401  (registers recognizer)
from neurotcs.cohorts import adni as _adni  # noqa: F401  (registers recognizer)
from neurotcs.cohorts import miriad as _miriad  # noqa: F401  (registers recognizer)
from neurotcs.cohorts import nacc as _nacc  # noqa: F401  (registers recognizer)
from neurotcs.cohorts import oasis3 as _oasis3  # noqa: F401  (registers recognizer)
from neurotcs.cohorts.base import CohortMatch, recognize_cohort

__all__ = ["CohortMatch", "recognize_cohort"]

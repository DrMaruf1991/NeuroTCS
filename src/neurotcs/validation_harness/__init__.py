"""
neurotcs.validation_harness — Synthetic-trajectory self-tests (Piece 7 of 7, PLANNED).

Per spec §C.3, every rule pack ships with a synthetic-trajectory test suite
that generates clean (admissible) and corrupted (violation-injected)
trajectories, then verifies the audit engine catches the violations at
expected rates. Acts as a "unit test for clinical correctness" of the
audit engine.

Planned harnesses:
  - AD: synthetic CN/MCI/AD trajectories with planted rapid CN->AD flips
  - PD: synthetic H&Y trajectories with planted backward jumps
  - MS: synthetic EDSS trajectories with planted impossible jumps
  - Oncology: synthetic RECIST sequences with planted CR->PD direct jumps
  - Stroke: synthetic mRS with planted post-death transitions
  - Lung: synthetic Fleischner with planted >180-day three-band jumps

Status: NOT YET IMPLEMENTED.
"""


class ValidationHarnessNotImplementedError(NotImplementedError):
    pass


def run_harness(*args, **kwargs):
    raise ValidationHarnessNotImplementedError(
        "neurotcs.validation_harness (Piece 7 of 7) is planned but not yet "
        "implemented."
    )


__all__ = ["run_harness", "ValidationHarnessNotImplementedError"]
__status__ = "planned"

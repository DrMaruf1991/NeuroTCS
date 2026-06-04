"""Error taxonomy and ground-truth manifest for the Arm B validation harness.

The taxonomy is the pre-registered set of realistic data-error types the study
declares in advance (protocol Section 6, step 1). Each injected error records
its exact coordinate (subject_id, visit, field) and type, so the scorer can
join injections against NeuroTCS flags without ambiguity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ErrorType(str, Enum):
    """Pre-registered realistic data-error taxonomy.

    These are categories of data-management defects documented in clinical-
    trial data-quality literature. They are intentionally framed as data
    problems (not biological states): the study measures whether a realistic
    distribution of such defects falls within the encoded rule set's
    detectable scope.
    """

    UNIT_ERROR = "unit_error"
    """Value recorded in the wrong unit (e.g. ng/mL vs pg/mL): scales value."""

    DECIMAL_SHIFT = "decimal_shift"
    """Misplaced decimal point (x10 or /10): a common transcription defect."""

    TRANSCRIPTION_DIGIT = "transcription_digit"
    """Single transposed/duplicated digit producing an out-of-range value."""

    SIGN_FLIP = "sign_flip"
    """Negated value (data-entry sign error)."""

    IMPLAUSIBLE_HIGH = "implausible_high"
    """Value pushed above the physiological/diagnostic envelope."""

    IMPLAUSIBLE_LOW = "implausible_low"
    """Value pushed below the physiological/diagnostic envelope."""

    CATEGORICAL_INVALID = "categorical_invalid"
    """Categorical field set to a value outside its admissible set
    (e.g. an APOE genotype containing a non-existent allele)."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True)
class InjectedError:
    """One injected error with its exact ground-truth coordinate.

    The (subject_id, field, visit) triple is the join key against NeuroTCS
    flags. ``visit`` is normalized to a string (or None) to match the flag
    schema, which emits visit as a string.
    """

    subject_id: str
    field: str
    visit: str | None
    error_type: ErrorType
    original_value: object
    corrupted_value: object
    sheet: str

    @property
    def key(self) -> tuple[str, str, str | None]:
        """Coordinate join key: (subject_id, field, visit)."""
        return (self.subject_id, self.field, self.visit)


@dataclass
class InjectionSpec:
    """How many errors of each type to inject.

    Counts are explicit and pre-declared (not random rates) so a run is fully
    reproducible and the denominator per type is known exactly. The injector
    consumes a spec + a seed; identical (spec, seed, cohort) reproduce an
    identical manifest.
    """

    counts: dict[ErrorType, int] = field(default_factory=dict)

    def total(self) -> int:
        return sum(self.counts.values())


@dataclass
class InjectionManifest:
    """Ground-truth record of everything injected into a cohort copy.

    ``injected`` is the list of all injected errors (the positives).
    ``clean_keys`` is the set of (subject_id, field, visit) coordinates that
    were left untouched on injectable fields -- the denominator for specificity
    (a flag on a clean key is a false positive for the injection study).
    """

    injected: list[InjectedError] = field(default_factory=list)
    clean_keys: set[tuple[str, str, str | None]] = field(default_factory=set)
    seed: int = 0
    cohort_path: str = ""

    def injected_keys(self) -> set[tuple[str, str, str | None]]:
        return {e.key for e in self.injected}

    def by_type(self) -> dict[ErrorType, list[InjectedError]]:
        out: dict[ErrorType, list[InjectedError]] = {}
        for e in self.injected:
            out.setdefault(e.error_type, []).append(e)
        return out

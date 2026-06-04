"""neurotcs.validation -- Arm B error-injection validation harness.

Implements the executable arm of the NeuroTCS Flag-Validation Study Protocol
(docs/VALIDATION_PROTOCOL.md, Section 6). Given a CLEAN cohort, it injects a
pre-registered taxonomy of realistic data errors at known coordinates, runs the
standard NeuroTCS audit, and scores detection against the injected ground-truth
manifest.

HONEST SCOPE (read this before interpreting any output):
  - This harness measures rule-set COVERAGE against a realistic error
    distribution, plus SPECIFICITY on un-injected records. It does NOT measure
    "accuracy": for an error type that maps exactly onto an encoded rule,
    detection is 1.0 by construction (NeuroTCS is a deterministic matcher).
  - It is NOT a substitute for Arm A (expert adjudication of natural flags),
    which establishes flag precision (PPV) and requires DUA-gated cohort data
    and board-certified reviewers. See the protocol, Sections 2-5 and 11.
  - All metrics are reported with confidence intervals; a coverage number
    without its CI and its taxonomy is not interpretable.

Public API:
    ErrorType, InjectedError, InjectionManifest        (taxonomy + ground truth)
    inject_errors(cohort_dir, spec, seed) -> manifest  (injector)
    score_detection(manifest, flags) -> DetectionReport (scorer)
    wilson_interval(k, n), clopper_pearson_interval(k, n)
"""
from neurotcs.validation.injector import inject_errors  # noqa: F401
from neurotcs.validation.runner import run_audit_flags  # noqa: F401
from neurotcs.validation.scorer import (  # noqa: F401
    DetectionReport,
    PerTypeResult,
    clopper_pearson_interval,
    score_detection,
    wilson_interval,
)
from neurotcs.validation.taxonomy import (  # noqa: F401
    ErrorType,
    InjectedError,
    InjectionManifest,
    InjectionSpec,
)

__all__ = [
    "ErrorType",
    "InjectedError",
    "InjectionManifest",
    "InjectionSpec",
    "DetectionReport",
    "PerTypeResult",
    "score_detection",
    "wilson_interval",
    "clopper_pearson_interval",
    "inject_errors",
    "run_audit_flags",
]

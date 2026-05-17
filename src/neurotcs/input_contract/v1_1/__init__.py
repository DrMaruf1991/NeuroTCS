"""
neurotcs.input_contract.v1_1 — Continuous-biomarker input contract (Piece 2 of 7).

Extends v1.0 with continuous biomarkers (e.g. hippocampal volume in mL),
UCUM unit allowlist, value_type enum, reference_range metadata. Full v1.0
backward compatibility. 11-step validation pipeline, fail-closed.

Production-validated against real ADNI UCSFFSX7: 9,536 predictions / 1,772
patients / 19,072 hippocampal volume measurements (ST29SV right + ST88SV
left, mm^3 -> mL); VALID with zero errors and zero warnings.

Public API:
    from neurotcs.input_contract.v1_1 import validate_submission

    report = validate_submission("path/to/submission_directory")
    if not report.has_errors:
        print(f"Valid: {report.summary()}")
"""

from neurotcs.input_contract.v1_1.validate import (  # noqa: F401
    THIS_VALIDATOR_VERSION,
    ValidationIssue,
    ValidationReport,
    validate_submission,
)

__all__ = [
    "THIS_VALIDATOR_VERSION",
    "ValidationIssue",
    "ValidationReport",
    "validate_submission",
]
__contract_version__ = "1.1.0"

"""
neurotcs.input_contract.v1_0 — Categorical input contract (Piece 1 of 7).

8-step validation pipeline for longitudinal medical AI predictions over a
discrete categorical state space (CN/MCI/AD, PR/CR/SD/PD, etc.). Fail-closed
on any error. Production-validated against real ADNI: 14,958 visits, 2,955
patients; caught 2 duplicate-visit anomalies and 76 timestamp ties.

Public API:
    from neurotcs.input_contract.v1_0 import validate_submission

    report = validate_submission("path/to/submission_directory")
    if report.has_errors:
        for issue in report.errors:
            print(issue)
"""

from neurotcs.input_contract.v1_0.validate import (  # noqa: F401
    CONTRACT_VERSION,
    ValidationIssue,
    ValidationReport,
    validate_submission,
)

__all__ = [
    "CONTRACT_VERSION",
    "ValidationIssue",
    "ValidationReport",
    "validate_submission",
]
__contract_version__ = "1.0.0"

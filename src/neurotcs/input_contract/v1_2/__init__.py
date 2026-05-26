"""
neurotcs.input_contract.v1_2 — Layer-3-anchored input contract.

Extends v1.1 (continuous biomarkers + UCUM units) with two new optional
manifest fields required to anchor Layer 3 cross-sheet invariants
(LAYER_3_DESIGN.md §9.3, manifest_data_consistency@1.0.0):

    - `declares_continuous_biomarkers` (boolean): when true the submission
      MUST include a biomarkers sheet with UCUM-conformant `unit` field on
      every numeric row. Enforced cross-sheet by
      cross_sheet/manifest_data_consistency invariant
      `continuous_biomarkers_declared_then_units_required`.
    - `data_files.attribution` (path): directory containing one attribution
      JSON file per (patient_id, visit_id) tuple. Required when
      conformance_level == "L3". Enforced cross-sheet by
      cross_sheet/manifest_data_consistency invariant
      `L3_conformance_requires_complete_attribution`.

Full backward compatibility: v1.0 and v1.1 submissions remain valid
under this validator. The new fields are optional unless the L3-attribution
branch fires.

Public API:
    from neurotcs.input_contract.v1_2 import validate_submission

    report = validate_submission("path/to/submission_directory")
    if not report.has_errors:
        print(f"Valid: {report.summary()}")
"""

from neurotcs.input_contract.v1_2.validate import (  # noqa: F401
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

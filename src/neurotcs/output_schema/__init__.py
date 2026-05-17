"""
neurotcs.output_schema — FHIR Observation output schema (Piece 5 of 7, PLANNED).

This subpackage will emit audit results as FHIR Observation resources for
EHR interoperability, per spec §C.4. Each Observation will encode:
  - cTCS / pTCS / uTCS values and bootstrap CIs
  - Rule pack ID and SHA-256 (for reproducibility)
  - Vendor model identifier
  - Patient/visit references (de-identified)

Status: NOT YET IMPLEMENTED.
"""


class OutputSchemaNotImplementedError(NotImplementedError):
    pass


def emit_fhir_observation(*args, **kwargs):
    raise OutputSchemaNotImplementedError(
        "neurotcs.output_schema (Piece 5 of 7) is planned but not yet "
        "implemented."
    )


__all__ = ["emit_fhir_observation", "OutputSchemaNotImplementedError"]
__status__ = "planned"

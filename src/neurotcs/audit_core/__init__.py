"""
neurotcs.audit_core — Audit engine (Piece 4 of 7, PLANNED).

This subpackage will house the cTCS / pTCS / uTCS scoring engine per
temporalmetric v1.6 FINAL spec §A.2-A.5:

    cTCS  Coherence Temporal Consistency Score (rule-based admissibility)
    pTCS  Probabilistic TCS (Markov log-likelihood with matrix exponential
          M(Δτ) = exp(Q · Δτ / 365), Huber c=1.345)
    uTCS  Unified TCS (weighted ensemble)

With cluster-bootstrap confidence intervals (B = 10,000 patient-level
resamples) per spec §A.5.

Public API (planned):
    from neurotcs.audit_core import audit
    result = audit(predictions, rulepack, transitions_priors=...)
    print(result.ctcs, result.ptcs.ci_95)

Status: NOT YET IMPLEMENTED. Stub raises NotImplementedError.
"""


class AuditCoreNotImplementedError(NotImplementedError):
    """Raised when audit_core APIs are called before piece 4 ships."""
    pass


def audit(*args, **kwargs):
    raise AuditCoreNotImplementedError(
        "neurotcs.audit_core (Piece 4 of 7) is planned but not yet "
        "implemented. Track progress at docs/spec/temporalmetric_v1.6_FINAL.md "
        "Sections A.2 through A.5."
    )


__all__ = ["audit", "AuditCoreNotImplementedError"]
__status__ = "planned"

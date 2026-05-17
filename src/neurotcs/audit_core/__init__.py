"""
neurotcs.audit_core — Audit engine (Piece 4 of 7).

The audit core consumes (input contract + rule pack) and produces:

  - cTCS  Categorical Temporal Consistency Score (rule-based admissibility,
          §A.2)
  - pTCS  Probabilistic TCS (time-aware Markov log-likelihood with
          matrix exponential M(Δτ) = exp(Q · Δτ / 365), §A.3)
  - uTCS  Uncertainty-weighted TCS (Thulasidasan 2019 extension, §A.4)

Each with cluster-bootstrap 95% confidence intervals (B = 10,000 by default,
BCa correction) and Huber M-estimator (c = 1.345). Per temporalmetric v1.6
FINAL spec §A.2 — §A.5.

Quick start
-----------

    from neurotcs import load_rulepack
    from neurotcs.audit_core import audit, trajectories_from_dataframe

    # Build trajectories from a long-format DataFrame
    trajectories = trajectories_from_dataframe(
        df,
        patient_id_col="RID",
        visit_date_col="EXAMDATE",
        state_col="DIAGNOSIS",
        state_label_map={"Dementia": "AD"},
    )

    # Load a production rule pack
    pack = load_rulepack("ad/niaaa_2018")

    # Run the audit
    result = audit(trajectories, pack, bootstrap_B=10_000, seed=42)
    print(result.summary())
    print(result.audit_id)
"""

from neurotcs.audit_core.audit import (  # noqa: F401
    AuditResult,
    MetricResult,
    audit,
)
from neurotcs.audit_core.bootstrap import (  # noqa: F401
    BootstrapCI,
    cluster_bootstrap,
    huber_m_estimate,
    paired_cluster_bootstrap_difference,
)
from neurotcs.audit_core.scoring import (  # noqa: F401
    GeneratorMatrix,
    PerPatientScores,
    build_generator,
    ctcs_per_patient,
    ctcs_per_patient_array,
    ptcs_per_patient,
    ptcs_per_patient_array,
    score_cohort,
    utcs_per_patient,
    utcs_per_patient_array,
)
from neurotcs.audit_core.trajectory import (  # noqa: F401
    Trajectory,
    trajectories_from_dataframe,
)

__status__ = "production"
__version__ = "1.0.0"

__all__ = [
    "AuditResult",
    "BootstrapCI",
    "GeneratorMatrix",
    "MetricResult",
    "PerPatientScores",
    "Trajectory",
    "audit",
    "build_generator",
    "cluster_bootstrap",
    "ctcs_per_patient",
    "ctcs_per_patient_array",
    "huber_m_estimate",
    "paired_cluster_bootstrap_difference",
    "ptcs_per_patient",
    "ptcs_per_patient_array",
    "score_cohort",
    "trajectories_from_dataframe",
    "utcs_per_patient",
    "utcs_per_patient_array",
]

"""
NeuroTCS / temporalmetric — Citation-locked, fail-closed longitudinal medical AI audit framework.

Subpackages:
  neurotcs.input_contract.v1_0    — Categorical input contract (Piece 1, SHIPPED)
  neurotcs.input_contract.v1_1    — Continuous-biomarker input contract (Piece 2, SHIPPED)
  neurotcs.rulepack               — Citation-locked clinical rule packs (Piece 3, SHIPPED)
  neurotcs.audit_core             — cTCS/pTCS/uTCS audit engine (Piece 4, PLANNED)
  neurotcs.output_schema          — FHIR Observation interop schema (Piece 5, PLANNED)
  neurotcs.adapters               — Dataset adapters: ADNI, PPMI, RIDER, MIRIAD (Piece 6, PLANNED)
  neurotcs.validation_harness     — Synthetic-trajectory self-tests (Piece 7, PLANNED)

Public API (the most common imports):
    from neurotcs.rulepack import load_rulepack, list_rulepacks
    from neurotcs.input_contract.v1_1 import validate_manifest
"""

__version__ = "1.4.0"
__author__ = "Marufjon Salokhiddinov, MD PhD"
__license__ = "Apache-2.0"

# Re-export the most-used names so users can write `from neurotcs import load_rulepack`.
# Audit core (Piece 4 of 7, SHIPPED in v1.2.0)
from neurotcs.audit_core import (  # noqa: E402,F401
    AuditResult,
    BootstrapCI,
    GeneratorMatrix,
    PerPatientScores,
    Trajectory,
    audit,
    cluster_bootstrap,
    huber_m_estimate,
    paired_cluster_bootstrap_difference,
    trajectories_from_dataframe,
)
from neurotcs.rulepack.loader import (  # noqa: E402,F401
    LoadedRulePack,
    RulePackLoadError,
    list_rulepacks,
    load_rulepack,
    load_rulepack_from_path,
)
from neurotcs.rulepack.schema import (  # noqa: E402,F401
    SCHEMA_VERSION,
    Citation,
    DiseaseDomain,
    InadmissibleTransition,
    RulePack,
    RulePackStatus,
    State,
    Transition,
    TransitionPrior,
)

__all__ = [
    "__version__",
    # rule pack
    "Citation",
    "DiseaseDomain",
    "InadmissibleTransition",
    "LoadedRulePack",
    "RulePack",
    "RulePackLoadError",
    "RulePackStatus",
    "SCHEMA_VERSION",
    "State",
    "Transition",
    "TransitionPrior",
    "list_rulepacks",
    "load_rulepack",
    "load_rulepack_from_path",
    # audit core
    "AuditResult",
    "BootstrapCI",
    "GeneratorMatrix",
    "PerPatientScores",
    "Trajectory",
    "audit",
    "cluster_bootstrap",
    "huber_m_estimate",
    "paired_cluster_bootstrap_difference",
    "trajectories_from_dataframe",
]

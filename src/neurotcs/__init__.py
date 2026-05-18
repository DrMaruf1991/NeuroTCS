"""
NeuroTCS / temporalmetric — Citation-locked, fail-closed longitudinal medical AI audit framework.

Subpackages:
  neurotcs.input_contract.v1_0    — Categorical input contract (Piece 1, SHIPPED)
  neurotcs.input_contract.v1_1    — Continuous-biomarker input contract (Piece 2, SHIPPED)
  neurotcs.rulepack               — Citation-locked clinical rule packs (Piece 3, SHIPPED)
  neurotcs.audit_core             — cTCS/pTCS/uTCS audit engine (Piece 4, SHIPPED v1.2.0)
  neurotcs.sample_size            — Riley 2024 sample-size calculator (NEW v1.7.0)
  neurotcs.fairness               — FUTURE-AI Fairness + Robustness panels (NEW v1.7.0)
  neurotcs.silent_deployment      — Kwong 2022 silent-trial methodology (NEW v1.7.0)
  neurotcs.scanner_factorial      — Scanner × vendor × interval factorial (NEW v1.7.0)
  neurotcs.threshold_derivation   — Empirical operational thresholds (NEW v1.7.0)
  neurotcs.output_schema          — FHIR Observation interop schema (Piece 5, PLANNED v1.7.4)
  neurotcs.adapters               — Dataset adapters: ADNI, PPMI, RIDER, MIRIAD (Piece 6, PLANNED)
  neurotcs.validation_harness     — Synthetic-trajectory self-tests (Piece 7, PLANNED v1.7.1)

Public API (the most common imports):
    from neurotcs.rulepack import load_rulepack, list_rulepacks
    from neurotcs.input_contract.v1_1 import validate_manifest
    from neurotcs.sample_size import binary_sample_size
    from neurotcs.fairness import fairness_audit, robustness_audit
    from neurotcs.silent_deployment import make_silent_deployment_evidence
"""

__version__ = "1.7.1"
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
from neurotcs.fairness import (  # noqa: E402,F401
    FairnessAuditResult,
    RobustnessAuditResult,
    StratumMetrics,
    fairness_audit,
    robustness_audit,
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
    AttributionType,
    Citation,
    DiseaseDomain,
    InadmissibleTransition,
    RulePack,
    RulePackStatus,
    State,
    Transition,
    TransitionPrior,
)

# v1.7.0 new modules
from neurotcs.sample_size import (  # noqa: E402,F401
    BinarySampleSize,
    binary_sample_size,
)
from neurotcs.scanner_factorial import (  # noqa: E402,F401
    FactorialCell,
    ScannerFactorialResult,
    scanner_factorial,
)
from neurotcs.silent_deployment import (  # noqa: E402,F401
    SilentDeploymentEvidence,
    SilentTrialTheme,
    SilentTrialThemeFinding,
    make_silent_deployment_evidence,
)
from neurotcs.threshold_derivation import (  # noqa: E402,F401
    OperationalThreshold,
    derive_threshold_conformal,
    derive_threshold_distribution,
)

__all__ = [
    "__version__",
    # rule pack
    "AttributionType",
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
    # v1.7.0: sample size (Riley 2024)
    "BinarySampleSize",
    "binary_sample_size",
    # v1.7.0: fairness + robustness (FUTURE-AI 2025)
    "FairnessAuditResult",
    "RobustnessAuditResult",
    "StratumMetrics",
    "fairness_audit",
    "robustness_audit",
    # v1.7.0: silent deployment (Kwong 2022 + DECIDE-AI 2022)
    "SilentDeploymentEvidence",
    "SilentTrialTheme",
    "SilentTrialThemeFinding",
    "make_silent_deployment_evidence",
    # v1.7.0: scanner factorial (FUTURE-AI Robustness 3)
    "FactorialCell",
    "ScannerFactorialResult",
    "scanner_factorial",
    # v1.7.0: threshold derivation (Larson 2025 ACR-SIIM)
    "OperationalThreshold",
    "derive_threshold_conformal",
    "derive_threshold_distribution",
]

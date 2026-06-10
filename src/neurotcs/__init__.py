"""
NeuroTCS / temporalmetric — Citation-locked, fail-closed longitudinal medical AI audit framework.

Subpackages:
  neurotcs.input_contract.v1_0    — Categorical input contract (Piece 1, SHIPPED)
  neurotcs.input_contract.v1_1    — Continuous-biomarker input contract (Piece 2, SHIPPED)
  neurotcs.rulepack               — Citation-locked clinical rule packs (Piece 3, SHIPPED)
  neurotcs.audit_core             — cTCS/pTCS/uTCS audit engine (Piece 4, SHIPPED v1.2.0)
  neurotcs.sample_size            — Riley 2024 sample-size calculator (NEW v1.7.0)
  neurotcs.fairness               — FUTURE-AI Fairness + Robustness panels (v1.7.0+)
  neurotcs.silent_deployment      — Kwong 2022 silent-trial methodology (v1.7.0+)
  neurotcs.scanner_factorial      — Scanner × vendor × interval factorial (v1.7.0+)
  neurotcs.threshold_derivation   — Empirical operational thresholds (v1.7.0+)
  neurotcs.provenance             — Primary-source citation/quote registry (v1.52.0+)
  neurotcs.output_schema          — FHIR Observation interop schema (ROADMAP v1.9.x; raises ImportError until shipped)
  neurotcs.adapters               — Dataset adapters: ADNI, OASIS-3, NACC, MIRIAD (4 AD cohorts; Piece 6, partial — see input_contract/v1_1/adapters/)
  neurotcs.validation_harness     — Synthetic-trajectory self-tests (ROADMAP v1.9.x; raises ImportError until shipped)

Public API (the most common imports):
    from neurotcs.rulepack import load_rulepack, list_rulepacks
    from neurotcs.input_contract.v1_1 import validate_manifest
    from neurotcs.sample_size import binary_sample_size
    from neurotcs.fairness import fairness_audit, robustness_audit
    from neurotcs.silent_deployment import make_silent_deployment_evidence
"""

__version__ = "1.73.0"
__author__ = "Marufjon Salokhiddinov, MD PhD"
__license__ = "Apache-2.0"


# ---------------------------------------------------------------------------
# Roadmap-namespace import hook (Issues 17+18, v1.8.1)
#
# In v1.8.0, `neurotcs.validation_harness` (Piece 7) and `neurotcs.output_schema`
# (Piece 5) shipped as empty stub subpackages that raised NotImplementedError
# on every call. In v1.8.1 the stub directories are removed entirely; this
# meta-path finder catches any import of the planned subpackages and raises
# a helpful ImportError pointing to the roadmap, rather than the bare
# ModuleNotFoundError users would otherwise see.
# ---------------------------------------------------------------------------
import sys as _sys
from importlib.abc import MetaPathFinder as _MetaPathFinder


class _PlannedModuleFinder(_MetaPathFinder):
    """Replace ModuleNotFoundError with a roadmap-pointer ImportError."""

    _PLANNED = {
        "neurotcs.validation_harness": (
            "Piece 7 of 7 (synthetic-trajectory self-tests)",
            "v1.9.x",
            "https://github.com/DrMaruf1991/NeuroTCS/issues",
        ),
        "neurotcs.output_schema": (
            "Piece 5 of 7 (FHIR Observation emitter)",
            "v1.9.x",
            "https://github.com/DrMaruf1991/NeuroTCS/issues",
        ),
    }

    def find_spec(self, name, path, target=None):  # noqa: D401, ARG002
        if name in self._PLANNED:
            piece, version, url = self._PLANNED[name]
            raise ImportError(
                f"`{name}` ({piece}) is a roadmap item planned for {version}. "
                f"Track progress: {url}. "
                f"It is intentionally NOT shipped in the current v1.x release."
            )
        return None


_sys.meta_path.insert(0, _PlannedModuleFinder())


# Re-export the most-used names so users can write `from neurotcs import load_rulepack`.
# Audit core (Piece 4 of 7, SHIPPED in v1.2.0)
from neurotcs.audit_core import (  # noqa: E402,F401
    AuditResult,
    BootstrapCI,
    GeneratorMatrix,
    PerPatientScores,
    PerTransitionFlags,
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
    cohort_fairness_audit,
    fairness_audit,
    robustness_audit,
)
from neurotcs.orchestration.bundle import (  # noqa: E402,F401
    BUNDLE_FORMAT_VERSION,
    BundleVerificationError,
    build_bundle,
    fingerprint_dataframe,
    fingerprint_file,
    render_report,
    verify_bundle,
)

# v1.23.0: fail-closed orchestrator + vocabulary gating (enforce the definition)
from neurotcs.orchestration.orchestrator import (  # noqa: E402,F401
    CoverageManifest,
    IncompleteAuditError,
    OrchestratorResult,
    run_full_audit,
)
from neurotcs.orchestration.vocabulary import (  # noqa: E402,F401
    VocabularyMatch,
    VocabularyMismatchError,
    assess_vocabulary,
    select_rulepack_or_refuse,
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
    "PerTransitionFlags",
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
    "cohort_fairness_audit",
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
    # v1.23.0: fail-closed orchestrator + vocabulary gating
    "run_full_audit",
    "OrchestratorResult",
    "CoverageManifest",
    "IncompleteAuditError",
    "assess_vocabulary",
    "select_rulepack_or_refuse",
    "VocabularyMatch",
    "VocabularyMismatchError",
    # v1.23.2: self-verifying result bundle
    "build_bundle",
    "verify_bundle",
    "fingerprint_dataframe",
    "fingerprint_file",
    "render_report",
    "BundleVerificationError",
    "BUNDLE_FORMAT_VERSION",
]

"""
neurotcs.silent_deployment — Silent-trial methodology for NeuroTCS audit deployment
====================================================================================

Implements the silent-trial 4-theme evaluation framework from:

    Kwong JCC, Erdman L, Khondker A, Skreta M, Goldenberg A, McCradden MD,
    Lorenzo AJ, Rickard M. The silent trial - the bridge between
    bench-to-bedside clinical AI applications.
    Front Digit Health 2022;4:929508.
    DOI: 10.3389/fdgth.2022.929508
    PMID: 36052317
    License: CC-BY 4.0 (verbatim Table 1 reproduction permitted with citation)

Verbatim silent-trial definition (Kwong 2022):

    "the silent trial, which evaluates the proposed model on patients in
     real-time, while the end-users (i.e., clinicians) are blinded to
     predictions such that they do not influence clinical decision-making."

Three-stage roadmap (Kwong 2022, verbatim):

    "(1) exploratory model development, (2) a silent trial, and
     (3) prospective clinical evaluation."

NeuroTCS sits in stage 2 — it is the auditor that runs during silent
deployment to provide objective trajectory-consistency evidence before
the model is allowed to influence clinical decisions.

This module also references the DECIDE-AI reporting guideline:

    Vasey B, Nagendran M, Campbell B, Clifton DA, Collins GS, Denaxas S, et al.;
    DECIDE-AI expert group. Reporting guideline for the early-stage clinical
    evaluation of decision support systems driven by artificial intelligence:
    DECIDE-AI. Nat Med 2022;28(5):924-933.
    DOI: 10.1038/s41591-022-01772-9
    PMID: 35585196

Memory-drift correction note
----------------------------
DECIDE-AI does NOT have Stage A/B/C labels. It is a SINGLE-STAGE reporting
guideline (17 AI-specific + 28 subitems + 10 generic items). The "silent
deployment" concept comes from Kwong 2022, a separate primary source. Both
are cited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "SilentTrialTheme",
    "SilentTrialThemeFinding",
    "SilentDeploymentEvidence",
    "make_silent_deployment_evidence",
    "KWONG_2022_CITATION",
    "KWONG_2022_DOI",
    "KWONG_2022_PMID",
    "DECIDE_AI_CITATION",
    "DECIDE_AI_DOI",
    "DECIDE_AI_PMID",
]

KWONG_2022_CITATION = (
    "Kwong JCC, Erdman L, Khondker A, Skreta M, Goldenberg A, McCradden MD, "
    "Lorenzo AJ, Rickard M. The silent trial - the bridge between "
    "bench-to-bedside clinical AI applications. "
    "Front Digit Health 2022;4:929508."
)
KWONG_2022_DOI = "10.3389/fdgth.2022.929508"
KWONG_2022_PMID = "36052317"

DECIDE_AI_CITATION = (
    "Vasey B, Nagendran M, Campbell B, Clifton DA, Collins GS, Denaxas S, "
    "Denniston AK, Faes L, Geerts B, Ibrahim M, Liu X, Mateen BA, Mathur P, "
    "McCradden MD, Morgan L, Ordish J, Rogers C, Saria S, Ting DSW, "
    "Watkinson P, Weber W, Wheatstone P, McCulloch P; DECIDE-AI expert group. "
    "Reporting guideline for the early-stage clinical evaluation of decision "
    "support systems driven by artificial intelligence: DECIDE-AI. "
    "Nat Med 2022;28(5):924-933."
)
DECIDE_AI_DOI = "10.1038/s41591-022-01772-9"
DECIDE_AI_PMID = "35585196"


class SilentTrialTheme(str, Enum):
    """Four major themes to explore during the silent trial.

    Verbatim from Kwong et al. 2022, Table 1.
    """

    DATASET_DRIFT = "dataset_drift"
    BIAS = "bias"
    FEASIBILITY = "feasibility"
    STAKEHOLDER_ATTITUDES = "stakeholder_attitudes"


# Verbatim from Kwong 2022 Table 1 — key questions per theme. Reproduced under
# CC-BY 4.0 with attribution.
KWONG_2022_THEME_QUESTIONS: dict[SilentTrialTheme, tuple[str, ...]] = {
    SilentTrialTheme.DATASET_DRIFT: (
        "Are there any changes as to how data are defined and collected?",
        "Are there any changes to patient demographics, clinical settings, or "
        "unexpected events (i.e.: COVID-19) that would impact the patient "
        "population in which the model is applied?",
        "Are there any changes in clinical practice such as indication, "
        "standard of care, or patient preference, that would influence the "
        "data being collected?",
    ),
    SilentTrialTheme.BIAS: (
        "Which subset of patients benefit from the model?",
        "Which subset of patients are harmed by the model?",
    ),
    SilentTrialTheme.FEASIBILITY: (
        "How much time does it take for the end-user (i.e.: clinician) to "
        "input the necessary variables to generate a prediction?",
        "How is the clinical workflow or duration of a clinic visit impacted "
        "with the use of the AI intervention? Importantly, does it slow down "
        "clinical workflow without a clear benefit?",
        "Is the user interface simple enough to be used at point of care with "
        "minimal or no training?",
        "Are the model predictions easy to understand? Are the model "
        "explanations easy to interpret?",
        "How much computing resources or infrastructure are required to "
        "maintain the AI model at scale?",
    ),
    SilentTrialTheme.STAKEHOLDER_ATTITUDES: (
        "Does the AI intervention facilitate patient counseling, "
        "decision-making, or treatment planning?",
        "Are patients comfortable with the use of AI interventions to support "
        "their care?",
        "What are the patient's priorities or goals of care regarding their "
        "condition and are they addressed by the AI intervention?",
    ),
}


@dataclass(frozen=True)
class SilentTrialThemeFinding:
    """A single finding under one of the four silent-trial themes."""

    theme: SilentTrialTheme
    question: str
    finding: str
    severity: str  # one of: "info", "warning", "critical"
    evidence_ref: str = ""  # optional pointer to supporting NeuroTCS audit output


@dataclass(frozen=True)
class SilentDeploymentEvidence:
    """A complete silent-deployment evidence package.

    Pairs the Kwong 2022 four-theme structure with NeuroTCS audit outputs so
    that the silent-trial period produces a structured, defensible report.
    """

    model_name: str
    model_hash: str  # SHA-256 of model artifact
    rulepack_id: str
    rulepack_version: str
    audit_id: str
    silent_trial_start: str  # ISO 8601 date
    silent_trial_end: str  # ISO 8601 date
    n_patients: int
    n_transitions: int
    n_flagged: int
    findings: tuple[SilentTrialThemeFinding, ...] = field(default_factory=tuple)
    kwong_2022_citation: str = KWONG_2022_CITATION
    kwong_2022_doi: str = KWONG_2022_DOI
    kwong_2022_pmid: str = KWONG_2022_PMID
    decide_ai_citation: str = DECIDE_AI_CITATION
    decide_ai_doi: str = DECIDE_AI_DOI
    decide_ai_pmid: str = DECIDE_AI_PMID

    def themes_covered(self) -> set[SilentTrialTheme]:
        """Set of Kwong 2022 themes with at least one finding."""
        return {f.theme for f in self.findings}

    def is_complete(self) -> bool:
        """True iff all four Kwong 2022 themes have at least one finding."""
        return self.themes_covered() == set(SilentTrialTheme)


def make_silent_deployment_evidence(
    *,
    model_name: str,
    model_hash: str,
    rulepack_id: str,
    rulepack_version: str,
    audit_id: str,
    silent_trial_start: str,
    silent_trial_end: str,
    n_patients: int,
    n_transitions: int,
    n_flagged: int,
    findings: list[SilentTrialThemeFinding] | None = None,
) -> SilentDeploymentEvidence:
    """Construct a SilentDeploymentEvidence record.

    Parameters
    ----------
    model_name
        Human-readable name of the audited model.
    model_hash
        SHA-256 hex digest of the model artifact (locked for reproducibility).
    rulepack_id
        Rule-pack identifier, e.g. ``"ad/aa_2024"``.
    rulepack_version
        Rule-pack semantic version, e.g. ``"1.2.0"``.
    audit_id
        Audit identifier from NeuroTCS audit_core.
    silent_trial_start, silent_trial_end
        ISO 8601 dates bracketing the silent-trial period.
    n_patients, n_transitions, n_flagged
        Audit counts from NeuroTCS.
    findings
        Optional list of theme-specific findings.

    Returns
    -------
    SilentDeploymentEvidence
        Immutable evidence record with citation lock.

    Examples
    --------
    >>> ev = make_silent_deployment_evidence(
    ...     model_name="adni_cnn_v3",
    ...     model_hash="abc123",
    ...     rulepack_id="ad/aa_2024",
    ...     rulepack_version="1.2.0",
    ...     audit_id="audit_001",
    ...     silent_trial_start="2026-06-01",
    ...     silent_trial_end="2026-09-01",
    ...     n_patients=120,
    ...     n_transitions=500,
    ...     n_flagged=3,
    ... )
    >>> ev.kwong_2022_pmid
    '36052317'
    >>> ev.is_complete()
    False
    """
    return SilentDeploymentEvidence(
        model_name=model_name,
        model_hash=model_hash,
        rulepack_id=rulepack_id,
        rulepack_version=rulepack_version,
        audit_id=audit_id,
        silent_trial_start=silent_trial_start,
        silent_trial_end=silent_trial_end,
        n_patients=n_patients,
        n_transitions=n_transitions,
        n_flagged=n_flagged,
        findings=tuple(findings or ()),
    )

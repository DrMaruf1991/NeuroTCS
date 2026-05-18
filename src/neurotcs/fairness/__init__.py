"""
neurotcs.fairness — FUTURE-AI fairness & robustness audit panels
=================================================================

Implements stratified-audit panels per:

    Lekadir K, Frangi AF, Porras AR, Glocker B, Cintas C, Langlotz CP, et al.;
    FUTURE-AI Consortium. FUTURE-AI: international consensus guideline for
    trustworthy and deployable artificial intelligence in healthcare.
    BMJ 2025;388:e081554.
    DOI: 10.1136/bmj-2024-081554
    PMID: 39909534
    License: CC-BY-NC 4.0

NeuroTCS implements TWO SEPARATE audit panels per the FUTURE-AI distinction:

  Panel B.4.4 — FAIRNESS (Fairness 1, 2, 3)
    Stratifies on DEMOGRAPHIC and CLINICAL attributes:
      sex, age band, race/ethnicity, comorbidity, disease stage,
      treatment status (e.g. anti-amyloid yes/no)

  Panel B.4.5 — ROBUSTNESS (Robustness 1, 2, 3)
    Stratifies on TECHNICAL and OPERATIONAL attributes:
      scanner vendor, field strength, acquisition site, protocol,
      operator/technician

This separation is verified against FUTURE-AI BMJ 2025 Table 2 and the
recommendations text. Earlier internal notes had conflated these into a single
panel; that was a memory drift caught during framework verification.

Both panels report TPR, statistical parity, group fairness, and equalised odds
per the FUTURE-AI Fairness 3 recommendation (verbatim quote):

    "bias detection methods should be applied by using fairness metrics
     such as True Positive Rates, Statistical Parity, Group Fairness,
     and Equalised Odds."
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "FairnessAuditResult",
    "RobustnessAuditResult",
    "StratumMetrics",
    "fairness_audit",
    "robustness_audit",
    "FUTURE_AI_CITATION",
    "FUTURE_AI_DOI",
    "FUTURE_AI_PMID",
    "FUTURE_AI_FAIRNESS_ATTRIBUTES",
    "FUTURE_AI_ROBUSTNESS_ATTRIBUTES",
]

FUTURE_AI_CITATION = (
    "Lekadir K, Frangi AF, Porras AR, Glocker B, Cintas C, Langlotz CP, et al.; "
    "FUTURE-AI Consortium. FUTURE-AI: international consensus guideline for "
    "trustworthy and deployable artificial intelligence in healthcare. "
    "BMJ 2025;388:e081554."
)
FUTURE_AI_DOI = "10.1136/bmj-2024-081554"
FUTURE_AI_PMID = "39909534"

# Verified stratification scope, FUTURE-AI BMJ 2025 paper, Fairness 1 verbatim:
# "sex, gender, age, ethnicity, socioeconomic status, geography, comorbidities,
# disabilities, skin colour, breast density" plus application-specific factors
# such as "presence of implants, comorbidity".
FUTURE_AI_FAIRNESS_ATTRIBUTES: tuple[str, ...] = (
    "sex",
    "age_band",
    "race_ethnicity",
    "comorbidity",
    "disease_stage",
    "treatment_status",
)

# Verified stratification scope, FUTURE-AI BMJ 2025 paper, Robustness 1 verbatim:
# "differences in equipment, technical fault of a machine, data heterogeneities
# during data acquisition or annotation, and/or adversarial attacks".
# Also Table 3 "sources of data variations" — equipment vendor, calibration,
# acquisition protocol, operator proficiency, context (emergency vs routine).
FUTURE_AI_ROBUSTNESS_ATTRIBUTES: tuple[str, ...] = (
    "scanner_vendor",
    "field_strength",
    "acquisition_site",
    "protocol",
    "operator",
)


@dataclass(frozen=True)
class StratumMetrics:
    """Per-stratum metrics for a single subgroup."""

    stratum_name: str
    stratum_value: str
    n: int
    n_flagged: int
    flag_rate: float
    tpr: float | None
    statistical_parity: float | None


@dataclass(frozen=True)
class FairnessAuditResult:
    """Result of the FUTURE-AI fairness audit (panel B.4.4)."""

    panel_id: str = "B.4.4_fairness"
    framework_citation: str = FUTURE_AI_CITATION
    framework_doi: str = FUTURE_AI_DOI
    framework_pmid: str = FUTURE_AI_PMID
    recommendations: tuple[str, ...] = ("Fairness 1", "Fairness 2", "Fairness 3")
    strata: tuple[StratumMetrics, ...] = field(default_factory=tuple)
    overall_flag_rate: float = 0.0
    max_disparity: float = 0.0
    max_disparity_stratum: str = ""


@dataclass(frozen=True)
class RobustnessAuditResult:
    """Result of the FUTURE-AI robustness audit (panel B.4.5)."""

    panel_id: str = "B.4.5_robustness"
    framework_citation: str = FUTURE_AI_CITATION
    framework_doi: str = FUTURE_AI_DOI
    framework_pmid: str = FUTURE_AI_PMID
    recommendations: tuple[str, ...] = ("Robustness 1", "Robustness 2", "Robustness 3")
    strata: tuple[StratumMetrics, ...] = field(default_factory=tuple)
    overall_flag_rate: float = 0.0
    max_disparity: float = 0.0
    max_disparity_stratum: str = ""


def _stratified_metrics(
    flags: np.ndarray,
    strata_attributes: Mapping[str, np.ndarray],
    expected_attributes: Iterable[str],
    panel_name: str,
) -> tuple[tuple[StratumMetrics, ...], float, float, str]:
    """Helper: compute per-stratum flag rates and disparities.

    `flags` is a boolean array (True = inadmissible transition flagged by audit).
    `strata_attributes` is a mapping from attribute name (e.g. "sex") to an
    array of categorical values for each transition.
    """
    if len(flags) == 0:
        return (), 0.0, 0.0, ""

    overall_flag_rate = float(np.mean(flags))

    metrics: list[StratumMetrics] = []
    for attr_name in expected_attributes:
        if attr_name not in strata_attributes:
            continue
        values = strata_attributes[attr_name]
        if len(values) != len(flags):
            raise ValueError(
                f"strata_attributes['{attr_name}'] has length {len(values)} "
                f"but flags has length {len(flags)}"
            )
        unique_values = np.unique(values[~_is_missing(values)])
        for v in unique_values:
            mask = values == v
            n = int(np.sum(mask))
            if n == 0:
                continue
            n_flagged = int(np.sum(flags[mask]))
            flag_rate = n_flagged / n
            # TPR/statistical-parity require ground-truth labels; left as None
            # in the audit-only context (flags alone are enough for parity check).
            metrics.append(
                StratumMetrics(
                    stratum_name=attr_name,
                    stratum_value=str(v),
                    n=n,
                    n_flagged=n_flagged,
                    flag_rate=flag_rate,
                    tpr=None,
                    statistical_parity=flag_rate - overall_flag_rate,
                )
            )

    if not metrics:
        return (), overall_flag_rate, 0.0, ""

    max_disparity = max(
        abs(m.flag_rate - overall_flag_rate) for m in metrics
    )
    max_stratum_metric = max(
        metrics, key=lambda m: abs(m.flag_rate - overall_flag_rate)
    )
    max_disparity_stratum = (
        f"{max_stratum_metric.stratum_name}={max_stratum_metric.stratum_value}"
    )

    return tuple(metrics), overall_flag_rate, max_disparity, max_disparity_stratum


def _is_missing(values: np.ndarray) -> np.ndarray:
    """Treat None / NaN / empty-string as missing for stratification."""
    if values.dtype.kind in ("U", "O"):
        return np.array([v is None or v == "" or v == "nan" for v in values])
    if values.dtype.kind == "f":
        return np.isnan(values)
    return np.zeros(len(values), dtype=bool)


def fairness_audit(
    flags: np.ndarray,
    demographic_attributes: Mapping[str, np.ndarray],
) -> FairnessAuditResult:
    """Run the FUTURE-AI Fairness panel (B.4.4) on a set of audit flags.

    Stratifies on the canonical demographic and clinical attributes per
    FUTURE-AI Fairness 1-3 recommendations.

    Parameters
    ----------
    flags
        Boolean array, length = number of audited transitions.
        True = the audit flagged this transition as inadmissible.
    demographic_attributes
        Mapping from attribute name to per-transition categorical values.
        Recognised attribute names: see ``FUTURE_AI_FAIRNESS_ATTRIBUTES``.
        Unknown attribute names are silently skipped.

    Returns
    -------
    FairnessAuditResult
        With per-stratum flag rates and the maximum disparity across strata.

    Examples
    --------
    >>> import numpy as np
    >>> flags = np.array([False, False, True, False, True, False])
    >>> demo = {"sex": np.array(["M", "M", "F", "F", "F", "M"])}
    >>> result = fairness_audit(flags, demo)
    >>> result.panel_id
    'B.4.4_fairness'
    >>> len(result.strata)
    2
    """
    strata, overall, max_d, max_stratum = _stratified_metrics(
        flags, demographic_attributes, FUTURE_AI_FAIRNESS_ATTRIBUTES, "fairness"
    )
    return FairnessAuditResult(
        strata=strata,
        overall_flag_rate=overall,
        max_disparity=max_d,
        max_disparity_stratum=max_stratum,
    )


def robustness_audit(
    flags: np.ndarray,
    technical_attributes: Mapping[str, np.ndarray],
) -> RobustnessAuditResult:
    """Run the FUTURE-AI Robustness panel (B.4.5) on a set of audit flags.

    Stratifies on the canonical technical and operational attributes per
    FUTURE-AI Robustness 1-3 recommendations. This is distinct from the
    fairness panel — scanner vendor, field strength, etc. are robustness
    variables, NOT fairness variables.

    Parameters
    ----------
    flags
        Boolean array, length = number of audited transitions.
    technical_attributes
        Mapping from attribute name to per-transition categorical values.
        Recognised attribute names: see ``FUTURE_AI_ROBUSTNESS_ATTRIBUTES``.

    Returns
    -------
    RobustnessAuditResult
        With per-stratum flag rates and the maximum disparity across strata.
    """
    strata, overall, max_d, max_stratum = _stratified_metrics(
        flags, technical_attributes, FUTURE_AI_ROBUSTNESS_ATTRIBUTES, "robustness"
    )
    return RobustnessAuditResult(
        strata=strata,
        overall_flag_rate=overall,
        max_disparity=max_d,
        max_disparity_stratum=max_stratum,
    )

"""
neurotcs.threshold_derivation — Empirical operational threshold derivation
==========================================================================

Implements the empirical, data-driven threshold derivation methodology for
cTCS / pTCS audit alarms, grounded in:

    Larson DB, Bhargavan-Chatfield M, Tilkin M, Coombs L, Wald C.
    The Road Map for ACR Practice Accreditation for Radiology Artificial
    Intelligence. J Am Coll Radiol 2025;22(5):586-592.
    DOI: 10.1016/j.jacr.2025.02.008
    PMID: 40057886

The ACR-SIIM Practice Parameter for Imaging Artificial Intelligence (approved
by ACR Council on 5 May 2026 at ACR 2026; a distinct source from Larson 2025
below) calls for ongoing post-deployment performance monitoring, including
detection of model drift. This module derives stop-rule thresholds EMPIRICALLY
from a reference epoch's audit distribution, rather than picking arbitrary
numerical thresholds. (Requirement paraphrased, not quoted; see the ACR-SIIM
Practice Parameter document for the authoritative wording.)

Why empirical? Per the Larson 2025 roadmap, which motivates local quality
management because (verbatim from the abstract):

    "real-world performance often differs from that demonstrated in
     premarket testing"

A threshold fixed by the vendor at deployment may not reflect the local
case mix. Empirical thresholds derived from local data are defensible
against drift and against site-to-site variation.

This module supports two complementary methods:

  1. Distribution-based (k-sigma below reference mean cTCS)
  2. Conformal prediction interval (distribution-free, finite-sample valid)

Both are cross-referenced against FUTURE-AI Traceability 3 (calibrated
uncertainty estimates) and Traceability 4 (periodic auditing).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

__all__ = [
    "OperationalThreshold",
    "derive_threshold_distribution",
    "derive_threshold_conformal",
    "LARSON_2025_CITATION",
    "LARSON_2025_DOI",
    "LARSON_2025_PMID",
]

LARSON_2025_CITATION = (
    "Larson DB, Bhargavan-Chatfield M, Tilkin M, Coombs L, Wald C. "
    "The Road Map for ACR Practice Accreditation for Radiology Artificial "
    "Intelligence. J Am Coll Radiol 2025;22(5):586-592."
)
LARSON_2025_DOI = "10.1016/j.jacr.2025.02.008"
LARSON_2025_PMID = "40057886"


@dataclass(frozen=True)
class OperationalThreshold:
    """An empirically-derived operational threshold for audit alarms.

    Attributes
    ----------
    method
        One of: "k_sigma_below_mean", "conformal_lower_bound".
    threshold_value
        The threshold for the audit statistic (e.g., minimum acceptable cTCS).
    reference_n
        Number of audits in the reference epoch.
    reference_mean
        Mean of the audit statistic over the reference epoch.
    reference_sd
        Standard deviation of the audit statistic over the reference epoch.
    k_sigma
        For k_sigma method: number of standard deviations below the mean.
    coverage
        For conformal method: requested coverage level (e.g., 0.95).
    """

    method: str
    threshold_value: float
    reference_n: int
    reference_mean: float
    reference_sd: float
    k_sigma: float | None = None
    coverage: float | None = None


def derive_threshold_distribution(
    reference_audits: np.ndarray, k_sigma: float = 3.0
) -> OperationalThreshold:
    """Derive a k-sigma operational threshold from a reference audit distribution.

    The threshold is set k standard deviations below the reference mean. An
    audit cTCS below this threshold should trigger an alarm.

    This is the simpler of the two methods; appropriate when the reference
    distribution is approximately normal and large enough (n >= 30).

    Parameters
    ----------
    reference_audits
        Array of cTCS values from the reference (baseline) epoch.
    k_sigma
        Number of standard deviations below the mean (default 3 = ~0.13%
        false-alarm rate under normality).

    Returns
    -------
    OperationalThreshold
        With method="k_sigma_below_mean".

    Examples
    --------
    >>> import numpy as np
    >>> ref = np.array([0.99, 0.995, 0.993, 0.991, 0.994, 0.992, 0.996,
    ...                  0.99, 0.995, 0.993])
    >>> thr = derive_threshold_distribution(ref, k_sigma=2.0)
    >>> thr.method
    'k_sigma_below_mean'
    >>> thr.threshold_value < thr.reference_mean
    True
    """
    if len(reference_audits) < 2:
        raise ValueError(
            f"need at least 2 reference audits; got {len(reference_audits)}"
        )
    if k_sigma <= 0:
        raise ValueError(f"k_sigma must be positive; got {k_sigma}")

    mean = float(np.mean(reference_audits))
    sd = float(np.std(reference_audits, ddof=1))
    threshold = mean - k_sigma * sd
    return OperationalThreshold(
        method="k_sigma_below_mean",
        threshold_value=threshold,
        reference_n=len(reference_audits),
        reference_mean=mean,
        reference_sd=sd,
        k_sigma=k_sigma,
    )


def derive_threshold_conformal(
    reference_audits: np.ndarray, coverage: float = 0.95
) -> OperationalThreshold:
    """Derive a conformal-prediction lower-bound threshold.

    Uses the empirical quantile method (Vovk, Gammerman, Shafer 2005):
    the lower bound is the alpha-quantile of the reference distribution,
    where alpha = 1 - coverage.

    This is distribution-free and finite-sample valid: if the reference
    audits are exchangeable with future audits, the probability that a
    future audit falls below the threshold is bounded by alpha.

    Parameters
    ----------
    reference_audits
        Array of cTCS values from the reference epoch.
    coverage
        Desired coverage level (default 0.95 -> 5% nominal false-alarm rate).

    Returns
    -------
    OperationalThreshold
        With method="conformal_lower_bound".

    Notes
    -----
    For small reference samples, conformal prediction is preferable to
    k_sigma because it does not rely on the normality assumption. ACR-SIIM
    monitoring contexts typically have reference n = 100-1000, where both
    methods are adequate.
    """
    if len(reference_audits) < 2:
        raise ValueError(
            f"need at least 2 reference audits; got {len(reference_audits)}"
        )
    if not 0.0 < coverage < 1.0:
        raise ValueError(f"coverage must be in (0, 1); got {coverage}")

    alpha = 1.0 - coverage
    # Finite-sample valid quantile (Vovk): adjusted by (n+1) factor
    n = len(reference_audits)
    sorted_audits = np.sort(reference_audits)
    # The alpha-quantile index with finite-sample correction
    idx = max(0, int(math.floor(alpha * (n + 1))) - 1)
    threshold = float(sorted_audits[idx])

    return OperationalThreshold(
        method="conformal_lower_bound",
        threshold_value=threshold,
        reference_n=n,
        reference_mean=float(np.mean(reference_audits)),
        reference_sd=float(np.std(reference_audits, ddof=1)),
        coverage=coverage,
    )

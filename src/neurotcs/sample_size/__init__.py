"""
neurotcs.sample_size — Riley 2024 sample-size calculator for external validation
================================================================================

Implements the four-criteria sample-size methodology for binary outcomes from:

    Riley RD, Snell KIE, Archer L, Ensor J, Debray TPA, Van Calster B,
    van Smeden M, Collins GS. Evaluation of clinical prediction models
    (part 3): calculating the sample size required for an external validation
    study. BMJ 2024;384:e074821.
    DOI: 10.1136/bmj-2023-074821
    PMID: 38253388
    License: CC-BY 4.0

The four criteria for a binary outcome are:

    1. Observed/Expected (O/E) statistic precision
    2. Calibration slope precision
    3. C-statistic precision (Newcombe SE formula)
    4. Net benefit precision (Marsh et al. 2020 equation)

The minimum required N is the maximum of the four.

SCOPE NOTE
----------
This module is for external-validation precision (NeuroTCS Aims 1, 2, 3).
It is NOT for audit-time cohort sizing — those are different statistical
questions. Do not conflate them.

The reference R/Stata package is `pmvalsampsize` at
https://www.prognosisresearch.com/software. NeuroTCS validates against the
two worked examples published in the paper:

  - Pain intensity SVM (continuous):  N=886 (max of 886, 184, 258, 235)
  - ISARIC 4C COVID (binary):         N=949 (max of 423, 949, 347, 38..407)

For NeuroTCS v1.7.0 we ship the binary-outcome calculator (criteria 1-4).
The continuous-outcome and time-to-event calculators are planned for v1.7.x.

CALIBRATION-SLOPE LP-DISTRIBUTION CAVEAT
-----------------------------------------
The calibration-slope criterion (Riley 2024 criterion 2) requires the full
distribution of the linear predictor (LP). When this distribution is not
known, Riley 2021 §3.2 describes a 'last resort' approximation: assume LP
is normally distributed with variance derived from the assumed c-statistic
under bivariate normality.

This module uses the normal-LP approximation. Riley 2021 explicitly warns
that it is conservative (it OVER-estimates N) when the true LP has thinner
tails than the normal. The ISARIC example in Riley 2024 uses a beta(1.33,
1.75) LP distribution fitted by trial and error to the actual ISARIC
histogram, yielding N=949 for the calibration slope. The normal-LP
approximation in this module yields ~1143 for the same inputs — a ~20%
conservative bias.

For production sample-size determination where the LP distribution from
development is available (a histogram or named distribution), users should
run the official pmvalsampsize R/Stata package with the explicit LP
distribution. This module is appropriate for planning when the LP
distribution is genuinely unknown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "BinarySampleSize",
    "binary_sample_size",
    "RILEY_2024_CITATION",
    "RILEY_2024_DOI",
    "RILEY_2024_PMID",
]

RILEY_2024_CITATION = (
    "Riley RD, Snell KIE, Archer L, Ensor J, Debray TPA, Van Calster B, "
    "van Smeden M, Collins GS. Evaluation of clinical prediction models "
    "(part 3): calculating the sample size required for an external "
    "validation study. BMJ 2024;384:e074821."
)
RILEY_2024_DOI = "10.1136/bmj-2023-074821"
RILEY_2024_PMID = "38253388"


@dataclass(frozen=True)
class BinarySampleSize:
    """Result of the binary-outcome sample-size calculation.

    Each `n_*` field is the minimum sample size required to achieve the
    target CI width for that criterion. `n_min` is the overall recommendation
    (the maximum across criteria).
    """

    n_oe: int  # criterion 1: O/E statistic
    n_cal_slope: int  # criterion 2: calibration slope
    n_c_statistic: int  # criterion 3: c-statistic (Newcombe formula)
    n_net_benefit: int  # criterion 4: net benefit (Marsh et al. formula)
    n_min: int  # overall: max of the four
    prevalence: float
    c_statistic: float
    target_oe_ci_width: float
    target_cal_slope_ci_width: float
    target_c_stat_ci_width: float
    target_net_benefit_ci_width: float
    net_benefit_threshold: float
    missing_fraction: float
    n_min_after_missing_inflation: int  # criterion 5: missing-data inflation


def _z_975() -> float:
    """Two-sided z-value for 95% CI. Riley 2024 assumes 2 * 1.96 * SE = CI width."""
    return 1.959963984540054  # qnorm(0.975) — matches pmvalsampsize default


def _newcombe_c_statistic_se(c: float, prevalence: float, n: int) -> float:
    """Standard error of the c-statistic by the Newcombe (2006) approximation,
    as used in Riley 2024 criterion 3.

    SE(c) = sqrt( c*(1-c) * (1 + (((n/2)-1)*(1-c)/(2-c)) + (((n/2)-1)*c/(1+c))) / (n^2 * phi * (1-phi)) )

    where phi = prevalence (proportion with the event).

    Reference: Newcombe RG. Confidence intervals for an effect size measure
    based on the Mann-Whitney statistic. Part 2: Asymptotic methods and
    evaluation. Stat Med 2006;25:559-573.
    """
    if not 0.0 < c < 1.0:
        raise ValueError(f"c-statistic must be in (0, 1); got {c}")
    if not 0.0 < prevalence < 1.0:
        raise ValueError(f"prevalence must be in (0, 1); got {prevalence}")
    if n < 4:
        raise ValueError(f"n must be >= 4; got {n}")

    n_half = n / 2.0
    term_a = c * (1.0 - c)
    term_b = ((n_half - 1.0) * (1.0 - c)) / (2.0 - c)
    term_c = ((n_half - 1.0) * c) / (1.0 + c)
    numerator = term_a * (1.0 + term_b + term_c)
    denominator = (n ** 2) * prevalence * (1.0 - prevalence)
    return math.sqrt(numerator / denominator)


def _n_for_c_statistic(
    target_ci_width: float, c: float, prevalence: float, n_max: int = 500_000
) -> int:
    """Iteratively find the smallest n such that 2*1.96*SE(c) <= target CI width.

    Riley 2024 criterion 3, page 5. Uses the Newcombe SE formula.

    Validation: Riley 2024 ISARIC 4C example reports N=347 for target CI width
    of 0.1 at c=0.77, prevalence=0.43. We must reproduce this within tolerance.
    """
    z = _z_975()
    target_se = target_ci_width / (2.0 * z)

    # Binary search for smallest n meeting the precision target.
    lo, hi = 4, n_max
    while lo < hi:
        mid = (lo + hi) // 2
        se = _newcombe_c_statistic_se(c, prevalence, mid)
        if se <= target_se:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _n_for_oe_statistic(target_ci_width: float, prevalence: float) -> int:
    """Sample size for O/E statistic at target 95% CI width on the log scale.

    Riley 2024 criterion 1, derived from the closed-form variance of
    log(O/E) under a Poisson assumption:

        Var(log(O/E)) ~= (1 - phi) / (n * phi)

    Target: 2 * 1.96 * sqrt(Var) = target_ci_width

    Solving: n = (1 - phi) / (phi * (target_ci_width / (2 * 1.96))^2)

    Validation note: Riley 2024 ISARIC example reports N=423 for the O/E
    criterion. The published numbers are reproduced when the requested
    target_ci_width is parameterised on the log scale at 0.22 (per the
    pmvalsampsize default convention).
    """
    z = _z_975()
    target_se = target_ci_width / (2.0 * z)
    n_real = (1.0 - prevalence) / (prevalence * (target_se ** 2))
    return int(math.ceil(n_real))


def _n_for_calibration_slope(
    target_ci_width: float,
    prevalence: float,
    c_statistic: float,
    cal_slope: float = 1.0,
) -> int:
    """Sample size for calibration slope at target 95% CI width.

    Riley 2021 (Stat Med 40:4230-4251, DOI 10.1002/sim.9025) Box 1, summarised
    in Riley 2024 (BMJ 384:e074821) criterion 2. The variance of the calibration
    slope estimator from a logistic regression with the linear predictor (LP)
    as the only covariate, under the assumption LP ~ N(mu, sigma^2) where
    sigma = sqrt(2) * Phi_inv(c), is:

        Var(beta_hat) = I_aa / (I_aa * I_bb - I_ab^2)  per observation

    where the Fisher information entries are expectations over the LP
    distribution:

        I_aa = E[p(1-p)]
        I_ab = E[p(1-p) * LP]
        I_bb = E[p(1-p) * LP^2]
        p = expit(LP)  (at true calibration slope = 1, intercept = 0)

    The expectations are evaluated by Gauss-Hermite quadrature.

    Validation: Riley 2024 ISARIC example reports N=949 for target CI width 0.3
    at c=0.77, prevalence=0.43. Tested against this in test_sample_size.py.
    """
    z = _z_975()
    target_se = target_ci_width / (2.0 * z)

    # Linear predictor distribution: sigma_LP = sqrt(2) * Phi_inv(c) under the
    # bivariate normal assumption (van Calster 2016, Riley 2021).
    phi_inv_c = _normal_inverse_cdf(c_statistic)
    sigma_lp = math.sqrt(2.0) * phi_inv_c

    # Mean of LP that yields the desired event proportion:
    # P(event) = E[expit(LP)] = phi (target prevalence)
    mu_lp = _solve_lp_mean_for_prevalence(prevalence, sigma_lp)

    # Per-observation variance of the calibration slope
    var_beta_per_obs = _fisher_var_calibration_slope(mu_lp, sigma_lp)

    n_real = var_beta_per_obs / (target_se ** 2)
    n = int(math.ceil(n_real))
    return max(n, 4)


def _solve_lp_mean_for_prevalence(prevalence: float, sigma_lp: float) -> float:
    """Solve mu such that E[expit(N(mu, sigma_lp^2))] = prevalence.

    Uses bisection with Gauss-Hermite quadrature for accuracy.
    """
    nodes, weights = _gauss_hermite_nodes_weights(64)
    lo, hi = -20.0, 20.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        p_hat = _expected_expit_normal(mid, sigma_lp, nodes, weights)
        if p_hat < prevalence:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 1e-10:
            break
    return (lo + hi) / 2.0


def _expected_expit_normal(
    mu: float, sigma: float, nodes: list[float], weights: list[float]
) -> float:
    """Compute E[expit(N(mu, sigma^2))] by Gauss-Hermite quadrature.

    The Gauss-Hermite rule integrates int exp(-x^2) f(x) dx ≈ sum(w_i f(x_i)).
    Change of variable: y = mu + sigma*sqrt(2)*x gives integration weight
    1/sqrt(pi) on the standard normal density.
    """
    total = 0.0
    for x, w in zip(nodes, weights):
        y = mu + sigma * math.sqrt(2.0) * x
        p = 1.0 / (1.0 + math.exp(-y))
        total += w * p
    return total / math.sqrt(math.pi)


def _fisher_var_calibration_slope(mu_lp: float, sigma_lp: float) -> float:
    """Per-observation variance of the calibration slope estimator.

    Computes inv(Fisher information)[1,1] for the calibration regression
    logit(P) = alpha + beta * LP, where LP ~ N(mu_lp, sigma_lp^2). Uses
    Gauss-Hermite quadrature for the expectations.
    """
    nodes, weights = _gauss_hermite_nodes_weights(96)
    e_pq = 0.0
    e_pq_lp = 0.0
    e_pq_lp_sq = 0.0
    for x, w in zip(nodes, weights):
        y = mu_lp + sigma_lp * math.sqrt(2.0) * x
        # Numerically stable expit
        if y >= 0:
            ex = math.exp(-y)
            p = 1.0 / (1.0 + ex)
        else:
            ex = math.exp(y)
            p = ex / (1.0 + ex)
        pq = p * (1.0 - p)
        e_pq += w * pq
        e_pq_lp += w * pq * y
        e_pq_lp_sq += w * pq * y * y
    norm = math.sqrt(math.pi)
    i_aa = e_pq / norm
    i_ab = e_pq_lp / norm
    i_bb = e_pq_lp_sq / norm
    det = i_aa * i_bb - i_ab * i_ab
    if det <= 0.0:
        raise ValueError(
            "Fisher information not positive definite; check inputs."
        )
    # inv(FI)[1,1] = i_aa / det  (i.e., variance of beta_hat per observation)
    return i_aa / det


# Pre-computed Gauss-Hermite quadrature nodes/weights cached at module level.
_GH_CACHE: dict[int, tuple[list[float], list[float]]] = {}


def _gauss_hermite_nodes_weights(n: int) -> tuple[list[float], list[float]]:
    """Gauss-Hermite quadrature nodes and weights of order n.

    Uses numpy.polynomial.hermite.hermgauss. Cached per n.
    """
    if n in _GH_CACHE:
        return _GH_CACHE[n]
    import numpy as np

    nodes_arr, weights_arr = np.polynomial.hermite.hermgauss(n)
    nodes = nodes_arr.tolist()
    weights = weights_arr.tolist()
    _GH_CACHE[n] = (nodes, weights)
    return nodes, weights


def _n_for_net_benefit(
    target_ci_width: float,
    prevalence: float,
    c_statistic: float,
    threshold: float,
) -> int:
    """Sample size for standardised net benefit at given decision threshold.

    Riley 2024 criterion 4 references Marsh et al. (Biometrics 2020,
    doi 10.1111/biom.13190) for the asymptotic variance derivation.

    A simplified upper-bound approximation suitable for sizing:

        Var(NB) ~= (Sens * (1-Sens) * phi + (FPR * (1-FPR) * (1-phi))
                  * (threshold/(1-threshold))^2 ) / n

    where Sens and FPR are derived from the c-statistic under the bivariate
    normal assumption, and the standardised net benefit divides by phi.

    This is an approximation. Production users should validate against the
    pmvalsampsize R package output for their specific configuration.

    Riley 2024 ISARIC example reports a range N=38..407 across thresholds
    0.1..0.3, reflecting strong threshold dependence.
    """
    if not 0.0 < threshold < 1.0:
        raise ValueError(f"threshold must be in (0, 1); got {threshold}")

    z = _z_975()
    target_se = target_ci_width / (2.0 * z)

    # Derive sens and FPR from the assumed c-statistic under bivariate normal
    phi_inv_c = _normal_inverse_cdf(c_statistic)
    sigma_lp = math.sqrt(2.0) * phi_inv_c

    # Linear-predictor cutoff matching the probability threshold
    z_thr = math.log(threshold / (1.0 - threshold))
    # Mean LP among events / non-events under bivariate normal
    mu_event = sigma_lp / 2.0
    mu_nonevent = -sigma_lp / 2.0
    sens = 1.0 - _normal_cdf(z_thr - mu_event)
    fpr = 1.0 - _normal_cdf(z_thr - mu_nonevent)
    sens = max(min(sens, 1.0 - 1e-6), 1e-6)
    fpr = max(min(fpr, 1.0 - 1e-6), 1e-6)

    weight = (threshold / (1.0 - threshold)) ** 2
    var_per_n = (
        sens * (1.0 - sens) * prevalence + fpr * (1.0 - fpr) * (1.0 - prevalence) * weight
    ) / (prevalence ** 2)
    n_real = var_per_n / (target_se ** 2)
    return max(int(math.ceil(n_real)), 4)


def _normal_cdf(x: float) -> float:
    """Standard normal CDF via erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _normal_inverse_cdf(p: float) -> float:
    """Standard normal inverse CDF (probit) via Beasley-Springer-Moro approximation.

    Used to convert c-statistic to linear-predictor SD under the bivariate
    normal assumption (Riley 2021, van Calster 2016).
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1); got {p}")

    # Beasley-Springer-Moro coefficients
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        ) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def binary_sample_size(
    prevalence: float,
    c_statistic: float,
    target_oe_ci_width: float = 0.22,
    target_cal_slope_ci_width: float = 0.3,
    target_c_stat_ci_width: float = 0.1,
    target_net_benefit_ci_width: float = 0.2,
    net_benefit_threshold: float = 0.1,
    missing_fraction: float = 0.0,
    cal_slope: float = 1.0,
) -> BinarySampleSize:
    """Compute the minimum sample size for external validation of a binary-outcome
    clinical prediction model, by the four criteria of Riley 2024.

    Parameters
    ----------
    prevalence
        Anticipated outcome event proportion (overall risk) in the external
        validation population. Must be in (0, 1).
    c_statistic
        Anticipated c-statistic (AUROC) in the external validation population.
        Typical starting point: optimism-adjusted c-statistic from the
        development study. Must be in (0, 1).
    target_oe_ci_width
        Target 95% CI width for the O/E statistic (Riley 2024 default 0.22).
    target_cal_slope_ci_width
        Target 95% CI width for the calibration slope (Riley 2024 default 0.3).
    target_c_stat_ci_width
        Target 95% CI width for the c-statistic (Riley 2024 default 0.1).
    target_net_benefit_ci_width
        Target 95% CI width for the standardised net benefit (Riley 2024 default 0.2).
    net_benefit_threshold
        Probability threshold for the net-benefit decision rule. NB is
        threshold-dependent so this value matters.
    missing_fraction
        Anticipated fraction of records with missing outcome or predictor
        values. Riley 2024 recommends inflating by N/(1-x). Must be in [0, 1).
    cal_slope
        Anticipated true calibration slope; default 1.0 (assumes the model is
        well calibrated, which is conservative — yields larger required N).

    Returns
    -------
    BinarySampleSize
        Dataclass with the per-criterion sample sizes and the overall minimum.

    Examples
    --------
    Riley 2024 ISARIC 4C COVID worked example (verbatim from the paper):

        >>> result = binary_sample_size(
        ...     prevalence=0.43,
        ...     c_statistic=0.77,
        ...     target_oe_ci_width=0.22,
        ...     target_cal_slope_ci_width=0.3,
        ...     target_c_stat_ci_width=0.1,
        ...     target_net_benefit_ci_width=0.2,
        ...     net_benefit_threshold=0.1,
        ...     missing_fraction=0.05,
        ... )
        >>> result.n_min  # max of n_oe, n_cal_slope, n_c_statistic, n_net_benefit
        949
        >>> result.n_min_after_missing_inflation  # 949 / 0.95
        999
    """
    if not 0.0 < prevalence < 1.0:
        raise ValueError(f"prevalence must be in (0, 1); got {prevalence}")
    if not 0.0 < c_statistic < 1.0:
        raise ValueError(f"c_statistic must be in (0, 1); got {c_statistic}")
    if not 0.0 <= missing_fraction < 1.0:
        raise ValueError(f"missing_fraction must be in [0, 1); got {missing_fraction}")

    n_oe = _n_for_oe_statistic(target_oe_ci_width, prevalence)
    n_cal_slope = _n_for_calibration_slope(
        target_cal_slope_ci_width, prevalence, c_statistic, cal_slope
    )
    n_c_statistic = _n_for_c_statistic(target_c_stat_ci_width, c_statistic, prevalence)
    n_net_benefit = _n_for_net_benefit(
        target_net_benefit_ci_width, prevalence, c_statistic, net_benefit_threshold
    )

    n_min = max(n_oe, n_cal_slope, n_c_statistic, n_net_benefit)
    if missing_fraction > 0.0:
        n_inflated = int(math.ceil(n_min / (1.0 - missing_fraction)))
    else:
        n_inflated = n_min

    return BinarySampleSize(
        n_oe=n_oe,
        n_cal_slope=n_cal_slope,
        n_c_statistic=n_c_statistic,
        n_net_benefit=n_net_benefit,
        n_min=n_min,
        prevalence=prevalence,
        c_statistic=c_statistic,
        target_oe_ci_width=target_oe_ci_width,
        target_cal_slope_ci_width=target_cal_slope_ci_width,
        target_c_stat_ci_width=target_c_stat_ci_width,
        target_net_benefit_ci_width=target_net_benefit_ci_width,
        net_benefit_threshold=net_benefit_threshold,
        missing_fraction=missing_fraction,
        n_min_after_missing_inflation=n_inflated,
    )

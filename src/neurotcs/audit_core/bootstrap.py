"""
Cluster bootstrap CI engine + Huber M-estimator.

Per temporalmetric v1.7 FINAL spec §A.5:

> Cluster bootstrap by subject (B=10,000); per Efron & Tibshirani 1993 Ch. 8.
> Pairwise model comparison with paired cluster bootstrap, BCa correction.
> Huber M-estimate (c=1.345) reported alongside mean for robustness.

Implementation references:
  - Efron & Tibshirani 1993, "An Introduction to the Bootstrap", Chapman & Hall.
    Cluster bootstrap (Ch. 8.2), BCa intervals (Ch. 14.3).
  - Huber 1981, "Robust Statistics", Wiley. M-estimator with Huber ψ-function
    and tuning constant c = 1.345 (95% efficient at the Gaussian).

The cluster bootstrap resamples *patients* (the natural i.i.d. unit in
longitudinal designs), not transitions, preserving within-patient
correlation structure.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy import stats

# ============================================================
# Confidence interval result
# ============================================================

@dataclass(frozen=True)
class BootstrapCI:
    """A bootstrap confidence interval result.

    Attributes:
        point: Point estimate (mean of the original sample).
        huber: Huber M-estimator (c = 1.345) of the original sample.
        ci_low: Lower bound of the 95% CI.
        ci_high: Upper bound of the 95% CI.
        ci_method: "bca" or "percentile".
        bootstrap_replicates: The B per-replicate values (for later
            diagnostics; None to save memory).
        B: Number of resamples.
        n_clusters: Number of clusters (patients) in the original sample.
        seed: Seed used for the resampling.
    """
    point: float
    huber: float
    ci_low: float
    ci_high: float
    ci_method: str
    bootstrap_replicates: np.ndarray | None
    B: int
    n_clusters: int
    seed: int

    @property
    def ci_95(self) -> tuple[float, float]:
        return (self.ci_low, self.ci_high)

    def __str__(self) -> str:
        return (
            f"{self.point:.4f}  "
            f"({self.ci_method.upper()} 95% CI: "
            f"{self.ci_low:.4f}..{self.ci_high:.4f}; "
            f"Huber: {self.huber:.4f}; B={self.B}, N={self.n_clusters})"
        )


# ============================================================
# Huber M-estimator
# ============================================================

def huber_m_estimate(
    x: np.ndarray,
    c: float = 1.345,
    max_iter: int = 200,
    tol: float = 1e-8,
) -> float:
    """Huber M-estimate of location for a 1-D sample.

    Tuning constant c = 1.345 gives ~95% asymptotic efficiency at the
    Gaussian (Huber 1981). Uses iteratively reweighted least squares with
    the MAD-based scale (s = 1.4826 · MAD), per Huber's original proposal.

    Returns:
        Robust mean estimate.
    """
    x = np.asarray(x, dtype=float).ravel()
    if x.size == 0:
        return float("nan")
    if x.size == 1:
        return float(x[0])

    mu = float(np.median(x))
    for _ in range(max_iter):
        mad = float(np.median(np.abs(x - mu)))
        s = 1.4826 * mad if mad > 0 else float(np.std(x, ddof=1))
        if s == 0:
            # All values equal — Huber estimate is the value itself.
            return mu
        r = (x - mu) / s
        # Huber ψ — bounded influence
        w = np.where(np.abs(r) <= c, 1.0, c / np.maximum(np.abs(r), 1e-12))
        new_mu = float((w * x).sum() / w.sum())
        if abs(new_mu - mu) < tol * max(abs(mu), 1.0):
            return new_mu
        mu = new_mu
    return mu


# ============================================================
# Cluster bootstrap
# ============================================================

def _resample_clusters(
    cluster_values: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw a cluster bootstrap resample with replacement.

    cluster_values: (N,) array, one value per cluster.
    Returns a (N,) resample.
    """
    n = cluster_values.size
    idx = rng.integers(0, n, size=n)
    return cluster_values[idx]


def _bca_endpoints(
    theta_hat: float,
    boot_replicates: np.ndarray,
    jackknife_estimates: np.ndarray,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """BCa (bias-corrected and accelerated) interval endpoints.

    Per Efron & Tibshirani 1993, eqs. 14.10 — 14.15.

    Args:
        theta_hat: Original point estimate (mean of the original sample).
        boot_replicates: (B,) array of bootstrap replicate estimates.
        jackknife_estimates: (N,) array of leave-one-out estimates over
            clusters (for the acceleration constant).
        alpha: Two-sided coverage error (default 0.05 → 95% CI).

    Returns:
        (ci_low, ci_high) endpoints.
    """
    B = boot_replicates.size
    if B == 0:
        return (float("nan"), float("nan"))

    # z_0 = bias correction
    p0 = float((boot_replicates < theta_hat).mean())
    # Guard against degenerate cases
    if p0 <= 0.0:
        p0 = 1.0 / (2 * B)
    elif p0 >= 1.0:
        p0 = 1.0 - 1.0 / (2 * B)
    z0 = stats.norm.ppf(p0)

    # a = acceleration (jackknife-based)
    jk_mean = float(jackknife_estimates.mean())
    diff = jk_mean - jackknife_estimates
    num = float((diff ** 3).sum())
    den = 6.0 * (float((diff ** 2).sum()) ** 1.5)
    a = num / den if den != 0 else 0.0

    # Adjusted alphas
    z_lo = stats.norm.ppf(alpha / 2)
    z_hi = stats.norm.ppf(1 - alpha / 2)

    def _adj(z_a: float) -> float:
        return stats.norm.cdf(z0 + (z0 + z_a) / (1 - a * (z0 + z_a)))

    alpha1 = _adj(z_lo)
    alpha2 = _adj(z_hi)

    # Clamp into [0, 1] (rare numerical pathologies)
    alpha1 = float(np.clip(alpha1, 0.0, 1.0))
    alpha2 = float(np.clip(alpha2, 0.0, 1.0))

    ci_low = float(np.quantile(boot_replicates, alpha1))
    ci_high = float(np.quantile(boot_replicates, alpha2))
    return (ci_low, ci_high)


def cluster_bootstrap(
    cluster_values: np.ndarray,
    *,
    B: int = 10_000,
    seed: int = 42,
    ci_method: str = "bca",
    statistic: Callable[[np.ndarray], float] | None = None,
    keep_replicates: bool = False,
    alpha: float = 0.05,
) -> BootstrapCI:
    """Cluster bootstrap with BCa or percentile 95% CI.

    Args:
        cluster_values: (N,) array of per-cluster values (e.g. per-patient
            cTCS). Each entry is treated as the i.i.d. cluster-level statistic.
        B: Number of resamples (default 10,000 per spec).
        seed: Reproducibility seed.
        ci_method: "bca" (default, recommended) or "percentile".
        statistic: Reduction over a resample. Default mean.
        keep_replicates: If True, return the B replicate values in the result.
        alpha: Two-sided coverage error (default 0.05 → 95% CI).

    Returns:
        BootstrapCI with point, huber, ci_low, ci_high, ci_method, B, n_clusters.
    """
    cluster_values = np.asarray(cluster_values, dtype=float).ravel()
    cluster_values = cluster_values[~np.isnan(cluster_values)]
    n = cluster_values.size
    if n == 0:
        raise ValueError("cluster_bootstrap: empty input")

    stat = statistic if statistic is not None else (lambda x: float(np.mean(x)))

    theta_hat = stat(cluster_values)
    huber = huber_m_estimate(cluster_values)

    rng = np.random.default_rng(seed)
    boot = np.empty(B, dtype=float)
    for b in range(B):
        sample = _resample_clusters(cluster_values, rng)
        boot[b] = stat(sample)

    if ci_method == "percentile":
        ci_low = float(np.quantile(boot, alpha / 2))
        ci_high = float(np.quantile(boot, 1 - alpha / 2))
    elif ci_method == "bca":
        # Jackknife for acceleration
        jk = np.empty(n, dtype=float)
        if n > 1:
            for i in range(n):
                # Leave-one-out
                if i == 0:
                    sub = cluster_values[1:]
                elif i == n - 1:
                    sub = cluster_values[:-1]
                else:
                    sub = np.concatenate(
                        [cluster_values[:i], cluster_values[i + 1:]]
                    )
                jk[i] = stat(sub)
            ci_low, ci_high = _bca_endpoints(theta_hat, boot, jk, alpha=alpha)
        else:
            # Degenerate: fall back to percentile
            ci_low = float(np.quantile(boot, alpha / 2))
            ci_high = float(np.quantile(boot, 1 - alpha / 2))
    else:
        raise ValueError(f"ci_method must be 'bca' or 'percentile', got {ci_method!r}")

    return BootstrapCI(
        point=theta_hat,
        huber=huber,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_method=ci_method,
        bootstrap_replicates=boot if keep_replicates else None,
        B=B,
        n_clusters=n,
        seed=seed,
    )


# ============================================================
# Paired bootstrap for model-vs-model comparison
# ============================================================

def paired_cluster_bootstrap_difference(
    values_a: np.ndarray,
    values_b: np.ndarray,
    *,
    B: int = 10_000,
    seed: int = 42,
    ci_method: str = "bca",
) -> BootstrapCI:
    """Paired cluster bootstrap of the difference (A − B).

    Both arrays must be aligned on the same cluster identifiers (same
    patient ordering). Resampling is performed on clusters (same indices
    drawn for both), so within-cluster pairing is preserved.

    Used for model-vs-model comparison per spec §A.5.

    Args:
        values_a: (N,) per-cluster values from model A.
        values_b: (N,) per-cluster values from model B (paired).
        B, seed, ci_method: As in cluster_bootstrap.

    Returns:
        BootstrapCI on the difference distribution.
    """
    values_a = np.asarray(values_a, dtype=float).ravel()
    values_b = np.asarray(values_b, dtype=float).ravel()
    if values_a.shape != values_b.shape:
        raise ValueError(
            f"paired_cluster_bootstrap_difference: shape mismatch "
            f"{values_a.shape} vs {values_b.shape}"
        )
    diff = values_a - values_b
    return cluster_bootstrap(diff, B=B, seed=seed, ci_method=ci_method)

"""Detection scorer for the Arm B validation harness.

Pure functions: given a ground-truth InjectionManifest and the NeuroTCS flag
output, compute detection coverage (per error type and overall), specificity on
un-injected coordinates, and confidence intervals. No I/O, no global state, so
the scoring logic is unit-testable on synthetic inputs.

Interval methods:
  - Wilson score interval for proportions (better small-sample coverage than
    Wald); used for coverage and specificity.
  - Clopper-Pearson (exact, Beta-quantile) interval; used where an exact
    guarantee is preferred (e.g. zero-event cells).

These mirror the protocol's Statistical Analysis Plan (Section 8).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from neurotcs.validation.taxonomy import ErrorType, InjectionManifest

# Standard normal quantile for two-sided 95% (z_{0.975}).
_Z_95 = 1.959963984540054


def wilson_interval(k: int, n: int, z: float = _Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n.

    Returns (low, high), each in [0, 1]. For n == 0 returns (0.0, 1.0) -- the
    only honest interval with no data.
    """
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"invalid counts k={k}, n={n}")
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _beta_quantile(a: float, b: float, q: float) -> float:
    """Inverse regularized incomplete Beta via bisection.

    Sufficient precision for reporting CIs; avoids a SciPy dependency. Monotone
    in x, so bisection converges reliably.
    """
    if a <= 0:
        return 0.0
    if b <= 0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _reg_inc_beta(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _reg_inc_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta I_x(a, b) via continued fraction (Lentz)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    # Lentz's algorithm for the continued fraction
    f, c, d = 1.0, 1.0, 0.0
    tiny = 1e-30
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < tiny:
            d = tiny
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < tiny:
            c = tiny
        cd = c * d
        f *= cd
        if abs(1.0 - cd) < 1e-12:
            break
    use_swap = x >= (a + 1) / (a + b + 2)
    if not use_swap:
        return front * (f - 1.0)
    # symmetry: I_x(a,b) = 1 - I_{1-x}(b,a)
    return 1.0 - _reg_inc_beta_raw(1 - x, b, a)


def _reg_inc_beta_raw(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    tiny = 1e-30
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < tiny:
            d = tiny
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < tiny:
            c = tiny
        cd = c * d
        f *= cd
        if abs(1.0 - cd) < 1e-12:
            break
    return front * (f - 1.0)


def clopper_pearson_interval(k: int, n: int,
                             alpha: float = 0.05) -> tuple[float, float]:
    """Exact Clopper-Pearson interval for k successes in n trials.

    Returns (low, high). Handles the boundary cases k == 0 and k == n exactly.
    """
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"invalid counts k={k}, n={n}")
    if n == 0:
        return (0.0, 1.0)
    lo = 0.0 if k == 0 else _beta_quantile(k, n - k + 1, alpha / 2)
    hi = 1.0 if k == n else _beta_quantile(k + 1, n - k, 1 - alpha / 2)
    return (lo, hi)


@dataclass
class PerTypeResult:
    """Detection coverage for one error type."""

    error_type: ErrorType
    injected: int
    detected: int

    @property
    def coverage(self) -> float:
        return self.detected / self.injected if self.injected else float("nan")

    @property
    def coverage_ci(self) -> tuple[float, float]:
        return wilson_interval(self.detected, self.injected)


@dataclass
class DetectionReport:
    """Full Arm B detection report.

    HONEST READING: ``overall_coverage`` is the fraction of a *pre-registered,
    realistic* error distribution that NeuroTCS flagged at the exact injected
    coordinate. It is a coverage measure, not accuracy, and is only
    interpretable alongside the taxonomy (per_type) and its CIs.
    """

    per_type: list[PerTypeResult]
    total_injected: int
    total_detected: int
    clean_coordinates: int
    false_positives_on_clean: int

    @property
    def overall_coverage(self) -> float:
        if not self.total_injected:
            return float("nan")
        return self.total_detected / self.total_injected

    @property
    def overall_coverage_ci(self) -> tuple[float, float]:
        return wilson_interval(self.total_detected, self.total_injected)

    @property
    def specificity(self) -> float:
        """1 - (false flags on clean injectable coordinates / clean coords)."""
        if not self.clean_coordinates:
            return float("nan")
        return 1.0 - self.false_positives_on_clean / self.clean_coordinates

    @property
    def specificity_ci(self) -> tuple[float, float]:
        tn = self.clean_coordinates - self.false_positives_on_clean
        return wilson_interval(tn, self.clean_coordinates)

    def to_dict(self) -> dict:
        return {
            "overall_coverage": self.overall_coverage,
            "overall_coverage_ci95": list(self.overall_coverage_ci),
            "specificity": self.specificity,
            "specificity_ci95": list(self.specificity_ci),
            "total_injected": self.total_injected,
            "total_detected": self.total_detected,
            "clean_coordinates": self.clean_coordinates,
            "false_positives_on_clean": self.false_positives_on_clean,
            "per_type": [
                {
                    "error_type": str(r.error_type),
                    "injected": r.injected,
                    "detected": r.detected,
                    "coverage": r.coverage,
                    "coverage_ci95": list(r.coverage_ci),
                }
                for r in self.per_type
            ],
            "_honest_note": (
                "Coverage measures the fraction of a pre-registered realistic "
                "error taxonomy detected at the exact injected coordinate. It "
                "is NOT accuracy and does NOT substitute for Arm A expert "
                "adjudication of natural flags (flag precision / PPV)."
            ),
        }


def _flag_keys(flags: dict) -> set[tuple[str, str, str | None]]:
    """Extract the set of (subject_id, field, visit) coordinates NeuroTCS
    flagged at any severity tier.

    Field names in flags may carry a sheet prefix (e.g. 'EN:apoe_genotype');
    both the prefixed and unprefixed forms are added so the join is robust to
    that convention.
    """
    keys: set[tuple[str, str, str | None]] = set()
    for tier in ("impossible", "implausible", "informational"):
        for fl in flags.get(tier, []) or []:
            sid = str(fl.get("subject_id")) if fl.get("subject_id") is not None else None
            field_name = fl.get("field")
            visit = fl.get("visit")
            visit_s = str(visit) if visit is not None else None
            if sid is None or field_name is None:
                continue
            keys.add((sid, field_name, visit_s))
            if ":" in field_name:
                keys.add((sid, field_name.split(":", 1)[1], visit_s))
    return keys


def score_detection(manifest: InjectionManifest, flags: dict) -> DetectionReport:
    """Score NeuroTCS flags against the injected ground-truth manifest.

    An injected error is 'detected' iff NeuroTCS emitted a flag at the same
    (subject_id, field, visit) coordinate (matched with or without sheet
    prefix, and tolerant of visit type). A flag on a clean injectable
    coordinate counts as a false positive for the injection study.
    """
    flagged = _flag_keys(flags)

    per_type: list[PerTypeResult] = []
    total_detected = 0
    for etype, errs in sorted(manifest.by_type().items(), key=lambda kv: str(kv[0])):
        det = sum(1 for e in errs if _matches(e.key, flagged))
        total_detected += det
        per_type.append(PerTypeResult(etype, len(errs), det))

    fp = sum(1 for key in manifest.clean_keys if _matches(key, flagged))

    return DetectionReport(
        per_type=per_type,
        total_injected=len(manifest.injected),
        total_detected=total_detected,
        clean_coordinates=len(manifest.clean_keys),
        false_positives_on_clean=fp,
    )


def _matches(key: tuple[str, str, str | None],
             flagged: set[tuple[str, str, str | None]]) -> bool:
    """Coordinate match tolerant of visit string/None and sheet prefix."""
    sid, field_name, visit = key
    candidates = {
        (sid, field_name, visit),
        (sid, field_name, str(visit) if visit is not None else None),
    }
    return bool(candidates & flagged)

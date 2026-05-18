"""Tests for neurotcs.threshold_derivation — empirical operational thresholds."""

import numpy as np
import pytest

from neurotcs.threshold_derivation import (
    LARSON_2025_CITATION,
    LARSON_2025_DOI,
    LARSON_2025_PMID,
    OperationalThreshold,
    derive_threshold_conformal,
    derive_threshold_distribution,
)

# -----------------------------------------------------------------------------
# Citation lock
# -----------------------------------------------------------------------------

def test_larson_2025_citation_locked():
    assert LARSON_2025_DOI == "10.1016/j.jacr.2025.02.008"
    assert LARSON_2025_PMID == "40057886"
    assert "Larson DB" in LARSON_2025_CITATION
    assert "J Am Coll Radiol 2025;22(5):586-592" in LARSON_2025_CITATION


# -----------------------------------------------------------------------------
# k-sigma threshold
# -----------------------------------------------------------------------------

def test_distribution_threshold_basic():
    """k-sigma threshold must be below the mean."""
    ref = np.array([0.99, 0.995, 0.993, 0.991, 0.994, 0.992, 0.996,
                     0.99, 0.995, 0.993])
    thr = derive_threshold_distribution(ref, k_sigma=2.0)
    assert isinstance(thr, OperationalThreshold)
    assert thr.method == "k_sigma_below_mean"
    assert thr.threshold_value < thr.reference_mean
    assert thr.k_sigma == 2.0
    assert thr.reference_n == 10


def test_distribution_threshold_k_sigma_monotonic():
    """Larger k_sigma → lower (stricter) threshold."""
    ref = np.array([0.99, 0.995, 0.993, 0.991, 0.994, 0.992, 0.996])
    thr_1 = derive_threshold_distribution(ref, k_sigma=1.0)
    thr_3 = derive_threshold_distribution(ref, k_sigma=3.0)
    assert thr_3.threshold_value < thr_1.threshold_value


def test_distribution_threshold_too_few_audits_raises():
    with pytest.raises(ValueError, match="at least 2"):
        derive_threshold_distribution(np.array([0.99]), k_sigma=2.0)


def test_distribution_threshold_negative_k_sigma_raises():
    ref = np.array([0.99, 0.995, 0.993])
    with pytest.raises(ValueError, match="k_sigma"):
        derive_threshold_distribution(ref, k_sigma=-1.0)


# -----------------------------------------------------------------------------
# Conformal threshold
# -----------------------------------------------------------------------------

def test_conformal_threshold_basic():
    ref = np.array([0.99, 0.995, 0.993, 0.991, 0.994, 0.992, 0.996,
                     0.99, 0.995, 0.993, 0.997, 0.989, 0.992, 0.994,
                     0.993, 0.991, 0.995, 0.992, 0.996, 0.990])
    thr = derive_threshold_conformal(ref, coverage=0.95)
    assert isinstance(thr, OperationalThreshold)
    assert thr.method == "conformal_lower_bound"
    assert thr.coverage == 0.95
    # Threshold is the empirical 5th percentile (with finite-sample correction);
    # must be in the data range
    assert min(ref) <= thr.threshold_value <= max(ref)


def test_conformal_coverage_monotonic():
    """Higher coverage → lower (more conservative) threshold."""
    ref = np.linspace(0.99, 1.0, 100)
    thr_95 = derive_threshold_conformal(ref, coverage=0.95)
    thr_99 = derive_threshold_conformal(ref, coverage=0.99)
    assert thr_99.threshold_value <= thr_95.threshold_value


def test_conformal_coverage_out_of_range_raises():
    ref = np.array([0.99, 0.995, 0.993])
    with pytest.raises(ValueError, match="coverage"):
        derive_threshold_conformal(ref, coverage=0.0)
    with pytest.raises(ValueError, match="coverage"):
        derive_threshold_conformal(ref, coverage=1.0)


def test_conformal_too_few_audits_raises():
    with pytest.raises(ValueError, match="at least 2"):
        derive_threshold_conformal(np.array([0.99]), coverage=0.95)


def test_operational_threshold_is_immutable():
    ref = np.array([0.99, 0.995, 0.993])
    thr = derive_threshold_distribution(ref, k_sigma=2.0)
    with pytest.raises((AttributeError, TypeError)):
        thr.threshold_value = 999.0  # type: ignore[misc]

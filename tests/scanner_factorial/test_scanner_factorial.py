"""Tests for neurotcs.scanner_factorial — FUTURE-AI Robustness 3 factorial."""

import numpy as np
import pytest

from neurotcs.scanner_factorial import (
    FactorialCell,
    ScannerFactorialResult,
    scanner_factorial,
)


def test_scanner_factorial_two_dimensions():
    """Basic 2D vendor × field-strength factorial."""
    flags = np.array([False, True, False, False, True, True, False, False])
    attrs = {
        "scanner_vendor": np.array(["GE", "GE", "Siemens", "Siemens",
                                     "GE", "GE", "Siemens", "Siemens"]),
        "field_strength": np.array(["1.5T", "1.5T", "1.5T", "1.5T",
                                     "3T", "3T", "3T", "3T"]),
    }
    result = scanner_factorial(
        flags, attrs, ("scanner_vendor", "field_strength"), min_cell_n=1
    )
    assert isinstance(result, ScannerFactorialResult)
    assert len(result.cells) == 4  # GE+1.5T, GE+3T, Siemens+1.5T, Siemens+3T


def test_scanner_factorial_detects_interaction():
    """GE 3T should have 100% flag rate, Siemens 1.5T 0% — max disparity 1.0."""
    flags = np.array([False, False, True, True])
    attrs = {
        "scanner_vendor": np.array(["Siemens", "Siemens", "GE", "GE"]),
        "field_strength": np.array(["1.5T", "1.5T", "3T", "3T"]),
    }
    result = scanner_factorial(
        flags, attrs, ("scanner_vendor", "field_strength"), min_cell_n=1
    )
    assert abs(result.interaction_disparity - 1.0) < 1e-9
    assert result.max_cell_flag_rate == 1.0


def test_scanner_factorial_min_cell_n_filter():
    """Cells with n < min_cell_n must be excluded."""
    flags = np.array([False, True, False])
    attrs = {
        "scanner_vendor": np.array(["GE", "GE", "Siemens"]),  # Siemens has only 1
        "field_strength": np.array(["1.5T", "1.5T", "1.5T"]),
    }
    result = scanner_factorial(
        flags, attrs, ("scanner_vendor", "field_strength"), min_cell_n=2
    )
    # Only GE+1.5T should pass the min_cell_n=2 filter
    assert len(result.cells) == 1
    assert result.cells[0].dimension_values == (
        ("scanner_vendor", "GE"), ("field_strength", "1.5T")
    )


def test_scanner_factorial_three_dimensions():
    """3D factorial: vendor × field-strength × protocol (n=16)."""
    flags = np.array([False] * 8 + [True] * 8)
    attrs = {
        "scanner_vendor": np.array(["GE"] * 8 + ["Siemens"] * 8),
        "field_strength": np.array((["1.5T"] * 4 + ["3T"] * 4) * 2),
        "protocol": np.array(["MPRAGE", "MPRAGE", "FLAIR", "FLAIR"] * 4),
    }
    result = scanner_factorial(
        flags, attrs,
        ("scanner_vendor", "field_strength", "protocol"),
        min_cell_n=1,
    )
    assert result.dimensions == ("scanner_vendor", "field_strength", "protocol")
    assert len(result.cells) >= 4  # at least some cells have data


def test_scanner_factorial_empty_flags():
    result = scanner_factorial(
        np.array([], dtype=bool), {}, ("scanner_vendor",), min_cell_n=1
    )
    assert len(result.cells) == 0


def test_scanner_factorial_missing_dimension_raises():
    flags = np.array([False, True])
    attrs = {"scanner_vendor": np.array(["GE", "Siemens"])}
    with pytest.raises(ValueError, match="not in technical_attributes"):
        scanner_factorial(flags, attrs, ("nonexistent_dim",), min_cell_n=1)


def test_scanner_factorial_length_mismatch_raises():
    flags = np.array([False, True, False])
    attrs = {"scanner_vendor": np.array(["GE", "Siemens"])}  # length 2 vs 3
    with pytest.raises(ValueError, match="length"):
        scanner_factorial(flags, attrs, ("scanner_vendor",), min_cell_n=1)


def test_factorial_cell_label():
    cell = FactorialCell(
        dimension_values=(("scanner_vendor", "GE"), ("field_strength", "3T")),
        n=10,
        n_flagged=2,
        flag_rate=0.2,
    )
    assert cell.label() == "scanner_vendor=GE,field_strength=3T"

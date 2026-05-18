"""
neurotcs.scanner_factorial — Cross-tabulated robustness sensitivity matrix
==========================================================================

Implements the scanner × vendor × interval factorial sensitivity matrix
described in NeuroTCS spec v1.7 §B.4.5, grounded in:

    FUTURE-AI Robustness 3 (Lekadir et al. BMJ 2025;388:e081554):
    "stress tests, repeatability tests... under conditions that reflect the
     variations of real-world clinical practice. These may include data,
     equipment, technician, clinician, patient and centre related variations."

This is COMPLEMENTARY to ``neurotcs.fairness.robustness_audit``:

  - ``robustness_audit`` computes per-attribute flag-rate disparities
    (1D stratification per attribute)
  - ``scanner_factorial`` computes a FULL CROSS-TABULATION across multiple
    technical dimensions simultaneously (e.g. vendor × field-strength ×
    follow-up interval), surfacing interaction effects that 1D
    stratification can miss.

Typical use: detect that a model is admissible on Siemens 3T scanners but
flags 8% of transitions on GE 1.5T scanners — a vendor × field-strength
interaction that one-attribute-at-a-time stratification would miss.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "FactorialCell",
    "ScannerFactorialResult",
    "scanner_factorial",
]


@dataclass(frozen=True)
class FactorialCell:
    """A single cell of the factorial sensitivity matrix.

    Each cell corresponds to one unique combination of attribute values
    across the requested dimensions.
    """

    dimension_values: tuple[tuple[str, str], ...]  # (attr_name, value) pairs
    n: int
    n_flagged: int
    flag_rate: float

    def label(self) -> str:
        """Human-readable label of the cell, e.g. 'vendor=GE,field_strength=1.5T'."""
        return ",".join(f"{k}={v}" for k, v in self.dimension_values)


@dataclass(frozen=True)
class ScannerFactorialResult:
    """Result of the scanner factorial sensitivity analysis."""

    dimensions: tuple[str, ...]
    cells: tuple[FactorialCell, ...] = field(default_factory=tuple)
    overall_flag_rate: float = 0.0
    max_cell_flag_rate: float = 0.0
    max_cell_label: str = ""
    interaction_disparity: float = 0.0  # max_cell - min_cell flag rate


def scanner_factorial(
    flags: np.ndarray,
    technical_attributes: Mapping[str, np.ndarray],
    dimensions: tuple[str, ...],
    min_cell_n: int = 5,
) -> ScannerFactorialResult:
    """Compute a factorial sensitivity matrix across multiple technical dimensions.

    Parameters
    ----------
    flags
        Boolean array, length = number of audited transitions.
    technical_attributes
        Mapping from attribute name to per-transition categorical values.
    dimensions
        Tuple of attribute names to cross-tabulate. Typical: ``("scanner_vendor",
        "field_strength")`` for a 2D matrix; ``("scanner_vendor", "field_strength",
        "protocol")`` for a 3D matrix.
    min_cell_n
        Cells with fewer than this many transitions are excluded (stable rate
        estimation needs at least a handful of observations).

    Returns
    -------
    ScannerFactorialResult
        With one ``FactorialCell`` per unique combination of dimension values
        that has at least ``min_cell_n`` transitions.

    Examples
    --------
    >>> import numpy as np
    >>> flags = np.array([False, True, False, False, True, True, False, False])
    >>> attrs = {
    ...     "scanner_vendor": np.array(["GE", "GE", "Siemens", "Siemens",
    ...                                  "GE", "GE", "Siemens", "Siemens"]),
    ...     "field_strength": np.array(["1.5T", "1.5T", "1.5T", "1.5T",
    ...                                  "3T", "3T", "3T", "3T"]),
    ... }
    >>> result = scanner_factorial(flags, attrs, ("scanner_vendor", "field_strength"),
    ...                            min_cell_n=1)
    >>> len(result.cells)
    4
    """
    if len(flags) == 0:
        return ScannerFactorialResult(dimensions=dimensions)
    if not dimensions:
        raise ValueError("at least one dimension required")
    for d in dimensions:
        if d not in technical_attributes:
            raise ValueError(f"dimension '{d}' not in technical_attributes")
        if len(technical_attributes[d]) != len(flags):
            raise ValueError(
                f"technical_attributes['{d}'] length {len(technical_attributes[d])} "
                f"!= flags length {len(flags)}"
            )

    overall_flag_rate = float(np.mean(flags))

    # Build per-cell aggregates
    cell_n: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)
    cell_flagged: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)

    for i in range(len(flags)):
        key = tuple(
            (d, str(technical_attributes[d][i])) for d in dimensions
        )
        # Skip rows with missing values in any dimension
        if any(v == "nan" or v == "" or v == "None" for _, v in key):
            continue
        cell_n[key] += 1
        if flags[i]:
            cell_flagged[key] += 1

    cells: list[FactorialCell] = []
    for key, n in cell_n.items():
        if n < min_cell_n:
            continue
        flagged = cell_flagged[key]
        cells.append(
            FactorialCell(
                dimension_values=key,
                n=n,
                n_flagged=flagged,
                flag_rate=flagged / n,
            )
        )

    if not cells:
        return ScannerFactorialResult(
            dimensions=dimensions,
            cells=(),
            overall_flag_rate=overall_flag_rate,
        )

    max_cell = max(cells, key=lambda c: c.flag_rate)
    min_cell = min(cells, key=lambda c: c.flag_rate)

    return ScannerFactorialResult(
        dimensions=dimensions,
        cells=tuple(cells),
        overall_flag_rate=overall_flag_rate,
        max_cell_flag_rate=max_cell.flag_rate,
        max_cell_label=max_cell.label(),
        interaction_disparity=max_cell.flag_rate - min_cell.flag_rate,
    )

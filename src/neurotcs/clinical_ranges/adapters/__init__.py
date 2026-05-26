"""Adapters that transform domain-specific input formats into the Layer 2
long-format measurements DataFrame."""

from neurotcs.clinical_ranges.adapters.trial_excel import (  # noqa: F401
    trial_excel_to_measurements,
)

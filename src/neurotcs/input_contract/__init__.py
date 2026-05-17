"""
neurotcs.input_contract — Input contracts for longitudinal medical AI predictions.

Two contract versions are shipped:
  - v1_0: Categorical-only predictions (CN/MCI/AD, PR/CR/SD/PD)
  - v1_1: Adds continuous biomarkers with UCUM units (volumes, doubling times)

Both versions are independently versioned; use the version that matches the
vendor's prediction format.

    from neurotcs.input_contract import v1_0, v1_1
    result = v1_1.validate_manifest(manifest_dict)
"""

from neurotcs.input_contract import v1_0, v1_1  # noqa: F401

__all__ = ["v1_0", "v1_1"]

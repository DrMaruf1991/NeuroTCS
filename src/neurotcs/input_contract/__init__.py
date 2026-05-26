"""
neurotcs.input_contract — Input contracts for longitudinal medical AI predictions.

Three contract versions are shipped:
  - v1_0: Categorical-only predictions (CN/MCI/AD, PR/CR/SD/PD)
  - v1_1: Adds continuous biomarkers with UCUM units (volumes, doubling times)
  - v1_2: Adds Layer 3 anchor fields (declares_continuous_biomarkers,
          data_files.attribution) required by
          cross_sheet/manifest_data_consistency@1.0.0

All three versions are independently versioned and fully backward compatible;
use the version that matches the vendor's prediction format.

    from neurotcs.input_contract import v1_0, v1_1, v1_2
    result = v1_2.validate_manifest(manifest_dict)
"""

from neurotcs.input_contract import v1_0, v1_1, v1_2  # noqa: F401

__all__ = ["v1_0", "v1_1", "v1_2"]

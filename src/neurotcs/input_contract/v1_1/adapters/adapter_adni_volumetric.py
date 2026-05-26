"""Deprecation shim — adapter_adni_volumetric.py moved in v1.8.1.

The canonical home for the ADNI volumetric submission builder is now:

    from neurotcs.reference_adapters.adni_volumetric_submission import (
        hash_patient_id, main,
    )

This shim re-exports those names and emits a DeprecationWarning. It will be
removed in v1.9.x. See src/neurotcs/reference_adapters/README.md for the
v1.8.1 reorganization rationale.

Note: this file is a *reference submission-builder*, NOT a runtime
trajectory loader. The v1.8 canonical runtime adapters for volumetric
biomarkers are still being designed; categorical loaders are the locked
v1.8 surface.
"""
import warnings

warnings.warn(
    "neurotcs.input_contract.v1_1.adapters.adapter_adni_volumetric has moved to "
    "neurotcs.reference_adapters.adni_volumetric_submission in v1.8.1. "
    "The old import path will be removed in v1.9.x. "
    "See src/neurotcs/reference_adapters/README.md.",
    DeprecationWarning,
    stacklevel=2,
)

from neurotcs.reference_adapters.adni_volumetric_submission import (  # noqa: F401,E402
    COHORT_SALT,
    hash_patient_id,
    main,
)

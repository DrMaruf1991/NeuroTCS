"""Deprecation shim — adapter_adni.py moved in v1.8.1.

The canonical home for the ADNI categorical submission builder is now:

    from neurotcs.reference_adapters.adni_categorical_submission import (
        hash_patient_id, build_predictions, derive_aa_2024_state,
        build_aa_2024_predictions, build_patients, build_manifest, main,
    )

This shim re-exports those names and emits a DeprecationWarning. It will be
removed in v1.9.x. See src/neurotcs/reference_adapters/README.md for the
v1.8.1 reorganization rationale.

Note: this file is a *reference submission-builder*, NOT the runtime
trajectory loader. For the v1.8 canonical runtime loader that drives
`neurotcs.audit()`, use:

    from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
        load_adni_trajectories,
    )
"""
import warnings

warnings.warn(
    "neurotcs.input_contract.v1_1.adapters.adapter_adni has moved to "
    "neurotcs.reference_adapters.adni_categorical_submission in v1.8.1. "
    "The old import path will be removed in v1.9.x. "
    "See src/neurotcs/reference_adapters/README.md.",
    DeprecationWarning,
    stacklevel=2,
)

from neurotcs.reference_adapters.adni_categorical_submission import (  # noqa: F401,E402
    COHORT_SALT,
    build_aa_2024_predictions,
    build_manifest,
    build_patients,
    build_predictions,
    derive_aa_2024_state,
    hash_patient_id,
    main,
)

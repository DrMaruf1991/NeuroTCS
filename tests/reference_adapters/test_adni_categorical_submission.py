"""Smoke test for neurotcs.reference_adapters.adni_categorical_submission.

This is a *reference submission-builder*, not a runtime loader. The smoke
test verifies the module imports cleanly and its public functions are
callable with sane synthetic input. It does NOT lock invariants — those
belong on the runtime adapter side.
"""
from __future__ import annotations

import pandas as pd

from neurotcs.reference_adapters.adni_categorical_submission import (
    build_predictions,
    hash_patient_id,
)


def test_hash_patient_id_deterministic():
    """Hashing the same RID twice produces the same anonymized identifier."""
    h1 = hash_patient_id(42)
    h2 = hash_patient_id(42)
    assert h1 == h2
    assert h1.startswith("ADNI_")
    assert len(h1) == len("ADNI_") + 16


def test_hash_patient_id_distinguishes_rids():
    """Different RIDs produce different hashed identifiers."""
    assert hash_patient_id(1) != hash_patient_id(2)


def test_build_predictions_filters_to_known_states():
    """build_predictions keeps only CN / MCI / Dementia rows with ≥2 visits.

    The function returns a transformed DataFrame with NeuroTCS input-contract
    columns (patient_id is hashed; original RID is not preserved). We verify
    the row count and the state filter, which are the two invariants the
    function guarantees.
    """
    df = pd.DataFrame({
        "RID": [1, 1, 2, 2, 3],
        "EXAMDATE": pd.to_datetime([
            "2020-01-01", "2021-01-01",
            "2020-06-01", "2021-06-01",
            "2020-01-01",  # only one visit -> dropped
        ]),
        "VISCODE2": ["bl", "m12", "bl", "m12", "bl"],
        "DIAGNOSIS": ["CN", "MCI", "MCI", "Dementia", "CN"],
    })
    out = build_predictions(df)
    # Subject 3 has only 1 visit -> dropped; 4 rows remain (subjects 1 + 2, 2 visits each)
    assert len(out) == 4, f"expected 4 rows after filtering, got {len(out)}"
    # All output rows are in the canonical state space
    assert set(out["predicted_state"]).issubset({"CN", "MCI", "Dementia"})
    # Two distinct hashed patient_ids (one per surviving subject)
    assert out["patient_id"].nunique() == 2


def test_deprecation_shim_still_works():
    """The old import path still resolves (with a DeprecationWarning)."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Force a fresh import via importlib to actually trigger the warning
        import importlib

        import neurotcs.input_contract.v1_1.adapters.adapter_adni as shim
        importlib.reload(shim)
        # At least one DeprecationWarning should have been issued
        assert any(issubclass(item.category, DeprecationWarning) for item in w)
    # The shim should re-export the canonical function
    assert callable(shim.hash_patient_id)
    assert shim.hash_patient_id(1) == hash_patient_id(1)

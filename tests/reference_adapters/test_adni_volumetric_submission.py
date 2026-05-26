"""Smoke test for neurotcs.reference_adapters.adni_volumetric_submission.

This is a *reference submission-builder*, not a runtime loader. The smoke
test verifies the module imports cleanly and its public functions are
callable. It does NOT lock invariants.
"""
from __future__ import annotations

from neurotcs.reference_adapters.adni_volumetric_submission import (
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


def test_module_imports_cleanly():
    """The renamed module exposes a callable main()."""
    from neurotcs.reference_adapters import adni_volumetric_submission
    assert callable(adni_volumetric_submission.main)


def test_deprecation_shim_still_works():
    """The old import path still resolves (with a DeprecationWarning)."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        import importlib

        import neurotcs.input_contract.v1_1.adapters.adapter_adni_volumetric as shim
        importlib.reload(shim)
        assert any(issubclass(item.category, DeprecationWarning) for item in w)
    assert callable(shim.hash_patient_id)
    assert shim.hash_patient_id(1) == hash_patient_id(1)

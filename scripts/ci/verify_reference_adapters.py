#!/usr/bin/env python3
"""
CI helper: verify the v1.8.1 reference_adapters reorganization is intact.

Pulled out of `.github/workflows/ci-matrix.yml` for cross-platform reliability.

Verifies:
  - The new path `neurotcs.reference_adapters.adni_categorical_submission` works
  - The old path `neurotcs.input_contract.v1_1.adapters.adapter_adni` still works
    via the deprecation shim
  - The shim emits a DeprecationWarning
  - Both paths return identical results from `hash_patient_id` (no behavior drift)
"""
from __future__ import annotations

import sys
import warnings


def main() -> int:
    try:
        from neurotcs.reference_adapters.adni_categorical_submission import (
            hash_patient_id as new_h,
        )
    except ImportError as e:
        print(f"FAIL: new reference_adapters path broken: {e}", file=sys.stderr)
        return 1

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        try:
            from neurotcs.input_contract.v1_1.adapters.adapter_adni import (
                hash_patient_id as old_h,
            )
        except ImportError as e:
            print(f"FAIL: deprecation shim broken: {e}", file=sys.stderr)
            return 1

        if not any(issubclass(w.category, DeprecationWarning) for w in captured):
            print(
                "FAIL: deprecation shim did not emit DeprecationWarning",
                file=sys.stderr,
            )
            return 1

    if new_h(1) != old_h(1):
        print(
            "FAIL: deprecation shim produces different hash than new path "
            "(behavior drift across paths)",
            file=sys.stderr,
        )
        return 1

    print("OK: reference_adapters reorganization intact (new + old paths agree)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

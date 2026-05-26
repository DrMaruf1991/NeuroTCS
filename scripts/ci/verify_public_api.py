#!/usr/bin/env python3
"""
CI helper: verify the documented public-API names import cleanly.

This is a smoke test, not a behavior test — if any of these names disappear
or get renamed, downstream users will break, so we trip CI early.

Pulled out of `.github/workflows/ci.yml` inline `python -c "..."` for
cross-platform reliability and local testability.
"""
from __future__ import annotations

import sys


def main() -> int:
    # audit_core (Piece 4 of 7, SHIPPED v1.2.0+)
    try:
        from neurotcs import BootstrapCI, Trajectory, audit, load_rulepack  # noqa: F401
        from neurotcs.audit_core import (  # noqa: F401
            build_generator,
            cluster_bootstrap,
            huber_m_estimate,
        )
    except ImportError as e:
        print(f"FAIL: audit_core public API broken: {e}", file=sys.stderr)
        return 1

    # v1.7.0 + v1.7.1 module public API
    try:
        from neurotcs import (  # noqa: F401
            AttributionType,
            binary_sample_size,
            derive_threshold_conformal,
            derive_threshold_distribution,
            fairness_audit,
            make_silent_deployment_evidence,
            robustness_audit,
            scanner_factorial,
        )
    except ImportError as e:
        print(f"FAIL: v1.7.0 / v1.7.1 public API broken: {e}", file=sys.stderr)
        return 1

    print("OK: audit_core public API + v1.7 modules import cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())

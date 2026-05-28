#!/usr/bin/env python3
"""
CI helper: verify the expected AD rule packs load cleanly.

Pulled out of `.github/workflows/ci.yml` inline `python -c "..."` so the
logic is testable locally and not subject to YAML/cmd quoting fragility.

Asserts:
  - exactly 4 rule packs (the AD-only scope: niaaa_2018, aa_2024, aa_2024_trac, at_biological)
  - all of them in the `ad/` namespace
  - none are INVALID status

Exits 0 on success, non-zero with a clear message on failure.
"""
from __future__ import annotations

import sys

from neurotcs import list_rulepacks


def main() -> int:
    packs = list_rulepacks()
    invalid = [p for p in packs if p.get("status") == "INVALID"]
    if invalid:
        print(f"FAIL: invalid packs detected: {invalid}", file=sys.stderr)
        return 1

    if len(packs) != 4:
        print(
            f"FAIL: expected 4 AD packs (v1.x AD-only scope, see docs/SCOPE.md); "
            f"got {len(packs)}: {[p['name'] for p in packs]}",
            file=sys.stderr,
        )
        return 1

    non_ad = [p["name"] for p in packs if not p["name"].startswith("ad/")]
    if non_ad:
        print(
            f"FAIL: non-AD packs present under v1.x AD-only scope: {non_ad}",
            file=sys.stderr,
        )
        return 1

    print(f"OK: all {len(packs)} AD rule packs load as production")
    for p in packs:
        print(f"   - {p['name']} (status: {p['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

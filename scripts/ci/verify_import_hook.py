#!/usr/bin/env python3
"""
CI helper: verify the planned-module import hook raises a helpful ImportError
when someone tries to import a roadmap module that isn't shipped yet.

The hook lives in `src/neurotcs/__init__.py` as `_PlannedModuleFinder`. It
exists so that `import neurotcs.validation_harness` (Piece 7) and
`import neurotcs.output_schema` (Piece 5) don't raise the default
`ModuleNotFoundError("No module named 'neurotcs.validation_harness'")` —
they raise an ImportError pointing to the v1.9.x+ roadmap.

We assert:
  - the package version starts with "1." (we ship the v1.x series from main)
  - both planned modules raise ImportError when imported
  - the error message contains the marker word "roadmap"

We deliberately do NOT pin the version to "1.9." or any other minor — the
test should not require updating on every minor release.
"""
from __future__ import annotations

import sys


def main() -> int:
    import neurotcs

    if not neurotcs.__version__.startswith("1."):
        print(
            f"FAIL: package version {neurotcs.__version__!r} not in the v1.x series",
            file=sys.stderr,
        )
        return 1

    ok = 0
    for mod in ("neurotcs.validation_harness", "neurotcs.output_schema"):
        try:
            __import__(mod)
            print(
                f"FAIL: {mod} should have raised ImportError but imported cleanly",
                file=sys.stderr,
            )
            return 1
        except ImportError as e:
            if "roadmap" in str(e):
                ok += 1
            else:
                print(
                    f"FAIL: {mod} raised ImportError but message lacks 'roadmap' "
                    f"marker (text was: {e!s})",
                    file=sys.stderr,
                )
                return 1

    print(f"OK: import hook fires for {ok}/2 planned modules with helpful messages")
    return 0


if __name__ == "__main__":
    sys.exit(main())

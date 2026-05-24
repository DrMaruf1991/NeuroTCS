#!/usr/bin/env python3
"""
CI helper: smoke-test that example scripts parse cleanly under the current
Python version. This is *not* a behavior test — we just ast.parse the files
to catch syntax errors that the matrix-cell Python version might trip on.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

EXAMPLES = [
    "examples/adni_audit_demo.py",
    "examples/oasis3_audit_demo.py",
]


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    fail = False
    for ex in EXAMPLES:
        path = root / ex
        if not path.exists():
            print(f"FAIL: example file missing: {ex}", file=sys.stderr)
            fail = True
            continue
        try:
            ast.parse(path.read_text(), filename=str(path))
            print(f"OK: {ex} parses")
        except SyntaxError as e:
            print(f"FAIL: {ex} has syntax error: {e}", file=sys.stderr)
            fail = True
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())

"""
scripts/compute_input_checksums.py
==================================

Compute SHA-256 checksums of cohort CSV files for reproducibility verification.

This is the canonical helper for AD-lock Step 2.4 (reproducibility report)
and Step 2.5 (blind-validation invitation). An external collaborator runs
this script on their downloaded cohort CSVs to verify they match the same
data that produced the locked audit_ids in
`docs/datasheet/ad_neurotcs_datasheet.md` Section A.

Cross-platform (Windows / macOS / Linux). Uses only the Python stdlib;
no external dependencies. Streams files (constant memory) so it works on
large CSVs.

Usage
-----
Single file:
    python scripts/compute_input_checksums.py path/to/cohort.csv

Multiple files (e.g. all three MIRIAD CSVs):
    python scripts/compute_input_checksums.py \\
        path/to/clinical.csv \\
        path/to/sessions.csv \\
        path/to/subjects.csv

Directory (recursively hashes every .csv inside):
    python scripts/compute_input_checksums.py --dir path/to/cohort_dir/

JSON output (machine-readable, for committing to a blind-validation report):
    python scripts/compute_input_checksums.py --json *.csv > checksums.json

Why SHA-256?
------------
- Cryptographically strong enough for integrity verification.
- Standard across all three target platforms (Linux `sha256sum`, macOS
  `shasum -a 256`, Windows `Get-FileHash -Algorithm SHA256`).
- This Python implementation produces IDENTICAL hashes to those CLIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_BUFFER_SIZE = 1024 * 1024  # 1 MiB — constant memory for arbitrary file sizes


def sha256_file(path: Path) -> str:
    """Stream-hash a file with SHA-256. Returns lowercase hex digest.

    Produces the same hex digest as `sha256sum file` (Linux),
    `shasum -a 256 file` (macOS), and
    `Get-FileHash -Algorithm SHA256 file` (Windows).
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_BUFFER_SIZE):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute SHA-256 checksums for cohort CSV files.",
    )
    parser.add_argument("paths", nargs="*", type=Path,
                          help="Files or directories to checksum.")
    parser.add_argument("--dir", type=Path, default=None,
                          help="Hash every .csv recursively under this directory.")
    parser.add_argument("--json", action="store_true",
                          help="Emit machine-readable JSON instead of text.")
    args = parser.parse_args(argv)

    targets: list[Path] = []
    for p in args.paths:
        if not p.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 2
        if p.is_dir():
            targets.extend(sorted(p.rglob("*.csv")))
        else:
            targets.append(p)
    if args.dir is not None:
        if not args.dir.is_dir():
            print(f"ERROR: --dir not a directory: {args.dir}", file=sys.stderr)
            return 2
        targets.extend(sorted(args.dir.rglob("*.csv")))

    if not targets:
        print("ERROR: no files to checksum. Pass paths or --dir.",
              file=sys.stderr)
        return 2

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[Path] = []
    for t in targets:
        key = str(t.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(t)

    results: list[dict] = []
    for path in deduped:
        size = path.stat().st_size
        digest = sha256_file(path)
        results.append({
            "path": str(path),
            "size_bytes": size,
            "sha256": digest,
        })

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"{'sha256':<64}  {'size_bytes':>12}  path")
        print(f"{'-'*64}  {'-'*12}  {'-'*40}")
        for r in results:
            print(f"{r['sha256']}  {r['size_bytes']:>12}  {r['path']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

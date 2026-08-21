"""
scripts/inject_known_errors.py
==============================

Deterministic known-error injector for otherwise-valid longitudinal state
data (external expert review, 2026-08; companion to ERRATA E-2026-011 and
docs/VALIDATION_PROTOCOL.md).

Purpose: measure how reliably the NeuroTCS auditor detects deliberately
introduced errors in REAL longitudinal data — the complement of the flag-
precision (PPV) arm. The fully synthetic benchmark
(benchmark/generate_benchmark.py) tests the detector on generated cohorts;
this tool corrupts a cohort you supply, so detection is measured under the
data's true noise and covariance structure.

Every mutation is recorded in an answer key (subject, row, column, original
value, injected value, error type), and the whole run is reproducible:
same input + same seed => byte-identical outputs. No wall-clock values are
written anywhere.

SOFTWARE TEST HARNESS only — outputs are corrupted data for detector
evaluation, never for analysis. The injected file is watermarked via the
manifest (input/injected SHA-256 pair).

Error types
-----------
dementia_reversion (default): pick subjects with a visit in the TOP state
    (e.g. AD) followed by a later visit; overwrite that later visit's state
    with the BOTTOM state (e.g. CN). Under every shipped AD staging pack a
    top->bottom reversion is an inadmissible transition, so a correct
    detector must flag every injected subject.

Usage
-----
    python scripts/inject_known_errors.py \
        --input clean.csv --out-dir out/ \
        --subject-col subject_id --state-col state \
        --states CN,MCI,AD \
        --n-errors 5 --seed 20260812

Outputs (in --out-dir)
----------------------
    injected.csv              input with exactly n mutated state cells
    answer_key.csv            one row per mutation
    injection_manifest.json   seed, counts, SHA-256 of input and output

Exit codes
----------
    0  success
    1  input/argument error (missing file, missing columns, bad states)
    2  fewer injectable sites than --n-errors (pass --allow-partial to
       accept injecting every available site instead)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import pandas as pd

try:  # tool_version in the manifest; never required for operation
    from neurotcs import __version__ as _NEUROTCS_VERSION
except Exception:  # pragma: no cover
    _NEUROTCS_VERSION = "unknown"

ERROR_TYPE_DEMENTIA_REVERSION = "dementia_reversion"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _find_injectable_sites(
    df: pd.DataFrame, subject_col: str, state_col: str, top_state: str
) -> dict[str, int]:
    """Map subject_id -> row index of the first visit AFTER a top-state visit.

    Rows are taken in file order within each subject (contract-conformant
    inputs are visit-ordered; the auditor itself re-derives order from
    dates, so an out-of-order input would be flagged upstream anyway).
    One site per subject: injecting a single cell per subject keeps the
    answer key unambiguous (each injected subject owes exactly one flag).
    """
    sites: dict[str, int] = {}
    for sid, group in df.groupby(subject_col, sort=True):
        idx = list(group.index)
        for pos, row_i in enumerate(idx[:-1]):
            if str(df.at[row_i, state_col]) == top_state:
                sites[str(sid)] = idx[pos + 1]
                break
    return sites


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inject_known_errors",
        description="Deterministically inject known errors into valid "
                    "longitudinal state data (detection-arm harness; see "
                    "docs/VALIDATION_PROTOCOL.md).",
    )
    parser.add_argument("--input", required=True, help="Clean input CSV")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--subject-col", default="subject_id")
    parser.add_argument("--state-col", default="state")
    parser.add_argument(
        "--states", default="CN,MCI,AD",
        help="Comma-separated state vocabulary ordered mild->severe "
             "(default: CN,MCI,AD). The LAST is the reversion source, the "
             "FIRST is the injected value.",
    )
    parser.add_argument("--n-errors", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--error-type", default=ERROR_TYPE_DEMENTIA_REVERSION,
        choices=[ERROR_TYPE_DEMENTIA_REVERSION],
    )
    parser.add_argument(
        "--allow-partial", action="store_true",
        help="Inject every available site when fewer sites exist than "
             "--n-errors, instead of failing closed.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 1

    states = [s.strip() for s in args.states.split(",") if s.strip()]
    if len(states) < 2:
        print("ERROR: --states needs at least two ordered states",
              file=sys.stderr)
        return 1
    bottom_state, top_state = states[0], states[-1]

    if args.n_errors < 1:
        print("ERROR: --n-errors must be >= 1", file=sys.stderr)
        return 1

    input_bytes = input_path.read_bytes()
    # dtype=str + keep_default_na=False: every untouched cell round-trips
    # verbatim, so the only difference between input and output is the
    # injected cells (byte-level minimal diff, deterministic output).
    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    for col in (args.subject_col, args.state_col):
        if col not in df.columns:
            print(f"ERROR: column '{col}' not in input "
                  f"(has: {list(df.columns)})", file=sys.stderr)
            return 1

    sites = _find_injectable_sites(
        df, args.subject_col, args.state_col, top_state
    )
    if not sites:
        print(f"ERROR: no injectable sites (no subject has a '{top_state}' "
              f"visit followed by a later visit)", file=sys.stderr)
        return 2
    if len(sites) < args.n_errors and not args.allow_partial:
        print(
            f"ERROR: requested {args.n_errors} errors but only {len(sites)} "
            f"injectable sites exist. Pass --allow-partial to inject "
            f"{len(sites)}.", file=sys.stderr,
        )
        return 2

    n_to_inject = min(args.n_errors, len(sites))
    rng = random.Random(args.seed)
    chosen_subjects = sorted(rng.sample(sorted(sites), n_to_inject))

    key_rows = []
    for sid in chosen_subjects:
        row_i = sites[sid]
        original = df.at[row_i, args.state_col]
        df.at[row_i, args.state_col] = bottom_state
        key_rows.append({
            "subject_id": sid,
            "row_index": int(row_i),
            "column": args.state_col,
            "original_value": original,
            "injected_value": bottom_state,
            "error_type": args.error_type,
        })
    key_rows.sort(key=lambda r: r["row_index"])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    injected_path = out_dir / "injected.csv"
    key_path = out_dir / "answer_key.csv"
    manifest_path = out_dir / "injection_manifest.json"

    df.to_csv(injected_path, index=False, lineterminator="\n")
    pd.DataFrame(key_rows).to_csv(key_path, index=False, lineterminator="\n")

    manifest = {
        "tool": "inject_known_errors",
        "tool_version": _NEUROTCS_VERSION,
        "error_type": args.error_type,
        "states": states,
        "subject_col": args.subject_col,
        "state_col": args.state_col,
        "seed": args.seed,
        "n_requested": args.n_errors,
        "n_injectable_sites": len(sites),
        "n_injected": n_to_inject,
        "input_file": input_path.name,
        "input_sha256": _sha256_bytes(input_bytes),
        "injected_sha256": _sha256_bytes(injected_path.read_bytes()),
        "answer_key_sha256": _sha256_bytes(key_path.read_bytes()),
        # NO timestamps: outputs must be byte-reproducible from input+seed.
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"injected {n_to_inject}/{args.n_errors} "
          f"({args.error_type}, seed {args.seed})")
    print(f"injected:   {injected_path}")
    print(f"answer key: {key_path}")
    print(f"manifest:   {manifest_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

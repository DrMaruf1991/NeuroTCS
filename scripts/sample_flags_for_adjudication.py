"""
scripts/sample_flags_for_adjudication.py
========================================

Deterministic, blinded Arm A adjudication sampler (external expert review,
2026-08). Implements the sampling and blinding design of
docs/VALIDATION_PROTOCOL.md:

  §3  Arm A draws a sample of flagged AND unflagged records.
  §5  Blinding: reviewers see the subject record and clinical context but
      NOT the NeuroTCS severity output, rule identity, citations, or whether
      the record was flagged. Record order is randomized; flagged and
      unflagged records are interleaved.
  §4  Rubric: DATA_ERROR / CORRECT_RARE / CORRECT_COMMON / INDETERMINATE.
  §7  Sample size targets are configurable (--n-flagged / --n-unflagged);
      the protocol's precision table is the source for the numbers.

Inputs
------
--flags   : flags CSV as emitted by `neurotcs audit ... --csv`
            (columns: severity, layer, subject_id, visit, field,
             observed_value, rule_id, citation, details)
--cohort  : the audited long-format cohort CSV (for drawing unflagged
            subjects and their visit context)

Outputs (in --out-dir)
----------------------
adjudication_worksheet.csv  BLINDED reviewer worksheet. Contains record_id,
                            subject/visit context, and empty adjudication
                            columns. Contains NO severity, NO rule identity,
                            NO flag status.
unblinding_key.csv          record_id -> flag status/severity/rule mapping.
                            COORDINATOR ONLY: never distribute to reviewers.
sampling_manifest.json      seed, counts, input SHA-256s, protocol pointer,
                            rubric. No wall-clock values: byte-reproducible.

Sampling design
---------------
Flagged records are stratified over severity tiers (impossible, implausible)
with proportional allocation and largest-remainder rounding, sampled
per-stratum with a seeded RNG. Unflagged records are drawn from cohort
subjects with no flag of any tier; each contributes one visit-record (seeded
choice) so unflagged rows are visually indistinguishable from flagged rows
in the worksheet. The combined set is shuffled (seeded) and record_ids are
assigned AFTER the shuffle, so presentation order cannot leak flag status.

Exit codes
----------
0 success; 1 input error; 2 requested sample exceeds available records
(pass --allow-partial to sample every available record instead).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import pandas as pd

try:
    from neurotcs import __version__ as _NEUROTCS_VERSION
except Exception:  # pragma: no cover
    _NEUROTCS_VERSION = "unknown"

RUBRIC = (
    "Assign exactly one label per record, blinded to NeuroTCS output: "
    "DATA_ERROR / CORRECT_RARE / CORRECT_COMMON / INDETERMINATE "
    "(docs/VALIDATION_PROTOCOL.md §4)."
)
PROTOCOL = "docs/VALIDATION_PROTOCOL.md (Arm A; §3 design, §5 blinding, §7 n)"

_SAMPLED_TIERS = ("impossible", "implausible")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _proportional_allocation(
    counts: dict[str, int], n: int
) -> dict[str, int]:
    """Largest-remainder proportional allocation of n over strata.

    Deterministic: remainder ties break on stratum name. Never allocates
    more than a stratum holds; shortfall (from capped strata) is spilled to
    the remaining strata with capacity, largest first.
    """
    total = sum(counts.values())
    if total == 0:
        return {k: 0 for k in counts}
    n = min(n, total)
    quotas = {k: n * c / total for k, c in counts.items()}
    alloc = {k: min(int(quotas[k]), counts[k]) for k in counts}
    # distribute the remainder by largest fractional part, then name
    while sum(alloc.values()) < n:
        candidates = [
            k for k in counts if alloc[k] < counts[k]
        ]
        candidates.sort(key=lambda k: (-(quotas[k] - int(quotas[k])), k))
        alloc[candidates[0]] += 1
    return alloc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sample_flags_for_adjudication",
        description="Draw the blinded Arm A adjudication sample "
                    "(docs/VALIDATION_PROTOCOL.md).",
    )
    parser.add_argument("--flags", required=True,
                        help="flags CSV from `neurotcs audit --csv`")
    parser.add_argument("--cohort", required=True,
                        help="audited long-format cohort CSV")
    parser.add_argument("--subject-col", default="subject_id")
    parser.add_argument("--n-flagged", type=int, required=True)
    parser.add_argument("--n-unflagged", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--allow-partial", action="store_true",
                        help="Sample every available record when the request "
                             "exceeds availability, instead of failing.")
    args = parser.parse_args(argv)

    flags_path, cohort_path = Path(args.flags), Path(args.cohort)
    for p in (flags_path, cohort_path):
        if not p.exists():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            return 1

    flags = pd.read_csv(flags_path, dtype=str, keep_default_na=False)
    cohort = pd.read_csv(cohort_path, dtype=str, keep_default_na=False)
    if "severity" not in flags.columns or "subject_id" not in flags.columns:
        print("ERROR: --flags must be a `neurotcs audit --csv` flags file "
              "(severity + subject_id columns)", file=sys.stderr)
        return 1
    if args.subject_col not in cohort.columns:
        print(f"ERROR: cohort lacks column '{args.subject_col}'",
              file=sys.stderr)
        return 1

    rng = random.Random(args.seed)

    # ---- flagged sample: proportional over severity tiers ----
    sampled_flags = flags[flags["severity"].isin(_SAMPLED_TIERS)]
    tier_counts = {
        t: int((sampled_flags["severity"] == t).sum()) for t in _SAMPLED_TIERS
    }
    n_available = sum(tier_counts.values())
    if n_available == 0:
        print("ERROR: no impossible/implausible flags to sample",
              file=sys.stderr)
        return 2
    if args.n_flagged > n_available and not args.allow_partial:
        print(f"ERROR: requested {args.n_flagged} flagged records but only "
              f"{n_available} exist. Pass --allow-partial to sample "
              f"{n_available}.", file=sys.stderr)
        return 2
    alloc = _proportional_allocation(
        tier_counts, min(args.n_flagged, n_available)
    )
    flag_rows: list[dict] = []
    for tier in _SAMPLED_TIERS:  # fixed tier order for determinism
        tier_idx = sorted(
            sampled_flags.index[sampled_flags["severity"] == tier]
        )
        for row_i in sorted(rng.sample(tier_idx, alloc[tier])):
            src = flags.loc[row_i]
            flag_rows.append({
                "flagged": True,
                "subject_id": src["subject_id"],
                "visit": src.get("visit", ""),
                "field": src.get("field", ""),
                "observed_value": src.get("observed_value", ""),
                "severity": src["severity"],
                "layer": src.get("layer", ""),
                "rule_id": src.get("rule_id", ""),
                "citation": src.get("citation", ""),
                "details": src.get("details", ""),
                "source_row_index": int(row_i),
            })

    # ---- unflagged sample: subjects with no flag of ANY tier ----
    flagged_subjects = set(flags["subject_id"])
    unflagged_subjects = sorted(
        set(cohort[args.subject_col]) - flagged_subjects
    )
    if args.n_unflagged > len(unflagged_subjects) and not args.allow_partial:
        print(f"ERROR: requested {args.n_unflagged} unflagged subjects but "
              f"only {len(unflagged_subjects)} exist. Pass --allow-partial.",
              file=sys.stderr)
        return 2
    n_unflagged = min(args.n_unflagged, len(unflagged_subjects))
    unflag_rows: list[dict] = []
    for sid in sorted(rng.sample(unflagged_subjects, n_unflagged)):
        # one seeded visit-record per subject so unflagged rows look exactly
        # like flagged rows in the worksheet (protocol §5 interleaving)
        subject_rows = sorted(cohort.index[cohort[args.subject_col] == sid])
        row_i = rng.choice(subject_rows)
        src = cohort.loc[row_i]
        unflag_rows.append({
            "flagged": False,
            "subject_id": sid,
            "visit": src.get("visit", ""),
            "field": "state",
            "observed_value": src.get("state", ""),
            "severity": "",
            "layer": "",
            "rule_id": "",
            "citation": "",
            "details": "",
            "source_row_index": int(row_i),
        })

    # ---- interleave, then assign record ids AFTER the shuffle ----
    records = flag_rows + unflag_rows
    rng.shuffle(records)
    for i, rec in enumerate(records, start=1):
        rec["record_id"] = f"R{i:04d}"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    worksheet = pd.DataFrame([
        {
            "record_id": r["record_id"],
            "subject_id": r["subject_id"],
            "visit": r["visit"],
            "field": r["field"],
            "observed_value": r["observed_value"],
            "adjudicated_label": "",
            "reviewer_id": "",
            "comments": "",
        }
        for r in records
    ])
    key = pd.DataFrame([
        {
            "record_id": r["record_id"],
            "subject_id": r["subject_id"],
            "flagged": r["flagged"],
            "severity": r["severity"],
            "layer": r["layer"],
            "rule_id": r["rule_id"],
            "citation": r["citation"],
            "details": r["details"],
            "source_row_index": r["source_row_index"],
        }
        for r in records
    ])

    ws_path = out_dir / "adjudication_worksheet.csv"
    key_path = out_dir / "unblinding_key.csv"
    worksheet.to_csv(ws_path, index=False, lineterminator="\n")
    key.to_csv(key_path, index=False, lineterminator="\n")

    manifest = {
        "tool": "sample_flags_for_adjudication",
        "tool_version": _NEUROTCS_VERSION,
        "protocol": PROTOCOL,
        "rubric": RUBRIC,
        "seed": args.seed,
        "n_flagged_requested": args.n_flagged,
        "n_flagged_available": n_available,
        "n_flagged_sampled": len(flag_rows),
        "allocation_by_tier": alloc,
        "n_unflagged_requested": args.n_unflagged,
        "n_unflagged_sampled": len(unflag_rows),
        "flags_file": flags_path.name,
        "flags_sha256": _sha256(flags_path),
        "cohort_file": cohort_path.name,
        "cohort_sha256": _sha256(cohort_path),
        "worksheet_sha256": _sha256(ws_path),
        "unblinding_key_sha256": _sha256(key_path),
        "blinding_note": (
            "unblinding_key.csv is COORDINATOR ONLY and must never be "
            "distributed to reviewers (protocol §5)."
        ),
        # NO timestamps: outputs must be byte-reproducible from inputs+seed.
    }
    (out_dir / "sampling_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"sampled {len(flag_rows)} flagged (allocation {alloc}) + "
          f"{len(unflag_rows)} unflagged, seed {args.seed}")
    print(f"worksheet (give to reviewers):    {ws_path}")
    print(f"unblinding key (COORDINATOR ONLY): {key_path}")
    print(f"manifest:                          "
          f"{out_dir / 'sampling_manifest.json'}")
    print(f"rubric: {RUBRIC}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

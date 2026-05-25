"""
Empirical false-positive validation harness for
cross_sheet/tool_declaration_consistency.

Purpose: establish empirical false-positive rate of the pack's 4 invariants
against a synthetic submission corpus *before* promoting the pack from
research_preview to production status.

Corpus design (deterministic, seed-locked):

  CORPUS-GOOD: 200 synthetic submissions per declared tool (4 tools = 800 total)
    Each submission has manifest.upstream_volumetry_tool set, and a single
    biomarker row with hippocampal_volume_total_cm3 drawn deterministically
    from the INTERIOR of that tool's normative range (lo+0.05 to hi-0.05).
    Expected flags from THIS pack: 0 across all 800 submissions.
    -> False-positive rate = (observed_flags / 800) on this corpus.

  CORPUS-BAD-BELOW: 100 synthetic submissions per declared tool (4 = 400)
    Value drawn below the tool's lo bound (lo - 0.5 to lo - 0.05).
    Expected flags: exactly 1 per submission, declared_tool matching manifest.
    -> True-positive rate = (observed_flags / 400) on this corpus.

  CORPUS-BAD-ABOVE: 100 synthetic submissions per declared tool (4 = 400)
    Value drawn above the tool's hi bound (hi + 0.05 to hi + 0.5).
    Expected flags: exactly 1 per submission, declared_tool matching manifest.

  CORPUS-EDGE: 8 submissions, one per (tool, boundary) testing
    the exact lo and hi values. By contract these should be IN-range
    (inclusive boundaries per the schema).

Total corpus: 1608 submissions, 1608 expected outcomes, audited reproducibly.

This script is *not* a unit test; it is an empirical validation that
runs once per release and whose results are pinned in the pack notes.
The unit tests in test_empirical_validation.py verify the script itself
is deterministic and the harness functions correctly; they do not
re-run the whole 1608-case validation on every pytest invocation.

Run with:
    python scripts/run_empirical_validation_tool_declaration.py

Output:
    JSON manifest of results, including:
      - observed_fp_count_corpus_good
      - observed_tp_count_corpus_bad_below
      - observed_tp_count_corpus_bad_above
      - observed_fp_count_corpus_edge
      - per-tool breakdown
      - hash of the input corpus (so future re-runs can verify byte-identity)
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neurotcs.cross_sheet import audit_cross_sheet, load_invariantpack

# Per-tool ranges, transcribed from the pack invariants. These are the
# *only* place in this script where the ranges are encoded; if they
# disagree with the YAML, the harness will report a discrepancy by
# producing unexpected FP counts.
TOOL_RANGES = {
    "neuroquant_5.0": (2.8, 5.0),
    "neuroreader":    (3.5, 5.5),
    "icometrix":      (2.8, 5.0),
    "quantib_nd":     (2.8, 5.0),
}

CORPUS_SEED = 42  # locked; do not change without bumping the validation revision
N_GOOD_PER_TOOL = 200
N_BAD_BELOW_PER_TOOL = 100
N_BAD_ABOVE_PER_TOOL = 100


@dataclass
class CorpusCase:
    case_id: str
    declared_tool: str
    value_cm3: float
    expected_flag_count: int
    bucket: str  # "good", "bad_below", "bad_above", "edge"


def _make_submission(case: CorpusCase) -> dict[str, Any]:
    return {
        "manifest": {"upstream_volumetry_tool": case.declared_tool},
        "biomarkers": [
            {
                "patient_id": f"synth_{case.case_id}",
                "visit_id": "v1",
                "hippocampal_volume_total_cm3": case.value_cm3,
            },
        ],
    }


def _build_corpus() -> list[CorpusCase]:
    """Deterministic corpus construction (seed-locked)."""
    rng = random.Random(CORPUS_SEED)
    cases: list[CorpusCase] = []

    # CORPUS-GOOD: interior values, expected 0 flags each
    for tool, (lo, hi) in TOOL_RANGES.items():
        interior_lo = lo + 0.05
        interior_hi = hi - 0.05
        for i in range(N_GOOD_PER_TOOL):
            val = rng.uniform(interior_lo, interior_hi)
            cases.append(
                CorpusCase(
                    case_id=f"good_{tool}_{i:03d}",
                    declared_tool=tool,
                    value_cm3=round(val, 4),
                    expected_flag_count=0,
                    bucket="good",
                )
            )

    # CORPUS-BAD-BELOW: value below lo
    for tool, (lo, _hi) in TOOL_RANGES.items():
        for i in range(N_BAD_BELOW_PER_TOOL):
            val = rng.uniform(lo - 0.5, lo - 0.05)
            cases.append(
                CorpusCase(
                    case_id=f"bad_below_{tool}_{i:03d}",
                    declared_tool=tool,
                    value_cm3=round(val, 4),
                    expected_flag_count=1,
                    bucket="bad_below",
                )
            )

    # CORPUS-BAD-ABOVE: value above hi
    for tool, (_lo, hi) in TOOL_RANGES.items():
        for i in range(N_BAD_ABOVE_PER_TOOL):
            val = rng.uniform(hi + 0.05, hi + 0.5)
            cases.append(
                CorpusCase(
                    case_id=f"bad_above_{tool}_{i:03d}",
                    declared_tool=tool,
                    value_cm3=round(val, 4),
                    expected_flag_count=1,
                    bucket="bad_above",
                )
            )

    # CORPUS-EDGE: exact boundary values (must be IN-range per schema)
    for tool, (lo, hi) in TOOL_RANGES.items():
        cases.append(
            CorpusCase(
                case_id=f"edge_{tool}_lo",
                declared_tool=tool,
                value_cm3=lo,
                expected_flag_count=0,
                bucket="edge",
            )
        )
        cases.append(
            CorpusCase(
                case_id=f"edge_{tool}_hi",
                declared_tool=tool,
                value_cm3=hi,
                expected_flag_count=0,
                bucket="edge",
            )
        )

    return cases


def _corpus_hash(cases: list[CorpusCase]) -> str:
    """SHA-256 of the canonical corpus representation."""
    payload = json.dumps(
        [
            {
                "case_id": c.case_id,
                "tool": c.declared_tool,
                "value": c.value_cm3,
                "expected": c.expected_flag_count,
                "bucket": c.bucket,
            }
            for c in cases
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_validation() -> dict[str, Any]:
    lp = load_invariantpack("cross_sheet/tool_declaration_consistency")
    cases = _build_corpus()
    corpus_sha = _corpus_hash(cases)

    by_bucket = {"good": [], "bad_below": [], "bad_above": [], "edge": []}
    by_tool_bucket: dict[tuple[str, str], dict[str, int]] = {}

    discrepancies: list[dict[str, Any]] = []

    for case in cases:
        submission = _make_submission(case)
        result = audit_cross_sheet(submission, [lp], dry_run=True)
        observed = len(result.flags)
        ok = observed == case.expected_flag_count

        key = (case.declared_tool, case.bucket)
        if key not in by_tool_bucket:
            by_tool_bucket[key] = {"n": 0, "observed_flags": 0, "discrepancies": 0}
        by_tool_bucket[key]["n"] += 1
        by_tool_bucket[key]["observed_flags"] += observed
        if not ok:
            by_tool_bucket[key]["discrepancies"] += 1
            discrepancies.append(
                {
                    "case_id": case.case_id,
                    "declared_tool": case.declared_tool,
                    "value_cm3": case.value_cm3,
                    "expected_flag_count": case.expected_flag_count,
                    "observed_flag_count": observed,
                    "bucket": case.bucket,
                }
            )

        by_bucket[case.bucket].append(observed)

    summary = {
        "pack": "cross_sheet/tool_declaration_consistency",
        "pack_yaml_sha256": lp.yaml_sha256,
        "pack_status": lp.status.value,
        "n_invariants": len(lp.invariantpack.invariants),
        "corpus_seed": CORPUS_SEED,
        "corpus_sha256": corpus_sha,
        "corpus_size_total": len(cases),
        "n_good": sum(1 for c in cases if c.bucket == "good"),
        "n_bad_below": sum(1 for c in cases if c.bucket == "bad_below"),
        "n_bad_above": sum(1 for c in cases if c.bucket == "bad_above"),
        "n_edge": sum(1 for c in cases if c.bucket == "edge"),
        "observed_total_flags_good": sum(by_bucket["good"]),
        "observed_total_flags_bad_below": sum(by_bucket["bad_below"]),
        "observed_total_flags_bad_above": sum(by_bucket["bad_above"]),
        "observed_total_flags_edge": sum(by_bucket["edge"]),
        "false_positive_rate_good": (
            sum(by_bucket["good"]) / max(1, sum(1 for c in cases if c.bucket == "good"))
        ),
        "true_positive_rate_bad_below": (
            sum(by_bucket["bad_below"]) / max(1, sum(1 for c in cases if c.bucket == "bad_below"))
        ),
        "true_positive_rate_bad_above": (
            sum(by_bucket["bad_above"]) / max(1, sum(1 for c in cases if c.bucket == "bad_above"))
        ),
        "false_positive_rate_edge": (
            sum(by_bucket["edge"]) / max(1, sum(1 for c in cases if c.bucket == "edge"))
        ),
        "n_discrepancies": len(discrepancies),
        "discrepancies": discrepancies[:20],  # cap to first 20 for output sanity
        "by_tool_bucket": {
            f"{k[0]}/{k[1]}": v for k, v in by_tool_bucket.items()
        },
    }
    return summary


if __name__ == "__main__":
    summary = run_validation()
    out_dir = Path(__file__).resolve().parent.parent / "validation_results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "tool_declaration_consistency_v1.11.0a5.json"
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True))

    print(f"Validation results written to: {out_path}")
    print()
    print(f"Pack: {summary['pack']}")
    print(f"Pack yaml_sha256: {summary['pack_yaml_sha256']}")
    print(f"Pack status: {summary['pack_status']}")
    print(f"Corpus seed: {summary['corpus_seed']}")
    print(f"Corpus SHA-256: {summary['corpus_sha256']}")
    print(f"Corpus size: {summary['corpus_size_total']}")
    print()
    print(f"CORPUS-GOOD       (n={summary['n_good']:4d}): "
          f"FP_rate = {summary['false_positive_rate_good']:.6f} "
          f"(observed {summary['observed_total_flags_good']} flags)")
    print(f"CORPUS-BAD-BELOW  (n={summary['n_bad_below']:4d}): "
          f"TP_rate = {summary['true_positive_rate_bad_below']:.6f} "
          f"(observed {summary['observed_total_flags_bad_below']} flags)")
    print(f"CORPUS-BAD-ABOVE  (n={summary['n_bad_above']:4d}): "
          f"TP_rate = {summary['true_positive_rate_bad_above']:.6f} "
          f"(observed {summary['observed_total_flags_bad_above']} flags)")
    print(f"CORPUS-EDGE       (n={summary['n_edge']:4d}): "
          f"FP_rate = {summary['false_positive_rate_edge']:.6f} "
          f"(observed {summary['observed_total_flags_edge']} flags)")
    print()
    print(f"Total discrepancies: {summary['n_discrepancies']}")
    if summary["n_discrepancies"] > 0:
        print("FAILED -- pack does not meet production-ready discipline")
        sys.exit(1)
    else:
        print("PASSED -- pack meets production-ready discipline")
        print("         (FP rate = 0.000000 on n=800 known-good corpus + n=8 edge cases)")
        print("         (TP rate = 1.000000 on n=400 known-bad-below + n=400 known-bad-above corpora)")
        sys.exit(0)

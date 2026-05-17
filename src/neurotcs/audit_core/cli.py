"""
NeuroTCS audit_core command-line interface.

Usage:
    python -m neurotcs.audit_core audit \\
        --predictions path/to/predictions.csv \\
        --rulepack ad/niaaa_2018 \\
        [--output report.json] \\
        [--bootstrap 10000] \\
        [--seed 42] \\
        [--ci-method bca|percentile] \\
        [--prior-type clinical|population] \\
        [--patient-col RID] \\
        [--date-col EXAMDATE] \\
        [--state-col DIAGNOSIS] \\
        [--probability-cols p_CN p_MCI p_AD] \\
        [--state-label-map Dementia=AD] \\
        [--include-per-patient]

Input CSV (or parquet) must have one row per (patient, visit) with at least
the patient_id, visit_date, and predicted state columns. Probability columns
are optional (enable uTCS weighting beyond cTCS).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from neurotcs.audit_core.audit import audit
from neurotcs.audit_core.trajectory import trajectories_from_dataframe
from neurotcs.rulepack.loader import load_rulepack


def _load_dataframe(path: Path) -> pd.DataFrame:
    """Load CSV or parquet by extension."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    elif suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    elif suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    else:
        raise ValueError(
            f"Unsupported file extension: {suffix}. Use .csv, .tsv, or .parquet."
        )


def _parse_label_map(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(
                f"--state-label-map entries must be 'OLD=NEW', got '{item}'"
            )
        old, new = item.split("=", 1)
        out[old] = new
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="neurotcs.audit_core",
        description="Audit a longitudinal medical AI model's predictions "
                    "against a citation-locked NeuroTCS rule pack.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser(
        "audit",
        help="Run the cTCS/pTCS/uTCS audit on a predictions file.",
    )
    p_audit.add_argument(
        "--predictions", required=True, type=Path,
        help="Path to predictions CSV/TSV/parquet (one row per visit).",
    )
    p_audit.add_argument(
        "--rulepack", required=True, type=str,
        help="Rule pack name (e.g. 'ad/niaaa_2018').",
    )
    p_audit.add_argument(
        "--output", type=Path, default=None,
        help="Output JSON report path. Default: print to stdout.",
    )
    p_audit.add_argument("--bootstrap", type=int, default=10_000,
                          help="Number of cluster-bootstrap resamples.")
    p_audit.add_argument("--seed", type=int, default=42)
    p_audit.add_argument("--ci-method", choices=["bca", "percentile"],
                          default="bca")
    p_audit.add_argument("--prior-type", choices=["clinical", "population"],
                          default="clinical")
    p_audit.add_argument("--patient-col", default="patient_id")
    p_audit.add_argument("--date-col", default="visit_date")
    p_audit.add_argument("--state-col", default="predicted_state")
    p_audit.add_argument("--probability-cols", nargs="+", default=None,
                          help="K probability columns enabling uTCS weighting.")
    p_audit.add_argument(
        "--state-label-map", nargs="+", default=[],
        metavar="OLD=NEW",
        help="Re-map state labels before scoring (repeatable).",
    )
    p_audit.add_argument(
        "--include-per-patient", action="store_true",
        help="Include per-patient score arrays in JSON output.",
    )
    p_audit.add_argument(
        "--quiet", action="store_true",
        help="Suppress the human-readable summary to stderr.",
    )

    args = parser.parse_args(argv)

    if args.command == "audit":
        df = _load_dataframe(args.predictions)
        label_map = _parse_label_map(args.state_label_map)
        trajectories = trajectories_from_dataframe(
            df,
            patient_id_col=args.patient_col,
            visit_date_col=args.date_col,
            state_col=args.state_col,
            probability_cols=args.probability_cols,
            state_label_map=(label_map if label_map else None),
        )

        rulepack = load_rulepack(args.rulepack)
        result = audit(
            trajectories,
            rulepack,
            bootstrap_B=args.bootstrap,
            seed=args.seed,
            ci_method=args.ci_method,
            prior_type=args.prior_type,
        )

        if not args.quiet:
            print(result.summary(), file=sys.stderr)

        report = result.to_json(
            indent=2, include_per_patient=args.include_per_patient,
        )
        if args.output is not None:
            args.output.write_text(report, encoding="utf-8")
            if not args.quiet:
                print(f"\nReport written to {args.output}", file=sys.stderr)
        else:
            print(report)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

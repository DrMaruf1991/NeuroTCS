"""
scripts/run_ad_fairness_audit.py
================================

Run the FUTURE-AI fairness audit (panel B.4.4) on a NeuroTCS-loaded AD cohort
and write a JSON report. Companion to scripts/run_aim3_miriad.py — same
runner pattern but produces fairness_report.json instead of (or alongside)
the aim3 longitudinal/test-retest reports.

Currently supports the MIRIAD cohort. ADNI and OASIS-3 support will be
added when their adapters extract demographic metadata into Trajectory.metadata.

Citation: Lekadir K et al.; FUTURE-AI Consortium. BMJ 2025;388:e081554.
          DOI 10.1136/bmj-2024-081554, PMID 39909534.

Usage:
    python scripts/run_ad_fairness_audit.py \\
        --cohort miriad \\
        --clinical /path/to/clinical.csv \\
        --sessions /path/to/sessions.csv \\
        --subjects /path/to/subjects.csv \\
        --rulepack ad/niaaa_2018 \\
        --out      /path/to/output_dir/

Output:
    {out}/ad_fairness_report.json   structured fairness report
    {out}/ad_fairness_summary.txt   human-readable summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import neurotcs
from neurotcs import audit, load_rulepack
from neurotcs.fairness import (
    FUTURE_AI_CITATION,
    FUTURE_AI_DOI,
    FUTURE_AI_PMID,
    cohort_fairness_audit,
)


def _fairness_to_dict(fairness_result, audit_result) -> dict:
    """Serialise a FairnessAuditResult plus the underlying audit metadata."""
    return {
        "neurotcs_version": neurotcs.__version__,
        "framework": {
            "citation": FUTURE_AI_CITATION,
            "doi": FUTURE_AI_DOI,
            "pmid": FUTURE_AI_PMID,
            "panel_id": fairness_result.panel_id,
            "recommendations": list(fairness_result.recommendations),
        },
        "audit": {
            "audit_id": audit_result.audit_id,
            "audit_id_v2": audit_result.audit_id_v2,
            "rulepack_id": audit_result.rulepack_id,
            "rulepack_sha256": audit_result.rulepack_sha256,
            "rulepack_schema_version": audit_result.rulepack_schema_version,
            "n_patients": audit_result.n_patients,
            "n_patients_scored": audit_result.n_patients_scored,
            "n_transitions": audit_result.n_transitions,
            "n_flagged": audit_result.n_flagged,
            "ctcs_point": audit_result.ctcs.ci.point,
            "ctcs_ci_low": audit_result.ctcs.ci.ci_low,
            "ctcs_ci_high": audit_result.ctcs.ci.ci_high,
            "bootstrap_B": audit_result.bootstrap_B,
            "seed": audit_result.seed,
        },
        "overall_flag_rate": fairness_result.overall_flag_rate,
        "max_disparity": fairness_result.max_disparity,
        "max_disparity_stratum": fairness_result.max_disparity_stratum,
        "strata": [
            {
                "attribute": s.stratum_name,
                "value": s.stratum_value,
                "n_transitions": s.n,
                "n_flagged": s.n_flagged,
                "flag_rate": s.flag_rate,
                "statistical_parity_vs_overall": s.statistical_parity,
            }
            for s in fairness_result.strata
        ],
    }


def _summary_text(fairness_dict: dict) -> str:
    """Human-readable summary of the fairness report."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(
        f"NeuroTCS v{fairness_dict['neurotcs_version']} — "
        f"AD Fairness Audit (FUTURE-AI Panel B.4.4)"
    )
    lines.append("=" * 70)
    lines.append(f"Framework citation: {fairness_dict['framework']['citation']}")
    lines.append(f"  DOI:  {fairness_dict['framework']['doi']}")
    lines.append(f"  PMID: {fairness_dict['framework']['pmid']}")
    lines.append("")
    lines.append("AUDIT CONTEXT")
    a = fairness_dict["audit"]
    lines.append(f"  rulepack_id        : {a['rulepack_id']}")
    lines.append(f"  rulepack_sha256    : {a['rulepack_sha256'][:16]}...")
    lines.append(f"  schema_version     : {a['rulepack_schema_version']}")
    lines.append(f"  audit_id           : {a['audit_id']}")
    lines.append(f"  audit_id_v2        : {a['audit_id_v2']}")
    lines.append(f"  n_patients         : {a['n_patients']}")
    lines.append(f"  n_transitions      : {a['n_transitions']}")
    lines.append(f"  n_flagged          : {a['n_flagged']}")
    lines.append(f"  cTCS               : {a['ctcs_point']:.4f} "
                 f"({a['ctcs_ci_low']:.4f}, {a['ctcs_ci_high']:.4f})")
    lines.append(f"  bootstrap          : B={a['bootstrap_B']}, seed={a['seed']}")
    lines.append("")
    lines.append("FAIRNESS SUMMARY")
    lines.append(f"  overall_flag_rate     : "
                 f"{100*fairness_dict['overall_flag_rate']:.3f}%")
    lines.append(f"  max_disparity         : "
                 f"{100*fairness_dict['max_disparity']:.3f}%")
    lines.append(f"  max_disparity_stratum : "
                 f"{fairness_dict['max_disparity_stratum']}")
    lines.append("")
    lines.append("PER-STRATUM FLAG RATES")
    lines.append(f"  {'attribute':<22} {'value':<14} {'n':>5} {'n_flag':>7} "
                 f"{'rate':>9} {'parity_vs_overall':>20}")
    lines.append("  " + "-" * 80)
    for s in fairness_dict["strata"]:
        lines.append(f"  {s['attribute']:<22} {str(s['value'])[:14]:<14} "
                     f"{s['n_transitions']:>5} {s['n_flagged']:>7} "
                     f"{100*s['flag_rate']:>8.3f}% "
                     f"{100*s['statistical_parity_vs_overall']:>+19.3f}%")
    lines.append("=" * 70)
    return "\n".join(lines)


def _run_miriad(args) -> int:
    """Load MIRIAD trajectories, run audit, run fairness audit, write output."""
    from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
        load_miriad_trajectories,
    )
    print(f"[1/4] Loading MIRIAD trajectories from {args.clinical}, "
          f"{args.sessions}, {args.subjects}")
    trajectories, report = load_miriad_trajectories(
        clinical_csv=args.clinical,
        sessions_csv=args.sessions,
        subjects_csv=args.subjects,
    )
    print(f"      loaded: {len(trajectories)} trajectories, "
          f"{report.n_transitions} transitions")

    if not trajectories:
        print("ERROR: no trajectories loaded; nothing to audit.")
        return 2

    print(f"[2/4] Loading rule pack: {args.rulepack}")
    pack = load_rulepack(args.rulepack)

    print(f"[3/4] Running audit (B={args.bootstrap_B}, seed={args.seed}) "
          f"with per-transition flag capture for fairness panel")
    result = audit(
        trajectories, pack,
        bootstrap_B=args.bootstrap_B,
        seed=args.seed,
        return_per_transition=True,
    )
    print(f"      cTCS={result.ctcs.ci.point:.4f}, "
          f"n_flagged={result.n_flagged}/{result.n_transitions} "
          f"({100*result.flagged_rate:.2f}%)")
    print(f"      audit_id    = {result.audit_id}")
    print(f"      audit_id_v2 = {result.audit_id_v2}")

    print("[4/4] Running fairness panel B.4.4 (FUTURE-AI BMJ 2025)")
    fairness = cohort_fairness_audit(result)
    print(f"      max disparity: {100*fairness.max_disparity:.3f}% "
          f"at stratum '{fairness.max_disparity_stratum}'")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fairness_dict = _fairness_to_dict(fairness, result)
    (out_dir / "ad_fairness_report.json").write_text(
        json.dumps(fairness_dict, indent=2, default=str)
    )
    summary = _summary_text(fairness_dict)
    (out_dir / "ad_fairness_summary.txt").write_text(summary)
    print()
    print(summary)
    print(f"\nFiles written to: {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run FUTURE-AI fairness audit on a NeuroTCS-loaded AD cohort."
    )
    parser.add_argument("--cohort", required=True,
                          choices=["miriad"],
                          help="Cohort to audit. Currently: miriad. "
                               "adni/oasis3 pending demographic-extraction "
                               "support in their adapters.")
    parser.add_argument("--clinical", required=True, type=Path,
                          help="Path to clinical CSV (MIRIAD: clinical assessment).")
    parser.add_argument("--sessions", required=True, type=Path,
                          help="Path to sessions CSV (MIRIAD: MR sessions).")
    parser.add_argument("--subjects", required=True, type=Path,
                          help="Path to subjects CSV (MIRIAD: demographics).")
    parser.add_argument("--rulepack", default="ad/niaaa_2018",
                          help="Rule pack ID (default: ad/niaaa_2018).")
    parser.add_argument("--out", required=True, type=Path,
                          help="Output directory for fairness report files.")
    parser.add_argument("--bootstrap-B", type=int, default=10_000,
                          help="Bootstrap resamples (default 10000).")
    parser.add_argument("--seed", type=int, default=42,
                          help="Reproducibility seed (default 42).")

    args = parser.parse_args(argv)

    if args.cohort == "miriad":
        return _run_miriad(args)
    # Future: elif args.cohort == "adni": ...
    # Future: elif args.cohort == "oasis3": ...

    print(f"ERROR: cohort '{args.cohort}' not supported yet.")
    return 2


if __name__ == "__main__":
    sys.exit(main())

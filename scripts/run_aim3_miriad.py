#!/usr/bin/env python3
"""
run_aim3_miriad.py — Standalone Aim 3 MIRIAD audit runner.

Runs both halves of the Aim 3 design on actual MIRIAD XNAT CSVs:

  (A) Longitudinal cTCS replication — third-cohort independent replication
      alongside Aim 1 (ADNI cTCS=0.9946) and Aim 2 (OASIS-3 cTCS=0.9942).
  (B) Test-retest measurement-noise floor — back-to-back same-session
      scans (weeks 0, 6, 38) passed through the audit kernel; the
      flag rate is the empirical noise floor.

Usage:
    python scripts/run_aim3_miriad.py \\
        --clinical "$NEUROTCS_MIRIAD_DIR/DrMaruf_5_18_2026_12_16_7.csv" \\
        --sessions "$NEUROTCS_MIRIAD_DIR/DrMaruf_5_18_2026_12_16_24.csv" \\
        --subjects "$NEUROTCS_MIRIAD_DIR/DrMaruf_5_18_2026_12_16_33.csv" \\
        --out      "$NEUROTCS_MIRIAD_DIR/MIRIAD_audit_results"

The --subjects argument is optional (the adapter falls back to
subject-ID-based group inference if no Subjects CSV is provided).

Outputs (in --out directory):
    aim3_longitudinal_audit.json    Full longitudinal AuditResult
    aim3_longitudinal_report.json   Adapter diagnostic counts
    aim3_test_retest_audit.json     Full test-retest AuditResult
    aim3_test_retest_report.json    Test-retest pair counts
    aim3_summary.txt                Human-readable summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    load_miriad_test_retest_pairs,
    load_miriad_trajectories,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aim 3 MIRIAD audit (longitudinal + test-retest)"
    )
    parser.add_argument("--clinical", required=True,
                        help="Path to ClinicalAssessment CSV "
                             "(per-visit MMSE)")
    parser.add_argument("--sessions", required=True,
                        help="Path to MR Sessions CSV (age-at-scan)")
    parser.add_argument("--subjects", default=None,
                        help="Optional path to Subjects CSV; if omitted, "
                             "group is inferred from subject IDs (Malone 2013 "
                             "convention: ids 188-233 = AD, 234+ = CN)")
    parser.add_argument("--out", required=True,
                        help="Output directory for results")
    parser.add_argument("--bootstrap-B", type=int, default=10_000,
                        help="Bootstrap resample count (default 10,000)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Reproducibility seed (default 42)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pack = load_rulepack("ad/niaaa_2018")
    summary_lines: list[str] = []

    # ---- (A) Longitudinal cTCS replication ----
    print()
    print("=" * 70)
    print("Aim 3 (A) — Longitudinal cTCS replication")
    print("=" * 70)
    trajectories, long_report = load_miriad_trajectories(
        clinical_csv=args.clinical,
        sessions_csv=args.sessions,
        subjects_csv=args.subjects,
    )
    print(f"Loaded: {len(trajectories)} trajectories, "
          f"{long_report.n_transitions} transitions")
    print(f"        rows_with_mmse={long_report.rows_with_mmse}, "
          f"unmappable_mmse={long_report.unmappable_mmse}")
    print(f"        mmse_forward_filled (visits w/o per-visit MMSE): "
          f"{long_report.mmse_forward_filled}")
    print(f"        group↔MMSE broad disagreements: "
          f"{long_report.group_mmse_disagreements}")
    print(f"        group↔MMSE state-DISCORDANT (clinically meaningful): "
          f"{long_report.group_mmse_state_discordant}")
    print(f"        test-retest scans excluded: "
          f"{long_report.n_test_retest_visits_excluded}")

    if len(trajectories) == 0:
        print("\nERROR: No valid trajectories built. Check the diagnostic "
              "counts above — likely an MMSE coverage problem or a "
              "column-name mismatch.")
        return 2

    long_result = audit(
        trajectories, pack,
        bootstrap_B=args.bootstrap_B, seed=args.seed,
    )
    print()
    print(long_result.summary())

    (out_dir / "aim3_longitudinal_audit.json").write_text(
        long_result.to_json(indent=2)
    )
    (out_dir / "aim3_longitudinal_report.json").write_text(
        json.dumps(long_report.to_dict(), indent=2)
    )

    summary_lines.append("AIM 3 (A) — LONGITUDINAL cTCS REPLICATION")
    summary_lines.append(f"  trajectories       : {len(trajectories)}")
    summary_lines.append(f"  n_transitions      : {long_result.n_transitions}")
    summary_lines.append(f"  n_flagged          : {long_result.n_flagged} "
                         f"({100 * long_result.flagged_rate:.2f}%)")
    summary_lines.append(f"  cTCS               : {long_result.ctcs.ci.point:.4f} "
                         f"({long_result.ctcs.ci.ci_low:.4f}, "
                         f"{long_result.ctcs.ci.ci_high:.4f})")
    if long_result.ptcs.available:
        summary_lines.append(f"  pTCS (clinical)    : "
                             f"{long_result.ptcs.ci.point:.4f}")
    summary_lines.append(f"  uTCS               : {long_result.utcs.ci.point:.4f}")
    summary_lines.append(f"  audit_id           : {long_result.audit_id}")
    summary_lines.append(f"  audit_id_v2        : {long_result.audit_id_v2}")
    summary_lines.append("")
    summary_lines.append(f"  mmse_forward_filled    : {long_report.mmse_forward_filled}")
    summary_lines.append(f"  group/MMSE broad       : {long_report.group_mmse_disagreements}")
    summary_lines.append(f"  group/MMSE discordant  : {long_report.group_mmse_state_discordant}")
    summary_lines.append(f"  test-retest scans excl : {long_report.n_test_retest_visits_excluded}")
    summary_lines.append("")
    summary_lines.append(f"  delta cTCS vs ADNI(0.9946)    : "
                         f"{long_result.ctcs.ci.point - 0.9946:+.4f}")
    summary_lines.append(f"  delta cTCS vs OASIS-3(0.9942) : "
                         f"{long_result.ctcs.ci.point - 0.9942:+.4f}")
    summary_lines.append("")

    # ---- (B) Test-retest noise floor ----
    print()
    print("=" * 70)
    print("Aim 3 (B) — Test-retest measurement-noise floor")
    print("=" * 70)
    pairs, pair_report = load_miriad_test_retest_pairs(
        clinical_csv=args.clinical,
        sessions_csv=args.sessions,
    )
    print(f"Loaded: {pair_report.n_rescan_pairs} same-session pairs identified")
    print(f"        {pair_report.n_subjects_with_rescan} subjects with rescans")
    print(f"        {pair_report.n_rescan_pairs_with_mmse} pairs with MMSE")
    print(f"        identical-state pairs: "
          f"{pair_report.n_pairs_state_identical}")
    print(f"        differing-state pairs: "
          f"{pair_report.n_pairs_state_differs}")

    if len(pairs) == 0:
        print()
        print("WARN: No audit-ready test-retest pairs. Skipping audit_id.")
        summary_lines.append("AIM 3 (B) — TEST-RETEST NOISE FLOOR")
        summary_lines.append(f"  pairs identified   : {pair_report.n_rescan_pairs}")
        summary_lines.append(f"  pairs with MMSE    : "
                             f"{pair_report.n_rescan_pairs_with_mmse}")
        summary_lines.append("  pairs audit-ready  : 0")
        summary_lines.append("")
    else:
        pair_result = audit(
            pairs, pack,
            bootstrap_B=args.bootstrap_B, seed=args.seed,
        )
        print()
        print(pair_result.summary())

        (out_dir / "aim3_test_retest_audit.json").write_text(
            pair_result.to_json(indent=2)
        )

        summary_lines.append("AIM 3 (B) — TEST-RETEST NOISE FLOOR")
        summary_lines.append(f"  pairs              : {len(pairs)}")
        summary_lines.append(f"  identical-state    : "
                             f"{pair_report.n_pairs_state_identical}")
        summary_lines.append(f"  differing-state    : "
                             f"{pair_report.n_pairs_state_differs}")
        summary_lines.append(f"  flag_rate          : "
                             f"{100 * pair_result.flagged_rate:.3f}%")
        summary_lines.append(f"  cTCS               : "
                             f"{pair_result.ctcs.ci.point:.4f}")
        summary_lines.append(f"  audit_id           : {pair_result.audit_id}")
        summary_lines.append(f"  audit_id_v2        : {pair_result.audit_id_v2}")
        summary_lines.append("")

    (out_dir / "aim3_test_retest_report.json").write_text(
        json.dumps(pair_report.to_dict(), indent=2)
    )

    import neurotcs
    # ---- Write summary ----
    summary_text = (
        "=" * 70 + "\n"
        + f"NeuroTCS v{neurotcs.__version__} — Aim 3 MIRIAD Audit Results\n"
        + "=" * 70 + "\n\n"
        + "\n".join(summary_lines)
        + "\n" + "=" * 70 + "\n"
        + "Files written to:\n"
        + f"  {out_dir}\n"
        + "=" * 70 + "\n"
    )
    (out_dir / "aim3_summary.txt").write_text(summary_text)
    print()
    print(summary_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())

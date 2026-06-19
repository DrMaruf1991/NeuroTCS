"""Runner for the Arm B validation harness.

Executes the standard, supported NeuroTCS audit CLI on a (corrupted) cohort
workbook and returns the parsed flags dict from the bundle. Using the public
CLI -- rather than importing internal audit functions -- keeps the harness
decoupled from internal APIs and guarantees it exercises the same code path a
real user runs.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_audit_flags(
    cohort_path: str | Path,
    *,
    confirm_assays: bool = True,
    allow_no_dates: bool = True,
    extra_args: tuple[str, ...] = (),
) -> dict:
    """Run `neurotcs audit` on ``cohort_path`` and return the flags dict.

    Returns the bundle's deterministic_core['flags'] (a dict keyed by severity
    tier). Raises RuntimeError if the audit does not produce a bundle.
    """
    cohort_path = Path(cohort_path)
    with tempfile.TemporaryDirectory() as td:
        outdir = Path(td)
        cmd = [
            sys.executable, "-m", "neurotcs.cli", "audit", str(cohort_path),
            "-o", str(outdir),
        ]
        if confirm_assays:
            cmd.append("--confirm-assays")
        if allow_no_dates:
            cmd.append("--allow-no-dates")
        cmd.extend(extra_args)
        subprocess.run(cmd, capture_output=True, text=True, check=False)
        bundles = list(outdir.glob("*.bundle.json"))
        if not bundles:
            raise RuntimeError(
                "NeuroTCS audit produced no bundle for "
                f"{cohort_path.name}; cannot score Arm B detection. "
                "Arm B injects errors into biomarker fields (e.g. FL plasma/"
                "csf, AM centiloid), but a cohort that produces no bundle "
                "cannot be scored. A valid validate-coverage cohort needs "
                "BOTH a staging axis (a clinical_stage or biological_stage "
                "column whose states match a rule pack, so the cohort audits "
                "to a bundle) AND injectable biomarker fields. A biomarker-"
                "only workbook will not bundle. See docs/VALIDATION_PROTOCOL.md."
            )
        bundle = json.loads(bundles[0].read_text())
        core = bundle["neurotcs_bundle"]["deterministic_core"]
        return core.get("flags", {}) or {}

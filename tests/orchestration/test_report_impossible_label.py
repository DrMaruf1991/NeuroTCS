"""Finding #8: the report 'Impossible' severity line must not claim a single
layer. Impossible-tier flags are produced by data_integrity AND clinical_ranges
(schema.py: 'physically/biologically impossible. Always flagged.') AND staging
transitions, so labelling the cross-layer impossible COUNT as '(data-integrity)'
is inaccurate. The label must describe the severity, not a presumed layer.

The report is a rendered view (never hashed), so this label is cosmetic to the
bundle -- but for a precision tool an inaccurate label undercuts trust, and the
per-flag 'layer' field already carries the true origin for anyone who needs it.
"""
from __future__ import annotations

import pandas as pd

from neurotcs.io import tables_to_submission
from neurotcs.orchestration.bundle import build_bundle, render_report
from neurotcs.orchestration.orchestrator import run_full_audit


def _report_for(df: pd.DataFrame) -> str:
    sub = tables_to_submission(
        {"S": df},
        {"clinical": {"sheet": "S", "subject_id": "subject_id", "visit": "visit",
                      "visit_date": None, "state": "state"}},
    )
    res = run_full_audit(sub)
    bundle = build_bundle(res, input_fingerprint="x", input_warnings=[])
    # use_symbols=False -> plain ASCII labels, stable to assert on.
    return render_report(bundle, use_symbols=False)


def test_impossible_severity_line_does_not_claim_data_integrity_layer():
    """The summary 'Impossible' line must not hardcode '(data-integrity)':
    impossible-tier flags span data_integrity, clinical_ranges, and staging."""
    df = pd.DataFrame({
        "subject_id": ["A", "A", "A"],
        "visit": [0, 1, 2],
        "state": ["CN", "MCI", "AD"],
    })
    report = _report_for(df)
    assert "Impossible" in report
    assert "Impossible (data-integrity)" not in report, (
        "report mislabels the cross-layer impossible severity as data-integrity")


def test_impossible_line_uses_severity_wording():
    """Positive: the line describes the severity ('hard violations')."""
    df = pd.DataFrame({
        "subject_id": ["A", "A"],
        "visit": [0, 1],
        "state": ["CN", "MCI"],
    })
    report = _report_for(df)
    assert "Impossible (hard violations)" in report

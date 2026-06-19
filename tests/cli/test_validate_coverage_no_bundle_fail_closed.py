"""Defect 2 regression: validate-coverage fails closed (EXIT_INPUT) when
run_audit_flags raises its documented no-bundle RuntimeError, instead of leaking
a traceback as exit 1. Tests the boundary extension directly (isolated from
inject_errors cell-count math and from a real subprocess audit).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from neurotcs import cli
from neurotcs.cli import EXIT_CLEAN, EXIT_INPUT
import neurotcs.validation as _val


def _tiny_cohort(tmp_path: Path) -> Path:
    f = tmp_path / "cohort.xlsx"
    pd.DataFrame({
        "subject_id": ["S0", "S1"],
        "visit": [0, 1],
        "visit_date": ["2020-01-01", "2021-01-01"],
        "mmse_total": [28, 27],
    }).to_excel(f, index=False)
    return f


def _args(cohort: Path):
    return cli.build_parser().parse_args([
        "validate-coverage", str(cohort), "--seed", "42",
        "--n-high", "1", "--n-unit", "0", "--n-decimal", "0",
        "--n-sign", "0", "--n-categorical", "0",
    ])


def test_no_bundle_runtimeerror_is_caught(tmp_path, monkeypatch, capsys):
    cohort = _tiny_cohort(tmp_path)

    def _inject_ok(*_a, **_k):
        return {"injected": []}  # dummy manifest; only its presence matters here

    def _raise_no_bundle(*_a, **_k):
        raise RuntimeError(
            "NeuroTCS audit produced no bundle for cohort.xlsx; "
            "cannot score Arm B detection.")

    def _must_not_reach(*_a, **_k):  # pragma: no cover
        raise AssertionError("score_detection reached on the error path")

    monkeypatch.setattr(_val, "inject_errors", _inject_ok, raising=True)
    monkeypatch.setattr(_val, "run_audit_flags", _raise_no_bundle, raising=True)
    monkeypatch.setattr(_val, "score_detection", _must_not_reach, raising=True)

    rc = cli.cmd_validate_coverage(_args(cohort))
    assert rc == EXIT_INPUT, f"expected EXIT_INPUT(4), got {rc}"
    err = capsys.readouterr().err.lower()
    assert "no bundle" in err or "cannot score" in err, err


def test_happy_path_still_clean(tmp_path, monkeypatch):
    """All three stages succeed -> EXIT_CLEAN; the boundary extension is
    transparent on success."""
    cohort = _tiny_cohort(tmp_path)

    class _Report:
        total_injected = 1
        total_detected = 1
        overall_coverage = 1.0
        overall_coverage_ci = (0.5, 1.0)
        specificity = 1.0
        specificity_ci = (0.9, 1.0)
        per_type = []
        def to_dict(self):
            return {"ok": True}

    monkeypatch.setattr(_val, "inject_errors", lambda *_a, **_k: {"injected": []},
                        raising=True)
    monkeypatch.setattr(_val, "run_audit_flags", lambda *_a, **_k: {}, raising=True)
    monkeypatch.setattr(_val, "score_detection", lambda *_a, **_k: _Report(),
                        raising=True)

    rc = cli.cmd_validate_coverage(_args(cohort))
    assert rc == EXIT_CLEAN, f"expected EXIT_CLEAN(0), got {rc}"

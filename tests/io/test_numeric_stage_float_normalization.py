"""Statistical formats (SPSS/RDS) read integer stage codes as float64 (1 -> 1.0)
because they have no integer type. The vocabulary match must normalize integer-
valued floats so such cohorts stage identically to integer-coded CSV/DTA, instead
of being refused for a spurious '1.0'-vs-'1' vocabulary mismatch (P1 #5).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.cli import main as cli_main


def _audit_status(path: Path, tmp_path: Path) -> tuple[str, list[str]]:
    out = tmp_path / "out"
    cli_main(["audit", str(path), "-o", str(out)])
    bundle = json.loads(next(out.glob("*.bundle.json")).read_text(encoding="utf-8"))
    core = bundle["neurotcs_bundle"]["deterministic_core"]
    axes = [a.get("layer", a.get("axis", "")) for a in core.get("axes", [])]
    return core["status"], axes


def _df() -> pd.DataFrame:
    return pd.DataFrame({
        "subject_id": ["S1", "S1", "S2", "S2"],
        "visit": [0, 1, 0, 1],
        "visit_date": ["2020-01-01", "2021-01-01", "2020-06-01", "2021-06-01"],
        "clinical_stage": [0, 1, 0, 2],  # integer-coded ordinal stages
    })


def test_csv_integer_stage_audits_clean(tmp_path):
    csv = tmp_path / "numstage.csv"
    _df().to_csv(csv, index=False)
    status, _ = _audit_status(csv, tmp_path)
    assert status == "CLEAN"


def test_sav_float_stage_audits_like_csv(tmp_path):
    pyreadstat = pytest.importorskip("pyreadstat")
    sav = tmp_path / "numstage.sav"
    pyreadstat.write_sav(_df(), str(sav))
    # pyreadstat reads integer codes back as float64 (1 -> 1.0); the vocabulary
    # match must normalize integer-valued floats so this is not refused.
    status, _ = _audit_status(sav, tmp_path)
    assert status == "CLEAN", (
        f"SAV numeric-stage cohort should audit CLEAN like CSV, got {status} "
        f"(integer-valued-float normalization regressed)")

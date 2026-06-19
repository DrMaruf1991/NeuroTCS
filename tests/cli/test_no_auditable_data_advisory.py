"""An empty cohort (every input table has zero data rows) returns CLEAN but
records a non-hashed run_metadata.advisories['no_auditable_data'] note, so the
vacuous-CLEAN result reads honestly. A non-empty cohort must NOT get the advisory
(the detector is input-shape based, narrow -- it does not misfire on a real
cohort that merely yields zero transitions).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from neurotcs.cli import main as cli_main


def _audit(tmp_path: Path, df: pd.DataFrame, name: str) -> dict:
    src = tmp_path / f"{name}.csv"
    df.to_csv(src, index=False)
    out = tmp_path / f"{name}_out"
    cli_main(["audit", str(src), "-o", str(out), "--quiet"])
    return json.loads(next(out.glob("*.bundle.json")).read_text(encoding="utf-8"))


def test_empty_cohort_records_no_auditable_data_advisory(tmp_path):
    bundle = _audit(tmp_path, pd.DataFrame({
        "subject_id": [], "visit": [], "visit_date": [], "clinical_stage": [],
    }), "empty")
    nb = bundle["neurotcs_bundle"]
    # Status contract preserved: empty input is still CLEAN.
    assert nb["deterministic_core"]["status"] == "CLEAN"
    # But the honest no-data signal is present (in NON-hashed run_metadata).
    adv = nb["run_metadata"].get("advisories", {})
    assert "no_auditable_data" in adv, f"advisories: {adv}"
    assert "vacuous" in adv["no_auditable_data"]["reason"].lower()
    assert adv["no_auditable_data"]["tables"] == {"empty": 0}


def test_real_cohort_does_not_misfire(tmp_path):
    """A real cohort (incl. a single-visit subject that yields zero transitions)
    must NOT receive the no-data advisory -- the detector is input-shape based,
    not transition-count based."""
    bundle = _audit(tmp_path, pd.DataFrame({
        "subject_id": ["S1", "S1", "S2"],
        "visit": [0, 1, 0],
        "visit_date": ["2020-01-01", "2021-01-01", "2020-06-01"],
        "clinical_stage": ["CN", "MCI", "CN"],
    }), "real")
    nb = bundle["neurotcs_bundle"]
    adv = nb["run_metadata"].get("advisories", {})
    assert "no_auditable_data" not in adv, f"misfired: {adv}"

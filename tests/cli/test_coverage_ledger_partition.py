"""Coverage-ledger correctness (audit round 4):

  * A per-visit treatment / TRAC column wired into biological staging is
    credited as CONSUMED, not parked in columns_ignored (P1 #3).
  * A recognized assay-calibrated biomarker (hippocampus_total_mm3) is REFUSED
    with a reason, not silently ignored (P1 #4).
  * The four coverage categories partition the present columns -- no column
    appears in more than one (P1 #8 / checklist #9).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from neurotcs.cli import main as cli_main


def _audit(tmp_path: Path, df: pd.DataFrame, sheet: str, *, confirm: bool) -> dict:
    src = tmp_path / "cohort.xlsx"
    df.to_excel(src, sheet_name=sheet, index=False)
    out = tmp_path / "out"
    args = ["audit", str(src), "-o", str(out)]
    if confirm:
        args.append("--confirm-assays")
    cli_main(args)
    bundle = json.loads(next(out.glob("*.bundle.json")).read_text(encoding="utf-8"))
    core = bundle["neurotcs_bundle"]["deterministic_core"]
    for v in core.values():
        if isinstance(v, dict) and any(k.startswith("columns_") for k in v):
            return v
    raise AssertionError("no coverage ledger found in bundle")


def _df():
    return pd.DataFrame({
        "subject_id": ["S1", "S1", "S2", "S2"],
        "visit": [0, 1, 0, 1],
        "visit_date": ["2020-01-01", "2021-01-01", "2020-06-01", "2021-06-01"],
        "clinical_stage": ["CN", "MCI", "CN", "MCI"],
        "biological_stage": ["A", "A", "B", "B"],
        "trac_status": ["none", "anti_amyloid_active", "none", "none"],
        "hippocampus_total_mm3": [3200, 3100, 3000, 2900],
    })


def _flatten(cat: dict) -> set[str]:
    """Flatten a {sheet: [cols]} or {sheet.col: reason} ledger category to a set
    of plain column names."""
    out: set[str] = set()
    if not isinstance(cat, dict):
        return out
    for k, v in cat.items():
        if isinstance(v, list):  # {sheet: [cols]}
            out.update(v)
        else:  # {"sheet.col": reason}
            col = k.split(".", 1)[1] if "." in k else k
            out.add(col)
    return out


def test_trac_status_is_consumed_not_ignored(tmp_path):
    led = _audit(tmp_path, _df(), "Clinical", confirm=True)
    consumed = _flatten(led.get("columns_consumed", {}))
    ignored = _flatten(led.get("columns_ignored", {}))
    assert "trac_status" in consumed, f"consumed={consumed}"
    assert "trac_status" not in ignored


def test_hippocampus_is_refused_not_ignored(tmp_path):
    led = _audit(tmp_path, _df(), "Clinical", confirm=False)
    refused = _flatten(led.get("columns_refused", {}))
    ignored = _flatten(led.get("columns_ignored", {}))
    assert "hippocampus_total_mm3" in refused, f"refused={refused}"
    assert "hippocampus_total_mm3" not in ignored


def test_coverage_categories_partition(tmp_path):
    """No column may appear in more than one of the four coverage categories."""
    for confirm in (False, True):
        led = _audit(tmp_path, _df(), "Clinical", confirm=confirm)
        cats = {
            name: _flatten(led.get(name, {}))
            for name in ("columns_consumed", "columns_ignored",
                         "columns_refused", "columns_unwired")
        }
        names = list(cats)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                overlap = cats[names[i]] & cats[names[j]]
                assert not overlap, (
                    f"confirm={confirm}: {names[i]} & {names[j]} overlap: {overlap}")

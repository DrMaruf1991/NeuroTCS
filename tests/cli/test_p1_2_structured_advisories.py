"""P1-2 regression: opt-in advisory layers (disease-control partition, conversion
audit) are recorded as STRUCTURED, machine-readable objects in
run_metadata.advisories -- not only as human-readable warning strings -- AND
without perturbing the hashed deterministic core (bundle_id unchanged).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from neurotcs.cli import main as cli_main


def _audit(workdir: Path, *flags: str) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "subject_id": ["S1", "S1", "S2", "S2"],
        "visit": [0, 1, 0, 1],
        "visit_date": ["2020-01-01", "2021-01-01", "2020-06-01", "2021-06-01"],
        "clinical_stage": ["CN", "MCI", "DLB", "DLB"],
    })
    src = workdir / "dc.csv"
    df.to_csv(src, index=False)
    out = workdir / "out"
    cli_main(["audit", str(src), "-o", str(out), "--quiet", *flags])
    return json.loads(next(out.glob("*.bundle.json")).read_text(encoding="utf-8"))


def test_disease_control_partition_is_structured(tmp_path):
    bundle = _audit(tmp_path / "dc", "--partition-disease-controls")
    adv = bundle["neurotcs_bundle"]["run_metadata"].get("advisories", {})
    assert "disease_control_partition" in adv, f"advisories: {adv}"
    dcp = adv["disease_control_partition"]
    # Machine-readable structure: subject S2 -> DLB, with citation anchors.
    assert dcp["by_category"].get("DLB") == ["S2"], dcp
    assert dcp["recognized"]["S2"]["category"] == "DLB", dcp
    assert dcp["ontology_id"], "ontology_id must be recorded"
    assert dcp["ontology_sha256"], "ontology_sha256 must be recorded"
    assert dcp["n_recognized"] == 1


def test_advisories_do_not_change_bundle_id(tmp_path):
    """Advisories live in non-hashed run_metadata: bundle_id must be identical
    with and without the opt-in flag (same deterministic core)."""
    b_noflag = _audit(tmp_path / "noflag")
    b_flag = _audit(tmp_path / "flag", "--partition-disease-controls")
    id_noflag = b_noflag["neurotcs_bundle"]["bundle_id"]
    id_flag = b_flag["neurotcs_bundle"]["bundle_id"]
    assert id_noflag == id_flag, (
        f"bundle_id changed: advisories must not touch the hashed core "
        f"({id_noflag[:16]} != {id_flag[:16]})")
    assert not b_noflag["neurotcs_bundle"]["run_metadata"].get("advisories")
    assert b_flag["neurotcs_bundle"]["run_metadata"]["advisories"]

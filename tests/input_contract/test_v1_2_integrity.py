"""Tests for NeuroTCS Input Contract validator v1.2.0 data-integrity additions.

v1.22.0 architecture refactor: data-integrity checks belong in the input
contract, not in the citation-locked clinical coherence invariant pack. This
file proves the two checks moved here fire correctly on planted controls:

  - DEMOGRAPHIC_IMPLAUSIBLE  -- impossible age (E002) / negative education (E003)
  - BIOMARKER_PATIENT_ORPHAN -- a biomarker row whose patient_id is absent from
                                the cohort (E022)

The harness builds known-good and known-bad submissions and confirms the
validator's behavior on each (test-the-harness-on-controls discipline).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.input_contract.v1_2.validate import validate_submission

# v1.36.0: jsonschema is declared as a hard dep in pyproject.toml, but environments
# without it should SKIP cleanly rather than raise RuntimeError. Same discipline as
# the v1.33.2 pyarrow guard in tests/io/test_readers.py.
try:
    import jsonschema  # noqa: F401
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

pytestmark = pytest.mark.skipif(
    not _HAS_JSONSCHEMA,
    reason=(
        "jsonschema not installed; declared as a hard dep in pyproject.toml. "
        "Install with: pip install jsonschema   (or: pip install -e .)"
    ),
)


def _write_submission(
    tmp_path: Path,
    *,
    patients: pd.DataFrame,
    predictions: pd.DataFrame,
    biomarkers: pd.DataFrame | None = None,
    level: str = "L2",
) -> Path:
    sub = tmp_path / "sub"
    sub.mkdir()
    predictions.to_parquet(sub / "predictions.parquet")
    patients.to_parquet(sub / "patients.parquet")
    data_files = {
        "predictions": "predictions.parquet",
        "patients": "patients.parquet",
    }
    if biomarkers is not None:
        biomarkers.to_parquet(sub / "biomarkers.parquet")
        data_files["biomarkers"] = "biomarkers.parquet"
    manifest = {
        "neurotcs_contract_version": "1.2.0",
        "conformance_level": level,
        "submission_id": "test_v1_2_integrity",
        "submission_timestamp": "2026-05-28T00:00:00Z",
        "source_system": {"name": "TestModel", "version": "0.1.0", "vendor": "self"},
        "disease_domain": "alzheimers",
        "rule_pack": {"id": "aa2024+trac@1.0", "source": "registry"},
        "data_files": data_files,
        "cohort_summary": {
            "n_patients": int(predictions["patient_id"].nunique()),
            "n_visits_total": int(len(predictions)),
            "date_range": ["2018-01-01", "2025-12-31"],
        },
    }
    (sub / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return sub


def _base_predictions() -> pd.DataFrame:
    return pd.DataFrame({
        "patient_id": ["P001", "P001", "P002", "P002"],
        "visit_id": ["v1", "v2", "v1", "v2"],
        "visit_timestamp": [
            "2020-01-01T00:00:00Z", "2020-07-01T00:00:00Z",
            "2020-02-01T00:00:00Z", "2020-08-01T00:00:00Z",
        ],
        "predicted_state": ["MCI", "MCI", "CN", "CN"],
        "uncertainty": [0.8, 0.8, 0.8, 0.8],
        "treatment_flags": [[], [], [], []],
    })


def _patients(ages, edus=None):
    df = pd.DataFrame({
        "patient_id": ["P001", "P002"],
        "sex": ["female", "male"],
        "age_at_baseline": ages,
        "race_ethnicity": ["white", "asian"],
        "site_id": ["s1", "s1"],
        "scanner_vendor": ["siemens", "siemens"],
    })
    if edus is not None:
        df["education_years"] = edus
    return df


def _codes(report):
    return [e.code for e in report.errors]


# ---------- controls: clean submission must NOT fire ----------

def test_clean_demographics_no_flag(tmp_path):
    sub = _write_submission(
        tmp_path,
        patients=_patients([72, 68], [16, 12]),
        predictions=_base_predictions(),
    )
    report = validate_submission(sub)
    assert "DEMOGRAPHIC_IMPLAUSIBLE" not in _codes(report)


# ---------- E002: impossible age ----------

def test_impossible_age_flagged(tmp_path):
    sub = _write_submission(
        tmp_path,
        patients=_patients([142, 68], [16, 12]),  # 142 is impossible
        predictions=_base_predictions(),
    )
    report = validate_submission(sub)
    assert "DEMOGRAPHIC_IMPLAUSIBLE" in _codes(report)


# ---------- E003: negative education ----------

def test_negative_education_flagged(tmp_path):
    sub = _write_submission(
        tmp_path,
        patients=_patients([72, 68], [-3, 12]),  # -3 is impossible
        predictions=_base_predictions(),
    )
    report = validate_submission(sub)
    assert "DEMOGRAPHIC_IMPLAUSIBLE" in _codes(report)


# ---------- E022: orphan biomarker patient ----------

def test_biomarker_patient_orphan_flagged(tmp_path):
    bio = pd.DataFrame({
        "patient_id": ["P001", "ORPHAN999"],  # ORPHAN999 not in predictions
        "visit_id": ["v1", "v1"],
        "biomarker_name": ["plasma_nfl_pgml", "plasma_nfl_pgml"],
        "value": [25.0, 30.0],
        "unit": ["pg/mL", "pg/mL"],
        "value_type": ["numeric", "numeric"],
    })
    sub = _write_submission(
        tmp_path,
        patients=_patients([72, 68], [16, 12]),
        predictions=_base_predictions(),
        biomarkers=bio,
    )
    report = validate_submission(sub)
    assert "BIOMARKER_PATIENT_ORPHAN" in _codes(report)


def test_biomarker_no_orphan_when_all_present(tmp_path):
    bio = pd.DataFrame({
        "patient_id": ["P001", "P002"],
        "visit_id": ["v1", "v1"],
        "biomarker_name": ["plasma_nfl_pgml", "plasma_nfl_pgml"],
        "value": [25.0, 30.0],
        "unit": ["pg/mL", "pg/mL"],
        "value_type": ["numeric", "numeric"],
    })
    sub = _write_submission(
        tmp_path,
        patients=_patients([72, 68], [16, 12]),
        predictions=_base_predictions(),
        biomarkers=bio,
    )
    report = validate_submission(sub)
    assert "BIOMARKER_PATIENT_ORPHAN" not in _codes(report)

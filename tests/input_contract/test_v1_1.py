"""
Tests for NeuroTCS Input Contract validator v1.1.0.

Coverage:
  - 10 backward-compatibility tests carried from v1.0 (must still pass)
  - 12 new tests for v1.1 features (continuous biomarkers, UCUM, conditional state)
  - 2 real-world tests using actual ADNI clinical labels AND FreeSurfer volumes
"""

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.input_contract.v1_1.validate import THIS_VALIDATOR_VERSION, validate_submission

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

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
SKIP = "\033[33m⏭\033[0m"

# ============================================================
# Test helpers
# ============================================================

def make_valid_v1_submission(tmpdir: Path, level: str = "L2",
                              contract_version: str = "1.1.0") -> Path:
    """Build a minimal valid submission (categorical only) for testing."""
    sub = tmpdir / "sub"
    sub.mkdir()

    predictions = pd.DataFrame({
        "patient_id": ["P001"] * 3 + ["P002"] * 3,
        "visit_id": ["v1", "v2", "v3"] * 2,
        "visit_timestamp": [
            "2020-01-01T00:00:00Z", "2020-07-01T00:00:00Z", "2021-01-01T00:00:00Z",
            "2020-02-01T00:00:00Z", "2020-08-01T00:00:00Z", "2021-02-01T00:00:00Z",
        ],
        "predicted_state": ["MCI", "MCI", "CN", "MCI", "MCI", "MCI"],
        "uncertainty": [0.85, 0.80, 0.70, 0.90, 0.88, 0.85],
        "treatment_flags": [[], [], [], [], [], []],
    })
    predictions.to_parquet(sub / "predictions.parquet")

    patients = pd.DataFrame({
        "patient_id": ["P001", "P002"],
        "sex": ["female", "male"],
        "age_at_baseline": [72, 68],
        "race_ethnicity": ["white", "asian"],
        "site_id": ["site_01", "site_01"],
        "scanner_vendor": ["siemens", "siemens"],
    })
    patients.to_parquet(sub / "patients.parquet")

    manifest = {
        "neurotcs_contract_version": contract_version,
        "conformance_level": level,
        "submission_id": "test_submission_001",
        "submission_timestamp": "2026-05-17T13:45:00Z",
        "source_system": {"name": "TestModel", "version": "0.1.0", "vendor": "self"},
        "disease_domain": "alzheimers",
        "rule_pack": {"id": "aa2024+trac@1.0", "source": "registry"},
        "data_files": {
            "predictions": "predictions.parquet",
            "patients": "patients.parquet",
        },
        "cohort_summary": {
            "n_patients": 2,
            "n_visits_total": 6,
            "date_range": ["2020-01-01", "2021-02-01"],
        },
    }
    with open(sub / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    return sub


def make_biomarker_submission_inline(tmpdir: Path,
                                      state_present: bool = True,
                                      mutator=None) -> Path:
    """Build a v1.1 submission with inline continuous biomarkers.

    Args:
        tmpdir: Temp working directory.
        state_present: If True, include predicted_state. If False, set to None.
        mutator: Optional callable(biomarkers_list) → modified biomarkers_list.
                 Receives the list of 3 visits, each containing a list of biomarker dicts.
                 Returns the same structure modified in place. Used to inject test errors.
    """
    sub = tmpdir / "sub"
    sub.mkdir()

    biomarkers_per_visit = [
        [{"name": "hippocampal_volume", "value": 3.85, "unit": "mL",
          "value_type": "continuous", "reference_range": [3.0, 5.0],
          "uncertainty": 0.05}],
        [{"name": "hippocampal_volume", "value": 3.72, "unit": "mL",
          "value_type": "continuous", "reference_range": [3.0, 5.0],
          "uncertainty": 0.06}],
        [{"name": "hippocampal_volume", "value": 3.60, "unit": "mL",
          "value_type": "continuous", "reference_range": [3.0, 5.0],
          "uncertainty": 0.06}],
    ]

    # Apply mutator BEFORE serialization to avoid pyarrow round-trip issues
    if mutator is not None:
        biomarkers_per_visit = mutator(biomarkers_per_visit)

    predictions_data = {
        "patient_id": ["P001", "P001", "P001"],
        "visit_id": ["v1", "v2", "v3"],
        "visit_timestamp": [
            "2020-01-01T00:00:00Z", "2020-07-01T00:00:00Z", "2021-01-01T00:00:00Z"
        ],
        "predicted_state": (
            ["MCI", "MCI", "CN"] if state_present else [None, None, None]
        ),
        "uncertainty": [0.85, 0.80, 0.70],
        "treatment_flags": [[], [], []],
        "continuous_biomarkers": biomarkers_per_visit,
    }

    # Write predictions as JSONL — preserves nested structure cleanly
    pred_path = sub / "predictions.jsonl"
    with open(pred_path, "w") as f:
        for i in range(len(predictions_data["patient_id"])):
            row = {k: v[i] for k, v in predictions_data.items()}
            f.write(json.dumps(row) + "\n")

    patients = pd.DataFrame({
        "patient_id": ["P001"],
        "sex": ["female"],
        "age_at_baseline": [72],
        "race_ethnicity": ["white"],
        "site_id": ["site_01"],
        "scanner_vendor": ["siemens"],
    })
    patients.to_parquet(sub / "patients.parquet")

    manifest = {
        "neurotcs_contract_version": "1.1.0",
        "conformance_level": "L2",
        "submission_id": "biomarker_inline_test",
        "submission_timestamp": "2026-05-17T13:45:00Z",
        "source_system": {"name": "VolumetricAI", "version": "1.0.0",
                           "vendor": "vendor_x"},
        "disease_domain": "alzheimers",
        "rule_pack": {"id": "aa2024+volumes@1.0", "source": "registry"},
        "data_files": {"predictions": "predictions.jsonl",
                        "patients": "patients.parquet"},
        "cohort_summary": {"n_patients": 1, "n_visits_total": 3,
                            "date_range": ["2020-01-01", "2021-01-01"]},
    }
    (sub / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return sub


def make_biomarker_submission_longform(tmpdir: Path) -> Path:
    """Build a v1.1 submission with long-format biomarkers.parquet."""
    sub = tmpdir / "sub"
    sub.mkdir()

    predictions = pd.DataFrame({
        "patient_id": ["P001"] * 3,
        "visit_id": ["v1", "v2", "v3"],
        "visit_timestamp": [
            "2020-01-01T00:00:00Z", "2020-07-01T00:00:00Z", "2021-01-01T00:00:00Z"
        ],
        "predicted_state": ["MCI", "MCI", "CN"],
        "uncertainty": [0.85, 0.80, 0.70],
        "treatment_flags": [[], [], []],
    })
    predictions.to_parquet(sub / "predictions.parquet")

    biomarkers = pd.DataFrame({
        "patient_id": ["P001"] * 6,
        "visit_id": ["v1", "v1", "v2", "v2", "v3", "v3"],
        "biomarker_name": [
            "hippocampal_volume", "ventricle_volume",
            "hippocampal_volume", "ventricle_volume",
            "hippocampal_volume", "ventricle_volume",
        ],
        "value": [3.85, 22.4, 3.72, 23.8, 3.60, 25.1],
        "unit": ["mL"] * 6,
        "value_type": ["continuous"] * 6,
        "ref_low": [3.0, 15.0, 3.0, 15.0, 3.0, 15.0],
        "ref_high": [5.0, 30.0, 5.0, 30.0, 5.0, 30.0],
        "uncertainty": [0.05, 0.10, 0.06, 0.10, 0.06, 0.11],
    })
    biomarkers.to_parquet(sub / "biomarkers.parquet")

    patients = pd.DataFrame({
        "patient_id": ["P001"],
        "sex": ["female"], "age_at_baseline": [72],
        "race_ethnicity": ["white"], "site_id": ["s1"], "scanner_vendor": ["siemens"],
    })
    patients.to_parquet(sub / "patients.parquet")

    manifest = {
        "neurotcs_contract_version": "1.1.0",
        "conformance_level": "L2",
        "submission_id": "biomarker_longform_test",
        "submission_timestamp": "2026-05-17T13:45:00Z",
        "source_system": {"name": "Vol", "version": "1.0", "vendor": "v"},
        "disease_domain": "alzheimers",
        "rule_pack": {"id": "aa2024+volumes@1.0", "source": "registry"},
        "data_files": {
            "predictions": "predictions.parquet",
            "patients": "patients.parquet",
            "biomarkers": "biomarkers.parquet",
        },
        "cohort_summary": {"n_patients": 1, "n_visits_total": 3,
                            "date_range": ["2020-01-01", "2021-01-01"]},
    }
    (sub / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return sub


# ============================================================
# Backward-compatibility tests (10 — carried from v1.0)
# ============================================================

def test_v10_valid_submission():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp), contract_version="1.0.0")
        report = validate_submission(sub)
        assert report.is_valid(), f"v1.0 submission must still validate; errors: {report.errors}"
        print(f"  {PASS} test_v10_valid_submission (backward compat)")


def test_v11_valid_categorical():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp), contract_version="1.1.0")
        report = validate_submission(sub)
        assert report.is_valid(), f"v1.1 categorical must validate; errors: {report.errors}"
        print(f"  {PASS} test_v11_valid_categorical")


def test_missing_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        sub = Path(tmp) / "empty"
        sub.mkdir()
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "MISSING_MANIFEST" for e in report.errors)
        print(f"  {PASS} test_missing_manifest")


def test_unsupported_version():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp))
        m = json.loads((sub / "manifest.json").read_text())
        m["neurotcs_contract_version"] = "0.9.0"
        (sub / "manifest.json").write_text(json.dumps(m))
        report = validate_submission(sub)
        assert not report.is_valid()
        codes = {e.code for e in report.errors}
        assert "SCHEMA_VIOLATION" in codes or "UNSUPPORTED_CONTRACT_VERSION" in codes
        print(f"  {PASS} test_unsupported_version")


def test_phi_detected():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp))
        preds = pd.read_parquet(sub / "predictions.parquet")
        old = preds.loc[0, "patient_id"]
        preds.loc[preds["patient_id"] == old, "patient_id"] = "123-45-6789"
        preds.to_parquet(sub / "predictions.parquet")
        pats = pd.read_parquet(sub / "patients.parquet")
        pats.loc[pats["patient_id"] == old, "patient_id"] = "123-45-6789"
        pats.to_parquet(sub / "patients.parquet")
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "PHI_PATTERN_DETECTED" for e in report.errors)
        print(f"  {PASS} test_phi_detected")


def test_future_timestamp():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp))
        preds = pd.read_parquet(sub / "predictions.parquet")
        preds.loc[0, "visit_timestamp"] = "2099-01-01T00:00:00Z"
        preds.to_parquet(sub / "predictions.parquet")
        report = validate_submission(sub)
        assert any(e.code == "FUTURE_TIMESTAMP" for e in report.errors)
        print(f"  {PASS} test_future_timestamp")


def test_duplicate_visit():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp))
        preds = pd.read_parquet(sub / "predictions.parquet")
        preds.loc[1, "visit_id"] = preds.loc[0, "visit_id"]
        preds.to_parquet(sub / "predictions.parquet")
        report = validate_submission(sub)
        assert any(e.code == "DUPLICATE_VISIT" for e in report.errors)
        print(f"  {PASS} test_duplicate_visit")


def test_cohort_summary_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp))
        m = json.loads((sub / "manifest.json").read_text())
        m["cohort_summary"]["n_patients"] = 99
        (sub / "manifest.json").write_text(json.dumps(m))
        report = validate_submission(sub)
        assert any(e.code == "COHORT_SUMMARY_MISMATCH" for e in report.errors)
        print(f"  {PASS} test_cohort_summary_mismatch")


def test_patient_id_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp))
        pats = pd.read_parquet(sub / "patients.parquet")
        pats = pats.iloc[:1]
        pats.to_parquet(sub / "patients.parquet")
        report = validate_submission(sub)
        assert any(e.code == "PATIENT_ID_MISMATCH" for e in report.errors)
        print(f"  {PASS} test_patient_id_mismatch")


# ============================================================
# v1.1 — new tests (12)
# ============================================================

def test_biomarker_inline_valid():
    """Inline biomarker submission with state should validate."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), state_present=True)
        report = validate_submission(sub)
        assert report.is_valid(), f"Inline biomarker submission must validate; errors: {report.errors}"
        print(f"  {PASS} test_biomarker_inline_valid")


def test_biomarker_inline_no_state():
    """Inline biomarker submission WITHOUT predicted_state should still validate
    because every row has at least one biomarker."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), state_present=False)
        report = validate_submission(sub)
        assert report.is_valid(), \
            f"Biomarker-only submission must validate; errors: {report.errors}"
        print(f"  {PASS} test_biomarker_inline_no_state")


def test_biomarker_longform_valid():
    """Long-format biomarkers.parquet should validate."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_longform(Path(tmp))
        report = validate_submission(sub)
        assert report.is_valid(), f"Long-format must validate; errors: {report.errors}"
        print(f"  {PASS} test_biomarker_longform_valid")


def test_missing_state_and_biomarker():
    """Row with neither categorical state nor any biomarker must error."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_v1_submission(Path(tmp))
        # Wipe out predicted_state entirely on one row, no biomarker present
        preds = pd.read_parquet(sub / "predictions.parquet")
        preds.loc[0, "predicted_state"] = None
        preds.to_parquet(sub / "predictions.parquet")
        report = validate_submission(sub)
        assert any(e.code == "MISSING_STATE_AND_BIOMARKER" for e in report.errors), \
            f"Expected MISSING_STATE_AND_BIOMARKER; got {[e.code for e in report.errors]}"
        print(f"  {PASS} test_missing_state_and_biomarker")


def test_invalid_ucum_unit():
    """Biomarker with non-UCUM unit (not x- prefixed) must error."""
    def m(bms):
        bms[0][0]["unit"] = "milliliters"  # bogus
        return bms
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), mutator=m)
        report = validate_submission(sub)
        assert any(e.code == "INVALID_UCUM_UNIT" for e in report.errors), \
            f"Expected INVALID_UCUM_UNIT; got {[e.code for e in report.errors]}"
        print(f"  {PASS} test_invalid_ucum_unit")


def test_custom_unit_warning():
    """Biomarker with x-prefixed custom unit should warn, not error."""
    def m(bms):
        for visit in bms:
            visit[0]["unit"] = "x-vendor_score"
        return bms
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), mutator=m)
        report = validate_submission(sub)
        assert report.is_valid(), f"Custom unit should NOT block; errors: {report.errors}"
        assert any(w.code == "CUSTOM_UNIT_USED" for w in report.warnings)
        print(f"  {PASS} test_custom_unit_warning")


def test_inconsistent_units():
    """Same biomarker name with different units across rows must error."""
    def m(bms):
        bms[1][0]["unit"] = "cm3"  # different from mL used elsewhere
        return bms
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), mutator=m)
        report = validate_submission(sub)
        assert any(e.code == "INCONSISTENT_UNITS" for e in report.errors), \
            f"Expected INCONSISTENT_UNITS; got {[e.code for e in report.errors]}"
        print(f"  {PASS} test_inconsistent_units")


def test_invalid_value_type():
    """Biomarker with value_type outside enum must error."""
    def m(bms):
        bms[0][0]["value_type"] = "fractional"
        return bms
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), mutator=m)
        report = validate_submission(sub)
        assert any(e.code == "INVALID_VALUE_TYPE" for e in report.errors)
        print(f"  {PASS} test_invalid_value_type")


def test_negative_volume_warning():
    """Negative value for a volume biomarker must warn (physically impossible)."""
    def m(bms):
        bms[0][0]["value"] = -1.5
        return bms
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), mutator=m)
        report = validate_submission(sub)
        assert report.is_valid(), "Negative volume is a WARNING not an ERROR"
        assert any(w.code == "NEGATIVE_VALUE_FOR_NONNEGATIVE_BIOMARKER"
                   for w in report.warnings)
        print(f"  {PASS} test_negative_volume_warning")


def test_biomarker_format_conflict():
    """Submission with BOTH inline and long-format must error."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp))
        # Add a biomarkers.parquet AND update manifest to reference it
        biomarkers = pd.DataFrame({
            "patient_id": ["P001"],
            "visit_id": ["v1"],
            "biomarker_name": ["hippocampal_volume"],
            "value": [3.85],
            "unit": ["mL"],
            "value_type": ["continuous"],
            "ref_low": [3.0], "ref_high": [5.0],
            "uncertainty": [0.05],
        })
        biomarkers.to_parquet(sub / "biomarkers.parquet")
        m = json.loads((sub / "manifest.json").read_text())
        m["data_files"]["biomarkers"] = "biomarkers.parquet"
        (sub / "manifest.json").write_text(json.dumps(m))
        report = validate_submission(sub)
        assert any(e.code == "BIOMARKER_FORMAT_CONFLICT" for e in report.errors), \
            f"Expected BIOMARKER_FORMAT_CONFLICT; got {[e.code for e in report.errors]}"
        print(f"  {PASS} test_biomarker_format_conflict")


def test_biomarker_orphan():
    """Long-format biomarker row that doesn't match any (patient_id, visit_id)
    in predictions must error."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_longform(Path(tmp))
        bio = pd.read_parquet(sub / "biomarkers.parquet")
        bio.loc[0, "visit_id"] = "nonexistent_visit"
        bio.to_parquet(sub / "biomarkers.parquet")
        report = validate_submission(sub)
        assert any(e.code == "BIOMARKER_ORPHAN" for e in report.errors)
        print(f"  {PASS} test_biomarker_orphan")


def test_reference_range_inverted():
    """ref_low > ref_high must produce a warning."""
    def m(bms):
        bms[0][0]["reference_range"] = [10.0, 3.0]
        return bms
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_biomarker_submission_inline(Path(tmp), mutator=m)
        report = validate_submission(sub)
        assert any(w.code == "REFERENCE_RANGE_INVERTED" for w in report.warnings)
        print(f"  {PASS} test_reference_range_inverted")


# ============================================================
# Real-world tests (2)
# ============================================================

def test_real_adni_clinical():
    """Real ADNI clinical labels — categorical only, v1.1.

    Resolves DXSUM.rda from NEUROTCS_ADNI_DXSUM_RDA. Skips if unset.
    """
    import os

    import pytest
    pyreadr = pytest.importorskip("pyreadr")
    adni_env = os.environ.get("NEUROTCS_ADNI_DXSUM_RDA")
    adni = Path(adni_env) if adni_env else None
    if adni is None or not adni.exists():
        print(f"  {SKIP} test_real_adni_clinical (ADNI not accessible)")
        return

    dx = pyreadr.read_r(str(adni))["DXSUM"]
    dx = dx[dx["DIAGNOSIS"].isin(["CN", "MCI", "Dementia"])].copy()
    dx["EXAMDATE"] = pd.to_datetime(dx["EXAMDATE"], errors="coerce")
    dx = dx.dropna(subset=["EXAMDATE", "RID", "VISCODE2"])

    counts = dx.groupby("RID").size()
    keep = counts[counts >= 3].index[:10]
    dx = dx[dx["RID"].isin(keep)].sort_values(["RID", "EXAMDATE"])

    # Disambiguate (RID, VISCODE2) by appending COLPROT (this was the v1.0
    # finding from a real adapter run)
    dx["_vis"] = dx["VISCODE2"].astype(str) + "_" + dx["COLPROT"].astype(str)

    import hashlib
    def hid(r): return "ADNI_" + hashlib.sha256(f"salt_{r}".encode()).hexdigest()[:16]

    with tempfile.TemporaryDirectory() as tmp:
        sub = Path(tmp) / "adni"
        sub.mkdir()
        preds = pd.DataFrame({
            "patient_id": dx["RID"].astype(int).apply(hid).values,
            "visit_id": dx["_vis"].values,
            "visit_timestamp": dx["EXAMDATE"].dt.strftime("%Y-%m-%dT00:00:00Z").values,
            "predicted_state": dx["DIAGNOSIS"].values,
            "uncertainty": [0.85] * len(dx),
            "treatment_flags": [[]] * len(dx),
        })
        preds.to_parquet(sub / "predictions.parquet")

        pat = preds[["patient_id"]].drop_duplicates()
        pat["sex"] = "unknown"
        pat["age_at_baseline"] = 70
        pat["race_ethnicity"] = "unknown"
        pat["site_id"] = "adni"
        pat["scanner_vendor"] = "unknown"
        pat.to_parquet(sub / "patients.parquet")

        manifest = {
            "neurotcs_contract_version": "1.1.0",
            "conformance_level": "L2",
            "submission_id": "adni_clinical_v11",
            "submission_timestamp": "2026-05-17T14:00:00Z",
            "source_system": {"name": "ADNI clinical labels",
                               "version": "ADNIMERGE2", "vendor": "ADNI"},
            "disease_domain": "alzheimers",
            "rule_pack": {"id": "aa2024+trac@1.0", "source": "registry"},
            "data_files": {"predictions": "predictions.parquet",
                            "patients": "patients.parquet"},
            "cohort_summary": {
                "n_patients": int(preds["patient_id"].nunique()),
                "n_visits_total": int(len(preds)),
                "date_range": [preds["visit_timestamp"].min()[:10],
                                preds["visit_timestamp"].max()[:10]],
            },
        }
        (sub / "manifest.json").write_text(json.dumps(manifest, indent=2))
        report = validate_submission(sub)
        assert report.is_valid(), f"ADNI clinical must validate; errors: {report.errors}"
        print(f"  {PASS} test_real_adni_clinical "
              f"({len(preds)} visits, {preds['patient_id'].nunique()} patients)")


def test_real_adni_volumetric():
    """Real ADNI FreeSurfer volumes as continuous biomarkers (v1.1 capability).

    Resolves DXSUM.rda from NEUROTCS_ADNI_DXSUM_RDA and UCSFFSX7.rda from
    NEUROTCS_ADNI_UCSFFSX7_RDA. Skips if either env var is unset.
    """
    import os

    import pytest
    pyreadr = pytest.importorskip("pyreadr")
    fs_env = os.environ.get("NEUROTCS_ADNI_UCSFFSX7_RDA")
    dx_env = os.environ.get("NEUROTCS_ADNI_DXSUM_RDA")
    fs = Path(fs_env) if fs_env else None
    dx = Path(dx_env) if dx_env else None
    if fs is None or dx is None or not fs.exists() or not dx.exists():
        print(f"  {SKIP} test_real_adni_volumetric (FreeSurfer/DXSUM env vars not set)")
        return

    fsdf = pyreadr.read_r(str(fs))["UCSFFSX7"]
    dxdf = pyreadr.read_r(str(dx))["DXSUM"]

    fsdf = fsdf.dropna(subset=["RID", "VISCODE2", "ST29SV"])
    fsdf["EXAMDATE"] = pd.to_datetime(fsdf["EXAMDATE"], errors="coerce")
    fsdf = fsdf.dropna(subset=["EXAMDATE"])

    counts = fsdf.groupby("RID").size()
    keep = counts[counts >= 3].index[:5]
    fsdf = fsdf[fsdf["RID"].isin(keep)].sort_values(["RID", "EXAMDATE"])
    fsdf["_vis"] = fsdf["VISCODE2"].astype(str) + "_" + fsdf["COLPROT"].astype(str)
    fsdf = fsdf.drop_duplicates(subset=["RID", "_vis"], keep="first")

    # Merge with DXSUM for optional categorical state
    dxdf_lite = dxdf[["RID", "VISCODE2", "COLPROT", "DIAGNOSIS"]].copy()
    dxdf_lite["_vis"] = (dxdf_lite["VISCODE2"].astype(str) + "_"
                          + dxdf_lite["COLPROT"].astype(str))
    merged = fsdf.merge(dxdf_lite[["RID", "_vis", "DIAGNOSIS"]],
                         on=["RID", "_vis"], how="left")
    merged = merged.drop_duplicates(subset=["RID", "_vis"], keep="first")
    merged = merged.reset_index(drop=True)

    import hashlib
    def hid(r): return "ADNI_" + hashlib.sha256(f"salt_{r}".encode()).hexdigest()[:16]

    with tempfile.TemporaryDirectory() as tmp:
        sub = Path(tmp) / "adni_vol"
        sub.mkdir()

        # Write predictions as JSONL — preserves nested biomarker structures cleanly
        pred_path = sub / "predictions.jsonl"
        total_biomarkers = 0
        with open(pred_path, "w") as f:
            for _, row in merged.iterrows():
                bm = []
                if pd.notna(row.get("ST29SV")):
                    bm.append({"name": "right_hippocampal_volume",
                               "value": float(row["ST29SV"]) / 1000.0,
                               "unit": "mL", "value_type": "continuous",
                               "reference_range": [2.5, 4.5], "uncertainty": None})
                if pd.notna(row.get("ST88SV")):
                    bm.append({"name": "left_hippocampal_volume",
                               "value": float(row["ST88SV"]) / 1000.0,
                               "unit": "mL", "value_type": "continuous",
                               "reference_range": [2.5, 4.5], "uncertainty": None})
                total_biomarkers += len(bm)
                dx_val = row["DIAGNOSIS"]
                state = (dx_val if dx_val in ("CN", "MCI", "Dementia") else None)
                obj = {
                    "patient_id": hid(int(row["RID"])),
                    "visit_id": row["_vis"],
                    "visit_timestamp": row["EXAMDATE"].strftime("%Y-%m-%dT00:00:00Z"),
                    "predicted_state": state,
                    "uncertainty": None,
                    "treatment_flags": [],
                    "continuous_biomarkers": bm,
                }
                f.write(json.dumps(obj) + "\n")

        n_patients = merged["RID"].nunique()
        n_visits = len(merged)

        pat = pd.DataFrame({
            "patient_id": [hid(int(r)) for r in merged["RID"].unique()],
            "sex": ["unknown"] * n_patients,
            "age_at_baseline": [70] * n_patients,
            "race_ethnicity": ["unknown"] * n_patients,
            "site_id": ["adni"] * n_patients,
            "scanner_vendor": ["unknown"] * n_patients,
        })
        pat.to_parquet(sub / "patients.parquet")

        ts_min = merged["EXAMDATE"].min().strftime("%Y-%m-%d")
        ts_max = merged["EXAMDATE"].max().strftime("%Y-%m-%d")

        manifest = {
            "neurotcs_contract_version": "1.1.0",
            "conformance_level": "L2",
            "submission_id": "adni_volumetric_v11",
            "submission_timestamp": "2026-05-17T14:00:00Z",
            "source_system": {"name": "FreeSurfer UCSFFSX7",
                               "version": "ADNIMERGE2", "vendor": "ADNI"},
            "disease_domain": "alzheimers",
            "rule_pack": {"id": "aa2024+volumes@1.0", "source": "registry"},
            "data_files": {"predictions": "predictions.jsonl",
                            "patients": "patients.parquet"},
            "cohort_summary": {
                "n_patients": n_patients,
                "n_visits_total": n_visits,
                "date_range": [ts_min, ts_max],
            },
        }
        (sub / "manifest.json").write_text(json.dumps(manifest, indent=2))
        report = validate_submission(sub)
        if not report.is_valid():
            print(f"\n   Errors: {[str(e) for e in report.errors]}")
        assert report.is_valid(), f"Volumetric must validate; errors: {report.errors}"
        print(f"  {PASS} test_real_adni_volumetric "
              f"({n_visits} visits, {total_biomarkers} biomarker measurements, "
              f"{n_patients} patients)")


# ============================================================
# Runner
# ============================================================

def run_all():
    tests = [
        # Backward-compat (10)
        test_v10_valid_submission,
        test_v11_valid_categorical,
        test_missing_manifest,
        test_unsupported_version,
        test_phi_detected,
        test_future_timestamp,
        test_duplicate_visit,
        test_cohort_summary_mismatch,
        test_patient_id_mismatch,
        # v1.1 new (13)
        test_biomarker_inline_valid,
        test_biomarker_inline_no_state,
        test_biomarker_longform_valid,
        test_missing_state_and_biomarker,
        test_invalid_ucum_unit,
        test_custom_unit_warning,
        test_inconsistent_units,
        test_invalid_value_type,
        test_negative_volume_warning,
        test_biomarker_format_conflict,
        test_biomarker_orphan,
        test_reference_range_inverted,
        # Real-world (2)
        test_real_adni_clinical,
        test_real_adni_volumetric,
    ]
    print(f"\nNeuroTCS Contract Validator v{THIS_VALIDATOR_VERSION} — running {len(tests)} tests:\n")
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  {FAIL} {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  {FAIL} {t.__name__}: unexpected {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)

"""
Tests for NeuroTCS Input Contract validator.

These tests exercise the validation pipeline against:
  1. Synthetic valid submissions (must pass)
  2. Synthetic invalid submissions (must fail with specific errors)
  3. Real-data adapters from ADNI and LUMIERE (proof of practical applicability)
"""

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.input_contract.v1_0.validate import CONTRACT_VERSION, validate_submission

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


def make_valid_submission(tmpdir: Path, level: str = "L2") -> Path:
    """Build a minimal valid submission for testing."""
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
        "neurotcs_contract_version": CONTRACT_VERSION,
        "conformance_level": level,
        "submission_id": "test_submission_001",
        "submission_timestamp": "2026-05-17T13:45:00Z",
        "source_system": {
            "name": "TestModel", "version": "0.1.0", "vendor": "self"
        },
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


def test_valid_submission():
    """A correctly-built submission must validate."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_submission(Path(tmp))
        report = validate_submission(sub)
        assert report.is_valid(), f"Expected valid; got errors: {report.errors}"
        print(f"  {PASS} test_valid_submission")


def test_missing_manifest():
    """Submission with no manifest must error."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = Path(tmp) / "empty"
        sub.mkdir()
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "MISSING_MANIFEST" for e in report.errors)
        print(f"  {PASS} test_missing_manifest")


def test_wrong_contract_version():
    """Submission declaring an old contract version must error."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_submission(Path(tmp))
        manifest_path = sub / "manifest.json"
        m = json.loads(manifest_path.read_text())
        m["neurotcs_contract_version"] = "0.9.0"
        # This violates schema (const: 1.0.0), so it'll fail at SCHEMA_VIOLATION
        manifest_path.write_text(json.dumps(m))
        report = validate_submission(sub)
        assert not report.is_valid()
        # Either UNSUPPORTED_CONTRACT_VERSION or SCHEMA_VIOLATION acceptable
        codes = {e.code for e in report.errors}
        assert "SCHEMA_VIOLATION" in codes or "UNSUPPORTED_CONTRACT_VERSION" in codes
        print(f"  {PASS} test_wrong_contract_version")


def test_phi_in_patient_id():
    """patient_id containing SSN pattern must trigger PHI detection."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_submission(Path(tmp))
        # SSN-like pattern with word boundaries the regex can detect.
        # Format "xxx-xx-xxxx" surrounded by spaces or as standalone string.
        new_id = "123-45-6789"  # Standalone SSN
        preds = pd.read_parquet(sub / "predictions.parquet")
        old_id = preds.loc[0, "patient_id"]
        preds.loc[preds["patient_id"] == old_id, "patient_id"] = new_id
        preds.to_parquet(sub / "predictions.parquet")
        pats = pd.read_parquet(sub / "patients.parquet")
        pats.loc[pats["patient_id"] == old_id, "patient_id"] = new_id
        pats.to_parquet(sub / "patients.parquet")
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "PHI_PATTERN_DETECTED" for e in report.errors), \
            f"Expected PHI_PATTERN_DETECTED, got: {[e.code for e in report.errors]}"
        print(f"  {PASS} test_phi_in_patient_id")


def test_future_timestamp():
    """Visits in the future relative to submission_timestamp must error."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_submission(Path(tmp))
        preds = pd.read_parquet(sub / "predictions.parquet")
        preds.loc[0, "visit_timestamp"] = "2099-01-01T00:00:00Z"
        preds.to_parquet(sub / "predictions.parquet")
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "FUTURE_TIMESTAMP" for e in report.errors)
        print(f"  {PASS} test_future_timestamp")


def test_duplicate_visit():
    """Two rows with same (patient_id, visit_id) must error."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_submission(Path(tmp))
        preds = pd.read_parquet(sub / "predictions.parquet")
        preds.loc[1, "visit_id"] = preds.loc[0, "visit_id"]  # collide
        preds.to_parquet(sub / "predictions.parquet")
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "DUPLICATE_VISIT" for e in report.errors)
        print(f"  {PASS} test_duplicate_visit")


def test_cohort_summary_mismatch():
    """Manifest cohort counts must match actual data."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_submission(Path(tmp))
        m = json.loads((sub / "manifest.json").read_text())
        m["cohort_summary"]["n_patients"] = 99  # wrong!
        (sub / "manifest.json").write_text(json.dumps(m))
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "COHORT_SUMMARY_MISMATCH" for e in report.errors)
        print(f"  {PASS} test_cohort_summary_mismatch")


def test_patient_id_mismatch():
    """patient_ids in predictions must all exist in patients table."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = make_valid_submission(Path(tmp))
        pats = pd.read_parquet(sub / "patients.parquet")
        pats = pats.iloc[:1]  # drop P002 from patients table
        pats.to_parquet(sub / "patients.parquet")
        report = validate_submission(sub)
        assert not report.is_valid()
        assert any(e.code == "PATIENT_ID_MISMATCH" for e in report.errors)
        print(f"  {PASS} test_patient_id_mismatch")


def test_l1_minimum_submission():
    """L1 submission with only required columns must validate."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = Path(tmp) / "l1_sub"
        sub.mkdir()
        preds = pd.DataFrame({
            "patient_id": ["P001"] * 3,
            "visit_id": ["v1", "v2", "v3"],
            "visit_timestamp": [
                "2020-01-01T00:00:00Z", "2020-07-01T00:00:00Z", "2021-01-01T00:00:00Z"
            ],
            "predicted_state": ["MCI", "MCI", "CN"],
        })
        preds.to_parquet(sub / "predictions.parquet")
        manifest = {
            "neurotcs_contract_version": CONTRACT_VERSION,
            "conformance_level": "L1",
            "submission_id": "l1_test",
            "submission_timestamp": "2026-05-17T13:45:00Z",
            "source_system": {"name": "Test", "version": "0.1", "vendor": "self"},
            "disease_domain": "alzheimers",
            "rule_pack": {"id": "aa2024+trac@1.0", "source": "registry"},
            "data_files": {"predictions": "predictions.parquet"},
            "cohort_summary": {
                "n_patients": 1, "n_visits_total": 3,
                "date_range": ["2020-01-01", "2021-01-01"],
            },
        }
        (sub / "manifest.json").write_text(json.dumps(manifest))
        report = validate_submission(sub)
        assert report.is_valid(), f"L1 should validate; errors: {report.errors}"
        print(f"  {PASS} test_l1_minimum_submission")


def test_real_world_adni_adapter():
    """Convert a tiny slice of real ADNI data into a conforming submission.
    This proves the contract handles real data, not just synthetic toys.

    Resolves the DXSUM.rda path from NEUROTCS_ADNI_DXSUM_RDA. Skips cleanly
    if the env var is unset or the file does not exist.
    """
    import os

    import pyreadr
    adni_env = os.environ.get("NEUROTCS_ADNI_DXSUM_RDA")
    adni_path = Path(adni_env) if adni_env else None
    if adni_path is None or not adni_path.exists():
        print("  ⏭  test_real_world_adni_adapter (ADNI not accessible — skipped)")
        return

    dx = pyreadr.read_r(str(adni_path))["DXSUM"]
    dx = dx[dx["DIAGNOSIS"].isin(["CN", "MCI", "Dementia"])].copy()
    dx["EXAMDATE"] = pd.to_datetime(dx["EXAMDATE"], errors="coerce")
    dx = dx.dropna(subset=["EXAMDATE", "RID"])

    # Pick first 10 patients with ≥3 visits
    counts = dx.groupby("RID").size()
    keep_rids = counts[counts >= 3].index[:10].tolist()
    dx = dx[dx["RID"].isin(keep_rids)].sort_values(["RID", "EXAMDATE"])

    with tempfile.TemporaryDirectory() as tmp:
        sub = Path(tmp) / "adni_sub"
        sub.mkdir()

        # Build adapter output — hash RIDs so no PHI-like patterns
        import hashlib
        def hash_id(rid):
            return "ADNI_" + hashlib.sha256(f"salt_{rid}".encode()).hexdigest()[:16]

        preds = pd.DataFrame({
            "patient_id": dx["RID"].astype(int).apply(hash_id).values,
            "visit_id": dx["VISCODE2"].astype(str).values,
            "visit_timestamp": dx["EXAMDATE"].dt.strftime("%Y-%m-%dT00:00:00Z").values,
            "predicted_state": dx["DIAGNOSIS"].values,
            "uncertainty": [0.85] * len(dx),
            "treatment_flags": [[]] * len(dx),
        })
        preds.to_parquet(sub / "predictions.parquet")

        unique_pat = preds.drop_duplicates(subset=["patient_id"])[["patient_id"]]
        unique_pat["sex"] = "unknown"
        unique_pat["age_at_baseline"] = 70
        unique_pat["race_ethnicity"] = "unknown"
        unique_pat["site_id"] = "adni"
        unique_pat["scanner_vendor"] = "unknown"
        unique_pat.to_parquet(sub / "patients.parquet")

        manifest = {
            "neurotcs_contract_version": CONTRACT_VERSION,
            "conformance_level": "L2",
            "submission_id": "adni_adapter_demo",
            "submission_timestamp": "2026-05-17T14:00:00Z",
            "source_system": {"name": "ADNI clinical labels", "version": "ADNIMERGE2", "vendor": "ADNI"},
            "disease_domain": "alzheimers",
            "rule_pack": {"id": "aa2024+trac@1.0", "source": "registry"},
            "data_files": {"predictions": "predictions.parquet", "patients": "patients.parquet"},
            "cohort_summary": {
                "n_patients": int(preds["patient_id"].nunique()),
                "n_visits_total": int(len(preds)),
                "date_range": [
                    preds["visit_timestamp"].min()[:10],
                    preds["visit_timestamp"].max()[:10],
                ],
            },
        }
        (sub / "manifest.json").write_text(json.dumps(manifest, indent=2))
        report = validate_submission(sub)
        assert report.is_valid(), f"ADNI adapter must validate; errors: {report.errors}"
        print(f"  {PASS} test_real_world_adni_adapter "
              f"({len(preds)} visits, {preds['patient_id'].nunique()} patients)")


def run_all():
    """Run every test, count results."""
    tests = [
        test_valid_submission,
        test_missing_manifest,
        test_wrong_contract_version,
        test_phi_in_patient_id,
        test_future_timestamp,
        test_duplicate_visit,
        test_cohort_summary_mismatch,
        test_patient_id_mismatch,
        test_l1_minimum_submission,
        test_real_world_adni_adapter,
    ]
    print(f"\nRunning {len(tests)} contract validator tests:\n")
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  {FAIL} {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  {FAIL} {t.__name__}: unexpected {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)

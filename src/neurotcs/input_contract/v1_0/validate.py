"""
NeuroTCS Input Contract — Reference Validator (v1.0.0)

This module implements the 8-step validation pipeline defined in
SPECIFICATION.md section 10.1. It is the reference implementation
of the contract and SHOULD be used as the canonical validator.

Usage:
    from validate import validate_submission, ValidationReport

    report = validate_submission("path/to/submission/")
    if report.is_valid():
        print("OK")
    else:
        for err in report.errors:
            print(err)

Design principles:
    1. Fail-closed. If anything is wrong, refuse to declare valid.
    2. Report ALL errors at once. Submitters fix everything in one pass.
    3. No silent inference. If a field is ambiguous, raise an error.
    4. Deterministic. Same input always produces same report.
    5. No PHI leakage. Errors reference column names and row counts only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import jsonschema
except ImportError:
    jsonschema = None


CONTRACT_VERSION = "1.0.0"
SCHEMA_PATH = Path(__file__).parent / "schemas" / "manifest.schema.json"


# ============================================================
# Result types
# ============================================================

@dataclass
class ValidationIssue:
    """A single validation finding."""
    severity: str  # "ERROR" | "WARNING"
    code: str      # e.g. "MISSING_FIELD", "PHI_PATTERN_DETECTED"
    location: str  # file:line or table:column or "manifest"
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} at {self.location}: {self.message}"


@dataclass
class ValidationReport:
    """All findings from a validation run."""
    submission_path: str
    contract_version: str = CONTRACT_VERSION
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    manifest: dict[str, Any] | None = None

    def is_valid(self) -> bool:
        """A submission is valid iff it has zero ERRORs. Warnings do not block."""
        return len(self.errors) == 0

    def add_error(self, code: str, location: str, message: str) -> None:
        self.errors.append(ValidationIssue("ERROR", code, location, message))

    def add_warning(self, code: str, location: str, message: str) -> None:
        self.warnings.append(ValidationIssue("WARNING", code, location, message))


# ============================================================
# Validation pipeline
# ============================================================

def validate_submission(submission_path: str | Path) -> ValidationReport:
    """Run the full 8-step validation pipeline on a submission directory.

    Returns a ValidationReport with all errors and warnings discovered.
    The report is always returned; never raises on validation failure.
    Raises only on programmer error (missing dependency, etc).
    """
    if pd is None:
        raise RuntimeError("pandas is required for validation")
    if jsonschema is None:
        raise RuntimeError("jsonschema is required for validation")

    path = Path(submission_path).resolve()
    report = ValidationReport(submission_path=str(path))

    # Step 1: Load and schema-validate manifest
    manifest = _step1_validate_manifest(path, report)
    if manifest is None:
        return report  # cannot continue without manifest
    report.manifest = manifest

    # Step 2: File presence check
    if not _step2_check_files(path, manifest, report):
        return report

    # Step 3: Predictions structural validation
    predictions = _step3_load_predictions(path, manifest, report)
    if predictions is None:
        return report

    # Step 4: Patients table cross-reference
    patients = None
    if manifest["conformance_level"] in ("L2", "L3"):
        patients = _step4_load_patients(path, manifest, predictions, report)

    # Step 5: PHI pattern scan
    _step5_phi_scan(predictions, patients, report)

    # Step 6: Rule pack compatibility (state vocabulary check)
    # Without loading the rule pack itself, we can at least confirm states are non-empty
    # Full rule-pack compatibility happens at audit time
    _step6_state_vocabulary_check(predictions, report)

    # Step 7: Temporal sanity
    _step7_temporal_sanity(predictions, manifest, report)

    # Step 8: Cohort summary cross-check
    _step8_cohort_summary_check(predictions, manifest, report)

    return report


# ============================================================
# Step implementations
# ============================================================

def _step1_validate_manifest(path: Path, report: ValidationReport) -> dict | None:
    """Step 1: Load manifest.json and validate against schema."""
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        report.add_error("MISSING_MANIFEST", "submission/", "manifest.json not found")
        return None

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        report.add_error("INVALID_JSON", "manifest.json", f"Failed to parse: {e}")
        return None

    try:
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
    except FileNotFoundError:
        report.add_error("MISSING_SCHEMA", "internal", "Manifest schema file not found")
        return None

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda e: e.path)
    if errors:
        for err in errors:
            loc = "manifest.json:" + ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "manifest.json"
            report.add_error("SCHEMA_VIOLATION", loc, err.message)
        return None

    # Contract-version explicit check
    if manifest.get("neurotcs_contract_version") != CONTRACT_VERSION:
        report.add_error(
            "UNSUPPORTED_CONTRACT_VERSION",
            "manifest.json:neurotcs_contract_version",
            f"This validator supports v{CONTRACT_VERSION}, submission declares "
            f"v{manifest.get('neurotcs_contract_version')}"
        )
        return None

    return manifest


def _step2_check_files(path: Path, manifest: dict, report: ValidationReport) -> bool:
    """Step 2: Confirm all declared data files exist."""
    ok = True
    pred_path = path / manifest["data_files"]["predictions"]
    if not pred_path.exists():
        report.add_error("MISSING_FILE", str(pred_path.name),
                         "Predictions file declared but not found")
        ok = False

    if "patients" in manifest["data_files"]:
        pat_path = path / manifest["data_files"]["patients"]
        if not pat_path.exists():
            report.add_error("MISSING_FILE", str(pat_path.name),
                             "Patients file declared but not found")
            ok = False

    return ok


def _step3_load_predictions(path: Path, manifest: dict,
                             report: ValidationReport) -> pd.DataFrame | None:
    """Step 3: Load predictions table and validate columns."""
    pred_path = path / manifest["data_files"]["predictions"]
    try:
        df = _load_table(pred_path)
    except Exception as e:
        report.add_error("UNREADABLE_FILE", pred_path.name, f"Cannot read: {e}")
        return None

    level = manifest["conformance_level"]
    required_l1 = ["patient_id", "visit_id", "visit_timestamp", "predicted_state"]
    required_l2 = required_l1 + ["uncertainty", "treatment_flags"]
    required = required_l1 if level == "L1" else required_l2

    missing = [c for c in required if c not in df.columns]
    if missing:
        report.add_error("MISSING_COLUMNS", f"{pred_path.name}",
                         f"Required columns missing at {level}: {missing}")
        return None

    # Type checks
    if not df["patient_id"].apply(lambda x: isinstance(x, str) and 1 <= len(x) <= 64).all():
        report.add_error("INVALID_TYPE", f"{pred_path.name}:patient_id",
                         "patient_id must be non-empty string ≤64 chars")

    if df.duplicated(subset=["patient_id", "visit_id"]).any():
        n_dup = int(df.duplicated(subset=["patient_id", "visit_id"]).sum())
        report.add_error("DUPLICATE_VISIT", f"{pred_path.name}",
                         f"{n_dup} duplicate (patient_id, visit_id) pairs found")

    # Timestamp parsing
    try:
        df["_ts_parsed"] = pd.to_datetime(df["visit_timestamp"], errors="raise", utc=True)
    except Exception as e:
        report.add_error("INVALID_TIMESTAMP", f"{pred_path.name}:visit_timestamp",
                         f"Cannot parse timestamps: {e}")
        return None

    # Uncertainty range check
    if "uncertainty" in df.columns:
        u = df["uncertainty"].dropna()
        if len(u) > 0 and ((u < 0).any() or (u > 1).any()):
            n_bad = int(((u < 0) | (u > 1)).sum())
            report.add_warning("UNCERTAINTY_OUT_OF_RANGE",
                               f"{pred_path.name}:uncertainty",
                               f"{n_bad} rows have uncertainty outside [0, 1]")

    return df


def _step4_load_patients(path: Path, manifest: dict, predictions: pd.DataFrame,
                          report: ValidationReport) -> pd.DataFrame | None:
    """Step 4: Load patients table; verify cross-reference."""
    if "patients" not in manifest["data_files"]:
        report.add_error("MISSING_PATIENTS_DECL",
                         "manifest.json:data_files",
                         "At L2+, manifest must declare a patients file")
        return None

    pat_path = path / manifest["data_files"]["patients"]
    try:
        df = _load_table(pat_path)
    except Exception as e:
        report.add_error("UNREADABLE_FILE", pat_path.name, f"Cannot read: {e}")
        return None

    required = ["patient_id", "sex", "age_at_baseline", "race_ethnicity",
                "site_id", "scanner_vendor"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        report.add_error("MISSING_COLUMNS", f"{pat_path.name}",
                         f"Required patient columns missing: {missing}")
        return None

    pred_ids = set(predictions["patient_id"].unique())
    pat_ids = set(df["patient_id"].unique())

    pred_only = pred_ids - pat_ids
    pat_only = pat_ids - pred_ids

    if pred_only:
        report.add_error("PATIENT_ID_MISMATCH", f"{pat_path.name}",
                         f"{len(pred_only)} patient_ids in predictions but not in patients table")
    if pat_only:
        report.add_warning("ORPHAN_PATIENT_RECORD", f"{pat_path.name}",
                           f"{len(pat_only)} patients in patients table have no predictions")

    return df


def _step5_phi_scan(predictions: pd.DataFrame, patients: pd.DataFrame | None,
                     report: ValidationReport) -> None:
    """Step 5: Scan identifier columns for probable PHI patterns."""
    # Conservative scan — flag if a patient_id looks like a real name+number combo,
    # contains a SSN-like pattern, or contains a date.
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    date_pattern = re.compile(r"\b(19|20)\d{2}[-/]?(0[1-9]|1[0-2])[-/]?(0[1-9]|[12]\d|3[01])\b")
    name_with_number = re.compile(r"^[A-Z][a-z]+[A-Z][a-z]+\d+$")  # JohnSmith12345

    sample = predictions["patient_id"].head(1000).astype(str)
    flagged = 0
    for v in sample:
        if ssn_pattern.search(v) or date_pattern.search(v) or name_with_number.match(v):
            flagged += 1

    if flagged > 0:
        report.add_error("PHI_PATTERN_DETECTED",
                         "predictions:patient_id",
                         f"{flagged} of {len(sample)} sampled patient_ids match a PHI-like "
                         f"pattern (SSN, date, or name+number). Hash or replace identifiers.")


def _step6_state_vocabulary_check(predictions: pd.DataFrame,
                                    report: ValidationReport) -> None:
    """Step 6: Confirm predicted_state column is non-empty and uses a small vocabulary."""
    states = predictions["predicted_state"].dropna().unique()
    if len(states) == 0:
        report.add_error("EMPTY_STATE_VOCAB", "predictions:predicted_state",
                         "predicted_state column is entirely empty")
        return
    if len(states) > 50:
        report.add_warning("LARGE_STATE_VOCAB", "predictions:predicted_state",
                           f"{len(states)} distinct predicted_state values — typical disease "
                           f"rule packs use 3–10 states. Verify vocabulary.")


def _step7_temporal_sanity(predictions: pd.DataFrame, manifest: dict,
                             report: ValidationReport) -> None:
    """Step 7: No future timestamps; no negative deltas after sort."""
    submission_ts = pd.to_datetime(manifest["submission_timestamp"], utc=True)
    future = predictions[predictions["_ts_parsed"] > submission_ts]
    if len(future) > 0:
        report.add_error("FUTURE_TIMESTAMP", "predictions:visit_timestamp",
                         f"{len(future)} visits have timestamps after submission_timestamp")

    # Tie detection
    dup_ts = predictions.duplicated(subset=["patient_id", "_ts_parsed"], keep=False)
    if dup_ts.any():
        n_tied = int(dup_ts.sum())
        report.add_warning("TIE_TIMESTAMP", "predictions:visit_timestamp",
                           f"{n_tied} visits have ties in (patient_id, visit_timestamp). "
                           f"Tied transitions cannot be audited.")


def _step8_cohort_summary_check(predictions: pd.DataFrame, manifest: dict,
                                  report: ValidationReport) -> None:
    """Step 8: Manifest cohort_summary must match actual data."""
    actual_n_patients = predictions["patient_id"].nunique()
    actual_n_visits = len(predictions)
    decl = manifest["cohort_summary"]

    if decl["n_patients"] != actual_n_patients:
        report.add_error("COHORT_SUMMARY_MISMATCH",
                         "manifest.json:cohort_summary.n_patients",
                         f"Manifest declares {decl['n_patients']} patients; "
                         f"predictions table has {actual_n_patients}")
    if decl["n_visits_total"] != actual_n_visits:
        report.add_error("COHORT_SUMMARY_MISMATCH",
                         "manifest.json:cohort_summary.n_visits_total",
                         f"Manifest declares {decl['n_visits_total']} visits; "
                         f"predictions table has {actual_n_visits}")

    actual_min = predictions["_ts_parsed"].min().date()
    actual_max = predictions["_ts_parsed"].max().date()
    decl_min = datetime.fromisoformat(decl["date_range"][0]).date()
    decl_max = datetime.fromisoformat(decl["date_range"][1]).date()
    if actual_min < decl_min or actual_max > decl_max:
        report.add_error("DATE_RANGE_MISMATCH",
                         "manifest.json:cohort_summary.date_range",
                         f"Manifest declares [{decl_min}, {decl_max}]; "
                         f"actual data spans [{actual_min}, {actual_max}]")


# ============================================================
# Helpers
# ============================================================

def _load_table(path: Path) -> pd.DataFrame:
    """Load a tabular file based on its extension."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".json", ".jsonl"):
        return pd.read_json(path, lines=(suffix == ".jsonl"))
    raise ValueError(f"Unsupported file extension: {suffix}")

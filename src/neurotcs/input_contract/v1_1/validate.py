"""
NeuroTCS Input Contract — Reference Validator (v1.1.0)

Backward-compatible extension of the v1.0 validator. All v1.0 submissions
remain valid under this validator. v1.1 adds three new validation steps:

    [9]  Biomarker structural validation
    [10] UCUM unit validation and consistency
    [11] State-or-biomarker presence check

Design principles (unchanged from v1.0):
    1. Fail-closed. If anything is wrong, refuse to declare valid.
    2. Report ALL errors at once.
    3. No silent inference.
    4. Deterministic.
    5. No PHI leakage in error messages.

Usage:
    from validate import validate_submission, ValidationReport

    report = validate_submission("path/to/submission/")
    if report.is_valid():
        print("OK")
    else:
        for err in report.errors:
            print(err)
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


# ============================================================
# Constants
# ============================================================

SUPPORTED_CONTRACT_VERSIONS = ("1.0.0", "1.1.0")
THIS_VALIDATOR_VERSION = "1.1.0"
SCHEMA_PATH = Path(__file__).parent / "schemas" / "manifest.schema.json"

# UCUM common subset — curated allowlist for medical AI biomarkers.
# Reference: https://ucum.org/ucum
UCUM_ALLOWLIST = frozenset({
    # Volume
    "mL", "cm3", "L", "uL", "mm3",
    # Length / area
    "mm", "cm", "m", "mm2", "cm2",
    # Mass
    "g", "mg", "kg", "ug", "ng",
    # Time
    "s", "min", "h", "d", "wk", "mo", "a",
    # Concentration
    "mg/dL", "mmol/L", "umol/L", "ng/mL", "pg/mL", "IU/mL", "g/L",
    # Pressure
    "mm[Hg]", "cm[H2O]", "kPa",
    # Dimensionless
    "%", "1", "score",
    # Counts
    "{count}", "{events}/a",
    # Composite
    "mL/min/{1.73_m2}", "m2", "kg/m2",
})

VALID_VALUE_TYPES = frozenset({"continuous", "ordinal", "count", "percentage"})

# Biomarkers whose value type implies physical non-negativity.
# These categories trigger NEGATIVE_VALUE_FOR_NONNEGATIVE_BIOMARKER warning.
NONNEGATIVE_UNITS = frozenset({
    "mL", "cm3", "L", "uL", "mm3",
    "mm", "cm", "m", "mm2", "cm2", "m2",
    "g", "mg", "kg", "ug", "ng",
    "mg/dL", "mmol/L", "umol/L", "ng/mL", "pg/mL", "IU/mL", "g/L",
    "mm[Hg]", "cm[H2O]", "kPa",
    "{count}",
})


# ============================================================
# Result types (unchanged from v1.0)
# ============================================================

@dataclass
class ValidationIssue:
    severity: str
    code: str
    location: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code} at {self.location}: {self.message}"


@dataclass
class ValidationReport:
    submission_path: str
    contract_version: str = ""
    validator_version: str = THIS_VALIDATOR_VERSION
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    manifest: dict[str, Any] | None = None

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, code: str, location: str, message: str) -> None:
        self.errors.append(ValidationIssue("ERROR", code, location, message))

    def add_warning(self, code: str, location: str, message: str) -> None:
        self.warnings.append(ValidationIssue("WARNING", code, location, message))


# ============================================================
# Main entry point
# ============================================================

def validate_submission(submission_path: str | Path) -> ValidationReport:
    """Run the 11-step validation pipeline on a submission directory.

    Always returns a ValidationReport. Never raises on validation failure.
    Raises only on programmer error.
    """
    if pd is None:
        raise RuntimeError("pandas is required for validation")
    if jsonschema is None:
        raise RuntimeError("jsonschema is required for validation")

    path = Path(submission_path).resolve()
    report = ValidationReport(submission_path=str(path))

    # [1] Manifest
    manifest = _step1_validate_manifest(path, report)
    if manifest is None:
        return report
    report.manifest = manifest
    report.contract_version = manifest["neurotcs_contract_version"]

    # [2] File presence
    if not _step2_check_files(path, manifest, report):
        return report

    # [3] Predictions structural
    predictions = _step3_load_predictions(path, manifest, report)
    if predictions is None:
        return report

    # [4] Patients cross-reference
    patients = None
    if manifest["conformance_level"] in ("L2", "L3"):
        patients = _step4_load_patients(path, manifest, predictions, report)

    # [5] PHI scan
    _step5_phi_scan(predictions, patients, report)

    # [6] State vocabulary
    _step6_state_vocabulary_check(predictions, report)

    # [7] Temporal sanity
    _step7_temporal_sanity(predictions, manifest, report)

    # [8] Cohort summary cross-check
    _step8_cohort_summary_check(predictions, manifest, report)

    # === v1.1 additions below ===

    # [9] Load biomarkers (inline or long-format) and validate structure
    biomarkers = _step9_load_biomarkers(path, manifest, predictions, report)

    # [10] UCUM units + consistency
    _step10_ucum_validation(predictions, biomarkers, report)

    # [11] State-or-biomarker presence
    _step11_state_or_biomarker_check(predictions, biomarkers, report)

    return report


# ============================================================
# Steps 1-8 — carried from v1.0 (preserved exactly)
# ============================================================

def _step1_validate_manifest(path: Path, report: ValidationReport) -> dict | None:
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
            loc = ("manifest.json:" + ".".join(str(p) for p in err.absolute_path)
                   if err.absolute_path else "manifest.json")
            report.add_error("SCHEMA_VIOLATION", loc, err.message)
        return None

    v = manifest.get("neurotcs_contract_version")
    if v not in SUPPORTED_CONTRACT_VERSIONS:
        report.add_error(
            "UNSUPPORTED_CONTRACT_VERSION",
            "manifest.json:neurotcs_contract_version",
            f"Validator v{THIS_VALIDATOR_VERSION} supports {SUPPORTED_CONTRACT_VERSIONS}, "
            f"submission declares v{v}"
        )
        return None

    return manifest


def _step2_check_files(path: Path, manifest: dict, report: ValidationReport) -> bool:
    ok = True
    pred_path = path / manifest["data_files"]["predictions"]
    if not pred_path.exists():
        report.add_error("MISSING_FILE", str(pred_path.name), "Predictions file not found")
        ok = False

    if "patients" in manifest["data_files"]:
        pat_path = path / manifest["data_files"]["patients"]
        if not pat_path.exists():
            report.add_error("MISSING_FILE", str(pat_path.name), "Patients file not found")
            ok = False

    if "biomarkers" in manifest["data_files"]:
        bio_path = path / manifest["data_files"]["biomarkers"]
        if not bio_path.exists():
            report.add_error("MISSING_FILE", str(bio_path.name), "Biomarkers file not found")
            ok = False

    return ok


def _step3_load_predictions(path: Path, manifest: dict,
                             report: ValidationReport) -> pd.DataFrame | None:
    pred_path = path / manifest["data_files"]["predictions"]
    try:
        df = _load_table(pred_path)
    except Exception as e:
        report.add_error("UNREADABLE_FILE", pred_path.name, f"Cannot read: {e}")
        return None

    # v1.1: predicted_state is now CONDITIONAL — required iff no continuous biomarker
    # We do NOT enforce its presence here; that's step 11. But the column SHOULD
    # exist (it may be all-null). If missing entirely AND no continuous_biomarkers
    # column AND no biomarkers.parquet, step 11 will catch it.
    required_base_l1 = ["patient_id", "visit_id", "visit_timestamp"]
    required_base_l2 = required_base_l1 + ["uncertainty", "treatment_flags"]

    level = manifest["conformance_level"]
    required = required_base_l1 if level == "L1" else required_base_l2

    missing = [c for c in required if c not in df.columns]
    if missing:
        report.add_error("MISSING_COLUMNS", f"{pred_path.name}",
                         f"Required columns missing at {level}: {missing}")
        return None

    # patient_id structural
    bad_pid = ~df["patient_id"].apply(
        lambda x: isinstance(x, str) and 1 <= len(x) <= 64
    )
    if bad_pid.any():
        n_bad = int(bad_pid.sum())
        report.add_error("INVALID_TYPE", f"{pred_path.name}:patient_id",
                         f"{n_bad} patient_id values are not non-empty string ≤64 chars")

    if df.duplicated(subset=["patient_id", "visit_id"]).any():
        n_dup = int(df.duplicated(subset=["patient_id", "visit_id"]).sum())
        report.add_error("DUPLICATE_VISIT", f"{pred_path.name}",
                         f"{n_dup} duplicate (patient_id, visit_id) pairs")

    try:
        df["_ts_parsed"] = pd.to_datetime(df["visit_timestamp"], errors="raise", utc=True)
    except Exception as e:
        report.add_error("INVALID_TIMESTAMP", f"{pred_path.name}:visit_timestamp",
                         f"Cannot parse timestamps: {e}")
        return None

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
    if "patients" not in manifest["data_files"]:
        report.add_error("MISSING_PATIENTS_DECL", "manifest.json:data_files",
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
                         f"{len(pred_only)} patient_ids in predictions but not in patients")
    if pat_only:
        report.add_warning("ORPHAN_PATIENT_RECORD", f"{pat_path.name}",
                           f"{len(pat_only)} patients in patients table have no predictions")

    return df


def _step5_phi_scan(predictions: pd.DataFrame, patients: pd.DataFrame | None,
                     report: ValidationReport) -> None:
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    date_pattern = re.compile(
        r"\b(19|20)\d{2}[-/]?(0[1-9]|1[0-2])[-/]?(0[1-9]|[12]\d|3[01])\b"
    )
    name_with_number = re.compile(r"^[A-Z][a-z]+[A-Z][a-z]+\d+$")

    sample = predictions["patient_id"].head(1000).astype(str)
    flagged = 0
    for v in sample:
        if (ssn_pattern.search(v) or date_pattern.search(v)
                or name_with_number.match(v)):
            flagged += 1

    if flagged > 0:
        report.add_error("PHI_PATTERN_DETECTED",
                         "predictions:patient_id",
                         f"{flagged} of {len(sample)} sampled patient_ids match a "
                         f"PHI-like pattern (SSN, date, or name+number).")


def _step6_state_vocabulary_check(predictions: pd.DataFrame,
                                    report: ValidationReport) -> None:
    # v1.1: predicted_state column may not exist if all rows use biomarkers.
    if "predicted_state" not in predictions.columns:
        return
    states = predictions["predicted_state"].dropna().unique()
    if len(states) > 50:
        report.add_warning("LARGE_STATE_VOCAB", "predictions:predicted_state",
                           f"{len(states)} distinct predicted_state values — typical "
                           f"rule packs use 3–10 states.")


def _step7_temporal_sanity(predictions: pd.DataFrame, manifest: dict,
                             report: ValidationReport) -> None:
    submission_ts = pd.to_datetime(manifest["submission_timestamp"], utc=True)
    future = predictions[predictions["_ts_parsed"] > submission_ts]
    if len(future) > 0:
        report.add_error("FUTURE_TIMESTAMP", "predictions:visit_timestamp",
                         f"{len(future)} visits have timestamps after submission_timestamp")

    dup_ts = predictions.duplicated(subset=["patient_id", "_ts_parsed"], keep=False)
    if dup_ts.any():
        n_tied = int(dup_ts.sum())
        report.add_warning("TIE_TIMESTAMP", "predictions:visit_timestamp",
                           f"{n_tied} visits have ties in (patient_id, visit_timestamp)")


def _step8_cohort_summary_check(predictions: pd.DataFrame, manifest: dict,
                                  report: ValidationReport) -> None:
    actual_n_patients = predictions["patient_id"].nunique()
    actual_n_visits = len(predictions)
    decl = manifest["cohort_summary"]

    if decl["n_patients"] != actual_n_patients:
        report.add_error("COHORT_SUMMARY_MISMATCH",
                         "manifest.json:cohort_summary.n_patients",
                         f"Manifest declares {decl['n_patients']}; "
                         f"actual {actual_n_patients}")
    if decl["n_visits_total"] != actual_n_visits:
        report.add_error("COHORT_SUMMARY_MISMATCH",
                         "manifest.json:cohort_summary.n_visits_total",
                         f"Manifest declares {decl['n_visits_total']}; "
                         f"actual {actual_n_visits}")

    actual_min = predictions["_ts_parsed"].min().date()
    actual_max = predictions["_ts_parsed"].max().date()
    decl_min = datetime.fromisoformat(decl["date_range"][0]).date()
    decl_max = datetime.fromisoformat(decl["date_range"][1]).date()
    if actual_min < decl_min or actual_max > decl_max:
        report.add_error("DATE_RANGE_MISMATCH",
                         "manifest.json:cohort_summary.date_range",
                         f"Manifest declares [{decl_min}, {decl_max}]; "
                         f"actual [{actual_min}, {actual_max}]")


# ============================================================
# v1.1 — Steps 9, 10, 11
# ============================================================

def _step9_load_biomarkers(path: Path, manifest: dict, predictions: pd.DataFrame,
                            report: ValidationReport) -> pd.DataFrame | None:
    """Step 9: Load biomarkers (inline or long-format) and validate structure.

    Returns a DataFrame in LONG format normalized regardless of original layout,
    or None if no biomarkers in this submission.
    """
    # Detect inline biomarkers. After parquet round-trip the column may contain
    # numpy.ndarray rather than list, so use a broader iterable check.
    def _is_nonempty_seq(x):
        if x is None:
            return False
        if isinstance(x, list | tuple):
            return len(x) > 0
        # numpy array
        if hasattr(x, "__len__") and not isinstance(x, str | bytes | dict):
            try:
                return len(x) > 0
            except TypeError:
                return False
        return False

    has_inline = ("continuous_biomarkers" in predictions.columns
                  and predictions["continuous_biomarkers"]
                       .apply(_is_nonempty_seq)
                       .any())
    has_longform = "biomarkers" in manifest["data_files"]

    if has_inline and has_longform:
        report.add_error("BIOMARKER_FORMAT_CONFLICT",
                         "submission",
                         "Submission has both inline continuous_biomarkers in predictions "
                         "AND a biomarkers.parquet file. Use one format only.")
        return None

    if not has_inline and not has_longform:
        return None  # No biomarkers — valid as long as states are present (step 11)

    if has_inline:
        return _normalize_inline_biomarkers(predictions, report)
    else:
        return _load_longform_biomarkers(path, manifest, predictions, report)


def _normalize_inline_biomarkers(predictions: pd.DataFrame,
                                  report: ValidationReport) -> pd.DataFrame | None:
    """Flatten inline list-of-dicts into a long-format DataFrame.

    Handles both Python lists and numpy arrays (which parquet round-trips
    produce). Also handles pandas NA / None / nan correctly.
    """
    import numpy as np

    rows = []
    for idx, row in predictions.iterrows():
        items = row.get("continuous_biomarkers")

        # Handle missing values
        if items is None:
            continue
        # pd.isna on a scalar nan
        if isinstance(items, float) and pd.isna(items):
            continue

        # Coerce numpy array to list
        if isinstance(items, np.ndarray):
            items = items.tolist()

        if not isinstance(items, list | tuple):
            report.add_error("INVALID_TYPE",
                             f"predictions:continuous_biomarkers[row {idx}]",
                             f"Expected list/array; got {type(items).__name__}")
            continue

        for bidx, b in enumerate(items):
            if isinstance(b, np.ndarray):
                # Edge case: nested arrays
                b = b.tolist() if b.dtype == object else b
            if not isinstance(b, dict):
                report.add_error("INVALID_TYPE",
                                 f"predictions:continuous_biomarkers[row {idx}][{bidx}]",
                                 f"Expected dict; got {type(b).__name__}")
                continue
            unpacked = _unpack_biomarker_dict(b, row["patient_id"], row["visit_id"],
                                                idx, bidx, report)
            if unpacked is not None:
                rows.append(unpacked)

    if not rows:
        return pd.DataFrame()  # empty but not None

    return pd.DataFrame(rows)


def _unpack_biomarker_dict(b: dict, patient_id: str, visit_id: str,
                            row_idx: int, b_idx: int,
                            report: ValidationReport) -> dict | None:
    """Convert one biomarker dict into a long-format row with structural validation."""
    loc = f"predictions:continuous_biomarkers[row {row_idx}][{b_idx}]"
    required = ["name", "value", "unit", "value_type"]
    missing = [k for k in required if k not in b]
    if missing:
        report.add_error("MISSING_BIOMARKER_FIELDS", loc,
                         f"Required fields missing: {missing}")
        return None

    if not isinstance(b["name"], str) or not b["name"]:
        report.add_error("INVALID_TYPE", loc + ".name",
                         "name must be non-empty string")
        return None

    try:
        value = float(b["value"])
    except (TypeError, ValueError):
        report.add_error("INVALID_TYPE", loc + ".value",
                         f"value must be numeric; got {type(b['value']).__name__}")
        return None

    if b["value_type"] not in VALID_VALUE_TYPES:
        report.add_error("INVALID_VALUE_TYPE", loc + ".value_type",
                         f"value_type must be one of {sorted(VALID_VALUE_TYPES)}; "
                         f"got '{b['value_type']}'")
        return None

    ref_range = b.get("reference_range")
    ref_low, ref_high = None, None
    if ref_range is not None:
        if not (isinstance(ref_range, list | tuple) and len(ref_range) == 2):
            report.add_error("INVALID_TYPE", loc + ".reference_range",
                             "reference_range must be a [low, high] pair")
            return None
        try:
            ref_low, ref_high = float(ref_range[0]), float(ref_range[1])
            if ref_low > ref_high:
                report.add_warning("REFERENCE_RANGE_INVERTED", loc + ".reference_range",
                                   f"ref_low ({ref_low}) > ref_high ({ref_high})")
        except (TypeError, ValueError):
            report.add_error("INVALID_TYPE", loc + ".reference_range",
                             "reference_range values must be numeric")
            return None

    uncertainty = b.get("uncertainty")
    if uncertainty is not None:
        try:
            uncertainty = float(uncertainty)
            if not (0.0 <= uncertainty <= 1.0):
                report.add_warning("UNCERTAINTY_OUT_OF_RANGE",
                                   loc + ".uncertainty",
                                   f"uncertainty {uncertainty} outside [0, 1]")
        except (TypeError, ValueError):
            report.add_error("INVALID_TYPE", loc + ".uncertainty",
                             "uncertainty must be numeric or null")
            return None

    return {
        "patient_id": patient_id,
        "visit_id": visit_id,
        "biomarker_name": b["name"],
        "value": value,
        "unit": str(b["unit"]),
        "value_type": b["value_type"],
        "ref_low": ref_low,
        "ref_high": ref_high,
        "uncertainty": uncertainty,
    }


def _load_longform_biomarkers(path: Path, manifest: dict, predictions: pd.DataFrame,
                                report: ValidationReport) -> pd.DataFrame | None:
    bio_path = path / manifest["data_files"]["biomarkers"]
    try:
        df = _load_table(bio_path)
    except Exception as e:
        report.add_error("UNREADABLE_FILE", bio_path.name, f"Cannot read: {e}")
        return None

    required = ["patient_id", "visit_id", "biomarker_name", "value", "unit", "value_type"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        report.add_error("MISSING_COLUMNS", f"{bio_path.name}",
                         f"Required biomarker columns missing: {missing}")
        return None

    # Cross-reference: every (patient_id, visit_id) in biomarkers MUST exist in predictions
    pred_keys = set(zip(predictions["patient_id"], predictions["visit_id"], strict=False))
    bio_keys = set(zip(df["patient_id"], df["visit_id"], strict=False))
    orphans = bio_keys - pred_keys
    if orphans:
        report.add_error("BIOMARKER_ORPHAN", f"{bio_path.name}",
                         f"{len(orphans)} biomarker (patient_id, visit_id) pairs "
                         f"have no matching predictions row")

    # value_type enum check
    bad_vt = df[~df["value_type"].isin(VALID_VALUE_TYPES)]
    if len(bad_vt) > 0:
        report.add_error("INVALID_VALUE_TYPE", f"{bio_path.name}:value_type",
                         f"{len(bad_vt)} rows have invalid value_type. "
                         f"Allowed: {sorted(VALID_VALUE_TYPES)}")

    # Reference range inverted check
    if "ref_low" in df.columns and "ref_high" in df.columns:
        inverted = df[(df["ref_low"].notna()) & (df["ref_high"].notna())
                       & (df["ref_low"] > df["ref_high"])]
        if len(inverted) > 0:
            report.add_warning("REFERENCE_RANGE_INVERTED",
                               f"{bio_path.name}",
                               f"{len(inverted)} rows have ref_low > ref_high")

    return df


def _step10_ucum_validation(predictions: pd.DataFrame, biomarkers: pd.DataFrame | None,
                              report: ValidationReport) -> None:
    """Step 10: UCUM unit allowlist + consistency check per biomarker name."""
    if biomarkers is None or len(biomarkers) == 0:
        return

    # UCUM allowlist check
    bad_units = biomarkers[
        ~biomarkers["unit"].apply(
            lambda u: (isinstance(u, str)
                       and (u in UCUM_ALLOWLIST or u.startswith("x-")))
        )
    ]
    if len(bad_units) > 0:
        # Aggregate by unique offending unit for readability
        unique_bad = sorted(bad_units["unit"].dropna().astype(str).unique())[:10]
        report.add_error("INVALID_UCUM_UNIT", "biomarkers:unit",
                         f"{len(bad_units)} rows use units not in UCUM allowlist "
                         f"and not x-prefixed. Examples: {unique_bad}")

    # Custom unit warning
    custom_units = biomarkers[biomarkers["unit"].astype(str).str.startswith("x-")]
    if len(custom_units) > 0:
        unique_custom = sorted(custom_units["unit"].astype(str).unique())[:5]
        report.add_warning("CUSTOM_UNIT_USED", "biomarkers:unit",
                           f"{len(custom_units)} rows use custom x- units. "
                           f"Examples: {unique_custom}")

    # Unit consistency per biomarker name
    inconsistent = []
    for name, group in biomarkers.groupby("biomarker_name"):
        units_used = group["unit"].dropna().astype(str).unique()
        if len(units_used) > 1:
            inconsistent.append((name, sorted(units_used)))
    if inconsistent:
        examples = "; ".join(f"{n}: {u}" for n, u in inconsistent[:5])
        report.add_error("INCONSISTENT_UNITS", "biomarkers",
                         f"{len(inconsistent)} biomarker names use inconsistent units. "
                         f"Examples: {examples}")

    # Negative non-negative biomarker warning
    nonneg = biomarkers[
        biomarkers["unit"].isin(NONNEGATIVE_UNITS) & (biomarkers["value"] < 0)
    ]
    if len(nonneg) > 0:
        report.add_warning("NEGATIVE_VALUE_FOR_NONNEGATIVE_BIOMARKER",
                           "biomarkers:value",
                           f"{len(nonneg)} biomarker rows have negative values for "
                           f"physically non-negative units (volume/length/mass/concentration)")


def _step11_state_or_biomarker_check(predictions: pd.DataFrame,
                                       biomarkers: pd.DataFrame | None,
                                       report: ValidationReport) -> None:
    """Step 11: Every prediction row must have predicted_state OR a biomarker."""
    has_state_col = "predicted_state" in predictions.columns

    if has_state_col:
        state_present = predictions["predicted_state"].notna()
    else:
        state_present = pd.Series(False, index=predictions.index)

    # Build a set of (patient_id, visit_id) that have at least one biomarker
    if biomarkers is not None and len(biomarkers) > 0:
        bio_keys = set(zip(biomarkers["patient_id"], biomarkers["visit_id"], strict=False))
    else:
        bio_keys = set()

    bio_present = predictions.apply(
        lambda r: (r["patient_id"], r["visit_id"]) in bio_keys, axis=1
    )

    neither = predictions[~state_present & ~bio_present]
    if len(neither) > 0:
        report.add_error("MISSING_STATE_AND_BIOMARKER",
                         "predictions",
                         f"{len(neither)} rows have neither predicted_state nor any "
                         f"continuous biomarker. Every row must have at least one.")


# ============================================================
# Helpers
# ============================================================

def _load_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".json", ".jsonl"):
        return pd.read_json(path, lines=(suffix == ".jsonl"))
    raise ValueError(f"Unsupported file extension: {suffix}")

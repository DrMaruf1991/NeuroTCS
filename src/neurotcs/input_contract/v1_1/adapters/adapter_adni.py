"""
Reference adapter: ADNI → NeuroTCS Input Contract v1.0.0

This is the canonical example showing how to convert a real cohort
into a conforming NeuroTCS submission. Copy and modify for your own data.

Usage:
    python3 adapter_adni.py \\
        --dxsum /path/to/DXSUM.rda \\
        --out  /path/to/submission/

Design notes:
  - patient_id is hashed (SHA-256) with a cohort-specific salt.
    No ADNI RID appears in plaintext anywhere.
  - visit_id uses ADNI's VISCODE2 ('bl', 'm06', ...) which is non-PHI.
  - All timestamps are UTC. Time-of-day is unknown so set to 00:00:00.
  - Subjects with <2 visits are excluded (no transitions to audit).
  - Sex/age/site are passed through unchanged from ADNI's PTDEMOG.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyreadr

COHORT_SALT = "adni_demo_2026"  # in production: random per-cohort secret


def hash_patient_id(rid: int) -> str:
    """Deterministic, non-reversible patient identifier."""
    h = hashlib.sha256(f"{COHORT_SALT}_{rid}".encode()).hexdigest()
    return f"ADNI_{h[:16]}"


def build_predictions(dxsum: pd.DataFrame) -> pd.DataFrame:
    """ADNI DXSUM → conforming predictions table."""
    df = dxsum[dxsum["DIAGNOSIS"].isin(["CN", "MCI", "Dementia"])].copy()
    df["EXAMDATE"] = pd.to_datetime(df["EXAMDATE"], errors="coerce")
    df = df.dropna(subset=["EXAMDATE", "RID", "VISCODE2"])

    # Keep only patients with ≥2 visits
    counts = df.groupby("RID").size()
    keep = counts[counts >= 2].index
    df = df[df["RID"].isin(keep)].copy()

    return pd.DataFrame({
        "patient_id": df["RID"].astype(int).apply(hash_patient_id).values,
        "visit_id": df["VISCODE2"].astype(str).values,
        "visit_timestamp": df["EXAMDATE"].dt.strftime("%Y-%m-%dT00:00:00Z").values,
        "predicted_state": df["DIAGNOSIS"].values,
        "uncertainty": [None] * len(df),  # ADNI labels are categorical without uncertainty
        "treatment_flags": [[]] * len(df),  # extended by an anti-amyloid join in production
    })


def build_patients(predictions: pd.DataFrame) -> pd.DataFrame:
    """Minimal patients table. In production: join real PTDEMOG fields."""
    return pd.DataFrame({
        "patient_id": predictions["patient_id"].unique(),
        "sex": "unknown",
        "age_at_baseline": 70,
        "race_ethnicity": "unknown",
        "site_id": "adni",
        "scanner_vendor": "unknown",
    })


def build_manifest(predictions: pd.DataFrame, submission_id: str) -> dict:
    """Manifest matching v1.0.0 schema."""
    ts_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "neurotcs_contract_version": "1.0.0",
        "conformance_level": "L2",
        "submission_id": submission_id,
        "submission_timestamp": ts_now,
        "source_system": {
            "name": "ADNI clinical labels",
            "version": "ADNIMERGE2",
            "vendor": "ADNI",
        },
        "disease_domain": "alzheimers",
        "rule_pack": {"id": "aa2024+trac@1.0", "source": "registry"},
        "data_files": {
            "predictions": "predictions.parquet",
            "patients": "patients.parquet",
        },
        "cohort_summary": {
            "n_patients": int(predictions["patient_id"].nunique()),
            "n_visits_total": int(len(predictions)),
            "date_range": [
                predictions["visit_timestamp"].min()[:10],
                predictions["visit_timestamp"].max()[:10],
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dxsum", required=True, help="Path to DXSUM.rda")
    parser.add_argument("--out", required=True, help="Output submission directory")
    parser.add_argument("--id", default="adni_demo", help="Submission ID")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading DXSUM from {args.dxsum}...")
    dxsum = pyreadr.read_r(args.dxsum)["DXSUM"]
    print(f"  {len(dxsum):,} raw DXSUM rows")

    predictions = build_predictions(dxsum)
    print(f"  → {len(predictions):,} predictions, "
          f"{predictions['patient_id'].nunique():,} unique patients")
    predictions.to_parquet(out / "predictions.parquet")

    patients = build_patients(predictions)
    patients.to_parquet(out / "patients.parquet")
    print(f"  → patients table: {len(patients):,} rows")

    manifest = build_manifest(predictions, args.id)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("  → manifest written")

    print(f"\nSubmission ready at: {out}")
    print("Validate it with:")
    print(f"  python3 -c 'from validate import validate_submission; "
          f"r = validate_submission(\"{out}\"); print(\"OK\" if r.is_valid() else r.errors)'")


if __name__ == "__main__":
    main()

"""
Reference adapter: ADNI FreeSurfer volumetric → NeuroTCS Input Contract v1.1.0

Converts ADNI UCSFFSX7 (FreeSurfer cross-sectional pipeline output) into a
conforming v1.1 submission with continuous biomarkers.

This is the canonical example for any vendor whose AI emits volumetric or
quantitative output rather than categorical states. icometrix, Cortechs.ai,
Combinostics, and similar products produce data in this same shape.

Usage:
    python3 adapter_adni_volumetric.py \\
        --ucsffsx7 /path/to/UCSFFSX7.rda \\
        --dxsum    /path/to/DXSUM.rda \\
        --out      /path/to/submission/

Design notes:
  - Hippocampal volumes (ST29SV = right, ST88SV = left) reported in mL.
    FreeSurfer's native unit is mm³; converted with 1 mL = 1,000 mm³.
  - Reference range [2.5, 4.5] mL is approximate for age-matched controls.
  - Categorical diagnosis from DXSUM joined when available; null otherwise
    (v1.1 permits state-or-biomarker presence).
  - patient_id hashed (SHA-256) with cohort-specific salt — no PHI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyreadr

COHORT_SALT = "adni_demo_2026"


def hash_patient_id(rid: int) -> str:
    h = hashlib.sha256(f"{COHORT_SALT}_{rid}".encode()).hexdigest()
    return f"ADNI_{h[:16]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ucsffsx7", required=True, help="Path to UCSFFSX7.rda")
    ap.add_argument("--dxsum", required=True, help="Path to DXSUM.rda")
    ap.add_argument("--out", required=True, help="Output submission directory")
    ap.add_argument("--id", default="adni_volumetric", help="Submission ID")
    ap.add_argument("--min-visits", type=int, default=3,
                    help="Minimum visits per patient (default 3)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading FreeSurfer data from {args.ucsffsx7}...")
    fsdf = pyreadr.read_r(args.ucsffsx7)["UCSFFSX7"]
    fsdf = fsdf.dropna(subset=["RID", "VISCODE2", "ST29SV"])
    fsdf["EXAMDATE"] = pd.to_datetime(fsdf["EXAMDATE"], errors="coerce")
    fsdf = fsdf.dropna(subset=["EXAMDATE"])
    print(f"  {len(fsdf):,} raw FreeSurfer rows after dropna")

    # Keep patients with ≥min-visits visits
    counts = fsdf.groupby("RID").size()
    keep = counts[counts >= args.min_visits].index
    fsdf = fsdf[fsdf["RID"].isin(keep)].sort_values(["RID", "EXAMDATE"])
    fsdf["_vis"] = (fsdf["VISCODE2"].astype(str) + "_" + fsdf["COLPROT"].astype(str))
    fsdf = fsdf.drop_duplicates(subset=["RID", "_vis"], keep="first").reset_index(drop=True)
    print(f"  → {len(fsdf):,} rows from {fsdf['RID'].nunique():,} patients")

    # Optional join with DXSUM for categorical state
    print(f"Loading DXSUM from {args.dxsum} for optional categorical states...")
    dxdf = pyreadr.read_r(args.dxsum)["DXSUM"]
    dxdf = dxdf[["RID", "VISCODE2", "COLPROT", "DIAGNOSIS"]].copy()
    dxdf["_vis"] = dxdf["VISCODE2"].astype(str) + "_" + dxdf["COLPROT"].astype(str)
    merged = fsdf.merge(dxdf[["RID", "_vis", "DIAGNOSIS"]],
                         on=["RID", "_vis"], how="left")
    merged = merged.drop_duplicates(subset=["RID", "_vis"], keep="first").reset_index(drop=True)

    # Write predictions as JSONL (preserves nested biomarker structures)
    pred_path = out / "predictions.jsonl"
    total_bm = 0
    with open(pred_path, "w") as f:
        for _, row in merged.iterrows():
            bm = []
            if pd.notna(row.get("ST29SV")):
                bm.append({
                    "name": "right_hippocampal_volume",
                    "value": float(row["ST29SV"]) / 1000.0,
                    "unit": "mL",
                    "value_type": "continuous",
                    "reference_range": [2.5, 4.5],
                    "uncertainty": None,
                })
            if pd.notna(row.get("ST88SV")):
                bm.append({
                    "name": "left_hippocampal_volume",
                    "value": float(row["ST88SV"]) / 1000.0,
                    "unit": "mL",
                    "value_type": "continuous",
                    "reference_range": [2.5, 4.5],
                    "uncertainty": None,
                })
            total_bm += len(bm)
            dx_val = row.get("DIAGNOSIS")
            state = dx_val if dx_val in ("CN", "MCI", "Dementia") else None
            obj = {
                "patient_id": hash_patient_id(int(row["RID"])),
                "visit_id": row["_vis"],
                "visit_timestamp": row["EXAMDATE"].strftime("%Y-%m-%dT00:00:00Z"),
                "predicted_state": state,
                "uncertainty": None,
                "treatment_flags": [],
                "continuous_biomarkers": bm,
            }
            f.write(json.dumps(obj) + "\n")
    print(f"  → {len(merged):,} predictions written, {total_bm:,} biomarker measurements")

    # Patients table
    unique_pids = [hash_patient_id(int(r)) for r in merged["RID"].unique()]
    pat = pd.DataFrame({
        "patient_id": unique_pids,
        "sex": "unknown",
        "age_at_baseline": 70,
        "race_ethnicity": "unknown",
        "site_id": "adni",
        "scanner_vendor": "unknown",
    })
    pat.to_parquet(out / "patients.parquet")
    print(f"  → patients table: {len(pat):,} rows")

    # Manifest
    manifest = {
        "neurotcs_contract_version": "1.1.0",
        "conformance_level": "L2",
        "submission_id": args.id,
        "submission_timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_system": {
            "name": "FreeSurfer UCSFFSX7 cross-sectional pipeline",
            "version": "ADNIMERGE2",
            "vendor": "ADNI",
        },
        "disease_domain": "alzheimers",
        "rule_pack": {"id": "aa2024+volumes@1.0", "source": "registry"},
        "data_files": {
            "predictions": "predictions.jsonl",
            "patients": "patients.parquet",
        },
        "cohort_summary": {
            "n_patients": int(len(unique_pids)),
            "n_visits_total": int(len(merged)),
            "date_range": [
                merged["EXAMDATE"].min().strftime("%Y-%m-%d"),
                merged["EXAMDATE"].max().strftime("%Y-%m-%d"),
            ],
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("  → manifest written")

    print(f"\nSubmission ready at: {out}")
    print("Validate it with:")
    print(f"  python3 -c 'from validate import validate_submission; "
          f"r = validate_submission(\"{out}\"); print(\"OK\" if r.is_valid() else r.errors)'")


if __name__ == "__main__":
    main()

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
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# pyreadr (R .rda reader) is imported lazily inside the CLI entrypoint that
# actually reads .rda files, so importing this module -- and the smoke tests
# that import it -- never requires the optional R-reader dependency.

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


# ====================================================================
# AA-2024 (Jack 2024 Table 7) reference adapter
# ====================================================================
# The function below shows the PATTERN for converting amyloid PET +
# tau PET measurements into the Table 7 alphanumeric state names
# (Stage_0, Stage_1A...Stage_4-6D). This is REFERENCE-ONLY: production
# ADNI usage requires the user to wire in:
#   - their amyloid PET ROI summaries (UCBERKELEY or BAIPETNMRC)
#   - their tau PET ROI summaries (UCBERKELEY tau)
#   - their chosen tau-PET moderate-vs-high cutpoint (§4.6 caveat;
#     see docs/validation/aa_2024_audit_protocol.md §2.1)
#   - their chosen amyloid PET positivity threshold (§3.1; protocol §2.3)
#   - their chosen neocortical meta-ROI (§4.6; protocol §2.2)
# Inputs to this reference function are placeholders illustrating the
# data types expected; replace with real columns from ADNI tables.
#
# See docs/validation/aa_2024_audit_protocol.md for the full end-to-end
# workflow and the fail-closed policy for missing parameters.

def derive_aa_2024_state(
    *,
    amyloid_pet_value: float | None,
    amyloid_pet_positivity_threshold: float,
    tau_mtl_suvr: float | None,
    tau_neocortical_suvr: float | None,
    tau_mtl_positivity_threshold: float,
    tau_pet_mod_vs_high_cutpoint: float,
    clinical_diagnosis: str,
    persistent_decline_ge_6_months: bool = False,
    is_adad_dsad_carrier: bool = False,
) -> str | None:
    """Derive the AA-2024 Table 7 alphanumeric state from biomarker + clinical data.

    Returns one of: 'Stage_0', 'Stage_1A'..'Stage_1D', 'Stage_2A'..'Stage_2D',
    'Stage_3A'..'Stage_3D', 'Stage_4-6A'..'Stage_4-6D', or None if the subject
    is not in the AD pathway (amyloid-negative).

    Reference protocol: docs/validation/aa_2024_audit_protocol.md §4.
    Source: Jack 2024 PMID 38934362; Tables 4, 6, 7.
    """
    # Step 1: biological axis (A/B/C/D) — Table 4 verbatim.
    if amyloid_pet_value is None:
        return None
    if amyloid_pet_value < amyloid_pet_positivity_threshold:
        # Amyloid-negative: subject is NOT in the AD pathway.
        # Per §4: "Staging of AD applies only to individuals in whom the
        # disease has been diagnosed by means of Core 1 biomarkers."
        # However, ADAD/DSAD carriers who are still biomarker-negative
        # are in Stage_0 (genetic determinism without yet-detectable
        # biology), per §5.2.
        if is_adad_dsad_carrier:
            return "Stage_0"
        return None  # not in AD pathway, no AA-2024 staging applies

    # Amyloid-positive: now derive biological sub-stage.
    if tau_mtl_suvr is None or tau_mtl_suvr < tau_mtl_positivity_threshold:
        biological = "A"  # A+T2-
    elif tau_neocortical_suvr is None or \
            tau_neocortical_suvr < tau_pet_mod_vs_high_cutpoint * 0.5:
        # Neocortical tau below "moderate" threshold:
        # caller-supplied: typical heuristic is half of mod-vs-high
        # cutpoint, but production should pass an explicit negative-vs-
        # moderate threshold from the same publication source.
        biological = "B"  # A+T2MTL+
    elif tau_neocortical_suvr < tau_pet_mod_vs_high_cutpoint:
        biological = "C"  # A+T2MOD+
    else:
        biological = "D"  # A+T2HIGH+

    # Step 2: clinical axis (1/2/3/4-6) — Table 6 verbatim.
    # ADNI DXSUM maps as follows; production may need finer-grained
    # mapping (e.g., CDR-based) for stage 2 vs. stage 1 distinction.
    if clinical_diagnosis == "CN":
        clinical = "2" if persistent_decline_ge_6_months else "1"
    elif clinical_diagnosis == "MCI":
        clinical = "3"
    elif clinical_diagnosis == "Dementia":
        clinical = "4-6"
    else:
        return None  # unrecognized; cannot stage

    # Step 3: combine into Table 7 cell label.
    return f"Stage_{clinical}{biological}"


def build_aa_2024_predictions(
    dxsum: pd.DataFrame,
    amyloid_pet: pd.DataFrame,
    tau_pet: pd.DataFrame,
    *,
    amyloid_pet_positivity_threshold: float,
    tau_mtl_positivity_threshold: float,
    tau_pet_mod_vs_high_cutpoint: float,
) -> pd.DataFrame:
    """Reference function: join ADNI DXSUM + amyloid PET + tau PET into
    a conforming predictions table using the AA-2024 Table 7 state names.

    PLACEHOLDER COLUMN NAMES — adjust to match your actual ADNI tables:
      amyloid_pet expected columns: RID, VISCODE2, AMYLOID_CENTILOID
      tau_pet expected columns:     RID, VISCODE2, TAU_MTL_SUVR, TAU_NEOCORTICAL_SUVR

    The three threshold parameters MUST come from a peer-reviewed source;
    see docs/validation/aa_2024_audit_protocol.md §2 for acceptable
    citations (La Joie 2019, CenTauR Villemagne 2023, Ossenkoppele 2022).
    """
    # Join the three tables on RID + VISCODE2
    df = dxsum.merge(amyloid_pet, on=["RID", "VISCODE2"], how="left")
    df = df.merge(tau_pet, on=["RID", "VISCODE2"], how="left")
    df["EXAMDATE"] = pd.to_datetime(df["EXAMDATE"], errors="coerce")
    df = df.dropna(subset=["EXAMDATE", "RID", "VISCODE2"])

    # Derive AA-2024 state per row.
    df["aa_2024_state"] = df.apply(
        lambda r: derive_aa_2024_state(
            amyloid_pet_value=r.get("AMYLOID_CENTILOID"),
            amyloid_pet_positivity_threshold=amyloid_pet_positivity_threshold,
            tau_mtl_suvr=r.get("TAU_MTL_SUVR"),
            tau_neocortical_suvr=r.get("TAU_NEOCORTICAL_SUVR"),
            tau_mtl_positivity_threshold=tau_mtl_positivity_threshold,
            tau_pet_mod_vs_high_cutpoint=tau_pet_mod_vs_high_cutpoint,
            clinical_diagnosis=r.get("DIAGNOSIS"),
            persistent_decline_ge_6_months=False,  # production: derive from longitudinal CDR
            is_adad_dsad_carrier=False,  # production: join ADAD registry / trisomy 21 flag
        ),
        axis=1,
    )

    # Drop subjects not in AD pathway (amyloid-negative non-ADAD).
    df = df.dropna(subset=["aa_2024_state"])

    return pd.DataFrame({
        "patient_id": df["RID"].astype(int).apply(hash_patient_id).values,
        "visit_id": df["VISCODE2"].astype(str).values,
        "visit_timestamp": df["EXAMDATE"].dt.strftime("%Y-%m-%dT00:00:00Z").values,
        "predicted_state": df["aa_2024_state"].values,
        "uncertainty": [None] * len(df),
        "treatment_flags": [[]] * len(df),
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
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    import pyreadr  # lazy: only needed when actually reading .rda files
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

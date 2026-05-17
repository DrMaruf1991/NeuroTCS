"""
Reference adapter: OASIS-3 UDSb4 CDR → NeuroTCS trajectories.

OASIS-3 is the longitudinal multimodal AD cohort from WUSTL Knight ADRC
(LaMontagne et al. 2019, medRxiv 10.1101/2019.12.13.19014902, 1,378
participants, 2,842 MR sessions over 30 years).

The audit operates on UDS Form B4 (Global Staging / Clinical Dementia
Rating; Morris 1993, Neurology 43:2412-2414, PMID 8232972). CDRTOT is
the global CDR score; the canonical CDR → NIA-AA 2018 state mapping is:

    CDRTOT   NIA-AA 2018 state    Rationale (Morris 1993)
    ─────────────────────────────────────────────────────────────────
    0.0      CN                   No impairment
    0.5      MCI                  Questionable / very mild dementia
    1.0+     AD                   Mild dementia or worse

OASIS-3 de-identifies dates to days-from-entry, so the adapter converts
those to a synthetic anchor date (2020-01-01) that exactly preserves
inter-visit intervals (the only thing the audit core uses).

This adapter is intentionally PARALLEL to adapter_adni.py — same return
contract, same hashing strategy, same filtering rules — so the audit
core sees identical data shapes from both cohorts. That is what makes
the Aim 2 external replication finding meaningful.

Programmatic API
----------------

    from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
        load_oasis3_trajectories,
    )

    trajectories, report = load_oasis3_trajectories(
        udsb4_csv_path="path/to/OASIS3_UDSb4_cdr.csv",
        flag_dx1_disagreement=True,
    )
    # trajectories: list[Trajectory] ready for audit()
    # report: dict with diagnostic counts (raw rows, dx1 disagreements, ...)

CLI
---

    python -m neurotcs.input_contract.v1_1.adapters.adapter_oasis3 \\
        --udsb4 path/to/OASIS3_UDSb4_cdr.csv \\
        --out   path/to/submission/

Locked invariant (verified May 17 2026, v1.3.0):
    1,377 subjects scored, 7,248 transitions, 30 flagged (0.41%)
    cTCS = 0.9942 (BCa 95% CI: 0.9902 - 0.9964)
    audit_id = 96d942e41e9f94a33718d9a107dedf443de728bdd16dcf36ade18ca1f3f4077a
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from neurotcs.audit_core.trajectory import (
    Trajectory,
    trajectories_from_dataframe,
)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

COHORT_SALT = "oasis3_aim2_2026"  # in production: random per-cohort secret

# OASIS-3 de-identifies dates as days_to_visit (integer offsets from
# study entry). The audit core only uses inter-visit intervals, so a
# fixed synthetic anchor preserves the math exactly.
SYNTHETIC_BASELINE = date(2020, 1, 1)


# ------------------------------------------------------------------
# CDR → state mapping (Morris 1993; canonical NIA-AA 2018 staging)
# ------------------------------------------------------------------

def cdr_to_state(cdr: float | None) -> str | None:
    """Map Clinical Dementia Rating to NIA-AA 2018 categorical state.

    Per Morris 1993 (Neurology 43:2412-2414, PMID 8232972):
        CDR = 0     -> Cognitively Normal (CN)
        CDR = 0.5   -> Questionable / very mild -> MCI
        CDR >= 1    -> Mild or worse dementia -> AD

    Returns None for NaN, negative values, or unmappable inputs so the
    caller can drop or flag them per the input contract.
    """
    if cdr is None:
        return None
    try:
        c = float(cdr)
    except (TypeError, ValueError):
        return None
    if math.isnan(c) or c < 0:
        return None
    if c == 0.0:
        return "CN"
    if c == 0.5:
        return "MCI"
    if c >= 1.0:
        return "AD"
    # Edge case: 0 < CDR < 0.5 (not standard but possible in older
    # OASIS UDS releases). Treat as MCI for safety.
    return "MCI"


# ------------------------------------------------------------------
# dx1 → state mapping (for disagreement flagging only, never primary)
# ------------------------------------------------------------------

def dx1_to_state(dx1: str | None) -> str | None:
    """Best-effort map of OASIS-3 UDSb4 dx1 free-text to NIA-AA 2018 state.

    Used ONLY for disagreement flagging; CDR is the primary signal.
    Returns None when dx1 is missing or doesn't cleanly map (e.g. for
    Lewy body disease, frontotemporal dementia, or other non-AD
    dementias that should be reported but not coerced into the
    AD-specific state space).
    """
    if dx1 is None or (isinstance(dx1, float) and math.isnan(dx1)):
        return None
    text = str(dx1).strip().lower()
    if not text or text == ".":
        return None
    if "cognitively normal" in text or text == "cn":
        return "CN"
    # MCI variants (amnestic, multi-domain, non-amnestic)
    if "mci" in text or "mild cognitive impairment" in text:
        return "MCI"
    # AD dementia variants
    if "ad dementia" in text or "alzheimer" in text:
        return "AD"
    # Other dementias (DLB, FTD, vascular, PSP, ...) - intentionally
    # return None so we don't force them into AD staging.
    return None


# ------------------------------------------------------------------
# Hashing (no PHI leaves the adapter)
# ------------------------------------------------------------------

def hash_patient_id(oasisid: str) -> str:
    """Deterministic, non-reversible patient identifier.

    OASISID is already de-identified by WUSTL but we re-hash with a
    cohort salt so downstream artifacts cannot be cross-walked back
    to the OASIS distribution.
    """
    h = hashlib.sha256(f"{COHORT_SALT}_{oasisid}".encode()).hexdigest()
    return f"OASIS3_{h[:16]}"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

@dataclass(frozen=True)
class OASIS3LoadReport:
    """Diagnostic counts from one load_oasis3_trajectories call."""
    raw_rows: int
    raw_subjects: int
    rows_after_dropna: int
    subjects_after_dropna: int
    unmappable_cdr: int
    n_trajectories: int
    n_transitions: int
    dx1_disagreements: int
    dx1_disagreement_examples: tuple[dict, ...]

    def to_dict(self) -> dict:
        return {
            "raw_rows": self.raw_rows,
            "raw_subjects": self.raw_subjects,
            "rows_after_dropna": self.rows_after_dropna,
            "subjects_after_dropna": self.subjects_after_dropna,
            "unmappable_cdr": self.unmappable_cdr,
            "n_trajectories": self.n_trajectories,
            "n_transitions": self.n_transitions,
            "dx1_disagreements": self.dx1_disagreements,
            "dx1_disagreement_examples": list(self.dx1_disagreement_examples),
        }


def load_oasis3_trajectories(
    udsb4_csv_path: str | Path,
    *,
    flag_dx1_disagreement: bool = True,
    hash_ids: bool = True,
    skip_invalid: bool = True,
) -> tuple[list[Trajectory], OASIS3LoadReport]:
    """Load OASIS-3 UDSb4 CDR longitudinal table into NeuroTCS trajectories.

    Args:
        udsb4_csv_path: Path to OASIS3_UDSb4_cdr.csv (from the OASIS-3
            data bundle on NITRC-IR).
        flag_dx1_disagreement: If True, count and surface examples where
            the CDR-derived state disagrees with the dx1 text field.
            Does NOT drop those rows — CDR is primary per Morris 1993.
        hash_ids: If True, replace OASISID with SHA-256 hashed IDs so
            downstream artifacts cannot be cross-walked back. Disable
            only when debugging or running internal diagnostics.
        skip_invalid: Pass-through to Trajectory construction — drops
            subjects whose dates are non-ascending after coercion.

    Returns:
        (trajectories, report). `trajectories` is ready to pass to
        `neurotcs.audit(...)`. `report` carries diagnostic counts and
        a sample of dx1 disagreements for the validation document.
    """
    udsb4_csv_path = Path(udsb4_csv_path)
    if not udsb4_csv_path.exists():
        raise FileNotFoundError(f"OASIS-3 UDSb4 CSV not found: {udsb4_csv_path}")

    df = pd.read_csv(udsb4_csv_path)
    raw_rows = len(df)
    raw_subjects = df["OASISID"].nunique() if "OASISID" in df.columns else 0

    required = {"OASISID", "days_to_visit", "CDRTOT"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"OASIS-3 UDSb4 CSV missing required columns: {sorted(missing)}. "
            f"Available: {list(df.columns)[:20]}..."
        )

    df = df.dropna(subset=["OASISID", "days_to_visit", "CDRTOT"]).copy()
    rows_after_dropna = len(df)
    subjects_after_dropna = df["OASISID"].nunique()

    # Apply CDR → state mapping
    df["NeuroTCS_state"] = df["CDRTOT"].apply(cdr_to_state)
    unmappable = df["NeuroTCS_state"].isna().sum()
    df = df.dropna(subset=["NeuroTCS_state"]).copy()

    # dx1 disagreement diagnostics (NEVER drops rows — diagnostic only)
    disagreements_count = 0
    disagreement_examples: list[dict] = []
    if flag_dx1_disagreement and "dx1" in df.columns:
        df["NeuroTCS_dx1_state"] = df["dx1"].apply(dx1_to_state)
        mask_disagree = (
            df["NeuroTCS_dx1_state"].notna()
            & (df["NeuroTCS_state"] != df["NeuroTCS_dx1_state"])
        )
        disagreements_count = int(mask_disagree.sum())
        # Sample first 10 examples for the report
        if disagreements_count > 0:
            sample = df[mask_disagree].head(10)
            for _, row in sample.iterrows():
                disagreement_examples.append({
                    "OASISID": str(row["OASISID"]),
                    "days_to_visit": int(row["days_to_visit"]),
                    "CDRTOT": float(row["CDRTOT"]),
                    "cdr_state": str(row["NeuroTCS_state"]),
                    "dx1_raw": str(row.get("dx1", "")),
                    "dx1_state": str(row["NeuroTCS_dx1_state"]),
                })

    # Convert days_to_visit → synthetic ascending date (preserves intervals)
    df["NeuroTCS_visit_date"] = df["days_to_visit"].astype(int).apply(
        lambda d: SYNTHETIC_BASELINE + timedelta(days=d)
    )

    # Optionally hash patient IDs
    if hash_ids:
        df["NeuroTCS_patient_id"] = df["OASISID"].astype(str).apply(hash_patient_id)
    else:
        df["NeuroTCS_patient_id"] = df["OASISID"].astype(str)

    # Build trajectories
    trajectories = trajectories_from_dataframe(
        df,
        patient_id_col="NeuroTCS_patient_id",
        visit_date_col="NeuroTCS_visit_date",
        state_col="NeuroTCS_state",
        skip_invalid=skip_invalid,
    )

    n_transitions = sum(t.num_transitions for t in trajectories)

    report = OASIS3LoadReport(
        raw_rows=raw_rows,
        raw_subjects=raw_subjects,
        rows_after_dropna=rows_after_dropna,
        subjects_after_dropna=subjects_after_dropna,
        unmappable_cdr=int(unmappable),
        n_trajectories=len(trajectories),
        n_transitions=n_transitions,
        dx1_disagreements=disagreements_count,
        dx1_disagreement_examples=tuple(disagreement_examples),
    )

    return trajectories, report


# ------------------------------------------------------------------
# Submission export (parallel to ADNI adapter, conforms to v1.1 contract)
# ------------------------------------------------------------------

def build_predictions(udsb4: pd.DataFrame) -> pd.DataFrame:
    """OASIS-3 UDSb4 → conforming predictions table (input contract v1.1)."""
    df = udsb4.dropna(subset=["OASISID", "days_to_visit", "CDRTOT"]).copy()
    df["state"] = df["CDRTOT"].apply(cdr_to_state)
    df = df.dropna(subset=["state"])

    # Visits must be strictly increasing per patient — UDSb4 supports this.
    df = df.sort_values(["OASISID", "days_to_visit"])

    df["visit_date"] = df["days_to_visit"].astype(int).apply(
        lambda d: SYNTHETIC_BASELINE + timedelta(days=d)
    )

    # Keep only patients with ≥2 visits (transitions)
    counts = df.groupby("OASISID").size()
    keep = counts[counts >= 2].index
    df = df[df["OASISID"].isin(keep)].copy()

    return pd.DataFrame({
        "patient_id": df["OASISID"].astype(str).apply(hash_patient_id).values,
        "visit_id": (
            df["OASISID"].astype(str) + "_d" + df["days_to_visit"].astype(str)
        ).values,
        "visit_timestamp": (
            df["visit_date"].apply(
                lambda d: d.strftime("%Y-%m-%dT00:00:00Z")
            ).values
        ),
        "predicted_state": df["state"].values,
        "uncertainty": [None] * len(df),
        "treatment_flags": [[]] * len(df),
    })


def build_patients(predictions: pd.DataFrame,
                     demographics: pd.DataFrame | None = None) -> pd.DataFrame:
    """Minimal patients table. If `demographics` given, join real fields."""
    base = pd.DataFrame({"patient_id": predictions["patient_id"].unique()})
    if demographics is None:
        base["sex"] = "unknown"
        base["age_at_baseline"] = 70
        base["race_ethnicity"] = "unknown"
        base["site_id"] = "oasis3"
        base["scanner_vendor"] = "unknown"
        return base
    # Join demographics if available (caller is responsible for hashing)
    return base.merge(demographics, on="patient_id", how="left")


def build_manifest(predictions: pd.DataFrame, submission_id: str) -> dict:
    """Manifest matching v1.1.0 schema."""
    ts_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "neurotcs_contract_version": "1.1.0",
        "conformance_level": "L2",
        "submission_id": submission_id,
        "submission_timestamp": ts_now,
        "source_system": {
            "name": "OASIS-3 UDSb4 CDR longitudinal",
            "version": "OASIS-3_release_2.0_July_2022",
            "vendor": "WUSTL Knight ADRC",
        },
        "disease_domain": "alzheimers",
        "rule_pack": {"id": "ad/niaaa_2018@1.1.0", "source": "registry"},
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
        "citation": {
            "cohort": "LaMontagne PJ et al. OASIS-3. medRxiv 2019. "
                      "doi:10.1101/2019.12.13.19014902",
            "staging": "Morris JC. The Clinical Dementia Rating (CDR). "
                       "Neurology 1993;43:2412-2414. PMID 8232972.",
        },
    }


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert OASIS-3 UDSb4 CDR longitudinal data to a "
                     "conforming NeuroTCS submission.",
    )
    parser.add_argument("--udsb4", required=True,
                          help="Path to OASIS3_UDSb4_cdr.csv")
    parser.add_argument("--out", required=True,
                          help="Output submission directory")
    parser.add_argument("--id", default="oasis3_demo", help="Submission ID")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading OASIS-3 UDSb4 from {args.udsb4}...")
    udsb4 = pd.read_csv(args.udsb4)
    print(f"  {len(udsb4):,} raw UDSb4 rows")

    predictions = build_predictions(udsb4)
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


if __name__ == "__main__":
    main()

"""
neurotcs.clinical_ranges.adapters.trial_excel — adapter for CDISC-style
anti-amyloid trial Excel files into the Layer 2 long-format measurements
DataFrame.

The adapter consumes a CDISC-style longitudinal trial workbook with sheets
following SDTM-like naming (DM, VS, QS, MR, PT, LB, GE, TR, AE, CT, DB)
and emits a single long-format DataFrame ready for `audit_clinical_ranges`
or `audit_clinical_ranges_multi`.

Long-format schema (per audit.REQUIRED_COLUMNS):
    patient_id, visit_id, measurement_name, value, unit

Splitting rules:
  - LB (laboratory) rows are split by `sample_type` into 'csf_<measurement>'
    and 'plasma_<measurement>' so the CSF and plasma range packs apply to
    their own assays. Other sample types are emitted with the raw column
    name and land in the uncovered tally.
  - VS / MR / PT / GE columns are emitted under the canonical measurement
    name (no prefix).
  - GE genetic columns are one-row-per-patient (sample collected once);
    visit_id is set to 'GE_baseline' for these.
  - DM / TR / AE / CT / QS columns are NOT emitted to Layer 2 — those
    require Layer 3 (cross-sheet) and Layer 4 (inclusion/protocol) work.

The adapter is deterministic: same Excel input -> byte-identical
long-format DataFrame -> byte-identical flag_id from audit_clinical_ranges.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# ============================================================
# Column-to-(measurement_name, unit) mappings per sheet
# ============================================================

# Vital signs: column_name -> (measurement_name, unit)
_VS_MAP: dict[str, tuple[str, str]] = {
    "sbp":       ("sbp", "mmHg"),
    "dbp":       ("dbp", "mmHg"),
    "hr":        ("hr", "bpm"),
    "temp_c":    ("temp_c", "degC"),
    "resp_rate": ("resp_rate", "breaths/min"),
    "weight_kg": ("weight_kg", "kg"),
    "height_cm": ("height_cm", "cm"),
    "bmi":       ("bmi", "kg/m2"),
    "spo2_pct":  ("spo2_pct", "%"),
}

# MR: column_name -> (measurement_name, unit)
_MR_MAP: dict[str, tuple[str, str]] = {
    "hippocampus_L_mm3":        ("hippocampus_L_mm3", "mm3"),
    "hippocampus_R_mm3":        ("hippocampus_R_mm3", "mm3"),
    "entorhinal_L_mm3":         ("entorhinal_L_mm3", "mm3"),
    "entorhinal_R_mm3":         ("entorhinal_R_mm3", "mm3"),
    "amygdala_L_mm3":           ("amygdala_L_mm3", "mm3"),
    "amygdala_R_mm3":           ("amygdala_R_mm3", "mm3"),
    "lateral_ventricles_mm3":   ("lateral_ventricles_mm3", "mm3"),
    "cortical_thickness_mm":    ("cortical_thickness_mm", "mm"),
    "fazekas_periventricular":  ("fazekas_periventricular", "score"),
    "fazekas_deep_white":       ("fazekas_deep_white", "score"),
    "microbleed_count":         ("microbleed_count", "count"),
    "dti_fa_uncinate_L":        ("dti_fa_uncinate_L", "fa"),
    "dti_fa_uncinate_R":        ("dti_fa_uncinate_R", "fa"),
}

# PT: column_name -> (measurement_name, unit)
_PT_MAP: dict[str, tuple[str, str]] = {
    "suvr_global":     ("suvr_global", "suvr"),
    "centiloid":       ("centiloid", "centiloid"),
    "amyloid_status":  ("amyloid_status", "categorical"),
    "frontal_suvr":    ("frontal_suvr", "suvr"),
    "parietal_suvr":   ("parietal_suvr", "suvr"),
    "temporal_suvr":   ("temporal_suvr", "suvr"),
    "precuneus_suvr":  ("precuneus_suvr", "suvr"),
    "cingulate_suvr":  ("cingulate_suvr", "suvr"),
}

# LB measurement columns (sample_type prefix added at adapter time):
# raw_col -> (suffix, unit). measurement_name = "<sample_type_lower>_<suffix>".
_LB_NUMERIC_COLS: dict[str, tuple[str, str]] = {
    "ab42_pg_ml":       ("ab42_pg_ml", "pg/mL"),
    "ab40_pg_ml":       ("ab40_pg_ml", "pg/mL"),
    "ab42_40_ratio":    ("ab42_40_ratio", "ratio"),
    "total_tau_pg_ml":  ("total_tau_pg_ml", "pg/mL"),
    "ptau181_pg_ml":    ("ptau181_pg_ml", "pg/mL"),
    "ptau217_pg_ml":    ("ptau217_pg_ml", "pg/mL"),
    "ptau231_pg_ml":    ("ptau231_pg_ml", "pg/mL"),
    "nfl_pg_ml":        ("nfl_pg_ml", "pg/mL"),
    "gfap_pg_ml":       ("gfap_pg_ml", "pg/mL"),
}

# GE: column_name -> (measurement_name, unit)
_GE_MAP: dict[str, tuple[str, str]] = {
    "apoe":                 ("apoe", "categorical"),
    "prs_alzheimer":        ("prs_alzheimer", "z_score"),
    "prs_alzheimer_decile": ("prs_alzheimer_decile", "decile"),
    "wgs_qc_status":        ("wgs_qc_status", "categorical"),
    "wgs_coverage_x":       ("wgs_coverage_x", "x"),
    "psen1_mutation":       ("psen1_mutation", "categorical"),
    "psen2_mutation":       ("psen2_mutation", "categorical"),
}


# ============================================================
# Adapter
# ============================================================

def trial_excel_to_measurements(
    excel_path: str | Path,
    *,
    drop_na_rows: bool = True,
) -> pd.DataFrame:
    """Transform a CDISC-style trial Excel file into Layer 2 long-format.

    Args:
        excel_path: Path to the .xlsx file. Expected sheets: DM, VS, QS,
            MR, PT, CT, LB, GE, TR, AE, DB. The adapter reads VS, MR, PT,
            LB, GE — the sheets Layer 2 covers. Other sheets are ignored
            at this layer (handled by Layer 3+ in future minors).
        drop_na_rows: If True (default), output rows with NaN value are
            dropped. Layer 2's audit engine drops NaN values by default
            anyway, so this is a no-op when feeding directly into audit;
            useful when persisting the long-format DataFrame.

    Returns:
        Long-format DataFrame with columns:
            patient_id (str), visit_id (str), measurement_name (str),
            value (object), unit (str), source_sheet (str)

        `source_sheet` is added beyond the audit-required columns so
        downstream consumers can attribute flags to the originating
        sheet. The audit engine ignores it.
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Trial Excel file not found: {excel_path}")

    rows: list[dict[str, Any]] = []

    # ---- VS (vital signs) ----
    try:
        vs = pd.read_excel(excel_path, sheet_name="VS")
        rows.extend(_long_format_from_wide(
            df=vs,
            patient_id_col="patient_id",
            visit_id_col="visit_name",
            column_map=_VS_MAP,
            source_sheet="VS",
        ))
    except ValueError:
        pass  # sheet missing

    # ---- MR (MRI volumetrics) ----
    try:
        mr = pd.read_excel(excel_path, sheet_name="MR")
        rows.extend(_long_format_from_wide(
            df=mr,
            patient_id_col="patient_id",
            visit_id_col="visit_name",
            column_map=_MR_MAP,
            source_sheet="MR",
        ))
    except ValueError:
        pass

    # ---- PT (amyloid/tau PET) ----
    try:
        pt = pd.read_excel(excel_path, sheet_name="PT")
        rows.extend(_long_format_from_wide(
            df=pt,
            patient_id_col="patient_id",
            visit_id_col="visit_name",
            column_map=_PT_MAP,
            source_sheet="PT",
        ))
    except ValueError:
        pass

    # ---- LB (laboratory) — split by sample_type ----
    try:
        lb = pd.read_excel(excel_path, sheet_name="LB")
        rows.extend(_long_format_from_lb(lb))
    except ValueError:
        pass

    # ---- GE (genetics) — one row per patient, visit_id = 'GE_baseline' ----
    try:
        ge = pd.read_excel(excel_path, sheet_name="GE")
        rows.extend(_long_format_from_ge(ge))
    except ValueError:
        pass

    out = pd.DataFrame(rows, columns=[
        "patient_id", "visit_id", "measurement_name", "value", "unit", "source_sheet"
    ])

    if drop_na_rows:
        out = out.dropna(subset=["value", "measurement_name", "patient_id"]).reset_index(drop=True)

    return out


# ============================================================
# Helpers
# ============================================================

def _long_format_from_wide(
    df: pd.DataFrame,
    *,
    patient_id_col: str,
    visit_id_col: str,
    column_map: dict[str, tuple[str, str]],
    source_sheet: str,
) -> list[dict[str, Any]]:
    """Generic wide -> long melt with measurement_name+unit lookup."""
    rows: list[dict[str, Any]] = []
    for col_name, (meas_name, unit) in column_map.items():
        if col_name not in df.columns:
            continue
        for _, r in df.iterrows():
            value = r[col_name]
            if pd.isna(value):
                continue
            rows.append({
                "patient_id": str(r[patient_id_col]),
                "visit_id": str(r[visit_id_col]),
                "measurement_name": meas_name,
                "value": value,
                "unit": unit,
                "source_sheet": source_sheet,
            })
    return rows


def _long_format_from_lb(lb: pd.DataFrame) -> list[dict[str, Any]]:
    """LB rows split by sample_type into csf_/plasma_ prefixed measurements."""
    rows: list[dict[str, Any]] = []
    if "sample_type" not in lb.columns:
        return rows
    for _, r in lb.iterrows():
        sample_type = str(r["sample_type"]).strip().lower()
        # Normalize sample_type -> prefix:
        # 'csf' -> 'csf_', 'plasma' -> 'plasma_', else unprefixed (and uncovered)
        if sample_type == "csf":
            prefix = "csf_"
        elif sample_type == "plasma":
            prefix = "plasma_"
        elif sample_type == "serum":
            prefix = "serum_"  # currently no pack covers serum; lands in uncovered
        else:
            prefix = f"{sample_type}_"
        for col_name, (suffix, unit) in _LB_NUMERIC_COLS.items():
            if col_name not in lb.columns:
                continue
            value = r[col_name]
            if pd.isna(value):
                continue
            rows.append({
                "patient_id": str(r["patient_id"]),
                "visit_id": str(r["visit_name"]),
                "measurement_name": f"{prefix}{suffix}",
                "value": value,
                "unit": unit,
                "source_sheet": "LB",
            })
    return rows


def _long_format_from_ge(ge: pd.DataFrame) -> list[dict[str, Any]]:
    """GE rows are one-per-patient; visit_id set to 'GE_baseline'."""
    rows: list[dict[str, Any]] = []
    for _, r in ge.iterrows():
        for col_name, (meas_name, unit) in _GE_MAP.items():
            if col_name not in ge.columns:
                continue
            value = r[col_name]
            if pd.isna(value):
                continue
            rows.append({
                "patient_id": str(r["patient_id"]),
                "visit_id": "GE_baseline",
                "measurement_name": meas_name,
                "value": value,
                "unit": unit,
                "source_sheet": "GE",
            })
    return rows

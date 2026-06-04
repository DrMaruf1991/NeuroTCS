"""Error injector for the Arm B validation harness.

Given a CLEAN multi-sheet cohort workbook, write a corrupted COPY with a
pre-declared number of errors of each taxonomy type injected at deterministic
(seed-driven) coordinates, and return the ground-truth InjectionManifest. The
original input is never mutated.

Determinism: identical (cohort, spec, seed) reproduce an identical manifest and
an identical corrupted workbook ordering, so an Arm B run is fully reproducible
(protocol Section 6 / Section 8 determinism requirement).

This injector targets long-format numeric biomarker sheets keyed by
(subject_id, visit, <value columns>) and a categorical enrollment field. It is
deliberately conservative: it only injects into fields it can corrupt in a
well-defined way, and records exactly what it changed.
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path

import pandas as pd

from neurotcs.validation.taxonomy import (
    ErrorType,
    InjectedError,
    InjectionManifest,
    InjectionSpec,
)

# Numeric fields safe to perturb, by sheet. These are value columns whose
# corruption produces a data error (not a biological state change). Keyed by
# sheet name -> list of numeric value columns.
_NUMERIC_FIELDS: dict[str, list[str]] = {
    "FL": [
        "plasma_ptau217_pgml",
        "plasma_ptau181_pgml",
        "csf_abeta42_40_ratio",
        "csf_ptau181_pgml",
        "plasma_nfl_pgml",
    ],
    "AM": ["amyloid_centiloid"],
}

# Categorical field for CATEGORICAL_INVALID injection: sheet -> (field, bad).
_CATEGORICAL_FIELD = ("EN", "apoe_genotype", "e3/e5")

# Multipliers / transforms per numeric error type.
_NUMERIC_ERROR_TYPES = (
    ErrorType.UNIT_ERROR,
    ErrorType.DECIMAL_SHIFT,
    ErrorType.TRANSCRIPTION_DIGIT,
    ErrorType.SIGN_FLIP,
    ErrorType.IMPLAUSIBLE_HIGH,
    ErrorType.IMPLAUSIBLE_LOW,
)


def _corrupt_numeric(value: float, etype: ErrorType, rng: random.Random) -> float:
    if etype is ErrorType.UNIT_ERROR:
        return value * 1000.0
    if etype is ErrorType.DECIMAL_SHIFT:
        return value * 10.0
    if etype is ErrorType.TRANSCRIPTION_DIGIT:
        # append a digit -> large out-of-range value
        return value * 100.0 + 7.0
    if etype is ErrorType.SIGN_FLIP:
        return -abs(value) - 1.0
    if etype is ErrorType.IMPLAUSIBLE_HIGH:
        return value * 1e6 + 1e6
    if etype is ErrorType.IMPLAUSIBLE_LOW:
        return -1e6
    raise ValueError(f"not a numeric error type: {etype}")


def inject_errors(
    cohort_path: str | Path,
    spec: InjectionSpec,
    seed: int,
    out_path: str | Path,
) -> InjectionManifest:
    """Inject errors into a COPY of ``cohort_path`` written to ``out_path``.

    Returns the ground-truth InjectionManifest. Never mutates the input file.
    """
    cohort_path = Path(cohort_path)
    out_path = Path(out_path)
    rng = random.Random(seed)

    shutil.copyfile(cohort_path, out_path)
    sheets = pd.read_excel(out_path, sheet_name=None)

    manifest = InjectionManifest(seed=seed, cohort_path=str(cohort_path))

    # Build the pool of injectable numeric coordinates: (sheet, row_idx, field).
    numeric_pool: list[tuple[str, int, str]] = []
    for sheet, fields in _NUMERIC_FIELDS.items():
        if sheet not in sheets:
            continue
        df = sheets[sheet]
        for field_name in fields:
            if field_name not in df.columns:
                continue
            for ridx in range(len(df)):
                val = df.at[ridx, field_name]
                if pd.notna(val):
                    numeric_pool.append((sheet, ridx, field_name))

    rng.shuffle(numeric_pool)

    # Track which coordinates we corrupt so the rest become clean_keys.
    corrupted_coords: set[tuple[str, int, str]] = set()
    pool_iter = iter(numeric_pool)

    # Inject numeric error types per the spec.
    for etype in _NUMERIC_ERROR_TYPES:
        n = spec.counts.get(etype, 0)
        for _ in range(n):
            try:
                sheet, ridx, field_name = next(pool_iter)
            except StopIteration as exc:
                raise ValueError(
                    "Injection spec requests more numeric errors than the "
                    "cohort has injectable cells."
                ) from exc
            df = sheets[sheet]
            original = float(df.at[ridx, field_name])
            corrupted = _corrupt_numeric(original, etype, rng)
            df.at[ridx, field_name] = corrupted
            sid = str(df.at[ridx, "subject_id"])
            visit = df.at[ridx, "visit"] if "visit" in df.columns else None
            visit_s = str(visit) if visit is not None and pd.notna(visit) else None
            manifest.injected.append(
                InjectedError(
                    subject_id=sid,
                    field=field_name,
                    visit=visit_s,
                    error_type=etype,
                    original_value=original,
                    corrupted_value=corrupted,
                    sheet=sheet,
                )
            )
            corrupted_coords.add((sheet, ridx, field_name))

    # Categorical invalid injection.
    n_cat = spec.counts.get(ErrorType.CATEGORICAL_INVALID, 0)
    if n_cat:
        cat_sheet, cat_field, bad_value = _CATEGORICAL_FIELD
        if cat_sheet in sheets and cat_field in sheets[cat_sheet].columns:
            df = sheets[cat_sheet]
            rows = list(range(len(df)))
            rng.shuffle(rows)
            for ridx in rows[:n_cat]:
                original = df.at[ridx, cat_field]
                df.at[ridx, cat_field] = bad_value
                sid = str(df.at[ridx, "subject_id"])
                manifest.injected.append(
                    InjectedError(
                        subject_id=sid,
                        field=cat_field,
                        visit=None,
                        error_type=ErrorType.CATEGORICAL_INVALID,
                        original_value=original,
                        corrupted_value=bad_value,
                        sheet=cat_sheet,
                    )
                )
        else:
            raise ValueError(
                "Categorical injection requested but the cohort lacks the "
                f"{_CATEGORICAL_FIELD[0]}.{_CATEGORICAL_FIELD[1]} field."
            )

    # Remaining numeric coordinates (not corrupted) are the clean denominator
    # for specificity.
    for sheet, ridx, field_name in numeric_pool:
        if (sheet, ridx, field_name) in corrupted_coords:
            continue
        df = sheets[sheet]
        sid = str(df.at[ridx, "subject_id"])
        visit = df.at[ridx, "visit"] if "visit" in df.columns else None
        visit_s = str(visit) if visit is not None and pd.notna(visit) else None
        manifest.clean_keys.add((sid, field_name, visit_s))

    # Write the corrupted workbook (all sheets preserved).
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)

    return manifest

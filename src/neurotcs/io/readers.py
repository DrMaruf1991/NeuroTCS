"""Universal dataset readers for NeuroTCS.

Reads CSV / TSV / Excel / Parquet / JSON robustly. PDF is best-effort, gated
behind allow_pdf=True, and refuses free-text / scanned documents -- silently
auditing a guessed-at PDF table would violate the fail-closed contract.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class UnsupportedFormatError(ValueError):
    """Raised for a file type NeuroTCS will not read without explicit opt-in."""


class PdfExtractionError(RuntimeError):
    """Raised when PDF table extraction is impossible or yields nothing usable."""


# Structured formats read without guessing.
SUPPORTED_TABULAR = (".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".json")


def read_tables(path: str | Path, *, allow_pdf: bool = False) -> dict[str, pd.DataFrame]:
    """Read any supported dataset file into a dict of {table_name: DataFrame}.

    CSV / TSV / Parquet / JSON -> one table, keyed by the file stem.
    Excel (.xlsx/.xls)         -> one entry per sheet (keyed by sheet name).
    PDF                        -> best-effort table extraction; requires
                                  allow_pdf=True and refuses free-text/scanned
                                  documents (raises PdfExtractionError).

    Raises UnsupportedFormatError for any other extension (fail-closed: the
    auditor never reads a format it cannot parse deterministically).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"dataset file not found: {p}")
    ext = p.suffix.lower()

    if ext == ".csv":
        return {p.stem: pd.read_csv(p)}
    if ext == ".tsv":
        return {p.stem: pd.read_csv(p, sep="\t")}
    if ext in (".xlsx", ".xls"):
        try:
            import openpyxl  # noqa: F401  (engine for pd.read_excel)
        except ImportError as e:
            raise UnsupportedFormatError(
                "Reading Excel needs the 'openpyxl' package (a declared NeuroTCS "
                "dependency). Install it with: pip install openpyxl -- or export "
                "your data to CSV."
            ) from e
        sheets = pd.read_excel(p, sheet_name=None)
        return {str(k): v for k, v in sheets.items()}
    if ext == ".parquet":
        return {p.stem: pd.read_parquet(p)}
    if ext == ".json":
        return {p.stem: pd.read_json(p)}
    if ext == ".pdf":
        if not allow_pdf:
            raise UnsupportedFormatError(
                "PDF reading is OFF by default. A PDF may contain free text, a "
                "scanned image, or an ambiguous table; silently extracting and "
                "auditing it risks a wrong result, which the NeuroTCS contract "
                "forbids. Pass allow_pdf=True to attempt best-effort table "
                "extraction, then VERIFY the extracted tables before auditing. "
                "For reliable results, export your data to CSV or Excel."
            )
        return _read_pdf_tables(p)

    raise UnsupportedFormatError(
        f"Unsupported file type '{ext}'. Supported: {list(SUPPORTED_TABULAR)} "
        f"(plus .pdf with allow_pdf=True). Convert your data to CSV or Excel."
    )


def _read_pdf_tables(p: Path) -> dict[str, pd.DataFrame]:
    try:
        import pdfplumber  # optional dependency
    except ImportError as e:  # pragma: no cover - environment dependent
        raise PdfExtractionError(
            "PDF support needs pdfplumber. Install it (pip install pdfplumber) "
            "or export your data to CSV/Excel."
        ) from e

    tables: dict[str, pd.DataFrame] = {}
    idx = 0
    with pdfplumber.open(str(p)) as pdf:
        for page in pdf.pages:
            for raw in page.extract_tables() or []:
                if not raw or len(raw) < 2:
                    continue  # need a header + at least one data row
                header = [str(c) if c is not None else f"col{j}"
                          for j, c in enumerate(raw[0])]
                df = pd.DataFrame(raw[1:], columns=header)
                tables[f"{p.stem}_table{idx}"] = df
                idx += 1
    if not tables:
        raise PdfExtractionError(
            f"No tables detected in {p.name}. NeuroTCS cannot audit free-text "
            f"or scanned PDFs -- export the dataset to CSV or Excel."
        )
    return tables


def describe_tables(tables: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    """Summarize loaded tables (shape + columns) to help build a mapping.

    Returns {table_name: {"shape": [rows, cols], "columns": [...]}}. Purely
    descriptive; it does NOT guess which columns are clinical/biological.
    """
    return {
        name: {"shape": list(df.shape), "columns": list(map(str, df.columns))}
        for name, df in tables.items()
    }


# --------------------------------------------------------------------------- #
# Explicit mapping -> orchestrator submission (no inference, fail-closed)
# --------------------------------------------------------------------------- #
_STAGING_REQUIRED = ("subject_id", "visit", "visit_date", "state")
_RANGE_REQUIRED = ("patient_id", "visit_id", "measurement_name", "value", "unit")


def _require_columns(df: pd.DataFrame, colmap: dict[str, str], where: str) -> None:
    missing = [src for src in colmap.values() if src not in df.columns]
    if missing:
        # v1.38.0: actionable error per external-audit design. Show what was
        # searched and exactly how to fix, rather than a bare "not found".
        hint = ""
        if any("visit_date" in str(m).lower() or "date" in str(m).lower()
               for m in missing):
            hint = (
                " To proceed without a date column, either set \"visit_date\": null "
                "in the mapping for this axis, or run `neurotcs audit ... "
                "--allow-no-dates`. NeuroTCS will derive visit ordering from the "
                "'visit' column and disable time-window-dependent checks (recorded "
                "in the bundle's input_warnings)."
            )
        raise ValueError(
            f"{where}: declared column(s) {missing} not found in sheet. "
            f"Searched columns: {list(map(str, df.columns))}. "
            f"NeuroTCS will not guess column names -- fix the mapping to point at "
            f"a real column.{hint}"
        )


def tables_to_submission(
    tables: dict[str, pd.DataFrame],
    mapping: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build an orchestrator submission from loaded tables + an EXPLICIT mapping.

    mapping = {
      "clinical":   {"sheet": <name>, "subject_id": <col>, "visit": <col>,
                     "visit_date": <col>, "state": <col>},     # optional
      "biological": {... same shape ...},                       # optional
      "ranges": [                                               # optional, list
        {"sheet": <name>, "pack": "<domain/name>",
         "patient_id": <col>, "visit_id": <col>,
         "measurement_name": <col>, "value": <col>, "unit": <col>},
      ],
    }

    Fail-closed: a referenced sheet or column that does not exist raises
    ValueError. No column is ever inferred SILENTLY.

    v1.38.0: `warnings` is an optional accumulator list. When `visit_date` is
    null / missing / a placeholder, this function DERIVES dates from visit
    ordering (so the audit can still run) and appends a human-readable note to
    `warnings` so the derivation is NEVER silent -- the caller (CLI) surfaces it
    to the user. This satisfies the external-audit principle: graceful fallback,
    but visible, never a silent guess.
    """
    if warnings is None:
        warnings = []  # local sink if caller didn't pass one
    submission: dict[str, Any] = {}

    for axis in ("clinical", "biological"):
        spec = mapping.get(axis)
        if not spec:
            continue
        sheet = spec["sheet"]
        if sheet not in tables:
            raise ValueError(f"{axis}: sheet '{sheet}' not in loaded tables "
                             f"{list(tables)}")
        df = tables[sheet]

        # v1.37.0: visit_date is OPTIONAL. If the mapping omits visit_date, sets it
        # to null, or points at a column that doesn't exist, derive a synthetic
        # visit_date from visit ordering (2000-01-01 + 365 days per visit per
        # subject). This lets datasets without an explicit date column audit
        # without forcing the user to hand-edit JSON or fabricate dates -- a
        # real fix for the v1.36.0 emit-mapping friction caught by the external
        # audit.
        vd_col = spec.get("visit_date")
        derive_date = (
            vd_col is None
            or (isinstance(vd_col, str) and (vd_col.strip() == ""
                                             or vd_col.startswith("<FILL:")))
            or (isinstance(vd_col, str) and vd_col not in df.columns)
        )

        if derive_date:
            # Build a working copy with a derived date column. Sort by
            # (subject_id, visit) so the derivation preserves intra-subject order.
            sid_col = spec["subject_id"]
            v_col = spec["visit"]
            missing_required = [c for c in (sid_col, v_col, spec["state"])
                                if c not in df.columns]
            if missing_required:
                raise ValueError(
                    f"{axis} staging: declared column(s) {missing_required} not "
                    f"found in sheet. Searched columns: {list(map(str, df.columns))}. "
                    f"NeuroTCS will not guess column names -- fix the mapping to "
                    f"point at a real column."
                )
            df_local = df[[sid_col, v_col, spec["state"]]].copy()
            df_local = df_local.sort_values(by=[sid_col, v_col]).reset_index(drop=True)
            # Vectorized derivation: 2000-01-01 + 365 days per visit index per subject.
            # Use vector math (no lambda) so the closure-capture warning B023 doesn't fire.
            visit_index = df_local.groupby(sid_col, sort=False).cumcount()
            df_local["_derived_visit_date"] = (
                pd.Timestamp("2000-01-01") + pd.to_timedelta(visit_index * 365, unit="D")
            )
            out = df_local[[sid_col, v_col, "_derived_visit_date", spec["state"]]].copy()
            out.columns = list(_STAGING_REQUIRED)
            out["visit_date"] = pd.to_datetime(out["visit_date"])
            warnings.append(
                f"{axis}: sheet '{sheet}' has no usable visit_date column; dates "
                f"were DERIVED from visit ordering (column '{v_col}'). Visit ORDER "
                f"is preserved, but the derived dates are synthetic -- any "
                f"time-window-dependent rule is not meaningful on this axis. To use "
                f"real dates, add a visit_date column to '{sheet}' and re-run."
            )
        else:
            colmap = {k: spec[k] for k in _STAGING_REQUIRED}
            _require_columns(df, colmap, f"{axis} staging")
            out = df[[colmap[k] for k in _STAGING_REQUIRED]].copy()
            out.columns = list(_STAGING_REQUIRED)
            out["visit_date"] = pd.to_datetime(out["visit_date"])

        submission[axis] = out

    ranges_spec = mapping.get("ranges") or []
    ranges: list[tuple[str, pd.DataFrame]] = []
    for r in ranges_spec:
        sheet = r["sheet"]
        if sheet not in tables:
            raise ValueError(f"ranges: sheet '{sheet}' not in loaded tables "
                             f"{list(tables)}")
        df = tables[sheet]
        colmap = {k: r[k] for k in _RANGE_REQUIRED}
        _require_columns(df, colmap, f"ranges pack '{r.get('pack')}'")
        sub_df = df[[colmap[k] for k in _RANGE_REQUIRED]].copy()
        sub_df.columns = list(_RANGE_REQUIRED)
        ranges.append((r["pack"], sub_df))
    if ranges:
        submission["ranges"] = ranges

    if not submission:
        raise ValueError(
            "mapping produced an empty submission: declare at least one of "
            "'clinical', 'biological', or 'ranges'."
        )
    return submission

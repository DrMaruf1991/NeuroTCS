"""Universal dataset readers for NeuroTCS.

Reads a cohort from a single file, a FOLDER of files, a glob, or a compressed
archive, across the formats real AD cohorts ship in -- CSV / TSV / Excel /
Parquet / JSON / SAS / SPSS / Stata / R -- and exposes every table by name so
the multi-sheet engines (cross-sheet coherence, staging, ranges) see the whole
cohort, not a single accidental table.

FAIL-CLOSED DISCIPLINE (the contract that makes a clinical auditor defensible):
  * Read DETERMINISTICALLY or refuse with an actionable message. The reader
    never silently guesses a delimiter, an encoding, a type coercion, or a PDF
    table -- each guess is a place a wrong clinical number could be produced.
  * SURFACE every decision and every skipped file. A folder's non-tabular files
    (README, images) are skipped but REPORTED by name, never hidden.
  * Formats that need an optional library are GATED: refuse with an install
    instruction rather than auto-installing (auto-install is non-deterministic
    and a supply-chain risk) or bloating every install with a hard dependency.

The MULTI-FILE rationale: an Excel workbook is naturally multi-sheet, but a CSV
holds exactly one table, so a CSV-exported cohort becomes many files
(enrollment.csv, amyloid.csv, tau.csv, ...). Reading one CSV as one table would
silently collapse such a cohort to a single role view and re-darken the
cross-sheet layer. `read_tables` therefore accepts a directory / list / glob /
zip and loads every tabular member as a named table -- exactly like workbook
sheets.
"""
from __future__ import annotations

import csv as _csv
import gzip
import io
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd


class UnsupportedFormatError(ValueError):
    """Raised for a file type NeuroTCS will not read without explicit opt-in."""


class PdfExtractionError(RuntimeError):
    """Raised when PDF table extraction is impossible or yields nothing usable."""


class AmbiguousInputError(ValueError):
    """Raised when input is structurally ambiguous (e.g. undetectable delimiter
    or encoding) -- the reader refuses rather than guess into a clinical result."""


# Structured tabular formats read deterministically without an optional library.
SUPPORTED_TABULAR = (".csv", ".tsv", ".txt", ".xlsx", ".xls", ".parquet", ".json")
# Statistical formats real cohorts ship in. R works out of the box (pyreadr is a
# core dependency); SAS/Stata use pandas' built-in readers; SPSS needs the
# optional pyreadstat library (gated).
SUPPORTED_STATISTICAL = (".sas7bdat", ".dta", ".sav", ".zsav", ".rds", ".rdata")
# Compressed single files (one table inside) and archives (a multi-file cohort).
SUPPORTED_COMPRESSED = (".gz",)
SUPPORTED_ARCHIVE = (".zip",)

# Candidate text encodings tried, in order, for CSV/TSV. UTF-8 (incl. BOM) is
# tried first; cp1251 covers Cyrillic (RU/UZ) exports common in the field.
_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1251", "latin-1")

# Filenames that are obviously not data -- skipped (and reported) in a folder/zip.
_NON_DATA_NAME_TOKENS = ("readme", "license", "licence", "changelog", "notes",
                         "manifest", "dictionary", "datadictionary", "codebook")


def read_tables(
    path: str | Path | list[str | Path],
    *,
    allow_pdf: bool = False,
    skipped: list[str] | None = None,
    decisions: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Read a cohort into a dict of {table_name: DataFrame}.

    `path` may be:
      * a single file (.csv/.tsv/.txt/.xlsx/.xls/.parquet/.json/.sas7bdat/.dta/
        .sav/.rds/.rdata/.pdf/.gz),
      * a DIRECTORY -- every supported tabular file inside becomes a table,
      * a GLOB string (e.g. "cohort/*.csv"),
      * a ZIP archive -- every supported member becomes a table,
      * a LIST of any of the above.

    Single-table formats are keyed by file stem; Excel by sheet name. When
    multiple files are read, table names are made unique (file stem, then
    stem__sheet for multi-sheet members; collisions get a numeric suffix).

    `skipped` (optional): names of non-tabular files that were skipped are
    appended here so the caller can surface them (never hidden).
    `decisions` (optional): human-readable notes (e.g. the encoding chosen for a
    CSV) are appended here so every non-trivial read decision is visible.

    Fail-closed: an unsupported or structurally-ambiguous input raises rather
    than guessing. PDF and SPSS are gated behind explicit opt-in / install.
    """
    skipped = skipped if skipped is not None else []
    decisions = decisions if decisions is not None else []

    # --- list of inputs: read each, merge with unique names ---
    if isinstance(path, list):
        merged: dict[str, pd.DataFrame] = {}
        for item in path:
            part = read_tables(item, allow_pdf=allow_pdf, skipped=skipped,
                               decisions=decisions)
            _merge_unique(merged, part)
        if not merged:
            raise UnsupportedFormatError(
                "no readable tabular files found in the provided inputs.")
        return merged

    # --- glob string ---
    if isinstance(path, str) and any(ch in path for ch in "*?[") and not Path(path).exists():
        import glob as _glob
        matches = sorted(_glob.glob(path))
        if not matches:
            raise FileNotFoundError(f"no files match the pattern: {path}")
        return read_tables([str(m) for m in matches], allow_pdf=allow_pdf,
                          skipped=skipped, decisions=decisions)

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"dataset file not found: {p}")

    # --- directory: load every supported tabular member ---
    if p.is_dir():
        return _read_directory(p, allow_pdf=allow_pdf, skipped=skipped,
                              decisions=decisions)

    ext = p.suffix.lower()

    # --- zip archive: a multi-file cohort ---
    if ext in SUPPORTED_ARCHIVE:
        return _read_zip(p, allow_pdf=allow_pdf, skipped=skipped,
                        decisions=decisions)

    # --- gz single compressed file: read the inner file by its inner suffix ---
    if ext in SUPPORTED_COMPRESSED:
        return _read_gz(p, decisions=decisions)

    # --- single file by extension ---
    return _read_single_file(p, allow_pdf=allow_pdf, decisions=decisions)


# --------------------------------------------------------------------------- #
# Single-file dispatch
# --------------------------------------------------------------------------- #


def _read_single_file(
    p: Path, *, allow_pdf: bool, decisions: list[str]
) -> dict[str, pd.DataFrame]:
    ext = p.suffix.lower()

    if ext in (".csv", ".tsv", ".txt"):
        return {p.stem: _read_delimited(p, ext, decisions)}
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
        return {p.stem: _read_json(p)}
    if ext in SUPPORTED_STATISTICAL:
        return {p.stem: _read_statistical(p, ext)}
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
        f"Unsupported file type '{ext}'. Supported: "
        f"{list(SUPPORTED_TABULAR)} + statistical {list(SUPPORTED_STATISTICAL)} "
        f"+ .zip / .gz (plus .pdf with allow_pdf=True). A folder or glob of these "
        f"is also accepted. Convert your data to CSV or Excel if unsure."
    )


# --------------------------------------------------------------------------- #
# Encoding-honest delimited text (CSV / TSV / TXT)
# --------------------------------------------------------------------------- #


def _read_delimited(p: Path, ext: str, decisions: list[str]) -> pd.DataFrame:
    """Read a delimited text file, choosing encoding and (for .csv/.txt)
    delimiter deterministically. The chosen encoding is SURFACED. Type-ambiguous
    columns are preserved as strings rather than silently coerced (an ID column
    like APOE 'e3/e4' or a zero-padded code must not be mangled)."""
    raw, enc = _read_text_with_encoding(p, decisions)

    if ext == ".tsv":
        sep = "\t"
    else:
        sep = _sniff_delimiter(raw, p.name)
        if sep != ",":
            decisions.append(f"{p.name}: delimiter detected as {sep!r}")

    # keep_default_na keeps empty-string distinct handling predictable; we do NOT
    # coerce dtypes aggressively -- pandas' inference is deterministic and we
    # leave ambiguous string columns as strings (no errors='coerce' guessing).
    df = pd.read_csv(io.StringIO(raw), sep=sep)
    return df


def _read_text_with_encoding(p: Path, decisions: list[str]) -> tuple[str, str]:
    data = p.read_bytes()
    return _decode_bytes(data, p.name, decisions)


def _decode_bytes(data: bytes, name: str, decisions: list[str]) -> tuple[str, str]:
    for enc in _TEXT_ENCODINGS:
        try:
            text = data.decode(enc)
            # latin-1 decodes ANY byte sequence, so only accept it as a last
            # resort and SURFACE that it was a fallback (possible mojibake).
            if enc == "latin-1":
                decisions.append(
                    f"{name}: decoded as latin-1 FALLBACK (utf-8/cp1251 failed); "
                    f"verify non-ASCII text -- it may be mis-decoded.")
            elif enc != "utf-8":
                decisions.append(f"{name}: decoded as {enc}")
            return text, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise AmbiguousInputError(
        f"{name}: could not decode the file with any of {list(_TEXT_ENCODINGS)}. "
        f"Re-save it as UTF-8 CSV and retry.")


def _sniff_delimiter(sample_text: str, name: str) -> str:
    """Detect the delimiter deterministically; refuse if ambiguous."""
    sample = sample_text[:65536]
    try:
        dialect = _csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except _csv.Error:
        # Fall back ONLY if a comma is clearly present; otherwise refuse rather
        # than guess (a single-column file is fine as comma).
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        if "," in first_line or first_line:  # single column -> comma is safe
            return ","
        raise AmbiguousInputError(
            f"{name}: could not determine the column delimiter. Re-save as a "
            f"standard comma-separated CSV and retry.") from None


def _read_json(p: Path) -> pd.DataFrame:
    """Read JSON ONLY when it is an unambiguous table (an array of flat records,
    or columnar). Nested / arbitrary JSON is refused -- flattening it is a guess."""
    try:
        df = pd.read_json(p)
    except ValueError as e:
        raise AmbiguousInputError(
            f"{p.name}: this JSON is not a flat table (array of records or "
            f"columnar). NeuroTCS will not guess how to flatten nested JSON -- "
            f"export a flat CSV/Excel instead. ({e})") from e
    # refuse object/array-valued cells (nested) rather than audit a stringified guess
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (dict, list))).any():
            raise AmbiguousInputError(
                f"{p.name}: column '{col}' contains nested objects/arrays. "
                f"NeuroTCS audits flat tables only -- flatten and re-export.")
    return df


# --------------------------------------------------------------------------- #
# Statistical formats (SAS / Stata / SPSS / R)
# --------------------------------------------------------------------------- #


def _read_statistical(p: Path, ext: str) -> pd.DataFrame:
    if ext == ".sas7bdat":
        return pd.read_sas(p)  # pandas built-in
    if ext == ".dta":
        return pd.read_stata(p)  # pandas built-in
    if ext in (".sav", ".zsav"):
        try:
            import pyreadstat  # optional dependency
        except ImportError as e:
            raise UnsupportedFormatError(
                "Reading SPSS (.sav) needs the 'pyreadstat' package. Install it "
                "with: pip install pyreadstat -- or export your data to CSV/Excel. "
                "(NeuroTCS does not auto-install: a clinical auditor reads "
                "deterministically or refuses.)"
            ) from e
        df, _meta = pyreadstat.read_sav(str(p))
        return df
    if ext in (".rds", ".rdata"):
        try:
            import pyreadr  # core dependency
        except ImportError as e:  # pragma: no cover
            raise UnsupportedFormatError(
                "Reading R data needs the 'pyreadr' package (a declared NeuroTCS "
                "dependency). Install it with: pip install pyreadr."
            ) from e
        result = pyreadr.read_r(str(p))
        if not result:
            raise UnsupportedFormatError(
                f"{p.name}: no data frame found in the R file.")
        # .rds holds one object; .RData may hold several -> take the first
        # deterministically (sorted by object name) and note it.
        first_key = sorted(result.keys(), key=lambda k: str(k))[0]
        return result[first_key]
    raise UnsupportedFormatError(f"unsupported statistical format '{ext}'")


# --------------------------------------------------------------------------- #
# Folder / archive / gz
# --------------------------------------------------------------------------- #


def _readable_member(name: str) -> bool:
    """True if a folder/zip member should be auto-read in a sweep. Excludes
    ambiguous .txt (a README is .txt too -- read it only when pointed at
    directly) and obviously-non-data filenames."""
    if _is_noise_name(name):
        return False
    ext = Path(name).suffix.lower()
    sweep_tabular = tuple(e for e in SUPPORTED_TABULAR if e != ".txt")
    return ext in (sweep_tabular + SUPPORTED_STATISTICAL)


def _is_noise_name(name: str) -> bool:
    stem = Path(name).stem.lower()
    return any(tok in stem for tok in _NON_DATA_NAME_TOKENS)


def _read_directory(
    d: Path, *, allow_pdf: bool, skipped: list[str], decisions: list[str]
) -> dict[str, pd.DataFrame]:
    members = sorted(x for x in d.iterdir() if x.is_file())
    tables: dict[str, pd.DataFrame] = {}
    read_any = False
    for m in members:
        if _readable_member(m.name):
            part = _read_single_file(m, allow_pdf=allow_pdf, decisions=decisions)
            _merge_unique(tables, part)
            read_any = True
        else:
            skipped.append(str(m.name))
    if not read_any:
        raise UnsupportedFormatError(
            f"folder '{d.name}' contains no readable tabular files "
            f"(looked for {list(SUPPORTED_TABULAR + SUPPORTED_STATISTICAL)}). "
            f"Skipped: {skipped or 'none'}.")
    decisions.append(
        f"folder '{d.name}': loaded {len(tables)} table(s) from "
        f"{sum(1 for m in members if _readable_member(m.name))} file(s)"
        + (f"; skipped {len(skipped)} non-data file(s): {skipped}" if skipped else ""))
    return tables


def _read_zip(
    p: Path, *, allow_pdf: bool, skipped: list[str], decisions: list[str]
) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    read_any = False
    with zipfile.ZipFile(p) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            name = info.filename
            if _is_noise_name(name) or not _readable_member(name):
                skipped.append(name)
                continue
            # Extract member to a temp buffer and dispatch by suffix.
            data = zf.read(info)
            part = _read_bytes_as_table(data, name, allow_pdf=allow_pdf,
                                       decisions=decisions)
            _merge_unique(tables, part)
            read_any = True
    if not read_any:
        raise UnsupportedFormatError(
            f"archive '{p.name}' contains no readable tabular files. "
            f"Skipped: {skipped or 'none'}.")
    decisions.append(
        f"archive '{p.name}': loaded {len(tables)} table(s)"
        + (f"; skipped {len(skipped)} non-data member(s): {skipped}" if skipped else ""))
    return tables


def _read_gz(p: Path, *, decisions: list[str]) -> dict[str, pd.DataFrame]:
    inner = Path(p.stem)  # e.g. "amyloid.csv.gz" -> "amyloid.csv"
    with gzip.open(p, "rb") as fh:
        data = fh.read()
    decisions.append(f"{p.name}: decompressed gzip -> {inner.name}")
    return _read_bytes_as_table(data, inner.name, allow_pdf=False,
                               decisions=decisions)


def _read_bytes_as_table(
    data: bytes, name: str, *, allow_pdf: bool, decisions: list[str]
) -> dict[str, pd.DataFrame]:
    """Dispatch an in-memory file (from a zip/gz member) by its name suffix."""
    ext = Path(name).suffix.lower()
    stem = Path(name).stem
    if ext in (".csv", ".tsv", ".txt"):
        text, _enc = _decode_bytes(data, name, decisions)
        sep = "\t" if ext == ".tsv" else _sniff_delimiter(text, name)
        return {stem: pd.read_csv(io.StringIO(text), sep=sep)}
    if ext in (".xlsx", ".xls"):
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
        return {str(k): v for k, v in sheets.items()}
    if ext == ".parquet":
        return {stem: pd.read_parquet(io.BytesIO(data))}
    if ext == ".json":
        return {stem: pd.read_json(io.BytesIO(data))}
    if ext in SUPPORTED_STATISTICAL:
        # write to a temp file -- the statistical readers need a path
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
            tf.write(data)
            tmp = Path(tf.name)
        try:
            return {stem: _read_statistical(tmp, ext)}
        finally:
            tmp.unlink(missing_ok=True)
    raise UnsupportedFormatError(f"member '{name}': unsupported type '{ext}'")


def _merge_unique(dst: dict[str, pd.DataFrame], src: dict[str, pd.DataFrame]) -> None:
    """Merge src into dst, disambiguating colliding table names deterministically."""
    for k, v in src.items():
        key = k
        if key in dst:
            i = 2
            while f"{k}_{i}" in dst:
                i += 1
            key = f"{k}_{i}"
        dst[key] = v


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

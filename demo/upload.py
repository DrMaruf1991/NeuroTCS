"""In-memory upload audit for the NeuroTCS demo -- BYO file, same engine path.

Lets an expert upload a single tabular file (.csv/.tsv/.txt/.xlsx/.xls/.parquet/
.json/.jsonl/.ndjson), get a describe-style auto-suggested
column mapping (subject_id / visit_date / state), confirm/adjust it, and run the
SAME staging audit path the cohorts use. Nothing is reimplemented:

    _read_bytes_as_table(data, name)      # neurotcs.io.readers -- in-memory (BytesIO),
                                          #   the same reader used for zip/gz members
      -> describe_tables(tables)          # neurotcs.io -- sheet/column inventory
      -> _scaffold_mapping(desc)          # neurotcs.cli -- the `describe` auto-mapping
      -> tables_to_submission(tables, m)  # neurotcs.io -- same submission builder
      -> run_full_audit(submission)       # neurotcs.orchestration -- the engine
      -> build_bundle(result, ...)        # neurotcs -- the self-verifying artifact

DUA / privacy: the upload is the caller's OWN file, processed transiently and
discarded when the request returns. Tabular formats (csv/tsv/txt/xlsx/xls/parquet/
json/jsonl/ndjson) are parsed ENTIRELY IN MEMORY via BytesIO -- nothing touches
disk (read_mode="in_memory"). Statistical formats (rds/rdata/rda/sav/dta/...) and
.zip have readers that require a filesystem path; for these the bytes are written
into a SECURE temp directory (mkdtemp, mode 0700) under the file's original name,
read via the shipped read_tables, and the whole directory is removed immediately
in a finally block, even on error (read_mode="transient_temp_file"). The response
carries the audit result back to the same caller; it is not a DUA cohort.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

import neurotcs
from neurotcs import build_bundle, load_rulepack
from neurotcs.cli import _clean_mapping, _scaffold_mapping
from neurotcs.io import describe_tables, read_tables, tables_to_submission
from neurotcs.io.readers import _read_bytes_as_table
from neurotcs.orchestration.orchestrator import run_full_audit

# Two tiers of accepted upload format:
#
# TABULAR_INMEM -- parsed by _read_bytes_as_table straight from a BytesIO buffer.
#   Nothing touches disk (mirrors neurotcs.io.readers.SUPPORTED_TABULAR).
#
# PATH_REQUIRED -- statistical formats (pyreadr/pyreadstat) and .zip, whose readers
#   need a filesystem path. For these we write the bytes into a SECURE temp
#   directory (mkdtemp, mode 0700) under the file's original name, read via the
#   shipped read_tables, and remove the whole directory immediately in a finally
#   block (even on error). This is a transient, controlled disk write -- surfaced
#   to the caller as read_mode="transient_temp_file" so the UI can say so honestly.
#   It matches how the shipped CLI reads these.
TABULAR_INMEM = (
    ".csv", ".tsv", ".txt", ".xlsx", ".xls",
    ".parquet", ".json", ".jsonl", ".ndjson",
)
PATH_REQUIRED = (
    ".rds", ".rdata", ".rda", ".sav", ".dta", ".sas7bdat", ".zsav", ".zip",
)
ALLOWED_EXT = TABULAR_INMEM + PATH_REQUIRED

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB -- a demo staging file, not a data lake
MAX_FLAGS_RETURNED = 200  # cap the flag list in the response payload

# The demo audits the clinical staging trajectory only (as the cohorts do).
_EXPECTED_LAYERS = ["staging_clinical"]


class UploadError(ValueError):
    """A bad upload (wrong type, too big, unparseable, or an unusable mapping)."""


def _norm(value: Any) -> str | None:
    """Normalize a scaffold value to a real column name or None.

    _scaffold_mapping leaves ``<FILL:...>`` placeholders where a synonym missed;
    the UI should see those as "unset" (None), not as a literal column.
    """
    if value is None:
        return None
    if isinstance(value, str) and (value.startswith("<FILL:") or value.strip() == ""):
        return None
    return value


# A column is "numeric-like" when almost all of its non-null values parse as
# numbers. If the user maps such a column to `state`, they are probably uploading
# raw staging CODES (ADNI 1/2/3, CDR 0/0.5/1, NACCUDSD 1-4) -- which the engine may
# match to a DIFFERENT published numeric scheme and misinterpret. The UI warns on
# this so a user cannot fall into that trap even if they skip the guide.
_NUMERIC_LIKE_FRACTION = 0.8
_NUMERIC_LIKE_MIN_ROWS = 3


def _numeric_like_columns(df: pd.DataFrame) -> list[str]:
    """Return the columns whose non-null values are >=80% numeric (>=3 values)."""
    out: list[str] = []
    for col in df.columns:
        nonnull = df[col].dropna()
        if len(nonnull) < _NUMERIC_LIKE_MIN_ROWS:
            continue
        frac = pd.to_numeric(nonnull, errors="coerce").notna().mean()
        if frac >= _NUMERIC_LIKE_FRACTION:
            out.append(str(col))
    return out


def _read_upload(filename: str, data: bytes) -> tuple[dict[str, pd.DataFrame], str]:
    """Parse the uploaded bytes into tables. Returns (tables, read_mode).

    read_mode is "in_memory" for tabular formats (BytesIO, no disk) or
    "transient_temp_file" for path-required formats (statistical / .zip), which
    are written to a secure temp file, read via the shipped read_tables, and
    deleted immediately. Fail-closed on type/size/parse errors.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise UploadError(
            f"unsupported file type '{ext}'. Upload one of: "
            f"{', '.join(ALLOWED_EXT)}."
        )
    if not data:
        raise UploadError("uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(
            f"file is {len(data) // (1024 * 1024)} MB; the limit is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    if ext in TABULAR_INMEM:
        # Pure in-memory: parse straight from a BytesIO buffer, nothing on disk.
        try:
            tables = _read_bytes_as_table(
                data, filename, allow_pdf=False, encoding=None, decisions=[]
            )
        except Exception as e:  # noqa: BLE001 -- clean parse error to the client
            raise UploadError(f"could not read the file: {e}") from e
        read_mode = "in_memory"
    else:
        # Path-required (statistical / zip): the readers need a filesystem path.
        # Write to a SECURE temp DIRECTORY (mkdtemp -> mode 0700) under the file's
        # ORIGINAL basename, read via the shipped loader, then remove the whole
        # directory in finally (even if the read raises). Using the original name
        # (not a random one) keeps the derived table key STABLE across the separate
        # describe and audit requests -- otherwise the confirmed sheet name would
        # not match on the second call. Path(...).name strips any directory
        # components, so a crafted filename cannot escape the temp dir.
        safe_name = Path(filename).name or f"upload{ext}"
        tmp_dir = tempfile.mkdtemp(prefix="neurotcs_upload_")
        tmp_path = os.path.join(tmp_dir, safe_name)
        try:
            with open(tmp_path, "wb") as fh:
                fh.write(data)
            tables = read_tables(
                tmp_path, allow_pdf=False, skipped=[], decisions=[]
            )
        except Exception as e:  # noqa: BLE001
            raise UploadError(f"could not read the file: {e}") from e
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        read_mode = "transient_temp_file"

    if not tables:
        raise UploadError("the file contained no readable tables.")
    return tables, read_mode


def describe_upload(filename: str, data: bytes) -> dict[str, Any]:
    """Read the upload in memory and return the sheet inventory + suggested mapping.

    Does NOT run an audit -- this is the "confirm the mapping" step. Returns the
    columns per sheet (so the UI can build dropdowns) and the auto-detected
    clinical staging axis (subject_id / state / visit_date / visit), with
    placeholders normalized to null.
    """
    tables, read_mode = _read_upload(filename, data)
    desc = describe_tables(tables)
    mapping = _clean_mapping(_scaffold_mapping(desc))
    clinical = mapping.get("clinical", {}) if isinstance(mapping, dict) else {}

    # Tag each sheet's numeric-like columns (done AFTER scaffolding so the mapper
    # sees a clean desc) so the UI can warn when the chosen `state` column looks
    # like raw codes (ADNI 1/2/3, CDR 0/0.5/1, ...).
    for name, info in desc.items():
        info["numeric_like"] = _numeric_like_columns(tables[name])

    suggested = {
        "sheet": _norm(clinical.get("sheet")),
        "subject_id": _norm(clinical.get("subject_id")),
        "state": _norm(clinical.get("state")),
        "visit_date": _norm(clinical.get("visit_date")),
        "visit": _norm(clinical.get("visit")),
    }
    # If the scaffold could not pick a sheet, default to the first table so the UI
    # still has something to render; the user can change it.
    if suggested["sheet"] is None and desc:
        suggested["sheet"] = next(iter(desc))

    return {
        "filename": filename,
        "sheets": desc,  # {name: {shape:[r,c], columns:[...]}}
        "suggested": suggested,
        "read_mode": read_mode,
        "complete": bool(
            suggested["sheet"] and suggested["subject_id"] and suggested["state"]
        ),
    }


def _hash_id(value: Any) -> str:
    """Deterministic short hash of a subject id -- de-identifies flags returned to
    the browser (the caller sees stable, non-reversible ids, never the raw value)."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def audit_upload(
    filename: str,
    data: bytes,
    mapping_in: dict[str, Any],
    normalize: bool = True,
) -> dict[str, Any]:
    """Run the staging audit on the uploaded file using the caller's confirmed mapping.

    ``mapping_in`` = {sheet, subject_id, state, visit_date?, visit?}. subject_id
    and state are required; visit_date/visit are optional (dates are derived from
    visit/row order when absent -- surfaced as a warning). Returns cTCS, CI,
    counts, flags (of the caller's own file), citations, the audit_id, and the
    self-verifying bundle.
    """
    tables, read_mode = _read_upload(filename, data)

    sheet = _norm(mapping_in.get("sheet"))
    subject_id = _norm(mapping_in.get("subject_id"))
    state = _norm(mapping_in.get("state"))
    visit_date = _norm(mapping_in.get("visit_date"))
    visit = _norm(mapping_in.get("visit"))

    if not sheet or not subject_id or not state:
        raise UploadError(
            "mapping incomplete: 'sheet', 'subject_id' and 'state' are required."
        )
    if sheet not in tables:
        raise UploadError(
            f"sheet '{sheet}' is not in the uploaded file "
            f"(available: {list(tables)})."
        )

    # Warn if the chosen state column looks like raw numeric codes -- those get
    # matched to a published numeric scheme that may not be the caller's, and
    # misinterpreted (see the guide). Surfaced in the response; never blocks.
    state_looks_numeric = state in _numeric_like_columns(tables[sheet])

    # Work on a COPY so we never mutate the reader's frame, and apply two
    # transforms before the audit runs:
    work_df = tables[sheet].copy()

    # (1) Optional label normalization (reuse the shipped citation-anchored
    # ontology): map raw stage labels ("Normal", "cognitively normal",
    # "Alzheimer's disease", "early MCI", ...) to the canonical
    # CN/SMC/EMCI/LMCI/MCI/AD the rule packs consume -- the same transform the
    # CLI's --normalize-labels applies. NON-SILENT: every raw->canonical change is
    # reported back in the response. (Numeric scale scores like CDR-global or
    # NACCUDSD codes are NOT label synonyms, so they are left untouched -- those
    # need cohort-specific crosswalks.)
    label_normalization: list[dict[str, str]] = []
    if normalize and state in work_df.columns:
        try:
            from neurotcs.orchestration.label_normalization import (
                load_label_ontology,
                normalize_labels,
            )
            ont = load_label_ontology()
            # Normalize ONLY non-null cells. A missing state (NaN/blank) must stay
            # NaN so the engine drops that visit exactly as the CLI does -- calling
            # .astype(str) on the whole column would turn NaN into the literal
            # string "nan", which the engine then audits as an out-of-vocabulary
            # state (2 spurious impossible transitions), diverging from the CLI.
            col = work_df[state]
            mask = col.notna()
            res = normalize_labels(list(col[mask].astype(str)), ont)
            work_df.loc[mask, state] = res.normalized
            seen: set[tuple[str, str]] = set()
            for rec in getattr(res, "applied", []) or []:
                key = (rec.get("raw", ""), rec.get("canonical", ""))
                if key not in seen and key[0] != key[1]:
                    seen.add(key)
                    label_normalization.append({
                        "raw": rec.get("raw", ""),
                        "canonical": rec.get("canonical", ""),
                    })
        except Exception:  # noqa: BLE001 -- normalization is best-effort convenience
            label_normalization = []

    # (2) De-identify: hash the subject-id column BEFORE the audit, so the entire
    # pipeline (cTCS, flags, audit_id, and the self-verifying bundle) is computed
    # over hashed ids. The raw id never enters the engine or any returned artifact.
    # Hashing is a bijection per id, so trajectory grouping -- and therefore the
    # cTCS/counts -- are IDENTICAL to a raw-id audit; only the id labels change.
    if subject_id in work_df.columns:
        work_df[subject_id] = work_df[subject_id].astype(str).map(_hash_id)

    tables[sheet] = work_df

    clinical: dict[str, Any] = {
        "sheet": sheet,
        "subject_id": subject_id,
        "state": state,
    }
    if visit_date:
        clinical["visit_date"] = visit_date
    if visit:
        clinical["visit"] = visit
    mapping = {"clinical": clinical, "ranges": []}

    warnings: list[str] = []
    try:
        submission = tables_to_submission(tables, mapping, warnings=warnings)
    except (ValueError, KeyError) as e:
        raise UploadError(f"mapping does not match the data: {e}") from e

    result = run_full_audit(submission, expected_layers=_EXPECTED_LAYERS)

    staging = next(
        (lyr for lyr in result.layers
         if lyr.layer == "staging_clinical" and lyr.ran),
        None,
    )
    if staging is None:
        raise UploadError(
            "the staging layer did not run -- check that 'state' points at a "
            "recognized staging column (CN/MCI/AD-style values)."
        )

    summary = staging.summary
    ctcs = summary.get("ctcs")
    n_transitions = int(summary.get("n_transitions", 0))
    n_flagged = int(summary.get("n_flagged", 0))

    # Citation + rulepack identity (reuse the loader).
    pack_name = summary.get("pack")
    rulepack_id = citation_pmid = citation_doi = None
    if pack_name:
        try:
            lp = load_rulepack(pack_name)
            rulepack_id = lp.rulepack.rulepack_id
            citation_pmid = lp.rulepack.anchor_citation.citation_pmid
            citation_doi = lp.rulepack.anchor_citation.citation_doi
        except Exception:  # noqa: BLE001 -- citation is metadata, never fail on it
            rulepack_id = pack_name

    # Build the self-verifying bundle. Fingerprint = sha256 of the raw upload
    # bytes ("same file -> same audit_id").
    raw_sha = hashlib.sha256(data).hexdigest()
    try:
        bundle = build_bundle(
            result,
            input_fingerprint=raw_sha,
            input_fingerprint_kind="raw_file_sha256",
            raw_input_sha256=raw_sha,
            input_warnings=warnings,
        )
    except Exception as e:  # noqa: BLE001
        raise UploadError(f"failed to build bundle: {e}") from e

    # Flags of the caller's OWN file (capped). Each is a transition the engine
    # judged inadmissible under the cited pack. Subject ids are ALREADY hashed
    # (the whole audit ran over hashed ids), so nothing raw leaves the process.
    flags = list(staging.flags or [])
    flags_out = flags[:MAX_FLAGS_RETURNED]

    return {
        "filename": filename,
        "sheet": sheet,
        "mapping": clinical,
        "read_mode": read_mode,
        "ctcs": float(ctcs) if ctcs is not None else None,
        "ci_low": summary.get("ctcs_ci_95_low"),
        "ci_high": summary.get("ctcs_ci_95_high"),
        "ci_method": summary.get("ctcs_ci_method"),
        "n_transitions": n_transitions,
        "n_flagged": n_flagged,
        "flagged_rate": (n_flagged / n_transitions) if n_transitions else 0.0,
        "status": "FLAGS_PRESENT" if n_flagged else "CLEAN",
        "audit_id": staging.audit_id,
        "rulepack_id": rulepack_id,
        "citation_pmid": citation_pmid,
        "citation_doi": citation_doi,
        "neurotcs_version": neurotcs.__version__,
        "label_normalization": label_normalization,
        "subject_ids_hashed": True,
        "state_looks_numeric": state_looks_numeric,
        "warnings": warnings,
        "flags": flags_out,
        "flags_truncated": len(flags) > len(flags_out),
        "bundle": bundle,
    }

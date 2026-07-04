"""In-memory upload audit for the NeuroTCS demo -- BYO file, same engine path.

Lets an expert upload a single .xlsx/.csv, get a describe-style auto-suggested
column mapping (subject_id / visit_date / state), confirm/adjust it, and run the
SAME staging audit path the cohorts use. Nothing is reimplemented:

    _read_bytes_as_table(data, name)      # neurotcs.io.readers -- in-memory (BytesIO),
                                          #   the same reader used for zip/gz members
      -> describe_tables(tables)          # neurotcs.io -- sheet/column inventory
      -> _scaffold_mapping(desc)          # neurotcs.cli -- the `describe` auto-mapping
      -> tables_to_submission(tables, m)  # neurotcs.io -- same submission builder
      -> run_full_audit(submission)       # neurotcs.orchestration -- the engine
      -> build_bundle(result, ...)        # neurotcs -- the self-verifying artifact

DUA / privacy: the upload is processed ENTIRELY IN MEMORY. The bytes are read
from the request into a local variable, parsed via BytesIO, and never written to
disk (uploads are restricted to xlsx/xls/csv/tsv, none of which take the temp-file
path in _read_bytes_as_table). The tables and bytes are discarded when the request
returns. The response carries the audit result of the caller's OWN file back to
the same caller; it is not a DUA cohort.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

import neurotcs
from neurotcs import build_bundle, load_rulepack
from neurotcs.cli import _clean_mapping, _scaffold_mapping
from neurotcs.io import describe_tables, tables_to_submission
from neurotcs.io.readers import _read_bytes_as_table
from neurotcs.orchestration.orchestrator import run_full_audit

# Uploads are restricted to formats _read_bytes_as_table parses via BytesIO only
# (no temp file). Statistical formats (.sav/.dta/.rds) are intentionally excluded
# because their readers need a path -- keeping the "never touch disk" guarantee.
ALLOWED_EXT = (".xlsx", ".xls", ".csv", ".tsv")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB -- a demo staging file, not a data lake
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


def _read_upload(filename: str, data: bytes) -> dict[str, pd.DataFrame]:
    """Parse the uploaded bytes into tables IN MEMORY. Fail-closed on type/size."""
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
    decisions: list[str] = []
    try:
        tables = _read_bytes_as_table(
            data, filename, allow_pdf=False, encoding=None, decisions=decisions
        )
    except Exception as e:  # noqa: BLE001 -- surface a clean parse error to the client
        raise UploadError(f"could not read the file: {e}") from e
    if not tables:
        raise UploadError("the file contained no readable tables.")
    return tables


def describe_upload(filename: str, data: bytes) -> dict[str, Any]:
    """Read the upload in memory and return the sheet inventory + suggested mapping.

    Does NOT run an audit -- this is the "confirm the mapping" step. Returns the
    columns per sheet (so the UI can build dropdowns) and the auto-detected
    clinical staging axis (subject_id / state / visit_date / visit), with
    placeholders normalized to null.
    """
    tables = _read_upload(filename, data)
    desc = describe_tables(tables)
    mapping = _clean_mapping(_scaffold_mapping(desc))
    clinical = mapping.get("clinical", {}) if isinstance(mapping, dict) else {}

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
        "complete": bool(
            suggested["sheet"] and suggested["subject_id"] and suggested["state"]
        ),
    }


def audit_upload(filename: str, data: bytes, mapping_in: dict[str, Any]) -> dict[str, Any]:
    """Run the staging audit on the uploaded file using the caller's confirmed mapping.

    ``mapping_in`` = {sheet, subject_id, state, visit_date?, visit?}. subject_id
    and state are required; visit_date/visit are optional (dates are derived from
    visit/row order when absent -- surfaced as a warning). Returns cTCS, CI,
    counts, flags (of the caller's own file), citations, the audit_id, and the
    self-verifying bundle.
    """
    tables = _read_upload(filename, data)

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
    # judged inadmissible under the cited pack.
    flags = list(staging.flags or [])
    flags_out = flags[:MAX_FLAGS_RETURNED]

    return {
        "filename": filename,
        "sheet": sheet,
        "mapping": clinical,
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
        "warnings": warnings,
        "flags": flags_out,
        "flags_truncated": len(flags) > len(flags_out),
        "bundle": bundle,
    }

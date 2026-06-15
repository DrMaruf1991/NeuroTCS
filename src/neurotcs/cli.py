"""NeuroTCS command-line interface.

Verbs:
  describe <file> [--emit-mapping PATH]   inspect a dataset file; scaffold a mapping
  audit    <file> --mapping map.json ...  audit a dataset, emit a fingerprinted bundle
  verify   <bundle.json>                  re-verify a fingerprinted bundle (tamper check)

Exit codes (stable contract -- safe to branch on in pipelines):
  0  CLEAN              audit ran, no flags / bundle verified
  1  FLAGS_PRESENT      audit ran, flags found
  2  (argparse usage)   bad command-line arguments
  3  INCOMPLETE_REFUSED auditor refused (e.g. unrecorded skip)
  4  INPUT_ERROR        file/mapping problem (missing, unreadable, unmapped)
  5  VERIFY_FAILED      bundle failed verification (tampered / malformed)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from neurotcs import (
    BundleVerificationError,
    build_bundle,
    fingerprint_dataframe,
    fingerprint_file,
    render_report,
    run_full_audit,
    verify_bundle,
)
from neurotcs.io import (
    AmbiguousInputError,
    PdfExtractionError,
    UnsupportedFormatError,
    describe_tables,
    read_tables,
    tables_to_submission,
)
from neurotcs.report import bundle_to_pdf, bundle_to_svg, flags_to_csv

EXIT_CLEAN = 0
EXIT_FLAGS = 1
EXIT_REFUSED = 3
EXIT_INPUT = 4
EXIT_VERIFY = 5

_STAGING_COLS = ("subject_id", "visit", "visit_date", "state")
_RANGE_COLS = ("patient_id", "visit_id", "measurement_name", "value", "unit")


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _note(msg: str) -> None:
    """Informational note to stderr -- NOT an error. On stderr (never
    stdout) so it cannot contaminate piped bundle/JSON output, but without
    the misleading 'error:' prefix that mislabels notes in production logs.
    """
    print(msg, file=sys.stderr)


def _load_tables(path: str, allow_pdf: bool,
                 encoding: str | None = None) -> dict[str, Any] | None:
    skipped: list[str] = []
    decisions: list[str] = []
    try:
        tables = read_tables(path, allow_pdf=allow_pdf, encoding=encoding,
                             skipped=skipped, decisions=decisions)
    except (FileNotFoundError, UnsupportedFormatError, PdfExtractionError,
            AmbiguousInputError) as e:
        _err(str(e))
        return None
    # Surface every non-trivial read decision (encoding chosen, folder/zip
    # contents, delimiter) and every skipped non-data file -- never hidden.
    for d in decisions:
        _note(f"NOTE: {d}")
    for s in skipped:
        _note(f"NOTE: skipped non-data file (not read): {s}")
    return tables


# --------------------------------------------------------------------------- #
# describe
# --------------------------------------------------------------------------- #
def cmd_describe(args: argparse.Namespace) -> int:
    tables = _load_tables(args.file, args.allow_pdf, args.encoding)
    if tables is None:
        return EXIT_INPUT
    desc = describe_tables(tables)
    print(f"# {args.file}")
    for name, info in desc.items():
        print(f"  sheet '{name}': {info['shape'][0]} rows x {info['shape'][1]} cols")
        print(f"    columns: {info['columns']}")

    if args.emit_mapping is not None:
        mapping = _scaffold_mapping(desc)
        out = Path(args.emit_mapping)
        out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        print(f"\nwrote mapping template -> {out}")
        cleaned = _clean_mapping(mapping)
        if _has_placeholder(cleaned):
            print("Some fields could not be auto-detected. Edit the '<FILL:...>' "
                  f"placeholders, then: neurotcs audit {args.file} --mapping {out}")
        else:
            print("Mapping is complete (everything auto-detected). Run: "
                  f"neurotcs audit {args.file} --mapping {out}")
            print("Or skip the mapping entirely: "
                  f"neurotcs audit {args.file} -o audit_out")
    return EXIT_CLEAN


def _match(columns: list[str], canonical: str) -> str:
    """Return the column if its canonical name is present, else a FILL placeholder."""
    return canonical if canonical in columns else f"<FILL:{canonical}>"


# --------------------------------------------------------------------------- #
# v1.37.0 -- smart sheet + column auto-detection for emit_mapping
#
# Before v1.37, _scaffold_mapping did "first sheet wins" -- a 5-sheet file like
# [Index, EN, AUDIT_CLINICAL, AUDIT_BIOLOGICAL, BIO] would auto-route clinical
# to Index (table-of-contents!) and biological to EN (enrollment, no biological
# state). A blind user hit that wall and the tool was unusable. v1.37 fixes the
# auto-detection so 'describe --emit-mapping' produces a mapping that JUST WORKS
# for datasets following obvious conventions, without hand-editing JSON.
# --------------------------------------------------------------------------- #

# Sheet-name patterns and scores per axis. Higher score = stronger match.
# A pattern is matched substring-case-insensitively on the sheet name.
_AXIS_SHEET_SCORES = {
    "clinical": (
        ("audit_clinical",   100),
        ("clinical_audit",    95),
        ("audit_clin",        90),
        ("clinical_staging",  90),
        ("clinical_state",    90),
        ("clinical",          80),
        ("staging_clinical",  85),
        ("diagnosis",         72),
        ("clin_state",        75),
        ("dx_state",          75),
        ("cdr_staging",       65),
        # v1.39.0: CDISC 'QS' (Questionnaires) and short 'dx'/'diagnosis' sheets
        ("qs",                60),
        ("dx",                60),
    ),
    "biological": (
        ("audit_biological", 100),
        ("biological_audit",  95),
        ("audit_bio",         90),
        ("biological_staging",90),
        ("biological_state",  90),
        ("biological",        80),
        ("atn_staging",       80),
        ("atn_state",         80),
        ("atn",               70),
        ("biomarker_staging", 70),
        # v1.39.0: a lone 'BIO' sheet routes to biological (low score so it never
        # beats AUDIT_BIOLOGICAL when both exist; still subject to the
        # recognizable-field guard in _build_axis_spec)
        ("bio",               55),
    ),
}

# v1.39.0: candidate MEASUREMENT (range-pack) sheet detection. These are surfaced
# in _notes as suggestions ONLY -- never auto-assigned to a pack, because picking
# which pack a sheet maps to is a guess and NeuroTCS does not guess silently.
# Maps a sheet-name substring -> the range-pack DOMAIN it most likely belongs to.
_MEASUREMENT_SHEET_HINTS = (
    ("mmse",      "cognitive_scales"),
    ("moca",      "cognitive_scales"),
    ("cdr",       "cognitive_scales"),
    ("cognition", "cognitive_scales"),
    ("cog",       "cognitive_scales"),
    ("mri",       "mri_volumetrics"),
    ("imaging",   "mri_volumetrics"),
    ("volumetr",  "mri_volumetrics"),
    ("amyloid",   "pet_amyloid"),
    ("av45",      "pet_amyloid"),
    ("tau_pet",   "tau_pet"),
    ("av1451",    "tau_pet"),
    ("fdg",       "fdg_pet"),
    ("csf",       "csf_biomarkers"),
    ("plasma",    "plasma_biomarkers"),
    ("dti",       "dti"),
    ("perfusion", "perfusion"),
    ("asl",       "perfusion"),
    ("oct",       "retinal_biomarkers"),
    ("retina",    "retinal_biomarkers"),
    ("sleep",     "sleep"),
    ("olfact",    "olfactory"),
)


def _suggest_measurement_domain(name: str) -> str | None:
    """If a sheet name looks like a measurement sheet, return the likely range-pack
    domain (a SUGGESTION for the user, never an auto-assignment)."""
    n = name.lower().strip()
    for pattern, domain in _MEASUREMENT_SHEET_HINTS:
        if pattern in n:
            return domain
    return None


def _sheet_has_recognizable_staging_field(info: dict[str, Any]) -> bool:
    """v1.39.0 (audit item 4): a sheet should not be auto-routed to a staging axis
    unless it has at least one recognizable subject-id-like column AND one
    recognizable state-like column. A sheet with neither (e.g. an enrollment sheet
    with only site + enrollment_date) is not staging data."""
    cols = list(info.get("columns", []))
    has_subject = _best_column(cols, _COL_SYN_SUBJECT_ID, "subject_id",
                               return_none_on_miss=True) is not None
    has_state = (
        _best_column(cols, _COL_SYN_STATE_CLINICAL, "state",
                     return_none_on_miss=True) is not None
        or _best_column(cols, _COL_SYN_STATE_BIOLOGICAL, "state",
                        return_none_on_miss=True) is not None
    )
    return has_subject and has_state

# Sheet names / column-shape signatures that mean "this is a TOC, NEVER auto-route".
_TOC_SHEET_NAMES = {
    "index", "toc", "table_of_contents", "readme", "manifest", "contents",
    "sheet_index", "sheets", "_index",
}
_TOC_COLUMN_SIGNATURES: tuple[tuple[str, ...], ...] = (
    ("sheet", "rows"),
    ("sheet", "description"),
    ("sheet_name", "description"),
    ("table_name", "description"),
    ("name", "description"),
)

# Column-name synonyms per canonical staging field. Each list is searched in order;
# the highest-scoring synonym present (case-insensitive) wins. Original-case column
# name from the actual sheet is returned so pandas indexing works downstream.
#
# v1.38.0: synonym tables expanded to cover the major real-world clinical-data
# conventions (CDISC SDTM, ADNI, OASIS, NACC) per the external-audit design, so a
# file following ANY of these standards auto-maps with zero <FILL:> placeholders:
#   - CDISC SDTM: USUBJID (subject), VISITNUM/VISIT (visit), SVSTDTC (visit date)
#   - ADNI:       RID/PTID (subject), VISCODE/VISCODE2 (visit), EXAMDATE (date)
#   - NACC/OASIS: common dx_status / cognitive-status column names
_COL_SYN_SUBJECT_ID = (
    ("subject_id", 100), ("usubjid", 98), ("subjid", 95), ("patient_id", 95),
    ("patientid", 90), ("rid", 90), ("ptid", 90), ("subject", 80), ("pid", 75),
    ("id", 50),
)
_COL_SYN_VISIT = (
    ("visit", 100), ("visit_id", 95), ("visitid", 95), ("visitnum", 92),
    ("visit_code", 85), ("viscode2", 85), ("viscode", 80), ("avisit", 78),
    ("visitdy", 72), ("event_id", 70), ("event", 65), ("timepoint", 70), ("tp", 60),
)
_COL_SYN_VISIT_DATE = (
    ("visit_date", 100), ("visit_dt", 95), ("examdate", 90), ("exam_date", 90),
    ("svstdtc", 88), ("assessment_date", 86), ("scandate", 85), ("scan_date", 85),
    ("vdate", 80), ("date", 55),
)
# state column is axis-specific (clinical vs biological)
_COL_SYN_STATE_CLINICAL = (
    ("clinical_state", 100), ("dx_state", 95), ("clinical_status", 92),
    ("dx_status", 90), ("diagnosis_state", 90), ("diagnosis_status", 88),
    ("cog_status", 85), ("cognitive_status", 85), ("dx_bl", 80), ("diagnosis", 80),
    ("cdglobal", 72), ("dx", 70), ("state", 60), ("clinical_stage", 65),
)
_COL_SYN_STATE_BIOLOGICAL = (
    ("biological_stage_atn", 100), ("biological_state", 100), ("biological_stage", 95),
    ("atn_stage", 95), ("stage_atn", 95), ("atn_profile", 92),
    ("biological_status", 90), ("atn", 70), ("stage", 55), ("state", 50),
)
# v1.71.0: per-visit treatment / TRAC column (drives the biological TRAC carve-out).
# Explicit names only -- never a broad match, so unrelated cohorts are untouched.
_COL_SYN_TREATMENT = (
    ("trac_status", 100), ("treatment_status", 95), ("trac", 80),
    ("treatment_arm_status", 75),
)


def _is_toc_sheet(name: str, info: dict[str, Any]) -> bool:
    """A TOC / Index sheet is NEVER auto-routed to a clinical/biological axis.

    Detection: (a) sheet name matches a TOC name, OR (b) the sheet's columns match
    a TOC signature like ('Sheet', 'Rows', 'Description')."""
    n = name.lower().strip()
    if n in _TOC_SHEET_NAMES:
        return True
    cols_lower = {str(c).lower() for c in info.get("columns", [])}
    for sig in _TOC_COLUMN_SIGNATURES:
        if all(c in cols_lower for c in sig):
            return True
    return False


def _score_sheet_for_axis(name: str, axis: str) -> int:
    """Return the maximum match score for the given axis (0 = no match)."""
    n = name.lower().strip()
    best = 0
    for pattern, score in _AXIS_SHEET_SCORES[axis]:
        if pattern in n and score > best:
            best = score
    return best


# v1.78.0: separator-insensitive normalization for the staging-column fallback.
# MUST stay byte-identical to neurotcs.io.autowire._norm so the staging matcher
# and the measurement matcher agree on what "same column" means. If you change
# one, change both -- enforced by tests/cli/test_best_column_norm_parity.py.
def _norm_col(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _best_column(cols: list[str], synonyms: tuple[tuple[str, int], ...],
                 fallback_canonical: str, return_none_on_miss: bool = False) -> str | None:
    """Find the highest-scoring synonym present in `cols`.

    Pass 1 (exact, case-insensitive): unchanged historical behavior -- every
    column that mapped before maps identically, so audit_ids never drift.
    Pass 2 (separator-insensitive fallback, v1.78.0): only if Pass 1 misses,
    retry under _norm_col so e.g. `DXSTATUS` matches synonym `dx_status`.
    Mirrors the measurement matcher (io.autowire._find_col/_norm). Fail-closed:
    a Pass-2 hit is accepted ONLY when exactly one column maps; any ambiguity
    (one synonym normalizing onto >1 column) refuses rather than guessing.

    Returns the actual column name from `cols` (original case). If nothing
    matches, returns `<FILL:fallback_canonical>` or None (return_none_on_miss)."""
    cols_lower_to_orig = {str(c).lower(): str(c) for c in cols}
    best_score = 0
    best_col: str | None = None
    for syn, score in synonyms:
        if syn.lower() in cols_lower_to_orig and score > best_score:
            best_score = score
            best_col = cols_lower_to_orig[syn.lower()]
    if best_col is not None:
        return best_col

    # Pass 2: separator-insensitive fallback (only reached when Pass 1 found nothing).
    norm_to_origs: dict[str, list[str]] = {}
    for c in cols:
        norm_to_origs.setdefault(_norm_col(c), []).append(str(c))
    best_score = 0
    best_norm: str | None = None
    for syn, score in synonyms:
        ns = _norm_col(syn)
        if ns in norm_to_origs and score > best_score:
            best_score = score
            best_norm = ns
    if best_norm is not None and len(norm_to_origs[best_norm]) == 1:
        return norm_to_origs[best_norm][0]

    return None if return_none_on_miss else f"<FILL:{fallback_canonical}>"


def _build_axis_spec(sheet: str, info: dict[str, Any], axis: str) -> dict[str, Any]:
    """Build a {sheet, subject_id, visit, visit_date, state} spec by auto-detecting
    columns via the synonym tables.

    visit_date is special: if no synonym matches, the spec gets visit_date=null and
    tables_to_submission will DERIVE synthetic dates from visit ordering. This means
    a real user with a dataset that lacks an explicit date column can still audit
    without hand-editing JSON. The auditor itself never sees the null -- it sees
    derived dates that preserve visit order."""
    cols = list(info.get("columns", []))
    state_syns = _COL_SYN_STATE_BIOLOGICAL if axis == "biological" else _COL_SYN_STATE_CLINICAL
    spec = {
        "sheet": sheet,
        "subject_id": _best_column(cols, _COL_SYN_SUBJECT_ID, "subject_id"),
        "visit":      _best_column(cols, _COL_SYN_VISIT, "visit"),
        # visit_date may be None -> consumer derives from visit order. Don't FILL.
        "visit_date": _best_column(cols, _COL_SYN_VISIT_DATE, "visit_date",
                                   return_none_on_miss=True),
        "state":      _best_column(cols, state_syns, "state"),
    }
    # v1.71.0: on the biological axis, also wire a per-visit treatment / TRAC
    # column if one is present, so tables_to_submission retains it and the
    # staging layer can apply the TRAC carve-out. Optional and additive: absent
    # column => key absent => unchanged behavior.
    if axis == "biological":
        _tx = _best_column(cols, _COL_SYN_TREATMENT, "treatment_status",
                           return_none_on_miss=True)
        if _tx is not None:
            spec["treatment_status"] = _tx
    return spec


def _detect_treatment_status_col(submission: dict[str, Any]) -> str | None:
    """Return the per-visit treatment column name to thread to the staging layer.

    By v1.71.0 design, `tables_to_submission` already retains a recognized
    treatment column on the staging frame as the literal column
    ``treatment_status`` (wired by the biological axis spec). This helper looks
    for that retained column on the staging frames and, when present, normalizes
    its values so that markers denoting treatment-related amyloid clearance read
    as the literal ``"TRAC"`` the biological-letter pack matches on (all other
    values pass through unchanged, so untreated rows still fail the carve-out and
    a genuine regression is flagged). Returns ``"treatment_status"`` if wired,
    else ``None`` (=> unchanged behavior).
    """
    import pandas as _pd

    _trac_markers = {"trac", "full_trac", "partial_trac"}
    for _axis in ("biological", "clinical"):
        _frame = submission.get(_axis)
        if not isinstance(_frame, _pd.DataFrame):
            continue
        if "treatment_status" not in _frame.columns:
            continue
        _vals = _frame["treatment_status"].astype(str)
        _is_trac = _vals.str.strip().str.lower().isin(_trac_markers)
        if not _is_trac.any():
            # Column present but no TRAC marker: still thread it (a future TRAC
            # row would be honored), but no normalization needed.
            return "treatment_status"
        _frame = _frame.copy()
        _frame["treatment_status"] = _vals.where(~_is_trac, "TRAC")
        submission[_axis] = _frame
        return "treatment_status"
    return None


def _scaffold_mapping(desc: dict[str, Any]) -> dict[str, Any]:
    """Build a mapping by AUTO-DETECTING which sheet feeds which axis.

    Strategy:
      1. Reject TOC / Index sheets outright (never auto-routed).
      2. Score each remaining sheet for clinical and biological axes by name pattern.
      3. Pick the highest-scoring sheet per axis (must score > 0).
      4. Within the chosen sheet, auto-detect columns via the synonym tables.
      5. If a column synonym misses, leave a <FILL:...> placeholder for review;
         except visit_date, which becomes null and is DERIVED from visit ordering
         at audit time (no hand-editing required for datasets that omit dates).

    Backward compatibility: a CSV with canonical column names (subject_id, visit,
    visit_date, state) on a single 'sheet' still works -- the first sheet wins as
    clinical, all synonyms find exact matches, visit_date is non-null.
    """
    if not desc:
        return {"clinical": {"sheet": "<FILL:sheet>",
                             **{c: f"<FILL:{c}>" for c in _STAGING_COLS}},
                "ranges": []}

    # 1. Classify sheets: TOC vs candidate
    candidates: dict[str, list[tuple[int, str, dict[str, Any]]]] = {
        "clinical": [], "biological": [],
    }
    non_toc_sheets: list[tuple[str, dict[str, Any]]] = []
    measurement_suggestions: list[str] = []
    for name, info in desc.items():
        if _is_toc_sheet(name, info):
            continue  # never auto-route TOC
        non_toc_sheets.append((name, info))
        # collect measurement-sheet suggestions (item 1 extension; notes only)
        dom = _suggest_measurement_domain(name)
        if dom is not None:
            measurement_suggestions.append(f"{name} -> ranges/{dom}")
        # axis candidates: name must score > 0 AND the sheet must actually have
        # recognizable staging fields (item 4: don't route a field-less sheet)
        if not _sheet_has_recognizable_staging_field(info):
            continue
        for axis in ("clinical", "biological"):
            sc = _score_sheet_for_axis(name, axis)
            if sc > 0:
                candidates[axis].append((sc, name, info))

    mapping: dict[str, Any] = {"_detected": desc}
    auto_routed: list[str] = []

    # 2. Pick best sheet per axis. Normally we avoid double-assignment of the
    #    same sheet (two physical sheets, one per axis). EXCEPTION (v1.71.0): a
    #    single sheet that carries BOTH a recognizable clinical state column AND
    #    a distinct recognizable biological state column (e.g. a one-CSV trial
    #    export with both `clinical_stage` and `biological_stage`) may serve both
    #    axes -- otherwise the biological axis could never auto-engage on a
    #    single-sheet file. We only allow the re-use when the two axes resolve to
    #    DIFFERENT state columns (so we never stage the same column twice).
    chosen_sheets: set[str] = set()
    axis_state_col: dict[str, str | None] = {}
    for axis in ("clinical", "biological"):
        ranked = sorted(candidates[axis], reverse=True)  # (score, name, info)
        for score, name, info in ranked:
            spec = _build_axis_spec(name, info, axis)
            this_state = spec.get("state")
            if name in chosen_sheets:
                # Sheet already used by the other axis. Allow dual-axis use only
                # if this axis resolves to a DIFFERENT, real (non-FILL) state
                # column than the one already taken on that sheet.
                other_states = {
                    axis_state_col[a]
                    for a in axis_state_col
                    if mapping.get(a, {}).get("sheet") == name
                }
                is_real = isinstance(this_state, str) and not this_state.startswith("<FILL")
                if not (is_real and this_state not in other_states):
                    continue
            mapping[axis] = spec
            axis_state_col[axis] = this_state
            chosen_sheets.add(name)
            auto_routed.append(f"{axis}<-{name} (score {score})")
            break

    # 3. If neither axis got a name-pattern match, fall back to the first non-TOC
    #    sheet that ACTUALLY has recognizable staging fields (item 4 guard). A
    #    generically-named single sheet (e.g. a one-CSV trial export named
    #    "Trial_Dataset") scores 0 for both axis NAME patterns, so it reaches
    #    here. v1.71.0: assign BOTH axes from that sheet when it carries a real
    #    (non-FILL) clinical state column AND a distinct real biological state
    #    column -- otherwise the biological axis could never auto-engage on such
    #    a file. Clinical alone remains the behavior when only one is present
    #    (byte-identical to pre-v1.71 for single-axis files).
    if not auto_routed:
        fallback = next(
            ((n, i) for n, i in non_toc_sheets
             if _sheet_has_recognizable_staging_field(i)),
            None,
        )
        if fallback is not None:
            name, info = fallback
            clin_spec = _build_axis_spec(name, info, "clinical")
            bio_spec = _build_axis_spec(name, info, "biological")
            clin_state = clin_spec.get("state")
            bio_state = bio_spec.get("state")
            clin_real = isinstance(clin_state, str) and not clin_state.startswith("<FILL")
            bio_real = isinstance(bio_state, str) and not bio_state.startswith("<FILL")
            if clin_real:
                mapping["clinical"] = clin_spec
                auto_routed.append(f"clinical<-{name} (fallback: no name match found)")
                # only add biological if it resolves to a DIFFERENT real column
                if bio_real and bio_state != clin_state:
                    mapping["biological"] = bio_spec
                    auto_routed.append(
                        f"biological<-{name} (fallback: distinct biological state column)")
            elif bio_real:
                # biological-only single sheet (no clinical state column)
                mapping["biological"] = bio_spec
                auto_routed.append(f"biological<-{name} (fallback: no name match found)")
            else:
                mapping["clinical"] = _build_axis_spec(name, info, "clinical")
                auto_routed.append(f"clinical<-{name} (fallback: no name match found)")
        else:
            mapping["clinical"] = {
                "sheet": "<FILL:sheet>",
                **{c: f"<FILL:{c}>" for c in _STAGING_COLS},
            }

    # 4. Top-level notes block (consumed by the user, dropped by _clean_mapping)
    notes = [
        "v1.37+ emit-mapping: sheets auto-routed by name pattern; columns auto-"
        "detected by synonym table (CDISC / ADNI / OASIS / NACC conventions).",
        "Auto-routing performed: " + ("; ".join(auto_routed) if auto_routed
                                      else "(none -- no sheet had recognizable "
                                           "staging fields)"),
        "<FILL:...> placeholders mean auto-detection couldn't find a match. EDIT "
        "those to point at the right column.",
        "visit_date == null means no date column was detected; visit_date will "
        "be DERIVED from visit ordering at audit time and a NOTE will be printed "
        "(no editing required; pass --allow-no-dates to acknowledge explicitly).",
        "TOC / Index sheets and sheets with no recognizable staging fields are "
        "intentionally excluded from auto-routing.",
        # v1.40.3 (E-2026-013): document the autowire-in-explicit-mapping
        # behavior so users know they DON'T need to author 'ranges' entries for
        # safe ordinal biomarkers. The audit path auto-wires safe ordinal packs
        # (MMSE/MoCA/CDR-SB/ADAS/NPI-Q/Braak/...) from any un-staged sheet that
        # has subject_id + visit columns, with the SAME fail-closed default for
        # assay-calibrated biomarkers (CSF/plasma/centiloid/volumetrics/FDG).
        "v1.40.3: 'ranges' may be left empty -- the audit path auto-wires safe "
        "ordinal packs from un-staged measurement sheets. Assay-calibrated "
        "biomarkers (CSF/plasma p-tau, NfL, centiloid, volumetry, FDG) are "
        "REFUSED by default (a column name cannot certify the assay); pass "
        "--confirm-assays to assert the data matches the matched pack's "
        "assay/scale, or add explicit 'ranges' entries to override per-column.",
    ]
    if measurement_suggestions:
        notes.append(
            "Candidate MEASUREMENT sheets detected (add to 'ranges' with the right "
            "pack id if they contain biomarker/cognitive measurements; NOT auto-"
            "assigned because pack selection must be explicit): "
            + "; ".join(measurement_suggestions)
        )
    mapping["_notes"] = notes

    mapping["ranges"] = []
    mapping["_ranges_example"] = {
        "sheet": "<FILL:measurements_sheet>",
        "pack": "<FILL:domain/pack_name>",
        **{c: f"<FILL:{c}>" for c in _RANGE_COLS},
    }
    return mapping


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def _clean_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """Drop the reference '_detected' block and any unfilled placeholder sections."""
    m = {k: v for k, v in mapping.items() if not k.startswith("_")}
    # drop a section if it still has FILL placeholders (so a half-edited template
    # fails loudly with a clear message rather than silently auditing nothing)
    return m


def _has_placeholder(obj: Any) -> bool:
    if isinstance(obj, str):
        return obj.startswith("<FILL:")
    if isinstance(obj, dict):
        return any(_has_placeholder(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_placeholder(v) for v in obj)
    return False


def _sheets_referenced_by_mapping(mapping: dict[str, Any]) -> set[str]:
    """Every sheet name the mapping actually wires into an audit (clinical /
    biological axes + each ranges entry). Used to compute file-level coverage:
    any sheet in the input NOT in this set was not audited."""
    refs: set[str] = set()
    for axis in ("clinical", "biological"):
        spec = mapping.get(axis)
        if isinstance(spec, dict) and isinstance(spec.get("sheet"), str):
            refs.add(spec["sheet"])
    for r in mapping.get("ranges") or []:
        if isinstance(r, dict) and isinstance(r.get("sheet"), str):
            refs.add(r["sheet"])
    return refs


def _columns_consumed_by_mapping(mapping: dict[str, Any]) -> dict[str, list[str]]:
    """Per source sheet, the columns the mapping actually wires into an audit.

    Staging axes consume {subject_id, visit, visit_date, state}; each ranges
    entry consumes {subject_id, visit_id, measurement_name, observed_value}.
    Only real, named columns are counted -- this is the machine-readable twin of
    the human coverage narrative, so it must never overstate what was examined.
    """
    consumed: dict[str, set[str]] = {}
    for axis in ("clinical", "biological"):
        spec = mapping.get(axis)
        if not isinstance(spec, dict):
            continue
        sheet = spec.get("sheet")
        if not isinstance(sheet, str):
            continue
        for key in ("subject_id", "visit", "visit_date", "state"):
            col = spec.get(key)
            if isinstance(col, str) and col:
                consumed.setdefault(sheet, set()).add(col)
    for r in mapping.get("ranges") or []:
        if not isinstance(r, dict):
            continue
        sheet = r.get("sheet")
        if not isinstance(sheet, str):
            continue
        for key in ("subject_id", "visit_id", "measurement_name",
                    "observed_value"):
            col = r.get(key)
            if isinstance(col, str) and col:
                consumed.setdefault(sheet, set()).add(col)
    return {s: sorted(cols) for s, cols in consumed.items()}


def _refused_columns(range_refusals: list[str]) -> dict[str, str]:
    """Parse autowire refusals 'sheet.column: reason' -> {'sheet.column': reason}.

    Captures the assay-not-certified / unit-mismatch refusals so the bundle
    records WHY a column was not audited, not only that it was skipped.
    """
    out: dict[str, str] = {}
    for rr in range_refusals:
        if ":" in rr:
            key, reason = rr.split(":", 1)
            out[key.strip()] = reason.strip()
        else:
            out[rr.strip()] = ""
    return out


def _column_coverage_ledger(
    tables: dict[str, Any],
    mapping: dict[str, Any],
    autowired_sources: set[str],
    range_refusals: list[str],
) -> dict[str, Any]:
    """Build the machine-readable column-coverage ledger for the bundle.

    Partitions every column of every input sheet into exactly one of:
      consumed -- a wired pack/axis read it,
      refused  -- a pack resolved it but declined (assay/unit), with the reason,
      unwired  -- present but no pack attached (sheet not referenced/autowired),
    plus columns_present (the full inventory). Fail-honest: a column is only
    'consumed' if the mapping names it; everything else is reported, never
    silently dropped.
    """
    columns_present: dict[str, list[str]] = {}
    for sheet, df in tables.items():
        if sheet.startswith("__autowired__"):
            continue
        try:
            cols = [str(c) for c in df.columns]
        except Exception:
            continue
        columns_present[sheet] = cols

    columns_consumed = _columns_consumed_by_mapping(mapping)
    columns_refused = _refused_columns(range_refusals)
    refused_cols_by_sheet: dict[str, set[str]] = {}
    for key in columns_refused:
        if "." in key:
            sheet, col = key.split(".", 1)
            refused_cols_by_sheet.setdefault(sheet, set()).add(col)

    referenced = _sheets_referenced_by_mapping(mapping)
    columns_unwired: dict[str, list[str]] = {}
    for sheet, cols in columns_present.items():
        if sheet in referenced or sheet in autowired_sources:
            # sheet was wired/used; any of its columns not consumed are reported
            # as ignored by the orchestrator (present - consumed), not unwired.
            continue
        if _is_toc_sheet(sheet, {"columns": cols}):
            continue
        columns_unwired[sheet] = sorted(cols)

    return {
        "columns_present": columns_present,
        "columns_consumed": columns_consumed,
        "columns_refused": columns_refused,
        "columns_unwired": columns_unwired,
    }


def cmd_audit(args: argparse.Namespace) -> int:
    tables = _load_tables(args.file, args.allow_pdf, args.encoding)
    range_refusals: list[str] = []
    _autowired_source_sheets: set[str] = set()
    if tables is None:
        return EXIT_INPUT

    # v1.80.0 (hazard H6 / gap G3): optional direct-identifier (PHI) input
    # gate. WARNS by default on probable direct identifiers (a patient_name /
    # MRN / SSN / DOB column, or SSN/email-shaped values), allowlisting the
    # de-identified study vocabulary so cohort data never trips it.
    # --refuse-phi turns the warning into a fail-closed refusal. Best-effort,
    # NOT a de-identification guarantee (see docs/PHI_INPUT_GATE.md).
    from neurotcs.io.phi_gate import scan_tables, format_findings
    _phi = scan_tables(tables)
    if _phi.has_findings:
        for _line in format_findings(_phi):
            _note(f"NOTE: {_line}")
        if getattr(args, "refuse_phi", False):
            _err("refusing: probable PHI detected and --refuse-phi is set. "
                 "De-identify the input (or remove the flagged columns) and "
                 "re-run. This gate is best-effort, not a de-identification "
                 "guarantee.")
            return EXIT_INPUT

    # v1.42.0: snapshot the ORIGINAL wide-format sheets before autowire_ranges
    # mutates `tables` with derived long-format range tables. The cross-sheet
    # role resolver must see the original cohort sheets, not the long-format
    # measurement tables (which would mis-merge on measurement_name/value/unit).
    _original_tables = dict(tables)

    # v1.39.2: zero-config path. If --mapping is omitted, auto-scaffold one
    # in-memory from the recognized sheet/column conventions. This is the
    # Layer-1 "strong conventions, zero mapping" path the input contract
    # promises -- a low-knowledge user runs `neurotcs audit file.xlsx -o out`
    # and a conventional file just works. It NEVER silently guesses: it only
    # auto-runs when detection is COMPLETE (no <FILL:> placeholders), it PRINTS
    # exactly what it auto-detected, and it falls back to the explicit-mapping
    # workflow the moment anything is ambiguous.
    if args.mapping is None:
        scaffold = _scaffold_mapping(describe_tables(tables))
        mapping = _clean_mapping(scaffold)
        if _has_placeholder(mapping) or not any(
            k in mapping for k in ("clinical", "biological")
        ):
            _err(
                "could not auto-detect a complete mapping for this file. "
                f"Run:  neurotcs describe {args.file} --emit-mapping mapping.json  "
                "then edit the '<FILL:...>' placeholders and re-run with "
                "--mapping mapping.json. (See INPUT_CONTRACT.md for the recognized "
                "sheet and column names.)"
            )
            return EXIT_INPUT
        if not args.quiet:
            print("# auto-detected mapping (no --mapping given):")
            for axis in ("clinical", "biological"):
                if axis in mapping:
                    sp = mapping[axis]
                    vd = sp.get("visit_date") or "(derived from visit order)"
                    print(f"  {axis}: sheet '{sp['sheet']}' "
                          f"subject_id={sp['subject_id']} visit={sp['visit']} "
                          f"visit_date={vd} state={sp['state']}")
            print("  (to override, generate and edit a mapping with "
                  "`neurotcs describe ... --emit-mapping mapping.json`)")

        # v1.40.0: auto-wire range packs to wide-format measurement sheets so
        # biomarker/cognitive VALUES are audited too -- not just staging. Strict:
        # a column is wired only on a confident name+unit match to exactly one
        # production pack; ambiguous / unit-mismatched columns are refused (left
        # to the coverage declaration). Every wiring decision is printed.
        from neurotcs.io.autowire import autowire_ranges
        wired_sheets = _sheets_referenced_by_mapping(mapping)
        consumed_cols = _columns_consumed_by_mapping(mapping)
        rspecs, extra_tables, decisions, _refusals, _wired_src = autowire_ranges(
            tables, wired_sheets,
            confirm_assays=getattr(args, "confirm_assays", False),
            consumed_columns=consumed_cols)
        range_refusals.extend(_refusals)
        _autowired_source_sheets.update(_wired_src)
        if rspecs:
            tables.update(extra_tables)
            mapping.setdefault("ranges", []).extend(rspecs)
            if not args.quiet:
                print("# auto-wired range packs (values audited; "
                      "each decision shown):")
                for d in decisions:
                    print(f"  {d}")
    else:
        try:
            mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
        except FileNotFoundError:
            _err(f"mapping file not found: {args.mapping}. Generate one with: "
                 f"neurotcs describe {args.file} --emit-mapping mapping.json")
            return EXIT_INPUT
        except json.JSONDecodeError as e:
            _err(f"mapping file is not valid JSON: {e}")
            return EXIT_INPUT

        mapping = _clean_mapping(mapping)
        if _has_placeholder(mapping):
            _err("mapping still contains <FILL:...> placeholders -- edit them before "
                 "auditing (the auditor will not guess column names).")
            return EXIT_INPUT

        # v1.40.3 (E-2026-013): explicit-mapping path ALSO auto-wires un-staged
        # sheets, just like the zero-config path. Before this fix, a user who
        # ran `describe --emit-mapping` got `ranges: []` and had to hand-author
        # the range specs from documentation; the assay packs (CSF/plasma/
        # centiloid/volumetrics/FDG) were unreachable for everyone except
        # operators who already knew the long-format spec. Now: any range spec
        # the user has hand-authored takes precedence (their explicit choices
        # are respected), and the autowire fills in the rest from un-staged
        # measurement sheets with the SAME fail-closed default + --confirm-assays
        # opt-in. This is the auditor's "make it universal in experience, never
        # in scope" lever applied to the explicit-mapping path.
        from neurotcs.io.autowire import autowire_ranges
        wired_sheets = _sheets_referenced_by_mapping(mapping)
        consumed_cols = _columns_consumed_by_mapping(mapping)
        rspecs, extra_tables, decisions, _refusals, _wired_src = autowire_ranges(
            tables, wired_sheets,
            confirm_assays=getattr(args, "confirm_assays", False),
            consumed_columns=consumed_cols)
        range_refusals.extend(_refusals)
        _autowired_source_sheets.update(_wired_src)
        if rspecs:
            tables.update(extra_tables)
            mapping.setdefault("ranges", []).extend(rspecs)
            if not args.quiet:
                print("# auto-wired range packs (values audited; "
                      "each decision shown):")
                for d in decisions:
                    print(f"  {d}")

    submission_warnings: list[str] = []
    try:
        submission = tables_to_submission(tables, mapping, warnings=submission_warnings)
    except (ValueError, KeyError) as e:
        _err(f"mapping does not match the data: {e}")
        return EXIT_INPUT

    # v1.71.0: detect a per-visit TREATMENT / TRAC column and expose it as
    # submission["treatment_status_col"] so the staging layer can carry per-visit
    # treatment context (schema v1.2+ conditional admissibility, e.g. the TRAC
    # carve-out on ad/niaaa_2024_biological_letter: a backward biological-stage
    # step is admissible only on a row whose treatment context == "TRAC").
    # Detection is conservative and additive: if no such column is present, the
    # key is absent and behavior is byte-identical to before. The engine context
    # channel is the literal field `treatment_status`; rows whose value is the
    # TRAC marker are normalized to the literal "TRAC" the pack matches on, all
    # other values pass through unchanged (so untreated rows fail the carve-out
    # and a genuine regression is still flagged).
    _tx_col = _detect_treatment_status_col(submission)
    if _tx_col is not None:
        submission["treatment_status_col"] = _tx_col

    # v1.59.0 (opt-in, --normalize-labels): map raw clinical-stage labels to the
    # canonical CN/SMC/EMCI/LMCI/MCI/AD vocabulary via the citation-anchored
    # subject-label synonym ontology, so a dataset that writes "cognitively
    # normal"/"early MCI"/"Alzheimer's dementia" audits against the clinical
    # staging packs instead of being read as contamination. SYNONYMS ONLY: it
    # never collapses distinct categories; unrecognized tokens pass through
    # unchanged. Applies ONLY to the clinical axis (the biological A/T/N
    # vocabulary is a different ontology not covered here). Every substitution is
    # recorded in the bundle. Default OFF -> existing runs are byte-identical.
    if getattr(args, "normalize_labels", False):
        from neurotcs.orchestration.label_normalization import (
            load_label_ontology,
            normalize_labels,
        )
        _ont = load_label_ontology()
        _clin = submission.get("clinical")
        if _clin is not None and "state" in getattr(_clin, "columns", []):
            _res = normalize_labels(list(_clin["state"]), _ont)
            _clin = _clin.copy()
            _clin["state"] = _res.normalized
            submission["clinical"] = _clin
            if not args.quiet and _res.mapping:
                print("# label normalization (--normalize-labels), clinical axis:")
                for raw, canon in sorted(_res.mapping.items()):
                    print(f"  {raw!r} -> {canon}")
            if _res.mapping:
                _subs = "; ".join(f"{raw}->{canon}"
                                  for raw, canon in sorted(_res.mapping.items()))
                submission_warnings.append(
                    f"label_normalization: clinical-stage labels normalized via "
                    f"{_res.ontology_id} (sha256 {_res.ontology_sha256[:12]}): "
                    f"{_subs}")

        # v1.60.0: biological A/T/N notation normalization (same opt-in flag).
        # Re-express prose / separator-variant AT(N) profiles ("amyloid positive
        # tau negative", "A+/T-/N+") as the canonical profile strings the
        # biological packs consume (A+T-N+ etc.), VERIFIED against the packs'
        # state sets so a reassembled profile is never invented. Applies to the
        # biological axis only; clinical axis handled above.
        from neurotcs.orchestration.atn_normalization import (
            load_atn_ontology,
            normalize_atn_labels,
        )
        from neurotcs.rulepack.loader import load_rulepack as _load_rp
        _bio = submission.get("biological")
        if _bio is not None and "state" in getattr(_bio, "columns", []):
            _valid: set[str] = set()
            for _bp in ("ad/atn_2018", "ad/at_biological"):
                try:
                    _valid |= {s.name for s in
                               _load_rp(_bp).rulepack.state_space}
                except Exception:  # noqa: BLE001 - missing pack must not break audit
                    pass
            if _valid:
                _aont = load_atn_ontology()
                _ares = normalize_atn_labels(list(_bio["state"]), _valid, _aont)
                _bio = _bio.copy()
                _bio["state"] = _ares.normalized
                submission["biological"] = _bio
                if not args.quiet and _ares.mapping:
                    print("# label normalization (--normalize-labels), "
                          "biological A/T/N axis:")
                    for raw, canon in sorted(_ares.mapping.items()):
                        print(f"  {raw!r} -> {canon}")
                if _ares.mapping:
                    _bsubs = "; ".join(f"{raw}->{canon}"
                                       for raw, canon in sorted(_ares.mapping.items()))
                    submission_warnings.append(
                        f"label_normalization: biological A/T/N labels normalized "
                        f"via {_ares.ontology_id} "
                        f"(sha256 {_ares.ontology_sha256[:12]}): {_bsubs}")

    # v1.42.0: AUTO-WIRE the Layer-3b cross-sheet coherence audit. Before this,
    # the cross-sheet layer never ran in zero-config (nothing populated
    # submission["cross_sheet"]), silently disabling ~1/5 of the auditor's
    # detection power (cross-modal conflicts, longitudinal monotonicity
    # reversals, genotype/phenotype coherence). The resolver maps raw cohort
    # sheets -> abstract roles deterministically and fail-closed; unresolved
    # sheets are surfaced, never force-fit. Only PRODUCTION invariant packs run
    # by default (research_preview packs require explicit opt-in).
    try:
        from neurotcs.cross_sheet.loader import list_invariantpacks
        from neurotcs.io.cross_sheet_autowire import build_cross_sheet_submission

        cs_sub, cs_res = build_cross_sheet_submission(_original_tables)
        # A cross-sheet audit is meaningful only with a data role view present
        # (predictions / patients / biomarkers) to relate; absent that there is
        # nothing to cross-check.
        data_role_views = [r for r in ("predictions", "patients", "biomarkers")
                           if r in cs_sub and cs_sub[r]]
        if len(data_role_views) >= 1 and ("biomarkers" in cs_sub or "predictions" in cs_sub):
            prod_pack_names = [p["name"] for p in list_invariantpacks()
                               if p.get("status") == "production"]
            if prod_pack_names:
                submission["cross_sheet"] = (cs_sub, prod_pack_names)
        # Surface role resolution (which sheet -> which role; what was unresolved)
        for line in cs_res.summary_lines():
            submission_warnings.append(line)
    except Exception as e:  # never let auto-wiring break the core audit
        submission_warnings.append(
            f"cross_sheet auto-wiring skipped (non-fatal): {type(e).__name__}: {e}")

    # v1.42.0: AUTO-WIRE the Layer-1 data-integrity audit. Runs universal,
    # deterministic, fail-closed structural checks over the ORIGINAL raw sheets
    # (categorical-domain validity, APOE genotype validity, hard patient-level
    # bounds, duplicate records, orphan records, intra-subject temporal cadence
    # breaks). Before this, none of these error classes were reachable in
    # zero-config because the patient-level enrollment sheet has no visit axis
    # and the visit-keyed range/staging layers never touched it.
    try:
        from neurotcs.io.data_integrity import audit_data_integrity
        di_flags = audit_data_integrity(_original_tables)
        if di_flags:
            submission["data_integrity"] = di_flags
    except Exception as e:  # never let integrity wiring break the core audit
        submission_warnings.append(
            f"data_integrity auto-wiring skipped (non-fatal): {type(e).__name__}: {e}")

    # v1.38/v1.39: surface any non-silent fallback (e.g. derived visit_date) to
    # the user BEFORE running the audit. --allow-no-dates acknowledges explicitly
    # (suppresses the per-axis stderr NOTE); the bundle records it either way.
    if submission_warnings and not getattr(args, "allow_no_dates", False):
        for w in submission_warnings:
            _note(f"NOTE: {w}")
        # v1.79.x: only advise --allow-no-dates when a date was actually
        # DERIVED; the flag has no effect on other warning types, so
        # printing it for label/coverage/partition notes is misleading.
        if any("DERIVED from visit ordering" in w
               for w in submission_warnings):
            _err("Pass --allow-no-dates to acknowledge derived dates "
                 "explicitly and suppress this note.")

    # v1.39: --dry-run resolves the mapping and reports what WOULD be audited,
    # then exits without running the audit. Lets a user verify routing first.
    if getattr(args, "dry_run", False):
        print("# dry-run: resolved mapping (no audit executed)")
        for axis in ("clinical", "biological"):
            if axis in submission:
                df = submission[axis]
                print(f"  {axis}: {len(df)} rows, "
                      f"{df['subject_id'].nunique()} subjects, "
                      f"states={sorted(df['state'].astype(str).unique())}")
        if "ranges" in submission:
            print(f"  ranges: {len(submission['ranges'])} pack(s)")
        for w in submission_warnings:
            print(f"  NOTE: {w}")
        print("dry-run OK -- re-run without --dry-run to produce the audit bundle.")
        return EXIT_CLEAN

    # Declare the layers the CLI expects to have offered, so the orchestrator's
    # structural completeness guard refuses on a silent wiring omission (the
    # circular-completeness hole). We expect every layer for which supporting
    # input is present in the submission.
    _expected = [name for name, key in (
        ("staging_clinical", "clinical"),
        ("staging_biological", "biological"),
        ("ranges", "ranges"),
        ("cross_sheet", "cross_sheet"),
        ("data_integrity", "data_integrity"),
    ) if submission.get(key) is not None]

    # v1.58.0: machine-readable column-coverage ledger. All inputs are known
    # here (resolved mapping incl. autowired ranges, full sheet/column inventory,
    # refusals) BEFORE the audit, so the bundle records exactly which columns were
    # consumed / refused (with reason) / left un-wired -- the same coverage the
    # CLI prints to stderr, now in the artifact a regulator reads.
    _ledger = _column_coverage_ledger(
        tables, mapping, _autowired_source_sheets, range_refusals)
    submission["columns_present"] = _ledger["columns_present"]
    submission["columns_consumed"] = _ledger["columns_consumed"]
    submission["columns_refused"] = _ledger["columns_refused"]
    submission["columns_unwired"] = _ledger["columns_unwired"]

    # v1.61.0 (opt-in, --partition-disease-controls): recognize non-AD dementia /
    # mimic labels and record those subjects as out-of-AD-scope (scope-honest),
    # citation-anchored. Recognition only; never relabels to an AD stage.
    if getattr(args, "partition_disease_controls", False):
        from neurotcs.orchestration.disease_control import (
            load_disease_control_ontology,
            recognize_disease_controls,
        )
        _clin_dc = submission.get("clinical")
        if _clin_dc is not None and "state" in getattr(_clin_dc, "columns", []):
            _dc_ont = load_disease_control_ontology()
            _pairs = list(zip(_clin_dc["subject_id"].astype(str),
                              _clin_dc["state"].astype(str), strict=True))
            _dc = recognize_disease_controls(_pairs, _dc_ont)
            if _dc.recognized:
                if not args.quiet:
                    print("# disease-control partition "
                          "(--partition-disease-controls): non-AD subjects "
                          "recorded out-of-AD-scope:")
                    for _cat, _subs in sorted(_dc.by_category.items()):
                        print(f"  {_cat}: {len(_subs)} subject(s)")
                _summary = "; ".join(f"{c}={len(s)}"
                                     for c, s in sorted(_dc.by_category.items()))
                submission_warnings.append(
                    f"disease_control_partition: {len(_dc.recognized)} subject(s) "
                    f"recognized as non-AD via {_dc.ontology_id} "
                    f"(sha256 {_dc.ontology_sha256[:12]}): {_summary}")

    # v1.61.0 (opt-in, --audit-conversions): advisory longitudinal conversion /
    # reversion audit over the canonical clinical-stage sequence.
    _conversion_result = None
    if getattr(args, "audit_conversions", False):
        from neurotcs.orchestration.conversion_audit import audit_conversions
        _clin_cv = submission.get("clinical")
        if _clin_cv is not None and {"subject_id", "visit", "state"} <= set(
                getattr(_clin_cv, "columns", [])):
            _rows = list(zip(_clin_cv["subject_id"].astype(str),
                             _clin_cv["visit"],
                             _clin_cv["state"].astype(str), strict=True))
            _conversion_result = audit_conversions(_rows)
            _cv = _conversion_result
            if _cv.flags:
                if not args.quiet:
                    print("# conversion audit (--audit-conversions): "
                          f"{_cv.n_transitions} transition(s), severity "
                          f"impossible {_cv.severity_counts.get('impossible', 0)} "
                          f"/ implausible {_cv.severity_counts.get('implausible', 0)} "
                          f"/ informational "
                          f"{_cv.severity_counts.get('informational', 0)}")
                    for _f in _cv.flags:
                        if _f.tier in ("impossible", "implausible"):
                            print(f"  [{_f.tier}] {_f.subject_id}: "
                                  f"{_f.from_state}->{_f.to_state} ({_f.reason})")
                _impl = sum(1 for _f in _cv.flags
                            if _f.tier in ("impossible", "implausible"))
                submission_warnings.append(
                    f"conversion_audit: {_cv.n_transitions} transition(s), "
                    f"{_impl} implausible/impossible flagged (advisory)")

    # v1.63.0 (opt-in, --recognize-aria-grades COLUMN): recognize ARIA severity
    # labels from a named clinical column -> canonical (type, grade), anchored to
    # van Etten 2026 + ASNR. Recognition only; numeric boundaries live in the
    # ad/aria_safety range pack. Unrecognized/ambiguous labels pass through.
    _aria_col = getattr(args, "recognize_aria_grades", None)
    if _aria_col:
        from neurotcs.orchestration.aria_grade import (
            load_aria_grade_ontology,
            recognize_aria_grades,
        )
        # Scan the RAW ingested tables (not the projected clinical submission,
        # which keeps only the canonical staging columns) for the named ARIA
        # column alongside a subject_id column.
        _ar_pairs: list[tuple[str, str]] = []
        for _sheet, _df in tables.items():
            _cols = list(getattr(_df, "columns", []))
            if _aria_col in _cols and "subject_id" in _cols:
                _ar_pairs.extend(zip(_df["subject_id"].astype(str),
                                     _df[_aria_col].astype(str), strict=True))
        if _ar_pairs:
            _ar_ont = load_aria_grade_ontology()
            _ar = recognize_aria_grades(_ar_pairs, _ar_ont)
            if _ar.recognized:
                if not args.quiet:
                    print("# ARIA grade recognition "
                          f"(--recognize-aria-grades {_aria_col}): "
                          f"{len(_ar.recognized)} subject(s) recognized:")
                    for _ty, _subs in sorted(_ar.by_type.items()):
                        print(f"  {_ty}: {len(_subs)} subject(s)")
                _ar_summary = "; ".join(f"{t}={len(s)}"
                                        for t, s in sorted(_ar.by_type.items()))
                submission_warnings.append(
                    f"aria_grade_recognition: {len(_ar.recognized)} subject(s) "
                    f"recognized via {_ar.ontology_id} "
                    f"(sha256 {_ar.ontology_sha256[:12]}): {_ar_summary}")
        elif not args.quiet:
            print(f"# ARIA grade recognition: column {_aria_col!r} (with "
                  "subject_id) not found in any sheet; nothing recognized.")

    result = run_full_audit(submission, expected_layers=_expected)

    # v1.39.3: UNIFIED COVERAGE HONESTY. NeuroTCS must never present a confident
    # audit while leaving part of the input un-audited and undeclared. There are
    # exactly two ways a slice of the input fails to get a real audit:
    #   (1) un-wired sheets   -- present in the file but no pack was attached
    #                            (e.g. zero-config wires only the staging axes);
    #   (2) skipped layers    -- a wired axis the engine then refused, e.g. a
    #                            staging vocabulary that matches no rule pack
    #                            (fail-closed: a score on mismatched vocab is not
    #                            a meaningful number).
    # Both are collected into ONE coverage statement, printed loudly and recorded
    # in the bundle, so a single line tells the user everything that did NOT get a
    # real audit. Domain-free: it reasons only about sheets/layers, never disease.
    referenced = _sheets_referenced_by_mapping(mapping)
    unaudited_sheets = [
        s for s in tables
        if s not in referenced
        and s not in _autowired_source_sheets
        and not s.startswith("__autowired__")
        and not _is_toc_sheet(s, {"columns": list(tables[s].columns)})
    ]
    skipped_layers = dict(getattr(result.manifest, "layers_skipped", {}) or {})
    if unaudited_sheets or skipped_layers or range_refusals:
        parts = ["coverage: not all input was audited."]
        if unaudited_sheets:
            parts.append(
                f"Un-wired sheet(s) (no pack attached, values NOT examined): "
                f"{unaudited_sheets}."
            )
        for layer, reason in sorted(skipped_layers.items()):
            short = reason.split(":")[0] if ":" in reason else reason
            parts.append(
                f"Wired-but-skipped layer '{layer}' ({short}) -- no score emitted."
            )
        for rr in range_refusals:
            parts.append(f"Column NOT wired: {rr}")
        parts.append(
            "To audit un-wired sheets add 'ranges' entries to a mapping "
            "(`neurotcs describe ... --emit-mapping`); skipped layers need a rule "
            "pack whose vocabulary matches the data."
        )
        msg = " ".join(parts)
        submission_warnings.append(msg)
        _err(f"COVERAGE: {msg}")

    try:
        from pathlib import Path as _P
        _fp_path = _P(args.file)
        if _fp_path.is_file() and _fp_path.suffix.lower() not in (".zip",):
            # single regular file -> raw-bytes fingerprint ("same file")
            fp = fingerprint_file(args.file)
            fp_kind = "raw_file_sha256"
        else:
            # directory / glob / zip / multi-file cohort -> fingerprint the
            # NORMALIZED loaded tables ("same logical input"), since there is no
            # single file to hash. Deterministic: sort tables by name, hash each.
            import hashlib as _hashlib
            _h = _hashlib.sha256()
            for _name in sorted(tables.keys()):
                _h.update(_name.encode("utf-8"))
                _h.update(fingerprint_dataframe(tables[_name]).encode("utf-8"))
            fp = _h.hexdigest()
            fp_kind = "normalized_data_sha256"
        bundle = build_bundle(result, input_fingerprint=fp,
                              input_fingerprint_kind=fp_kind,
                              input_warnings=submission_warnings)
    except Exception as e:  # noqa: BLE001 - surface any build failure cleanly
        _err(f"failed to build bundle: {e}")
        return EXIT_INPUT

    # always write the fingerprinted artifact of record + the text report
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.file).stem
    (outdir / f"{stem}.bundle.json").write_text(
        json.dumps(bundle, indent=2), encoding="utf-8")
    (outdir / f"{stem}.report.txt").write_text(
        render_report(bundle, use_symbols=True), encoding="utf-8")
    if args.csv:
        (outdir / f"{stem}.flags.csv").write_text(flags_to_csv(bundle), encoding="utf-8")
    if args.svg:
        (outdir / f"{stem}.summary.svg").write_text(bundle_to_svg(bundle), encoding="utf-8")
    if args.pdf:
        bundle_to_pdf(bundle, outdir / f"{stem}.report.pdf")

    core = bundle["neurotcs_bundle"]["deterministic_core"]
    status = core.get("status", "UNKNOWN")
    if not args.quiet:
        _print_summary(bundle, outdir, stem, args)

    if status == "INCOMPLETE_REFUSED":
        return EXIT_REFUSED
    if status == "FLAGS_PRESENT":
        return EXIT_FLAGS
    return EXIT_CLEAN


def _print_summary(bundle: dict[str, Any], outdir: Path, stem: str,
                   args: argparse.Namespace) -> None:
    core = bundle["neurotcs_bundle"]["deterministic_core"]
    sev = core.get("severity_counts", {})
    print(f"status: {core.get('status')}")
    for ax in core.get("axes", []):
        lo, hi = ax.get("ctcs_ci_95_low"), ax.get("ctcs_ci_95_high")
        ci = f" [95% CI {lo}-{hi}]" if lo is not None and hi is not None else ""
        print(f"  {ax['axis']}: cTCS {ax['ctcs']}{ci}  "
              f"({ax['n_flagged']}/{ax['n_transitions']} flagged)")
    print(f"severity: impossible {sev.get('impossible', 0)} / "
          f"implausible {sev.get('implausible', 0)} / "
          f"informational {sev.get('informational', 0)}")
    print(f"bundle:   {outdir / (stem + '.bundle.json')}")
    print(f"report:   {outdir / (stem + '.report.txt')}")
    if args.csv:
        print(f"flags:    {outdir / (stem + '.flags.csv')}")
    if args.svg:
        print(f"svg:      {outdir / (stem + '.summary.svg')}")
    if args.pdf:
        print(f"pdf:      {outdir / (stem + '.report.pdf')}")


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
def _resolve_bundle_path(target: str) -> Path | None:
    """Resolve a verify target to a bundle JSON file.

    v1.39.1: `neurotcs verify` accepts EITHER a bundle file OR the audit output
    DIRECTORY (the natural workflow: `neurotcs audit ... -o out` then
    `neurotcs verify out`). Given a directory, locate the single *.bundle.json
    inside it. Previously, passing a directory crashed with an uncaught
    IsADirectoryError -- breaking the third leg of describe -> audit -> verify.
    """
    p = Path(target)
    if p.is_dir():
        candidates = sorted(p.glob("*.bundle.json"))
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) == 0:
            _err(f"no '*.bundle.json' found in directory: {target}. Run "
                 f"`neurotcs audit <file> --mapping <map> -o {target}` first.")
            return None
        _err(f"multiple bundles found in {target}: "
             f"{[c.name for c in candidates]}. Pass the specific bundle file, "
             f"e.g. `neurotcs verify {candidates[0]}`.")
        return None
    return p


def cmd_verify(args: argparse.Namespace) -> int:
    bundle_path = _resolve_bundle_path(args.bundle)
    if bundle_path is None:
        return EXIT_INPUT
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _err(f"bundle not found: {bundle_path}")
        return EXIT_INPUT
    except IsADirectoryError:
        _err(f"expected a bundle file but got a directory: {bundle_path}")
        return EXIT_INPUT
    except json.JSONDecodeError as e:
        _err(f"bundle is not valid JSON: {e}")
        return EXIT_INPUT
    try:
        ok = verify_bundle(bundle)
    except BundleVerificationError as e:
        print(f"VERIFY FAILED: {e}")
        return EXIT_VERIFY
    except (KeyError, TypeError) as e:
        _err(f"not a NeuroTCS bundle: {e}")
        return EXIT_VERIFY
    if ok:
        bid = bundle["neurotcs_bundle"].get("bundle_id", "")
        print(f"VERIFIED OK  bundle_id {str(bid)[:24]}...")
        return EXIT_CLEAN
    print("VERIFY FAILED")
    return EXIT_VERIFY


def cmd_validate_coverage(args: argparse.Namespace) -> int:
    """Arm B coverage measurement: inject a realistic error taxonomy into a
    CLEAN cohort and report rule-set detection coverage with CIs.

    HONEST: this measures COVERAGE of a realistic error distribution, not
    accuracy, and does not substitute for Arm A expert adjudication. See
    docs/VALIDATION_PROTOCOL.md.
    """
    import json as _json
    import tempfile as _tempfile
    from pathlib import Path as _Path

    from neurotcs.validation import (
        ErrorType,
        InjectionSpec,
        inject_errors,
        run_audit_flags,
        score_detection,
    )

    spec = InjectionSpec(counts={
        ErrorType.IMPLAUSIBLE_HIGH: args.n_high,
        ErrorType.UNIT_ERROR: args.n_unit,
        ErrorType.DECIMAL_SHIFT: args.n_decimal,
        ErrorType.SIGN_FLIP: args.n_sign,
        ErrorType.CATEGORICAL_INVALID: args.n_categorical,
    })
    with _tempfile.TemporaryDirectory() as td:
        corrupt = _Path(td) / "corrupt.xlsx"
        try:
            manifest = inject_errors(args.cohort, spec, args.seed, corrupt)
        except (ValueError, FileNotFoundError) as e:
            _err(str(e))
            return EXIT_INPUT
        flags = run_audit_flags(str(corrupt))
        report = score_detection(manifest, flags)

    payload = report.to_dict()
    payload["seed"] = args.seed
    payload["cohort"] = str(args.cohort)

    cov = report.overall_coverage
    lo, hi = report.overall_coverage_ci
    print("NeuroTCS Arm B coverage (NOT accuracy; see VALIDATION_PROTOCOL.md)")
    print(f"  injected: {report.total_injected}  detected: {report.total_detected}")
    print(f"  overall coverage: {cov:.3f}  95% CI [{lo:.3f}, {hi:.3f}]")
    sp = report.specificity
    slo, shi = report.specificity_ci
    print(f"  specificity (clean coords): {sp:.4f}  95% CI [{slo:.4f}, {shi:.4f}]")
    for r in report.per_type:
        clo, chi = r.coverage_ci
        print(f"    {str(r.error_type):20} {r.detected:>3}/{r.injected:<3} "
              f"coverage={r.coverage:.2f} CI[{clo:.2f},{chi:.2f}]")

    if args.out:
        _Path(args.out).write_text(_json.dumps(payload, indent=2))
        _note(f"NOTE: coverage report written to {args.out}")
    return EXIT_CLEAN


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="neurotcs",
        description="NeuroTCS - fail-closed clinical trajectory auditor.",
        epilog="For low-level single-axis audits with bootstrap/prior tuning, "
               "see the 'neurotcs-audit' command.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("describe", help="inspect a dataset file; scaffold a mapping")
    d.add_argument("file", help="dataset to audit: a single file (.csv/.tsv/.xlsx/.xls/.parquet/.json/.sas7bdat/.dta/.sav/.rds/.pdf), a FOLDER of such files, a glob, or a .zip/.gz archive")
    d.add_argument("--emit-mapping", metavar="PATH", default=None,
                   help="write a mapping template to PATH")
    d.add_argument("--allow-pdf", action="store_true",
                   help="enable best-effort PDF table extraction")
    d.add_argument("--encoding", default=None, metavar="CODEPAGE",
                   help="assert the text encoding of delimited files (e.g. cp1251 Cyrillic, cp1252 Western European). Default: UTF-8 only; a non-UTF-8 file is refused unless this is given.")
    d.set_defaults(func=cmd_describe)

    a = sub.add_parser("audit", help="audit a dataset and emit a fingerprinted bundle")
    a.add_argument("file", help="dataset to audit: a single file (.csv/.tsv/.xlsx/.xls/.parquet/.json/.sas7bdat/.dta/.sav/.rds/.pdf), a FOLDER of such files, a glob, or a .zip/.gz archive")
    a.add_argument("--mapping", default=None,
                   help="mapping JSON (see 'describe --emit-mapping'). OMIT to "
                        "auto-detect a mapping for conventional files (zero-config).")
    a.add_argument("-o", "--outdir", default="neurotcs_out", help="output directory")
    a.add_argument("--csv", action="store_true", help="also write flags CSV")
    a.add_argument("--svg", action="store_true", help="also write summary SVG")
    a.add_argument("--pdf", action="store_true", help="also write PDF report")
    a.add_argument("--quiet", action="store_true", help="suppress the stdout summary")
    a.add_argument("--allow-pdf", action="store_true",
                   help="enable best-effort PDF table extraction")
    a.add_argument("--encoding", default=None, metavar="CODEPAGE",
                   help="assert the text encoding of delimited files (e.g. cp1251 Cyrillic, cp1252 Western European). Default: UTF-8 only; a non-UTF-8 file is refused unless this is given.")
    a.add_argument("--allow-no-dates", action="store_true",
                   help="acknowledge derived visit_date explicitly (no date column "
                        "in data): use visit ordering, suppress the per-axis NOTE. "
                        "The bundle still records that dates were derived.")
    a.add_argument("--dry-run", action="store_true",
                   help="resolve the mapping and report what WOULD be audited, then "
                        "exit without producing a bundle (verify routing first)")
    a.add_argument("--refuse-phi", action="store_true",
                   help="fail closed if probable direct identifiers (PHI) "
                        "are detected in the input (default: warn only). "
                        "Best-effort; not a de-identification guarantee.")
    a.add_argument("--confirm-assays", action="store_true",
                   help="assert that assay/scale-calibrated biomarker columns "
                        "(CSF/plasma p-tau, NfL, centiloid, volumetry, FDG, ...) "
                        "were measured on the assay/scale the matched production "
                        "pack encodes, so the zero-config auditor wires them too. "
                        "Off by default (fail-closed): without this flag those "
                        "columns are refused, since a column name cannot certify "
                        "the assay. The assertion is recorded in the bundle.")
    a.add_argument("--normalize-labels", action="store_true",
                   help="normalize raw clinical-stage labels (e.g. 'cognitively "
                        "normal', 'CU', 'subjective memory complaint', 'early "
                        "MCI', \"Alzheimer's dementia\") to the canonical "
                        "vocabulary (CN/SMC/EMCI/LMCI/MCI/AD) via the "
                        "citation-anchored subject-label synonym ontology before "
                        "staging. Off by default. SYNONYMS ONLY -- never collapses "
                        "distinct categories; unrecognized tokens pass through "
                        "unchanged (still surface as contamination). Every "
                        "substitution is recorded in the bundle.")
    a.add_argument("--partition-disease-controls", action="store_true",
                   help="recognize non-AD dementia / mimic labels (vascular "
                        "dementia, DLB, PDD, bvFTD, PPA, iNPH, TES, autoimmune "
                        "encephalitis, mixed dementia, CBD, PSP, depression-"
                        "related cognitive impairment) via the citation-anchored "
                        "disease-control ontology, and record those subjects as "
                        "out-of-AD-scope (scope-honest) rather than forcing them "
                        "through AD staging. Recognition only -- never relabels "
                        "to an AD stage; unrecognized labels pass through. Off by "
                        "default; recorded in the bundle.")
    a.add_argument("--audit-conversions", action="store_true",
                   help="audit longitudinal clinical-stage conversions/reversions "
                        "(CN<SMC<EMCI<LMCI<MCI<AD). Forward progression is "
                        "expected; MCI->CN reversion is flagged as plausible "
                        "(documented, never rejected); AD reverting to a milder "
                        "stage is flagged implausible for data-quality review. "
                        "Advisory overlay reported alongside the audit; off by "
                        "default.")
    a.add_argument("--recognize-aria-grades", metavar="COLUMN", default=None,
                   help="recognize Amyloid-Related Imaging Abnormalities (ARIA) "
                        "severity labels from the named column of the clinical "
                        "table and resolve each to a canonical (type, grade) on "
                        "the {none, mild, moderate, severe} scheme for ARIA-E, "
                        "ARIA-H microhemorrhage, and ARIA-H siderosis "
                        "(macrohemorrhage recognized as a separate finding). "
                        "Anchored to the 2026 Alzheimer's Association ARIA "
                        "workgroup update (van Etten 2026) + ASNR consensus. "
                        "Recognition only; the numeric grade boundaries live in "
                        "the ad/aria_safety range pack. Unrecognized/ambiguous "
                        "labels pass through (never guessed). Off by default.")
    a.set_defaults(func=cmd_audit)

    v = sub.add_parser("verify", help="re-verify a fingerprinted bundle")
    v.add_argument("bundle",
                   help="path to a *.bundle.json file, OR the audit output "
                        "directory (the bundle inside it is located automatically)")
    v.set_defaults(func=cmd_verify)

    vc = sub.add_parser(
        "validate-coverage",
        help="Arm B: inject a realistic error taxonomy into a CLEAN cohort "
             "and measure rule-set detection coverage (NOT accuracy)")
    vc.add_argument("cohort", help="path to a CLEAN cohort workbook")
    vc.add_argument("-o", "--out", default=None,
                    help="path to write the coverage report JSON "
                         "(default: stdout only)")
    vc.add_argument("--seed", type=int, default=0,
                    help="injection seed (determinism)")
    vc.add_argument("--n-high", type=int, default=10,
                    help="number of implausible_high errors to inject")
    vc.add_argument("--n-unit", type=int, default=10,
                    help="number of unit_error errors to inject")
    vc.add_argument("--n-decimal", type=int, default=10,
                    help="number of decimal_shift errors to inject")
    vc.add_argument("--n-sign", type=int, default=5,
                    help="number of sign_flip errors to inject")
    vc.add_argument("--n-categorical", type=int, default=5,
                    help="number of categorical_invalid errors to inject")
    vc.set_defaults(func=cmd_validate_coverage)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

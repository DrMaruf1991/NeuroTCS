"""NeuroTCS command-line interface.

Verbs:
  describe <file> [--emit-mapping PATH]   inspect a dataset file; scaffold a mapping
  audit    <file> --mapping map.json ...  audit a dataset, emit a signed bundle
  verify   <bundle.json>                  re-verify a signed bundle (tamper check)

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
import sys
from pathlib import Path
from typing import Any

from neurotcs import (
    BundleVerificationError,
    build_bundle,
    fingerprint_file,
    render_report,
    run_full_audit,
    verify_bundle,
)
from neurotcs.io import (
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


def _load_tables(path: str, allow_pdf: bool) -> dict[str, Any] | None:
    try:
        return read_tables(path, allow_pdf=allow_pdf)
    except (FileNotFoundError, UnsupportedFormatError, PdfExtractionError) as e:
        _err(str(e))
        return None


# --------------------------------------------------------------------------- #
# describe
# --------------------------------------------------------------------------- #
def cmd_describe(args: argparse.Namespace) -> int:
    tables = _load_tables(args.file, args.allow_pdf)
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


def _best_column(cols: list[str], synonyms: tuple[tuple[str, int], ...],
                 fallback_canonical: str, return_none_on_miss: bool = False) -> str | None:
    """Find the highest-scoring synonym that's present in `cols` (case-insensitive).

    Returns the actual column name from `cols` (original case). If no synonym matches,
    returns either `<FILL:fallback_canonical>` or None (when `return_none_on_miss`)."""
    cols_lower_to_orig = {str(c).lower(): str(c) for c in cols}
    best_score = 0
    best_col: str | None = None
    for syn, score in synonyms:
        if syn.lower() in cols_lower_to_orig and score > best_score:
            best_score = score
            best_col = cols_lower_to_orig[syn.lower()]
    if best_col is not None:
        return best_col
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
    return {
        "sheet": sheet,
        "subject_id": _best_column(cols, _COL_SYN_SUBJECT_ID, "subject_id"),
        "visit":      _best_column(cols, _COL_SYN_VISIT, "visit"),
        # visit_date may be None -> consumer derives from visit order. Don't FILL.
        "visit_date": _best_column(cols, _COL_SYN_VISIT_DATE, "visit_date",
                                   return_none_on_miss=True),
        "state":      _best_column(cols, state_syns, "state"),
    }


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

    # 2. Pick best sheet per axis (avoid double-assignment of the same sheet)
    chosen_sheets: set[str] = set()
    for axis in ("clinical", "biological"):
        ranked = sorted(candidates[axis], reverse=True)  # (score, name, info)
        for score, name, info in ranked:
            if name in chosen_sheets:
                continue
            mapping[axis] = _build_axis_spec(name, info, axis)
            chosen_sheets.add(name)
            auto_routed.append(f"{axis}<-{name} (score {score})")
            break

    # 3. If neither axis got a name-pattern match, fall back to the first non-TOC
    #    sheet that ACTUALLY has recognizable staging fields (item 4 guard) as
    #    clinical. If no such sheet exists, leave <FILL:sheet>.
    if not auto_routed:
        fallback = next(
            ((n, i) for n, i in non_toc_sheets
             if _sheet_has_recognizable_staging_field(i)),
            None,
        )
        if fallback is not None:
            name, info = fallback
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


def cmd_audit(args: argparse.Namespace) -> int:
    tables = _load_tables(args.file, args.allow_pdf)
    range_refusals: list[str] = []
    _autowired_source_sheets: set[str] = set()
    if tables is None:
        return EXIT_INPUT

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
        rspecs, extra_tables, decisions, _refusals, _wired_src = autowire_ranges(
            tables, wired_sheets)
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

    submission_warnings: list[str] = []
    try:
        submission = tables_to_submission(tables, mapping, warnings=submission_warnings)
    except (ValueError, KeyError) as e:
        _err(f"mapping does not match the data: {e}")
        return EXIT_INPUT

    # v1.38/v1.39: surface any non-silent fallback (e.g. derived visit_date) to
    # the user BEFORE running the audit. --allow-no-dates acknowledges explicitly
    # (suppresses the per-axis stderr NOTE); the bundle records it either way.
    if submission_warnings and not getattr(args, "allow_no_dates", False):
        for w in submission_warnings:
            _err(f"NOTE: {w}")
        _err("Pass --allow-no-dates to acknowledge derived dates explicitly "
             "and suppress this note.")

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

    result = run_full_audit(submission)

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
        fp = fingerprint_file(args.file)
        bundle = build_bundle(result, input_fingerprint=fp,
                              input_fingerprint_kind="raw_file_sha256",
                              input_warnings=submission_warnings)
    except Exception as e:  # noqa: BLE001 - surface any build failure cleanly
        _err(f"failed to build bundle: {e}")
        return EXIT_INPUT

    # always write the signed artifact of record + the text report
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
    d.add_argument("file")
    d.add_argument("--emit-mapping", metavar="PATH", default=None,
                   help="write a mapping template to PATH")
    d.add_argument("--allow-pdf", action="store_true",
                   help="enable best-effort PDF table extraction")
    d.set_defaults(func=cmd_describe)

    a = sub.add_parser("audit", help="audit a dataset and emit a signed bundle")
    a.add_argument("file")
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
    a.add_argument("--allow-no-dates", action="store_true",
                   help="acknowledge derived visit_date explicitly (no date column "
                        "in data): use visit ordering, suppress the per-axis NOTE. "
                        "The bundle still records that dates were derived.")
    a.add_argument("--dry-run", action="store_true",
                   help="resolve the mapping and report what WOULD be audited, then "
                        "exit without producing a bundle (verify routing first)")
    a.set_defaults(func=cmd_audit)

    v = sub.add_parser("verify", help="re-verify a signed bundle")
    v.add_argument("bundle",
                   help="path to a *.bundle.json file, OR the audit output "
                        "directory (the bundle inside it is located automatically)")
    v.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

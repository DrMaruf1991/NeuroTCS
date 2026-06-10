"""neurotcs.io.cdisc -- CDISC SDTM / ADaM recognizer and normalizer.

WHAT THIS IS (and is NOT)
-------------------------
NeuroTCS audits AD trajectories. Pharma sponsors and CROs hand off data in the
CDISC submission format -- SDTM (tabulation) and ADaM (analysis-ready). This
module RECOGNIZES that structure and NORMALIZES it into the long format the rest
of NeuroTCS already speaks (subject_id / visit / visit_date / state, plus numeric
measurement columns), so a CDISC dataset can be dropped in directly. It then
flows through the existing typed-read contract (v1.47) and the partitioning
orchestrator (v1.46). NO new audit logic.

It is NOT a CDISC validator. define.xml parsing and full controlled-terminology
(CT) compliance checking are the job of dedicated industry tools (e.g.
Pinnacle 21); duplicating them would be scope-creep, not focus. NeuroTCS
recognizes structure to ingest it, and says so honestly in its provenance.

VERIFIED STRUCTURE (primary CDISC / NCI-EVS sources, checked 2026-06-01)
-----------------------------------------------------------------------
* Identity / timing (stable across CT versions):
    USUBJID                         -> subject_id   (unique per subject)
    VISITNUM (+ VISIT)              -> visit
    --DTC  (SDTM) / ADT (ADaM)      -> visit_date   (ISO 8601)
* Findings result quartet:
    SDTM:  --TESTCD / --ORRES / --STRESC / --STRESN   (keyed by --TESTCD)
    ADaM:  PARAMCD / AVALC / AVAL                      (keyed by PARAMCD)
  SDTM vs ADaM is auto-detected by variable presence (AVALC/PARAMCD => ADaM;
  --STRESC/--STRESN => SDTM).
* Diagnosis / clinical classification lives in the RS domain (SDTMIG v3.3
  "Disease Response and Clin Classification"); cognitive scales (ADAS-Cog,
  MMSE, CDR, NPI, MoCA) are QS instruments = NUMERIC measurements.

RECOGNITION BY STRUCTURAL ROLE (not fragile C-codes)
----------------------------------------------------
CDISC CT is versioned (current SDTM CT 2026-03-27, NCI-EVS), so instrument
C-codes drift. This recognizer keys on the STABLE structural role:
  * a code recognized as a COGNITIVE-SCALE INSTRUMENT (small verified name
    registry below) -> NUMERIC measurement (routes to a range pack);
  * a code in the RS domain, or recognized as a DIAGNOSIS / GLOBAL CLINICAL
    CLASSIFICATION -> candidate clinical `state`;
  * anything else -> FAIL CLOSED: the available codes are listed and the
    operator must select which carries the state (never guessed).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

# --------------------------------------------------------------------------- #
# Verified cognitive-scale instrument recognition (TESTCD/PARAMCD prefixes).
# These identify NUMERIC measurement instruments (route to range packs), NOT
# the clinical state axis. Names verified against CDISC QS/QRS CT (NCI-EVS).
# Matching is by normalized token / known synonym, robust to CT version drift.
# --------------------------------------------------------------------------- #
_COGNITIVE_SCALE_TOKENS: frozenset[str] = frozenset({
    "mmse",        # Mini-Mental State Examination
    "moca",        # Montreal Cognitive Assessment
    "adas", "adascog", "adascg",   # ADAS-Cog (CDISC C100131)
    "cdr", "cdrsb", "cdrglob", "cdrsob",  # Clinical Dementia Rating (+ sum of boxes)
    "npi", "npiq",  # Neuropsychiatric Inventory
    "iadrs", "adcs", "adcsadl", "adl",    # ADCS-ADL / iADRS
    "faq",         # Functional Activities Questionnaire
    "gds",         # Geriatric Depression Scale
    "mbi",         # Mild Behavioral Impairment
})

# Tokens that signal a DIAGNOSIS / GLOBAL CLINICAL CLASSIFICATION result
# (candidate `state` axis). RS domain is the strongest signal; these augment it
# for QS/custom domains that carry a global classification.
_DIAGNOSIS_TOKENS: frozenset[str] = frozenset({
    "dx", "diag", "diagnosis", "dxdecod", "mhdecod",
    "cogstat", "cognitivestatus", "clinstat", "clinicalstatus",
    "globalstage", "stage", "adstage", "researchgroup", "rg",
    "cdrglobal",  # CDR-Global is sometimes used AS the staging axis (0/0.5/1/2/3)
})

# SDTM/ADaM identity & timing variable names (case-insensitive).
_USUBJID = ("usubjid",)
_SUBJID = ("subjid",)
_VISITNUM = ("visitnum",)
_VISIT = ("visit",)
_SDTM_DTC_RE = re.compile(r"^[a-z]{2}dtc$|^dtc$", re.IGNORECASE)  # e.g. QSDTC, RSDTC
_ADAM_DATE = ("adt", "adtm")

# Findings result variables.
_SDTM_TESTCD_RE = re.compile(r"^[a-z]{2}testcd$", re.IGNORECASE)   # QSTESTCD, RSTESTCD
_SDTM_STRESC_RE = re.compile(r"^[a-z]{2}stresc$", re.IGNORECASE)
_SDTM_STRESN_RE = re.compile(r"^[a-z]{2}stresn$", re.IGNORECASE)
_SDTM_ORRES_RE = re.compile(r"^[a-z]{2}orres$", re.IGNORECASE)
_ADAM_PARAMCD = ("paramcd",)
_ADAM_AVALC = ("avalc",)
_ADAM_AVAL = ("aval",)
_DOMAIN = ("domain",)


class CdiscMappingError(ValueError):
    """Raised when CDISC structure is recognized but the state code is
    ambiguous and the operator has not selected one (fail-closed)."""


@dataclass
class CdiscRecognition:
    """Result of inspecting a table for CDISC structure."""

    is_cdisc: bool
    model: str | None = None              # "SDTM" | "ADaM" | None
    domain: str | None = None             # e.g. "QS", "RS", "DM"
    subject_col: str | None = None
    visit_col: str | None = None
    date_col: str | None = None
    testcd_col: str | None = None         # --TESTCD or PARAMCD
    resultc_col: str | None = None        # --STRESC or AVALC
    resultn_col: str | None = None        # --STRESN or AVAL
    orres_col: str | None = None          # --ORRES (SDTM only)
    available_codes: tuple[str, ...] = ()
    state_codes: tuple[str, ...] = ()     # codes recognized as diagnosis/state
    measurement_codes: tuple[str, ...] = ()  # codes recognized as numeric scales
    unknown_codes: tuple[str, ...] = ()   # neither -> fail-closed selection
    notes: list[str] = field(default_factory=list)


def _cols_lower(df: pd.DataFrame) -> dict[str, str]:
    """Map lowercased column name -> actual column name."""
    return {str(c).lower(): str(c) for c in df.columns}


def _norm(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(tok).lower())


def _find(cols: dict[str, str], names: tuple[str, ...]) -> str | None:
    for n in names:
        if n in cols:
            return cols[n]
    return None


def _find_re(cols: dict[str, str], rx: re.Pattern) -> str | None:
    for low, actual in cols.items():
        if rx.match(low):
            return actual
    return None


def _classify_code(code: str) -> str:
    """Classify a TESTCD/PARAMCD value by structural role.

    Returns 'measurement' | 'state' | 'unknown'.
    """
    n = _norm(code)
    # cognitive-scale instruments (and their item/total variants) -> measurement
    for tok in _COGNITIVE_SCALE_TOKENS:
        if n == tok or n.startswith(tok):
            # CDR-Global as a staging axis is the one overlap; handled below.
            if tok == "cdr" and n in ("cdrglob", "cdrglobal"):
                return "state"
            return "measurement"
    # diagnosis / global classification -> state
    for tok in _DIAGNOSIS_TOKENS:
        if n == tok or n.startswith(tok):
            return "state"
    return "unknown"


def recognize_cdisc(df: pd.DataFrame) -> CdiscRecognition:
    """Inspect a table for CDISC SDTM/ADaM structure. Pure inspection; no
    mutation. Detection is conservative: requires a subject key plus either a
    DOMAIN column or a recognizable findings/identity signature."""
    cols = _cols_lower(df)

    subject = _find(cols, _USUBJID) or _find(cols, _SUBJID)
    if subject is None:
        return CdiscRecognition(is_cdisc=False)

    # ADaM signature: PARAMCD + AVAL/AVALC. SDTM signature: --TESTCD + --STRES*.
    paramcd = _find(cols, _ADAM_PARAMCD)
    avalc = _find(cols, _ADAM_AVALC)
    aval = _find(cols, _ADAM_AVAL)
    testcd = _find_re(cols, _SDTM_TESTCD_RE)
    stresc = _find_re(cols, _SDTM_STRESC_RE)
    stresn = _find_re(cols, _SDTM_STRESN_RE)
    orres = _find_re(cols, _SDTM_ORRES_RE)
    domain_col = _find(cols, _DOMAIN)

    model: str | None = None
    code_col = resc = resn = orr = None
    if paramcd is not None and (aval is not None or avalc is not None):
        model = "ADaM"
        code_col, resc, resn = paramcd, avalc, aval
    elif testcd is not None and (stresc is not None or stresn is not None
                                 or orres is not None):
        model = "SDTM"
        code_col, resc, resn, orr = testcd, stresc, stresn, orres
    else:
        # DM-style subject-level table (no findings quartet) is CDISC but carries
        # no trajectory state; recognize it (so the reader can report) but mark
        # it as having no findings.
        if domain_col is not None or _find(cols, ("age",)) and _find(cols, ("sex",)):
            rec = CdiscRecognition(
                is_cdisc=True, model="SDTM",
                domain=(str(df[domain_col].iloc[0]) if domain_col is not None
                        and len(df) else "DM"),
                subject_col=subject)
            rec.notes.append(
                "CDISC subject-level table recognized (no findings quartet; "
                "carries no trajectory state to audit).")
            return rec
        return CdiscRecognition(is_cdisc=False)

    visit = _find(cols, _VISITNUM) or _find(cols, _VISIT)
    date = (_find_re(cols, _SDTM_DTC_RE) if model == "SDTM"
            else _find(cols, _ADAM_DATE))
    domain = (str(df[domain_col].iloc[0]) if domain_col is not None and len(df)
              else None)

    codes = tuple(sorted({str(v) for v in df[code_col].dropna().tolist()}))
    state_c: list[str] = []
    meas_c: list[str] = []
    unk_c: list[str] = []
    for c in codes:
        # RS domain is itself a strong "state" signal regardless of code token.
        role = _classify_code(c)
        if role == "unknown" and (domain or "").upper() == "RS":
            role = "state"
        (state_c if role == "state" else
         meas_c if role == "measurement" else unk_c).append(c)

    rec = CdiscRecognition(
        is_cdisc=True, model=model, domain=domain,
        subject_col=subject, visit_col=visit, date_col=date,
        testcd_col=code_col, resultc_col=resc, resultn_col=resn, orres_col=orr,
        available_codes=codes,
        state_codes=tuple(state_c), measurement_codes=tuple(meas_c),
        unknown_codes=tuple(unk_c))
    rec.notes.append(
        f"CDISC {model} findings table recognized (domain={domain or 'unknown'}; "
        f"keyed by {code_col!r}). NeuroTCS recognizes CDISC structure for "
        "ingestion; it is not a CDISC validator (use Pinnacle 21 for "
        "define.xml / CT-compliance checks). CT is versioned -- recognition is "
        "by structural role, not fixed C-codes.")
    return rec


def normalize_cdisc_to_long(
    df: pd.DataFrame,
    rec: CdiscRecognition,
    decisions: list[str],
    *,
    state_code: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Normalize a recognized CDISC findings table into NeuroTCS long format.

    Returns a dict possibly containing:
      "clinical": DataFrame[subject_id, visit, visit_date, state]
      "measurements": DataFrame[subject_id, visit, visit_date, <code columns>]
        (a wide table of numeric scales, for range-pack auditing)

    State-code selection (fail-closed):
      * If exactly one recognized state code exists, it is used and surfaced.
      * If several exist, or none but unknown codes are present, the operator
        MUST pass `state_code` (one of rec.available_codes). Otherwise
        CdiscMappingError is raised listing the choices -- never guessed.
    """
    if not rec.is_cdisc or rec.testcd_col is None:
        raise CdiscMappingError("table is not a recognized CDISC findings table")

    subj, visit, date = rec.subject_col, rec.visit_col, rec.date_col
    code_col = rec.testcd_col
    resc = rec.resultc_col
    resn = rec.resultn_col
    orr = rec.orres_col

    # ---- decide the state code (fail-closed) ----
    chosen = state_code
    if chosen is None:
        if len(rec.state_codes) == 1 and not rec.unknown_codes:
            chosen = rec.state_codes[0]
            decisions.append(
                f"CDISC: state axis auto-mapped to recognized diagnosis/"
                f"classification code {chosen!r}.")
        elif len(rec.state_codes) > 1 or rec.unknown_codes:
            raise CdiscMappingError(
                "CDISC state code is ambiguous -- select one explicitly. "
                f"Recognized diagnosis/classification codes: "
                f"{list(rec.state_codes)}; numeric-scale codes (not states): "
                f"{list(rec.measurement_codes)}; unrecognized: "
                f"{list(rec.unknown_codes)}. Pass state_code=<one of "
                f"{list(rec.available_codes)}>.")
        # else: no state codes at all -> clinical axis simply absent (only
        # measurements), which is fine.
    elif chosen not in rec.available_codes:
        raise CdiscMappingError(
            f"selected state_code {chosen!r} is not present in the data "
            f"(available: {list(rec.available_codes)}).")

    out: dict[str, pd.DataFrame] = {}

    def _visit_series(frame: pd.DataFrame) -> pd.Series:
        if visit is not None:
            return frame[visit]
        # derive a stable per-subject visit order if no VISITNUM/VISIT
        return frame.groupby(subj).cumcount() + 1

    def _date_series(frame: pd.DataFrame) -> pd.Series:
        if date is not None:
            return frame[date]
        return pd.Series([None] * len(frame), index=frame.index)

    # ---- clinical state axis (if a state code was chosen) ----
    if chosen is not None:
        sdf = df[df[code_col].astype(str) == str(chosen)].copy()
        # state value: prefer the character result (STRESC/AVALC), then ORRES.
        state_src = resc or orr or resn
        if state_src is None:
            raise CdiscMappingError(
                "no result column (--STRESC/AVALC/--ORRES) to read the state "
                "from.")
        clinical = pd.DataFrame({
            "subject_id": sdf[subj].astype(str).values,
            "visit": _visit_series(sdf).values,
            "visit_date": _date_series(sdf).values,
            "state": sdf[state_src].astype(str).values,
        })
        out["clinical"] = clinical
        decisions.append(
            f"CDISC: clinical state taken from {code_col}={chosen!r} -> "
            f"{state_src} ({len(clinical)} rows).")

    # ---- numeric measurements (cognitive scales) -> wide table for ranges ----
    if rec.measurement_codes and resn is not None:
        mdf = df[df[code_col].astype(str).isin(rec.measurement_codes)].copy()
        if len(mdf):
            mdf["_subject_id"] = mdf[subj].astype(str)
            mdf["_visit"] = _visit_series(mdf).values
            mdf["_visit_date"] = _date_series(mdf).values
            wide = mdf.pivot_table(
                index=["_subject_id", "_visit", "_visit_date"],
                columns=code_col, values=resn, aggfunc="first").reset_index()
            wide = wide.rename(columns={
                "_subject_id": "subject_id", "_visit": "visit",
                "_visit_date": "visit_date"})
            wide.columns.name = None
            out["measurements"] = wide
            decisions.append(
                f"CDISC: {len(rec.measurement_codes)} numeric cognitive-scale "
                f"code(s) normalized to a measurements table for range auditing "
                f"({list(rec.measurement_codes)}).")

    if not out:
        decisions.append(
            "CDISC: table recognized but produced no clinical state or numeric "
            "measurement (no state code chosen and no recognized scales).")
    return out


def read_cdisc_submission(
    path: str,
    decisions: list[str] | None = None,
    *,
    state_code: str | None = None,
) -> dict[str, object]:
    """Read a CDISC SDTM/ADaM file (or folder/zip of domains) and normalize the
    first recognized findings table into a NeuroTCS submission.

    Composes the existing universal reader (so encoding, format, and the
    typed-read contract all apply), recognizes CDISC structure per table, and
    normalizes. Returns a submission dict ({"clinical": df, ...}) plus a
    "_cdisc" key carrying the recognition for transparency. Fail-closed: an
    ambiguous state code raises CdiscMappingError (callers surface the choices).
    """
    from neurotcs.io.readers import read_tables

    decisions = decisions if decisions is not None else []
    tables = read_tables(path, decisions=decisions)

    # Find the first CDISC findings table (deterministic: sorted by sheet name).
    chosen_rec: CdiscRecognition | None = None
    chosen_df: pd.DataFrame | None = None
    recognized: list[str] = []
    for name in sorted(tables):
        df = tables[name]
        rec = recognize_cdisc(df)
        if rec.is_cdisc:
            recognized.append(f"{name}({rec.model}/{rec.domain or '?'})")
            if rec.testcd_col is not None and chosen_rec is None:
                chosen_rec, chosen_df = rec, df
    if recognized:
        decisions.append(f"CDISC: recognized table(s): {', '.join(recognized)}.")
    if chosen_rec is None or chosen_df is None:
        raise CdiscMappingError(
            "no CDISC findings table (with --TESTCD/PARAMCD + result) found in "
            f"the input. Recognized non-findings tables: {recognized or 'none'}.")

    submission = normalize_cdisc_to_long(
        chosen_df, chosen_rec, decisions, state_code=state_code)
    submission["_cdisc"] = chosen_rec  # type: ignore[assignment]
    return submission


# --------------------------------------------------------------------------- #
# Multi-domain join: a full SDTM/ADaM folder -> one unified NeuroTCS sheet dict
# --------------------------------------------------------------------------- #


def join_cdisc_domains(
    path: str,
    decisions: list[str] | None = None,
    *,
    state_code: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Read every CDISC domain in a folder/zip and JOIN them into one unified
    set of NeuroTCS-shaped sheets, keyed on USUBJID (+ VISITNUM).

    A real SDTM submission is multiple domains, not one table:
      * RS (or the chosen diagnosis domain) -> clinical state sheet
        (subject_id / visit / visit_date / state).
      * QS cognitive scales -> a wide MEASUREMENTS sheet (subject_id / visit /
        visit_date / <SCALE columns>), suitable for range-pack auto-wiring.
      * DM (demographics) -> a per-subject sheet (subject_id / AGE / SEX / ...),
        suitable for the data_integrity layer.

    The returned dict uses NeuroTCS-standard column names (subject_id, visit,
    visit_date) so the EXISTING auto-wiring (audit_data_integrity, autowire_
    ranges, cross_sheet) consumes the sheets directly -- this function does NOT
    re-implement the audit wiring, it only normalizes each domain so the sheets
    join on the common keys. Returned keys are the domain labels (e.g.
    'clinical', 'measurements', 'demographics'); deterministic (domains and
    columns sorted). Fail-closed: an ambiguous RS state code raises
    CdiscMappingError listing the choices.
    """
    from neurotcs.io.readers import read_tables

    decisions = decisions if decisions is not None else []
    tables = read_tables(path, decisions=decisions)

    # Recognize every table; bucket by structural role.
    diagnosis_tables: list[tuple[str, pd.DataFrame, CdiscRecognition]] = []
    scale_tables: list[tuple[str, pd.DataFrame, CdiscRecognition]] = []
    demographics_tables: list[tuple[str, pd.DataFrame, CdiscRecognition]] = []
    recognized: list[str] = []

    for tname in sorted(tables):
        df = tables[tname]
        rec = recognize_cdisc(df)
        if not rec.is_cdisc:
            continue
        recognized.append(f"{tname}({rec.model}/{rec.domain or '?'})")
        if rec.testcd_col is None:
            # subject-level (DM-like): demographics
            demographics_tables.append((tname, df, rec))
        elif rec.state_codes and not rec.measurement_codes:
            diagnosis_tables.append((tname, df, rec))
        elif rec.measurement_codes and not rec.state_codes:
            scale_tables.append((tname, df, rec))
        elif rec.state_codes and rec.measurement_codes:
            # mixed QS carrying both a diagnosis code and scales: it can serve
            # as both -- use it for diagnosis AND scales.
            diagnosis_tables.append((tname, df, rec))
            scale_tables.append((tname, df, rec))
        else:
            # only unknown codes: defer to fail-closed selection below.
            diagnosis_tables.append((tname, df, rec))

    if recognized:
        decisions.append(f"CDISC join: recognized domain(s): {', '.join(recognized)}.")
    if not (diagnosis_tables or scale_tables or demographics_tables):
        raise CdiscMappingError(
            "no CDISC domains found in the input (need USUBJID + a recognized "
            "domain signature).")

    out: dict[str, pd.DataFrame] = {}

    # ---- clinical state (first diagnosis-bearing domain; RS preferred) ----
    diagnosis_tables.sort(key=lambda t: (0 if (t[2].domain or "").upper() == "RS"
                                         else 1, t[0]))
    for tname, df, rec in diagnosis_tables:
        norm = normalize_cdisc_to_long(df, rec, decisions, state_code=state_code)
        if "clinical" in norm:
            out["clinical"] = norm["clinical"]
            decisions.append(f"CDISC join: clinical state sourced from {tname!r}.")
            break

    # ---- measurements (merge all scale domains on subject_id/visit) ----
    measurement_frames: list[pd.DataFrame] = []
    for _tname, df, rec in scale_tables:
        norm = normalize_cdisc_to_long(
            df, rec, decisions,
            state_code=(state_code if rec.state_codes else None)
            if rec.state_codes else None)
        if "measurements" in norm:
            measurement_frames.append(norm["measurements"])
    if measurement_frames:
        merged = measurement_frames[0]
        for nxt in measurement_frames[1:]:
            merged = merged.merge(
                nxt, on=["subject_id", "visit", "visit_date"], how="outer")
        # deterministic column order
        keys = ["subject_id", "visit", "visit_date"]
        rest = sorted(c for c in merged.columns if c not in keys)
        out["measurements"] = merged[keys + rest]
        decisions.append(
            f"CDISC join: {len(rest)} cognitive-scale column(s) merged into a "
            "measurements sheet.")

    # ---- demographics (DM) -> per-subject sheet ----
    for tname, df, rec in demographics_tables:
        cols = _cols_lower(df)
        subj = rec.subject_col
        keep = {"subject_id": df[subj].astype(str).values}
        for std in ("age", "sex", "race", "ethnic", "armcd", "arm",
                    "educlvl", "education"):
            actual = cols.get(std)
            if actual is not None:
                keep[std] = df[actual].values
        if len(keep) > 1:
            out["demographics"] = pd.DataFrame(keep)
            decisions.append(
                f"CDISC join: demographics sheet from {tname!r} "
                f"({sorted(k for k in keep if k != 'subject_id')}).")
            break

    if not out:
        raise CdiscMappingError(
            "CDISC domains recognized but none yielded a clinical state, "
            "measurement, or demographics sheet.")
    return out

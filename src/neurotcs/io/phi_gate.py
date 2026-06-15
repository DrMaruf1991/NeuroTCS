"""neurotcs.io.phi_gate -- optional direct-identifier (PHI) input gate.

WHY THIS MODULE EXISTS (hazard H6 / gap G3)
-------------------------------------------
NeuroTCS audits DE-IDENTIFIED research values. It operates on
values/trajectories, not on identity fields, and subject_id values flow into the
bundle's flags. If a user MISUSES the tool by feeding identifiable patient data
(PHI) -- e.g. a subject column that is really a patient name or MRN -- those
identifiers can propagate into the output bundle (H6: "identifiers exposed in
outputs"). Until now PHI handling was "by convention, not enforced" (G3). This
module adds the recommended optional identifier-detection gate that WARNS (or,
opt-in, REFUSES) on probable direct-identifier columns.

DESIGN -- two failure modes, deliberately biased toward not breaking real data
------------------------------------------------------------------------------
A PHI gate can fail two ways, and they pull opposite directions:
  * FALSE NEGATIVE: PHI passes -> a privacy breach. Catastrophic direction.
  * FALSE POSITIVE: legitimate DE-IDENTIFIED cohort data (ADNI/OASIS/NACC --
    the tool's entire validated use) is wrongly flagged/refused -> the tool is
    broken for its primary purpose.
Because the tool's whole job is de-identified cohort data that superficially
resembles identifiers (subject IDs, visit dates, ages), the gate is built to
NOT break that data:
  * It keys ONLY on HIGH-CONFIDENCE direct-identifier signals (column names like
    'patient_name'/'mrn'/'ssn'/'dob', or strict value patterns like SSN/email).
  * It ALLOWLISTS the full study-column vocabulary the tool already understands
    (subject_id, rid, ptid, usubjid, visit, visit_date, age, the measurement
    scales, ...), so de-identified cohort columns never trigger.
  * DEFAULT is WARN, never refuse: a false positive is a dismissable note, not a
    broken audit. Refusal is OPT-IN (refuse=True / CLI --refuse-phi).

HONEST LIMITS -- this is NOT a de-identification guarantee
----------------------------------------------------------
This is a best-effort warning for COMMON direct-identifier patterns. It does NOT
and CANNOT catch all PHI: free-text names in a notes field, contextual
identifiers, unusual formats, or quasi-identifiers in combination are out of
scope. The user remains responsible for de-identification. NeuroTCS is not a
de-identification tool and makes no PHI-detection completeness claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def _norm(s: Any) -> str:
    """Separator-insensitive lowercase, mirroring the tool's column matchers."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


# --------------------------------------------------------------------------- #
# Allowlist: the de-identified study vocabulary the tool understands. A column
# whose normalized name is in (or is a synonym of) this set is NEVER flagged.
# Kept in sync conceptually with io.data_integrity / io.autowire synonyms.
# --------------------------------------------------------------------------- #
_ALLOWLIST_NORMS: frozenset[str] = frozenset(_norm(x) for x in (
    # identity (study IDs -- de-identified by convention, NOT direct identifiers)
    "subject_id", "patient_id", "rid", "ptid", "usubjid", "participant_id", "id",
    # visit / timepoint
    "visit", "visit_id", "viscode", "visitnum", "event_id", "visit_code",
    "timepoint", "wave", "visit_no",
    # dates that are NOT dates-of-birth (visit/exam/scan/assessment dates)
    "visit_date", "visitdate", "exam_date", "examdate", "date", "scan_date",
    "assessment_date",
    # de-identified clinical / demographic values the tool audits
    "age", "sex", "gender", "education", "educ", "apoe", "state",
    "clinical_state", "biological_stage_atn", "diagnosis", "dx",
    # measurement-code / value columns
    "testcd", "paramcd", "measurement", "measurement_code", "measurement_name",
    "test_code", "param_code", "measure", "analyte",
    "stresn", "aval", "value", "result", "orres", "stresc",
    "measurement_value", "val",
))


# --------------------------------------------------------------------------- #
# High-confidence DIRECT-IDENTIFIER column-name tokens. A column whose
# normalized name contains one of these (and is not allowlisted) is probable PHI.
# These are deliberately specific to direct identifiers -- NOT generic words.
# --------------------------------------------------------------------------- #
_IDENTIFIER_NAME_TOKENS: tuple[str, ...] = (
    "patientname", "subjectname", "fullname", "firstname", "lastname",
    "givenname", "surname", "familyname", "maidenname",
    "ssn", "socialsecurity", "mrn", "medicalrecord", "medicalrecordnumber",
    "nationalid", "passport", "driverlicense", "driverslicense",
    "dob", "dateofbirth", "birthdate", "birthday",
    "address", "street", "streetaddress", "homeaddress", "zipcode", "postalcode",
    "phone", "telephone", "phonenumber", "mobile", "cellphone", "fax",
    "email", "emailaddress",
    "insuranceid", "policynumber", "accountnumber",
)

# Exact whole-name identifier matches (short tokens that must match the WHOLE
# normalized name to avoid catching substrings like 'id' inside 'rid').
_IDENTIFIER_NAME_EXACT: frozenset[str] = frozenset((
    "name", "ssn", "mrn", "dob", "zip", "phone", "fax", "email",
))


# --------------------------------------------------------------------------- #
# Strict VALUE patterns -- low false-positive direct identifiers.
# --------------------------------------------------------------------------- #
_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("US SSN", re.compile(r"^\d{3}-\d{2}-\d{4}$")),
    ("email address", re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")),
    ("US phone", re.compile(r"^\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")),
)


@dataclass
class PHIFinding:
    sheet: str
    column: str
    reason: str  # human-readable: what signal fired


@dataclass
class PHIScanResult:
    findings: list[PHIFinding] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


def _column_name_signal(col: str) -> str | None:
    """Return a reason string if the column NAME is a probable direct identifier."""
    n = _norm(col)
    if n in _ALLOWLIST_NORMS:
        return None
    if n in _IDENTIFIER_NAME_EXACT:
        return f"column name '{col}' matches a direct-identifier term"
    for tok in _IDENTIFIER_NAME_TOKENS:
        if tok in n:
            return f"column name '{col}' contains direct-identifier token '{tok}'"
    return None


def _column_value_signal(values: list[Any], sample: int = 50) -> str | None:
    """Return a reason if a sample of VALUES matches a strict identifier pattern.

    Requires MULTIPLE matches (not a single coincidence) to fire, keeping the
    false-positive rate low on de-identified data.
    """
    seen = 0
    for label, pat in _VALUE_PATTERNS:
        hits = 0
        checked = 0
        for v in values:
            if v is None:
                continue
            sv = str(v).strip()
            if not sv:
                continue
            checked += 1
            if pat.match(sv):
                hits += 1
            if checked >= sample:
                break
        # fire only if a clear majority of non-empty sampled values match
        if checked >= 3 and hits >= max(2, int(checked * 0.5)):
            return f"values look like {label} ({hits}/{checked} sampled)"
        seen += 1
    return None


def scan_tables(tables: dict[str, Any]) -> PHIScanResult:
    """Scan input tables for probable DIRECT identifiers. Best-effort, not a
    completeness guarantee. Returns findings; the caller decides warn vs refuse.
    """
    result = PHIScanResult()
    for sheet, df in tables.items():
        try:
            cols = list(df.columns)
        except Exception:
            continue
        for col in cols:
            # 1) column-name signal (allowlist-first)
            reason = _column_name_signal(str(col))
            if reason is not None:
                result.findings.append(PHIFinding(str(sheet), str(col), reason))
                continue
            # 2) value-pattern signal -- skip allowlisted columns entirely
            if _norm(col) in _ALLOWLIST_NORMS:
                continue
            try:
                values = list(df[col].tolist())
            except Exception:
                continue
            vreason = _column_value_signal(values)
            if vreason is not None:
                result.findings.append(PHIFinding(str(sheet), str(col), vreason))
    return result


def format_findings(result: PHIScanResult) -> list[str]:
    """Human-readable note lines for the findings (no 'error:' framing)."""
    lines: list[str] = []
    for f in result.findings:
        lines.append(
            f"possible direct identifier (PHI) in sheet '{f.sheet}': {f.reason}. "
            f"NeuroTCS expects de-identified input and embeds subject_id values "
            f"in flags; confirm de-identification before sharing the bundle."
        )
    return lines

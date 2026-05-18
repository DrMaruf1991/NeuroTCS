"""
Reference adapter: MIRIAD (Minimal Interval Resonance Imaging in AD)
to NeuroTCS trajectories.

MIRIAD is the UCL Dementia Research Centre longitudinal test-retest
cohort: 46 mild-moderate AD subjects + 23 cognitively-normal controls,
708 T1 MRI scans collected at 2, 6, 14, 26, 38 and 52 weeks plus
back-to-back same-session rescans at weeks 0, 6 and 38 (Malone IB,
Cash D, Ridgway GR, MacManus DG, Ourselin S, Fox NC, Schott JM.
MIRIAD - public release of a multiple time point Alzheimer's MR
imaging dataset. NeuroImage 2013;70:33-36, PMID 23274184,
DOI 10.1016/j.neuroimage.2012.12.044).

What MIRIAD is good for
-----------------------

MIRIAD's dual structure — test-retest pairs + longitudinal follow-up —
makes it the right cohort for **Aim 3 measurement-noise floor**:

  (A) Test-retest pairs (weeks 0, 6, 38 each have two back-to-back
      scans on the same day). The audit kernel should produce
      n_flagged ~ 0 on these pairs; any non-zero flag rate represents
      measurement noise that the kernel mis-attributes to biological
      inadmissibility. This is the noise-floor characterization.

  (B) Longitudinal follow-up (weeks 0, 2, 6, 14, 26, 38, 52, 78, 104).
      A third-cohort cTCS replication alongside Aim 1 (ADNI) and
      Aim 2 (OASIS-3). The independent UCL/UK cohort + same-scanner
      design provides the strongest possible test of cTCS portability.

State staging strategy
----------------------

MIRIAD's clinical-assessment table reports MMSE at every visit and
CDR (with CDR-SoB) at *screening only* for AD subjects. The Subjects
table has a `group` column (AD / control) that is fixed at baseline.

Two options for state staging:

  Option A: Use the fixed `group` column → all transitions are
  self-loops (AD->AD or CN->CN). cTCS = 1.0 by construction. This
  is uninformative for the audit kernel.

  Option B: Use MMSE-derived staging at each visit, with thresholds
  from Folstein 1975 (PMID 1202204) and Tombaugh & McIntyre 1992 MMSE
  literature review (PMID 1512391):

      MMSE >= 27   ->  CN  (normal)
      18 <= MMSE <= 26  ->  MCI (mild)
      MMSE <= 17  ->  AD  (moderate-severe dementia)

  This adapter uses Option B for the audit because it produces
  non-trivial state transitions and lets the cTCS / pTCS / uTCS
  scores actually test the kernel. The `group` column is preserved
  in the diagnostic report so any disagreement between MMSE-derived
  state and group-fixed state can be surfaced (analogous to the
  OASIS-3 adapter's dx1 disagreement flagging).

Test-retest pair detection
--------------------------

The adapter exposes a separate `load_miriad_test_retest_pairs()`
function that returns short trajectories built from back-to-back
same-session scans (same subject, same visit number, same age-at-scan
within 0.01 years). Each such pair is one trajectory of length 2 with
a delta_t of 0 days. These are passed through the standard audit kernel
unmodified — the C5+C6 audit_id is computed exactly as for the longitudinal
cohort, so the noise-floor finding is bit-identical reproducible.

Programmatic API
----------------

    from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
        load_miriad_trajectories,
        load_miriad_test_retest_pairs,
    )

    # Longitudinal cTCS replication (Aim 3 primary)
    trajectories, report = load_miriad_trajectories(
        clinical_csv="path/to/ClinicalAssessment.csv",
        sessions_csv="path/to/MR_Sessions.csv",
        subjects_csv="path/to/Subjects.csv",
    )

    # Test-retest noise floor (Aim 3 secondary)
    pairs, pair_report = load_miriad_test_retest_pairs(
        clinical_csv="path/to/ClinicalAssessment.csv",
        sessions_csv="path/to/MR_Sessions.csv",
    )

Cohort hashing
--------------

MIRIAD subject IDs in the public release are already random IDs
(MIRIAD_xxx pattern), but we re-hash with a cohort salt so audit
artifacts cannot be cross-walked back to the MIRIAD release. This
matches the OASIS-3 adapter pattern exactly.

Reference
---------
Malone IB et al. MIRIAD-Public release of a multiple time point
Alzheimer's MR imaging dataset. NeuroImage 2013;70:33-36.
PMID 23274184, DOI 10.1016/j.neuroimage.2012.12.044.
Folstein MF, Folstein SE, McHugh PR. "Mini-mental state". A practical
method for grading the cognitive state of patients for the clinician.
J Psychiatr Res 1975;12(3):189-198. PMID 1202204.
Tombaugh TN, McIntyre NJ. The Mini-Mental State Examination: a
comprehensive review. J Am Geriatr Soc 1992;40(9):922-935. PMID 1512391.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from neurotcs.audit_core.trajectory import (
    Trajectory,
    trajectories_from_dataframe,
)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

COHORT_SALT = "miriad_aim3_2026"  # in production: random per-cohort secret

# MIRIAD reports "age at scan" rather than a calendar date. We synthesize
# visit dates from a fixed baseline + (age - age_at_first_scan) * 365.25.
# Inter-visit intervals are exactly preserved, which is the only thing
# the audit core uses.
SYNTHETIC_BASELINE = date(2010, 1, 1)
DAYS_PER_YEAR = 365.25

# MMSE-based staging thresholds (Folstein 1975, Tombaugh & McIntyre 1992).
# See module docstring for citation rationale.
MMSE_THRESHOLD_CN = 27   # MMSE >= 27 -> CN
MMSE_THRESHOLD_AD = 18   # MMSE < 18 -> AD; 18..26 -> MCI

# Tolerance for matching back-to-back same-session scans by age-at-scan
# (MIRIAD records age to two decimal places; same-day rescans should be
# bit-equal at that precision, but float-conversion drift can push them
# to 0.0001 or so).
TEST_RETEST_AGE_TOLERANCE_YEARS = 0.005  # ~1.8 days


# ------------------------------------------------------------------
# MMSE → state mapping (Folstein 1975 / Tombaugh-McIntyre 1992)
# ------------------------------------------------------------------

def mmse_to_state(mmse: float | None) -> str | None:
    """Map MMSE score to NIA-AA 2018 categorical state.

    Per Folstein 1975 (J Psychiatr Res 12:189-198, PMID 1202204) and
    Tombaugh & McIntyre 1992 (J Am Geriatr Soc 40:922-935, PMID 1512391):

        MMSE >= 27   -> CN  (no impairment)
        18-26        -> MCI (mild cognitive impairment / very mild dementia)
        MMSE <= 17   -> AD  (moderate to severe dementia)

    These thresholds are the consensus operationalization in the AD
    research literature; individual studies vary by ±1 point at each
    boundary. The strict ≥27 / ≤17 cuts here are deliberately
    conservative so that MMSE noise within a 1-point window does not
    silently move a subject across a state boundary.

    Returns None for NaN, negative values, or out-of-range inputs so
    the caller can drop or flag them.
    """
    if mmse is None:
        return None
    try:
        m = float(mmse)
    except (TypeError, ValueError):
        return None
    if math.isnan(m):
        return None
    if m < 0 or m > 30:
        return None  # invalid MMSE
    if m >= MMSE_THRESHOLD_CN:
        return "CN"
    if m < MMSE_THRESHOLD_AD:
        return "AD"
    return "MCI"


# ------------------------------------------------------------------
# group → state mapping (Subjects table, fixed-at-baseline)
# ------------------------------------------------------------------

def group_to_state(group: str | None) -> str | None:
    """Map MIRIAD `group` column to NIA-AA 2018 state.

    Used ONLY for disagreement flagging against the MMSE-derived state;
    MMSE is primary per the module docstring. Returns None for
    unrecognized values rather than coercing.
    """
    if group is None or (isinstance(group, float) and math.isnan(group)):
        return None
    text = str(group).strip().lower()
    if text in {"control", "controls", "ctrl", "cn", "hc", "healthy"}:
        return "CN"
    if text in {"ad", "alzheimer", "alzheimers", "alzheimer's", "patient"}:
        return "AD"
    return None


# ------------------------------------------------------------------
# Hashing (no PHI leaves the adapter)
# ------------------------------------------------------------------

def hash_patient_id(subject_id: str) -> str:
    """Deterministic, non-reversible patient identifier.

    Re-hashes the (already random) MIRIAD subject ID with a cohort salt
    so downstream artifacts cannot be cross-walked back to MIRIAD.
    """
    h = hashlib.sha256(f"{COHORT_SALT}_{subject_id}".encode()).hexdigest()
    return f"MIRIAD_{h[:16]}"


# ------------------------------------------------------------------
# Defensive column resolution
# ------------------------------------------------------------------

def _resolve_column(df: pd.DataFrame, candidates: list[str],
                    purpose: str) -> str:
    """Find the first matching column name from `candidates` in `df`.

    MIRIAD's XNAT-exported CSVs vary by export profile (`Subject`,
    `subject_id`, `xnat:subjectData/ID`, etc). This helper tries a list
    of plausible names and raises a clear error if none match.
    """
    lower_to_actual = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_to_actual:
            return lower_to_actual[cand.lower()]
    raise KeyError(
        f"MIRIAD adapter could not find {purpose} column. Tried "
        f"{candidates!r}. Available columns: {list(df.columns)}"
    )


SUBJECT_COL_CANDIDATES = [
    "Subject", "subject_id", "Subject ID", "subjectID", "Subject_ID",
    "xnat_subjectData/ID", "xnat:subjectData/ID", "ID",
]
AGE_COL_CANDIDATES = [
    "Age", "age", "age_at_scan", "Age (years)", "scan_age",
    "xnat:mrSessionData/age",
]
MMSE_COL_CANDIDATES = [
    "MMSE", "mmse", "mmse_score", "MMSE Score", "MMSE_total", "mmse_total",
]
GROUP_COL_CANDIDATES = [
    "Group", "group", "diagnosis", "Diagnosis", "category", "Category",
]
VISIT_COL_CANDIDATES = [
    "Visit", "visit", "visit_label", "visit_number", "Session", "session",
    "label", "Label",
]


# ------------------------------------------------------------------
# MIRIAD Label parsing (XNAT export format)
# ------------------------------------------------------------------

# MIRIAD XNAT exports the per-row identifier in a `Label` column that
# encodes (subject, visit, modality) as one composite string:
#   miriad_188_1_MR_1   -> subject miriad_188, visit 1, MR scan 1
#   miriad_188_2_MR_2   -> subject miriad_188, visit 2, MR scan 2 (rescan)
#   miriad_255_1_MMSE   -> subject miriad_255, visit 1, MMSE assessment
#
# The visit number is the second integer between the subject prefix and
# the modality token. We use a strict regex so anything that doesn't
# match returns None (signals "use this column as-is for join").

_MIRIAD_LABEL_RE = __import__("re").compile(
    r"^miriad_\d+_(?P<visit_num>\d+)_(?:MR_\d+|MMSE|.*)$",
    __import__("re").IGNORECASE,
)


def parse_miriad_visit_number(label: str | None) -> str | None:
    """Extract the visit number from a MIRIAD XNAT Label string.

    Examples:
        miriad_188_1_MR_1   -> "1"
        miriad_188_2_MR_2   -> "2"
        miriad_255_1_MMSE   -> "1"
        anything else       -> None
    """
    if label is None or (isinstance(label, float) and math.isnan(label)):
        return None
    m = _MIRIAD_LABEL_RE.match(str(label).strip())
    return m.group("visit_num") if m else None


def _label_looks_like_miriad_xnat(values: pd.Series) -> bool:
    """Check whether a column's values look like MIRIAD XNAT composite labels.

    Returns True if at least 80% of non-null values parse cleanly via
    `parse_miriad_visit_number`. Used to decide whether to derive a
    `visit_num` join key or treat the column as a visit label directly.
    """
    non_null = values.dropna()
    if len(non_null) == 0:
        return False
    parsed = non_null.astype(str).apply(parse_miriad_visit_number)
    return (parsed.notna().sum() / len(non_null)) >= 0.80


# ------------------------------------------------------------------
# Subject-ID → group inference (when Subjects.csv has no Group column)
# ------------------------------------------------------------------

# Per Malone 2013 the MIRIAD subject-ID space splits AD and controls
# at id 234: ids 188-233 inclusive are the 46 AD subjects, ids 234-278
# inclusive (or thereabouts) are the 23 controls. This is the
# published convention; we use it ONLY when the Subjects CSV has no
# explicit `Group` column. If `Group` is present we prefer it.
# Subjects with IDs outside [188, 278] return None ("unknown group").

MIRIAD_AD_ID_MAX = 233  # ids 188-233 inclusive: 46 AD subjects
MIRIAD_CONTROL_ID_MAX = 280  # ids 234-280 covers the 23 controls
                              # (a few unused IDs in this range)


def infer_miriad_group_from_subject_id(subject_id: str | None) -> str | None:
    """Infer AD vs control from a MIRIAD subject ID (Malone 2013 convention).

    The published MIRIAD release assigns subject IDs sequentially:
    188-233 are AD subjects, 234+ are controls. Used only when the
    Subjects.csv export has no `Group` column. Returns None when the
    subject ID doesn't fit the expected pattern.
    """
    if subject_id is None:
        return None
    text = str(subject_id).strip().lower()
    # Accept both "miriad_188" and bare "188"
    if text.startswith("miriad_"):
        text = text[len("miriad_"):]
    try:
        sid = int(text)
    except (TypeError, ValueError):
        return None
    if 188 <= sid <= MIRIAD_AD_ID_MAX:
        return "AD"
    if MIRIAD_AD_ID_MAX < sid <= MIRIAD_CONTROL_ID_MAX:
        return "CN"
    return None


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

@dataclass(frozen=True)
class MIRIADLoadReport:
    """Diagnostic counts from one load_miriad_trajectories call."""
    raw_sessions_rows: int
    raw_clinical_rows: int
    raw_subjects_rows: int
    merged_rows: int
    rows_with_mmse: int
    mmse_forward_filled: int
    unmappable_mmse: int
    out_of_range_mmse: int
    n_trajectories: int
    n_transitions: int
    group_mmse_disagreements: int
    group_mmse_state_discordant: int
    group_mmse_disagreement_examples: tuple[dict, ...]
    n_test_retest_visits_excluded: int

    def to_dict(self) -> dict:
        return {
            "raw_sessions_rows": self.raw_sessions_rows,
            "raw_clinical_rows": self.raw_clinical_rows,
            "raw_subjects_rows": self.raw_subjects_rows,
            "merged_rows": self.merged_rows,
            "rows_with_mmse": self.rows_with_mmse,
            "mmse_forward_filled": self.mmse_forward_filled,
            "unmappable_mmse": self.unmappable_mmse,
            "out_of_range_mmse": self.out_of_range_mmse,
            "n_trajectories": self.n_trajectories,
            "n_transitions": self.n_transitions,
            "group_mmse_disagreements": self.group_mmse_disagreements,
            "group_mmse_state_discordant": self.group_mmse_state_discordant,
            "group_mmse_disagreement_examples": list(
                self.group_mmse_disagreement_examples
            ),
            "n_test_retest_visits_excluded": self.n_test_retest_visits_excluded,
        }


@dataclass(frozen=True)
class MIRIADTestRetestReport:
    """Diagnostic counts from one load_miriad_test_retest_pairs call."""
    raw_sessions_rows: int
    raw_clinical_rows: int
    n_subjects_with_rescan: int
    n_rescan_pairs: int
    n_rescan_pairs_with_mmse: int
    n_pairs_state_identical: int
    n_pairs_state_differs: int
    pair_state_differences: tuple[dict, ...]

    def to_dict(self) -> dict:
        return {
            "raw_sessions_rows": self.raw_sessions_rows,
            "raw_clinical_rows": self.raw_clinical_rows,
            "n_subjects_with_rescan": self.n_subjects_with_rescan,
            "n_rescan_pairs": self.n_rescan_pairs,
            "n_rescan_pairs_with_mmse": self.n_rescan_pairs_with_mmse,
            "n_pairs_state_identical": self.n_pairs_state_identical,
            "n_pairs_state_differs": self.n_pairs_state_differs,
            "pair_state_differences": list(self.pair_state_differences),
        }


def _load_csvs(
    clinical_csv: Path,
    sessions_csv: Path,
    subjects_csv: Path | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    """Read the three MIRIAD CSVs with defensive error messages."""
    if not clinical_csv.exists():
        raise FileNotFoundError(
            f"MIRIAD ClinicalAssessment CSV not found: {clinical_csv}"
        )
    if not sessions_csv.exists():
        raise FileNotFoundError(
            f"MIRIAD MR Sessions CSV not found: {sessions_csv}"
        )
    clinical = pd.read_csv(clinical_csv)
    sessions = pd.read_csv(sessions_csv)
    subjects = None
    if subjects_csv is not None and Path(subjects_csv).exists():
        subjects = pd.read_csv(subjects_csv)
    return clinical, sessions, subjects


def _build_visit_dates(
    sessions: pd.DataFrame,
    subject_col: str,
    age_col: str,
) -> pd.Series:
    """Convert per-row age-at-scan to synthetic ascending dates."""
    # For each subject, find minimum age (== first scan) and convert
    # (age - min_age) * 365.25 days to a synthetic date offset.
    age_floats = pd.to_numeric(sessions[age_col], errors="coerce")
    sessions = sessions.assign(_age_float=age_floats)
    sessions["_age_min"] = sessions.groupby(subject_col)["_age_float"].transform("min")
    offsets_days = ((sessions["_age_float"] - sessions["_age_min"])
                    * DAYS_PER_YEAR).round().astype("Int64")
    visit_dates = offsets_days.apply(
        lambda d: SYNTHETIC_BASELINE + timedelta(days=int(d))
        if pd.notna(d) else pd.NaT
    )
    return visit_dates


def load_miriad_trajectories(
    clinical_csv: str | Path,
    sessions_csv: str | Path,
    subjects_csv: str | Path | None = None,
    *,
    flag_group_disagreement: bool = True,
    hash_ids: bool = True,
    skip_invalid: bool = True,
    exclude_test_retest_rescans: bool = True,
) -> tuple[list[Trajectory], MIRIADLoadReport]:
    """Load MIRIAD into Aim 3 longitudinal trajectories.

    Joins the three MIRIAD tables on subject ID and (where possible) visit
    label, deduplicates same-session rescans for the longitudinal audit,
    derives state from MMSE (per the module docstring rationale), and
    builds trajectories ready for `neurotcs.audit(...)`.

    Args:
        clinical_csv: Path to ClinicalAssessment.csv (provides MMSE per visit).
        sessions_csv: Path to MR_Sessions.csv (provides age-at-scan).
        subjects_csv: Optional path to Subjects.csv (provides `group`
            for disagreement diagnostics).
        flag_group_disagreement: If True, count rows where the MMSE-derived
            state disagrees with the Subjects.group column. Diagnostic only;
            never drops rows.
        hash_ids: Re-hash subject IDs with a cohort salt.
        skip_invalid: Drop subjects whose dates can't be coerced.
        exclude_test_retest_rescans: If True (default), only one scan per
            (subject, visit_label) is kept in the longitudinal cohort —
            the other back-to-back scan is reserved for the test-retest
            analysis. If False, both rescans appear as identical visits
            on the same synthetic date.

    Returns:
        (trajectories, report). `trajectories` is ready to pass to
        `neurotcs.audit(...)`. `report` carries the diagnostic counts.
    """
    clinical_csv = Path(clinical_csv)
    sessions_csv = Path(sessions_csv)
    subjects_csv = Path(subjects_csv) if subjects_csv else None

    clinical, sessions, subjects = _load_csvs(
        clinical_csv, sessions_csv, subjects_csv,
    )
    raw_clinical_rows = len(clinical)
    raw_sessions_rows = len(sessions)
    raw_subjects_rows = len(subjects) if subjects is not None else 0

    # ---- Resolve column names defensively ----
    subj_col_s = _resolve_column(sessions, SUBJECT_COL_CANDIDATES,
                                  purpose="subject (MR Sessions)")
    age_col = _resolve_column(sessions, AGE_COL_CANDIDATES,
                              purpose="age-at-scan (MR Sessions)")
    subj_col_c = _resolve_column(clinical, SUBJECT_COL_CANDIDATES,
                                  purpose="subject (ClinicalAssessment)")
    mmse_col = _resolve_column(clinical, MMSE_COL_CANDIDATES,
                               purpose="MMSE (ClinicalAssessment)")

    # Visit label is optional but improves clinical↔session join quality.
    # MIRIAD's XNAT exports encode visit number inside a composite `Label`
    # column (e.g. miriad_188_2_MR_1 means "subject 188, visit 2, scan 1").
    # When detected, we parse it into a clean `_visit_num` join key.
    visit_col_s = None
    visit_col_c = None
    for cand in VISIT_COL_CANDIDATES:
        if cand.lower() in {c.lower() for c in sessions.columns}:
            visit_col_s = next(c for c in sessions.columns if c.lower() == cand.lower())
            break
    for cand in VISIT_COL_CANDIDATES:
        if cand.lower() in {c.lower() for c in clinical.columns}:
            visit_col_c = next(c for c in clinical.columns if c.lower() == cand.lower())
            break

    # Detect MIRIAD XNAT Label format and derive visit_num join key
    use_miriad_label_parsing = False
    if (visit_col_s is not None and visit_col_c is not None
            and _label_looks_like_miriad_xnat(sessions[visit_col_s])
            and _label_looks_like_miriad_xnat(clinical[visit_col_c])):
        use_miriad_label_parsing = True
        sessions = sessions.copy()
        clinical = clinical.copy()
        sessions["_visit_num"] = sessions[visit_col_s].apply(
            parse_miriad_visit_number
        )
        clinical["_visit_num"] = clinical[visit_col_c].apply(
            parse_miriad_visit_number
        )

    # ---- Build synthetic visit dates from age-at-scan ----
    if not use_miriad_label_parsing:
        sessions = sessions.copy()
    sessions["_visit_date"] = _build_visit_dates(
        sessions, subj_col_s, age_col,
    )
    sessions = sessions.dropna(subset=["_visit_date"]).copy()

    # ---- Deduplicate same-session rescans for the longitudinal cohort ----
    n_test_retest_visits_excluded = 0
    if exclude_test_retest_rescans:
        if use_miriad_label_parsing:
            # Dedup by (subject, visit_num) — MIRIAD's Label encodes scan
            # number after the visit number, so two rescans at visit N
            # produce two rows with the same `_visit_num`.
            before = len(sessions)
            sessions = sessions.drop_duplicates(
                subset=[subj_col_s, "_visit_num"], keep="first",
            )
            n_test_retest_visits_excluded = before - len(sessions)
        elif visit_col_s is not None:
            # Drop duplicates by (subject, visit_label) — keep first
            before = len(sessions)
            sessions = sessions.drop_duplicates(
                subset=[subj_col_s, visit_col_s], keep="first",
            )
            n_test_retest_visits_excluded = before - len(sessions)
        else:
            # No visit label — fall back to (subject, age) deduplication
            # at the test-retest tolerance.
            sessions["_age_rounded"] = (
                pd.to_numeric(sessions[age_col], errors="coerce")
                / TEST_RETEST_AGE_TOLERANCE_YEARS
            ).round().astype("Int64")
            before = len(sessions)
            sessions = sessions.drop_duplicates(
                subset=[subj_col_s, "_age_rounded"], keep="first",
            )
            n_test_retest_visits_excluded = before - len(sessions)

    # ---- Merge clinical MMSE into sessions ----
    if use_miriad_label_parsing:
        # Join on (subject, parsed_visit_num)
        clinical_for_merge = (
            clinical[[subj_col_c, "_visit_num", mmse_col]]
            .rename(columns={subj_col_c: subj_col_s})
            .drop_duplicates(subset=[subj_col_s, "_visit_num"], keep="first")
        )
        merged = sessions.merge(
            clinical_for_merge,
            on=[subj_col_s, "_visit_num"],
            how="left",
        )
    elif visit_col_s is not None and visit_col_c is not None:
        merged = sessions.merge(
            clinical[[subj_col_c, visit_col_c, mmse_col]].rename(
                columns={subj_col_c: subj_col_s, visit_col_c: visit_col_s}
            ),
            on=[subj_col_s, visit_col_s],
            how="left",
        )
    else:
        # No visit label common to both — fall back to nearest-MMSE-by-subject
        # join. Take median MMSE per subject if multiple values exist.
        mmse_by_subj = clinical.groupby(subj_col_c)[mmse_col].median()
        merged = sessions.copy()
        merged[mmse_col] = merged[subj_col_s].map(mmse_by_subj)

    # ---- Forward-fill MMSE within each subject ----
    # MIRIAD records MMSE at baseline and 6-monthly intervals (Malone 2013),
    # not at every scan visit. Visits without a per-visit MMSE inherit the
    # most recent prior assessment — the standard treatment of intermittent
    # clinical-assessment cohorts. Without this step the longitudinal
    # trajectories would lose ~40% of their visits (the ones at 2, 6, 14
    # week timepoints, which have no MMSE).
    #
    # We sort within each subject by visit date and forward-fill. Subjects
    # who only have a single MMSE (e.g. baseline only) get that one value
    # propagated to all their visits.
    forward_fill_count = 0
    if mmse_col in merged.columns:
        merged = merged.sort_values([subj_col_s, "_visit_date"]).copy()
        before_nulls = int(merged[mmse_col].isna().sum())
        merged[mmse_col] = (
            merged.groupby(subj_col_s, group_keys=False)[mmse_col]
            .ffill()
        )
        # Optionally backfill the very first visit if no baseline MMSE
        # exists yet — accepting that the earliest assessment may be
        # from a future visit. This handles the rare case where the
        # first scan precedes the first MMSE record.
        merged[mmse_col] = (
            merged.groupby(subj_col_s, group_keys=False)[mmse_col]
            .bfill()
        )
        after_nulls = int(merged[mmse_col].isna().sum())
        forward_fill_count = before_nulls - after_nulls

    merged_rows = len(merged)
    rows_with_mmse = int(merged[mmse_col].notna().sum())

    # ---- MMSE → state ----
    merged["_NeuroTCS_state"] = merged[mmse_col].apply(mmse_to_state)
    out_of_range = int(
        merged[mmse_col].apply(
            lambda v: (
                isinstance(v, (int, float))
                and not math.isnan(float(v))
                and (float(v) < 0 or float(v) > 30)
            )
        ).sum()
    )
    unmappable = int(merged["_NeuroTCS_state"].isna().sum())
    merged = merged.dropna(subset=["_NeuroTCS_state"]).copy()

    # ---- Group↔MMSE disagreement diagnostics ----
    disagreement_count = 0
    state_discordant_count = 0
    disagreement_examples: list[dict] = []
    if flag_group_disagreement:
        group_map: dict[str, str] = {}
        if subjects is not None:
            subj_col_subj = _resolve_column(subjects, SUBJECT_COL_CANDIDATES,
                                             purpose="subject (Subjects)")
            group_col = None
            for cand in GROUP_COL_CANDIDATES:
                if cand.lower() in {c.lower() for c in subjects.columns}:
                    group_col = next(c for c in subjects.columns
                                      if c.lower() == cand.lower())
                    break
            if group_col is not None:
                group_map = dict(zip(
                    subjects[subj_col_subj].astype(str),
                    subjects[group_col].astype(str),
                ))

        # If we have a non-empty explicit group_map, use it. Otherwise fall
        # back to subject-ID-based inference (Malone 2013 convention:
        # MIRIAD ids 188-233 are AD, 234+ are controls). This handles
        # XNAT exports of the Subjects table that omit the Group column.
        if group_map:
            merged["_group_state"] = (
                merged[subj_col_s].astype(str).map(group_map).apply(group_to_state)
            )
        else:
            merged["_group_state"] = (
                merged[subj_col_s].astype(str).apply(
                    infer_miriad_group_from_subject_id
                )
            )
        # All non-equal pairs (including AD-group with MCI-MMSE, which is
        # consistent with mild AD per Malone 2013 inclusion criterion of
        # MMSE 12-26). Counted for transparency.
        mask = (
            merged["_group_state"].notna()
            & (merged["_NeuroTCS_state"] != merged["_group_state"])
        )
        disagreement_count = int(mask.sum())

        # State-DISCORDANT subset: the only clinically meaningful flag.
        # AD group with CN-range MMSE (>=27) or CN group with AD-range
        # MMSE (<=17). AD group with MCI-range MMSE (18-26) is the
        # MIRIAD inclusion criterion and is NOT a disagreement.
        discordant_mask = (
            merged["_group_state"].notna()
            & (
                ((merged["_group_state"] == "AD")
                 & (merged["_NeuroTCS_state"] == "CN"))
                | ((merged["_group_state"] == "CN")
                   & (merged["_NeuroTCS_state"] == "AD"))
            )
        )
        state_discordant_count = int(discordant_mask.sum())

        if state_discordant_count > 0:
            sample = merged[discordant_mask].head(10)
            for _, row in sample.iterrows():
                disagreement_examples.append({
                    "subject_id": str(row[subj_col_s]),
                    "age_at_scan": float(row[age_col]),
                    "MMSE": float(row[mmse_col]),
                    "mmse_state": str(row["_NeuroTCS_state"]),
                    "group_state": str(row["_group_state"]),
                    "discordance_type": "state_discordant",
                })

    # ---- Hash patient IDs ----
    if hash_ids:
        merged["_NeuroTCS_patient_id"] = (
            merged[subj_col_s].astype(str).apply(hash_patient_id)
        )
    else:
        merged["_NeuroTCS_patient_id"] = merged[subj_col_s].astype(str)

    # ---- Build trajectories ----
    trajectories = trajectories_from_dataframe(
        merged,
        patient_id_col="_NeuroTCS_patient_id",
        visit_date_col="_visit_date",
        state_col="_NeuroTCS_state",
        skip_invalid=skip_invalid,
    )

    n_transitions = sum(t.num_transitions for t in trajectories)

    report = MIRIADLoadReport(
        raw_sessions_rows=raw_sessions_rows,
        raw_clinical_rows=raw_clinical_rows,
        raw_subjects_rows=raw_subjects_rows,
        merged_rows=merged_rows,
        rows_with_mmse=rows_with_mmse,
        mmse_forward_filled=forward_fill_count,
        unmappable_mmse=unmappable,
        out_of_range_mmse=out_of_range,
        n_trajectories=len(trajectories),
        n_transitions=n_transitions,
        group_mmse_disagreements=disagreement_count,
        group_mmse_state_discordant=state_discordant_count,
        group_mmse_disagreement_examples=tuple(disagreement_examples),
        n_test_retest_visits_excluded=n_test_retest_visits_excluded,
    )
    return trajectories, report


def load_miriad_test_retest_pairs(
    clinical_csv: str | Path,
    sessions_csv: str | Path,
    *,
    hash_ids: bool = True,
) -> tuple[list[Trajectory], MIRIADTestRetestReport]:
    """Load MIRIAD same-session back-to-back scans as test-retest pairs.

    Returns one Trajectory per (subject, visit) pair where two scans
    were collected on the same day. Each trajectory has length 2 with
    a delta_t of 0 days; for the audit kernel these are admissible
    self-loops by construction, so any flagged transition represents
    measurement-noise leakage into the audit decision.

    Args:
        clinical_csv: Path to ClinicalAssessment.csv.
        sessions_csv: Path to MR_Sessions.csv.
        hash_ids: Re-hash subject IDs with a cohort salt.

    Returns:
        (pairs, report). `pairs` is a list of length-2 Trajectory objects
        ready for `neurotcs.audit(...)`. `report` carries pair counts and
        state-disagreement examples.
    """
    clinical_csv = Path(clinical_csv)
    sessions_csv = Path(sessions_csv)
    clinical = pd.read_csv(clinical_csv)
    sessions = pd.read_csv(sessions_csv)
    raw_clinical_rows = len(clinical)
    raw_sessions_rows = len(sessions)

    subj_col_s = _resolve_column(sessions, SUBJECT_COL_CANDIDATES,
                                  purpose="subject (MR Sessions)")
    age_col = _resolve_column(sessions, AGE_COL_CANDIDATES,
                              purpose="age-at-scan (MR Sessions)")
    subj_col_c = _resolve_column(clinical, SUBJECT_COL_CANDIDATES,
                                  purpose="subject (ClinicalAssessment)")
    mmse_col = _resolve_column(clinical, MMSE_COL_CANDIDATES,
                               purpose="MMSE (ClinicalAssessment)")

    # Identify back-to-back pairs: same subject, same age (within tolerance).
    sessions = sessions.copy()
    sessions["_age_float"] = pd.to_numeric(sessions[age_col], errors="coerce")
    sessions = sessions.dropna(subset=["_age_float"]).copy()
    sessions["_age_bin"] = (
        sessions["_age_float"] / TEST_RETEST_AGE_TOLERANCE_YEARS
    ).round().astype("Int64")

    # Group by (subject, age_bin) and find groups with exactly 2 rows
    grouped = sessions.groupby([subj_col_s, "_age_bin"])
    pair_rows: list[pd.DataFrame] = []
    n_subjects_with_rescan: set = set()
    for (subj, _bin), group in grouped:
        if len(group) >= 2:
            # Take the first two scans (some triplets exist in MIRIAD)
            pair_rows.append(group.head(2))
            n_subjects_with_rescan.add(subj)
    if not pair_rows:
        # Return empty result rather than crash
        return [], MIRIADTestRetestReport(
            raw_sessions_rows=raw_sessions_rows,
            raw_clinical_rows=raw_clinical_rows,
            n_subjects_with_rescan=0,
            n_rescan_pairs=0,
            n_rescan_pairs_with_mmse=0,
            n_pairs_state_identical=0,
            n_pairs_state_differs=0,
            pair_state_differences=tuple(),
        )

    pairs_df = pd.concat(pair_rows, ignore_index=True)
    pairs_df["_visit_date"] = SYNTHETIC_BASELINE  # all pairs collapse to baseline

    # Attach MMSE to each pair-row. Two strategies:
    #   (a) Label-based per-visit join (preferred): parse visit number
    #       from sessions.Label and clinical.Label, join on (subject,
    #       visit_num). This gives the correct MMSE for the specific
    #       visit where the back-to-back rescan occurred.
    #   (b) Fallback: median MMSE per subject. Used when Label parsing
    #       isn't available. Within a single visit MMSE is identical
    #       between scans by construction (one assessment per visit),
    #       so per-subject median is a reasonable proxy.
    visit_col_s_pair = None
    visit_col_c_pair = None
    for cand in VISIT_COL_CANDIDATES:
        if cand.lower() in {c.lower() for c in pairs_df.columns}:
            visit_col_s_pair = next(c for c in pairs_df.columns
                                     if c.lower() == cand.lower())
            break
    for cand in VISIT_COL_CANDIDATES:
        if cand.lower() in {c.lower() for c in clinical.columns}:
            visit_col_c_pair = next(c for c in clinical.columns
                                     if c.lower() == cand.lower())
            break

    if (visit_col_s_pair is not None and visit_col_c_pair is not None
            and _label_looks_like_miriad_xnat(pairs_df[visit_col_s_pair])
            and _label_looks_like_miriad_xnat(clinical[visit_col_c_pair])):
        pairs_df["_visit_num"] = pairs_df[visit_col_s_pair].apply(
            parse_miriad_visit_number
        )
        clinical_for_pairs = clinical[[subj_col_c, visit_col_c_pair,
                                        mmse_col]].copy()
        clinical_for_pairs["_visit_num"] = (
            clinical_for_pairs[visit_col_c_pair].apply(parse_miriad_visit_number)
        )
        clinical_for_pairs = (
            clinical_for_pairs[[subj_col_c, "_visit_num", mmse_col]]
            .rename(columns={subj_col_c: subj_col_s})
            .drop_duplicates(subset=[subj_col_s, "_visit_num"], keep="first")
        )
        pairs_df = pairs_df.merge(
            clinical_for_pairs,
            on=[subj_col_s, "_visit_num"],
            how="left",
        )
    else:
        # Fallback: per-subject median MMSE. Filter to mappable MMSE values
        # BEFORE taking the median, so out-of-range sentinels (e.g. 99 used
        # as a "missing" marker) don't poison the median. Equivalent: take
        # the median of only the values that mmse_to_state() can map.
        clinical_valid = clinical[
            clinical[mmse_col].apply(
                lambda v: mmse_to_state(v) is not None
            )
        ]
        mmse_by_subj = clinical_valid.groupby(subj_col_c)[mmse_col].median()
        pairs_df[mmse_col] = pairs_df[subj_col_s].map(mmse_by_subj)
    pairs_df["_NeuroTCS_state"] = pairs_df[mmse_col].apply(mmse_to_state)

    n_rescan_pairs = len(pairs_df) // 2

    # n_rescan_pairs_with_mmse counts pairs where BOTH scans have a valid
    # MMSE-derived state — i.e. pairs that will proceed to the audit.
    # The previous implementation counted groups with at least one valid
    # scan, which over-reported by including pairs where one scan was
    # then dropped by the dropna step below.
    _valid = pairs_df.dropna(subset=["_NeuroTCS_state"])
    _pair_sizes = _valid.groupby([subj_col_s, "_age_bin"]).size()
    n_rescan_pairs_with_mmse = int((_pair_sizes >= 2).sum())

    # Filter to rows with valid MMSE-derived state
    pairs_df = pairs_df.dropna(subset=["_NeuroTCS_state"]).copy()

    # Re-pair after filtering (in case one of two had invalid MMSE)
    final_groups = pairs_df.groupby([subj_col_s, "_age_bin"])
    final_pair_rows: list[pd.DataFrame] = []
    for (_subj, _bin), group in final_groups:
        if len(group) >= 2:
            final_pair_rows.append(group.head(2))
    if not final_pair_rows:
        return [], MIRIADTestRetestReport(
            raw_sessions_rows=raw_sessions_rows,
            raw_clinical_rows=raw_clinical_rows,
            n_subjects_with_rescan=len(n_subjects_with_rescan),
            n_rescan_pairs=n_rescan_pairs,
            n_rescan_pairs_with_mmse=n_rescan_pairs_with_mmse,
            n_pairs_state_identical=0,
            n_pairs_state_differs=0,
            pair_state_differences=tuple(),
        )

    # Build the per-pair trajectories. Both rescans land on the SAME
    # synthetic date — the Trajectory class allows ties on dates (per
    # `audit_core/trajectory.py:66`: "allow ties — same-day re-read"),
    # which is the correct semantic encoding of back-to-back same-session
    # scans (delta_t_days = 0.0). Using +1 day would mis-represent the
    # measurement-noise floor as a 1-day-apart trajectory.
    rows_to_build: list[dict] = []
    state_differences: list[dict] = []
    n_identical = 0
    n_differs = 0
    pair_idx = 0
    for group in final_pair_rows:
        rows = group.head(2).to_dict("records")
        # Build a unique trajectory ID per pair so they don't collide
        pair_pid_raw = f"pair_{pair_idx}_{rows[0][subj_col_s]}"
        pair_idx += 1
        if hash_ids:
            pair_pid = hash_patient_id(pair_pid_raw)
        else:
            pair_pid = pair_pid_raw
        rows_to_build.append({
            "_NeuroTCS_patient_id": pair_pid,
            "_visit_date": SYNTHETIC_BASELINE,
            "_NeuroTCS_state": rows[0]["_NeuroTCS_state"],
        })
        rows_to_build.append({
            "_NeuroTCS_patient_id": pair_pid,
            "_visit_date": SYNTHETIC_BASELINE,  # SAME day — delta_t = 0
            "_NeuroTCS_state": rows[1]["_NeuroTCS_state"],
        })
        if rows[0]["_NeuroTCS_state"] == rows[1]["_NeuroTCS_state"]:
            n_identical += 1
        else:
            n_differs += 1
            if len(state_differences) < 10:
                state_differences.append({
                    "subject_id": str(rows[0][subj_col_s]),
                    "scan_a_state": str(rows[0]["_NeuroTCS_state"]),
                    "scan_b_state": str(rows[1]["_NeuroTCS_state"]),
                    "age_at_scan": float(rows[0]["_age_float"]),
                })

    pair_df = pd.DataFrame(rows_to_build)
    trajectories = trajectories_from_dataframe(
        pair_df,
        patient_id_col="_NeuroTCS_patient_id",
        visit_date_col="_visit_date",
        state_col="_NeuroTCS_state",
        skip_invalid=True,
    )

    report = MIRIADTestRetestReport(
        raw_sessions_rows=raw_sessions_rows,
        raw_clinical_rows=raw_clinical_rows,
        n_subjects_with_rescan=len(n_subjects_with_rescan),
        n_rescan_pairs=n_rescan_pairs,
        n_rescan_pairs_with_mmse=n_rescan_pairs_with_mmse,
        n_pairs_state_identical=n_identical,
        n_pairs_state_differs=n_differs,
        pair_state_differences=tuple(state_differences),
    )
    return trajectories, report


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Load MIRIAD into NeuroTCS trajectories"
    )
    parser.add_argument("--clinical", required=True,
                        help="Path to ClinicalAssessment.csv")
    parser.add_argument("--sessions", required=True,
                        help="Path to MR_Sessions.csv")
    parser.add_argument("--subjects", default=None,
                        help="Path to Subjects.csv (optional)")
    parser.add_argument("--out", required=True,
                        help="Output directory")
    parser.add_argument("--mode",
                        choices=["longitudinal", "test_retest", "both"],
                        default="both")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode in ("longitudinal", "both"):
        trajectories, report = load_miriad_trajectories(
            args.clinical, args.sessions, args.subjects,
        )
        (out_dir / "miriad_longitudinal_report.json").write_text(
            json.dumps(report.to_dict(), indent=2)
        )
        print(f"Longitudinal: {len(trajectories)} trajectories, "
              f"{report.n_transitions} transitions")

    if args.mode in ("test_retest", "both"):
        pairs, pair_report = load_miriad_test_retest_pairs(
            args.clinical, args.sessions,
        )
        (out_dir / "miriad_test_retest_report.json").write_text(
            json.dumps(pair_report.to_dict(), indent=2)
        )
        print(f"Test-retest: {len(pairs)} pairs, "
              f"{pair_report.n_pairs_state_identical} identical, "
              f"{pair_report.n_pairs_state_differs} differs")

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

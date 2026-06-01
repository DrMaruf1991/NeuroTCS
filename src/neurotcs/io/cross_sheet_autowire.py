"""neurotcs.io.cross_sheet_autowire -- universal, deterministic, fail-closed
resolution of real-world cohort sheets into the abstract cross-sheet ROLE
views (manifest / predictions / patients / biomarkers / attribution) that the
Layer-3b cross-sheet invariant engine consumes.

WHY THIS MODULE EXISTS
----------------------
The cross-sheet engine (neurotcs.cross_sheet.audit.audit_cross_sheet) binds
invariants to FIXED abstract sheet roles and CANONICAL column names
(e.g. role 'biomarkers', field 'amyloid_centiloid'). Real cohort exports
(ADNI / NACC / OASIS / bespoke) instead split data across many domain sheets
(amyloid PET sheet, tau PET sheet, fluid sheet, MRI sheet, ...) keyed by
(subject_id, visit), with domain-specific column names (e.g. 'centiloid_value').

Before v1.42.0 nothing translated real sheets -> roles, so in zero-config the
cross-sheet layer NEVER RAN: ~1/5 of the auditor's detection power (cross-modal
conflicts, longitudinal monotonicity reversals, genotype/phenotype coherence)
was silently dead. This module is the missing translator.

DESIGN PRINCIPLES (philosophy A: conservative / explicit / fail-closed)
-----------------------------------------------------------------------
1. DETERMINISTIC. Pure structural + exact-synonym classification. No content
   sniffing, no fuzzy matching, no probabilistic role guessing. The same input
   always yields the same role assignment -> determinism of the bundle_id is
   preserved.
2. FAIL-CLOSED / NO FALSE POSITIVES. A sheet is assigned a role ONLY when its
   structure unambiguously implies that role. Anything ambiguous is reported as
   UNRESOLVED (surfaced to the operator), never force-fit. A false role
   assignment in a clinical auditor is as damaging as a missed error, so we
   refuse to guess. This is the same line autowire_ranges draws for
   assay-calibrated measurements.
3. SURFACE, NEVER SILENTLY DROP. Every sheet is accounted for: assigned a role,
   or listed in `unresolved` with the reason. The caller surfaces both so the
   coverage manifest is honest.
4. CANONICAL-FIELD EXACTNESS. A real column is mapped to a canonical invariant
   field only on exact (normalized) synonym match. A column that cannot be
   mapped is left under its original name (invariants referencing the canonical
   name simply find the field absent and self-skip with missing-field info,
   which is the engine's documented fail-closed behavior).

The output of `build_cross_sheet_submission` is the dict that
audit_cross_sheet expects:
    {
      "manifest":   {... synthesized minimal manifest ...},
      "predictions": <DataFrame with canonical columns incl. predicted_state>,
      "patients":    <DataFrame with canonical columns incl. apoe_genotype>,
      "biomarkers":  <DataFrame: ALL measurement sheets merged on
                      (subject_id, visit_id), canonical columns>,
      "attribution": None,           # optional; absent unless a sheet supplies it
    }
plus a `CrossSheetResolution` describing exactly how every sheet was handled.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import reduce
from typing import Any

import pandas as pd

# --------------------------------------------------------------------------- #
# Normalization (shared convention with autowire_ranges)
# --------------------------------------------------------------------------- #


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


# --------------------------------------------------------------------------- #
# Identity columns
# --------------------------------------------------------------------------- #

_PID_SYNONYMS = ("subject_id", "patient_id", "rid", "ptid", "usubjid",
                 "participant_id", "id")
_VISIT_SYNONYMS = ("visit", "visit_id", "viscode", "visitnum", "event_id",
                   "visit_code", "timepoint", "wave")

# A column whose normalized name indicates a CLINICAL STATE per visit -> the
# 'predictions' role carries the per-visit state under canonical 'predicted_state'.
_STATE_SYNONYMS = ("state", "predicted_state", "clinical_state", "dx",
                   "diagnosis", "dx_group_visit", "stage", "cdr_global_state")

# Patient-level (one-row-per-subject) markers: presence of these and ABSENCE of
# a visit column indicates the 'patients' role.
_PATIENT_LEVEL_FIELDS = ("apoe_genotype", "apoe", "sex", "education_years",
                         "age_enroll", "handedness", "race", "enroll_date",
                         "app_mutation_status", "psen1_mutation_status",
                         "psen2_mutation_status", "protocol",
                         "treatment_assignment", "dx_group")


# --------------------------------------------------------------------------- #
# Canonical biomarker / patient / prediction field synonyms
# --------------------------------------------------------------------------- #
# Maps NORMALIZED real column name -> canonical invariant field name. Exact
# (normalized) match only. This is the column-level half of role resolution.
# Extend this table (never loosen to fuzzy) when a new cohort naming convention
# appears; each entry is a deliberate, reviewable assertion of equivalence.

_CANONICAL_FIELD_SYNONYMS: dict[str, str] = {
    # --- amyloid PET ---
    "amyloidcentiloid": "amyloid_centiloid",
    "centiloid": "amyloid_centiloid",
    "centiloidvalue": "amyloid_centiloid",
    "amyloidstatus": "amyloid_status",
    # --- tau PET ---
    "taupetsuvr": "tau_pet_neocortical_uptake_ratio_flortaucipir",
    "taupetneocorticaluptakeratioflortaucipir":
        "tau_pet_neocortical_uptake_ratio_flortaucipir",
    "taupetneocorticalsuvr": "tau_pet_neocortical_uptake_ratio_flortaucipir",
    # --- fluid: plasma ---
    "plasmaptau217pgml": "plasma_ptau217_pgml",
    "plasmaptau217": "plasma_ptau217_pgml",
    "plasmanflpgml": "plasma_nfl_pgml",
    "plasmanfl": "plasma_nfl_pgml",
    "plasmagfappgml": "plasma_gfap_pgml",
    "plasmagfap": "plasma_gfap_pgml",
    # --- fluid: CSF ---
    "csfptau217pgml": "csf_ptau217_pgml",
    "csfptau217": "csf_ptau217_pgml",
    "csfnflpgml": "csf_nfl_pgml",
    "csfgfappgml": "csf_gfap_pgml",
    # --- MRI volumetry ---
    "hippocampustotalcm3": "hippocampus_total_cm3",
    "hippocampustotal": "hippocampus_total_cm3",
    # --- treatment gate ---
    "treatmentflags": "treatment_flags",
    "treatmentflag": "treatment_flags",
    "treatmentassignment": "treatment_flags",
    # --- OCT / DTI / ASL / SV2A (biomarker_longitudinal_monotonicity pack) ---
    "rnflperipapillarythicknessum": "rnfl_peripapillary_thickness_um",
    "gciplmacularthicknessum": "gc_ipl_macular_thickness_um",
    "ucbjdvrhippocampus": "ucbj_dvr_hippocampus",
    "ucbjdvrneocorticalmeta": "ucbj_dvr_neocortical_meta",
    "aslcbfglobalmlper100gmin": "asl_cbf_global_ml_per_100g_min",
    "fafornix": "fa_fornix",
    "mdfornix": "md_fornix",
    # --- patient-level genomics ---
    "apoegenotype": "apoe_genotype",
    "apoe": "apoe_genotype",
    "appmutationstatus": "app_mutation_status",
    "psen1mutationstatus": "psen1_mutation_status",
    "psen2mutationstatus": "psen2_mutation_status",
    # --- sample type ---
    "sampletype": "sample_type",
    # --- clinical state (predictions role) ---
    "clinicalstate": "predicted_state",
    "state": "predicted_state",
    "predictedstate": "predicted_state",
    "dx": "predicted_state",
    "diagnosis": "predicted_state",
}


@dataclass
class CrossSheetResolution:
    """Audit-trail of how every sheet was classified. Surfaced to the operator
    so role resolution is NEVER a silent guess."""

    roles: dict[str, list[str]] = field(default_factory=dict)
    # role -> list of source sheet names that were merged into it
    unresolved: list[tuple[str, str]] = field(default_factory=list)
    # (sheet_name, reason) for sheets that could not be confidently assigned
    canonical_renames: dict[str, dict[str, str]] = field(default_factory=dict)
    # sheet_name -> {original_col: canonical_field} applied

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        for role, sheets in self.roles.items():
            if sheets:
                lines.append(f"cross_sheet role '{role}' <- {', '.join(sheets)}")
        for sheet, reason in self.unresolved:
            lines.append(f"cross_sheet UNRESOLVED sheet '{sheet}': {reason}")
        return lines


# --------------------------------------------------------------------------- #
# Column helpers
# --------------------------------------------------------------------------- #


def _find_col(cols: list[str], synonyms: tuple[str, ...]) -> str | None:
    norm_to_real = {_norm(c): c for c in cols}
    for s in synonyms:
        if _norm(s) in norm_to_real:
            return norm_to_real[_norm(s)]
    return None


def _canonicalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Rename real columns to canonical invariant field names via EXACT
    normalized synonym match. Returns (renamed_df, {original: canonical})."""
    renames: dict[str, str] = {}
    for c in df.columns:
        canon = _CANONICAL_FIELD_SYNONYMS.get(_norm(c))
        if canon and canon != c:
            renames[c] = canon
    if renames:
        df = df.rename(columns=renames)
    return df, renames


# --------------------------------------------------------------------------- #
# Sheet classification (deterministic, fail-closed)
# --------------------------------------------------------------------------- #

# Sheets that are NEVER data sheets (index / table-of-contents / answer keys).
_NON_DATA_SHEET_TOKENS = ("index", "toc", "contents", "readme", "answerkey",
                          "answer_key", "summary", "legend", "dictionary",
                          "datadictionary", "notes")


def _is_non_data_sheet(name: str) -> bool:
    n = _norm(name)
    return any(tok.replace("_", "") in n for tok in _NON_DATA_SHEET_TOKENS)


# Normalized names of NON-measurement numeric columns (bookkeeping / time
# offsets) that must NOT cause a clinical-state sheet to be misread as a
# biomarker sheet.
_NON_MEASUREMENT_NUMERIC = frozenset({
    "dayssinceenroll", "daysfromenroll", "dayssincebaseline", "monthssinceenroll",
    "visitnum", "visitnumber", "age", "ageatvisit", "yearssinceenroll",
})

# Tokens that mark a state value as CLINICAL (CN/MCI/AD continuum) vs BIOLOGICAL
# (A/T/N profile). Clinical-state sheets become the 'predictions' role; the
# biological axis is already audited by Layer-3 staging_biological and is NOT
# re-routed into cross-sheet predictions (its vocabulary would not match the
# CN/MCI/AD predicted_state invariants).
_CLINICAL_STATE_VALUES = frozenset({
    "cn", "mci", "ad", "dementia", "scd", "normal", "impaired",
    "stage0", "stage1", "stage2", "stage3", "stage4", "stage5", "stage6",
})


def _state_value_kind(df: pd.DataFrame, state_col: str) -> str:
    """Classify the state column's values as 'clinical', 'biological', or
    'unknown' by sampling distinct values. Deterministic (sorted sample)."""
    try:
        vals = [str(v) for v in df[state_col].dropna().unique()]
    except Exception:
        return "unknown"
    norm_vals = {_norm(v) for v in vals}
    if not norm_vals:
        return "unknown"
    # biological if values look like A/T/N profiles (contain a/t and +/-)
    bio_like = sum(1 for v in vals if re.fullmatch(r"[AaTtNn][+\-][AaTtNn][+\-].*", str(v).strip()))
    if bio_like >= max(1, len(vals) // 2):
        return "biological"
    clin_like = len(norm_vals & _CLINICAL_STATE_VALUES)
    if clin_like >= max(1, len(norm_vals) // 2):
        return "clinical"
    return "unknown"


def _classify_sheet(
    name: str, df: pd.DataFrame
) -> tuple[str | None, str]:
    """Return (role, reason). role in {patients, predictions, biomarkers} or
    None when the sheet cannot be confidently assigned (reason explains why).

    Fail-closed rules (philosophy A):
      - Non-data sheets (Index/TOC/Summary/AnswerKey) -> None, recognized.
      - Must have a subject-id column to be any role.
      - subject_id present, NO visit column, has >=1 patient-level field
        -> patients.
      - subject_id + visit + CLINICAL state column -> predictions.
      - subject_id + visit + BIOLOGICAL state column -> None (already audited by
        Layer-3 staging_biological; not a cross-sheet predictions role).
      - subject_id + visit + >=1 measurement column (numeric, excluding
        bookkeeping/time columns) -> biomarkers.
      - Otherwise -> None with reason (surfaced, not forced).
    """
    if _is_non_data_sheet(name):
        return None, "non-data sheet (index/toc/summary/answer-key)"

    cols = list(df.columns)
    pid = _find_col(cols, _PID_SYNONYMS)
    if pid is None:
        return None, "no subject/patient id column"

    visit = _find_col(cols, _VISIT_SYNONYMS)
    state = _find_col(cols, _STATE_SYNONYMS)

    # patient-level: identity but no per-visit axis
    if visit is None:
        has_patient_field = any(
            _norm(pf) in {_norm(c) for c in cols} for pf in _PATIENT_LEVEL_FIELDS
        )
        if has_patient_field:
            return "patients", "subject-level (id, no visit, patient fields)"
        return None, "id present but no visit and no patient-level fields"

    # measurement columns = numeric, excluding identity + state + bookkeeping
    non_id = [c for c in cols
              if c not in (pid, visit)
              and (state is None or _norm(c) != _norm(state))]
    measurement_like = [
        c for c in non_id
        if pd.api.types.is_numeric_dtype(df[c])
        and _norm(c) not in _NON_MEASUREMENT_NUMERIC
    ]

    if state is not None:
        kind = _state_value_kind(df, state)
        if kind == "biological":
            # The biological A/T/N axis is audited by Layer-3 staging_biological.
            # Do not also route it into cross-sheet predictions (vocabulary
            # mismatch with CN/MCI/AD predicted_state invariants).
            return None, ("biological-state sheet (A/T/N) -- audited by "
                          "staging_biological, not a cross-sheet predictions role")
        if len(measurement_like) == 0:
            return "predictions", "id + visit + clinical state, no measurements"
        # mixed clinical-state + measurements: route to biomarkers for cross-
        # modal checks; the state rides along canonicalized.
        return "biomarkers", "id + visit + clinical state + measurements (mixed)"

    # visit but no state column
    if len(measurement_like) == 0:
        return None, "id + visit but no state and no measurement columns"
    return "biomarkers", "id + visit + measurements"


# --------------------------------------------------------------------------- #
# Identity canonicalization for merge
# --------------------------------------------------------------------------- #


def _standardize_identity(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None, str | None]:
    """Rename subject-id -> 'patient_id' and visit -> 'visit_id' (the canonical
    join keys the cross-sheet engine groups by; the engine groups trajectories
    and per-row checks on 'patient_id'). Returns (df, pid, visit)."""
    cols = list(df.columns)
    pid = _find_col(cols, _PID_SYNONYMS)
    visit = _find_col(cols, _VISIT_SYNONYMS)
    ren: dict[str, str] = {}
    if pid and pid != "patient_id":
        ren[pid] = "patient_id"
    if visit and visit != "visit_id":
        ren[visit] = "visit_id"
    if ren:
        df = df.rename(columns=ren)
    return df, ("patient_id" if pid else None), ("visit_id" if visit else None)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def build_cross_sheet_submission(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], CrossSheetResolution]:
    """Resolve raw cohort sheets into the cross-sheet ROLE submission.

    Returns (submission, resolution). `submission` has role keys suitable for
    audit_cross_sheet; `resolution` is the audit trail (which sheet -> which
    role, what was unresolved, what columns were canonically renamed).

    Deterministic and fail-closed: ambiguous sheets are surfaced in
    resolution.unresolved rather than force-assigned.
    """
    res = CrossSheetResolution(roles={"patients": [], "predictions": [],
                                       "biomarkers": []})

    patient_frames: list[pd.DataFrame] = []
    prediction_frames: list[pd.DataFrame] = []
    biomarker_frames: list[pd.DataFrame] = []

    # Deterministic order: sort sheet names so merge order is stable.
    for name in sorted(tables.keys()):
        df = tables[name]
        if df is None or df.empty:
            res.unresolved.append((name, "empty sheet"))
            continue
        role, reason = _classify_sheet(name, df)
        if role is None:
            res.unresolved.append((name, reason))
            continue

        # canonicalize identity + fields
        std, _sid, _vid = _standardize_identity(df.copy())
        std, renames = _canonicalize_columns(std)
        if renames:
            res.canonical_renames[name] = renames

        res.roles[role].append(name)
        if role == "patients":
            patient_frames.append(std)
        elif role == "predictions":
            prediction_frames.append(std)
        else:
            biomarker_frames.append(std)

    submission: dict[str, Any] = {}

    # NOTE: the cross-sheet engine's _iter_rows() accepts ONLY list[dict] or
    # dict, NOT DataFrames (a DataFrame yields zero rows -> every invariant
    # would silently self-skip). We therefore emit list-of-record dicts for
    # every role sheet. This is the single most important correctness detail
    # in this module.

    def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
        # Replace pandas NaN with None so invariant comparisons see real nulls.
        return df.where(pd.notnull(df), None).to_dict(orient="records")

    # ---- patients: outer-merge on patient_id (one row per subject) ----
    if patient_frames:
        pat = reduce(
            lambda a, b: pd.merge(a, b, on="patient_id", how="outer",
                                  suffixes=("", "_dup")),
            patient_frames,
        ) if len(patient_frames) > 1 else patient_frames[0]
        pat = pat.loc[:, ~pat.columns.str.endswith("_dup")]
        submission["patients"] = _records(pat)

    # ---- predictions: concat (each is id+visit+state) ----
    if prediction_frames:
        pred = (pd.concat(prediction_frames, ignore_index=True)
                if len(prediction_frames) > 1 else prediction_frames[0])
        submission["predictions"] = _records(pred)

    # ---- biomarkers: OUTER MERGE all measurement sheets on (patient_id, visit_id) ----
    # This is the heart of cross-modal checking: a single biomarkers row per
    # (subject, visit) carries amyloid + tau + fluid + MRI together, so an
    # invariant comparing amyloid_centiloid vs plasma_ptau217_pgml can see both.
    if biomarker_frames:
        def _merge_bio(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
            join_keys = [k for k in ("patient_id", "visit_id")
                         if k in a.columns and k in b.columns]
            if not join_keys:
                return pd.concat([a, b], ignore_index=True)
            return pd.merge(a, b, on=join_keys, how="outer", suffixes=("", "_dup"))

        bio = (reduce(_merge_bio, biomarker_frames)
               if len(biomarker_frames) > 1 else biomarker_frames[0])
        bio = bio.loc[:, ~bio.columns.str.endswith("_dup")]

        # Derived numeric encoding for qualitative reads so numeric_conflict
        # invariants can consume them. tau_visual_read_negative_flag = 1.0 when
        # a tau visual read column records a negative read, else 0.0. This is a
        # deterministic, lossless re-expression of an existing column (NOT a new
        # measurement); absent a tau_visual_read column the flag is simply not
        # created and the dependent invariant self-skips (fail-closed).
        _tau_read_col = None
        for cand in ("tau_visual_read", "tauvisualread", "tau_read"):
            real = _find_col(list(bio.columns), (cand,))
            if real:
                _tau_read_col = real
                break
        if _tau_read_col is not None and "tau_visual_read_negative_flag" not in bio.columns:
            bio["tau_visual_read_negative_flag"] = bio[_tau_read_col].apply(
                lambda v: 1.0 if str(v).strip().lower() in ("negative", "neg", "0", "false")
                else (0.0 if v is not None and str(v).strip() != "" else None)
            )

        submission["biomarkers"] = _records(bio)

    # ---- manifest: synthesized minimal manifest so manifest-keyed invariants
    # can run. We declare only what we can verify from the resolved data. ----
    manifest: dict[str, Any] = {
        "conformance_level": "L2",  # data-only; not L3-attributed
        "declares_continuous_biomarkers": bool(biomarker_frames),
    }
    submission["manifest"] = manifest

    # attribution: absent unless a sheet supplied it (none does in zero-config).
    # Leaving it out is correct -- manifest_data_consistency will info-skip the
    # attribution-required invariant, which is the documented fail-closed path.

    return submission, res

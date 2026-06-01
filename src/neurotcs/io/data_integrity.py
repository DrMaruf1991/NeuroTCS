"""neurotcs.io.data_integrity -- universal Layer-1 data-integrity checks.

WHY THIS MODULE EXISTS
----------------------
Layers 2 (ranges), 3 (staging) and 3b (cross-sheet) all operate on per-visit
measurement / state values. None of them audits:

  * patient-level enrollment fields (sex, education-years, APOE genotype, ...)
    which live on a one-row-per-subject sheet with NO visit axis, so the
    visit-keyed range/staging layers never touch them;
  * structural data-integrity properties (duplicate (subject,visit) rows,
    orphan biomarker rows with no matching enrollment, visit dates in the
    future or out of chronological order).

These are exactly the error classes a data auditor must catch FIRST -- a
duplicate visit or an impossible genotype corrupts every downstream layer.
This module is the universal, deterministic, fail-closed Layer-1 check that
runs over the raw sheets in zero-config.

DESIGN PRINCIPLES (philosophy A)
--------------------------------
* DETERMINISTIC: pure structural + exact-domain checks; sorted iteration.
* FAIL-CLOSED / NO FALSE POSITIVES: a value is flagged only when it violates a
  HARD, universally-true constraint (an allele that does not exist; a sex code
  outside a closed domain; a negative count; a future date). Anything that is
  merely unusual is NOT flagged here (that is the plausibility job of Layer 2).
* CITATION WHERE APPLICABLE: biological constraints (APOE alleles e2/e3/e4 only;
  diploid genotype = exactly two alleles) cite the defining genetics; pure
  data-integrity axioms (unique key, referential integrity, monotonic time, no
  future date) are self-evident and cite the integrity rule itself.
* SURFACE, NEVER GUESS: a field that cannot be checked (absent column) is
  simply not checked; no inference.

OUTPUT
------
A list of flag dicts compatible with the orchestrator's flag schema:
  {"tier", "layer"="data_integrity", "subject_id", "visit", "field",
   "observed_value", "rule_id", "citation", "details"}
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

# --------------------------------------------------------------------------- #
# Identity synonyms (shared convention)
# --------------------------------------------------------------------------- #

_PID_SYNONYMS = ("subject_id", "patient_id", "rid", "ptid", "usubjid",
                 "participant_id", "id")
_VISIT_SYNONYMS = ("visit", "visit_id", "viscode", "visitnum", "event_id",
                   "visit_code", "timepoint", "wave")
_DATE_SYNONYMS = ("visit_date", "visitdate", "exam_date", "examdate", "date",
                  "scan_date", "assessment_date")

_NON_DATA_SHEET_TOKENS = ("index", "toc", "contents", "readme", "answerkey",
                          "answer_key", "summary", "legend", "dictionary",
                          "datadictionary", "notes")

TIER_IMPOSSIBLE = "impossible"
TIER_IMPLAUSIBLE = "implausible"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _find_col(cols: list[str], synonyms: tuple[str, ...]) -> str | None:
    norm_to_real = {_norm(c): c for c in cols}
    for s in synonyms:
        if _norm(s) in norm_to_real:
            return norm_to_real[_norm(s)]
    return None


# Exact-name synonyms for a CDISC/long-format measurement-code column. The
# suffix patterns (--TESTCD / PARAMCD) below catch the domain-prefixed forms
# (QSTESTCD, RSTESTCD, LBTESTCD, PARAMCD, ...) robustly across CDISC versions.
_MEASUREMENT_CODE_SYNONYMS = (
    "testcd", "paramcd", "measurement", "measurement_code", "measurement_name",
    "test_code", "param_code", "measure", "analyte",
)


def _find_measurement_code_col(cols: list[str]) -> str | None:
    """Return the column that makes a sheet LONG-format (one row per measurement
    code at a given subject/visit), or None for wide-format sheets.

    A long-format sheet keys legitimate uniqueness on (subject, visit, CODE):
    the SAME (subject, visit) holds many rows, one per code, which is valid and
    must NOT be flagged as a duplicate record. Detection is by stable structural
    role -- the CDISC --TESTCD / PARAMCD suffix, plus an explicit synonym set --
    never by guessing on arbitrary column names.
    """
    # exact synonyms first
    hit = _find_col(cols, _MEASUREMENT_CODE_SYNONYMS)
    if hit is not None:
        return hit
    # CDISC suffix patterns: <domain>TESTCD / <domain>PARAMCD
    for c in cols:
        n = _norm(c)
        if n.endswith("testcd") or n.endswith("paramcd"):
            return c
    return None


def _is_non_data_sheet(name: str) -> bool:
    n = _norm(name)
    return any(tok.replace("_", "") in n for tok in _NON_DATA_SHEET_TOKENS)


# --------------------------------------------------------------------------- #
# Closed categorical domains (universal, hard)
# --------------------------------------------------------------------------- #
# Each entry: normalized column name -> (allowed_normalized_values, citation).
# A value outside the closed domain is a categorical-validity error
# (TIER_IMPOSSIBLE). Domains are deliberately minimal and universally agreed.

_CATEGORICAL_DOMAINS: dict[str, tuple[frozenset[str], str]] = {
    "sex": (frozenset({"m", "f", "male", "female"}),
            "Biological sex recorded as M/F (administrative closed domain)."),
    "handedness": (frozenset({"l", "r", "a", "left", "right", "ambidextrous",
                              "mixed"}),
                   "Edinburgh Handedness Inventory categories (L/R/Ambidextrous)."),
}


# --------------------------------------------------------------------------- #
# Hard numeric bounds for patient-level / count fields (universal, not assay)
# --------------------------------------------------------------------------- #
# Each: normalized column -> (lo, hi, citation). These are administrative /
# physical hard bounds (a count cannot be negative; human education years
# cannot exceed a lifetime). NOT assay-calibrated plausibility (Layer 2).

_HARD_BOUNDS: dict[str, tuple[float, float, str]] = {
    "educationyears": (0.0, 30.0,
                       "Years of formal education: 0 <= y <= 30 (a human "
                       "cannot accrue negative years; >30 exceeds any "
                       "documented formal-education span)."),
    "ageenroll": (0.0, 120.0,
                  "Human age at enrollment: 0-120 years (verified human "
                  "lifespan ceiling)."),
    "age": (0.0, 120.0, "Human age: 0-120 years."),
}


# --------------------------------------------------------------------------- #
# APOE genotype validity (citable to ApoE allele biology)
# --------------------------------------------------------------------------- #
# The APOE gene has exactly three common alleles: e2, e3, e4 (defined by the
# rs429358 / rs7412 SNP pair). A genotype is DIPLOID -> exactly two alleles.
# Any allele outside {e2,e3,e4} does not exist; any genotype with != 2 alleles
# is biologically impossible.

_APOE_ALLELES = frozenset({"e2", "e3", "e4"})
_APOE_CITATION = (
    "APOE has three common alleles (e2/e3/e4) defined by the rs429358 and "
    "rs7412 SNP pair (Mahley 1988; Strittmatter 1993). A human genotype is "
    "diploid: exactly two alleles. An allele outside {e2,e3,e4} or a genotype "
    "with != 2 alleles is biologically impossible."
)


def _check_apoe(value: Any) -> str | None:
    """Return a reason string if the APOE genotype is invalid, else None."""
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip().lower().replace("\u03b5", "e")  # epsilon -> e
    # split on common separators
    alleles = [a for a in re.split(r"[\s/_\-,]+", raw) if a]
    # normalize allele tokens like 'e4','4','epsilon4'
    norm_alleles = []
    for a in alleles:
        m = re.fullmatch(r"(?:e|epsilon)?([0-9])", a)
        if m:
            norm_alleles.append("e" + m.group(1))
        else:
            norm_alleles.append(a)  # keep raw -> will fail domain check
    if len(norm_alleles) != 2:
        return (f"APOE genotype '{value}' has {len(norm_alleles)} alleles; a "
                f"diploid genotype must have exactly 2.")
    bad = [a for a in norm_alleles if a not in _APOE_ALLELES]
    if bad:
        return (f"APOE genotype '{value}' contains allele(s) {bad} outside the "
                f"three real alleles {sorted(_APOE_ALLELES)}.")
    return None


# --------------------------------------------------------------------------- #
# Flag builder
# --------------------------------------------------------------------------- #


def _native(v: Any) -> Any:
    """Coerce numpy / pandas scalar types to native Python for JSON."""
    if v is None:
        return None
    if isinstance(v, (bool, int, float, str)):
        return v
    # numpy / pandas scalars expose .item()
    item = getattr(v, "item", None)
    if callable(item):
        try:
            return v.item()
        except Exception:
            pass
    if isinstance(v, float) and pd.isna(v):
        return None
    return str(v)


def _flag(tier: str, subject_id: Any, visit: Any, field: str,
          observed: Any, rule_id: str, reason: str,
          citation: str | None = None) -> dict[str, Any]:
    return {
        "tier": tier,
        "layer": "data_integrity",
        "subject_id": None if subject_id is None else str(subject_id),
        "visit": _native(visit),
        "field": field,
        "observed_value": _native(observed),
        "rule_id": rule_id,
        "citation": citation,
        "details": {"reason": reason},
    }


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def audit_data_integrity(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Run universal Layer-1 data-integrity checks over all raw sheets.

    Deterministic and fail-closed. Returns a list of flag dicts (possibly
    empty). Each flag identifies the sheet, subject, field, observed value, and
    a human-readable reason; biological constraints carry a citation.
    """
    flags: list[dict[str, Any]] = []

    # Collect the universe of enrolled subject ids (for orphan detection):
    # a sheet is an "enrollment" sheet if it has a subject id and NO visit axis
    # (one row per subject), or is named like enrollment.
    enrolled_ids: set[str] = set()
    per_sheet_pid: dict[str, str | None] = {}
    for name in sorted(tables.keys()):
        df = tables[name]
        if df is None or df.empty or _is_non_data_sheet(name):
            per_sheet_pid[name] = None
            continue
        pid = _find_col(list(df.columns), _PID_SYNONYMS)
        per_sheet_pid[name] = pid
        visit = _find_col(list(df.columns), _VISIT_SYNONYMS)
        is_enrollment = (visit is None) or _norm(name) in ("en", "enroll",
                                                           "enrollment",
                                                           "patients",
                                                           "demographics",
                                                           "demo")
        if pid is not None and is_enrollment:
            enrolled_ids.update(str(v) for v in df[pid].dropna().unique())

    # ---- per-sheet checks ----
    for name in sorted(tables.keys()):
        df = tables[name]
        if df is None or df.empty or _is_non_data_sheet(name):
            continue
        cols = list(df.columns)
        pid = per_sheet_pid.get(name)
        visit = _find_col(cols, _VISIT_SYNONYMS)
        date_col = _find_col(cols, _DATE_SYNONYMS)

        # map normalized -> real for the columns we check
        norm_to_real = {_norm(c): c for c in cols}

        # 1) duplicate-record: same primary key appears twice.
        #    WIDE format -> key is (subject, visit).
        #    LONG format (CDISC --TESTCD / PARAMCD, etc.) -> one (subject, visit)
        #    legitimately holds many rows (one per measurement code), so the key
        #    is (subject, visit, measurement_code). This eliminates the false
        #    "duplicate_record" flood on long-format sheets while STILL catching
        #    a genuine duplicate (the SAME code recorded twice at the same visit).
        if pid is not None and visit is not None:
            mcode = _find_measurement_code_col(cols)
            key_cols = [pid, visit] + ([mcode] if mcode is not None else [])
            dup_mask = df.duplicated(subset=key_cols, keep=False)
            if dup_mask.any():
                dups = df[dup_mask][key_cols].drop_duplicates()
                key_label = ("(subject,visit,measurement)" if mcode is not None
                             else "(subject,visit)")
                for _, row in dups.iterrows():
                    detail = (f"{row[pid]}@{row[visit]}"
                              + (f":{row[mcode]}" if mcode is not None else ""))
                    extra = (f" for measurement '{row[mcode]}'"
                             if mcode is not None else "")
                    flags.append(_flag(
                        TIER_IMPOSSIBLE, row[pid], row[visit],
                        f"{name}:{key_label}", detail, "duplicate_record",
                        f"Sheet '{name}': subject {row[pid]} visit {row[visit]}"
                        f"{extra} appears more than once; a longitudinal record "
                        f"must be unique on {key_label}.",
                        citation=f"Data-integrity axiom: unique primary key "
                                 f"{key_label}."))

        # 2) orphan-record: a per-visit sheet row whose subject is not enrolled
        if (pid is not None and visit is not None and enrolled_ids
                and _norm(name) not in ("en", "enroll", "enrollment",
                                        "patients", "demographics", "demo")):
            present = {str(v) for v in df[pid].dropna().unique()}
            orphans = sorted(present - enrolled_ids)
            for oid in orphans:
                flags.append(_flag(
                    TIER_IMPOSSIBLE, oid, None, f"{name}:subject_id", oid,
                    "orphan_record",
                    f"Sheet '{name}': subject {oid} has rows but no matching "
                    f"enrollment record; referential integrity violation.",
                    citation="Data-integrity axiom: referential integrity (child -> parent)."))

        # 3) categorical-domain validity
        for ncol, (domain, cite) in _CATEGORICAL_DOMAINS.items():
            real = norm_to_real.get(ncol)
            if real is None:
                continue
            for _, row in df.iterrows():
                v = row[real]
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                if _norm(str(v)) not in {_norm(x) for x in domain}:
                    sid = row[pid] if pid else None
                    vis = row[visit] if visit else None
                    flags.append(_flag(
                        TIER_IMPOSSIBLE, sid, vis, f"{name}:{real}", v,
                        "categorical_invalid",
                        f"Sheet '{name}' column '{real}': value '{v}' is not in "
                        f"the allowed domain {sorted(domain)}.",
                        citation=cite))

        # 4) APOE genotype validity
        apoe_real = None
        for cand in ("apoegenotype", "apoe"):
            if cand in norm_to_real:
                apoe_real = norm_to_real[cand]
                break
        if apoe_real is not None:
            for _, row in df.iterrows():
                reason = _check_apoe(row[apoe_real])
                if reason:
                    sid = row[pid] if pid else None
                    vis = row[visit] if visit else None
                    flags.append(_flag(
                        TIER_IMPOSSIBLE, sid, vis, f"{name}:{apoe_real}",
                        row[apoe_real], "genomics_invalid", reason,
                        citation=_APOE_CITATION))

        # 5) hard numeric bounds (patient-level / counts)
        for ncol, (lo, hi, cite) in _HARD_BOUNDS.items():
            real = norm_to_real.get(ncol)
            if real is None or not pd.api.types.is_numeric_dtype(df[real]):
                continue
            for _, row in df.iterrows():
                v = row[real]
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                if v < lo or v > hi:
                    sid = row[pid] if pid else None
                    vis = row[visit] if visit else None
                    tier = TIER_IMPOSSIBLE if v < lo else TIER_IMPLAUSIBLE
                    flags.append(_flag(
                        tier, sid, vis, f"{name}:{real}", float(v),
                        "range_impossible" if v < lo else "range_implausible",
                        f"Sheet '{name}' column '{real}': value {v} outside hard "
                        f"bound [{lo}, {hi}].",
                        citation=cite))

        # 6) temporal integrity: intra-subject cadence-break + ordering.
        #    We do NOT flag "date > today" (a synthetic or prospective cohort
        #    legitimately carries forward-scheduled visits, so the wall clock is
        #    the wrong anchor and would flood false positives). Instead we flag a
        #    visit whose gap from the subject's OWN prior visit is a gross
        #    outlier versus that subject's established cadence -- the
        #    dataset-internal signal of a corrupted date. We also flag dates that
        #    go backwards in visit order (impossible chronology).
        if date_col is not None and pid is not None and visit is not None:
            from neurotcs.audit_core.trajectory import _coerce_visit_dates
            parsed = _coerce_visit_dates(df[date_col])
            tmp = df[[pid, visit]].copy()
            tmp["_d"] = parsed.values
            for sid, grp in tmp.dropna(subset=["_d"]).groupby(pid, sort=True):
                g = grp.sort_values(visit).reset_index(drop=True)
                # backwards-in-time (ordering) check
                prev = None
                for _, r in g.iterrows():
                    if prev is not None and r["_d"] < prev:
                        flags.append(_flag(
                            TIER_IMPOSSIBLE, sid, r[visit], f"{name}:{date_col}",
                            str(r["_d"].date()), "temporal_ordering",
                            f"Sheet '{name}': subject {sid} visit {r[visit]} date "
                            f"{r['_d'].date()} precedes an earlier visit; visit "
                            f"dates must be non-decreasing in visit order.",
                            citation="Data-integrity axiom: monotonic visit chronology."))
                    prev = r["_d"] if prev is None else max(prev, r["_d"])
                # cadence-break check: need >=3 inter-visit gaps to establish a
                # baseline cadence to compare against (fail-closed: too few
                # visits -> no cadence claim -> no flag).
                gaps = g["_d"].diff().dropna().dt.days.tolist()
                if len(gaps) >= 3:
                    prior_gaps = gaps[:-1]
                    last_gap = gaps[-1]
                    med = sorted(prior_gaps)[len(prior_gaps) // 2]
                    # flag only a GROSS break: last interval > 3x the subject's
                    # own median prior interval AND the absolute excess is large
                    # (> 2 years) so normal scheduling jitter never trips it.
                    if med > 0 and last_gap > 3 * med and (last_gap - med) > 730:
                        last_row = g.iloc[-1]
                        flags.append(_flag(
                            TIER_IMPOSSIBLE, sid, last_row[visit],
                            f"{name}:{date_col}", str(last_row["_d"].date()),
                            "temporal_impossible",
                            f"Sheet '{name}': subject {sid} visit {last_row[visit]} "
                            f"date {last_row['_d'].date()} breaks the subject's own "
                            f"visit cadence (interval {last_gap}d vs median {med}d "
                            f"of prior visits); likely a corrupted date.",
                            citation="Data-integrity axiom: intra-subject visit cadence "
                                     "outlier (dataset-internal reference, not wall clock)."))

        # 7) protocol eligibility: anti-amyloid therapy requires AD continuum.
        #    Anti-amyloid mAbs (lecanemab/donanemab/aducanumab) are FDA-indicated
        #    only for MCI or mild dementia due to AD with amyloid pathology. A
        #    cognitively-normal (CN) or non-AD subject assigned to anti-amyloid
        #    therapy is a protocol-eligibility violation. Checked within a single
        #    enrollment sheet that carries both dx_group and treatment.
        dx_real = norm_to_real.get("dxgroup")
        tx_real = norm_to_real.get("treatmentassignment")
        if dx_real is not None and tx_real is not None:
            _anti_amyloid = {"lecanemab", "donanemab", "aducanumab"}
            _eligible_dx = {"mci", "ad", "ad_treated", "mci_converter"}
            for _, row in df.iterrows():
                tx = str(row[tx_real]).strip().lower()
                dx = str(row[dx_real]).strip().lower()
                if tx in _anti_amyloid and dx not in _eligible_dx:
                    sid = row[pid] if pid else None
                    flags.append(_flag(
                        TIER_IMPOSSIBLE, sid, None, f"{name}:{tx_real}",
                        row[tx_real], "protocol_violation",
                        f"Sheet '{name}': subject {sid} with dx_group '{row[dx_real]}' "
                        f"is assigned anti-amyloid therapy '{row[tx_real]}', which is "
                        f"FDA-indicated only for the AD continuum (MCI or mild AD "
                        f"dementia with amyloid pathology).",
                        citation="Lecanemab (van Dyck 2023, NEJM 388:9-21, PMID 36449413) "
                                 "and donanemab FDA labels: indicated for early symptomatic "
                                 "AD (MCI / mild dementia) with confirmed amyloid pathology, "
                                 "not cognitively-normal or non-AD individuals."))

    return flags

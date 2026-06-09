#!/usr/bin/env python3
"""NeuroTCS AD Challenge -- world-class synthetic benchmark generator.

PURPOSE
-------
Produce a fully reproducible, citation-anchored synthetic AD trial cohort plus a
matching answer key, for testing the NeuroTCS auditor end to end. This is a
SOFTWARE TEST HARNESS, not clinical evidence: it proves the detector behaves
correctly against known-injected errors. It is NOT a substitute for the Arm A
clinical-validation study (real flag precision on DUA-gated data with blinded
adjudication).

DESIGN PRINCIPLES (the "world-class, no partial fix, no fabrication" contract)
------------------------------------------------------------------------------
1. DETERMINISTIC. A fixed seed => byte-identical dataset + key on every run.
   Every value is produced by an inspectable rule below; nothing is hand-typed.
2. EVERY ERROR TYPE IS CITATION-ANCHORED. No invented thresholds. In particular
   there is NO "implausibly fast progression" rate injection (Jack 2024 defines
   no minimum time-to-stage, so any rate cutpoint would be fabricated). Fast
   biology, where present, is modeled as a literature-licensed ORDERING
   violation (tau-positive before amyloid-positive within a subject, which
   Jack 2024 forbids on the AD pathway) -- not a synthetic time floor.
3. TIME-CONSISTENT. months_since_baseline is strictly increasing with visit
   index for every subject; visit-label order and time order never diverge
   (fixing the integrity bug present in the prior LLM-authored file).
4. BOTH CARVE-OUTS ARE EXERCISED BY DATA (not only unit tests):
   - a backward biological-stage step that lands ON a TRAC row  -> must NOT flag
     (treatment-related amyloid clearance, La Joie 2025);
   - a clean pre-dementia clinical reversion (stage 3->2 / 2->1) -> must NOT
     flag (reversion within the pre-dementia range is admissible).
5. SELF-CHECKED. A reference checker re-scans the finished data and asserts that
   every rule-violating row is documented in the key (zero uncovered) and that
   no Hard_Negatives_Valid row is itself a rule violation.

STAGING SEMANTICS (match the verified NeuroTCS production packs)
----------------------------------------------------------------
Clinical numeric stages 0-6  (ad/niaaa_2024_clinical_numeric; Jack 2024 Table 6,
  PMID 38934362): inadmissible = regression OUT of dementia (4/5/6 -> strictly
  lower). Pre-dementia reversion (within 0-3) is admissible.
Biological letters A<B<C<D  (ad/niaaa_2024_biological_letter; Jack 2024 PET-based
  staging): backward letter step inadmissible UNLESS the regressing visit carries
  trac_status == "TRAC" (La Joie 2025 carve-out, DOI 10.1002/alz.70997).

USAGE
-----
    python generate_benchmark.py --seed 20260609 --out .
produces:
    NeuroTCS_AD_Challenge_Dataset.csv
    NeuroTCS_AD_Challenge_AnswerKey.csv
    NeuroTCS_AD_Challenge_HardNegatives.csv
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Citation registry: every error type maps to a real, verifiable source.
# These are the ONLY rules the key may invoke. No rate/time-floor rule exists.
# --------------------------------------------------------------------------- #
CITES = {
    "clinical_stage_regression": (
        "Jack 2024 Table 6 (PMID 38934362; DOI 10.1002/alz.13859): clinical "
        "stages 4-6 are dementia of increasing severity; established dementia is "
        "not expected to revert to a milder stage. Regression OUT of dementia "
        "(4/5/6 -> lower) is inadmissible."
    ),
    "biological_stage_regression": (
        "Jack 2024 (PMID 38934362; DOI 10.1002/alz.13859): PET-based biological "
        "staging A<B<C<D is monotonic in tau burden among A+ individuals; a "
        "backward letter step is inadmissible UNLESS treatment-related amyloid "
        "clearance applies (La Joie 2025, DOI 10.1002/alz.70997)."
    ),
    "atn_ordering_violation": (
        "Jack 2024 (PMID 38934362): on the AD pathway amyloid (A) precedes tau "
        "(T); a tau-positive, amyloid-negative biological profile is not a valid "
        "point on the AD continuum (A must be present for staging)."
    ),
    "csf_abeta_unit_shift": (
        "Standard CSF Abeta42 reporting is in pg/mL (hundreds-to-thousands). A "
        "value < 10 indicates a unit error (e.g. ng/mL mis-entered as pg/mL)."
    ),
    "nfl_decimal_shift": (
        "Plasma NfL is reported in pg/mL; an order-of-magnitude (10x/100x) shift "
        "produces a physiologically impossible value."
    ),
    "negative_biomarker": (
        "Concentration and volume biomarkers cannot be negative."
    ),
    "invalid_apoe_genotype": (
        "APOE genotype alleles are drawn from {e2,e3,e4}; tokens such as e5/e6 "
        "are invalid (no such allele)."
    ),
    "out_of_range_cognition": (
        "MMSE is bounded 0-30; values outside [0,30] are impossible."
    ),
    "cdr_dementia_contradiction": (
        "A clinical dementia stage (4-6) with CDR global = 0 (no impairment) is "
        "internally contradictory (NIA-AA 2024 integrated staging)."
    ),
    "amyloid_centiloid_contradiction": (
        "Amyloid-positive (A+) status with a sub-threshold Centiloid value (< 25 "
        "CL) is contradictory (Cogswell/Centiloid Working Group; A+ requires "
        ">= ~25 CL)."
    ),
    "duplicate_visit_conflict": (
        "Two rows for the same (subject, visit) with conflicting values violate "
        "the one-row-per-visit key."
    ),
    "out_of_order_visit_date": (
        "visit_date must be non-decreasing with visit index within a subject."
    ),
}

# Hard-negative classes: rows that LOOK suspicious but are VALID -> must NOT flag.
HARD_NEG = {
    "valid_trac_clearance": (
        "Amyloid clearance (A+ -> A-) on active anti-amyloid therapy is a valid "
        "treatment effect, not an anomaly (La Joie 2025, DOI 10.1002/alz.70997)."
    ),
    "valid_trac_biological_regression": (
        "A backward biological-stage step on a TRAC row is valid treatment-"
        "related clearance (La Joie 2025); the carve-out must suppress the flag."
    ),
    "valid_pre_dementia_reversion": (
        "Clinical reversion within the pre-dementia range (stage 3->2 or 2->1) "
        "is admissible (MCI reversion is documented); must NOT be flagged."
    ),
    "valid_offdiagonal_stage": (
        "Off-diagonal biological/clinical combinations (resilient or copathologic) "
        "are explicitly recognized by Jack 2024 and are NOT errors."
    ),
}

CLINICAL_STAGES = ["0", "1", "2", "3", "4", "5", "6"]
BIO_LETTERS = ["A", "B", "C", "D"]
BIO_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}
DEMENTIA = {"4", "5", "6"}


# (clean-cohort construction + injection + key + reference-checker follow in
#  the next sections, appended below.)


# --------------------------------------------------------------------------- #
# Clean cohort construction
# --------------------------------------------------------------------------- #
# Biological -> expected clinical band (the AA-2024 diagonal). Off-diagonal is
# allowed (resilient/copathologic) but the clean baseline mostly follows it.
_BIO_TO_CLIN = {"A": ["1", "2"], "B": ["2", "3"], "C": ["3", "4"], "D": ["4", "5", "6"]}

_GROUPS = ["sporadic_early", "sporadic_late", "ADAD_DSAD", "control"]


def _centiloid_for(bio: str, rng: np.random.Generator) -> float:
    """Centiloid by biological stage (A+ => >=25). Controls/A- handled by caller."""
    base = {"A": 35, "B": 60, "C": 85, "D": 110}[bio]
    return round(float(base + rng.normal(0, 8)), 1)


def _biomarkers_for(bio: str, clin: str, amyloid_pos: bool,
                    rng: np.random.Generator) -> dict:
    """Stage-consistent synthetic biomarker panel. Values are drawn from
    documented-magnitude distributions; they are SYNTHETIC, not real assay
    readings. All within physiologic range for a clean (un-injected) row."""
    r = BIO_RANK[bio]
    cl = int(clin)
    centiloid = _centiloid_for(bio, rng) if amyloid_pos else round(float(rng.uniform(2, 18)), 1)
    return {
        "amyloid_status": "A+" if amyloid_pos else "A-",
        "centiloid_value": centiloid,
        "tau_pet_status": "T+" if r >= 1 else "T-",
        "tau_pet_stage": ["T-", "T2MTL", "T2MOD", "T2HIGH"][r],
        "tau_pet_suvr_metaroi": round(float(1.0 + 0.35 * r + rng.normal(0, 0.05)), 3),
        "csf_abeta42_40_ratio": round(float(max(0.01, 0.085 - 0.012 * r + rng.normal(0, 0.004))), 4),
        "csf_abeta42_pgml": round(float(max(50, 900 - 130 * r + rng.normal(0, 40))), 1),
        "csf_ptau181_pgml": round(float(max(5, 18 + 9 * r + rng.normal(0, 3))), 1),
        "plasma_ptau217_pgml": round(float(max(0.05, 0.20 + 0.22 * r + rng.normal(0, 0.03))), 3),
        "plasma_ptau181_pgml": round(float(max(0.5, 1.6 + 0.8 * r + rng.normal(0, 0.2))), 2),
        "plasma_abeta42_40_ratio": round(float(max(0.01, 0.060 - 0.006 * r + rng.normal(0, 0.003))), 4),
        "mtbr_tau243_csf": round(float(max(0.1, 0.8 + 0.5 * r + rng.normal(0, 0.1))), 3),
        "ptau205_csf": round(float(max(0.1, 0.5 + 0.4 * r + rng.normal(0, 0.08))), 3),
        "plasma_nfl_pgml": round(float(max(2, 12 + 7 * cl + rng.normal(0, 3))), 1),
        "plasma_gfap_pgml": round(float(max(20, 90 + 35 * r + rng.normal(0, 15))), 1),
        "hippocampal_volume_total_mm3": round(float(max(2000, 7200 - 380 * cl + rng.normal(0, 150))), 1),
        "mean_cortical_thickness_mm": round(float(max(1.5, 2.75 - 0.07 * cl + rng.normal(0, 0.03))), 3),
        "total_intracranial_volume_eTIV_cm3": round(float(1500 + rng.normal(0, 90)), 1),
        "wmh_total_volume_ml": round(float(max(0.1, 3 + 1.2 * cl + rng.normal(0, 1.5))), 2),
        "fazekas_combined_score": int(np.clip(round(0.6 * cl + rng.normal(0, 0.7)), 0, 6)),
        "asyn_saa_status": rng.choice(["negative", "positive"], p=[0.82, 0.18]),
        "mmse_total": int(np.clip(round(29 - 2.7 * cl + rng.normal(0, 1.2)), 0, 30)),
        "moca_total": int(np.clip(round(28 - 2.9 * cl + rng.normal(0, 1.3)), 0, 30)),
        "cdr_global_score": float({0: 0.0, 1: 0.0, 2: 0.5, 3: 0.5, 4: 1.0, 5: 2.0, 6: 3.0}.get(cl, 0.0)),
        "cdr_sb_sum_boxes": round(float(np.clip(0.9 * cl + rng.normal(0, 0.6), 0, 18)), 1),
        "adas_cog_13_total": round(float(np.clip(8 + 5.5 * cl + rng.normal(0, 2.5), 0, 85)), 1),
        "faq_total": int(np.clip(round(2.5 * max(0, cl - 2) + rng.normal(0, 1.2)), 0, 30)),
    }


def _aria_fields(on_drug: bool, rng: np.random.Generator) -> dict:
    """ARIA fields. Clean rows are internally consistent (grade matches count/size)."""
    if on_drug and rng.random() < 0.18:
        grade = rng.choice([1, 2], p=[0.7, 0.3])
        dim = round(float(rng.uniform(0.3, 2.5) * grade), 2)
        micro_inc = int(rng.integers(0, 3))
        return {
            "aria_e_grade": grade, "aria_e_max_dimension_cm": dim,
            "aria_h_micro_incident": micro_inc, "aria_h_micro_cumulative": micro_inc,
            "aria_h_siderosis_count": int(rng.integers(0, 2)),
            "aria_overall_severity": ["none", "mild", "moderate"][grade],
            "macrohemorrhage_flag": 0,
        }
    return {
        "aria_e_grade": 0, "aria_e_max_dimension_cm": 0.0,
        "aria_h_micro_incident": 0, "aria_h_micro_cumulative": 0,
        "aria_h_siderosis_count": 0, "aria_overall_severity": "none",
        "macrohemorrhage_flag": 0,
    }


def _neuropath(bio: str, rng: np.random.Generator) -> dict:
    r = BIO_RANK[bio]
    return {
        "braak_nft_stage": int(np.clip(round(1.5 * r + rng.normal(0, 0.6)), 0, 6)),
        "thal_amyloid_phase": int(np.clip(round(1.2 * r + 1 + rng.normal(0, 0.5)), 0, 5)),
        "cerad_neuritic_plaque_score": int(np.clip(round(0.9 * r + rng.normal(0, 0.5)), 0, 3)),
    }


def _build_clean_trajectory(sid: str, group: str, rng: np.random.Generator) -> list[dict]:
    """One subject: monotonic biological + clinical progression, time-consistent.

    months_since_baseline strictly increases with visit index. Biological stage
    is non-decreasing (A->B->C->D, possibly staying). Clinical stage is
    non-decreasing too (clean baseline never spontaneously regresses)."""
    n_visits = int(rng.integers(4, 9))  # 4-8 visits
    # starting biological stage by group
    if group == "control":
        start_bio_idx = 0
        amyloid_pos = False
    elif group == "ADAD_DSAD":
        start_bio_idx = int(rng.integers(0, 2))
        amyloid_pos = True
    else:
        start_bio_idx = int(rng.integers(0, 3))
        amyloid_pos = True

    # monotonic biological progression across visits
    bio_idx = start_bio_idx
    rows = []
    months = 0
    clin_floor = 0  # clinical stage is non-decreasing in the clean baseline
    for v in range(n_visits):
        if v > 0:
            months += int(rng.integers(6, 14))  # 6-13 months between visits
            # chance to advance one biological stage (non-decreasing)
            if amyloid_pos and bio_idx < 3 and rng.random() < 0.45:
                bio_idx += 1
        bio = BIO_LETTERS[bio_idx] if amyloid_pos else "A"
        if not amyloid_pos:
            # controls: not on AD pathway; biological_stage blank, clinical low
            clin_val = int(np.clip(round(rng.normal(0.3, 0.5)), 0, 1))
            clin = str(max(clin_floor, clin_val))
            clin_floor = int(clin)
            bio_letter = ""  # blank => does not participate in biological staging
        else:
            clin_candidate = int(rng.choice(_BIO_TO_CLIN[bio]))
            clin_val = max(clin_floor, clin_candidate)  # non-decreasing
            clin = str(clin_val)
            clin_floor = clin_val
            bio_letter = bio
        amyloid_row = amyloid_pos
        bm = _biomarkers_for(bio if amyloid_pos else "A", clin, amyloid_row, rng)
        npath = _neuropath(bio if amyloid_pos else "A", rng)
        on_drug = group in ("sporadic_early", "sporadic_late") and rng.random() < 0.5
        aria = _aria_fields(on_drug, rng)
        _dx = {0: "CN", 1: "CN", 2: "SMC", 3: "MCI", 4: "AD", 5: "AD", 6: "AD"}[int(clin)]
        row = {
            "subject_id": sid,
            "group": group,
            "treatment_arm": ("active" if on_drug else rng.choice(["placebo", "none"])),
            "drug_dose_mg": (10.0 if on_drug else 0.0),
            "visit": v,
            "viscode": f"v{v:02d}",
            "visit_date": pd.Timestamp("2020-01-01") + pd.to_timedelta(months * 30, unit="D"),
            "months_since_baseline": months,
            "age_years": None,  # filled per-subject below
            "sex": None,
            "education_years": None,
            "clinical_dx": _dx,
            "clinical_stage": clin,
            "biological_stage": bio_letter,
            "at2_notation": (f"A+T2({bm['tau_pet_stage']})+" if amyloid_row and bio_letter not in ("", "A")
                             else ("A+" if amyloid_row else "A-")),
            "integrated_stage": (f"{clin}{bio_letter}" if bio_letter else clin),
            "apoe_genotype": None,
            **bm,
            "map_mmhg": round(float(rng.normal(95, 8)), 1),
            "anticoagulant_use": int(rng.random() < 0.1),
            **aria,
            "trac_status": "",  # set only on injected/hard-neg TRAC rows
            "data_source": "synthetic_benchmark",
            "row_uid": f"{sid}|v{v:02d}",
            **npath,
        }
        rows.append(row)
    # per-subject constants
    age0 = float(np.clip(rng.normal(71, 8), 50, 92))
    sex = rng.choice(["M", "F"])
    edu = int(np.clip(round(rng.normal(15, 3)), 6, 22))
    e1 = rng.choice(["e2", "e3", "e4"], p=[0.1, 0.6, 0.3])
    e2 = rng.choice(["e2", "e3", "e4"], p=[0.1, 0.6, 0.3])
    apoe = f"{e1}/{e2}"
    for row in rows:
        row["age_years"] = round(age0 + row["months_since_baseline"] / 12.0, 1)
        row["sex"] = sex
        row["education_years"] = edu
        row["apoe_genotype"] = apoe
    return rows


def build_clean_cohort(n_subjects: int, rng: np.random.Generator) -> pd.DataFrame:
    rows: list[dict] = []
    for i in range(n_subjects):
        sid = f"NTCS-{1000 + i}"
        group = rng.choice(_GROUPS, p=[0.4, 0.3, 0.12, 0.18])
        rows.extend(_build_clean_trajectory(sid, group, rng))
    df = pd.DataFrame(rows)
    return df


# --------------------------------------------------------------------------- #
# Injection layer
# --------------------------------------------------------------------------- #
# Each injection mutates ONE cell on ONE row, returns a key record documenting
# the change. Injections operate on a working copy; the clean cohort is the
# ground truth. Every record carries the citation for its error_type.
# --------------------------------------------------------------------------- #

@dataclass
class KeyRecord:
    error_id: str
    subject_id: str
    visit: str
    row_uid: str
    group: str
    column: str
    clean_value: object
    injected_value: object
    error_category: str
    error_type: str
    rule_violated: str
    why_it_is_wrong: str
    expected_detector_action: str
    severity: str
    note: str = ""


@dataclass
class HardNegRecord:
    hn_id: str
    subject_id: str
    visit: str
    row_uid: str
    column: str
    value: object
    hard_negative_type: str
    why_it_is_valid: str
    expected_detector_action: str
    note: str = ""


@dataclass
class InjectionPlan:
    df: pd.DataFrame
    key: list[KeyRecord] = field(default_factory=list)
    hard_neg: list[HardNegRecord] = field(default_factory=list)
    used_subjects: set = field(default_factory=set)
    _counter: int = 0

    def next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}{self._counter:04d}"


def _rows_by_subject(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {sid: g.sort_values("visit") for sid, g in df.groupby("subject_id")}


def _pick_subjects(plan, predicate, rng, k):
    """Return up to k subject_ids whose sorted trajectory satisfies predicate(g),
    EXCLUDING subjects already used by a prior injection (disjoint pools, so no
    row gets double-labeled). Picked subjects are reserved immediately."""
    cands = [sid for sid, g in _rows_by_subject(plan.df).items()
             if sid not in plan.used_subjects and predicate(g)]
    rng.shuffle(cands)
    chosen = cands[:k]
    for sid in chosen:
        plan.used_subjects.add(sid)
    return chosen


def _set_cell(df, sid, viscode, col, value):
    mask = (df["subject_id"] == sid) & (df["viscode"] == viscode)
    df.loc[mask, col] = value


def _get_cell(df, sid, viscode, col):
    mask = (df["subject_id"] == sid) & (df["viscode"] == viscode)
    return df.loc[mask, col].iloc[0]


def inject_clinical_stage_regression(plan, rng, n=6):
    """Set a visit BELOW its immediately-preceding visit, where the prior visit
    is in dementia (>=4). Guarantees a genuine regression OUT of dementia
    (the prior->current step is strictly downward). Jack 2024 Table 6."""
    def pred(g):
        cs = [int(x) for x in g["clinical_stage"]]
        # need some interior/late visit whose PRIOR visit is >=4
        return len(g) >= 3 and any(cs[i - 1] >= 4 for i in range(1, len(cs)))
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        cs = [int(x) for x in g["clinical_stage"]]
        # pick the first i where prior visit (i-1) is in dementia
        cand = [i for i in range(1, len(cs)) if cs[i - 1] >= 4]
        if not cand:
            continue
        i = cand[0]
        later = g.iloc[i]
        prior_stage = cs[i - 1]                       # >= 4
        clean = cs[i]
        injected = str(max(0, prior_stage - 2))       # strictly below prior -> regression
        _set_cell(plan.df, sid, later["viscode"], "clinical_stage", injected)
        _set_cell(plan.df, sid, later["viscode"], "clinical_dx",
                  {0: "CN", 1: "CN", 2: "SMC", 3: "MCI"}.get(int(injected), "MCI"))
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, later["viscode"], later["row_uid"], later["group"],
            "clinical_stage", str(clean), injected, "longitudinal",
            "clinical_stage_regression", CITES["clinical_stage_regression"],
            "Established dementia stage reverts to a milder stage (regression out of dementia).",
            "flag (impossible) on staging_clinical", "high"))


def inject_biological_stage_regression(plan, rng, n=6):
    """Set a visit's biological letter BELOW its immediately-preceding visit's
    letter, on an UNTREATED row. Guarantees a genuine backward step. Jack 2024."""
    def pred(g):
        letters = list(g["biological_stage"])
        ranks = [BIO_RANK[x] if x in BIO_RANK else None for x in letters]
        # need an i whose prior visit has a letter of rank >= 1 (room to go down)
        return len(g) >= 3 and any(
            ranks[i - 1] is not None and ranks[i] is not None and ranks[i - 1] >= 1
            for i in range(1, len(ranks)))
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        letters = list(g["biological_stage"])
        ranks = [BIO_RANK[x] if x in BIO_RANK else None for x in letters]
        cand = [i for i in range(1, len(ranks))
                if ranks[i - 1] is not None and ranks[i] is not None and ranks[i - 1] >= 1]
        if not cand:
            continue
        i = cand[0]
        later = g.iloc[i]
        prior_rank = ranks[i - 1]                      # >= 1
        clean = letters[i]
        injected = BIO_LETTERS[prior_rank - 1]         # strictly below prior letter
        _set_cell(plan.df, sid, later["viscode"], "biological_stage", injected)
        _set_cell(plan.df, sid, later["viscode"], "trac_status", "")  # untreated
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, later["viscode"], later["row_uid"], later["group"],
            "biological_stage", str(clean), injected, "longitudinal",
            "biological_stage_regression", CITES["biological_stage_regression"],
            "Biological tau-PET stage moves backward on an untreated row (no TRAC).",
            "flag (impossible) on staging_biological", "high"))


def inject_atn_ordering_violation(plan, rng, n=4):
    """Tau-positive while amyloid-negative on a row: not a valid AD-pathway point.
    Modeled as an A-/T+ contradiction (Jack 2024: A precedes T)."""
    def pred(g):
        return len(g) >= 2
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[len(g) // 2]
        clean_a = row["amyloid_status"]
        _set_cell(plan.df, sid, row["viscode"], "amyloid_status", "A-")
        _set_cell(plan.df, sid, row["viscode"], "tau_pet_status", "T+")
        _set_cell(plan.df, sid, row["viscode"], "centiloid_value", round(float(rng.uniform(2, 18)), 1))
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "amyloid_status", str(clean_a), "A-", "cross_field",
            "atn_ordering_violation", CITES["atn_ordering_violation"],
            "Tau-positive with amyloid-negative: invalid A-/T+ profile on the AD pathway.",
            "flag (impossible/implausible) on cross_sheet", "high"))


def inject_csf_abeta_unit_shift(plan, rng, n=4):
    def pred(g): return len(g) >= 1
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[0]
        clean = float(row["csf_abeta42_pgml"])
        injected = round(clean / 1000.0, 4)  # pg/mL -> ng/mL magnitude error
        _set_cell(plan.df, sid, row["viscode"], "csf_abeta42_pgml", injected)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "csf_abeta42_pgml", clean, injected, "integrity",
            "csf_abeta_unit_shift", CITES["csf_abeta_unit_shift"],
            "CSF Abeta42 reported ~1000x too small (unit shift pg/mL vs ng/mL).",
            "flag (impossible) on ranges/cross_sheet", "medium"))


def inject_nfl_decimal_shift(plan, rng, n=4):
    def pred(g): return len(g) >= 1
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[-1]
        clean = float(row["plasma_nfl_pgml"])
        injected = round(clean * 100.0, 1)
        _set_cell(plan.df, sid, row["viscode"], "plasma_nfl_pgml", injected)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "plasma_nfl_pgml", clean, injected, "integrity",
            "nfl_decimal_shift", CITES["nfl_decimal_shift"],
            "Plasma NfL inflated ~100x (decimal shift) to a physiologically impossible value.",
            "flag (impossible) on ranges", "medium"))


def inject_negative_biomarker(plan, rng, n=3):
    def pred(g): return len(g) >= 1
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[0]
        clean = float(row["hippocampal_volume_total_mm3"])
        injected = round(-abs(clean), 1)
        _set_cell(plan.df, sid, row["viscode"], "hippocampal_volume_total_mm3", injected)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "hippocampal_volume_total_mm3", clean, injected, "integrity",
            "negative_biomarker", CITES["negative_biomarker"],
            "Negative hippocampal volume is impossible.",
            "flag (impossible) on ranges", "medium"))


def inject_invalid_apoe(plan, rng, n=4):
    def pred(g): return len(g) >= 1
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[0]
        clean = row["apoe_genotype"]
        injected = rng.choice(["e4/e5", "e5/e3", "e6/e4"])
        # apoe is a per-subject constant -> set on all rows; flag the baseline row
        plan.df.loc[plan.df["subject_id"] == sid, "apoe_genotype"] = injected
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "apoe_genotype", str(clean), injected, "integrity",
            "invalid_apoe_genotype", CITES["invalid_apoe_genotype"],
            "APOE genotype contains a non-existent allele (e5/e6).",
            "flag (impossible) on data_integrity", "medium"))


def inject_out_of_range_cognition(plan, rng, n=3):
    def pred(g): return len(g) >= 1
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[rng.integers(0, len(g))]
        clean = int(row["mmse_total"])
        injected = int(rng.choice([-3, 42]))
        _set_cell(plan.df, sid, row["viscode"], "mmse_total", injected)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "mmse_total", clean, injected, "integrity",
            "out_of_range_cognition", CITES["out_of_range_cognition"],
            "MMSE outside the valid 0-30 range.",
            "flag (impossible) on ranges", "medium"))


def inject_cdr_dementia_contradiction(plan, rng, n=3):
    def pred(g): return any(int(x) >= 4 for x in g["clinical_stage"])
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        dem = g[g["clinical_stage"].astype(int) >= 4].iloc[0]
        clean = float(dem["cdr_global_score"])
        _set_cell(plan.df, sid, dem["viscode"], "cdr_global_score", 0.0)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, dem["viscode"], dem["row_uid"], dem["group"],
            "cdr_global_score", clean, 0.0, "cross_field",
            "cdr_dementia_contradiction", CITES["cdr_dementia_contradiction"],
            "Dementia clinical stage (4-6) with CDR global = 0 (no impairment).",
            "flag on cross_sheet", "high"))


def inject_amyloid_centiloid_contradiction(plan, rng, n=4):
    def pred(g): return any(a == "A+" for a in g["amyloid_status"])
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        pos = g[g["amyloid_status"] == "A+"].iloc[0]
        clean = float(pos["centiloid_value"])
        injected = round(float(rng.uniform(5, 18)), 1)  # sub-threshold
        _set_cell(plan.df, sid, pos["viscode"], "centiloid_value", injected)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, pos["viscode"], pos["row_uid"], pos["group"],
            "centiloid_value", clean, injected, "cross_field",
            "amyloid_centiloid_contradiction", CITES["amyloid_centiloid_contradiction"],
            "Amyloid-positive with sub-threshold Centiloid (< 25 CL).",
            "flag on cross_sheet", "high"))


def inject_out_of_order_visit_date(plan, rng, n=3):
    """Set a visit's date BEFORE the prior visit's date (out-of-order). To avoid
    creating a PHANTOM staging regression when the auditor re-sorts by date, we
    only pick an adjacent visit pair whose clinical AND biological stages are
    EQUAL -- so reordering them changes no staging step. The error is purely the
    date ordering itself."""
    def pred(g):
        cs = list(g["clinical_stage"])
        bs = list(g["biological_stage"])
        # need an interior i (>=1) where visit i and i-1 share both stages
        return len(g) >= 3 and any(
            cs[i] == cs[i - 1] and bs[i] == bs[i - 1] for i in range(1, len(g)))
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        cs = list(g["clinical_stage"])
        bs = list(g["biological_stage"])
        cand = [i for i in range(1, len(g)) if cs[i] == cs[i - 1] and bs[i] == bs[i - 1]]
        if not cand:
            continue
        i = cand[0]
        row = g.iloc[i]
        clean = row["visit_date"]
        prior_date = pd.Timestamp(g.iloc[i - 1]["visit_date"])
        injected = prior_date - pd.Timedelta(days=30)
        _set_cell(plan.df, sid, row["viscode"], "visit_date", injected)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "visit_date", str(pd.Timestamp(clean).date()), str(pd.Timestamp(injected).date()),
            "integrity", "out_of_order_visit_date", CITES["out_of_order_visit_date"],
            "visit_date decreases relative to the prior visit (out-of-order).",
            "flag on data_integrity", "medium"))


# --------------------------------------------------------------------------- #
# Hard negatives: VALID rows that look suspicious -> must NOT be flagged.
# These EXERCISE the carve-out branches from data (not just unit tests).
# --------------------------------------------------------------------------- #

def make_valid_trac_biological_regression(plan, rng, n=4):
    """A backward biological-stage step (vs the immediately-prior visit) that
    lands ON a TRAC row -> valid treatment-related amyloid clearance (La Joie
    2025). The carve-out must suppress the flag. The branch the prior dataset
    never exercised."""
    def pred(g):
        letters = list(g["biological_stage"])
        ranks = [BIO_RANK[x] if x in BIO_RANK else None for x in letters]
        return len(g) >= 3 and any(
            ranks[i - 1] is not None and ranks[i] is not None and ranks[i - 1] >= 1
            for i in range(1, len(ranks)))
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        letters = list(g["biological_stage"])
        ranks = [BIO_RANK[x] if x in BIO_RANK else None for x in letters]
        cand = [i for i in range(1, len(ranks))
                if ranks[i - 1] is not None and ranks[i] is not None and ranks[i - 1] >= 1]
        if not cand:
            continue
        i = cand[0]
        later = g.iloc[i]
        prior_rank = ranks[i - 1]
        injected_letter = BIO_LETTERS[prior_rank - 1]   # strictly below prior -> backward step
        _set_cell(plan.df, sid, later["viscode"], "biological_stage", injected_letter)
        _set_cell(plan.df, sid, later["viscode"], "trac_status", "TRAC")   # the carve-out
        _set_cell(plan.df, sid, later["viscode"], "amyloid_status", "A-")  # clearance
        _set_cell(plan.df, sid, later["viscode"], "treatment_arm", "active")
        _set_cell(plan.df, sid, later["viscode"], "centiloid_value", round(float(rng.uniform(5, 22)), 1))
        plan.hard_neg.append(HardNegRecord(
            plan.next_id("HN"), sid, later["viscode"], later["row_uid"],
            "biological_stage", injected_letter, "valid_trac_biological_regression",
            HARD_NEG["valid_trac_biological_regression"],
            "must NOT flag (TRAC carve-out suppresses biological regression)"))


def make_valid_pre_dementia_reversion(plan, rng, n=4):
    """A clean clinical reversion within the pre-dementia range (3->2 or 2->1)
    on a real later visit -> admissible (MCI reversion). Must NOT flag. This is
    the clinical pack's false-positive trap, exercised from data."""
    def pred(g):
        cs = [int(x) for x in g["clinical_stage"]]
        return len(g) >= 3 and max(cs) <= 3 and max(cs) >= 2  # pre-dementia, reaches 2 or 3
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        # find a visit at stage 2 or 3 with a later visit; set the later one lower
        idx = [i for i, x in enumerate(g["clinical_stage"]) if int(x) in (2, 3)]
        if not idx or idx[0] + 1 >= len(g):
            continue
        later = g.iloc[idx[0] + 1]
        prior = int(g.iloc[idx[0]]["clinical_stage"])
        injected = str(prior - 1)  # 3->2 or 2->1, stays in pre-dementia
        _set_cell(plan.df, sid, later["viscode"], "clinical_stage", injected)
        _set_cell(plan.df, sid, later["viscode"], "clinical_dx",
                  {1: "CN", 2: "SMC"}.get(int(injected), "MCI"))
        plan.hard_neg.append(HardNegRecord(
            plan.next_id("HN"), sid, later["viscode"], later["row_uid"],
            "clinical_stage", injected, "valid_pre_dementia_reversion",
            HARD_NEG["valid_pre_dementia_reversion"],
            "must NOT flag (pre-dementia reversion is admissible)"))


def make_valid_trac_clearance(plan, rng, n=4):
    """Amyloid clearance (A+ -> A-) on active therapy, biological letter held
    (no regression) -> valid treatment effect. Must NOT flag as an anomaly."""
    def pred(g):
        return len(g) >= 3 and any(a == "A+" for a in g["amyloid_status"])
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        pos_idx = [i for i, a in enumerate(g["amyloid_status"]) if a == "A+"]
        if not pos_idx or pos_idx[-1] + 1 >= len(g):
            continue
        later = g.iloc[pos_idx[-1] + 1]
        _set_cell(plan.df, sid, later["viscode"], "amyloid_status", "A-")
        _set_cell(plan.df, sid, later["viscode"], "trac_status", "TRAC")
        _set_cell(plan.df, sid, later["viscode"], "treatment_arm", "active")
        _set_cell(plan.df, sid, later["viscode"], "centiloid_value", round(float(rng.uniform(5, 22)), 1))
        plan.hard_neg.append(HardNegRecord(
            plan.next_id("HN"), sid, later["viscode"], later["row_uid"],
            "amyloid_status", "A-", "valid_trac_clearance",
            HARD_NEG["valid_trac_clearance"],
            "must NOT flag (amyloid clearance on active therapy is a valid effect)"))


def make_valid_offdiagonal(plan, rng, n=3):
    """Off-diagonal integrated stage (advanced clinical, early biological, or
    vice versa) -> recognized resilient/copathologic, NOT an error."""
    def pred(g):
        return len(g) >= 2 and any(x in BIO_RANK for x in g["biological_stage"])
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[-1]
        # bump clinical up while biological stays low (copathologic) -- keep
        # clinical monotonic by only raising it
        cur = int(row["clinical_stage"])
        injected = str(min(6, cur + 2))
        _set_cell(plan.df, sid, row["viscode"], "clinical_stage", injected)
        _set_cell(plan.df, sid, row["viscode"], "clinical_dx",
                  {4: "AD", 5: "AD", 6: "AD", 3: "MCI"}.get(int(injected), "AD"))
        plan.hard_neg.append(HardNegRecord(
            plan.next_id("HN"), sid, row["viscode"], row["row_uid"],
            "integrated_stage", f"{injected}{row['biological_stage']}",
            "valid_offdiagonal", HARD_NEG["valid_offdiagonal_stage"],
            "must NOT flag (off-diagonal copathologic/resilient is recognized by Jack 2024)"))


def inject_duplicate_visit_conflict(plan, rng, n=3):
    """Append a duplicate (subject, viscode) row with a conflicting NON-staging
    value (mmse_total). Conflicting on a staging column would masquerade as a
    spurious stage regression; the duplicate-visit error is about the key
    violation itself, so we conflict on a cognitive score instead."""
    def pred(g): return len(g) >= 2
    new_rows = []
    for sid in _pick_subjects(plan, pred, rng, n):
        g = _rows_by_subject(plan.df)[sid]
        row = g.iloc[1].to_dict()
        clean_mmse = int(row["mmse_total"])
        dup = dict(row)
        # conflicting cognition value (clearly different, still in-range)
        dup["mmse_total"] = int(np.clip(clean_mmse + rng.choice([-7, 7]), 0, 30))
        if dup["mmse_total"] == clean_mmse:
            dup["mmse_total"] = int(np.clip(clean_mmse + 5, 0, 30))
        new_rows.append(dup)
        plan.key.append(KeyRecord(
            plan.next_id("E"), sid, row["viscode"], row["row_uid"], row["group"],
            "mmse_total", clean_mmse, dup["mmse_total"], "integrity",
            "duplicate_visit_conflict", CITES["duplicate_visit_conflict"],
            "Duplicate (subject, visit) row with a conflicting mmse_total value.",
            "flag on data_integrity", "high"))
    if new_rows:
        plan.df = pd.concat([plan.df, pd.DataFrame(new_rows)], ignore_index=True)
    return plan


# --------------------------------------------------------------------------- #
# Orchestration + reference checker + writers
# --------------------------------------------------------------------------- #

def apply_all_injections(df: pd.DataFrame, rng: np.random.Generator) -> InjectionPlan:
    plan = InjectionPlan(df=df.copy())
    # error injections (disjoint subject pools by construction of _pick_subjects
    # randomness; small overlap is acceptable since each targets a distinct cell)
    inject_clinical_stage_regression(plan, rng, n=6)
    inject_biological_stage_regression(plan, rng, n=6)
    inject_atn_ordering_violation(plan, rng, n=4)
    inject_csf_abeta_unit_shift(plan, rng, n=4)
    inject_nfl_decimal_shift(plan, rng, n=4)
    inject_negative_biomarker(plan, rng, n=3)
    inject_invalid_apoe(plan, rng, n=4)
    inject_out_of_range_cognition(plan, rng, n=3)
    inject_cdr_dementia_contradiction(plan, rng, n=3)
    inject_amyloid_centiloid_contradiction(plan, rng, n=4)
    inject_out_of_order_visit_date(plan, rng, n=3)
    plan = inject_duplicate_visit_conflict(plan, rng, n=3)
    # hard negatives (must NOT flag)
    make_valid_trac_biological_regression(plan, rng, n=4)
    make_valid_pre_dementia_reversion(plan, rng, n=4)
    make_valid_trac_clearance(plan, rng, n=4)
    make_valid_offdiagonal(plan, rng, n=3)
    return plan


def reference_check(plan: InjectionPlan) -> dict:
    """Independently re-scan the finished data for the two staging regression
    classes and assert every occurrence is DOCUMENTED -- either as a key error
    or as a hard-negative (TRAC carve-out / pre-dementia reversion). Returns a
    report; raises AssertionError on any uncovered violation."""
    df = plan.df
    keyed = {(r.row_uid, r.column) for r in plan.key}
    hn = {(r.row_uid, r.column) for r in plan.hard_neg}
    documented = keyed | hn

    uncovered = []
    # ---- biological backward steps ----
    for _sid, g in df[df["row_uid"].notna()].groupby("subject_id"):
        g = g.sort_values(["months_since_baseline", "visit"])
        prev_rank = None
        for _, row in g.iterrows():
            L = row["biological_stage"]
            if L not in BIO_RANK:
                continue
            if prev_rank is not None and BIO_RANK[L] < prev_rank:
                # backward step on this (later) row
                is_trac = str(row.get("trac_status", "")).strip().upper() == "TRAC"
                key_id = (row["row_uid"], "biological_stage")
                if is_trac:
                    # must be documented as a hard-negative (carve-out), not an error
                    if key_id not in hn:
                        uncovered.append(("biological_regression_TRAC_undocumented", key_id))
                else:
                    if key_id not in documented:
                        uncovered.append(("biological_regression_undocumented", key_id))
            prev_rank = BIO_RANK[L]

    # ---- clinical regressions ----
    for _sid, g in df[df["row_uid"].notna()].groupby("subject_id"):
        g = g.sort_values(["months_since_baseline", "visit"])
        prev = None
        for _, row in g.iterrows():
            c = int(row["clinical_stage"])
            if prev is not None and c < prev:
                key_id = (row["row_uid"], "clinical_stage")
                out_of_dementia = prev >= 4
                if out_of_dementia:
                    if key_id not in documented:
                        uncovered.append(("clinical_regression_out_of_dementia_undocumented", key_id))
                else:
                    # pre-dementia reversion: must be a documented hard-negative
                    if key_id not in hn:
                        uncovered.append(("pre_dementia_reversion_undocumented", key_id))
            prev = c

    # ---- no hard-negative may also be a keyed error (no double-labeling) ----
    overlap = keyed & hn
    if overlap:
        uncovered.append(("hard_negative_also_keyed", sorted(overlap)))

    report = {
        "n_errors": len(plan.key),
        "n_hard_negatives": len(plan.hard_neg),
        "uncovered": uncovered,
    }
    assert not uncovered, f"reference check FAILED -- uncovered violations: {uncovered}"
    return report


_DATASET_COLS = [
    "subject_id", "group", "treatment_arm", "drug_dose_mg", "visit", "viscode",
    "visit_date", "months_since_baseline", "age_years", "sex", "education_years",
    "clinical_dx", "clinical_stage", "biological_stage", "at2_notation",
    "integrated_stage", "apoe_genotype", "amyloid_status", "centiloid_value",
    "tau_pet_status", "tau_pet_stage", "tau_pet_suvr_metaroi", "csf_abeta42_40_ratio",
    "csf_abeta42_pgml", "csf_ptau181_pgml", "plasma_ptau217_pgml", "plasma_ptau181_pgml",
    "plasma_abeta42_40_ratio", "mtbr_tau243_csf", "ptau205_csf", "plasma_nfl_pgml",
    "plasma_gfap_pgml", "hippocampal_volume_total_mm3", "mean_cortical_thickness_mm",
    "total_intracranial_volume_eTIV_cm3", "wmh_total_volume_ml", "fazekas_combined_score",
    "asyn_saa_status", "mmse_total", "moca_total", "cdr_global_score", "cdr_sb_sum_boxes",
    "adas_cog_13_total", "faq_total", "map_mmhg", "anticoagulant_use", "aria_e_grade",
    "aria_e_max_dimension_cm", "aria_h_micro_incident", "aria_h_micro_cumulative",
    "aria_h_siderosis_count", "aria_overall_severity", "macrohemorrhage_flag",
    "trac_status", "data_source", "row_uid", "braak_nft_stage", "thal_amyloid_phase",
    "cerad_neuritic_plaque_score",
]


def write_outputs(plan: InjectionPlan, out_dir: str) -> dict:
    import os
    os.makedirs(out_dir, exist_ok=True)
    df = plan.df[_DATASET_COLS].copy()
    df = df.sort_values(["subject_id", "visit"]).reset_index(drop=True)
    ds_path = os.path.join(out_dir, "NeuroTCS_AD_Challenge_Dataset.csv")
    key_path = os.path.join(out_dir, "NeuroTCS_AD_Challenge_AnswerKey.csv")
    hn_path = os.path.join(out_dir, "NeuroTCS_AD_Challenge_HardNegatives.csv")
    df.to_csv(ds_path, index=False)
    pd.DataFrame([vars(r) for r in plan.key]).to_csv(key_path, index=False)
    pd.DataFrame([vars(r) for r in plan.hard_neg]).to_csv(hn_path, index=False)
    return {"dataset": ds_path, "answer_key": key_path, "hard_negatives": hn_path,
            "n_rows": len(df), "n_errors": len(plan.key), "n_hard_neg": len(plan.hard_neg)}


def main():
    ap = argparse.ArgumentParser(description="NeuroTCS AD Challenge benchmark generator")
    ap.add_argument("--seed", type=int, default=20260609)
    ap.add_argument("--subjects", type=int, default=450)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    clean = build_clean_cohort(args.subjects, rng)
    plan = apply_all_injections(clean, rng)
    report = reference_check(plan)
    info = write_outputs(plan, args.out)
    print(json.dumps({"seed": args.seed, **info, "reference_check": report}, indent=2, default=str))


if __name__ == "__main__":
    main()

# Aim 3 — MIRIAD Measurement-Noise Floor + Third-Cohort Generalisation Test

**Status**: pipeline shipped (v1.7.4); locked invariants to be re-derived on Maruf's first MIRIAD-data run.
**Framework**: temporalmetric v1.7 FINAL §B.1 Aim 3.
**Rule pack**: `ad/niaaa_2018@1.2.0` (same as Aim 1 ADNI, Aim 2 OASIS-3).
**Cohort**: MIRIAD (Malone et al. 2013 *NeuroImage* 70:33-36, PMID 23274184, DOI 10.1016/j.neuroimage.2012.12.044). 46 mild-to-moderate AD + 23 cognitively-normal controls (n=69 total), 708 T1 MRI scans, UCL Dementia Research Centre.

## What MIRIAD adds to the validation story

Aim 1 (ADNI, n_transitions = 12,006) and Aim 2 (OASIS-3, n_transitions = 7,248) established that the cTCS metric generalises across two large independent CDR-anchored AD cohorts. **MIRIAD asks two complementary questions** that the other two cohorts cannot:

1. **Does the kernel logic generalise to an MMSE-anchored staging?** ADNI and OASIS-3 derive state from Clinical Dementia Rating (Morris 1993). MIRIAD has only MMSE per visit (Folstein 1975); no CDR data per scan. The rule pack's CN/MCI/AD admissibility rules are themselves clinically agnostic about the upstream staging instrument — but until v1.7.4 this generalisation had not been tested empirically.
2. **What is the within-session measurement-noise floor?** MIRIAD is the **only** of the three cohorts with back-to-back same-session rescans (weeks 0, 6, 38 each have two scans). The audit flag rate on these pairs quantifies what fraction of "flagged transitions" in ADNI/OASIS-3 could plausibly be attributable to within-session noise versus genuine biological inadmissibility.

| Property | ADNI (Aim 1) | OASIS-3 (Aim 2) | MIRIAD (Aim 3) |
|---|---|---|---|
| Sponsor / source | NIH / multi-site US | WUSTL Knight ADRC, US | UCL DRC, UK |
| Sample size | 2,958 subjects | 1,247 subjects | 69 subjects |
| Follow-up window | up to 18 years | up to 30 years | up to 2 years |
| Scanner heterogeneity | many | many | **single scanner** (same radiographer, same sequences) |
| Test-retest scans | none | none | **3 visits × 2 back-to-back scans ≈ 207 pairs** |
| Per-visit clinical signal | clinical diagnosis | CDR global score | **MMSE only** (no per-visit CDR) |
| MMSE cadence | every visit (when collected) | every visit | **6-monthly** (Malone 2013) |
| Statistical question | natural-history admissibility | natural-history replication (CDR↔CDR) | **kernel-logic generalisation (CDR→MMSE) + within-session noise floor** |

### Honest framing — what this is NOT

This is **not a literal like-for-like replication of Aim 1 / Aim 2**. ADNI and OASIS-3 both stage with CDR; MIRIAD stages with MMSE. CDR and MMSE measure overlapping but distinct constructs (CDR is a structured clinical interview spanning 6 cognitive/functional domains; MMSE is a brief screening test of orientation, memory, attention, language, and visuospatial function). The mapping from each to CN/MCI/AD has different thresholds and different sensitivity to mild impairment. So:

- A favourable MIRIAD cTCS does NOT replicate the CDR-anchored ADNI/OASIS-3 finding in the strict sense — it shows the kernel's admissibility logic *generalises* to MMSE-anchored staging.
- The 0.0004 ΔcTCS between ADNI and OASIS-3 is a strict like-for-like replication number; the MIRIAD ΔcTCS will be compared with looser tolerance.
- The headline scientific claim from MIRIAD is the **within-session measurement-noise floor**, not the longitudinal cTCS replication.

This honesty is encoded in the paper framing for the Nature Medicine W22 submission: the three-cohort table appears with explicit columns showing the staging instrument (CDR/CDR/MMSE) and a footnote acknowledging the construct difference.

## Design: two statistical instruments, one cohort

Aim 3 splits MIRIAD's 708 scans into two non-overlapping audit cohorts:

**(A) Longitudinal cohort** — for kernel-logic generalisation. Each subject contributes one trajectory built from their unique scan visits at weeks 0, 2, 6, 14, 26, 38, 52, 78, 104 (subset that applies). Back-to-back rescans at weeks 0, 6, 38 are deduplicated to a single visit. State at each visit is derived from MMSE using Folstein 1975 thresholds (MMSE ≥ 27 → CN, 18-26 → MCI, ≤ 17 → AD), with **forward-fill from the most recent prior assessment** (necessary because Malone 2013 records MMSE every 6 months, not at every scan visit).

**(B) Test-retest cohort** — for noise-floor characterisation. Each pair of back-to-back same-session scans contributes one length-2 trajectory with `delta_t_days = 0` (the Trajectory class natively allows date ties for same-session re-reads). Both scans inherit the same per-visit MMSE assessment, so under noiseless conditions every pair should be an admissible self-loop. The audit flag rate is the empirical noise floor.

Both cohorts pass through the same `audit(...)` kernel with the same `niaaa_2018@1.2.0` rule pack and the same bootstrap parameters (B=10,000, seed=42, BCa). Each produces a locked `audit_id` and `audit_id_v2`.

## Methodological details (v1.7.4)

### MMSE forward-fill (F11 fix)

MIRIAD's clinical protocol records MMSE at baseline + every 6 months (Malone 2013 verbatim: "MMSE score was recorded at baseline and 6-monthly intervals"). Scan visits at weeks 2, 6, 14, 38 do NOT have a per-visit MMSE; only weeks 0, 26, 52, 78, 104 do. Without intervention, joining sessions × clinical on (subject, visit) drops ~40% of scan visits.

The adapter applies **forward-fill within each subject** after the join: visits without a per-visit MMSE inherit the most recent prior assessment. A backfill pass handles the edge case where the first scan precedes the first clinical assessment. The `mmse_forward_filled` field of the load report tracks how many rows were filled.

**Why this is correct**: forward-fill is the standard treatment in AD-cohort epidemiology for intermittent clinical assessment. MMSE doesn't change rapidly enough that a 4-week stale value misclassifies state at the Folstein boundaries (≥27 / ≤17). A reviewer asking "why not nearest-neighbour interpolation?" gets the answer: MMSE is not monotonic on short timescales (within-subject test-retest variability ±1-2 points per Tombaugh & McIntyre 1992), so forward-fill is the conservative choice that doesn't fabricate trajectory smoothness.

### Same-session pair encoding (F8 fix)

Test-retest pairs encode `delta_t_days = 0` (both rescans on the same synthetic date). The Trajectory class allows date ties (per `audit_core/trajectory.py:66`: "allow ties — same-day re-read"). This is the semantically correct encoding; using `delta_t = 1 day` (as v1.7.3 did) would mis-represent the noise floor as a 1-day-apart trajectory.

### State-discordant vs severity-consistent disagreements (F2 + F12 fix)

Per Malone 2013 the MIRIAD AD inclusion criterion is **MMSE 12-26**, which spans the Folstein MCI and AD ranges. So an AD-group subject with MMSE in 18-26 (MCI by Folstein) is the inclusion criterion, NOT a clinically meaningful "disagreement." The adapter now distinguishes:

- **`group_mmse_disagreements`**: broad count of any group ≠ MMSE-state pair (for transparency).
- **`group_mmse_state_discordant`**: AD-group + CN-state, OR CN-group + AD-state. These are the only clinically meaningful flags.

The `group_mmse_disagreement_examples` field surfaces only state-discordant cases.

## Expected results

**Longitudinal (Aim 3 A)**:
- cTCS in the **0.95-1.00 range**, BCa 95% CI width comparable to OASIS-3's (~0.006).
- ΔcTCS vs ADNI within ±0.05 — looser tolerance than ADNI↔OASIS-3 because of the MMSE↔CDR construct difference.
- flag rate ≤ 5% — MMSE staging is noisier than CDR staging because MMSE moves by ±1-2 points within-subject due to test-retest variability, and a 1-point change can cross a Folstein boundary.

**Test-retest (Aim 3 B)**:
- pair count ≥ 100 (MIRIAD has 3 rescan visits × ~69 subjects ≈ 207 maximum, with attrition).
- flag rate **≤ 0.01%** in the synthetic-data dry-run (because both scans inherit the same per-visit MMSE → identical state by construction). On real data the floor depends on whether MMSE was administered separately for each back-to-back scan; per Malone 2013, only one MMSE per visit was recorded, so the noise floor in MIRIAD is bounded BY THE DATA STRUCTURE at ≤ 0.01%.

**This last point matters scientifically**: MIRIAD's design does NOT actually let us measure within-session MMSE noise (because MMSE was administered once per visit, not once per scan). What MIRIAD's test-retest CAN do is verify that the adapter and kernel are **self-consistent** — the same MMSE value produces the same state on both scans of a pair, and the kernel correctly handles delta_t=0 self-loops. The "noise floor" claim is therefore narrower than originally framed: it bounds **pipeline noise** (adapter → kernel processing), not **MMSE re-administration noise**.

For Nature Medicine framing this still has value: it's an end-to-end pipeline-determinism guarantee on independent data. But we will NOT claim it measures MMSE measurement noise per se. The honest claim is: "the audit kernel produces bit-identical decisions on bit-identical inputs, demonstrated on 207 independent same-session pairs."

To measure actual MMSE re-administration noise, we would need ADNI's longitudinal cohort where MMSE IS sometimes re-administered within sessions, or a dedicated test-retest cohort like RIDER (planned for v0.2).

## What this enables

For the **Nature Medicine W22 submission**: three independent cohorts × cTCS finding + a pipeline-determinism end-to-end guarantee. The honest framing keeps reviewer credibility intact: we claim what the data actually supports.

For the **ASFNR Newport Beach workshop (October 2026)**: a 2×3 panel — three cohorts × {staging instrument, cTCS, flag rate} — with explicit honesty about CDR-vs-MMSE construct differences.

For the **FDA Q-Sub (Q1 2027)**: pipeline-determinism on independent data is a measurement-system-analysis result that documents the audit kernel's processing reliability. The within-session MMSE re-administration question is deferred to a dedicated cohort.

## Reproducibility

```python
from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    load_miriad_trajectories,
    load_miriad_test_retest_pairs,
)

# Aim 3 (A): longitudinal kernel-logic generalisation
trajectories, report_long = load_miriad_trajectories(
    clinical_csv="path/to/ClinicalAssessment.csv",
    sessions_csv="path/to/MR_Sessions.csv",
    subjects_csv="path/to/Subjects.csv",
)
pack = load_rulepack("ad/niaaa_2018")
result_long = audit(trajectories, pack, bootstrap_B=10_000, seed=42)
print(result_long.summary())

# Aim 3 (B): pipeline-determinism end-to-end on test-retest pairs
pairs, report_pairs = load_miriad_test_retest_pairs(
    clinical_csv="path/to/ClinicalAssessment.csv",
    sessions_csv="path/to/MR_Sessions.csv",
)
result_pairs = audit(pairs, pack, bootstrap_B=10_000, seed=42)
print(result_pairs.summary())
```

Or use the standalone runner:

```bash
python scripts/run_aim3_miriad.py \
    --clinical path/to/ClinicalAssessment.csv \
    --sessions path/to/MR_Sessions.csv \
    --subjects path/to/Subjects.csv \
    --out      output_directory/
```

Locked invariants (captured on Maruf's first real-data run) live in `tests/audit_core/test_real_miriad_audit.py` and follow the same re-derive-on-first-run pattern as `test_real_oasis3_audit.py`.

## Citation hygiene

- Malone IB, Cash D, Ridgway GR, MacManus DG, Ourselin S, Fox NC, Schott JM. MIRIAD - Public release of a multiple time point Alzheimer's MR imaging dataset. *NeuroImage* 2013;70:33-36. PMID 23274184, DOI 10.1016/j.neuroimage.2012.12.044, PMCID PMC3809512.
- Folstein MF, Folstein SE, McHugh PR. "Mini-mental state". A practical method for grading the cognitive state of patients for the clinician. *J Psychiatr Res* 1975;12(3):189-198. PMID 1202204.
- Tombaugh TN, McIntyre NJ. The Mini-Mental State Examination: a comprehensive review. *J Am Geriatr Soc* 1992;40(9):922-935. PMID 1512391.
- Morris JC. The Clinical Dementia Rating (CDR): current version and scoring rules. *Neurology* 1993;43(11):2412-2414. PMID 8232972.

All four citations are gated by `scripts/verify_citations.py` against Crossref + PubMed EUtils on every commit.

## Version history

- **v1.7.2** — initial MIRIAD adapter shipped with MMSE staging, group-disagreement diagnostic, and same-session rescan exclusion.
- **v1.7.3** — surgical patch for real XNAT export format (composite `Label` parsing, subject-ID-based group inference fallback).
- **v1.7.4** — deep audit + 4 critical fixes after expert-grade methodology review:
  - F1: `BootstrapCI` attribute names (would have crashed the runner).
  - F8: same-session pair `delta_t = 0` (was 1 day, methodologically incorrect).
  - F11: MMSE forward-fill within subject (Malone 2013 records MMSE 6-monthly, not per scan).
  - F2+F12: state-discordant vs severity-consistent disagreement distinction (MIRIAD AD inclusion criterion is MMSE 12-26 = MCI range under Folstein).
  - F13: honest framing of what MIRIAD's test-retest design actually measures (pipeline determinism, not MMSE re-administration noise).

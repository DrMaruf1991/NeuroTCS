# Aim 3 — MIRIAD Measurement-Noise Floor + Third-Cohort Generalisation Test

**Status**: REAL-DATA RUN COMPLETE (2026-05-18); invariants locked in v1.7.7.
**Framework**: temporalmetric v1.7 FINAL §B.1 Aim 3.
**Rule pack**: `ad/niaaa_2018@1.3.0` (same as Aim 1 ADNI, Aim 2 OASIS-3).
**Cohort**: MIRIAD (Malone et al. 2013 *NeuroImage* 70:33-36, PMID 23274184, DOI 10.1016/j.neuroimage.2012.12.044). 46 mild-to-moderate AD + 23 cognitively-normal controls (n=69 total), 708 T1 MRI scans, UCL Dementia Research Centre.

## Real-data findings (2026-05-18 run, NeuroTCS v1.7.6)

### (A) Longitudinal kernel-logic generalisation — **PASSED**

| Metric | Value | Locked? |
|---|---|---|
| Trajectories | 69 / 69 (full cohort) | ✓ |
| Transitions | 454 | ✓ |
| Flagged | 7 (1.54 %) | ✓ |
| cTCS | **0.9854** (BCa 95 % CI: 0.9715–0.9937) | ✓ |
| pTCS (clinical) | −0.3622 | — |
| uTCS | 0.9854 | — |
| ΔcTCS vs ADNI (0.9946) | **−0.0092** | — |
| ΔcTCS vs OASIS-3 (0.9942) | **−0.0088** | — |
| audit_id | `abda26cb4f77c4f5c7644b421b459b79dfa5caf58f32d60860736c6a2c9ee57f` | ✓ |
| audit_id_v2 | `1aeb56ce5a88d9f74e7b6942ca4b3e2329fd918d96264b4df062744247cf1a80` | ✓ |

**Interpretation**: The cTCS kernel — designed and validated on CDR-anchored ADNI/OASIS-3 — produces a generalisation cTCS of 0.9854 on MMSE-anchored MIRIAD, within 0.01 of the CDR-anchored cohorts. This is closer agreement than the conservative ±0.05 band set for the construct difference. The kernel's admissibility logic is robust across staging instruments.

### (B) Test-retest pipeline determinism — **PASSED**

| Metric | Value | Locked? |
|---|---|---|
| Same-session pairs identified | 185 candidate | — |
| Pairs with per-visit MMSE | 69 (baseline-rescan only) | ✓ |
| Pairs entered into audit | 69 | ✓ |
| Identical-state pairs | 69 (100 %) | ✓ |
| Differing-state pairs | 0 | ✓ |
| Flag rate | **0.000 %** | ✓ |
| cTCS | 1.0000 (BCa 95 % CI: 1.0000–1.0000) | — |
| audit_id | `4de7f7111aedea86636dae2f81a768a1013849e5949a21062e3bdbd99f499136` | ✓ |
| audit_id_v2 | `fa30cd364d9239a5fbc5774182a4d5093189605c10d5a1abe956653dd76afa1f` | ✓ |

**Why only 69 pairs of an expected ~207?** MIRIAD has back-to-back rescans at weeks 0, 6, and 38 (= 3 rescan visits × 69 subjects = 207 candidate pairs). However, per Malone 2013, MMSE is recorded at baseline + every 6 months only. The week-0 baseline rescan has same-visit MMSE; the week-6 and week-38 rescans do NOT have a clinical-assessment row with matching visit number. The adapter's per-visit Label-based join correctly excludes pairs without same-visit MMSE rather than fabricating values, leaving the **baseline rescan for each subject = 69 audit-ready pairs**.

**Interpretation**: 69 independent same-session pairs flow through the audit kernel with zero flagged transitions. The kernel produces bit-identical decisions on bit-identical inputs across 69 independent test cases. This bounds **pipeline determinism**, not MMSE re-administration noise (which would require Malone 2013-style per-scan MMSE administration, not present in MIRIAD's protocol). True MMSE re-administration noise would require a dedicated AD test-retest cohort with per-scan cognitive scoring; in this AD-only v1.x scope (see [`docs/SCOPE.md`](../SCOPE.md)) this remains a documented gap.

### Adapter diagnostics (v1.7.6 round-2 audit fields)

| Field | Value | Meaning |
|---|---|---|
| `rows_with_mmse` | 523 / 523 | Every loaded scan has matched MMSE after forward-fill |
| `unmappable_mmse` | 0 | All MMSE values map cleanly to Folstein states |
| `mmse_forward_filled` | (computed at runtime) | Visits inherited MMSE from prior assessment per Malone 2013's 6-monthly cadence |
| `group_mmse_disagreements` (broad) | 359 | All AD-MCI severity-consistent + state-discordant cases |
| `group_mmse_state_discordant` | (computed at runtime) | The clinically meaningful subset only |
| `n_test_retest_visits_excluded` | 185 | Back-to-back rescan scans removed from longitudinal cohort |

The high broad disagreement count (359) is expected because MIRIAD's AD inclusion criterion is MMSE 12-26, which spans the Folstein MCI and AD ranges. The clinically meaningful state-discordant count is the field to report.

## What MIRIAD adds to the validation story

Aim 1 (ADNI, n_transitions = 12,006) and Aim 2 (OASIS-3, n_transitions = 7,248) established that the cTCS metric generalises across two large independent CDR-anchored AD cohorts. **MIRIAD answers two complementary questions** that the other two cohorts cannot:

1. **Does the kernel logic generalise to MMSE-anchored staging?** ADNI and OASIS-3 derive state from Clinical Dementia Rating (Morris 1993). MIRIAD has only MMSE per visit (Folstein 1975); no CDR data per scan. The rule pack's CN/MCI/AD admissibility rules are themselves clinically agnostic about the upstream staging instrument. **Answer (2026-05-18): YES** — cTCS 0.9854 vs ADNI 0.9946 (Δ = −0.0092).
2. **What is the pipeline determinism floor?** MIRIAD is the only of the three cohorts with back-to-back same-session rescans. **Answer (2026-05-18): EXACT** — 69 pairs, 0 flagged, cTCS = 1.0000.

| Property | ADNI (Aim 1) | OASIS-3 (Aim 2) | MIRIAD (Aim 3) |
|---|---|---|---|
| Sponsor / source | NIH / multi-site US | WUSTL Knight ADRC, US | UCL DRC, UK |
| Sample size | 2,958 subjects | 1,247 subjects | 69 subjects |
| Follow-up window | up to 18 years | up to 30 years | up to 2 years |
| Scanner heterogeneity | many | many | **single scanner** (same radiographer, same sequences) |
| Test-retest scans | none | none | 69 audit-ready baseline pairs |
| Per-visit clinical signal | clinical diagnosis | CDR global score | **MMSE only** (no per-visit CDR) |
| MMSE/CDR cadence | every visit | every visit | **6-monthly** (Malone 2013) |
| cTCS | 0.9946 | 0.9942 | **0.9854** (longitudinal) / 1.0000 (test-retest) |
| Statistical question | natural-history admissibility | natural-history replication (CDR↔CDR) | **kernel-logic generalisation (CDR→MMSE) + pipeline-determinism floor** |

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

To measure actual MMSE re-administration noise, we would need ADNI's longitudinal cohort where MMSE IS sometimes re-administered within sessions, or a dedicated AD-cohort with per-scan cognitive scoring. This is a documented limitation of MIRIAD-as-test-retest-reference under the v1.x AD-only scope.

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
- **v1.7.4** — round-1 deep methodology audit + 6 fixes (F1-F13) after expert-grade review.
- **v1.7.6** — round-2 deep audit + 2 reporting bugs fixed (R1, R2) + 11 edge-case regression tests added. 237 tests passing on two consecutive runs from cold install.
- **v1.7.7** — REAL-DATA RUN COMPLETE. Locked invariants from 2026-05-18 MIRIAD run: longitudinal cTCS = 0.9854, audit_id `947ab24e...`; test-retest cTCS = 1.0000, audit_id `80430399...`. Three-cohort consistency achieved (ADNI 0.9946 / OASIS-3 0.9942 / MIRIAD 0.9854 — all within 0.01 of each other). Runner now displays state-discordant disagreement count separately from broad count. Numerical invariants (trajectory count, transitions, flag count, cTCS to 4dp) locked as test assertions.

# MIRIAD label mapping — MMSE-threshold-anchored (per visit)

**Adapter:** `src/neurotcs/input_contract/v1_1/adapters/adapter_miriad.py`
**Source files:** `ClinicalAssessment.csv` (MMSE), `MR_Sessions.csv`
(age-at-scan), optional `Subjects.csv` (group + demographics). Column names
resolved defensively against several candidate spellings (XNAT exports).

## Mapping rule (`mmse_to_state`, adapter lines ~159–192)

| `MMSE` (per visit) | State | Basis |
|---|---|---|
| ≥ 27 | CN | Folstein 1975 (PMID 1202204); Tombaugh & McIntyre 1992 (PMID 1512391) |
| 18–26 | MCI | " |
| < 18 | AD | " |
| < 0 or > 30 | dropped (`out_of_range`) | invalid MMSE |
| NaN after imputation | dropped (`unmappable`) | |

Thresholds are deliberately conservative so 1-point MMSE noise does not
silently cross a state boundary. The `group` column (AD vs control per
Malone 2013) is **diagnostics only** — using it for states would make every
trajectory a self-loop and cTCS = 1.0 by construction (uninformative).

## Key non-obvious behaviors

- **MMSE imputation:** MMSE exists only at baseline + 6-monthly visits;
  within-subject forward-fill then backfill attaches states to the 2/6/14-
  week scan visits (~40% of visits would otherwise drop). An imputed state
  is a *carried-forward measurement*, not a new assessment.
- **Synthetic dates:** MIRIAD reports age-at-scan, not dates; per-subject
  offsets (365.25 × age delta) from a fixed baseline preserve intervals
  exactly.
- **Test-retest handling:** same-session rescans are de-duplicated for the
  longitudinal cohort; the separate test-retest loader pairs rescans at
  identical synthetic dates (Δt = 0) to measure the pipeline noise floor
  (0 flags expected and locked: cTCS = 1.0000).
- **Group inference fallback:** when `Subjects.csv` lacks a group column,
  the Malone 2013 ID convention infers it (188–233 → AD, 234–280 → CN) —
  diagnostics only.
- Subject IDs salted-hashed by default (`MIRIAD_` prefix).

## Mapping-artifact risks (check before adjudicating a flag as DATA_ERROR)

1. **MMSE is not a diagnosis.** MMSE staging is a severity proxy; education,
   language, and practice effects move MMSE without any change in clinical
   status. A 26→27 crossing surfaces as MCI→CN, and 18→17 as MCI→AD; flags
   at ±1 point around a threshold are prime type-3 (mapping-artifact)
   candidates.
2. **Imputation-induced stability/jumps.** Forward/backfill can place a
   *later* assessment's state on an *earlier* scan visit (backfill at the
   first visits), or hold a stale state across a real change; a flagged
   transition adjacent to imputed visits must be checked against which MMSE
   values are measured vs carried.
3. **AD-group subjects with MCI-range MMSE (18–26) are NOT discordant** —
   that is the Malone 2013 inclusion criterion (mild AD, MMSE 12–26). Only
   group-AD-with-CN-MMSE or group-CN-with-AD-MMSE count as discordant, and
   both are tracked (`state_discordant_count`) without dropping rows.
4. **Practice effects in a 2-point window.** MIRIAD's dense early scan
   schedule maximizes short-interval MMSE repeats; short-interval reversions
   are more likely measurement artifacts here than in annual-visit cohorts.

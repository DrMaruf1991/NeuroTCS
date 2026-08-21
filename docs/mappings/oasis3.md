# OASIS-3 label mapping — CDR-anchored

**Adapter:** `src/neurotcs/input_contract/v1_1/adapters/adapter_oasis3.py`
**Source file:** `OASIS3_UDSb4_cdr.csv` (UDS Form B4, Global CDR)
**Required columns:** `OASISID`, `days_to_visit`, `CDRTOT` (KeyError if absent)

## Mapping rule (`cdr_to_state`, adapter lines ~87–114)

| `CDRTOT` | State | Basis |
|---|---|---|
| 0.0 | CN | Morris 1993 (PMID 8232972): CDR 0 = no dementia |
| 0.5 | MCI | CDR 0.5 = questionable/very mild impairment |
| ≥ 1.0 | AD | CDR ≥ 1 = dementia |
| 0 < CDR < 0.5 (non-standard, older releases) | MCI | conservative "treat as MCI for safety" |
| NaN / negative / non-numeric | dropped | counted as `unmappable_cdr` |

## Exclusions

1. Rows with null `OASISID` / `days_to_visit` / `CDRTOT` dropped
   (`rows_after_dropna` / `subjects_after_dropna` counters).
2. Rows with unmappable CDR dropped (`unmappable_cdr` counter).
3. Subjects with non-ascending derived dates skipped
   (`skip_invalid=True` default).
4. The trajectory loader keeps single-visit subjects (0 transitions);
   only `build_predictions` (submission-builder path) enforces ≥ 2 visits.

## Visit ordering / dates

OASIS-3 publishes no calendar dates. `days_to_visit` offsets are converted
to synthetic dates from a fixed baseline (2020-01-01); **intervals are
preserved exactly**, and only intervals matter to the audit. Subject IDs are
salted-hashed (`OASIS3_` prefix) by default.

## Edge cases and diagnostics

- Free-text `dx1` (clinical diagnosis) is consumed **only** for
  disagreement diagnostics; it never changes a state and never drops a row.
  Non-AD dementias (DLB, FTD, vascular, PSP) deliberately map to no state in
  the diagnostic comparison so they are not forced into AD staging.
- Locked cohort invariant: 1,377 subjects scored, 7,248 transitions,
  30 flagged (0.41%), cTCS 0.994191.

## Mapping-artifact risks (check before adjudicating a flag as DATA_ERROR)

1. **CDR 0.5 ambiguity.** CDR 0.5 covers both "questionable impairment" and
   early dementia in some clinical usage. A subject oscillating 0 ↔ 0.5 maps
   to CN ↔ MCI; the MCI→CN direction is admissible (≥180 d), but rater
   variability at this boundary can still produce implausible-tier flags
   that are measurement noise, not data errors.
2. **CDR ≥ 1 collapse.** All of CDR 1/2/3 map to AD, so within-dementia
   improvement (e.g. 2 → 1) is invisible — but a 1 → 0.5 change surfaces as
   AD→MCI, which is **inadmissible** under `ad/niaaa_2018`. Adjudicators
   must check the underlying CDR pair before calling this a data error:
   a genuine rater reclassification 1 → 0.5 is a mapping-boundary artifact
   (type-3), not corruption.
3. **Non-AD dementia contamination.** `CDRTOT` stages dementia severity, not
   etiology; an OASIS-3 subject with non-AD dementia is still mapped into
   the AD staging vocabulary. Trajectories that violate AD natural history
   may be legitimate courses of another disease (type-2/rare-biology).

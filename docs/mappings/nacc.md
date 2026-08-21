# NACC label mapping — NACCUDSD-anchored, empirically validated vs CDRGLOB

**Adapter:** `src/neurotcs/input_contract/v1_1/adapters/adapter_nacc.py`
**Source file:** NACC UDS investigator file (e.g. `investigator_nacc73.csv`)
**Required columns:** `NACCID`, `VISITDATE`, `NACCUDSD`. `CDRGLOB`/`CDRSUM`
are read but used only for offline validation of the map, never for state
derivation. Mapping validation is recorded as ERRATA E-2026-003/E-2026-006
(NACC empirical mapping) and in the datasheet cross-tab section.

## Mapping rule (`NACCUDSD_TO_STATE`, adapter lines ~58–64)

| `NACCUDSD` | Meaning | n (of 214,976 visits) | modal `CDRGLOB` | State |
|---|---|---|---|---|
| 1 | Normal cognition | 106,475 | 0.0 (91.4%) | CN |
| 2 | Impaired-not-MCI | 9,575 | 0.5 (65.9%) | MCI |
| 3 | MCI | 37,957 | 0.5 (86.7%) | MCI |
| 4 | Dementia | 60,945 | ≥1.0 bucket (76.0%) | AD |
| 8 | Other/unknown | 24 | mixed | dropped (`naccudsd_8_dropped`) |

`NACCUDSD=5` does not exist in the data (max code is 8); earlier ad hoc
mappings claiming `{1:CN, 3:CN, 4:MCI, 5:Dementia}` are empirically wrong
and must not be used. The adapter warns that this dict must not change
without re-running the cross-tab.

**Documented borderline:** under a strict "single modal CDR ≥50%" reading,
NACCUDSD=4 has modal CDRGLOB=1.0 at only 39.1%; under the clinically
meaningful bucket reading (CDR ≥1.0 at 76.0%, Morris 1993) the 4→AD mapping
is justified. This is recorded in the datasheet (§G) and Errata E-2026-003.

## Exclusions

1. Unparseable `VISITDATE`, missing `NACCID`/`NACCUDSD` → dropped
   (`rows_after_date_filter`).
2. Unmappable `NACCUDSD` (code 8, or any code outside the dict) → dropped
   (`rows_after_state_map`; full code histogram reported).
3. Subjects failing trajectory construction silently skipped
   (`skip_invalid=True` default).
4. Single-visit subjects kept — hence n_scored 39,361 vs n_total 56,529.

## Visit ordering / privacy

Rows sorted by `(NACCID, VISITDATE)`; the adapter builds trajectories
directly. `hash_ids=True` by DEFAULT (DUA compliance): salted SHA-256,
`NACC_` prefix; cell counts <10 must be suppressed by the caller.

## Mapping-artifact risks (check before adjudicating a flag as DATA_ERROR)

1. **NACCUDSD=2 ("impaired-not-MCI") → MCI.** These subjects are explicitly
   adjudicated by NACC as *not* MCI, yet the map places them in MCI (their
   modal CDR is 0.5). Flags on 1↔2 or 2↔3 boundary churn can be pure
   category-collapse artifacts (type-3).
2. **Dementia (4) → AD without etiology filter.** NACCUDSD=4 includes
   non-AD dementias (NACC records etiology separately, e.g. `NACCALZD`,
   which this map does not consult). Reversions or atypical courses may be
   legitimate non-AD trajectories (type-2).
3. **Consensus reclassification.** NACC UDS diagnoses are annual
   consensus-conference outputs; a 4→3 transition is frequently a
   *documented reclassification* (e.g. dementia attributed to resolved
   delirium/depression at the later conference) rather than a data error —
   exactly the reviewer's example. This is the single most important check
   for AD→MCI flags in NACC.
4. **CDR-vs-UDSD discordance.** ~9–24% of visits per code carry a CDR
   outside the modal bucket; a flag driven by a visit whose CDRGLOB
   contradicts its NACCUDSD deserves type-3 scrutiny.

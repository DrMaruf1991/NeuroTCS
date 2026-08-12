# ADNI label mapping — adjudicated-diagnosis-anchored (canonical R-format)

**Adapter:** `src/neurotcs/input_contract/v1_1/adapters/adapter_adni_canonical.py`
**Source:** `ADNIMERGE2/data/DXSUM.rda` (R-format adjudicated diagnosis
table) — NOT the raw `All_Subjects_DXSUM_*.csv`. Source decision, including
the ~10–15% CSV-vs-R disagreement cross-tab, is documented in
`docs/reproducibility/adni_source_decision.md`.
**Columns consumed:** `RID`, `EXAMDATE`, `DIAGNOSIS`.

## Mapping rule (`DIAGNOSIS_MAP`, adapter line ~39)

| `DIAGNOSIS` (string, R table) | State |
|---|---|
| `CN` | CN |
| `MCI` | MCI |
| `Dementia` | AD |
| anything else (incl. missing) | dropped (`rows_after_diagnosis_filter`) |

No CDR or MMSE thresholds are applied on this path: the mapping trusts
ADNI's own adjudicated diagnosis labels.

## Exclusions

1. `DIAGNOSIS` not in {CN, MCI, Dementia} → dropped.
2. Unparseable `EXAMDATE` or missing `RID` → dropped
   (`rows_after_date_filter`).
3. Subjects failing trajectory construction (non-ascending dates) skipped
   (`skip_invalid=True`).
4. Single-visit subjects kept (0 transitions) — hence the n_scored (2,958)
   vs n_total (3,762) split in the datasheet.

## Visit ordering / dates

`EXAMDATE` (coerced datetime) is the ordering key. `hash_ids=False` by
default on this path to reproduce the v1.7.13 published audit_id (raw RID
retained; the demo layer hashes independently).

## SMC / EMCI / LMCI strata

The canonical CN/MCI/AD path does **not** use ADNI's recruitment strata
(SMC/EMCI/LMCI). Those are handled only by the separate
`ad/adni_clinical_stage` rule pack (6-state vocabulary), and the label
ontology explicitly forbids collapsing SMC→CN or EMCI/LMCI→MCI. Auditing
strata data with the 3-state pack (or vice versa) is a vocabulary mismatch
the orchestrator refuses (vocabulary gating, ERRATA E-2026-010 context).

## Mapping-artifact risks (check before adjudicating a flag as DATA_ERROR)

1. **Adjudicated-label revisions.** ADNI diagnoses are consensus labels that
   ADNI itself revises between releases; the R-format table embodies
   re-adjudication (the documented CSV↔R disagreement is 10–15%). A flagged
   reversion (e.g. Dementia→MCI) may be ADNI *correcting its own earlier
   label* — diagnostic reclassification, not data corruption (type-2), or a
   release-skew artifact (type-3).
2. **`Dementia` ≠ AD etiology.** DXSUM `Dementia` includes non-AD dementia
   adjudications in some phases; mapping it to "AD" imports non-AD natural
   histories into AD staging rules.
3. **Release pinning.** Flags are only interpretable against the exact
   DXSUM.rda release named in
   `docs/reproducibility/cohort_input_checksums.md`; re-running against a
   newer release moves labels and can create or dissolve flags with no
   change in NeuroTCS.

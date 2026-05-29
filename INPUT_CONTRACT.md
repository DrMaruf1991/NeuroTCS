# NeuroTCS Input Contract

*Auto-generated from the framework's recognition tables in `neurotcs/cli.py`
(v1.39.2). This file is the published contract: if your data follows it,
`neurotcs describe → audit → verify` runs with zero configuration.*

NeuroTCS is an **auditor**. It does not measure, segment, or compute biomarker
values — it audits values your upstream tools produced against published
staging rules. It **never silently guesses** what your columns mean; everything
below is either an exact match, a documented synonym, or an explicit, visible
fallback.

## The three layers

1. **Strong conventions, auto-recognized.** If your sheets and columns use the
   names below, no mapping is needed.
2. **Fuzzy detection, explicit confirmation.** Unrecognized names get a
   `<FILL:...>` placeholder you edit once. The audit refuses to run on an
   unedited placeholder — it never guesses.
3. **Explicit mapping for custom files.** Non-standard files get a hand-written
   mapping; error messages say exactly which column is missing and where the
   framework looked.

## Recognized sheet names

Matched as case-insensitive substrings of sheet names:

- **Clinical staging axis:** `audit_clinical`, `clinical_audit`, `audit_clin`, `clinical_staging`, `clinical_state`, `clinical`, `staging_clinical`, `diagnosis`, `clin_state`, `dx_state`, `cdr_staging`, `qs`, `dx`
- **Biological (ATN) staging axis:** `audit_biological`, `biological_audit`, `audit_bio`, `biological_staging`, `biological_state`, `biological`, `atn_staging`, `atn_state`, `atn`, `biomarker_staging`, `bio`

Table-of-contents / index sheets (named `Index`, `TOC`, `Manifest`, etc., or
shaped like `[Sheet, Rows, Description]`) are **never** auto-routed. A sheet is
routed to a staging axis only if it ALSO has at least one recognizable
subject-id column and one recognizable state column.

### Candidate measurement sheets (suggested, not auto-assigned)

`describe` SUGGESTS a range-pack domain for these patterns; it does **not**
auto-assign the pack (pack selection must be explicit for citation-locking):

- `mmse` → `ranges/cognitive_scales`
- `moca` → `ranges/cognitive_scales`
- `cdr` → `ranges/cognitive_scales`
- `cognition` → `ranges/cognitive_scales`
- `cog` → `ranges/cognitive_scales`
- `mri` → `ranges/mri_volumetrics`
- `imaging` → `ranges/mri_volumetrics`
- `volumetr` → `ranges/mri_volumetrics`
- `amyloid` → `ranges/pet_amyloid`
- `av45` → `ranges/pet_amyloid`
- `tau_pet` → `ranges/tau_pet`
- `av1451` → `ranges/tau_pet`
- `fdg` → `ranges/fdg_pet`
- `csf` → `ranges/csf_biomarkers`
- `plasma` → `ranges/plasma_biomarkers`
- `dti` → `ranges/dti`
- `perfusion` → `ranges/perfusion`
- `asl` → `ranges/perfusion`
- `oct` → `ranges/retinal_biomarkers`
- `retina` → `ranges/retinal_biomarkers`
- `sleep` → `ranges/sleep`
- `olfact` → `ranges/olfactory`

## Recognized column names (synonyms)

Drawn from CDISC SDTM, ADNI, OASIS, NACC conventions (case-insensitive):

| Canonical field | Recognized synonyms |
|---|---|
| `subject_id` | `subject_id`, `usubjid`, `subjid`, `patient_id`, `patientid`, `rid`, `ptid`, `subject`, `pid`, `id` |
| `visit` | `visit`, `visit_id`, `visitid`, `visitnum`, `visit_code`, `viscode2`, `viscode`, `avisit`, `visitdy`, `event_id`, `event`, `timepoint`, `tp` |
| `visit_date` *(optional)* | `visit_date`, `visit_dt`, `examdate`, `exam_date`, `svstdtc`, `assessment_date`, `scandate`, `scan_date`, `vdate`, `date` |
| `state` (clinical axis) | `clinical_state`, `dx_state`, `clinical_status`, `dx_status`, `diagnosis_state`, `diagnosis_status`, `cog_status`, `cognitive_status`, `dx_bl`, `diagnosis`, `cdglobal`, `dx`, `state`, `clinical_stage` |
| `state` (biological axis) | `biological_stage_atn`, `biological_state`, `biological_stage`, `atn_stage`, `stage_atn`, `atn_profile`, `biological_status`, `atn`, `stage`, `state` |

## Optional fields

- **`visit_date` is optional.** A sheet with a `visit` ordering but no
  recognizable date column makes NeuroTCS derive visit ordering from `visit`
  alone and **disable time-window-dependent checks**. A visible `NOTE` is
  printed and recorded in the bundle's `run_metadata.input_warnings`. Pass
  `--allow-no-dates` to acknowledge explicitly. The audit never crashes for a
  missing date column.

## If your file is different

```
neurotcs describe yourfile.xlsx --emit-mapping mapping.json   # see auto-detection + _notes
# edit any <FILL:...> placeholders
neurotcs audit yourfile.xlsx --mapping mapping.json --dry-run  # verify routing, no bundle
neurotcs audit yourfile.xlsx --mapping mapping.json -o out     # produce the signed bundle
neurotcs verify out
```

## Worked example: zero-editing conventional file

A workbook with `AUDIT_CLINICAL` (`subject_id, visit, visit_date,
clinical_state`) and `AUDIT_BIOLOGICAL` (`subject_id, visit, visit_date,
biological_stage_ATN`) audits with no JSON editing. The same holds for CDISC
SDTM (`USUBJID, VISITNUM, SVSTDTC, ...`) and ADNI exports (`RID, VISCODE,
EXAMDATE, ...`).

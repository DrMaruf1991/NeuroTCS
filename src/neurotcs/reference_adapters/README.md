# `neurotcs.reference_adapters` — Reference vendor adapters

This subpackage hosts **reference submission-builders**, not runtime loaders.

## What lives here

| File | Purpose |
|---|---|
| `adni_categorical_submission.py` | Convert ADNI DXSUM (clinical labels) → NeuroTCS v1.0 categorical submission |
| `adni_volumetric_submission.py` | Convert ADNI FreeSurfer UCSFFSX7 (continuous biomarkers) → NeuroTCS v1.1 submission |

These are CLI scripts that emit JSON manifests in the NeuroTCS input-contract
format. They serve two purposes:

1. **Vendor onboarding.** A vendor whose AI emits longitudinal predictions
   (icometrix, Cortechs.ai, Combinostics, Pixyl, QuantibBrain) clones these
   adapters and modifies them to convert their own pipeline output into a
   conforming submission for NeuroTCS audit.
2. **FDA Q-Sub demonstration.** Worked examples showing the end-to-end path
   from cohort data → submission → audit.

## What does NOT live here

The v1.8 canonical **runtime loaders** that drive `neurotcs.audit()` live
under `src/neurotcs/input_contract/v1_1/adapters/`. These are different
in purpose:

| Location | Purpose | Tested? | Locked? |
|---|---|---|---|
| `src/neurotcs/input_contract/v1_1/adapters/` | Runtime loaders for `audit()` | ✅ | ✅ five locked invariants |
| `src/neurotcs/reference_adapters/` (this dir) | Vendor submission-builder templates | ✅ smoke-tested | n/a (no audit invariants) |

Importing the *old* paths (`from neurotcs.input_contract.v1_1.adapters import
adapter_adni`) still works under v1.8.1 via deprecation shims, but emits a
`DeprecationWarning` pointing here. Plan to migrate; the shims are scheduled
for removal in v1.9.x.

## How to use as a vendor template

```bash
# Clone the categorical template and adapt for your cohort
cp src/neurotcs/reference_adapters/adni_categorical_submission.py \
   my_cohort_submission.py
# Edit: change the column names, the state-label mapping, the cohort salt,
# the output schema fields. The skeleton of the conversion stays the same.

# Run it
python my_cohort_submission.py \
    --input /path/to/my_cohort.csv \
    --out /path/to/submission/
```

## v1.8.1 reorganization notes

In v1.8.0 these files lived at
`src/neurotcs/input_contract/v1_1/adapters/adapter_adni.py` and
`...adapter_adni_volumetric.py`. They were untested standalone scripts
that shipped in the wheel alongside the runtime loaders, causing
confusion about which to use for what.

The v1.8.1 reorganization:

- Moved the files to this dedicated `reference_adapters/` subpackage.
- Renamed for clarity: `adapter_adni.py` → `adni_categorical_submission.py`;
  `adapter_adni_volumetric.py` → `adni_volumetric_submission.py`.
- Added smoke tests under `tests/reference_adapters/`.
- Left deprecation shims at the old paths for backwards compatibility.

The reorganization is structural only — no behavior changed. Existing
external callers using the old paths continue to work but see a
`DeprecationWarning`.

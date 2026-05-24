# ADNI Source Decision: Canonical Data Source for cTCS Audit (v1.8.0)

## Decision

**The canonical ADNI source for NIA-AA 2018 cTCS audit is the R-format
`ADNIMERGE2/data/DXSUM.rda` (adjudicated final diagnosis).**

NOT the raw CSV `All_Subjects_DXSUM_*.csv` (raw clinical form responses).

## Evidence

Cross-validation on 28,352 matched (PTID, EXAMDATE) rows between the two
sources showed ~10–15% disagreement:

| CSV DIAGNOSIS | R = CN | R = MCI | R = Dementia |
|---|---:|---:|---:|
| 1 (CN-form) | 7,456 | 737 | 420 |
| 2 (MCI-form) | 702 | 6,902 | 240 |
| 3 (Dementia-form) | 420 | 252 | 3,123 |

The CSV contains the raw clinical-form entries; the R file contains the
adjudicated final diagnosis after consensus review. Adjudication
reclassifies some borderline cases (CN↔MCI, MCI↔Dementia) based on
biomarker data, neuropsych battery review, and clinician follow-up.

For longitudinal cTCS audit, the **adjudicated final diagnosis is the
clinically meaningful state** at each visit. Using raw form responses
introduces transient noise and inadmissibility flags that would resolve
on adjudication.

## Empirical confirmation

Using R-format DXSUM, the canonical loader reproduces the v1.7.13
published invariants exactly:

- `n_trajectories_scored = 2958` (matches `examples/adni_audit_demo.py`)
- `n_transitions = 12006` (matches docstring)
- `cTCS = 0.994575` → rounds to published 0.9946

Using CSV DXSUM, the same pipeline yields:
- `n_trajectories = 3685`
- `n_transitions = 12321`
- `cTCS = 0.994970`

A ~315-transition difference, fully explained by the adjudication delta.

## Canonical loader

```python
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
    load_adni_trajectories,
)

trajectories, report = load_adni_trajectories(
    "ADNIMERGE2/data/DXSUM.rda",
)
```

The loader uses `pyreadr` to read the `.rda` file. Default `hash_ids=False`
to reproduce the v1.7.13 published audit_id; set `hash_ids=True` for
DUA-style ID hashing at the cost of a different audit_id.

## Note on the legacy submission-builder

The pre-existing `adapter_adni.py` is a **submission-builder** that
converts ADNI into the NeuroTCS input contract format. It is NOT a
trajectory loader for cTCS audit. The two modules serve different
purposes:

| Module | Purpose |
|---|---|
| `neurotcs.reference_adapters.adni_categorical_submission` (v1.8.1+) | Builds NeuroTCS submission tables from ADNI data |
| `neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical` | Loads ADNI trajectories for `neurotcs.audit()` |

**v1.8.1 path change.** Previously the submission-builder lived at
`src/neurotcs/input_contract/v1_1/adapters/adapter_adni.py`. It was moved
to `src/neurotcs/reference_adapters/adni_categorical_submission.py` to
make the runtime-vs-reference distinction structurally explicit. A
deprecation shim at the old path preserves backwards compatibility and
will be removed in v1.9.x.

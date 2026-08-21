# Per-cohort label mappings (CN / MCI / AD)

**Why this directory exists (external expert review, 2026-08).** ADNI, NACC,
OASIS-3 and MIRIAD do not define clinical categories the same way. Every
NeuroTCS cohort result depends on how each dataset's native variables were
mapped into the rule pack's state space, and **a flag can be an artifact of
that mapping rather than a data error**. These documents make each mapping
explicit, auditable, and criticizable — one page per cohort, derived
line-by-line from the shipped adapter code.

| Cohort | Doc | Anchor variable | Mapping style | Adapter |
|---|---|---|---|---|
| OASIS-3 | [oasis3.md](oasis3.md) | `CDRTOT` (Global CDR) | CDR-anchored | `input_contract/v1_1/adapters/adapter_oasis3.py` |
| ADNI | [adni.md](adni.md) | `DIAGNOSIS` (DXSUM.rda, adjudicated) | Diagnosis-label-anchored | `input_contract/v1_1/adapters/adapter_adni_canonical.py` |
| NACC | [nacc.md](nacc.md) | `NACCUDSD` (validated vs `CDRGLOB`) | Diagnosis-code-anchored | `input_contract/v1_1/adapters/adapter_nacc.py` |
| MIRIAD | [miriad.md](miriad.md) | `MMSE` per visit | MMSE-threshold-anchored | `input_contract/v1_1/adapters/adapter_miriad.py` |

## Shared machinery

All adapters except NACC feed `trajectories_from_dataframe`
(`audit_core/trajectory.py`), which drops rows with null date / subject /
state, applies the label map, and sorts by `(subject, visit_date)` — visit
order is **always date order**. `Trajectory` construction rejects strictly
decreasing dates (ties allowed for same-day re-reads); with the default
`skip_invalid=True`, such subjects are skipped and counted. Single-visit
subjects are kept as 1-state trajectories: they contribute 0 transitions and
do not enter the scored denominator (`n_patients_scored` counts subjects
with ≥ 1 transition; this is the `n_scored` vs `n_total` split in the
README/datasheet tables).

## How to use these docs during flag adjudication

For every flag adjudicated under `docs/VALIDATION_PROTOCOL.md`, the type-3
("encoding limitation") decomposition includes **mapping artifacts**: cases
where the underlying source values are internally consistent and the flag
exists only because of how the labels were collapsed into CN/MCI/AD. Each
cohort doc ends with a "Mapping-artifact risks" section listing the known
mechanisms an adjudicator should check before labeling a flag DATA_ERROR.

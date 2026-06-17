# NeuroTCS -- Locked Invariants Summary

**Release:** v1.80.0 | **Commit:** `30886101ab49bacd8ca2122586f566a2b1e16755`
**Source of truth:** `tests/audit_core/test_real_*.py`

> NeuroTCS is a reproducible, fail-closed *auditor*: it audits the cTCS values
> and transition data that other tools produced; it does not measure or diagnose.
> These invariants prove **reproducibility** (same input -> byte-identical
> audit_id), **not** clinical validity. Clinical accuracy (flag PPV / sensitivity)
> is a separate, open question -- see `docs/VALIDATION_PROTOCOL.md` (Arm A).

## What each column means

- **audit_id** -- the byte-exact SHA-256 cryptographic anchor. *This* is the hard
  invariant: any drift on identical input means the pipeline changed. Shown as the
  current locked value (historical pre-correction ids are retained in the test
  files for traceability but are not the active lock).
- **cTCS** -- a derived point statistic with a bootstrap CI; locked to ~4 decimals
  and asserted within tolerance (it is *reproducible-within-tolerance*, not a hash).
- **N** -- cohort size at the locked data freeze. NACC is a freeze-dependent
  *minimum*, not a fixed count.
- **Reproduction** -- ADNI was live-reproduced on v1.80.0 code in-session; the four
  DUA-gated cohorts are reviewer-verifiable on data the reviewer controls.

## The five locked invariants

| Cohort | Status | cTCS (point) | 95% CI (BCa) | audit_id (current) | N | Reproduction |
|---|:---:|---|---|---|---|---|
| OASIS-3 | [OK] | 0.9942 | 0.9902 .. 0.9964 | `92df5429...c9ad6478` | 1,247 scored | reviewer-verifiable (DUA) |
| ADNI | [OK] | 0.994575 (~0.9946) | -- | `7a973f7b...36588f08` | 3,762 traj / 12,006 trans / 2,958 pts | **live-reproduced (this release)** |
| NACC | [OK] | 0.991502 | -- | `58329c65...cfcf07a9` | >=50,000 traj / >=140,000 trans (freeze-dependent) | reviewer-verifiable (DUA) |
| MIRIAD (longitudinal) | [OK] | 0.9854 | 0.9715 .. 0.9937 | `abda26cb...a2c9ee57f` | longitudinal cohort | reviewer-verifiable (DUA) |
| MIRIAD (test-retest) | [OK] | 1.0000 | -- | `4de7f711...b99f499136` | 69 pairs, 0 flagged | reviewer-verifiable (DUA) |

### Full audit_id values

```
OASIS-3:            92df5429ed8439f84a9a65d18b1c489a2b50107facc08e3e59538948c9ad6478
ADNI:               7a973f7b57a91f7cf0af796fd9f69552e14b57aa91f4241fabd5262436588f08
NACC:               58329c656e5ae14c8c6af496a6b526c2f93d317379ba3ffd145776e1cfcf07a9
MIRIAD (long.):     abda26cb4f77c4f5c7644b421b459b79dfa5caf58f32d60860736c6a2c9ee57f
MIRIAD (test-ret.): 4de7f7111aedea86636dae2f81a768a1013849e5949a21062e3bdbd99f499136
```

## Triangulation invariant

[OK] Max pairwise cTCS spread across the cohorts <= 0.01 (an internal
consistency check, not an externally validated threshold):

| Pair | delta cTCS |
|---|---|
| OASIS-3 vs ADNI | 0.0004 |
| OASIS-3 vs MIRIAD | -0.0088 |
| ADNI vs MIRIAD | -0.0092 |

Max absolute spread = 0.0092 <= 0.01.

## How a reviewer verifies these

1. Clone the locked release: `git clone --branch v1.80.0 ...` (commit `30886101`).
2. Install: `pip install -e .` (or `pip install neurotcs==1.80.0` from PyPI).
3. With your own DUA-approved cohort data on disk, run the corresponding
   `tests/audit_core/test_real_*.py` (env-gated by data path). A pass means your
   run reproduced the locked audit_id byte-for-byte.
4. Full protocol + input-file checksums: `reviewer_verification_prompt_v1.80.0.md`
   and the Colab notebook in this folder (framework-only, zero-install).

## Honest scope

These invariants demonstrate the audit pipeline is deterministic and
cross-platform-stable. They do **not** establish that NeuroTCS's flags are
clinically correct -- that requires adjudicated validation against ground truth
(DUA cohort, blinded reviewers, biostatistician co-author, OSF pre-registration),
which is documented as open future work, not claimed here.

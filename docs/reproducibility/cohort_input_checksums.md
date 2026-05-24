# Cohort Input File SHA-256 Checksums (v1.8.0)

This document publishes the SHA-256 checksums of every cohort input file
used to derive the v1.8 locked audit_ids. A reviewer reproducing the v1.8
results must verify these checksums match their local copies before
re-running.

Closes the v1.7.13 honest gap: *"Cohort CSV checksums not yet published."*

## Files

### OASIS-3

| File | Size (bytes) | SHA-256 (first 16 chars) |
|---|---:|---|
| `OASIS3_UDSb4_cdr.csv` | 915,615 | `7c9070af2d72dc34` |
| `OASIS3_demographics.csv` | 77,999 | `6875561898bafe02` |

### ADNI (canonical R-format)

| File | Size (bytes) | SHA-256 (first 16 chars) |
|---|---:|---|
| `ADNIMERGE2/data/DXSUM.rda` | 225,634 | `ca5c11b9228511c2` |
| `ADNIMERGE2.tar.gz` (source archive) | 82,668,578 | `c2b2973e3216a6da` |
| `All_Subjects_PTDEMOG_19May2026.csv` | 2,274,093 | `2b00c09eabb5ca8e` |
| `APOERES_19May2026.csv` | 326,246 | `2a00213aedf5e699` |

### NACC

| File | Size (bytes) | SHA-256 (first 16 chars) |
|---|---:|---|
| `investigator_nacc73.csv` (full) | 997,611,978 | `a21a8537dc8ca679` |
| `investigator_nacc73_slim.csv` (used in audit) | 16,007,986 | `7a349eb84920d366` |

The slim CSV contains only the columns needed for cTCS + fairness panel
(NACCID, VISITDATE, NACCUDSD, NACCAGE, NACCSEX, NACCNIHR, NACCHISP,
NACCEDULVL, NACCAPOE, NACCNE4S, CDRGLOB, CDRSUM, and a few additional
diagnostic fields). It is generated from the full file with `pandas.read_csv(usecols=...)`
followed by `to_csv(...)` and is a strict subset of the full file's content.

### MIRIAD

| File | Size (bytes) | SHA-256 (first 16 chars) |
|---|---:|---|
| `DrMaruf_5_18_2026_12_16_7.csv` (ClinicalAssessment) | 18,666 | `a322fe6401b2daa8` |
| `DrMaruf_5_18_2026_12_16_24.csv` (MR_Sessions) | 37,599 | `149270d341ac0221` |
| `DrMaruf_5_18_2026_12_16_33.csv` (Subjects) | 1,695 | `bf2701961ede888d` |

## Computing the full SHA-256

```bash
sha256sum OASIS3_UDSb4_cdr.csv
sha256sum ADNIMERGE2/data/DXSUM.rda
sha256sum investigator_nacc73_slim.csv
# ...etc
```

If any of these checksums differ on your local copy, do not expect the v1.8
locked audit_ids to reproduce. Either the data freeze has changed, the file
is corrupted, or the file is from a different source.

## v1.8 locked audit_ids depend on these inputs

| Cohort | cTCS | audit_id |
|---|---:|---|
| OASIS-3 | 0.994191 | `766ffc5f26eae47fb95eddd21e33bbecb798989304ed17584db15aa0d4740f90` |
| ADNI | 0.994575 | `9e708f2ebd610e8ffe0abbc01d867ff34ff61fcd6aba14e2d6a293cd650e2b16` |
| NACC | 0.991502 | `def60e6836a5a9feecc666dc558c5b115973f73dd65dd42ef13969819318754c` |
| MIRIAD | 0.985369 | `947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0` |
| MIRIAD test-retest | 1.000000 | `804303993ff5c9134b5f4dfa8919fc6600d03a86081cedb02227ef5845784e85` |

Four-cohort triangulation: max ΔcTCS = 0.009206 (ADNI vs MIRIAD), all 6
pairs ≤ 0.01 world-class threshold.

## Cross-platform reproducibility note

The audit_id formula uses explicit little-endian byte order
(`.astype("<f8")` for floats, `.astype("<i8")` for int64 counts) so that
the hash is identical across big-endian and little-endian platforms. See
`src/neurotcs/audit_core/audit.py:_compute_audit_id` for the canonical
implementation.

Per-platform verification status:
- Linux x86_64, Python 3.12.3, numpy 2.4.4, pandas 3.0.2: **confirmed**
- Linux x86_64, Python 3.12.3, numpy 2.0.2: **confirmed** (cross-numpy-version)
- Linux x86_64, Python 3.12.3, pyreadr 0.5.0 vs 0.5.6: **confirmed** (cross-pyreadr-version)
- **Windows 10/11 x86_64, Python 3.12.7, pyreadr 0.5.x: confirmed (2026-05-24)**
  All 5 locked audit_ids reproduce byte-exactly; full pytest 408/408 passes.
  The pyreadr `datetime64[D]` cast RuntimeWarning is benign and does not affect
  audit_id (downstream date handling normalizes via `pd.to_datetime`).
- macOS: not yet independently verified.

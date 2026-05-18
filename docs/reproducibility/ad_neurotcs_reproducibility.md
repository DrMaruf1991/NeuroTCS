# AD NeuroTCS — Reproducibility Report

**Status**: AD-lock Step 2.4 deliverable. Shipped in NeuroTCS v1.7.12.
**Audience**: external collaborators, reviewers, FDA / EU AI Act auditors,
journal peer reviewers who want to verify the AD validation locked
invariants bit-exactly on their own machine.

This document plus `requirements.lock` plus `scripts/compute_input_checksums.py`
constitute the **reproducibility certificate** for the cryptographic anchors
in `docs/datasheet/ad_neurotcs_datasheet.md` Section A. Following the
canonical command sequence below, you obtain bit-identical audit_ids on
your machine.

---

## 1. Reproducibility guarantee

The following table lists the exact invariants you should reproduce. If
your run produces these values, the AD validation has been verified end-to-end
on your machine.

### 1.1 — Code identity (rule packs)

These SHA-256 hashes are computed by `LoadedRulePack.sha256` from the
shipped YAML files. They are bit-identical across platforms (Linux / macOS /
Windows) because the loader canonicalises the YAML before hashing.

| Rule pack | rulepack_id | schema_version | SHA-256 |
|---|---|---|---|
| `ad/niaaa_2018` | `ad/niaaa_2018@1.2.0` | 1.1.0 | `f359148d1cbf6abed3d4f1d36de6b3bf315c10e8997d5e73beb1a0d7bdf9e374` |
| `ad/aa_2024` | `ad/aa_2024@1.2.0` | 1.1.0 | `e6fb93d7fe5e19eb503eccca932f660361e135a2b2ae0391456c4bee0d656af5` |
| `ad/aa_2024_trac` | `ad/aa_2024_trac@1.0.0` | 1.2.0 | `b704a4d21efbe893dead9ea906940c5e61196f9db7f938df55b506cbee6be6e7` |

### 1.2 — Audit identity (cohort-level)

For each cohort, running the canonical audit command on the SAME input
CSVs with the SAME rule pack and SAME seed must produce these identifiers.
A divergence is a regression to investigate; do NOT silently accept a
different hash.

| Cohort | n_transitions | n_flagged | cTCS (BCa 95% CI) | audit_id (SHA-256) | audit_id_v2 |
|---|---|---|---|---|---|
| ADNI-2/3/4 | 12,006 | 65 (0.54%) | 0.9946 | `d344ec1a...` (full hash in Section A of datasheet) | locked locally on maintainer's machine |
| OASIS-3 | 7,248 | 30 (0.41%) | 0.9942 (0.9902–0.9964) | locked locally | locked locally |
| MIRIAD longitudinal | 454 | 7 (1.54%) | 0.9854 (0.9715–0.9937) | `947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0` | `aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da` |
| MIRIAD test-retest | 69 | 0 (0.00%) | 1.0000 | `804303993ff5c9134b5f4dfa8919fc6600d03a86081cedb02227ef5845784e85` | `dcf8b7de3ff9019e9cda703064039e3a71193566d1f5082ce96646188fd52fc4` |

### 1.3 — Test-suite identity

| Run | Expected outcome |
|---|---|
| `pytest tests/ -q` on this version, no env vars | **331 passed, 2 skipped** |
| `pytest tests/ -q` with `NEUROTCS_MIRIAD_DIR` pointing at the canonical CSVs | **333 passed, 0 skipped** (the two skips become asserting tests) |
| Same command run twice consecutively | identical outcome both times (double-test rule) |

The 2 skips are real-MIRIAD locked-invariant tests that engage only when
the CSVs are available. They are NOT "TODO" tests — they are hard
equality assertions that pass on the maintainer's machine and skip
cleanly elsewhere.

---

## 2. Canonical environment

Reproduction requires the EXACT versions in `requirements.lock`. Floors
declared in `pyproject.toml` describe what NeuroTCS minimally supports;
pins in `requirements.lock` describe what NeuroTCS was tested with for
the locked invariants above.

### 2.1 — Operating system

The reference build was produced on:

- **OS**: Ubuntu 24.04 LTS (sandbox build)
- **Kernel**: 6.x stock
- **C compiler for native wheels**: GCC 13.3.0

The locked invariants reproduce on Windows 11 and macOS 14+ as long as the
Python and package versions in `requirements.lock` are installed. The
maintainer's primary verification runs on Windows 11 + PowerShell + Python
3.12 via pip from PyPI.

### 2.2 — Python version

- **Python**: 3.12.3 (or 3.12.x with the same patch family). Other 3.12.x
  patches are expected to reproduce identically but only 3.12.3 has been
  exhaustively verified.

### 2.3 — Locked dependency versions

Reproduced here for completeness; canonical source is `requirements.lock`
in the repo root.

| Package | Pinned version |
|---|---|
| pydantic | 2.13.4 |
| PyYAML | 6.0.3 |
| pandas | 3.0.2 |
| pyarrow | 24.0.0 |
| jsonschema | 4.26.0 |
| pyreadr | 0.5.6 |
| numpy | 2.4.4 |
| scipy | 1.17.1 |
| pytest | 9.0.3 |
| ruff | 0.15.13 |

`pytest-cov` and `fhir.resources` are declared in `pyproject.toml` for
developer convenience but are NOT required to verify the locked invariants.
Omit them if you only want to run the verification pipeline.

### 2.4 — Random seed and bootstrap parameters

These are baked into the audit:

| Parameter | Locked value |
|---|---|
| `seed` | 42 |
| `bootstrap_B` | 10,000 |
| `ci_method` | `"bca"` (bias-corrected and accelerated) |
| `prior_type` | `"clinical"` |

Any change to these values produces a different audit_id by design. The
audit_id IS the cryptographic fingerprint of (rulepack, per-patient
scores, bootstrap-B, seed, CI-method, prior-type).

---

## 3. Canonical command sequence

This is the single sequence of commands an external collaborator runs to
verify the AD validation end-to-end. It assumes you have already obtained
the cohort CSVs from their respective providers (ADNI, OASIS-3, MIRIAD)
under each provider's data use agreement.

### 3.1 — Step 1: clone and install

```bash
git clone https://github.com/DrMaruf1991/NeuroTCS.git
cd NeuroTCS
git checkout v1.7.12     # or whatever tag you're verifying against
pip install -r requirements.lock
pip install -e .
```

PowerShell equivalent (Windows):

```powershell
git clone https://github.com/DrMaruf1991/NeuroTCS.git
cd NeuroTCS
git checkout v1.7.12
pip install -r requirements.lock
pip install -e .
```

### 3.2 — Step 2: verify code + rule-pack identity

Before touching cohort data, verify the code you cloned is the code that
produced the locked invariants:

```bash
# Rule-pack SHA-256 — must match Section 1.1 above
python -c "from neurotcs import load_rulepack; \
    p = load_rulepack('ad/niaaa_2018'); \
    print(p.sha256)"
# Expected: f359148d1cbf6abed3d4f1d36de6b3bf315c10e8997d5e73beb1a0d7bdf9e374

python -c "from neurotcs import load_rulepack; \
    p = load_rulepack('ad/aa_2024'); \
    print(p.sha256)"
# Expected: e6fb93d7fe5e19eb503eccca932f660361e135a2b2ae0391456c4bee0d656af5

python -c "from neurotcs import load_rulepack; \
    p = load_rulepack('ad/aa_2024_trac'); \
    print(p.sha256)"
# Expected: b704a4d21efbe893dead9ea906940c5e61196f9db7f938df55b506cbee6be6e7
```

If any of these three hashes diverges, your local rule packs have been
modified or the wrong tag was checked out. Do NOT proceed.

### 3.3 — Step 3: run the offline test suite

```bash
pytest tests/ -q
# Expected (no env vars): 331 passed, 2 skipped
```

Run it a SECOND time to confirm reproducibility:

```bash
pytest tests/ -q
# Expected: identical to first run
```

If the outcomes differ between runs, you have non-determinism that must
be investigated before proceeding.

### 3.4 — Step 4 (optional): verify cohort CSV integrity

If you intend to reproduce the cohort-level audit_ids (Section 1.2),
first verify your downloaded CSVs match the ones that produced the
locked hashes.

The CSV file SHA-256 checksums are **not** distributed in this repository
(because the CSVs themselves are not redistributed — each cohort has its
own data use agreement). They are obtained from the maintainer at the
time of blind validation, or you can publish your own and use them for
your own future reproducibility verification.

Compute checksums of your downloaded files:

```bash
python scripts/compute_input_checksums.py \
    /path/to/your/clinical.csv \
    /path/to/your/sessions.csv \
    /path/to/your/subjects.csv
```

PowerShell equivalent (Windows native; no Python needed):

```powershell
Get-FileHash -Algorithm SHA256 `
    "$env:USERPROFILE\Downloads\DrMaruf_5_18_2026_12_16_7.csv", `
    "$env:USERPROFILE\Downloads\DrMaruf_5_18_2026_12_16_24.csv", `
    "$env:USERPROFILE\Downloads\DrMaruf_5_18_2026_12_16_33.csv"
```

Both produce identical hex digests. Compare against the maintainer's
locked checksum table (provided separately under DUA-compliant
channel). If you obtain different hashes, you have a different version
of the cohort data and the audit_id will not match expected.

### 3.5 — Step 5: run the MIRIAD audit (the cohort with full local
support)

```bash
# Linux / macOS
export NEUROTCS_MIRIAD_DIR=/path/to/miriad/csvs
pytest tests/audit_core/test_real_miriad_audit.py -v
# Expected: all assertions pass; audit_ids 947ab24e... and 80430399...
# reproduce exactly.
```

```powershell
# Windows
$env:NEUROTCS_MIRIAD_DIR = "$env:USERPROFILE\Downloads"
pytest tests/audit_core/test_real_miriad_audit.py -v
```

### 3.6 — Step 6 (optional): run the AD fairness audit

This step requires the v1.7.10 fairness pipeline. Produces both JSON
and human-readable text reports linked to the audit_id from Step 5.

```bash
python scripts/run_ad_fairness_audit.py \
    --cohort   miriad \
    --clinical /path/to/clinical.csv \
    --sessions /path/to/sessions.csv \
    --subjects /path/to/subjects.csv \
    --rulepack ad/niaaa_2018 \
    --out      /path/to/output_dir/
```

The `ad_fairness_report.json` produced will contain the same `audit_id`
as Step 5, plus per-stratum flag rates.

### 3.7 — Step 7: verify all citations

```bash
python scripts/verify_citations.py --offline
# Expected: "Scanning 190 citation references"
# "All structural checks passed (offline mode)."
```

---

## 4. Cohort access notes

The three cohorts have separate access procedures. NeuroTCS does NOT
redistribute any of these.

### 4.1 — ADNI

- Apply at [adni.loni.usc.edu](https://adni.loni.usc.edu) with your IRB
  protocol number and institutional affiliation. Approval is typically
  granted within 2 weeks.
- Download DXSUM and PTDEMOG (and APOE for APOE4 stratification).
- Cite: Mueller SG, Weiner MW, Thal LJ, et al. The Alzheimer's Disease
  Neuroimaging Initiative. *Neuroimaging Clin N Am* 2005;15:869-877.

### 4.2 — OASIS-3

- Apply at [oasis-brains.org](https://www.oasis-brains.org/) with your
  IRB protocol number.
- Download the `OASIS3_UDSb4_cdr.csv` longitudinal CDR table plus
  demographics.
- Cite: LaMontagne PJ, Benzinger TLS, Morris JC, et al. OASIS-3:
  Longitudinal Neuroimaging, Clinical, and Cognitive Dataset for Normal
  Aging and Alzheimer Disease. *medRxiv* 2019. (Plus the published
  follow-up; consult the OASIS-3 citation page for the current
  authoritative reference.)

### 4.3 — MIRIAD

- Apply at the UCL Dementia Research Centre. MIRIAD is freely available
  for non-commercial research subject to a brief DUA.
- The XNAT export produces three CSVs (Clinical Assessment, MR Sessions,
  Subjects). NeuroTCS adapters resolve their column layouts defensively.
- Cite: Malone IB, Cash D, Ridgway GR, et al. MIRIAD—Public release of a
  multiple time point Alzheimer's MR imaging dataset. *NeuroImage*
  2013;70:33-36. PMID 23274184. DOI 10.1016/j.neuroimage.2012.12.044.

---

## 5. What this report covers — and what it does not

### 5.1 — Covered by this report

- ✅ Code identity: rule-pack SHA-256 hashes.
- ✅ Environment identity: Python + package version pins.
- ✅ Audit-pipeline identity: seed, bootstrap_B, CI method, prior_type.
- ✅ Test-suite identity: 331 passed, 2 skipped (or 333 passed, 0
  skipped with MIRIAD CSVs present).
- ✅ Locked audit_ids for MIRIAD longitudinal and test-retest.
- ✅ Cross-platform CSV-checksum command using only stdlib /
  system tools.

### 5.2 — Not covered (honest gaps)

- ❌ **Cohort CSV checksums are not yet published** in this repository.
  Each cohort's CSVs are under DUA — the maintainer can share the
  reference checksums under the DUA channel; they will be added to a
  future release once a stable per-cohort snapshot is identified.
- ❌ **ADNI and OASIS-3 audit_ids are not yet locked in CI tests**.
  These live on the maintainer's machine; CI runs only the MIRIAD
  invariants. Adding ADNI/OASIS-3 to CI requires either uploading the
  CSVs (DUA-prohibited) or installing them via a private CI runner.
- ❌ **The Jack 2024 PDF transcription is pending**. The `ad/aa_2024`
  rule pack ships a structural skeleton; full §3 staging text awaits
  PDF acquisition. See `docs/datasheet/ad_neurotcs_datasheet.md`
  Section F gap #1.

These are documented honestly per the AD-lock no-future-fix discipline.
A reviewer should know that the AD validation is fully reproducible for
MIRIAD today; ADNI and OASIS-3 reproducibility extends to "verify on
your own data, with cryptographic identity of the rule pack and
audit pipeline".

---

## 6. Troubleshooting a divergent run

If your audit_id differs from the expected value, work through this
checklist in order:

1. **Rule-pack SHA mismatch (Step 3.2)?** You have a modified rule
   pack. Re-clone the tag.
2. **`pytest` not at 331 passed + 2 skipped (Step 3.3)?** Your
   environment has a dependency at a different version. Re-install
   from `requirements.lock`.
3. **Cohort CSV SHA-256 mismatch (Step 3.4)?** You have a different
   snapshot of the cohort data. Re-download from the provider's
   canonical source.
4. **Non-deterministic results (Step 3.3 second run differs from
   first)?** Your environment has non-deterministic numeric behaviour.
   Check that `numpy` and `scipy` are at the pinned versions and that
   no `OMP_NUM_THREADS` / `MKL_*` env vars are set to non-default
   values.
5. **Still diverging after the above four checks?** Open a GitHub Issue
   at `DrMaruf1991/NeuroTCS/issues` with your environment details
   (Python version, OS, locked dependency versions, the divergent
   audit_id you obtained). The maintainer will investigate as a
   regression.

---

## 7. Citation

Salokhiddinov M. NeuroTCS: a citation-locked temporal coherence audit
framework for Alzheimer's disease cohort validation — reproducibility
report. NeuroTCS v1.7.12, AD-lock Step 2.4 deliverable. 2026.
[https://github.com/DrMaruf1991/NeuroTCS](https://github.com/DrMaruf1991/NeuroTCS).

Companion documents:

- `docs/datasheet/ad_neurotcs_datasheet.md` — four-framework consolidation.
- `docs/validation/ad_fairness_audit.md` — FUTURE-AI Panel B.4.4 validation.
- `docs/reproducibility/blind_validation_protocol.md` — blind-validation
  protocol for collaborators with their own cohorts (AD-lock Step 2.5).

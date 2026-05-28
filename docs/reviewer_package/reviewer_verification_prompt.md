# NeuroTCS v1.8.0 — Third-Party Reproducibility Verification Prompt v2

**Status:** v2 (canonical). Supersedes v1.
**Repository:** `https://github.com/DrMaruf1991/NeuroTCS` (Apache-2.0, currently Private)
**Locked release:** tag `v1.8.0` at commit `9e8f693e3d5576e7c52507f4ee7f66699c1f6ce1`
**Last reproducibility commit on main:** `80ec637` (Windows verification, 2026-05-24)
**Length:** ~250 lines. Expected reviewer time: 90 minutes (full) or 25 minutes (framework-only).

---

## Audience

This protocol enables independent technical reviewers to verify the NeuroTCS v1.8.0 framework reproduces five locked audit invariants on cohort data the reviewer controls under their own Data Use Agreements. Primary audiences:

- FDA CDRH technical staff (Q-Sub Volume I Performance Testing supporting evidence)
- Pharma diligence teams (icometrix, Cortechs.ai, QuantiB, Combinostics, Riverain, Aidence, Optellum, Subtle Medical, Rad AI, Aidoc)
- Academic peer reviewers (Nature Medicine, Lancet Digital Health, Radiology AI)
- Hospital AI governance committees (ARCH-AI / Assess-AI per ACR-SIIM Practice Parameter, approved 5 May 2026)
- ESNR-BRACCO independent validators

## What this protocol proves and does not prove

**Proves:** the v1.8.0 audit pipeline is deterministic, cross-platform-stable, and reproduces the five locked invariants byte-exactly on identical inputs.

**Does not prove:** clinical validity, fitness for any specific clinical decision, FDA clearance, or deployment readiness. Clinical validity will be established by the Aim 1–5 study results per project proposal (in execution W1–W22 of the 21-week timeline; Nature Medicine submission W22; FDA Q-Submission Q1 2027).

## Security posture

This protocol runs locally in a Python virtual environment. The framework makes no outbound network calls beyond the initial `git clone` and `pip install`. No cohort data leaves the reviewer's machine. The Apache-2.0 license grants the reviewer full inspection, modification, and redistribution rights.

---

## Prerequisites

| Item | Requirement |
|---|---|
| OS | Linux x86_64 (kernel ≥ 5.x) or Windows 10/11 x86_64. macOS will likely work but is not yet observed-verified by the sponsor. |
| Python | 3.10, 3.11, 3.12, or 3.13 |
| RAM | ≥ 8 GB |
| Disk | ~2 GB free |
| Cohort data under DUA | At minimum **one** of: NACC investigator file, ADNI `DXSUM.rda` from `ADNIMERGE2` R package, OASIS-3 `OASIS3_UDSb4_cdr.csv`, MIRIAD three-CSV bundle. Sponsor cannot lawfully provide any of these. |
| Time | 90 minutes (full four-cohort verification) or 25 minutes (framework-only check at Steps 1–3) |

---

## Locked invariants — the canonical reference

These are the five values your verification must reproduce when your input file SHA-256s match the manifest below. Source of truth: the LOCKED_AUDIT_ID constants in `tests/audit_core/test_real_*.py` in the v1.8.0 release.

```
OASIS-3:            cTCS=0.994191  audit_id=92df5429ed8439f84a9a65d18b1c489a2b50107facc08e3e59538948c9ad6478
ADNI:               cTCS=0.994575  audit_id=7a973f7b57a91f7cf0af796fd9f69552e14b57aa91f4241fabd5262436588f08
NACC:               cTCS=0.991502  audit_id=58329c656e5ae14c8c6af496a6b526c2f93d317379ba3ffd145776e1cfcf07a9
MIRIAD:             cTCS=0.985369  audit_id=abda26cb4f77c4f5c7644b421b459b79dfa5caf58f32d60860736c6a2c9ee57f
MIRIAD test-retest: cTCS=1.000000  audit_id=4de7f7111aedea86636dae2f81a768a1013849e5949a21062e3bdbd99f499136
```

**Triangulation invariant:** max pairwise ΔcTCS across all four cohorts ≤ 0.01 (sponsor-observed: 0.009206, ADNI vs MIRIAD).

## Expected input-file SHA-256 prefixes (first 16 chars)

These prefixes are sufficient to detect file-version mismatch without printing 64-character strings inline. Full 64-char values are available in `docs/reproducibility/cohort_input_checksums.md` of the release.

```
OASIS3_UDSb4_cdr.csv                    915,615 bytes    7c9070af2d72dc34
ADNIMERGE2/data/DXSUM.rda               225,634 bytes    ca5c11b9228511c2
investigator_nacc73_slim.csv         16,007,986 bytes    7a349eb84920d366
investigator_nacc73.csv (full)      997,611,978 bytes    a21a8537dc8ca679
MIRIAD ClinicalAssessment.csv            18,666 bytes    a322fe6401b2daa8
MIRIAD MR_Sessions.csv                   37,599 bytes    149270d341ac0221
MIRIAD Subjects.csv                       1,695 bytes    bf2701961ede888d
```

The NACC audit is run on the **slim** subset (16 MB), generated from the full investigator file by column whitelist. Both produce identical audit_ids; the slim file is provided for memory-constrained reviewers. If your NACC file is from a different freeze, expect a different audit_id but cTCS should still fall in [0.95, 1.00].

---

## The protocol — eight steps

### STEP 1 — Environment isolation (~2 minutes)

```bash
python3 -m venv neurotcs_audit_env
source neurotcs_audit_env/bin/activate          # Linux/macOS
# .\neurotcs_audit_env\Scripts\Activate.ps1     # Windows PowerShell

python --version
# EXPECT: Python 3.10.x, 3.11.x, 3.12.x, or 3.13.x
```

### STEP 2 — Clone the locked release (~1 minute)

```bash
git clone https://github.com/DrMaruf1991/NeuroTCS.git
cd NeuroTCS
git checkout v1.8.0
git rev-parse HEAD
# EXPECT: 9e8f693e3d5576e7c52507f4ee7f66699c1f6ce1
```

If the SHA does not match exactly, either the release has been force-pushed (record this) or you cloned the wrong repo. STOP.

```bash
head -2 LICENSE
# EXPECT: Apache License, Version 2.0
```

### STEP 3 — Install and run the framework-only test suite (~5 minutes)

```bash
python -m pip install -e . --quiet
python -c "import neurotcs; assert neurotcs.__version__ == '1.8.0'; print('OK', neurotcs.__version__)"

# Run the framework-only tests (no cohort data required):
python -m pytest tests/ -q \
    --ignore=tests/audit_core/test_real_adni_audit.py \
    --ignore=tests/audit_core/test_real_oasis3_audit.py \
    --ignore=tests/audit_core/test_real_nacc_audit.py \
    --ignore=tests/audit_core/test_real_miriad_audit.py \
    --ignore=tests/audit_core/test_real_miriad_fairness_audit.py \
    --ignore=tests/audit_core/test_four_cohort_triangulation.py
```

EXPECT: `400 passed, 0 failed` on a clean install where no cohort env vars are set. (The count rises to `408 passed` when all four cohort env vars from Step 4 are set and point at valid files.) Any failure here indicates the framework is broken on your environment independent of cohort data. STOP and document the failure verbatim before proceeding.

**Reviewers without cohort data can stop after Step 3 and produce a "FRAMEWORK_INSTALL_VERIFIED" partial attestation. Steps 4–8 require cohort data.**

### STEP 4 — Compute SHA-256 of your input files (~5 minutes)

Linux/macOS:
```bash
sha256sum /path/to/OASIS3_UDSb4_cdr.csv
sha256sum /path/to/ADNIMERGE2/data/DXSUM.rda
sha256sum /path/to/investigator_nacc73_slim.csv
sha256sum /path/to/MIRIAD/DrMaruf_5_18_2026_12_16_7.csv
sha256sum /path/to/MIRIAD/DrMaruf_5_18_2026_12_16_24.csv
sha256sum /path/to/MIRIAD/DrMaruf_5_18_2026_12_16_33.csv
```

Windows PowerShell:
```powershell
Get-FileHash <path> -Algorithm SHA256
```

For each file you have access to, record the first 16 chars and compare to the manifest above. If your hashes match, you expect to reproduce the locked audit_ids byte-exactly. If they differ (different DUA freeze), you expect different audit_ids but cTCS in [0.95, 1.00].

### STEP 5 — Set environment variables (~1 minute)

Linux/macOS:
```bash
export NEUROTCS_OASIS3_CDR=/path/to/OASIS3_UDSb4_cdr.csv
export NEUROTCS_ADNI_DXSUM_RDA=/path/to/ADNIMERGE2/data/DXSUM.rda
export NEUROTCS_NACC_CSV=/path/to/investigator_nacc73_slim.csv
export NEUROTCS_MIRIAD_DIR=/path/to/MIRIAD_directory_containing_three_csvs
```

Windows PowerShell:
```powershell
$env:NEUROTCS_OASIS3_CDR = "C:\path\OASIS3_UDSb4_cdr.csv"
$env:NEUROTCS_ADNI_DXSUM_RDA = "C:\path\ADNIMERGE2\data\DXSUM.rda"
$env:NEUROTCS_NACC_CSV = "C:\path\investigator_nacc73_slim.csv"
$env:NEUROTCS_MIRIAD_DIR = "C:\path\MIRIAD"
```

Verify with `Test-Path` (Windows) or `[ -f $X ]` (Linux/macOS) before proceeding.

### STEP 6 — Run cohort regression tests (~3 minutes)

```bash
python -m pytest tests/audit_core/test_real_oasis3_audit.py \
                 tests/audit_core/test_real_adni_audit.py \
                 tests/audit_core/test_real_nacc_audit.py \
                 tests/audit_core/test_real_miriad_audit.py \
                 tests/audit_core/test_real_miriad_fairness_audit.py \
                 tests/audit_core/test_four_cohort_triangulation.py \
                 -v
```

EXPECT IF YOUR INPUT HASHES MATCHED MANIFEST: every test passes; locked audit_ids reproduce.

EXPECT IF HASHES DIFFERED: audit_id assertion tests fail with a clear message showing observed vs locked. cTCS plausibility is still verified in Step 7.

### STEP 7 — Programmatic audit_id verification (~5 minutes)

Run this Python block. It uses the **exact** parameters required to reproduce the locked invariants — every flag matters.

```python
import os, sys
from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import load_oasis3_trajectories
from neurotcs.input_contract.v1_1.adapters.adapter_nacc import load_nacc_trajectories
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import load_adni_trajectories
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    load_miriad_trajectories, load_miriad_test_retest_pairs,
)

LOCKED = {
    "OASIS-3":            ("0.994191", "92df5429ed8439f84a9a65d18b1c489a2b50107facc08e3e59538948c9ad6478"),
    "ADNI":               ("0.994575", "7a973f7b57a91f7cf0af796fd9f69552e14b57aa91f4241fabd5262436588f08"),
    "NACC":               ("0.991502", "58329c656e5ae14c8c6af496a6b526c2f93d317379ba3ffd145776e1cfcf07a9"),
    "MIRIAD":             ("0.985369", "abda26cb4f77c4f5c7644b421b459b79dfa5caf58f32d60860736c6a2c9ee57f"),
    "MIRIAD-test-retest": ("1.000000", "4de7f7111aedea86636dae2f81a768a1013849e5949a21062e3bdbd99f499136"),
}

rp = load_rulepack("ad/niaaa_2018")
results = {}

# OASIS-3
if os.environ.get("NEUROTCS_OASIS3_CDR"):
    t, _ = load_oasis3_trajectories(
        udsb4_csv_path=os.environ["NEUROTCS_OASIS3_CDR"],
        flag_dx1_disagreement=True, hash_ids=True, skip_invalid=True,
    )
    r = audit(t, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    results["OASIS-3"] = (f"{r.ctcs.ci.point:.6f}", r.audit_id)

# ADNI: hash_ids=False to reproduce locked audit_id.
# NOTE — hash_ids parity exception: ADNI's locked audit_id was captured with
# hash_ids=False (the v1.7.13 published demo did not hash RIDs). The other
# three cohorts (OASIS-3, NACC, MIRIAD) lock with hash_ids=True (DUA-compliant
# default). This is INTENTIONAL — the locked invariants for each cohort
# reproduce the exact value captured at lock time. Do not change these flags
# during reviewer verification.
if os.environ.get("NEUROTCS_ADNI_DXSUM_RDA"):
    t, _ = load_adni_trajectories(
        dxsum_rda_path=os.environ["NEUROTCS_ADNI_DXSUM_RDA"],
        hash_ids=False, skip_invalid=True,
    )
    r = audit(t, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    results["ADNI"] = (f"{r.ctcs.ci.point:.6f}", r.audit_id)

# NACC
if os.environ.get("NEUROTCS_NACC_CSV"):
    t, _ = load_nacc_trajectories(
        nacc_csv_path=os.environ["NEUROTCS_NACC_CSV"],
        hash_ids=True, skip_invalid=True,
    )
    r = audit(t, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    results["NACC"] = (f"{r.ctcs.ci.point:.6f}", r.audit_id)

# MIRIAD — exclude_test_retest_rescans=True is REQUIRED for the lock
if os.environ.get("NEUROTCS_MIRIAD_DIR"):
    d = os.environ["NEUROTCS_MIRIAD_DIR"]
    t, _ = load_miriad_trajectories(
        clinical_csv=f"{d}/DrMaruf_5_18_2026_12_16_7.csv",
        sessions_csv=f"{d}/DrMaruf_5_18_2026_12_16_24.csv",
        subjects_csv=f"{d}/DrMaruf_5_18_2026_12_16_33.csv",
        flag_group_disagreement=True, hash_ids=True, skip_invalid=True,
        exclude_test_retest_rescans=True,   # MUST be True for the lock
    )
    r = audit(t, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    results["MIRIAD"] = (f"{r.ctcs.ci.point:.6f}", r.audit_id)

    # MIRIAD test-retest pairs
    pairs, _ = load_miriad_test_retest_pairs(
        clinical_csv=f"{d}/DrMaruf_5_18_2026_12_16_7.csv",
        sessions_csv=f"{d}/DrMaruf_5_18_2026_12_16_24.csv",
        hash_ids=True,
    )
    r = audit(pairs, rp, bootstrap_B=10_000, seed=42, ci_method="bca")
    results["MIRIAD-test-retest"] = (f"{r.ctcs.ci.point:.6f}", r.audit_id)

# Programmatic comparison
print(f"{'Cohort':<22} {'cTCS_obs':<10} {'cTCS_lock':<10} {'audit_id match':<18}")
print("-" * 70)
all_match = True
for cohort, (ctcs_obs, aid_obs) in sorted(results.items()):
    ctcs_lock, aid_lock = LOCKED[cohort]
    ctcs_match = (ctcs_obs == ctcs_lock)
    aid_match = (aid_obs == aid_lock)
    if not (ctcs_match and aid_match):
        all_match = False
    flag = "✓" if (ctcs_match and aid_match) else "✗"
    print(f"{cohort:<22} {ctcs_obs:<10} {ctcs_lock:<10} {flag} {aid_obs[:16]}/{aid_lock[:16]}")

print()
print(f"Overall: {'ALL MATCH' if all_match else 'DIVERGENCE — see lines above'}")
sys.exit(0 if all_match else 1)
```

EXPECT: every printed line ends with `✓` if your input SHA-256s match the manifest. The script exit code is 0 on full match, 1 on any divergence.

### STEP 8 — Cold-rerun determinism check (~10 minutes)

Run Step 7 again in a fresh shell. Then again. Total five reruns.

EXPECT: identical audit_ids and identical cTCS values to 6 decimal places across all five reruns. Any divergence indicates non-determinism and is a defect.

---

## YAML attestation — the deliverable

After completing the protocol, write a file named `neurotcs_v1.8.0_third_party_attestation.yaml` with this exact schema. This is the artifact that gets ingested into FDA Q-Sub Volume I, pharma diligence pipelines, and peer-review submissions.

```yaml
# NeuroTCS v1.8.0 third-party reproducibility attestation
attestation:
  schema_version: "1.0"
  protocol_version: "v2"
  protocol_url: "https://github.com/DrMaruf1991/NeuroTCS/blob/main/docs/reviewer_package/reviewer_verification_prompt.md"
  verified_release_tag: "v1.8.0"
  verified_release_commit: "9e8f693e3d5576e7c52507f4ee7f66699c1f6ce1"

reviewer:
  name: ""                    # e.g. "Dr. Jane Doe"
  affiliation: ""             # e.g. "Stanford University, Department of Radiology"
  email: ""                   # e.g. "jdoe@stanford.edu"
  orcid: ""                   # optional, recommended for academic reviewers
  role: ""                    # one of: FDA_REVIEWER, PHARMA_DILIGENCE, ACADEMIC_PEER,
                              #         HOSPITAL_AI_GOVERNANCE, INDEPENDENT_TECHNICAL

environment:
  date_utc: ""                # ISO-8601, e.g. "2026-06-15T14:22:11Z"
  os: ""                      # e.g. "Linux 6.5.0-Ubuntu-24.04 x86_64"
  python_version: ""          # e.g. "3.12.7"
  numpy_version: ""           # e.g. "2.0.2"
  pandas_version: ""          # e.g. "2.2.3"
  pyreadr_version: ""         # e.g. "0.5.6"

inputs:
  files_accessed:             # list cohorts you ran; omit entries you didn't run
    OASIS-3:
      file_sha256: ""         # 64-char hex of OASIS3_UDSb4_cdr.csv
      file_sha256_matches_manifest: null   # true/false
    ADNI:
      file_sha256: ""
      file_sha256_matches_manifest: null
    NACC:
      file_sha256: ""
      file_sha256_matches_manifest: null
    MIRIAD:
      files_sha256:
        clinical: ""
        sessions: ""
        subjects: ""
      files_sha256_match_manifest: null

framework_tests:
  step_3_passed: null         # integer count; expected 401
  step_3_failed: null         # integer count; expected 0
  step_3_outcome: ""          # one of: PASSED, FAILED, NOT_RUN

cohort_audit_results:         # omit entries you didn't run
  OASIS-3:
    cTCS_observed: ""         # e.g. "0.994191"
    audit_id_observed: ""     # 64-char hex
    matches_locked: null      # true/false
  ADNI:
    cTCS_observed: ""
    audit_id_observed: ""
    matches_locked: null
  NACC:
    cTCS_observed: ""
    audit_id_observed: ""
    matches_locked: null
  MIRIAD:
    cTCS_observed: ""
    audit_id_observed: ""
    matches_locked: null
  MIRIAD-test-retest:
    cTCS_observed: ""
    audit_id_observed: ""
    matches_locked: null

triangulation:
  max_pairwise_delta_cTCS_observed: null    # e.g. 0.009206
  world_class_threshold: 0.01
  threshold_met: null                       # true/false
  notes: ""

determinism:
  cold_reruns_performed: null               # integer; recommended 5
  all_reruns_identical: null                # true/false
  notes: ""

verdict:
  reproducibility_verdict: ""               # one of:
                                            #   FULL_REPRODUCED
                                            #   METHOD_CONSISTENT_DIFFERENT_FREEZE
                                            #   FRAMEWORK_INSTALL_VERIFIED
                                            #   PARTIAL
                                            #   REFUTED
  verdict_rationale: ""                     # 2-4 sentences explaining the verdict
  scope_limitation: ""                      # what this attestation does NOT cover

signature:
  reviewer_signature: ""                    # typed name or detached GPG signature
  signature_method: ""                      # "TYPED_NAME" or "GPG" or "S/MIME"
  signature_date_utc: ""                    # ISO-8601
```

### Verdict definitions

- **FULL_REPRODUCED** — All accessed cohorts: input SHA-256s match manifest AND audit_ids match locked values AND cold-rerun determinism observed across ≥3 reruns.
- **METHOD_CONSISTENT_DIFFERENT_FREEZE** — Input SHA-256s differ from manifest (different DUA freeze), but cTCS values fall in [0.95, 1.00] AND cold-rerun determinism observed.
- **FRAMEWORK_INSTALL_VERIFIED** — Steps 1–3 completed (framework installs and 401 tests pass); cohort verification not attempted.
- **PARTIAL** — Some cohorts verified, others not accessed; specify which in `scope_limitation`.
- **REFUTED** — A locked invariant did not reproduce on matching inputs; specify which and provide observed values.

---

## Using the attestation

### In FDA Q-Submission Volume I — Performance Testing section

```
Per Q-Sub Final Guidance 29 May 2025, the sponsor presents third-party
reproducibility attestations for the v1.8.0 reference implementation.
Attestations are appended as Attachment Q-Sub-7 in YAML format per the
protocol at [protocol_url]. Each attestation independently verifies the
five locked audit invariants on cohort data sourced through the
attesting reviewer's institutional DUAs, with byte-deterministic
reproducibility observed across operating systems and Python
environments. Attestations support, but do not substitute for, the
per-aim study evidence in Volume II.
```

### In peer review code-and-data-availability section

```
Code: github.com/DrMaruf1991/NeuroTCS @ v1.8.0 (Apache-2.0).
Reproducibility: an independent verification protocol is available at
[protocol_url] producing YAML-format third-party attestations. Reviewers
are invited to execute the protocol during peer review. At time of
submission, N attestations have been collected from non-sponsor
institutions: [list reviewer affiliations and verdicts].
```

### In pharma BD response to "how do we know this works"

```
The framework is Apache-2.0 at [release URL]. We invite your technical
team to execute the verification protocol at [protocol_url] on any
longitudinal cohort data you control under DUA. The protocol produces
a YAML attestation in approximately 90 minutes. If your team's
attestation returns FULL_REPRODUCED or METHOD_CONSISTENT_DIFFERENT_FREEZE,
we can then schedule a paid pilot on your de-identified clinical-trial
data with appropriate IP and contracting in place.
```

---

## Open limitations as of v1.8.0 (Step 13 of v1 — kept inline here)

Reviewers should read `docs/datasheet/ad_neurotcs_datasheet.md` for the complete list. The 13 open gaps as of v1.8.0 release:

1. pTCS unavailable under AA-2024 rulepack (by design; transition_priors empty)
2. Single-rater attestation; ESNR κ ≥ 0.6 second-reader pending
3. AA-2024 cross-cohort triangulation fails on real data (max ΔcTCS = 0.0806); NIA-AA 2018 remains operative pack
4. TRAC rulepack not validated on real data
5. macOS cross-platform reproducibility not yet observed (Linux + Windows are)
6. Analysis plan not pre-registered (OSF preregistration is a project action item per proposal §A.9)
7. No power analysis for cohort sizes against Riley 2024 framework targets yet
8. No multiple-comparisons correction beyond a post-hoc Bonferroni (3/47 NACC strata flagged: sex M, sex F, race Multi)
9. The 0.01 ΔcTCS triangulation threshold is framework-internal, not externally validated
10. Single-rater attestation is the only clinical adjudication done to date
11. No external code review of the framework conducted yet
12. Lead investigator (DrMaruf1991) has a commercial interest in CURANIQ; this is disclosed but not adjudicated by a COI committee
13. cTCS / pTCS / uTCS terminology not yet bridged to standard clinical-AI evaluation concepts (calibration, discrimination, ECE, Brier score)

These gaps do not invalidate reproducibility evidence. They define the scope within which v1.8.0 evidence is interpretable.

---

## Versioning and updates

- **v1** (deprecated, 425 lines, 2026-05-24): superseded by this v2. Reason: missing `exclude_test_retest_rescans=True` flag for MIRIAD caused false REFUTATIONs.
- **v2** (canonical, this document): corrects MIRIAD flag, embeds expected SHA-256 prefixes, replaces free-text attestation with YAML schema, adds programmatic audit_id comparison.
- Future versions will be tagged in the repo at `docs/reviewer_package/reviewer_verification_prompt.md` and version-bumped in this header.

If a discrepancy exists between this protocol and the actual test files in the v1.8.0 release, the **test files are the source of truth** and this protocol is in error. Report any such discrepancy to the sponsor for correction.

---

*Protocol document v2 · 2026-05-24 · Apache-2.0 license matches the underlying framework · Sponsor: Dr. Marufjon Salokhiddinov (DrMaruf1991), KIUT Tashkent.*

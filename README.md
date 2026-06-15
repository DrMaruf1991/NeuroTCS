# NeuroTCS

**Citation-locked, fail-closed longitudinal medical AI audit framework.**

[![CI](https://github.com/DrMaruf1991/NeuroTCS/actions/workflows/ci.yml/badge.svg)](https://github.com/DrMaruf1991/NeuroTCS/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version 1.80.0](https://img.shields.io/badge/version-1.80.0-success.svg)](CHANGELOG.md)
[![Tests 2004](https://img.shields.io/badge/tests-2004%20passed-success.svg)](tests/)
[![Spec v1.7 FINAL](https://img.shields.io/badge/spec-v1.7%20FINAL-success.svg)](docs/spec/temporalmetric_v1.7_FINAL.md)

NeuroTCS audits the temporal coherence of longitudinal medical AI predictions
against internationally endorsed published clinical guidelines. It answers the
question regulators, hospitals, and trialists ask first: does this AI model's
visit-to-visit prediction trajectory obey the clinical biology it claims to
predict?

The framework is anchored on Dr. Marufjon Salokhiddinov's ASNR 2026 presentation
(Austin, May 2026) and the temporalmetric v1.7 FINAL technical specification.

## Hallmark result -- four-cohort triangulation lock

Five locked audit invariants reproduce byte-exactly across N=5 cold reruns,
numpy 2.0.2 <-> 2.4.4, pyreadr 0.5.0 <-> 0.5.6, on Linux and Windows. Max
pairwise delta-cTCS = 0.009206 (ADNI vs MIRIAD), all 6 pairwise comparisons
within our pre-specified <= 0.01 threshold.

| Cohort | n_scored / n_total | Transitions | Flagged | cTCS | audit_id |
|--------|--------------------|-------------|---------|------|----------|
| OASIS-3 (Aim 2 external replication) | 1,377 | 7,248 | 30 (0.41%) | 0.994191 | 92df5429... |
| ADNI-2/3/4 (Aim 1, canonical R-format) | 2,958 / 3,762 | 12,006 | 65 (0.54%) | 0.994575 | 7a973f7b... |
| NACC UDS v73 (added v1.8) | 39,361 / 56,529 | 158,423 | 1,217 (0.77%) | 0.991502 | 58329c65... |
| MIRIAD longitudinal (Aim 3 A) | 69 | 454 | 7 (1.54%) | 0.985369 | abda26cb... |
| MIRIAD test-retest (Aim 3 B) | 69 (pairs) | 69 | 0 (0.00%) | 1.000000 | 4de7f711... |

Each cohort also locks an audit_id_v2 (C6 collision-resistant variant). See
tests/audit_core/test_real_*.py for full locked-invariant constants, and
docs/datasheet/ad_neurotcs_datasheet.md Section A for full audit_ids and
methodology.

The cTCS metric generalises across institution, decade, recruitment criteria,
AND staging instrument. Three of the four cohorts use CDR-anchored staging;
MIRIAD uses MMSE-anchored staging. The 4-cohort agreement at <= 0.01 delta-cTCS
is, in these tested cohorts, strong cross-cohort evidence that the framework
measures what it claims to measure. (This is a within-tested-cohort observation,
not a comparative claim against other tools or the wider literature.)

## What's in this repo

NeuroTCS is the umbrella for seven engineering pieces plus five v1.7.0
methodological modules. Pieces 1-4 + 6 are production-shipped; Pieces 5 and 7 are
roadmap items planned for v1.9.x (importing them raises a helpful `ImportError`
pointing to the roadmap).

| Piece | Subpackage | Status | Description |
|-------|------------|--------|-------------|
| 1 | `neurotcs.input_contract.v1_0` | [shipped] | Categorical input contract (8-step validation, fail-closed) |
| 2 | `neurotcs.input_contract.v1_1` | [shipped] | Continuous-biomarker contract with UCUM unit enforcement |
| 3 | `neurotcs.rulepack` | [shipped] | **8 production AD rule packs** (NIA-AA 2018, AA 2024, AA 2024 TRAC, AT(N) 2018, A/T biological, ADNI clinical-stage, NIA-AA 2024 numeric, NIA-AA 2024 biological letter) |
| 4 | `neurotcs.audit_core` | [shipped] | cTCS (all packs) / pTCS (where transition priors are published) / uTCS engine + cluster bootstrap + BCa + Huber |
| 5 | `neurotcs.output_schema` | [roadmap v1.9.x] | FHIR Observation emitter (importing raises ImportError) |
| 6a | `neurotcs.input_contract.v1_1.adapters` | [shipped] | OASIS-3, ADNI (canonical R-format), NACC, MIRIAD trajectory loaders |
| 6b | `neurotcs.reference_adapters` | [shipped] | Reference submission-builders for vendor onboarding (ADNI categorical + volumetric) |
| 7 | `neurotcs.validation_harness` | [roadmap v1.9.x] | Synthetic-trajectory self-tests (importing raises ImportError) |

Plus five methodological modules (all shipped in v1.7.0+, all with tests):

- `neurotcs.sample_size` -- external-validation precision per Riley 2024
- `neurotcs.fairness` -- FUTURE-AI Fairness + Robustness panels per Lekadir 2025 BMJ
- `neurotcs.silent_deployment` -- Kwong 2022 silent-trial methodology
- `neurotcs.scanner_factorial` -- Scanner x vendor x interval factorial robustness
- `neurotcs.threshold_derivation` -- Larson 2025 empirical operational thresholds

## Rule packs shipped

NeuroTCS is an **Alzheimer's-disease** auditing tool. The 8 production AD rule
packs encode the dominant diagnostic and trajectory frameworks. See
[docs/SCOPE.md](docs/SCOPE.md) for the scope rationale and regulatory status.
Non-AD packs that previously shipped in v1.7.x (PD/Hoehn-Yahr, MS/McDonald,
oncology RECIST + iRECIST, stroke mRS, lung-nodule Fleischner) were extracted at
v1.9.0 and are preserved as archival history only; NeuroTCS does not roadmap
non-AD coverage.

| Pack | Disease | Anchor publication | PMID | Transitions |
|------|---------|--------------------|------|-------------|
| `ad/niaaa_2018@1.3.0` | Alzheimer's | Jack 2018 NIA-AA Framework | 29653606 | 4 + 2 inadmissible |
| `ad/aa_2024@2.1.0` | Alzheimer's | Jack 2024 AA Revised Criteria | 38934362 | 28 + 17 inadmissible (Table 7 integrated staging, 17 states) |
| `ad/aa_2024_trac@1.1.0` | Alzheimer's (anti-Abeta) | La Joie 2025 TRAC framework | 41298245 | 6 + 3 inadmissible (5 require `treatment_status`) |
| `ad/atn_2018@1.0.0` | Alzheimer's | Jack 2024 AA Revised Criteria (AT(N) origin Jack 2016/2018) | 38934362 | 5 + 0 inadmissible (8 biomarker-profile states; A-T+ inadmissibility enforced) |
| `ad/at_biological@1.0.0` | Alzheimer's | Jack 2024 AA Revised Criteria (A/T biological staging) | 38934362 | 3 + 3 inadmissible (3 states) |
| `ad/adni_clinical_stage@1.0.0` | Alzheimer's | ADNI clinical-stage staging (CN/SMC/EMCI/LMCI/MCI/AD); DOI 10.1002/alz.14167 | -- | 20 + 5 inadmissible (6 states) |
| `ad/niaaa_2024_clinical_numeric@1.0.0` | Alzheimer's | NIA-AA 2024 numeric clinical staging (stages 0-6, Jack 2024 Table 6) | 38934362 | 27 + 15 inadmissible (7 states; dementia-regression inadmissible) |
| `ad/niaaa_2024_biological_letter@1.0.0` | Alzheimer's | NIA-AA 2024 biological letter staging (A/B/C/D PET-based, Jack 2024) | 38934362 | 12 admissible (6 backward TRAC-gated; 4 states; backward step inadmissible unless TRAC) |

Each rule pack is:

- **Citation-locked** -- every transition requires `citation_pmid` or
  `citation_doi` AND `guideline_section` (exact section/table/figure pointer).
- **Version-stamped** -- canonical JSON SHA-256 hash computed at load time.
- **Fail-closed** -- Pydantic v2 strict mode rejects unknown fields, missing
  citations, inconsistent state spaces.

**Schema v1.3.0** adds backward-compatible support for **context-conditional
admissibility** (the TRAC pack uses this to encode that A+ -> A- amyloid
clearance is admissible *only* under anti-Abeta therapy) and `attribution_type`
(clinical_inference vs guideline_quote, per ERRATA E-2026-003).

## Authority model

NeuroTCS rule packs do NOT require disease-specialist co-authorship to be
authoritative. They require provenance to internationally endorsed published
guidelines. The schema makes this explicit:

- `clinical_source_authority` -- names the peer-reviewed publication + endorsing
  professional society where clinical authority resides.
- `transcribed_by` -- names the board-certified physician who attests the YAML
  faithfully encodes the cited guideline.
- `guideline_section` per transition -- exact pointer so any reviewer can verify
  the transcription.
- `reviewers` -- additive specialist sign-off (non-blocking).

This mirrors how FHIR / SNOMED / LOINC terminology encodings work. Authority
lives in the cited publication, not in a co-author's signature.

See [`docs/transcription_audit/`](docs/transcription_audit/) for side-by-side
YAML <-> source-paragraph audits.

## Quick start

```
git clone https://github.com/DrMaruf1991/NeuroTCS.git
cd NeuroTCS
pip install -e .

# Tests (no cohort data required) -- expect 2004 passed, ~24 skipped (v1.80.0)
python -m pytest tests/ -q \
    --ignore=tests/audit_core/test_real_adni_audit.py \
    --ignore=tests/audit_core/test_real_oasis3_audit.py \
    --ignore=tests/audit_core/test_real_nacc_audit.py \
    --ignore=tests/audit_core/test_real_miriad_audit.py \
    --ignore=tests/audit_core/test_real_miriad_fairness_audit.py \
    --ignore=tests/audit_core/test_four_cohort_triangulation.py

# Full suite with cohort data (set env vars first; expect 2004+cohort tests passed, cohort-version-dependent)
export NEUROTCS_OASIS3_CDR=/path/to/OASIS3_UDSb4_cdr.csv
export NEUROTCS_ADNI_DXSUM_RDA=/path/to/ADNIMERGE2/data/DXSUM.rda
export NEUROTCS_NACC_CSV=/path/to/investigator_nacc73_slim.csv
export NEUROTCS_MIRIAD_DIR=/path/to/MIRIAD_directory
python -m pytest tests/ -q
```

The test count is environment-dependent: **2004 passed / 24 skipped** on a
standard install without cohort env vars (cohort-data tests skip; current as of
v1.80.0). As of v1.73.0 the R (`pyreadr`) and SPSS (`pyreadstat`) readers ship in
core, so those format tests run on a standard install -- no extra is needed. With
all four cohort env vars pointing at valid files, the cohort tests additionally
execute and pass; the exact pass count is cohort-version-dependent. Both outcomes
are correct behavior.

### Rule pack only

```python
from neurotcs import load_rulepack

pack = load_rulepack("ad/niaaa_2018")
ok, rule = pack.rulepack.is_admissible("CN", "AD", delta_t_days=200)
print(ok)  # False -- CN->AD requires >=365 days (Jack 2018)
```

### Full audit pipeline (canonical pattern)

```python
from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import (
    load_adni_trajectories,
)

pack = load_rulepack("ad/niaaa_2018")
trajectories, report = load_adni_trajectories(
    dxsum_rda_path="/path/to/ADNIMERGE2/data/DXSUM.rda",
    hash_ids=False, skip_invalid=True,
)
result = audit(trajectories, pack, bootstrap_B=10_000, seed=42, ci_method="bca")

print(f"cTCS:        {result.ctcs.ci.point:.6f}")   # 0.994575 (v1.20.0 locked)
print(f"audit_id:    {result.audit_id}")            # 7a973f7b... (v1.20.0 locked)
print(f"audit_id_v2: {result.audit_id_v2}")         # dda642ff... (v1.20.0 locked)
result.to_json("report.json")
```

Worked examples for all four cohorts: see tests/audit_core/test_real_*.py (each
test reproduces a locked invariant) and examples/ (runnable demos).

### CLI

```
neurotcs-audit audit \
  --predictions predictions.csv \
  --rulepack ad/niaaa_2018 \
  --output report.json \
  --bootstrap 10000 --seed 42 \
  --patient-col RID --date-col EXAMDATE --state-col DIAGNOSIS \
  --state-label-map Dementia=AD
```

## Reviewer verification

For third-party reviewers (FDA technical staff, pharma diligence, academic peer
reviewers, hospital AI governance):

- **v2 canonical protocol**: [`docs/reviewer_package/reviewer_verification_prompt.md`](docs/reviewer_package/reviewer_verification_prompt.md) -- 8-step manual reproduction (~90 min). Produces signed YAML attestation.
- **Cursor IDE prompt**: [`docs/reviewer_package/cursor_verification_prompt.md`](docs/reviewer_package/cursor_verification_prompt.md) -- AI-guided execution (~30 min).
- **Colab notebook**: [`docs/reviewer_package/NeuroTCS_v1.8.0_Reviewer_Verification.ipynb`](docs/reviewer_package/NeuroTCS_v1.8.0_Reviewer_Verification.ipynb) -- browser-only zero-install preview (~10 min, synthetic-data demo).

All three surfaces produce the same YAML attestation schema and reference the same
locked invariants. The Colab path can only achieve FRAMEWORK_INSTALL_VERIFIED
(DUA-controlled data cannot be uploaded to third-party cloud); local paths can
achieve FULL_REPRODUCED.

## Specification

The canonical spec is docs/spec/temporalmetric_v1.7_FINAL.md. Read this to
understand:

- Sec.A.2 -- Coherence Temporal Consistency Score (cTCS) definition
- Sec.A.3 -- Probabilistic TCS with matrix exponential M(delta-tau) = exp(Q * delta-tau / 365)
- Sec.A.4 -- Unified TCS (weighted ensemble)
- Sec.A.5 -- Cluster bootstrap (B = 10,000) + Huber M-estimation (c = 1.345)
- Sec.B.1 -- Aims 1-6 validation plan
- Sec.B.2 -- Required datasets (ADNI, OASIS-3, NACC, MIRIAD; ALZ-NET planned)
- Sec.B.6 -- Rule pack registry and engineering discipline
- Sec.C -- Library architecture

## Roadmap to v0.2 / v1.0 / Q-Sub

- **v1.8.0** (May 2026) -- Four-cohort triangulation lock + ADNI canonical source. [shipped].
- **v1.8.1** (May 2026) -- Documentation, test hygiene, CI matrix, reference-adapter reorganization, citation backfill. [shipped].
- **v1.9.0** (May 2026) -- **AD-only scope contraction**: non-AD rule packs (PD, MS, oncology, stroke, lung nodule) extracted; preserved as archival history only. [shipped].
- **v1.9.x** (Q3 2026) -- Piece 5 (FHIR output) + Piece 7 (validation harness) + cohort-specific transition priors.
- **W22 (~Sept 2026)** -- Nature Medicine submission with AD validation across ADNI + OASIS-3 + NACC + MIRIAD.
- **Oct 2026** -- ASFNR Newport Beach workshop demo.

Aspirational (not a commitment): a future FDA Q-Submission and v1.0.0 release.
NeuroTCS is currently a research instrument and is not FDA-cleared; see
docs/SCOPE.md Regulatory status.

## Citation

```bibtex
@software{salokhiddinov2026neurotcs,
  author    = {Salokhiddinov, Marufjon},
  title     = {NeuroTCS: Citation-locked, fail-closed longitudinal medical AI audit framework},
  version   = {1.80.0},
  year      = {2026},
  url       = {https://github.com/DrMaruf1991/NeuroTCS},
  note      = {temporalmetric v1.7 FINAL specification, 8 AD production rule packs, four-cohort triangulation lock; v1.9.0+ AD-only scope}
}
```

See CITATION.cff for GitHub's citation widget.

## Known limitations (honestly disclosed)

NeuroTCS publicly documents what is NOT yet covered so reviewers can assess
fitness for purpose. The complete, current gap disclosure -- spanning
methodological, validation, fairness, and regulatory-status gaps -- is maintained
as a single source of truth in docs/datasheet/ad_neurotcs_datasheet.md
**Section F -- Honest gaps acknowledged**.

To avoid drift, the README does not duplicate the list here; Section F is
authoritative (enforced by tests/docs/test_gap_disclosure_single_source.py). These
gaps do not invalidate the reproducibility evidence -- they define the scope
within which it is interpretable.

## License

Apache 2.0 -- see [`LICENSE`](LICENSE). The cited published guidelines remain (c)
their respective publishers; this package transcribes them into machine-readable
form for academic / regulatory audit purposes under fair-use interpretation.
NeuroTCS does NOT redistribute the publications themselves.

## Contact

Dr. Marufjon Salokhiddinov, MD PhD
ESOR-BRACCO-ESNR Neuroimaging Fellow
Kimyo International University in Tashkent (KIUT), Uzbekistan

Issues and contributions via GitHub.

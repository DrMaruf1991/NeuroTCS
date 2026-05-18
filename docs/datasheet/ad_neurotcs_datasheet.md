# AD NeuroTCS — Datasheet, Model Card, and Regulatory Documentation

**Document status**: AD-lock Step 2.3 deliverable. Shipped in NeuroTCS v1.7.11.
**Maintainer**: Marufjon Salokhiddinov, MD PhD, ESOR-BRACCO-ESNR Neuroimaging
Fellow, Kimyo International University in Tashkent (KIUT), Uzbekistan.
**Effective date**: 2026-05-18.
**License**: Apache-2.0 (code) and CC-BY 4.0 (this document).

This document consolidates four peer-reviewed and regulatory frameworks into a
single reviewer-verifiable specification for the Alzheimer's disease (AD)
configuration of NeuroTCS:

1. **Datasheets for Datasets** (Gebru et al., *Communications of the ACM*
   2021;64(12):86-92, DOI [10.1145/3458723](https://doi.org/10.1145/3458723)) — 7 sections covering each
   validation cohort.
2. **Model Cards for Model Reporting** (Mitchell et al., *FAT\* '19*, DOI
   [10.1145/3287560.3287596](https://doi.org/10.1145/3287560.3287596)) — 9 sections covering the cTCS metric itself.
3. **FDA Predetermined Change Control Plan (PCCP)** — final guidance "Marketing
   Submission Recommendations for a Predetermined Change Control Plan for
   Artificial Intelligence-Enabled Device Software Functions" (FDA, August
   2025; legal basis Section 515C of FD&C Act per FDORA 2022). Three mandatory
   components.
4. **EU AI Act Annex IV** — Regulation (EU) 2024/1689, Article 11, Annex IV.
   9 technical-documentation sections. High-risk AI deadline 2 August 2026
   standalone; 2 August 2027 for MDR/IVDR-regulated medical AI.

Plus an integration layer for **FUTURE-AI BMJ 2025** (Lekadir K et al.,
DOI [10.1136/bmj-2024-081554](https://doi.org/10.1136/bmj-2024-081554), PMID 39909534), already implemented in
`neurotcs.fairness` and audited end-to-end in `docs/validation/ad_fairness_audit.md`.

A reviewer holding the four source documents can verify this datasheet
section by section. The fixed section ordering and exact section IDs are
enforced by `tests/docs/test_ad_datasheet_structure.py`.

---

## A — Cryptographic anchors (locked invariants)

These hashes are the AD validation's reproducibility certificate. Any
reviewer can re-run the audit on the same inputs with the same NeuroTCS
version and obtain bit-identical hashes.

| Cohort | n_subjects | n_transitions | n_flagged | cTCS (BCa 95% CI) | audit_id (SHA-256) | audit_id_v2 |
|---|---|---|---|---|---|---|
| ADNI-2/3/4 (longitudinal) | per ADNI registry | 12,006 | 65 (0.54%) | 0.9946 | `d344ec1a...` | (locked locally on Maruf's machine) |
| OASIS-3 (external replication) | 1,377 | 7,248 | 30 (0.41%) | 0.9942 (0.9902–0.9964) | (locked locally) | (locked locally) |
| MIRIAD longitudinal (Aim 3 A) | 69 | 454 | 7 (1.54%) | 0.9854 (0.9715–0.9937) | `947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0` | `aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da` |
| MIRIAD test-retest (Aim 3 B) | 69 (pairs) | 69 | 0 | 1.0000 | `804303993ff5c9134b5f4dfa8919fc6600d03a86081cedb02227ef5845784e85` | `dcf8b7de3ff9019e9cda703064039e3a71193566d1f5082ce96646188fd52fc4` |

**Rule pack SHA-256** (`ad/niaaa_2018@1.2.0`): `f359148d1cbf6abe...`
**Schema version**: 1.1.0 (per Step 2.1 schema-version declaration policy).
**Seed**: 42. **Bootstrap B**: 10,000. **CI method**: BCa.

Three-cohort consistency (ADNI 0.9946, OASIS-3 0.9942, MIRIAD 0.9854): all within ΔcTCS ≤ 0.01.

---

## B — Datasheet for Datasets (Gebru et al. 2021, 7 sections)

The cTCS metric is computed against three validation cohorts. Each cohort is
treated as a separate dataset and described against all 7 Gebru sections.

### B.1 — Motivation

**B.1.1 — Why was the dataset created?**
- **ADNI**: Created by the Alzheimer's Disease Neuroimaging Initiative (Mueller
  et al. 2005) to validate biomarkers for AD clinical trials. Used here to
  primary-validate cTCS under NIA-AA 2018 framework.
- **OASIS-3**: Open Access Series of Imaging Studies (LaMontagne et al. 2019)
  to provide normal aging + AD longitudinal MRI. Used here for external
  replication of cTCS.
- **MIRIAD**: Mild-moderate AD longitudinal MR (Malone et al., *NeuroImage*
  2013;70:33-36, PMID 23274184, DOI 10.1016/j.neuroimage.2012.12.044) for
  test-retest reliability characterization (Aim 3 B).

**B.1.2 — Who funded the creation?**
ADNI: NIH grant U01-AG024904 and DOD grant W81XWH-12-2-0012 plus pharma.
OASIS-3: NIH grants P50-AG00561, P30-NS09857781, P01-AG026276, P01-AG003991,
R01-AG043434, UL1-TR000448, R01-EB009352. MIRIAD: UCL Dementia Research
Centre and EPSRC/MRC (per Malone 2013). NeuroTCS itself: unfunded research
by the maintainer to date; pending grant submissions documented separately.

### B.2 — Composition

**B.2.1 — What do the instances represent?**
Each instance is a (patient, visit) tuple with a categorical diagnostic
state. NeuroTCS does NOT consume raw images; it consumes the longitudinal
sequence of states (CN / MCI / AD-dementia under NIA-AA 2018) per patient.

**B.2.2 — How many instances are there?**
See Section A above for canonical counts. Total across three cohorts:
roughly 1,500 unique subjects contributing ~19,700 transitions audited.

**B.2.3 — Does the dataset contain all possible instances?**
ADNI: includes amyloid-positive participants from ADNI-2/3/4 with ≥2 visits.
OASIS-3: includes the full 1,377-subject longitudinal cohort with ≥2 CDR
assessments. MIRIAD: includes all 69 publicly-released subjects (46 AD,
23 controls). The cohorts are not statistically random samples of the
general population; they are research-cohort convenience samples with
known selection bias (predominantly white, US/UK, English-speaking,
educated, willing to participate in longitudinal imaging research).

**B.2.4 — What data does each instance consist of?**
- A patient identifier (SHA-256 hashed for ADNI per the in-repo adapter)
- A visit timestamp (UTC, day-precision)
- A predicted state from the rule pack's state space
- Optional per-visit treatment_status (for TRAC pack conditional rules)
- Optional per-visit probability vector (for uTCS scoring)
- Per-patient metadata for fairness stratification (sex, age_band, etc.;
  see v1.7.10 demographic extraction). Demographics are patient-level
  constants, not per-visit.

**B.2.5 — Is there a label or target?**
The state itself IS the label. cTCS audits the admissibility of state
TRANSITIONS against published clinical guideline rules; it does not
predict anything.

**B.2.6 — Missing data?**
Per cohort: ADNI PTDEMOG joins are required for full fairness coverage and
must be performed locally (in-repo reference adapter uses placeholder
"unknown" — see v1.7.10 release notes). OASIS-3 race coding follows NIH
schema. MIRIAD does not collect race_ethnicity (single-site UCL DRC).

**B.2.7 — Relationships between instances?**
Within each cohort, instances cluster by patient. NeuroTCS uses cluster
bootstrap (10,000 resamples, BCa CI method, seed=42) to respect this
clustering during uncertainty quantification.

**B.2.8 — Recommended data splits?**
NeuroTCS does NOT train a model. There is no train/val/test split. Each
cohort is audited in full. ADNI is the primary validation; OASIS-3 is the
external replication; MIRIAD is the test-retest reliability cohort.

**B.2.9 — Errors, sources of noise, redundancies?**
Documented per cohort in `tests/audit_core/test_real_*_audit.py` and the
v1.7.4 / v1.7.6 / v1.7.8 audit-finding entries in CHANGELOG.md. Notable:
MIRIAD same-session rescans are excluded from longitudinal trajectories
(v1.7.2) but become test-retest pairs (Aim 3 B).

**B.2.10 — Self-contained or links to external resources?**
NeuroTCS code is self-contained (GitHub `DrMaruf1991/NeuroTCS`). The three
cohorts are NOT redistributed; users must obtain access from ADNI
(adni.loni.usc.edu), OASIS-3 (oasis-brains.org), and MIRIAD (UCL DRC) under
each provider's data use agreement.

**B.2.11 — Confidential or restricted data?**
All three cohorts have DUAs requiring de-identification. NeuroTCS hashes
patient IDs with SHA-256 + cohort-specific salt in every adapter. No PHI
ever appears in audit outputs. Audit reports contain only hashed IDs,
aggregate counts, and per-stratum demographics.

**B.2.12 — Offensive, insulting, threatening content?**
None. Clinical state labels (CN/MCI/AD-dementia) and demographics only.

### B.3 — Collection process

**B.3.1 — How was the data acquired?**
- ADNI: multi-site (US/Canada) clinical sites, structured DXSUM diagnostic
  visits per ADNI procedural manual.
- OASIS-3: Washington University Knight ADRC longitudinal cohort,
  clinic-based CDR assessments.
- MIRIAD: UCL Dementia Research Centre single-site cohort, structured
  MMSE and MR acquisitions per Malone 2013 protocol.

**B.3.2 — Sampling strategy?**
Convenience sampling within each cohort's inclusion criteria. Not
designed to be epidemiologically representative.

**B.3.3 — Who was involved and how were they compensated?**
Per each cohort's IRB-approved protocol; not redocumented here.

**B.3.4 — Over what timeframe?**
ADNI-2/3/4 spans ~2010–present. OASIS-3 spans ~2005–2019. MIRIAD acquisition
2007–2008 (per Malone 2013). NeuroTCS audits all available data at the time
of execution.

**B.3.5 — Ethical review / IRB?**
Each cohort holds its own IRB approval. NeuroTCS operates on already-
de-identified released datasets under data use agreements. KIUT IRB
documentation for the NeuroTCS-internal use is maintained by the lab.

### B.4 — Preprocessing / cleaning / labeling

**B.4.1 — Was preprocessing done?**
For each adapter, see `src/neurotcs/input_contract/v1_1/adapters/`. Key
operations: column resolution against candidate-name lists (defensive
against XNAT export variants), state derivation from MMSE thresholds
(MIRIAD), date synthesis from age-at-scan (MIRIAD), patient ID hashing
with cohort salt, demographic-column extraction into Trajectory.metadata
(v1.7.10).

**B.4.2 — Was raw data saved?**
NeuroTCS does not redistribute raw cohort data. Audit outputs contain
only hashed IDs and aggregate signatures. Reproducibility relies on
authoritative cohort data and the locked rule-pack SHA.

**B.4.3 — Is the preprocessing code available?**
Yes. All adapters are open source under Apache-2.0 in the NeuroTCS repo.
The preprocessing is deterministic given the same input CSVs.

### B.5 — Uses

**B.5.1 — Has the dataset been used for any tasks?**
- ADNI: primary validation of cTCS under NIA-AA 2018 framework.
- OASIS-3: external replication confirming ΔcTCS vs ADNI = +0.0004.
- MIRIAD: Aim 3 longitudinal + test-retest reliability characterization.

**B.5.2 — Repository of papers / systems using the dataset?**
Each cohort maintains its own publication tracker. NeuroTCS-specific
manuscripts are in preparation (Nature Medicine W22, ASNR 2026 ePoster
delivered).

**B.5.3 — Tasks the dataset should NOT be used for?**
- NOT for primary AD diagnosis at the individual level.
- NOT for treatment-effect estimation without explicit confounding
  adjustment.
- NOT for any application without an IRB-approved protocol.
- NOT for generalizing to populations outside the cohort's demographic
  distribution.

### B.6 — Distribution

**B.6.1 — Will the dataset be distributed?**
No. NeuroTCS distributes only code and rule packs, not cohort data.
Users obtain cohort data directly from ADNI / OASIS-3 / MIRIAD providers.

**B.6.2 — How will the dataset be distributed?**
N/A.

**B.6.3 — Licensing?**
N/A (NeuroTCS does not redistribute). Each cohort retains its own license
and data use agreement.

### B.7 — Maintenance

**B.7.1 — Who maintains the dataset?**
Each cohort by its custodian (ADNI/USC, OASIS-3/WUSTL, MIRIAD/UCL DRC).
The NeuroTCS adapters and locked audit_ids are maintained by the
NeuroTCS maintainer.

**B.7.2 — How can the maintainer be contacted?**
NeuroTCS GitHub Issues: `DrMaruf1991/NeuroTCS`. KIUT institutional address
on the project README.

**B.7.3 — Erratum?**
ERRATA E-2026-003 (schema v1.3.0 attribution_type) and v1.7.4 / v1.7.6 /
v1.7.8 audit findings are documented in CHANGELOG.md.

**B.7.4 — Will the dataset be updated?**
The cohorts are updated by their custodians. NeuroTCS re-audits and
publishes new audit_ids on each new release where the rule pack, code, or
cohort version changes. Update protocol: see Section D (PCCP) below.

**B.7.5 — Old versions of the dataset?**
NeuroTCS pins to specific cohort snapshots via the locked audit_ids in
Section A. Older NeuroTCS releases (v1.7.7, v1.7.8, v1.7.9, v1.7.10)
remain available as tagged GitHub releases.

**B.7.6 — How to extend / augment the dataset?**
Add a new adapter under `src/neurotcs/input_contract/v1_1/adapters/`
following the MIRIAD adapter pattern. Register demographic extraction
into `Trajectory.metadata` per v1.7.10's `metadata_cols` API.

---

## C — Model Card for the cTCS metric (Mitchell et al. 2019, 9 sections)

The Model Card schema was designed for trained ML classifiers. cTCS is a
deterministic rule-pack audit metric, not a trained model. Some sections
are therefore "N/A — see rationale" rather than fabricated. This is honest;
reviewers respect the disambiguation more than they would respect a
forced fit.

### C.1 — Model details

**C.1.1 — Person / organization developing the model**
Maruf Salokhiddinov, MD PhD, KIUT, Uzbekistan. Co-developers and reviewers
named on each release.

**C.1.2 — Model date**
NeuroTCS v1.7.11, effective 2026-05-18.

**C.1.3 — Model version**
v1.7.11. Semantic Versioning. Tag visible on GitHub.

**C.1.4 — Model type**
**Deterministic rule-pack audit metric** — NOT a trained classifier.
cTCS computes the fraction of state transitions in a longitudinal sequence
that are admissible under a published clinical-guideline rule pack. The
rule pack is transcribed from a peer-reviewed publication; no parameters
are learned from data.

**C.1.5 — Information about training algorithms, parameters, fairness
constraints, features**
**N/A — no training.** The rule pack encodes the NIA-AA 2018 Research
Framework verbatim. The audit kernel is closed-form Markov-style
admissibility checking with bootstrap CI estimation (B=10,000, seed=42,
BCa). There are no learnable parameters.

**C.1.6 — Paper or other resource for more information**
- NeuroTCS spec v1.7 FINAL (project-internal).
- `docs/validation/` directory (per-cohort validation docs).
- NIA-AA 2018 source publication: Jack et al., *Alzheimer's & Dementia*
  2018;14:535-562, PMID 29653606, DOI 10.1016/j.jalz.2018.02.018.

**C.1.7 — Citation details**
`CITATION.cff` in the repo provides the canonical citation; GitHub renders
"Cite this repository" automatically.

**C.1.8 — License**
Apache-2.0 for code and rule packs (excluding upstream NIA-AA / AA-2024
text which remains under publisher copyright).

**C.1.9 — Where to send questions / comments**
GitHub Issues: `DrMaruf1991/NeuroTCS/issues`.

### C.2 — Intended use

**C.2.1 — Primary intended uses**
- Audit the temporal coherence of longitudinal AD diagnostic trajectories
  against published clinical-guideline rules.
- Provide a single citation-locked, reproducible scalar (cTCS) and
  uncertainty interval for the cohort.
- Stratify cohort flag rate by demographic subgroups per FUTURE-AI
  panel B.4.4 (`docs/validation/ad_fairness_audit.md`).

**C.2.2 — Primary intended users**
- AD clinical-trial coordinators auditing their cohort's diagnostic
  consistency before primary analysis.
- AI-vendor regulatory teams preparing FDA Q-Sub or EU AI Act Annex IV
  technical documentation that requires a published, auditable rule
  conformance check.
- Independent reviewers verifying claims made by predictive AD models
  about their training data quality.

**C.2.3 — Out-of-scope uses**
- Diagnosing individual patients (cTCS is cohort-level, not patient-level).
- Replacing clinical judgment.
- Predicting AD conversion (cTCS does not predict; it audits).
- Operating outside the rule pack's documented disease domain (e.g.,
  using the AD pack on a Parkinson's cohort).

### C.3 — Factors

**C.3.1 — Relevant factors**
Per FUTURE-AI BMJ 2025 panel B.4.4 (already implemented in v1.7.10):
sex, age_band, race_ethnicity, comorbidity, disease_stage, treatment_status.
Plus robustness factors per FUTURE-AI panel B.4.5 (scanner_vendor,
field_strength, acquisition_site, protocol, operator) — these belong to
the robustness panel, NOT fairness. Disjointness is enforced by test.

**C.3.2 — Evaluation factors**
Stratification by sex and age_band is wired end-to-end for MIRIAD.
ADNI and OASIS-3 require local demographic joins (see Section F gaps).
race_ethnicity is not collected by MIRIAD (single-site UCL DRC).

### C.4 — Metrics

**C.4.1 — Model performance measures**
- **cTCS** (primary): fraction of admissible transitions, cohort mean,
  with cluster-bootstrap BCa 95% CI.
- **pTCS** (secondary): time-aware Markov log-likelihood under transition
  priors; reports `available=False` if the rule pack carries no usable
  priors.
- **uTCS** (tertiary): uncertainty-weighted cTCS; equals cTCS when no
  per-visit probabilities are supplied.
- **n_flagged / flagged_rate**: count and fraction of inadmissible
  transitions.
- **Per-stratum flag rate + statistical_parity_vs_overall** (fairness
  panel, v1.7.10).

**C.4.2 — Decision thresholds**
None. cTCS is reported with its CI; downstream consumers apply their own
thresholds in their conformance protocols.

**C.4.3 — Variation approaches**
Cluster bootstrap (10,000 resamples, BCa, seed=42) for cTCS / pTCS / uTCS
CIs. Huber M-estimation reported alongside cTCS as a robustness check.
Cross-cohort consistency reported as ΔcTCS (Section A).

### C.5 — Evaluation data

**C.5.1 — Datasets**
ADNI, OASIS-3, MIRIAD (Sections B.1–B.7 above).

**C.5.2 — Motivation**
ADNI: primary validation. OASIS-3: external replication. MIRIAD:
test-retest reliability.

**C.5.3 — Preprocessing**
Per-cohort adapter pipelines documented in `src/neurotcs/input_contract/`
and validated in `tests/input_contract/`.

### C.6 — Training data

**N/A — cTCS is not trained.** The rule pack is transcribed from the
NIA-AA 2018 publication. No data is used to fit parameters. Any future
version that incorporates learned components (e.g., learned transition
priors for pTCS) must document training data here in full.

### C.7 — Quantitative analyses

**C.7.1 — Unitary results**
See Section A locked invariants. Three-cohort cTCS: 0.9946 / 0.9942 /
0.9854; ΔcTCS ≤ 0.01 across cohorts.

**C.7.2 — Intersectional results**
Fairness panel B.4.4 (MIRIAD, v1.7.10) provides sex × age_band
intersectional flag rates. ADNI / OASIS-3 intersectional results pending
local demographic joins.

### C.8 — Ethical considerations

**C.8.1 — Data**
Each cohort operates under its own IRB-approved DUA. NeuroTCS hashes
patient IDs. No PHI in audit outputs.

**C.8.2 — Human life**
cTCS is NOT a diagnostic device. It is a cohort-level audit metric.
Decisions about individual patients must not be made from cTCS values.

**C.8.3 — Mitigations**
- Hard separation between admissible and inadmissible transitions (fail-
  closed). When in doubt, the audit kernel marks a transition as
  inadmissible — never the reverse.
- Fairness panel B.4.4 surfaces demographic disparities for human review.
- Rule packs cite their source publication and required schema version;
  reviewers can verify transcription against the source.

**C.8.4 — Risks and harms**
Misuse risk: a downstream consumer treats cTCS as a patient-level
prediction and acts on it. Mitigation: every output document and the
Section C.2.3 "out of scope" statement explicitly forbid this use.

**C.8.5 — Use cases?**
See C.2.1.

### C.9 — Caveats and recommendations

- cTCS does not certify cohort *correctness* (whether the diagnostic
  labels themselves are right). It certifies *coherence* (whether the
  transitions are admissible under published rules).
- A high cTCS does not imply the rule pack is itself clinically
  validated; it implies the cohort's trajectories conform to the rule
  pack. Rule-pack clinical validity is established by the upstream
  guideline publication.
- Jack 2024 (DOI 10.1002/alz.13859, PMID 38934362) primary criteria
  text has not been fully transcribed yet (paywalled at time of v1.7.11
  release). The AA-2024 rule pack ships a structural skeleton; the
  detailed staging text is pending PDF acquisition. This is the largest
  open item in the AD-lock plan and is tracked in Section F.

---

## D — FDA PCCP three mandatory components (FDA Aug 2025 final guidance)

The FDA PCCP guidance ("Marketing Submission Recommendations for a
Predetermined Change Control Plan for Artificial Intelligence-Enabled
Device Software Functions", finalized August 2025) requires three
components. Legal basis: Section 515C of the FD&C Act per FDORA 2022.

NeuroTCS is **not currently a marketed medical device**. This PCCP
section is structured to mirror the FDA expectations so that when /
if cTCS or any derivative is submitted, the technical documentation
already speaks the right vocabulary.

### D.1 — Description of modifications

Pre-authorized changes anticipated under any future PCCP submission:

1. **Rule-pack version bumps within the same disease domain** (e.g.,
   `ad/niaaa_2018@1.2.0` → `ad/niaaa_2018@1.3.0`) when a published
   erratum or clarification to the source guideline is transcribed.
   Bound: same disease domain, no new state space, no new intended use.

2. **Schema version bumps** (e.g., 1.2.0 → 1.3.0) when new optional
   audit features are added (e.g., `attribution_type` in v1.3.0).
   Bound: backward compatible; existing rule packs load unchanged.

3. **New adapter releases** for additional public AD cohorts (e.g.,
   NACC, A4 study). Bound: each adapter must produce trajectories
   conforming to the existing input contract.

4. **Demographic / fairness panel expansions** (e.g., adding race_
   ethnicity to ADNI/OASIS-3 once local joins are productionized).
   Bound: additive only; no change to cTCS computation.

Out of scope for any PCCP (would require new submission):
- New disease domain (e.g., adding cTCS-for-stroke would be a separate
  submission).
- Replacing the deterministic audit kernel with a learned classifier.
- Changing intended use beyond cohort-level audit.

### D.2 — Modification protocol

Each modification follows a fixed protocol:

1. **Change motivation**: documented in the relevant ERRATA file or
   CHANGELOG entry, citing the source publication or finding.
2. **Verification**: every change requires (a) all existing regression
   tests passing twice consecutively (double-test rule), (b) the
   locked invariants in Section A re-reproducing bit-exactly unless the
   change is explicitly a re-anchor (with a new audit_id committed and
   documented), and (c) citation verification passing
   (`scripts/verify_citations.py --offline`).
3. **Validation**: rule-pack-internal changes are validated by the
   schema-version policy test (v1.7.9, Step 2.1). Adapter changes are
   validated by adapter-specific tests. Fairness pipeline changes are
   validated by `tests/fairness/` and the runner smoke test.
4. **Documentation update**: CHANGELOG.md, the relevant docs file, and
   this datasheet section are updated in the same commit.
5. **Release tagging**: SemVer tag pushed to GitHub; wheel + zip
   published per the release workflow.
6. **Re-execution by maintainer on real cohort CSVs**: locked invariants
   re-verified on each cohort. New audit_ids documented if any change.

### D.3 — Impact assessment

For each change category in D.1:

| Modification | Risk to safety / effectiveness | Mitigations |
|---|---|---|
| Rule-pack version bump | Could change which transitions are flagged | Audit-id v1 will change; v2 will also change. Both are re-locked in tests. Cross-cohort consistency (ΔcTCS ≤ 0.01) re-verified. |
| Schema version bump | Could break backward compatibility | Schema declaration policy test (v1.7.9) catches under-declarations. Pydantic feature gating catches incompatible field usage. |
| New adapter | Could introduce a cohort-specific bias | Adapter must pass input-contract validation. Cohort fairness audit runs on first integration. |
| Fairness panel expansion | Could change disparity findings | Additive only — does not change cTCS itself. New strata are documented; old strata remain comparable. |

All four mitigations rely on the regression-test suite (271 passed,
2 skipped in v1.7.10) being run on every change.

---

## E — EU AI Act Annex IV technical documentation (9 sections)

Regulation (EU) 2024/1689 Article 11 requires Annex IV technical
documentation for high-risk AI systems. Compliance deadline: 2 August
2026 for standalone high-risk AI; 2 August 2027 for MDR/IVDR-regulated
medical AI. The Digital Omnibus (Nov 2025) proposes extension to 2
December 2027 for some categories.

NeuroTCS is research software. If commercialized as a high-risk medical
AI component, the following Annex IV mapping applies. Section numbering
matches Annex IV ordering.

### E.1 — General description of the AI system

cTCS is a deterministic rule-pack audit metric for Alzheimer's disease
longitudinal cohort coherence. Inputs: a cohort of patient trajectories
(states + timestamps). Outputs: cTCS scalar with bootstrap CI, per-
transition admissibility verdicts (opt-in), and FUTURE-AI fairness
stratification (opt-in). Intended deployment: research workflows;
prospective marketing as a medical-device component subject to a separate
submission.

### E.2 — Detailed description of system elements

#### E.2.a — Software components
- `src/neurotcs/audit_core/` — audit kernel, scoring, bootstrap.
- `src/neurotcs/rulepack/` — rule-pack schema, loader, and shipped packs.
- `src/neurotcs/input_contract/v1_1/adapters/` — cohort adapters.
- `src/neurotcs/fairness/` — FUTURE-AI panels B.4.4 / B.4.5.
- `scripts/` — runner scripts.

#### E.2.b — Methods and steps for development
- Specification: project-internal NeuroTCS v1.7 FINAL spec.
- Implementation: maintainer + Claude (Anthropic) as co-developer per
  the maintainer's documented review workflow. Every change reviewed by
  the maintainer; no autonomous modifications.
- Testing: regression test suite of 271+ tests passing double-run.

#### E.2.c — System architecture (per Section 2(c) Annex IV)
Required by the EU AI Act explicitly: "the system architecture
explaining how software components build on or feed into each other".

```
Cohort CSVs (ADNI / OASIS-3 / MIRIAD)
      │
      ▼  (per-cohort adapter)
Trajectory list  ──── metadata (sex, age_band, ...)
      │
      ▼  (audit_core.audit, return_per_transition opt-in)
AuditResult
      ├── ctcs / ptcs / utcs (cluster-bootstrap CIs)
      ├── audit_id / audit_id_v2 (SHA-256 reproducibility hashes)
      └── per_transition: PerTransitionFlags
                  │
                  ▼  (fairness.cohort_fairness_audit)
            FairnessAuditResult (FUTURE-AI panel B.4.4)
```

#### E.2.d — Data requirements and provenance
See Section B.2 and B.3 above.

#### E.2.e — Human oversight measures
The cTCS output is an audit signal for a human reviewer. The fairness
panel surfaces disparities for human investigation. No autonomous
decisions are made.

### E.3 — Monitoring, functioning, control

#### E.3.a — Capabilities and limitations
- cTCS scores are bounded [0, 1]. Bootstrap CIs are reported.
- Limitation: cTCS does not measure clinical correctness; only coherence
  against the rule pack.
- Limitation: rule packs reflect their source publication; if a
  guideline becomes outdated, the corresponding pack does too. Rule-
  pack effective dates are visible in each pack header.

#### E.3.b — Foreseeable unintended outcomes
- Risk: a downstream consumer treats cTCS as a per-patient signal.
  Mitigation: explicit Section C.2.3 prohibition; cohort-level CIs only.
- Risk: rule pack drifts from source publication. Mitigation: rule-pack
  SHA-256 + transcription-attestation policy (v1.1.0 schema feature).

#### E.3.c — Human oversight (per Article 14)
A trained reviewer is the consumer of the cTCS output. The fairness
panel B.4.4 surfaces demographic disparities for review.

#### E.3.d — Specifications on input data
See Section B.2.4 above.

### E.4 — Performance metrics

cTCS and its CIs; flag rate and per-stratum flag rates. See Section C.4.

### E.5 — Risk management system (per Article 9)
- Identified risks: misuse for individual diagnosis; rule-pack staleness;
  demographic disparity.
- Mitigations: documented in C.8.3, D.3, and `docs/validation/`.
- Continuous monitoring: the regression-test suite + double-test
  discipline + locked invariants in Section A.

### E.6 — Lifecycle changes
All changes go through the protocol in Section D.2. CHANGELOG.md is the
canonical change record.

### E.7 — Standards and specifications applied
- Datasheets for Datasets (Gebru 2021).
- Model Cards (Mitchell 2019).
- FUTURE-AI (Lekadir 2025).
- NIA-AA 2018 Research Framework (Jack 2018).
- ISO 14971 risk management principles (referenced; not yet certified).
- IEC 62304 software lifecycle (referenced; not yet certified).

### E.8 — EU declaration of conformity
N/A — NeuroTCS is research software. If submitted as a high-risk AI
medical-device component, this section will be completed at submission.

### E.9 — Post-market monitoring plan
Each release produces a new audit_id on each cohort. Cross-release
consistency is monitored by the locked-invariant tests in
`tests/audit_core/test_real_*_audit.py`. Any divergence from a locked
audit_id triggers a regression investigation before release.

---

## F — Honest gaps acknowledged

This section is the single source of truth for what is NOT yet covered.

1. **Jack 2024 §3 Staging text not yet transcribed.** AA-2024 rule pack
   currently ships a structural skeleton plus the TRAC companion pack
   (`ad/aa_2024_trac@1.0.0`, schema 1.2.0). Full §3 transcription
   blocked on PDF acquisition by the maintainer (the paper is paywalled
   at Alzheimer's & Dementia).
   - Source: Jack et al., *Alzheimer's & Dementia* 2024;20(8):5143-5169,
     DOI [10.1002/alz.13859](https://doi.org/10.1002/alz.13859), PMID 38934362.
   - When obtained, schema-version declaration policy (v1.7.9) and
     transcription-attestation policy (v1.1.0 schema) apply.

2. **ADNI and OASIS-3 fairness pending local joins.** The in-repo
   reference adapters use placeholder demographics. Maruf's production
   workflow already joins PTDEMOG (ADNI) and the OASIS-3 demographics
   table; the runner pattern from v1.7.10 supports them once
   `Trajectory.metadata` is populated with the canonical attribute names.
   Once executed, ADNI and OASIS-3 fairness reports will be locked as
   invariants paralleling the MIRIAD pattern.

3. **No race_ethnicity in MIRIAD.** Single-site UCL DRC cohort; race
   not collected. The fairness panel correctly reports
   `race_ethnicity: unknown` for the entire cohort rather than
   fabricating values.

4. **No comorbidity / disease_stage / treatment_status extraction yet.**
   These canonical FUTURE-AI attributes are recognized by the panel but
   not yet populated by any adapter. They show `unknown` strata.

5. **No TPR / Equalized Odds reported.** cTCS is a rule-pack audit, not
   a classifier. The classifier-level fairness metrics from FUTURE-AI
   Fairness 3 do not apply to this context. The `tpr` field on
   `StratumMetrics` returns `None` by design.

6. **NeuroTCS is not yet a marketed medical device.** Sections D and E
   above prepare for that future submission but no submission has been
   made. ISO 14971 / IEC 62304 / EU AI Act conformity assessment
   processes are referenced but not yet executed.

---

## G — Version history

- **v1.7.11 (AD-lock Step 2.3)**: this datasheet shipped. Four-framework
  consolidation document, structural regression test, citation lock.
- **v1.7.10 (AD-lock Step 2.2)**: demographic fairness pipeline shipped.
- **v1.7.9 (AD-lock Step 2.1)**: schema-version declaration policy +
  silent under-declaration fixed.
- **v1.7.7**: real-MIRIAD audit_ids locked. Three-cohort consistency
  established (ADNI 0.9946 / OASIS-3 0.9942 / MIRIAD 0.9854).

## H — Citation

Salokhiddinov M. NeuroTCS: a citation-locked temporal coherence audit
framework for Alzheimer's disease cohort validation. Version 1.7.11.
2026. Available at: https://github.com/DrMaruf1991/NeuroTCS.

For the underlying frameworks cited in this document, see the linked
DOIs and PMIDs in Section A and at the top of this document.

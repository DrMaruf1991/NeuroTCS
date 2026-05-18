# Changelog

All notable changes to NeuroTCS are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] — 2026-05-18

### Added — Five new methodological modules with primary-source-locked citations

This release implements five new modules that close the spec-vs-code gap for
spec v1.7. Every framework was primary-source verified during a dedicated
framework-audit phase BEFORE any code was written. Seven memory drifts were
caught and corrected; without this phase they would have generated a third
public erratum after E-2026-001 and E-2026-002.

**New modules:**

| Module | Source | License |
|---|---|---|
| `neurotcs.sample_size` | Riley 2024 (BMJ 384:e074821, PMID 38253388) | CC-BY 4.0 |
| `neurotcs.fairness` | FUTURE-AI / Lekadir 2025 (BMJ 388:e081554, PMID 39909534) | CC-BY-NC 4.0 |
| `neurotcs.silent_deployment` | Kwong 2022 (Front Digit Health 4:929508, PMID 36052317) + DECIDE-AI / Vasey 2022 (Nat Med 28:924-933, PMID 35585196) | CC-BY 4.0 + Springer sub |
| `neurotcs.scanner_factorial` | FUTURE-AI Robustness 3 | CC-BY-NC 4.0 |
| `neurotcs.threshold_derivation` | Larson 2025 ACR-SIIM (JACR 22:586-592, PMID 40057886) | Elsevier sub |

**Module summaries:**

- **`sample_size`**: Riley 2024 four-criteria sample-size calculator for binary
  outcomes (O/E, calibration slope, c-statistic, net benefit). Calibration
  slope uses Gauss-Hermite-quadrature Fisher-information integration; the
  Newcombe (2006) formula gives the c-statistic SE. Reproduces N=347 for the
  Riley 2024 ISARIC c-statistic example exactly; calibration-slope criterion
  yields ~1143 vs the paper's 949 (a ~20% conservative bias of the normal-LP
  approximation vs the paper's beta(1.33, 1.75) LP fit; documented and tested).

- **`fairness`**: Two SEPARATE audit panels per the FUTURE-AI distinction
  caught during framework verification: panel B.4.4 stratifies on six
  demographic/clinical attributes (sex, age_band, race_ethnicity, comorbidity,
  disease_stage, treatment_status); panel B.4.5 stratifies on five
  technical/operational attributes (scanner_vendor, field_strength,
  acquisition_site, protocol, operator). The two attribute sets are disjoint
  by design and the test suite enforces this.

- **`silent_deployment`**: Kwong 2022 four-theme silent-trial framework
  (dataset drift, bias, feasibility, stakeholder attitudes) with verbatim
  Table 1 key questions reproduced under CC-BY 4.0 license. Cites BOTH Kwong
  2022 (for silent-trial methodology) AND DECIDE-AI (for reporting items) —
  these are separate primary sources, not a single Stage-A/B/C scheme.
  `SilentDeploymentEvidence` dataclass produces a structured evidence record
  with model hash, rule-pack ID, audit ID, and per-theme findings.

- **`scanner_factorial`**: Multi-dimensional cross-tabulation of audit flags
  across technical dimensions (e.g. vendor × field-strength × interval). Filters
  cells below `min_cell_n` for stable rate estimation. Complements the 1D
  per-attribute robustness panel by surfacing INTERACTION effects (e.g. model
  is fine on Siemens 3T but flags 8% of GE 1.5T transitions) that single-
  attribute stratification can miss.

- **`threshold_derivation`**: Two empirical methods for deriving operational
  audit thresholds from a reference epoch. (1) k-sigma below the reference
  mean; (2) Vovk-style finite-sample conformal lower bound (distribution-free,
  finite-sample valid). Supports ACR-SIIM's "ongoing monitoring with drift
  detection and stop rules" obligation without requiring vendor-fixed
  thresholds.

### Documentation

- **NEW**: `docs/transcription_audit/v1.7_frameworks.md` — full primary-source
  verification audit for all 10 sources (5 frameworks + 5 cross-references)
  with PMID/DOI, license terms, verbatim quotes, and a section enumerating the
  seven memory drifts caught BEFORE code.
- **REPLACED**: `docs/spec/temporalmetric_v1.6_FINAL.md` → `temporalmetric_v1.7_FINAL.md`
  (96 KB, v1.7 spec text from upstream).

### Memory-drift corrections caught during framework verification

| # | Drift | Corrected to | Source check |
|---|---|---|---|
| 1 | FUTURE-AI = 118 experts / 51 countries | 117 / 50 | BMJ paper (not arXiv preprint) |
| 2 | Haller 2022 pages 851–858 | 851–864 (14 pages) | Springer metadata + PubMed |
| 3 | DECIDE-AI has Stage A/B/C silent-deployment labels | DECIDE-AI single-stage; silent-deployment is Kwong 2022 | Vasey 2022 full text + Kwong 2022 |
| 4 | FUTURE-AI Fairness includes scanner vendor | Scanner vendor is Robustness 1; two panels | FUTURE-AI BMJ Table 2 |
| 5 | DECIDE-AI = 17-item core | 17 AI-specific + 28 subitems + 10 generic | Vasey 2022 abstract |
| 6 | Riley framework applies to audit-time sizing | Riley is external-validation precision | Riley 2024 §1 |
| 7 | Larson 2025 has no commercial conflict | Larson holds Bunkerhill Health equity | JACR competing-interests section |

### Tests

- Baseline 145/145 tests still passing (locked ADNI invariant intact:
  cTCS=0.9946, audit_id=fa448b8f…; locked OASIS-3 replication intact:
  cTCS=0.9942, ΔcTCS=0.0004).
- **NEW**: 12 sample-size tests (validated against Riley 2024 worked
  examples; c-statistic N=347 reproduced exactly).
- **NEW**: 9 fairness tests (citation lock, attribute disjointness between
  B.4.4 and B.4.5 panels, disparity detection).
- **NEW**: 9 silent-deployment tests (Kwong 2022 + DECIDE-AI citation locks,
  verbatim Table 1 questions, DECIDE-AI-no-stage-labels regression test).
- **NEW**: 8 scanner-factorial tests (2D/3D interaction detection, min_cell_n
  filter, length-mismatch errors).
- **NEW**: 10 threshold-derivation tests (k-sigma monotonicity, conformal
  coverage monotonicity, Larson 2025 citation lock).

### Citation block

`CITATION.cff` updated with 10 new bibliography entries: Riley 2024,
Lekadir 2025 (FUTURE-AI), Haller 2022 (R-AI-DIOLOGY), Larson 2025 (ACR-SIIM),
Vasey 2022 (DECIDE-AI), Kwong 2022 (silent trial), Collins 2024 (TRIPOD+AI),
Tejani 2024 (CLAIM).

### What's next

- v1.7.1: validation harness (Piece 7 of 7) — synthetic-trajectory self-tests
- v1.7.2: signed JSON audit certificates + DICOM SR output
- v1.7.3: MLOps callbacks (MLflow, Weights & Biases)
- v1.7.4: FHIR Observation output schema (Piece 5 of 7)
- v1.8.0: six non-AD rule-pack priors (PD, MS, oncology, stroke, lung nodule)
- v1.9.0: FDA PCCP Evidence Pack (3 required components per Final Guidance 2024)
- v2.0.0: Layer 2 leaderboard + Layer 3 dashboard

---

## [1.6.0] — 2026-05-18

### Fixed — `ad/aa_2024` priors populated (ERRATA E-2026-002)

**Severity**: Restrictive — pTCS was unavailable on AA-2024 audits since v1.0.0. Did not affect cTCS, uTCS, or any published Aim 1 ADNI / Aim 2 OASIS-3 findings (those use `niaaa_2018`).

**What changed**: `ad/aa_2024@1.1.0` shipped with `transition_priors: []`. v1.6.0 bumps to `@1.2.0` with **13 transition priors**, every one citation-locked to a peer-reviewed primary source that explicitly reports the rate as annual (not cumulative-misinterpreted-as-annual, per E-2026-001 methodology).

**Primary sources used** (5 independent cohorts triangulated: MCSA, ADNI, multicenter Karagianni, BioFINDER-2 / Ossenkoppele, NACC):

| Transition | Setting | ACR | Source |
|---|---|---|---|
| Stage_0 → Stage_1 | population | 0.024 | Roberts 2018 (JAMA Neurol, PMID 29710225) |
| Stage_0 → Stage_1 | clinical | 0.156 | Jagust & Landau 2021 (Neurology, PMID 33408147) |
| Stage_1 → Stage_2 | clinical | 0.0675 | Karagianni 2025 (Alz Dem Suppl, PMC12724900) |
| Stage_2 → Stage_3 | clinical | 0.10 | Ossenkoppele 2022 (Nat Med, PMID 36357681) |
| Stage_3 → Stage_4 | clinical | 0.13 | Ossenkoppele 2022 (Nat Med, PMID 36357681) |
| Stage_4 → Stage_5 | clinical | 0.20 | Tariot 2024 (Alz Res Ther, PMID 38355706) |
| Stage_4 → Stage_5 | population | 0.06 | Salemme 2025 (Alz Dem DADM, DOI 10.1002/dad2.70074) |
| Stage_5 → Stage_6 | clinical | 0.266 | Tariot 2024 (Alz Res Ther, PMID 38355706) |

Plus 5 derived Stage_N → Stage_N+2 priors marked `prior_type: "derived"` (products of single-step ACRs with √2 CI inflation; Tariot 2024 multistate Markov methodology).

**Tests**: 144/144 passing (added 6 new priors-specific tests in `tests/rulepack/`, plus updated 2 stale audit-core tests; new test `test_audit_ptcs_available_on_aa_2024` confirms pTCS is now computable on AA-2024 trajectories).

**Methodology**: every ACR-type value is now subject to the methodology requirements established in E-2026-001 and E-2026-002:
1. Verified against peer-reviewed primary source via DOI or PMID
2. Source paper methods section explicitly confirms rate is annual (not cumulative)
3. Clinical vs population stratification preserved where literature supports
4. Derived priors marked `prior_type: "derived"` with link to underlying primaries

### Strategic

The AA-2024 instantiation is now fully operational. NeuroTCS can audit anti-amyloid-treated patients using the TRAC pack (v1.4.0) AND can compute pTCS on AA-2024 staging (v1.6.0). The Aim 3 MIRIAD test-retest workflow can now use `niaaa_2018` for clinical labels and `aa_2024` for biological staging when tau-PET is available. The AD instantiation has zero remaining "Known Limitations" entries in its core scope.

### Test suite: **144/144** passing
- 42 rulepack (36 prior + 6 new AA-2024 priors tests)
- 10 input contract v1.0
- 23 input contract v1.1
- 28 OASIS-3 adapter
- 41 audit core (39 prior + 2 renamed/repurposed tests for v1.2.0 priors)

---

## [1.5.0] — 2026-05-18

### Fixed — MCI→AD transition priors corrected (ERRATA E-2026-001)

**Severity**: Affects pTCS values only. **cTCS and uTCS — including the headline Aim 1 ADNI and Aim 2 OASIS-3 replication findings — are unaffected** (cTCS is the admissibility kernel and does not depend on priors).

**What happened**: The `ad/niaaa_2018@1.1.0` rule pack encoded MCI→AD annual transition priors as 0.415 (clinical) and 0.27 (population), citing Salemme 2025. These figures are actually the **cumulative incidence of dementia over the meta-analysis's mean 5.2-year follow-up**, NOT annual rates. The correct annual conversion rates from the same primary source are 0.11 (clinical) and 0.06 (population), explicitly reported by Salemme 2025 (DOI 10.1002/dad2.70074): *"The ACR nearly doubled from 6% in population settings to 11% in clinical settings."*

**Fix**: `ad/niaaa_2018` bumped to `@1.2.0` with corrected priors derived directly from Salemme 2025 ACR values, plus a new clinical CN→MCI prior (Hayden 2017, doi:10.1016/j.jalz.2016.07.151, UC Davis ADC longitudinal cohort: 30% ACR for memory-clinic referrals vs 5% for community recruits). All priors cross-validated by Mitchell & Shiri-Feshki 2009 (DOI 10.1111/j.1600-0447.2008.01326.x).

**Locked ADNI invariant (v1.5.0)**: 12,006 transitions, 65 flagged (0.54 %), **cTCS = 0.9946**, **pTCS = -0.3452** (corrected, clinical priors), uTCS = 0.9946, **audit_id = `fa448b8fc8bc410fa5a35e5845083e1d00a216ba4ee5baba482762139fd4a74a`**.

**Locked OASIS-3 invariant (v1.5.0)**: 1,247 subjects, 7,248 transitions, 30 flagged (0.41 %), **cTCS = 0.9942** (unchanged), pTCS and audit_id need local re-derivation with corrected priors (test file updated to capture them on first run).

**ΔcTCS vs ADNI = 0.0004 (preserved)**. The headline external-replication finding is bit-exact unchanged.

### Methodology
- Every numerical value in a rule pack must now be cross-validated against at least one additional primary source before commit. For ACR-type values specifically, the source paper's methods section must explicitly confirm whether the rate is annual or cumulative. This is the most common source of confusion in MCI prognosis literature.
- Public ERRATA file (`ERRATA.md`) added at repo root for transparent correction tracking.

### Acknowledgment
Bug identified by Dr. Salokhiddinov during a v1.5.0 review session that pushed for primary-source evidence verification of all AD rule packs. The methodology fix is more important than the value fix.

### Test suite: **136/136** passing
- 36 rulepack (TRAC + schema v1.2 tests retained)
- 10 input contract v1.0
- 23 input contract v1.1
- 28 OASIS-3 adapter
- 39 audit core (added "see ERRATA E-2026-001" cross-reference to test comments)

### Strategic
This is the first published NeuroTCS errata, and it follows the right pattern: bug found by primary-source review, root-cause analysis published transparently, fix shipped with full forward-citation pointers, methodology updated to prevent recurrence. For the FDA Q-Submission (Q1 2027), having a public errata process is a positive signal, not a negative one.

---

## [1.4.0] — 2026-05-18

### Added — TRAC framework + schema v1.2 + evidence-base verification

**TRAC rule pack** (`ad/aa_2024_trac@1.0.0`) — Treatment-Related Amyloid Clearance:
- Encodes the framework from La Joie R, Cummings JL, Dage JL, et al., *Alzheimer's & Dementia* 2025;21(11):e70997 (DOI 10.1002/alz.70997, PMCID PMC12657122), an Alzheimer's Association-convened workgroup paper led by UCSF (Renaud La Joie, PhD).
- State space: `A_neg`, `A_pos`, `Partial_TRAC`, `Full_TRAC`.
- 6 admissible transitions (1 natural amyloid accumulation + 5 treatment-conditional).
- 3 documented inadmissible transitions (e.g. untreated A+ → A−, biologically implausible spontaneous clearance).
- Drug-specific Centiloid thresholds noted: lecanemab interruption criterion 1 scan <11 CL OR 2 consecutive <25 CL; donanemab fibrillar clearance criterion <24.1 CL (both verified from La Joie 2025 footnote on TRAILBLAZER-ALZ criteria).
- Transcription audit doc at `docs/transcription_audit/ad_aa_2024_trac.md` maps every YAML line to its source statement in La Joie 2025.
- Covers FDA-approved anti-Aβ therapies: **lecanemab (Leqembi**, Eisai/Biogen; accelerated approval 2023-01-06, traditional/full approval **2023-07-06**, maintenance dosing 2025-01-26) and **donanemab (Kisunla**, donanemab-azbt, Eli Lilly; full approval **2024-07-02**, modified-titration label 2025-07-09 per TRAILBLAZER-ALZ 6).

**Schema v1.2.0** — backward-compatible extension of rule pack format:
- Added optional `required_conditions: dict[str, list[str]]` field to `Transition` for context-conditional admissibility.
- Added optional `conditions_evaluated_at: Literal["from_visit", "to_visit", "either"]` field controlling which visit's context is checked. Default `"either"`.
- Added `SUPPORTED_SCHEMA_VERSIONS = {"1.1.0", "1.2.0"}` — existing 8 production packs continue to load unchanged.
- New `check_schema_version_supported` model validator on `RulePack` rejects unknown versions.
- New `_check_required_conditions` helper evaluates per-visit context fields against `required_conditions`.

**Audit core updates**:
- `Trajectory.transitions_with_context()` — new method exposes per-visit `treatment_status` context alongside each transition.
- `ctcs_per_patient` and `utcs_per_patient` now thread context through `is_admissible(...)` so conditional transitions are evaluated correctly. Trajectories lacking `treatment_status` pass `None` context, which the rule pack treats as fail-closed for conditional transitions (correct behavior — cannot certify a treatment-dependent transition without treatment evidence).
- `audit()` flagged-transition counter also honors context.

**Evidence-base verification methodology**:
- All FDA approval dates and DOIs in the TRAC pack and v1.4.0 documentation were verified against primary sources via web search before committing — no claim relies on language-model memory. Citations are traceable to Eisai/Biogen and Eli Lilly press releases, FDA announcements, and PubMed/PMC.
- The verified-evidence table (FDA dates, DOIs, Centiloid thresholds) is reproduced in `docs/transcription_audit/ad_aa_2024_trac.md` so any reviewer can spot-check.

**README** — added "Known limitations and roadmap" section that publicly documents remaining gaps after v1.4.0:
- AA 2024 transition priors still empty (`transition_priors: []`) — pTCS unavailable for that pack until populated from Mendes 2025 (PMC12079574, *Neurology* May 13 2025, DOI 10.1212/WNL.0000000000213675) and similar.
- Plasma p-tau217 / Aβ42/40 reference range bindings — partial in input contract v1.1, full in v1.5.0.
- Tau PET tracer scope — Tauvid/flortaucipir (Eli Lilly, AV-1451, FDA approved 2020) supported; **MK-6240 / florquinitau F-18** (Lantheus, NDA accepted 2025-10-28, PDUFA target **2026-08-13**) will be added on approval.

**Tests** — 16 new tests added (12 rulepack + 4 audit_core):
- Schema v1.2 acceptance of `required_conditions` and `conditions_evaluated_at`.
- TRAC pack loads under v1.2 schema with correct state space and citation.
- All 6 admissibility cases for treatment-conditional transitions (with/without treatment, with/without context, natural progression).
- End-to-end audit on a synthetic 3-patient TRAC cohort: correct flagging of untreated implausible clearance.
- Backward compatibility: all 8 existing v1.1.0 packs still load under v1.2.0 schema.
- Locked ADNI invariant **unchanged** post-schema-bump: cTCS = 0.9946, 65/12006 flagged.

### Test suite: **136/136** passing
- 36 rulepack (24 prior + 12 new for v1.2 / TRAC)
- 10 input contract v1.0
- 23 input contract v1.1
- 28 OASIS-3 adapter
- 39 audit core (35 prior + 4 new for TRAC end-to-end)

### Strategic
- Closes the largest gap in the AD instantiation: NeuroTCS now correctly handles successfully-treated anti-amyloid therapy patients without falsely flagging biological reversal as model error.
- Schema v1.2 generalizes beyond AD — any future rule pack can declare conditional admissibility for any context field (e.g. treatment status, comorbidity, dose).
- Methodology fix: every regulatory-relevant fact verified at primary source before commit. Documented in CHANGELOG and transcription audit. Material for the FDA Q-Submission (Q1 2027).

---

## [1.3.0] — 2026-05-17

### Added — Aim 2 external replication (OASIS-3)
- **`neurotcs.input_contract.v1_1.adapters.adapter_oasis3`** — production adapter for the OASIS-3 longitudinal cohort (LaMontagne et al. 2019, doi:10.1101/2019.12.13.19014902). Loads UDS Form B4 CDR (Morris 1993, PMID 8232972), maps `CDRTOT` → NIA-AA 2018 categorical states, builds Trajectory objects ready for `audit()`. Cites both sources in the emitted manifest.
- **`load_oasis3_trajectories()`** programmatic API with `OASIS3LoadReport` diagnostic dataclass.
- **dx1-disagreement flagging** — adapter records (but never drops) rows where the clinician-text diagnosis disagrees with CDR-derived state. Diagnostic only; CDR remains primary per Morris 1993.
- **PHI hashing** with `oasis3_aim2_2026` salt — OASISIDs are re-hashed before leaving the adapter so downstream artifacts cannot be cross-walked to the OASIS distribution.
- **Submission-export pipeline** (`build_predictions` / `build_patients` / `build_manifest`) parallel to the ADNI adapter, conforming to input contract v1.1.
- **Locked-invariant test** at `tests/audit_core/test_real_oasis3_audit.py`. Asserts the exact Aim 2 numbers reproduce when the OASIS-3 bundle is present. Skipped on CI; runs locally.
- **`examples/oasis3_audit_demo.py`** worked example, mirrors the ADNI demo.
- **`docs/validation/aim2_oasis3_external_replication.md`** — validation report ready for the Nature Medicine supplement.
- **28 new unit tests** at `tests/input_contract/test_oasis3_adapter.py` covering CDR mapping, dx1 mapping, hash determinism, NaN handling, interval preservation, and submission export.

### Validated — locked invariants
- **OASIS-3 (Aim 2):** 1,247 subjects scored, 7,248 transitions, 30 flagged (0.41%), **cTCS = 0.9942** (BCa 95% CI: 0.9902–0.9964), pTCS = −0.5188, uTCS = 0.9942, `audit_id = 96d942e41e9f94a33718d9a107dedf443de728bdd16dcf36ade18ca1f3f4077a`.
- **ΔcTCS vs ADNI (Aim 1, cTCS = 0.9946) = 0.0004.** Two independent cohorts, confidence intervals overlap almost completely. The cTCS metric generalizes.
- **Test suite total: 120/120** (24 rule pack + 10 input v1.0 + 23 input v1.1 + 28 OASIS-3 adapter + 35 audit core).

### Strategic
- First external NeuroTCS replication. Headline result for the Nature Medicine paper's Aim 2 section. Moves NeuroTCS from "ADNI methodology paper" to "validated multi-cohort audit metric."

---

## [1.2.0] — 2026-05-17

### Added
- **Piece 4 — Audit core (`src/neurotcs/audit_core/`).** End-to-end scoring engine implementing temporalmetric v1.6 FINAL spec §A.2–A.5.
  - **cTCS** (Categorical Temporal Consistency Score) — rule-based admissibility kernel.
  - **pTCS** (Probabilistic TCS) — time-aware Markov log-likelihood with matrix exponential `M(Δτ) = exp(Q · Δτ / 365)`. Generator `Q` built automatically from rule pack `transition_priors`.
  - **uTCS** (Uncertainty-weighted TCS) — Thulasidasan 2019 extension; weights = `max(p̂_t) · max(p̂_{t+1})`.
  - **Cluster bootstrap CI** — B=10,000 patient-level resamples (Efron & Tibshirani 1993 Ch. 8) with **BCa correction** (Ch. 14).
  - **Huber M-estimator** (c = 1.345) reported alongside mean for robustness (Huber 1981).
  - **Paired cluster bootstrap** for model-vs-model comparison.
  - **`audit_id`** — SHA-256 over (rule pack SHA, per-patient scores, B, seed, ci_method, prior_type). Reproducible across machines.
- **CLI**: `neurotcs-audit audit --predictions X.csv --rulepack ad/niaaa_2018 --output report.json` (also: `python -m neurotcs.audit_core audit ...`).
- **35 audit_core tests** covering trajectory invariants, scoring correctness on synthetic data, generator-matrix construction, BCa correctness, determinism, paired bootstrap, and end-to-end synthetic + real-ADNI audit.
- Top-level convenience imports: `from neurotcs import audit, Trajectory, cluster_bootstrap, ...`.
- `numpy>=1.24` and `scipy>=1.11` promoted to core dependencies.

### Validated
- **Real ADNI end-to-end audit:** 12,006 transitions, 65 flagged (0.54%); cTCS=0.9946, pTCS=-0.3319, uTCS=0.9946. Identical flagged count to v1.1 invariant.
- **Test suite total: 92/92** (24 rule pack + 10 input v1.0 + 23 input v1.1 + 35 audit core).

### Changed
- Top-level `neurotcs/__init__.py` re-exports audit_core API.
- `pyproject.toml` adds `neurotcs-audit` console-script entry point.

---

## [1.1.0] — 2026-05-17

### Added
- Umbrella repo structure with `src/` layout (PEP 621).
- Piece 1 — Input contract v1.0 (categorical, 10 tests).
- Piece 2 — Input contract v1.1 (continuous biomarkers, UCUM, 23 tests).
- Piece 3 — Rule pack v1.1: 8 production rule packs via verbatim transcription (24 tests).
- Repo hygiene: `pyproject.toml`, LICENSE (Apache-2.0), CHANGELOG, CONTRIBUTING, SECURITY, CI workflow.
- Real-world validation: 12,006 ADNI transitions, 65 flagged (0.54%).

### Strategic
- Adopted "published-guideline-as-authority" model. Rule packs require provenance to internationally endorsed published guidelines, not novel specialist authorship.

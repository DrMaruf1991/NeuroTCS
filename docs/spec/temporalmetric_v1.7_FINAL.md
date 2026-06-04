# `temporalmetric` — Final Executable Project Specification v1.7 FINAL

> **⚠️ v1.9.0 scope-override notice (2026-05-24; updated 2026-06-04):** This spec was authored when NeuroTCS was scoped as a multi-disease platform with PD / MS / oncology / stroke / lung-nodule rule packs designed-for. As of v1.9.0, NeuroTCS is **scope-narrowed to Alzheimer's disease only**, and it stays that way: NeuroTCS does not roadmap non-AD coverage. The non-AD rule packs, the Aim 5 multi-disease portability arm (PPMI + RIDER cohorts), and the §B.6 multi-disease rule-pack registry are **removed from scope and preserved as archival history only** (recoverable from git tag v1.8.1 / the offline archive). They are NOT a committed future deliverable of NeuroTCS or of any other repository. The non-AD content in this spec is retained purely as historical record of the original design intent; it is **not** the operational scope. The canonical scope and regulatory-status statement is [`docs/SCOPE.md`](../SCOPE.md). The §B.6 registry, Aim 5, and dataset-table entries for PPMI / RIDER are explicitly out-of-scope; the four operational cohorts are ADNI, OASIS-3, NACC, and MIRIAD (all AD), which produce the byte-exact four-cohort triangulation lock recorded in the v1.8.0 + v1.9.0 release notes. NeuroTCS is a research instrument and is not FDA-cleared; any FDA pathway is an aspiration, not a current claim (see docs/SCOPE.md Regulatory status).

---

**A Model-Agnostic Temporal Coherence Audit Framework for Longitudinal Medical AI** — with **NeuroTCS** as the Alzheimer's Disease Instantiation _(v1.9.0+ AD-only scope; designed-for non-AD packs are archival history only, not a roadmap)_.

Lead: Dr. Maruf Salokhiddinov (DrMaruf1991), ESOR-BRACCO-ESNR Neuroimaging Fellow, KIUT, Tashkent.
Version 1.7 FINAL · 12 May 2026 · License: Apache-2.0 (library), CC-BY-4.0 (paper).

v1.7 closes five gaps flagged by external auditor (deep-research report, May 2026), each verified against primary sources before integration:

1. **Subgroup fairness audit panel** (§B.4.4) — explicit stratification by sex, age band, race/ethnicity, scanner vendor, field strength, disease stage, treatment status; aligns with TRIPOD+AI (Collins 2024), CLAIM 2024 (Tejani 2024), FUTURE-AI Fairness principle (Lekadir 2025 BMJ).
2. **Silent-deployment phase** (§B.5.3, Kwong 2022 silent-trial methodology + DECIDE-AI reporting items) — explicit two-site silent pilot in W17–W20 logging alert frequency, review yield, operational burden without changing clinical decisions; aligned with Kwong et al. *Front Digit Health* 2022;4:929508 (CC-BY 4.0) and reported per Vasey et al. *Nat Med* 2022;28:924-933 DECIDE-AI checklist.
3. **Riley 2024 sample-size methodology** (§B.4.1) — Aims 1, 2, 3, 5 sample sizes replaced with Riley framework (Riley 2024 BMJ 388:e074821; Riley 2021 *Stat Med* binary DOI 10.1002/sim.9025; Archer 2021 *Stat Med* continuous DOI 10.1002/sim.8766) targeting precise CI widths for calibration, discrimination, and clinical utility.
4. **Scanner/vendor and interval-length stress tests** (§B.4.5) — explicit factorial sensitivity matrix including Siemens × GE × Philips × Canon vendor stratification; 1.5T vs 3T field strength; short (<6mo), medium (6–18mo), long (>18mo) interval bins.
5. **Operational threshold derivation methodology** (§A.8) — methodology only, not predetermined values; thresholds will be empirically calibrated from Aim 1 mediation analysis with bootstrap CI per Threshold Optimization principles, ACR-SIIM Practice Parameter (approved 5 May 2026) "stop rules" guidance, and conformal prediction frameworks.

Three new framework citations added — all verified primary-source May 2026:
- **FUTURE-AI** (Lekadir K et al. *BMJ* 2025;388:e081554, DOI 10.1136/bmj-2024-081554, PMID 39909534) — six principles consensus framework, 117 experts from 50 countries.
- **R-AI-DIOLOGY** (Haller S et al. *Neuroradiology* 2022, DOI 10.1007/s00234-021-02890-w, PMID 35098343) — neuroradiology-specific 10-aspect AI checklist; high relevance for ASFNR audience.
- **ACR-SIIM Practice Parameter for Imaging AI** (approved ACR Council 5 May 2026 + ARCH-AI designation + Assess-AI registry + Larson 2025 JACR roadmap DOI 10.1016/j.jacr.2025.02.008, PMID 40057886) — first professional-society practice parameter explicitly requiring ongoing AI performance monitoring with drift detection and stop rules. `temporalmetric` is operationally aligned with this parameter.

All v1.6 content preserved: AA 2024 primary + TRAC handling + ADNI translation layer + Schuessler 2025 + Jian 2025 TimeFlow differentiation + AUDIT citation correction.

---

## TL;DR

`temporalmetric` is a post-hoc, model-agnostic, disease-agnostic temporal coherence audit framework that scores any longitudinal medical AI classifier on whether its per-visit predictions obey clinically plausible disease trajectories. The library ships a versioned, citation-locked YAML rule-pack registry. **NeuroTCS** is the launch instantiation, with **Alzheimer's Association 2024 biological + clinical staging (Jack 2024 PMID 38934362) as the primary production rulepack** and NIA-AA 2018 retained as legacy compatibility mode. The **Treatment-Related Amyloid Clearance (TRAC) framework (La Joie 2025 Alzheimer's & Dementia 21(11):e70997, DOI 10.1002/alz.70997)** is integrated to handle anti-amyloid-treated patients — distinguishing true biological clearance from spurious AI trajectory flips. Designed-for rule packs cover Parkinson's (Hoehn-Yahr / MDS-UPDRS), multiple sclerosis (EDSS + McDonald 2024 [Montalban 2025]), oncology (RECIST 1.1 / iRECIST), stroke follow-up (modified Rankin Scale), and lung nodule surveillance (Fleischner 2017). The architectural moat is the rule-pack registry: adding a new disease is a clinician-authored YAML PR with citation_pmid, not a library rewrite.

Workshop-first execution from ASNR Austin (17–20 May 2026) through ASFNR Newport Beach (9–12 Oct 2026), Nature Medicine submission by W22, FDA Q-Submission Q1 2027 with PCCP-aligned post-market monitoring positioning under FDORA §515C (21 USC 360e-4) and FDA Final Guidance of 4 December 2024.

The critical engineering discipline is citation-locked, version-stamped YAML rules — never inferred from a model — returning INSUFFICIENT_DATA rather than fabricating a score. This matches Maruf's CURANIQ evidence-locked architecture and directly addresses the post-market audit gap that FDA OSEL identified as an active research need (FDA Methods and Tools for Effective Postmarket Monitoring of AI-Enabled Medical Devices program, ongoing). Only ~8% of FDA-cleared AI/ML devices through 2025 have authorized PCCPs; only ~30% of submissions report key performance metrics (Sivakumar 2025 PMC12595527; industry analyses per IntuitionLabs PCCP review 2025). The gap is real, quantified, and platform-sized: AD-only TAM ~$200M → multi-specialty platform TAM ~$5B+.

---

## A. Methodology

### A.1 Setup

For subjects *i ∈ {1, …, N}* with visits *t = 1, …, Tᵢ* at calendar dates *τᵢ,ₜ*, an AI classifier *f* returns per visit:
- categorical prediction `ŷᵢ,ₜ ∈ S` (disease-specific state space)
- probability vector `p̂ᵢ,ₜ ∈ Δ^|S|`
- optional uncertainty `σᵢ,ₜ ∈ [0,1]`

The audit operates without retraining f. Post-hoc and model-agnostic.

### A.2 Categorical TCS (cTCS)

`cTCSᵢ = (1 / (Tᵢ − 1)) · Σₜ K(ŷᵢ,ₜ, ŷᵢ,ₜ₊₁, Δτ)`

where K is a binary clinical-plausibility kernel from a versioned rulepack. Cohort cTCS = (1/N) Σᵢ cTCSᵢ ∈ [0,1].

**NeuroTCS v1.0 PRIMARY rule matrix — AA 2024 (Jack 2024 PMID 38934362, Alzheimer's & Dementia 20:5143-5169, DOI 10.1002/alz.13859):**

State space = integrated biological + clinical staging:
- **Biological staging** based on core biomarkers (Core 1: amyloid PET, CSF Aβ42/40, plasma p-tau217, plasma Aβ42/40; Core 2: tau PET, plasma MTBR-tau243). Stages 0–6, with Stage 0 added for asymptomatic biomarker-negative individuals with genetically determined AD.
- **Clinical staging** runs in parallel and is bounded by copathology, cognitive reserve, and resistance modifiers (per Jack 2024 §3 and Hansson & Jack 2024 Nature Aging 4:1029-1031).

Admissibility rules:
- Biological staging is **monotone non-decreasing** in the absence of treatment-related amyloid clearance (TRAC, see §A.2.1). Backward biological-stage transitions in untreated patients are inadmissible by default.
- Clinical staging can fluctuate within bounds defined by copathology and reserve (e.g., delirium, depression, sleep disorders can transiently worsen clinical stage without biological progression).
- Cross-stage jumps (e.g., Stage 1 → Stage 4 within < 12 months) are inadmissible without intervening biomarker confirmation.
- AT(N) classification flips that are biologically implausible (e.g., A+ → A− without TRAC criteria met) are flagged.

**NeuroTCS v0.x LEGACY rule matrix — NIA-AA 2018 (Jack 2018 PMID 29653606):**

Retained for processing pre-2024 ADNI/OASIS-3 categorical labels. State space = CN / MCI / AD with biomarker categories A/T/N. Admissible — self-loops, CN→MCI any Δτ, MCI→AD any Δτ, CN→AD only Δτ ≥ 365 days. Reversion MCI→CN only Δτ ≥ 180 days with population-prior flag (Salemme 2025 reversion rates: 8.7% clinical / 28.2% population). AD→MCI and AD→CN inadmissible by default; overrideable with citation.

**ADNI label translation layer (NIA-AA 2018 → AA 2024):**

ADNI codes subjects as CN / SMC / EMCI / LMCI / AD. The library ships a translation layer:
- CN with A− → AA 2024 Stage 0 (asymptomatic biomarker-negative)
- CN with A+ → AA 2024 Stage 1 (asymptomatic biomarker-positive)
- SMC/EMCI with A+T+ → AA 2024 Stage 2–3 (transitional cognitive/clinical)
- LMCI with A+T+N+ → AA 2024 Stage 4 (MCI with biological + neurodegenerative confirmation)
- AD with A+T+N+ → AA 2024 Stage 5–6 (dementia, severity-dependent)
- Where biomarkers are missing (subset of ADNI subjects without amyloid PET), fall back to clinical staging only with explicit `BIOMARKER_INCOMPLETE` flag in output

Translation is deterministic, YAML-encoded, and version-stamped (`adni_translation_v1.yaml`).

### A.2.1 TRAC handling — anti-amyloid-treated patients

The Treatment-Related Amyloid Clearance (TRAC) framework (La Joie R, Cummings JL, Dage JL, et al. *Alzheimer's & Dementia* 2025;21(11):e70997, DOI 10.1002/alz.70997, PMC12657122) defines biomarker-confirmed amyloid clearance after anti-Aβ therapy. The framework requires:

1. Pretreatment biomarker confirmation of cerebral Aβ deposition (amyloid PET positive at baseline)
2. Treatment with an Aβ-targeting therapy (lecanemab, donanemab, aducanumab, or future-approved)
3. Follow-up biomarker test indicative of partial or full clearance of Aβ deposits

TRAC classifications:
- **Full TRAC**: post-treatment amyloid-PET < 11 CL (Centiloid) or < 24.1 CL (donanemab criterion)
- **Partial TRAC**: significant Centiloid drop but remaining above threshold

For NeuroTCS, TRAC patients are a special case:
- A patient on lecanemab whose amyloid PET goes from positive → negative (full TRAC) over treatment is a **real biological change**, not a model flip. The rulepack must NOT penalize this as an inconsistency.
- The library accepts an optional `treatment_status` field per visit: `none` / `anti_amyloid_active` / `anti_amyloid_discontinued`. If `anti_amyloid_active` is present and amyloid-PET shows partial or full TRAC criteria met, biological-stage reversion (e.g., A+ → A−) is **admissible**.
- Clinical-stage trajectory is independent: per AA 2024 Workgroup and La Joie 2025, full TRAC does not equate to clinical cure ("disease is still there, modified version of the disease"; UCSF press release Jan 2026). Clinical stage continues forward per natural history modulated by treatment effect.
- The rulepack `ad/aa_2024_trac.yaml` ships in v0.1 as an extension of the primary AA 2024 rulepack. Activation requires explicit `treatment_status` field in the input CSV; falls back to non-TRAC AA 2024 rules if `treatment_status` is absent.

This is the differentiator that makes NeuroTCS deployable in current anti-amyloid-treated patient populations (ALZ-NET's 600+ anti-amyloid-treated subset, CTAD 3 Dec 2025 readout). Without TRAC handling, NeuroTCS would falsely flag every successfully-treated patient as inconsistent.

### A.3 Probabilistic TCS (pTCS)

Time-aware Markov log-likelihood with matrix exponential of clinically-constrained generator Q:

`M(Δτ) = exp(Q · Δτ/365)`

`pTCSᵢ = (1 / (Tᵢ − 1)) · Σₜ log Mŷᵢ,ₜ, ŷᵢ,ₜ₊₁(Δτ)`

Q calibrated from literature priors (Salemme 2025 for AD; Goetz 2008 MDS-UPDRS for PD; Eisenhauer 2009 RECIST 1.1 response thresholds for oncology) or held-out training cohort. Never the test cohort.

### A.4 Uncertainty-weighted TCS (uTCS)

Extends Thulasidasan 2019 Overconfidence Error (arXiv 1905.11001) from single predictions to transitions:

`uTCSᵢ = (1 / (Tᵢ − 1)) · Σₜ wᵢ,ₜ · K(ŷᵢ,ₜ, ŷᵢ,ₜ₊₁, Δτ)`

with `wᵢ,ₜ = max(p̂ᵢ,ₜ) · max(p̂ᵢ,ₜ₊₁)`. Confident clinically-implausible flips penalized hardest.

### A.5 Bootstrap CI

Cluster bootstrap by subject (B=10,000); per Efron & Tibshirani 1993 Ch. 8. Pairwise model comparison with paired cluster bootstrap, BCa correction. Huber M-estimate (c=1.345) reported alongside mean for robustness.

### A.6 Anatomical inconsistency attribution

For high-penalty flips (K=0 and wᵢ,ₜ > 0.7), compute differential saliency `ΔSᵢ,ₜ = |Sᵢ,ₜ₊₁ − Sᵢ,ₜ|` using GradCAM (Selvaraju 2017) or SHAP (Lundberg & Lee 2017). Aggregate over AAL atlas ROIs (Tzourio-Mazoyer 2002, NeuroImage 15:273-289). Report regional flip signature — does inconsistency localize to disease-relevant regions (hippocampus / entorhinal / posterior cingulate for AD; substantia nigra / putamen for PD)?

### A.7 Cohort-level mediation

Pre-specified hypothesis: cohort TCS predicts downstream cognitive decline beyond per-scan AUC.

- Model 1: `ΔMMSE_24 ~ AUC + age + sex + APOE + (1|site)`
- Model 2: `ΔMMSE_24 ~ AUC + cTCSᵢ + age + sex + APOE + (1|site)`

Causal mediation via Imai 2010 (Psychological Methods 15:309-334; R package `mediation`). Analogous for PD (ΔMDS-UPDRS-III at 24mo) and oncology (time-to-progression beyond per-scan response classification).

### A.8 Sample size calculations (Riley 2024 framework)

Replaces ad hoc round-number minima with **Riley framework calculations** (Riley RD et al. *BMJ* 2024;385:e074821, DOI 10.1136/bmj-2023-074821 — "Evaluation of clinical prediction models part 3: calculating the sample size required for an external validation study"; methods papers Riley 2021 *Stat Med* binary DOI 10.1002/sim.9025; Archer 2021 *Stat Med* continuous DOI 10.1002/sim.8766; Riley 2022 *Stat Med* time-to-event DOI 10.1002/sim.9275). Each Aim's N is derived from explicit target CI widths for the primary performance measure, anticipated event proportion, expected effect size, and assumed variance — not from convenience minima.

**Aim 1 (ADNI reliable scoring):** Primary measure = cohort cTCS with target 95% CI half-width ≤ 0.025 (i.e., CI width ≤ 0.05 on [0,1] scale). Riley closed-form (continuous outcome, Archer 2021 §3) with assumed within-cohort cTCS SD ≈ 0.18 (estimated from preliminary AD pilots Ouyang 2021, Zhang 2025 L2C-FNN) and ICC = 0.05 for site clustering: required N ≥ 200 subjects per model with ≥3 visits each, design-effect-adjusted to N ≈ 490 across ≥6 base models. ADNI provides ~1,500 subjects with ≥3 visits — meets criterion comfortably. **C-statistic precision check** (Riley 2021 §4.3): target SE(C) ≤ 0.025 for stage-transition discrimination at anticipated AUC = 0.78 (per Salemme 2025 MCI→AD baseline) and 30% event proportion requires ~500 subjects with ≥150 transition events — met.

**Aim 2 (OASIS-3 external validation):** Primary measure = per-model ΔcTCS between ADNI and OASIS-3, with target 95% CI half-width ≤ 0.03. Riley framework for external validation of continuous performance measure (Archer 2021 criterion 4 — calibration slope precision): assuming anticipated O/E miscalibration ratio between 0.85–1.15 with target SE(ln(O/E)) ≤ 0.08, and OASIS-3 event proportion ≈ 25% (AD/MCI subjects in 2,842 sessions), required N_OASIS-3 ≥ 360 subjects. OASIS-3 cohort = 1,378 participants / 2,842 MR sessions — meets criterion. **Per Riley 2024 BMJ §Box 1**, calibration precision is the binding criterion, not raw discrimination.

**Aim 3 (MIRIAD short-interval stability):** Primary measure = per-model deviation from cTCS = 1.0 on stable CN subjects. Riley framework for within-subject repeatability (continuous outcome with paired structure): target detect 5pp deviation from cTCS = 1.0 with power 0.85 at α = 0.05; within-subject visit-pair SD estimated from Malone 2013 *NeuroImage* 70:33-36 MIRIAD design paper variability bounds (test-retest CV ≈ 3–8% for cortical volume measures). N = 23 CN + 46 AD with 6 short-interval timepoints (2/6/14/26/38/52 weeks) per subject yields ~12 effective per-subject visit pairs; pooled effective N = 828 paired comparisons. Power 0.85 achieved.

**Aim 4 (Mediation analysis):** Primary measure = bias-corrected bootstrap mediation effect β_med = 0.10 SD per 0.1 ΔcTCS, justified by Salemme 2025 reversion-rate variance bounds. Per Fritz & MacKinnon 2007 *Psychological Science* 18:233-239 sample-size tables (bias-corrected bootstrap with B = 10,000): detecting β_med = 0.10 at power 0.80 requires N ≈ 280 subjects. Site clustering adjustment: design effect DE = 1 + (m̄ − 1)·ICC with m̄ = 30 visits/site, ICC range 0.01–0.10 (conservative midpoint 0.05, Jacobson & Berkman 2010 *Quality of Life Research* 19:533-541) → DE ≈ 2.45. Adjusted N ≈ 686. ADNI provides ~1,500 subjects across 60+ sites — overpowered even at ICC = 0.10. **Pre-registered fallback:** if ICC empirically exceeds 0.10 in pilot data, switch to hierarchical Bayesian mediation per Imai 2010 with site-level random effects.

**Aim 5 (Multi-disease portability):** Primary measure = cTCS difference ≥ 0.15 between best and worst model on a non-AD disease. Riley framework (Archer 2021 criterion 3, paired cluster bootstrap) with assumed within-disease cTCS SD ≈ 0.16 and ICC = 0.06: required N ≥ 95 subjects per disease with ≥3 visits. PPMI (2,000+ subjects with serial H&Y/MDS-UPDRS) — overpowered. RIDER Lung PET-CT (244 subjects with serial scans) — meets criterion. **Pre-specified downgrade rule:** if any disease cohort falls below N = 50 evaluable subjects, that arm demoted from statistical claim to "feasibility demonstration" — documented in OSF pre-registration.

### A.9 Robustness against publication bias

Pre-register on OSF before any model is scored on test data. Sensitivity analyses pre-specified across (a) NIA-AA 2018 vs AA 2024 rule packs, (b) clinical vs population transition priors (Salemme 2025), (c) strict irreversibility vs allowing 8.7% reversion, (d) Huber M-estimate vs mean, (e) AAL vs Brainnetome atlas for attribution, (f) scanner vendor and field strength stratification (per §B.4.5). Negative or null results published with same prominence as positive findings.

### A.10 Operational alert threshold derivation (methodology only — values empirically calibrated)

`temporalmetric` reports cTCS, pTCS, uTCS as continuous scores. For deployment use (e.g., ALZ-NET integration, ACR Assess-AI registry submission), operational alert thresholds are required to translate continuous scores into actionable categories ("review", "investigate", "stop"). Per **ACR-SIIM Practice Parameter for Imaging AI** (approved 5 May 2026), AI tools require "stop rules" — predefined performance bands below which the system is paused for investigation. Per the Larson 2025 *JACR* roadmap (DOI 10.1016/j.jacr.2025.02.008, PMID 40057886), these rules must be empirically derived, not pre-stated.

**Threshold derivation methodology (executed in Aim 1, NOT prefilled in spec):**

1. **Compute cohort cTCS distributions** across ≥6 ADNI base models with cluster-bootstrap 95% CIs (B = 10,000).
2. **Cross-reference with mediation analysis (Aim 4)** to identify the cTCS range where the mediation effect on ΔMMSE/ΔCDR-SB at 24 months reaches |β_med| ≥ 0.10 SD per 0.1 cTCS.
3. **Anchor on Threshold-Optimization (OT) methodology** per Threshold optimization in AI imaging (PMC12454861 2025) — define operational threshold τ such that:
   - cTCS < τ_high_alert → "high alert; case review recommended"
   - τ_high_alert ≤ cTCS < τ_review → "review; flag for follow-up"
   - cTCS ≥ τ_review → "low concern"
4. **Cross-validate** on OASIS-3 external (Aim 2) and MIRIAD short-interval (Aim 3); thresholds adjusted if external CIs do not overlap internal CIs.
5. **Clinician adjudication calibration** (per §B.5.2 Cohen's κ ≥ 0.6 target) — thresholds tuned to maintain false-alert burden below clinician-determined acceptability (target ≤ 15% false alerts at high-alert tier, per Kwong 2022 silent pilot reported on the DECIDE-AI checklist, §B.5.3).
6. **Conformal prediction wrapper** (per Conformal Triage methodology, medRxiv 2024.02.09.24302543) — provides distribution-free statistical guarantees on PPV/NPV at the chosen thresholds for site-specific patient populations.

**Specific threshold values (τ_high_alert, τ_review) are NOT predetermined in this spec.** They will be derived from Aim 1 data and reported in the methods paper with bootstrap CIs, OASIS-3 external validation, and ALZ-NET silent-deployment recalibration. Pre-stating specific cutoffs without empirical grounding would be hallucinated science and is explicitly disallowed by the spec's citation-locked rule discipline.

**Implementation in v0.1:** `temporalmetric.thresholds` module ships with `derive_thresholds()` function accepting a calibration set; produces YAML threshold file `thresholds_v1_calibration_<DATE>.yaml` with version stamp and bootstrap CIs. Users select threshold YAML at runtime; mismatched threshold-YAML/rulepack-YAML version combinations fail closed.

---

## B. Study Design

### B.1 Five aims

| Aim | Question | Primary endpoint | Cohort | Decision gate |
|---|---|---|---|---|
| 1 | Reliable scoring on ADNI? | cTCS/pTCS/uTCS with cluster-bootstrap 95% CI for ≥6 AD models | ADNI | ≥10pp spread → proceed |
| 2 | External replication? | Per-model ΔcTCS between ADNI and OASIS-3 | OASIS-3 (1,378 / 2,842 sessions) | Pattern preserved or portability gap identified — either publishable |
| 3 | Test-retest stress detection? | Per-model cTCS on MIRIAD short intervals | MIRIAD (46 AD + 23 CN / 708 scans; intervals 2/6/14/26/38/52wk + 18/24mo) | ≥1 model with cTCS<0.9 on short-interval CN → headline |
| 4 | Does cohort TCS predict cognition beyond AUC? | Mediation analysis ΔMMSE/ΔCDR-SB at 24mo | ADNI + OASIS-3 longitudinal cognition | p<0.01 mediation → primary claim validated |
| 5 | Multi-disease portability? | cTCS/pTCS/uTCS on PD (PPMI) AND oncology (RIDER Lung PET-CT, 244 subjects) using disease-specific rulepacks | PPMI + RIDER Lung PET-CT | Either disease shows interpretable TCS pattern → platform validated |

**Optional Aim 6:** ALZ-NET real-world treated-patient validation (deferred to v0.2). DAUR via alz-net.org/participate-alz-net, managed by ACR.

### B.2 Datasets (verified May 2026)

| Dataset | N / scans | Use | Access | Status |
|---|---|---|---|---|
| ADNI | ~2,400 subjects, multi-visit | AD train/bench | adni.loni.usc.edu | 4–6 wk DUA |
| OASIS-3 | 1,378 / 2,842 MR sessions | AD external | central.xnat.org | Verified open |
| MIRIAD | 46 AD + 23 CN / 708 scans, intervals 2-52 wk + 18/24 mo same scanner | AD test-retest | UCL portal | Verified open (Malone 2013 DOI 10.1016/j.neuroimage.2012.12.044) |
| AIBL | optional | AD secondary | aibl.csiro.au | Optional |
| ALZ-NET | 118 active clinical sites + 93 imaging centers; >3,600 enrolled patients (>600 receiving anti-amyloid); CTAD 3 Dec 2025 readout | AD real-world treated | DAUR via alz-net.org; CMS-approved CED study, managed by ACR | Newly opened Dec 2025 |
| PPMI | 2,000+ / 50 sites / 12 countries | PD portability | ppmi-info.org/access-data-specimens | Verified open; H&Y, MDS-UPDRS, DaTSCAN, MRI, DTI |
| RIDER Lung PET-CT | 244 longitudinal subjects | Oncology RECIST portability | TCIA (cancerimagingarchive.net) | Verified open (designed for therapy response evaluation) |
| RIDER Lung CT | 32 subjects, same-day repeat + longitudinal | Oncology test-retest secondary | TCIA DOI 10.7937/k9/tcia.2015.u1x8a5nr | Verified open |
| TCIA NSCLC-Radiomics (Lung1) | 422 NSCLC | Oncology baseline reference (pretreatment only — NOT longitudinal) | TCIA | Verified; supplementary only |

### B.3 Models to benchmark (verified May 2026)

| Model | Source | Status |
|---|---|---|
| ClinicaDL 2D_slice + 3D_patch + 3D_ROI, baseline + longitudinal, AD_CN + sMCI_pMCI | Zenodo 3491003 + aramislab.paris.inria.fr | Verified — primary public AD weights |
| Zhang 2025 L2C-FNN | github.com/ThomasYeoLab/CBIG/.../Zhang2025_L2CFNN + Standalone repo | Verified pretrained; DOI 10.1002/hbm.70280, PMC12315237 |
| Ouyang 2021 LP+consistency | github.com/ouyangjiahong/longitudinal-pooling | README-only; full reimplementation budgeted at 4 wk; LP-only fallback |
| Cho ICML 2024 AGT | PMLR 235:8593-8608 | Author code not verified public; reimpl if absent |
| Dao IEEE JBHI 2024 | DOI 10.1109/JBHI.2024.3472462 | Not verified; reimpl if absent |
| ResNet-3D / DenseNet-3D | torchvision / MONAI | Architecture only; train from scratch |
| TAMME MICCAI 2025 | Author code | Not verified; optional stretch |
| MONAI Model Zoo AD bundle | github.com/Project-MONAI/model-zoo | No dedicated AD classification bundle confirmed; contribute one as dissemination |

### B.4 Reporting compliance and trustworthy-AI framework alignment

#### B.4.1 Reporting standards

All reporting follows:
- **CLAIM 2024** — Tejani AS et al. *Radiology: Artificial Intelligence* 2024;6(4):e240300. DOI 10.1148/ryai.240300.
- **TRIPOD+AI** — Collins GS et al. *BMJ* 2024;385:e078378. DOI 10.1136/bmj-2023-078378.
- **STARD-AI** — Sounderajah V et al. *Nature Medicine* 2025;31(10):3283-3289. DOI 10.1038/s41591-025-03953-8.
- **DECIDE-AI** — Vasey B et al. *Nature Medicine* 2022;28(5):924-933. DOI 10.1038/s41591-022-01772-9.

Compliance verified by senior author before submission. Each checklist completed in supplementary materials with item-by-item annotation.

#### B.4.2 Trustworthy-AI framework alignment

`temporalmetric` is designed to operationalize three independent trustworthy-AI frameworks. Each principle in each framework maps to specific spec components, documented per framework checklist:

**FUTURE-AI** (Lekadir K et al. *BMJ* 2025;388:e081554, DOI 10.1136/bmj-2024-081554, PMID 39909534) — six principles: Fairness, Universality, Traceability, Usability, Robustness, Explainability. 117-expert consortium from 50 countries.
- *Fairness* → §B.4.4 subgroup audit panel + §B.4.5 scanner/vendor stratification.
- *Universality* → §B.6 multi-disease rule-pack registry + ADNI label translation layer.
- *Traceability* → §C.2 version-stamped citation-locked YAML rule packs; §C.3 audit_report_pdf_sha; rulepack_sha in all output JSON.
- *Usability* → §C.3 dashboard + Python CLI + Streamlit Cloud demo; §H.4 patient-facing trajectory dashboard.
- *Robustness* → §A.9 sensitivity matrix + §B.4.5 scanner stratification + §A.5 Huber M-estimator + cluster bootstrap.
- *Explainability* → §A.7 anatomical attribution (Grad-CAM + SHAP + AAL/Brainnetome aggregation).

**R-AI-DIOLOGY** (Haller S et al. *Neuroradiology* 2022, DOI 10.1007/s00234-021-02890-w, PMID 35098343) — 10-aspect neuroradiology-specific checklist. Highest relevance for ASFNR audience. Spec maps to each aspect: disease definition (§A.2 AA 2024 + TRAC), case selection (§B.2 datasets), reference standard (§B.5 ESNR-certified rater κ ≥ 0.6), data partitioning (§B.4.3 split discipline), modality and pre-processing transparency (rule-pack YAML), method validation (§B.1 five aims), uncertainty handling (uTCS + bootstrap), interpretability (§A.7), generalizability (§B.4.5 stress tests), ethics and regulation (§E).

**ACR-SIIM Practice Parameter for Imaging Artificial Intelligence** (approved by ACR Council 5 May 2026 at ACR 2026 Washington DC; joint ACR + Society for Imaging Informatics in Medicine). Operational alignment:
- AI governance group with clinical/technical/compliance leaders → §E.5 data governance.
- Inventory of AI tools with versions and intended use → `temporalmetric_version` + `rulepack_sha` in every output JSON (§C.3).
- Local acceptance testing before deployment → §B.5.3 silent-deployment phase.
- Real-world performance monitoring for drift with stop rules → §A.10 operational threshold derivation; conformal prediction wrapper.
- HIPAA privacy and security including strong access controls and logging → §E.5 data governance + audit_report_pdf_sha.

Companion sources: **Larson DB et al.** *JACR* 2025;22(5):586-592 — "The Road Map for ACR Practice Accreditation for Radiology Artificial Intelligence." DOI 10.1016/j.jacr.2025.02.008. PMID 40057886. **ACR Assess-AI registry** (first AI quality registry; launched June 2024, expanded May 2026). **ARCH-AI designation** (ACR Recognized Center for Healthcare-AI). `temporalmetric` is designed as one of the post-market monitoring tools that practices can use to fulfill ARCH-AI requirements.

#### B.4.3 Split discipline

Pre-registered on OSF before any model touches test data. Three split types pre-specified, all reported in publication:
- **Subject-level random split** (training/validation/test = 70/15/15) — primary.
- **Chronological split** (train on visits ≤ 2018-12-31, validate 2019-2021, test ≥ 2022) — temporal validation per Riley 2024.
- **Site-level held-out** (train on N-1 sites, test on Nth site, leave-one-site-out cross-validation) — geographic validation.

Splits are deterministic given seed; seeds locked in `experiments/seeds.yaml` with git commit hash.

#### B.4.4 Subgroup fairness audit panel

Per **FUTURE-AI Fairness principle** and **TRIPOD+AI item 19c** (subgroup performance), fairness is audited along seven dimensions for both the underlying base models and `temporalmetric` itself (does the audit metric disproportionately flag or miss errors in any subgroup?):

| Dimension | Strata | Source |
|---|---|---|
| Sex | M, F | All cohorts: demographic variable |
| Age band | 55–64, 65–74, 75–84, ≥85 | All cohorts: age at baseline |
| Race/ethnicity (where available) | NIH categories: White, Black/African American, Asian, Hispanic, Other | ADNI + OASIS-3 (limited diversity acknowledged); ALZ-NET silent pilot expected to broaden |
| Scanner vendor | Siemens, GE, Philips, Canon (formerly Toshiba) | DICOM `(0008,0070)` Manufacturer |
| Field strength | 1.5T, 3T | DICOM `(0018,0087)` MagneticFieldStrength |
| Disease stage at baseline | CN, MCI/EMCI/LMCI, AD-dementia (legacy); AA 2024 Stages 0–1, 2–3, 4–6 (primary) | NIA-AA 2018 → AA 2024 translation layer |
| Treatment status | None, anti-amyloid active, anti-amyloid discontinued | `treatment_status` input field |

Per-subgroup metrics reported: cTCS mean ± cluster-bootstrap 95% CI, pTCS log-likelihood, uTCS, flag rate, false-alert rate, INSUFFICIENT_DATA rate. **Equalized-odds disparity metric**: max(|cTCS_subgroup_i − cTCS_overall|) across all subgroups; pre-registered threshold for "fairness concern" = > 0.10 (i.e., any subgroup deviating > 10pp from overall cohort cTCS triggers documented fairness review). **Intersectional analysis**: sex × age × scanner_vendor (cells with N ≥ 20 reported).

Critically, this audit operates at **two levels** per FUTURE-AI Fairness §3.4:
1. Whether the underlying base model is unstable in particular subgroups (input audit).
2. Whether `temporalmetric` itself produces systematically different audit scores in those same subgroups (metric audit).

Both levels reported. If `temporalmetric` is itself biased (level 2), this is a finding to publish honestly, not to suppress.

#### B.4.5 Scanner/vendor and interval-length stress tests

Per FUTURE-AI Robustness + Universality principles, sensitivity matrix is factorial:

| Stress dimension | Strata | Pre-specified pass criterion |
|---|---|---|
| Scanner vendor | Siemens × GE × Philips × Canon | Max pairwise ΔcTCS across vendors ≤ 0.08 |
| Field strength | 1.5T × 3T | ΔcTCS between 1.5T and 3T ≤ 0.05 |
| Interval length | Short (<6mo), Medium (6–18mo), Long (>18mo) | Per-bin cTCS reported; no pre-specified threshold (descriptive) |
| Acquisition protocol | T1 MPRAGE vs T1 SPGR vs T1 FFE | Per-protocol cTCS reported |
| Slice thickness | ≤1.2mm vs >1.2mm | ΔcTCS ≤ 0.05 |
| Resampling/registration pipeline | FreeSurfer 7.x vs FastSurfer vs SynthSeg | ΔcTCS ≤ 0.05 |

Any pre-specified threshold breach → documented in published sensitivity supplement; does not invalidate primary findings but must be reported transparently per CLAIM 2024 item 25c.

### B.5 Human review and clinical validation pipeline

#### B.5.1 Adjudication structure

Two ESNR-certified neuroradiologists (Maruf + external EU collaborator, recruited via ESNR-BRACCO network) rate 50–100 high-penalty flips on 3-point clinical-plausibility scale (1 = clinically implausible, 2 = uncertain, 3 = clinically plausible given context). Stratified sampling: 50% high-penalty flips, 25% borderline, 25% low-penalty controls (blinded to category). $200/rater honorarium budgeted per case batch.

#### B.5.2 Agreement metrics

Cohen's quadratic-weighted κ with bootstrap CI (B = 10,000). Pre-registered targets:
- κ ≥ 0.6 (substantial agreement, Landis & Koch 1977) — primary criterion.
- κ ≥ 0.4 (moderate) — minimum acceptable; below this, taxonomy revisited.
- Disagreements adjudicated by third senior reader (recruited if κ < 0.6).

#### B.5.3 Silent-deployment phase (Kwong 2022 silent-trial methodology, DECIDE-AI reporting checklist)

Per the silent-trial methodology of **Kwong et al.** (*Front Digit Health* 2022;4:929508, PMID 36052317, CC-BY 4.0), the framework runs in silent mode at ≥2 deployment sites before any claim of clinical decision impact. Silent mode = system computes scores in real time on actual incoming AD AI predictions; outputs are logged but NOT shown to clinicians and do NOT influence any clinical decision. Verbatim from Kwong 2022: "the silent trial… evaluates the proposed model on patients in real-time, while the end-users (i.e., clinicians) are blinded to predictions such that they do not influence clinical decision-making." Reporting follows **DECIDE-AI** (Vasey 2022 *Nat Med* 28:924-933, PMID 35585196), a single-stage reporting guideline for early-stage clinical evaluation of AI decision-support systems; DECIDE-AI itself defines no Stage A/B/C labels (per ERRATA notice in docs/transcription_audit/v1.7_frameworks.md).

**Sites:** KIUT (primary, Maruf-led) + 1 EU site recruited via ESNR-BRACCO network (target: Munich Klinikum rechts der Isar or Karolinska — relationships under exploration). ALZ-NET integration explored as a post-silent-trial extension (post-CMS-approved CED).

**Window:** W17–W20 of the 21-week timeline (4 weeks before ASFNR Newport Beach Oct 2026); extended through Q1 2027 for FDA Q-Sub data package.

**Logged endpoints (per Kwong 2022 silent-trial themes — dataset drift, bias, feasibility, stakeholder attitudes — reported on the DECIDE-AI 17-item checklist):**
- Alert frequency per 100 serial cases (target benchmark from Aim 1 results)
- Expert-adjudication confirmation rate of flagged cases (target ≥ 60% — i.e., when `temporalmetric` flags, expert agrees ≥60% of the time)
- Time-to-quality-review per flagged case
- False-alert burden (clinician-rated; target ≤ 15% at high-alert tier)
- INSUFFICIENT_DATA rate in real-world data (vs ADNI's curated environment)
- Operational burden — wall-clock time, compute cost, IT integration effort
- System reliability — uptime, fail-closed rate, error logs

**Stop rules (per ACR-SIIM Practice Parameter):**
- If false-alert burden > 30% sustained over 4 consecutive weeks → pause and recalibrate thresholds (§A.10).
- If INSUFFICIENT_DATA rate > 25% sustained → revisit data quality requirements; flag as deployment-readiness concern in publication.
- If wall-clock time > 30 min per cohort report (target ≤ 5 min) → infrastructure review.

**No clinical decisions changed during the silent-deployment phase.** This is the regulatory and ethical boundary: silent-deployment data informs the subsequent prospective workflow-study phase (planned post-publication, after ALZ-NET formal agreement; corresponds to Kwong 2022 stage 3 "prospective clinical evaluation"), NOT immediate care.

#### B.5.4 Conformal prediction wrapper (optional, v0.2)

Per Conformal Triage methodology (medRxiv 2024.02.09.24302543), `temporalmetric.conformal` module wraps cTCS/pTCS/uTCS outputs with distribution-free PPV/NPV guarantees calibrated on a representative site-specific dataset. Allows the system to abstain on the most uncertain cases. Ships as `v0.2`; v0.1 reports raw scores only with bootstrap CIs.

### B.6 Multi-disease rule-pack registry

The library exposes an abstract `RulePack` API. Every disease lives at `temporalmetric/rules/<disease>/<framework>.yaml` with mandatory fields: `state_space`, `state_descriptions`, `admissible_transitions` (with min/max Δτ), `transition_priors`, `citation_pmid` or `citation_doi` for every rule, `ruleset_version`, `effective_date`, `clinician_author`, `override_allowed`, `notes`. Loading fails closed on any missing field or citation.

| Disease | Framework | State space | Reversion | Anchor citation |
|---|---|---|---|---|
| **AD v1.0 PRIMARY (NeuroTCS launch v0.1)** | **AA 2024 + TRAC** | **Biological Stages 0–6 + clinical staging** | **Monotone biological except under TRAC; clinical bounded by copathology** | **Jack 2024 Alz Dem 20:5143-5169, DOI 10.1002/alz.13859, PMID 38934362; La Joie 2025 Alz Dem 21:e70997, DOI 10.1002/alz.70997 (TRAC)** |
| AD v0.x LEGACY | NIA-AA 2018 | CN/MCI/AD | MCI→CN with population flag | Jack 2018 PMID 29653606 |
| PD | Hoehn-Yahr + MDS-UPDRS | H&Y 1, 1.5, 2, 2.5, 3, 4, 5 | No (monotone) | Hoehn & Yahr 1967 Neurology 17:427-442; Goetz 2008 Mov Dis 23:2129-2170 |
| MS | McDonald 2024 + EDSS | EDSS 0–10 + relapse | Allowed (RRMS) | Montalban 2025 Lancet Neurology 24:850-865, DOI 10.1016/S1474-4422(25)00270-4; Kurtzke 1983 Neurology 33:1444-1452 |
| Oncology solid | RECIST 1.1 | CR/PR/SD/PD | CR→PR/SD allowed; PD absorbing | Eisenhauer 2009 EJC 45:228-247, DOI 10.1016/j.ejca.2008.10.026, PMID 19097774 |
| Oncology immunotherapy | iRECIST | iCR/iPR/iSD/iUPD/iCPD | iUPD→iSD/iPR (pseudoprogression) | Seymour 2017 Lancet Oncol 18:e143-e152, DOI 10.1016/S1470-2045(17)30074-8, PMID 28271869 |
| Stroke | modified Rankin Scale | mRS 0–6 | 30/90/180/365d expected | Banks & Marotta 2007 Stroke 38:1091-1096 |
| Lung nodule | Fleischner 2017 | Size + doubling-time bins | Monotone growth | MacMahon 2017 Radiology 284:228-243, DOI 10.1148/radiol.2017161659 |

**Production status:** v0.1 ships **AD AA 2024 (Jack 2024) as primary** + TRAC handling (La Joie 2025) + NIA-AA 2018 legacy compatibility + ADNI translation layer, all in production. Schema-validated YAML skeletons ship for PD, MS, oncology, stroke, lung nodule. v0.2 (Q1 2027) ships PD, MS (McDonald 2024), oncology RECIST 1.1, stroke, lung nodule — each with optional disease-specialist sign-off via the schema's `reviewers` field (additive and non-blocking; clinical authority resides in the cited published guideline per §B.6, not in a co-author signature). v0.3+ extends to prostate (Epstein), diabetic retinopathy (ETDRS), NYHA heart failure, METAVIR liver fibrosis, RANO neuro-oncology, BI-RADS longitudinal breast.

---

## C. Architecture

### C.1 Three layers

- **Layer 1**: `temporalmetric` Python library (pip, Apache-2.0, ~400–800 LOC core).
- **Layer 2**: `tcs-benchmark` public repo with multi-disease leaderboard.
- **Layer 3**: FastAPI + Streamlit/React dashboard on Railway.

### C.2 File structure

```
temporalmetric/
├── pyproject.toml                  # Apache-2.0, python>=3.10
├── README.md                       # EN/RU/UZ
├── CITATION.cff                    # cited as Salokhiddinov 2026, Zenodo DOI reserved
├── temporalmetric/
│   ├── __init__.py                 # __version__ = "0.1.0"
│   ├── core/{ctcs,ptcs,utcs,bootstrap,huber,version_stamp}.py
│   ├── rules/
│   │   ├── schema.py               # Pydantic; fails closed on missing citation
│   │   ├── registry.py
│   │   ├── ad/
│   │   │   ├── aa_2024.yaml         # v0.1 PRIMARY — Jack 2024 PMID 38934362
│   │   │   ├── aa_2024_trac.yaml    # v0.1 PRODUCTION — TRAC extension, La Joie 2025
│   │   │   ├── adni_translation.yaml # v0.1 PRODUCTION — NIA-AA 2018 → AA 2024 mapping
│   │   │   └── niaaa_2018.yaml      # v0.1 LEGACY — Jack 2018 PMID 29653606
│   │   ├── pd/hoehn_yahr.yaml                   # v0.2
│   │   ├── ms/mcdonald_2024.yaml                # v0.2 — Montalban 2025
│   │   ├── oncology/{recist_1_1,irecist}.yaml   # v0.2
│   │   ├── stroke/mrs_followup.yaml             # v0.2
│   │   └── lung_nodule/fleischner_2017.yaml     # v0.2
│   ├── priors/{salemme_2025,wang_2023,salazar_2010}.yaml
│   ├── attribution/{gradcam,shap_wrapper,aal_aggregation}.py
│   ├── io/{csv_loader,json_api,pdf_report}.py
│   ├── failclosed.py
│   ├── cards/                      # Model Card + Data Sheet templates (Mitchell 2019, Gebru 2018)
│   │   ├── model_card_template.md
│   │   └── data_sheet_template.md
│   └── cli.py
├── tests/{unit,integration,regression,property}/
├── docs/                           # Sphinx + ReadTheDocs
└── .github/workflows/{ci,release}.yml
```

### C.3 Layer 2 — `tcs-benchmark`

```
tcs-benchmark/
├── leaderboard.md                  # auto-updated multi-disease
├── models/{ad,pd,oncology,ms}/
├── runners/                        # ADNI / OASIS-3 / MIRIAD / PPMI / RIDER harness
├── results/                        # signed JSON, model hash + commit
└── notebooks/                      # reproducible reports
```

### C.4 Layer 3 — Dashboard

FastAPI Python 3.11 on Railway + PostgreSQL + S3-compatible object store for de-identified prediction CSVs. Auth0/Clerk auth. HIPAA-ready posture (BAA placeholder). Streamlit MVP for ASFNR Oct 2026; React v0.2.

### C.5 I/O schema

**Input CSV:**
```
subject_id,visit_date,model_pred,p_state_1,...,p_state_K,uncertainty,treatment_status,amyloid_centiloid
S001,2024-01-15,Stage_2,0.10,0.70,0.20,0.12,none,85.0
S001,2024-07-12,Stage_3,0.05,0.20,0.75,0.08,anti_amyloid_active,42.0
S001,2025-01-15,Stage_3,0.10,0.30,0.60,0.10,anti_amyloid_active,18.0
```

`treatment_status` ∈ {`none`, `anti_amyloid_active`, `anti_amyloid_discontinued`} — required for TRAC handling. Falls back to non-TRAC rules if absent.

`amyloid_centiloid` — optional numeric Centiloid value; used for TRAC classification (full TRAC < 11 CL; partial TRAC = significant drop above threshold per La Joie 2025).

**JSON API output (version-stamped):**
```json
{
  "temporalmetric_version": "0.1.0",
  "rulepack": "ad/aa_2024_trac",
  "rulepack_sha": "ab12cd34...",
  "legacy_translation_applied": true,
  "translation_source": "adni_niaaa_2018",
  "prior": "ad/salemme_2025_clinical",
  "n_subjects": 412,
  "n_subjects_anti_amyloid_treated": 38,
  "n_subjects_full_trac": 12,
  "n_subjects_partial_trac": 9,
  "n_visits": 1847,
  "cTCS": {"mean": 0.812, "ci95": [0.793, 0.829], "huber": 0.815},
  "pTCS": {"mean": -0.41, "ci95": [-0.47, -0.36]},
  "uTCS": {"mean": 0.79, "ci95": [0.77, 0.81]},
  "flagged_flips": 38,
  "flagged_flips_excluding_trac": 31,
  "insufficient_data_subjects": 6,
  "biomarker_incomplete_subjects": 24,
  "timestamp_utc": "2026-10-09T14:22:11Z",
  "audit_report_pdf_sha": "ef56gh78..."
}
```

### C.6 Engineering discipline

1. Evidence-locked YAML; Pydantic-validated; fails closed on missing citation.
2. Fail-closed on missing timestamps, Tᵢ<2, NaN probabilities → INSUFFICIENT_DATA.
3. Version-stamped: library + rulepack + prior + git commit SHA on every output.
4. Deterministic numerical code; no LLM in clinical scoring path.
5. Clinical rules NEVER inferred from model output.

### C.7 Testing

- Unit: ≥80% coverage.
- Integration: synthetic shards with known ground-truth TCS.
- Regression: pinned outputs for fixed inputs.
- Property-based (Hypothesis): cTCS ∈ [0,1]; pTCS monotone; uTCS ≤ cTCS for w ∈ [0,1].
- Fuzzing: malformed CSV / NaN → INSUFFICIENT_DATA, never crash.

### C.8 Documentation and dissemination

- ReadTheDocs auto-built per tag.
- Jupyter quickstarts: ADNI / OASIS-3 / MIRIAD / PPMI / RIDER Lung PET-CT / ALZ-NET (v0.2) / RECIST iRECIST (v0.2).
- GitHub Actions CI: pytest + ruff + mypy + bandit + Sphinx + PyPI auto-publish on tag.
- Multi-language READMEs: English (primary), Russian, Uzbek.
- Hugging Face Space: `temporalmetric/audit-demo` for community submissions.

### C.9 Pre-reserved DOI and citation

- Zenodo reserved DOI: register `temporalmetric` repo on Zenodo on day 1; reserve a v0.1.0 DOI before any code commit so the manuscript can cite the released version. Action item: Zenodo → GitHub integration set up at https://zenodo.org/account/settings/github/ during week 1.
- CITATION.cff generated with reserved DOI placeholder; replaced with final DOI on tag.
- JOSS submission (Journal of Open Source Software) planned in parallel — joss.theoj.org accepts open-source research software with peer review and a citable DOI.
- Model cards and data sheets: every rulepack and every benchmark dataset adapter gets a one-page Model Card (Mitchell et al. 2019, FAT* '19, "Model Cards for Model Reporting") and Data Sheet (Gebru et al. 2018, arXiv 1803.09010, "Datasheets for Datasets"). Templates ship in `temporalmetric/cards/`.

---

## D. Execution Timeline — Week-by-Week

ASNR Austin 17–20 May 2026 → ASFNR Newport Beach 9–12 Oct 2026 (21 weeks).

**Pre-W1 (at and just after ASNR Austin):**
- OSF preregistration drafted (full statistical plan, transition matrices, all primary endpoints, sample size justifications per §A.8).
- ADNI, OASIS-3, MIRIAD, PPMI DUAs filed in parallel.
- KIUT IRB exemption requested (de-identified secondary data).
- TCIA registration for RIDER Lung PET-CT.
- Collaborators recruited at ASNR Austin: biostatistician (US), second neuroradiologist, PD specialist (W12 target), oncology radiologist (W12 target).
- PyPI name `temporalmetric` reserved; GitHub orgs `temporalmetric` and `tcs-benchmark` locked.
- Zenodo DOI reserved.
- US patent counsel engaged for provisional filing within 8 weeks.

**Weeks 1–4 — Library build:**
- W1: skeleton repo, CI/CD, Pydantic schemas, fail-closed scaffolding, abstract `RulePack` API designed for multi-disease from day one. Run `python -m monai.bundle list` to confirm no AD bundle exists.
- W2: cTCS + **AA 2024 YAML + TRAC extension YAML + ADNI translation layer + NIA-AA 2018 legacy YAML** + unit tests; PD/MS/oncology/stroke/lung-nodule YAML skeletons committed as schema-validated placeholders.
- W3: pTCS (matrix exponential, time-aware) + Salemme 2025 prior YAML + tests.
- W4: uTCS + cluster bootstrap + Huber M-estimate + first integration test on synthetic data. **Gate G1: v0.1.0 tagged with reserved Zenodo DOI; ≥80% coverage; regression suite green.**

**Weeks 5–8 — ADNI benchmark + Ouyang reimpl:**
- W5: ADNI ingest; ClinicaDL baseline + longitudinal weights loaded.
- W6: Zhang 2025 L2C-FNN reproduction; ResNet-3D / DenseNet-3D trained.
- W7–8: Ouyang 2021 LP+consistency reimplementation; LP-only fallback if slipping. **Gate G2: ≥6 models scored on ADNI with bootstrap CI; ≥10pp cTCS spread.**

**Weeks 9–12 — OASIS-3 external validation:**
- W9: OASIS-3 ingest; FreeSurfer features parsed.
- W10: Rescore every model on OASIS-3; ΔcTCS table.
- W11: pTCS sensitivity (clinical vs population priors; NIA-AA 2018 vs AA 2024).
- W12: uTCS analysis; disease-specialist `reviewers` field populated for v0.2 rulepacks (additive sign-off per §B.6).

**Weeks 13–16 — MIRIAD test-retest stress test:**
- W13: MIRIAD ingest; visit alignment.
- W14: All models scored on MIRIAD across all 8 intervals.
- W15: GradCAM/SHAP on top 50 flips.
- W16: AAL atlas aggregation; regional flip signature figure. **Gate G3: short-interval flip rate > expected baseline → headline.**

**Weeks 17–20 — saliency / mediation / human review / multi-disease portability / silent deployment:**
- W17: Mediation analysis on ADNI + OASIS-3 (R `mediation`). **Silent-deployment phase launched** at KIUT + 1 EU site (per §B.5.3, Kwong 2022 silent-trial methodology); logging endpoints active.
- W18: Two-rater human review; Cohen's κ. Silent deployment continuing; weekly alert-frequency reports.
- W19: Aim 5 multi-disease portability — PPMI ingest, score ≥1 published PD AI classifier with PD rulepack; RIDER Lung PET-CT ingest, score with RECIST 1.1 rulepack. Goal: supplementary figures. Silent deployment week 3.
- W20: Sensitivity analyses, final figures, supplements. Silent deployment week 4: interim report on false-alert burden, INSUFFICIENT_DATA rate, operational metrics. Subgroup fairness audit panel results compiled (§B.4.4). Stress test matrix complete (§B.4.5). **Gate G4: silent deployment without stop-rule breach + κ ≥ 0.6 + fairness audit no breach > 0.10 → submission-ready.**

**Weeks 21–22 — Manuscript and submission:**
- W21: Nature Medicine draft. Lancet Digital Health backup cover letter prepared. Silent deployment continuing in background (extends through Q1 2027 for FDA Q-Sub data package).
- W22: Internal review (≥4 readers); Nature Medicine submission; ASFNR Newport Beach poster + oral.

**Parallel workstreams (Maruf-led):**
- W5+: Layer 3 dashboard built on Railway, ready for ASFNR live demo.
- W10+: FDA Q-Sub draft started for Q1 2027 filing.
- W12+: Provisional patent filing with broad claims.
- W17+: Silent-deployment phase (Kwong 2022 silent-trial methodology, DECIDE-AI reporting) per §B.5.3; runs through Q1 2027 for FDA data package.

**Buffer**: 2 weeks float distributed across W3, W7, W14, W19.

---

## E. Regulatory and Commercial Track

### E.1 FDA Q-Submission

Cost $0. eCopy + cover letter via CDRH portal; 3 proposed meeting dates. FDA confirms within 15 calendar days; written feedback within 70 calendar days per Q-Sub Final Guidance 29 May 2025.

Five specific questions to file:

1. Is `temporalmetric` — open-source audit library not making per-patient diagnostic claims — a device under 21 USC 360c, or within the CDS carve-out of 21st Century Cures Act §3060?
2. If device, confirm Class II De Novo pathway under §513(f)(2) is appropriate, with new product code, given no predicate exists.
3. Confirm PCCP framework (Final Guidance 4 Dec 2024) is the appropriate mechanism for updating clinical rulepacks (AA 2024 → future Alzheimer's Association revisions; TRAC framework updates as anti-amyloid evidence base evolves; McDonald 2024 → future revisions; RECIST 1.1 → future revisions).
4. Advise on Special Controls — version-stamping, citation-locked YAML, fail-closed determinism, labeled use limited to aggregate model monitoring.
5. Confirm real-world post-market data from ALZ-NET (CMS-approved CED via ACR) is acceptable PCCP impact-assessment data.

### E.2 PCCP alignment

FDA Final PCCP Guidance 4 Dec 2024 + August 2024 PCCP general guidance + FDORA 2022 §515C (21 USC 360e-4) + August 2025 multinational guiding principles (FDA + Health Canada + UK MHRA) + FDA OSEL active post-market monitoring program give `temporalmetric` a clear regulatory home.

Sivakumar 2025 (JAMA Network Open, PMC12595527) is the verified source for AI/ML clearance gap quantification: across 950 FDA-authorized AI/ML devices through June 2024, only 5% had prospective testing, 8% had human-in-the-loop validation, 29% had any clinical testing. Cumulative FDA AI/ML-authorized devices reached 1,451 by December 2025 (1,104 radiology) per Bipartisan Policy Center analysis Nov 2025. CMS pays for only ~10. These are the verified gap numbers.

PCCP for this product covers: rulepack version updates (AA 2024 → future Alzheimer's Association revisions; TRAC framework updates; McDonald 2024 → future revisions; RECIST 1.1 → future revisions), legacy rulepack maintenance (NIA-AA 2018 retained for backward compatibility), new disease rulepack additions, prior calibration updates, atlas additions. Impact assessment: predefined bounds on cohort cTCS shift (Δ > 0.05 → new submission required).

### E.3 De Novo Class II pathway

No predicate exists across the 1,451 FDA AI/ML-authorized devices through Dec 2025. Babic et al. 2025 (npj Digital Medicine 8:328, DOI 10.1038/s41746-025-01717-9) explicitly identifies the post-market surveillance gap that `temporalmetric` fills.

Proposed Special Controls: (i) mandatory version-stamping, (ii) citation-locked YAML rules, (iii) fail-closed on insufficient data, (iv) labeled use limited to aggregate model monitoring — never per-patient diagnosis.

### E.4 EU AI Act and CE-MDR pathway

EU AI Act (Regulation 2024/1689) entered into force August 2024 with phased application; high-risk medical AI provisions began applying in stages from February 2025, with full application by August 2026. Under the AI Act, `temporalmetric` is a high-risk AI system when used as a safety component of a medical device — requires conformity assessment, technical documentation, post-market monitoring, transparency, human oversight, accuracy/robustness/cybersecurity requirements per Annex III.

Under EU MDR (Regulation 2017/745), `temporalmetric` is Class IIa Software as Medical Device under Rule 11 (intended to provide information used to make decisions for diagnostic or therapeutic purposes). Conformity assessment via Notified Body (BSI, TÜV SÜD, DEKRA candidates). CE mark required for EU market.

Strategic positioning: file FDA Q-Sub first (Q1 2027), use response to inform CE-MDR Technical File preparation (Q3 2027), submit to Notified Body Q4 2027–Q1 2028. EU customers (icometrix Belgium, QuantiB Netherlands, Combinostics Finland) cannot purchase without CE mark.

### E.5 Data governance architecture

**Library (Layer 1) — no data movement.** Library is installed locally; processes only de-identified per-visit prediction CSVs that never leave the user's environment. No PHI by design. Open-source under Apache-2.0; no governance burden on library distribution.

**Benchmark (Layer 2) — researcher-controlled.** ADNI/OASIS-3/MIRIAD/PPMI/RIDER data accessed via user's own DUAs; benchmark code in public repo, runs on user's infrastructure. No data uploaded to GitHub or Hugging Face beyond aggregate, de-identified TCS scores.

**Dashboard (Layer 3) — SaaS posture, three regimes:**

| Regime | Jurisdiction | Posture | Mitigation |
|---|---|---|---|
| US clinical sites | HIPAA + state laws | BAA-ready; SOC 2 Type I roadmap; Railway US region | Accept only de-identified predictions; no raw images; no PHI; encrypt at rest + in transit |
| EU clinical sites | GDPR + national supplements | Data processor under Art. 28 DPA; SCC for any non-EU transfer; Railway EU region (Amsterdam) or migrate to OVH/Scaleway | Data minimization; right to erasure honored; DPIA conducted before EU launch |
| Uzbekistan | Law ZRU-547 "On Personal Data" (effective Oct 2019, amended 2021) | Cross-border data transfer requires explicit consent or adequacy determination; data localization for sensitive health data | Maintain copy of any Uzbek patient predictions in-country; obtain consent for cross-border processing |

Pre-launch action items: (1) draft Data Processing Agreement template, (2) GDPR DPIA template ready, (3) Uzbekistan ZRU-547 compliance review with local counsel, (4) HIPAA Security Risk Assessment before any clinical pilot.

### E.6 IP strategy

Provisional patent (USPTO), broad claims with AD as worked example:

1. Time-aware Markov transition penalty using matrix exponential of clinically-constrained generator Q for longitudinal medical AI of any state-bearing disease, with versioned citation-locked rulepack.
2. Uncertainty-weighted temporal coherence extending Thulasidasan-style OE to transitions.
3. Versioned, hash-stamped, citation-locked clinical rule-pack registry as regulatory-grade rule management.
4. Method of auditing per-patient longitudinal AI prediction trajectories with anatomical/feature attribution.

File provisional within 8 weeks (before public disclosure including OSF preregistration). Counsel options: Cooley / Wilson Sonsini / Fenwick / Tashkent-linked US patent counsel. Budget: $3–5K provisional, $25–40K non-provisional within 12 months, $15–25K PCT international filing within 12 months for EU/Japan/China. Apache-2.0 on open-source library is patent grant-back compatible (§3); commercial SaaS licenses negotiated per-customer.

### E.7 Investor pitch

**Thesis**: `temporalmetric` is the post-hoc temporal coherence audit layer for every longitudinal medical AI device — wedge in AD where ARIA monitoring and anti-amyloid eligibility create urgency, expanding to oncology RECIST, stroke mRS, MS EDSS + McDonald 2024, PD Hoehn-Yahr, lung nodule Fleischner. Closes the post-market monitoring gap FDA PCCP demands and CMS coverage conditions on.

**Novelty claim (precision-tuned for Nature Medicine review)**: To our knowledge, `temporalmetric` is the first post-hoc, model-agnostic temporal coherence audit framework operating at the **per-patient trajectory level** with a citation-locked clinical rule-pack registry across multiple diseases. Adjacent prior art exists at the **cohort-drift validation level** (Schuessler et al. 2025, Communications Medicine, oncology ACU prediction) and at the **brain MRI registration level** (Jian et al. 2025 TimeFlow, longitudinal deformation fields for aging analysis), but neither addresses per-patient clinical-plausibility audit of classification outputs across visits with versioned, citation-locked clinical rules. Training-time methods (Ouyang 2021 LP+consistency, Cho ICML 2024 AGT, Yang 2025 MM-DURA) enforce temporal behavior during model training rather than auditing trained models post hoc. The defendable novelty has three layers: (a) post-hoc model-agnostic per-patient trajectory audit, (b) citation-locked YAML rule-pack registry as regulatory-grade rule management, (c) disease-agnostic platform architecture validated on AD with portability demonstrated across PD and oncology.

**Why now**: FDA Final PCCP 4 Dec 2024 + FDORA §515C + August 2025 multinational guiding principles + EU AI Act phased application 2025–2026 + ALZ-NET data access opened Dec 2025 + McDonald 2024 (Montalban 2025 Lancet Neurology) just published + CMS coverage gap (only ~10/1,451 reimbursed) + FDA OSEL active post-market monitoring research program.

**TAM methodology (bottom-up):**
- AD beachhead: ~1,104 FDA-cleared radiology AI devices × estimated 20% with longitudinal AD-relevant use cases × $50K/device/year QA SaaS = ~$11M near-term; plus ~118 ALZ-NET clinical sites × $40K/site/year audit subscription = ~$4.7M; plus anti-amyloid monitoring services market (~$150M by 2028 per industry analyst aggregates) — addressable wedge ~$200M.
- Neuro expansion (AD + PD + MS + stroke): ~6× AD-only addressable based on prevalence × device-count ratios across these four conditions in FDA AI/ML database — ~$1.2B.
- Multi-specialty platform (+ oncology RECIST + lung nodule + cardiac + ophth): ~25× AD-only based on the same ratio applied across the broader 1,104 radiology AI devices and adjacent specialty AI in cardiology, ophthalmology, pathology — ~$5B+ at maturity.

These are wedge → platform reasoned estimates anchored to the verified FDA-cleared device count (1,451 cumulative through Dec 2025; 1,104 radiology) and CMS reimbursement ratio (~10/1,451). Investors will scrutinize; bottom-up market sizing methodology documented for diligence.

**Target investors**: a16z bio (Pande digital health thesis), GV (Verily relationship), Anthropic Health (AI-safety framing for clinical AI), Khosla Ventures, Pillar VC, Lux Capital, Section 32 (Foley medical-AI focus), Civilization Ventures. Strategic CVCs later: GE HealthCare Ventures, Siemens Healthineers Ventures, Bayer Leaps.

**Beachhead market (year 1)**: 10–15 imaging AI vendors with longitudinal use cases — icometrix, Cortechs.ai, QuantiB, Combinostics, Riverain, Aidence, Optellum, Subtle Medical, Rad AI, Aidoc. Secondary: 20 academic medical centers with AI governance committees (MGB, Stanford, Mayo, Cleveland Clinic, Duke, Hopkins, Penn, Michigan, UCSF, MD Anderson, MSK, Dana-Farber). Tertiary: regulators (FDA CDRH, MHRA, Health Canada) and HTA bodies (NICE) as enterprise users.

**Seed ask**: $2–3M for 18 months.

**Use of funds:**
- 2 ML engineers (US-comp): $480K
- 1 clinical lead (Maruf): $150K
- 4 disease-specialist consultants (PD, MS, oncology, stroke rulepack `reviewers` field sign-off; additive per §B.6): $80K total
- Regulatory consultant retainer (Hogan Lovells health or Ropes & Gray FDA practice): $30–60K focused Q-Sub engagement; $150–250K full De Novo submission package — budget $200K
- Regulatory affairs / quality systems lead (part-time, year 2): $80K
- EU MDR Notified Body fees + Technical File preparation: $80–120K
- Patent (US provisional + non-provisional + PCT): $50–70K
- GPU compute (Lambda Labs / AWS spot): $50K
- Legal (formation, contracts, DPA templates, ZRU-547 review, Uzbek counsel): $40K
- Clinical validation site (1 pilot site for prospective DECIDE-AI study): $150K
- Contingency 10%: $130K

Total: ~$1.5M; remainder of $2-3M seed for operational runway + sales/BD year 2.

**Defensibility**: (a) Citation-locked, hash-stamped rule-pack registry; (b) FDA De Novo Class II with new product code (no predicate); (c) broad patent on time-aware kernel + uncertainty-weighted temporal coherence + rulepack architecture; (d) clinical reviewer network of disease specialists (additive sign-off via the schema's `reviewers` field; per §B.6 clinical authority lives in the cited published guideline); (e) 18-month head start in a niche requiring deep neuroradiology + ML + regulatory expertise — Maruf is one of a small set of people combining all three.

### E.8 Competitive intelligence

| Company / Project | Scope | Differentiator vs `temporalmetric` |
|---|---|---|
| CheXstray (Stanford 2022) | Drift detection on chest X-ray | Population drift, single modality, no temporal coherence, no clinical rule grounding |
| MMC+ medical imaging AI monitoring (arXiv 2410.13174 Oct 2024) | Foundation-model-based drift detection | Population drift on inputs, not per-patient temporal coherence on outputs |
| **Schuessler et al. 2025 (Commun Med 5:261, DOI 10.1038/s43856-025-00965-w, PMID 40596645)** | **Model-agnostic diagnostic framework to validate clinical ML models on time-stamped data; demonstrated in oncology ACU prediction on 24,000+ patients from EHR 2010–2022; Stanford Hernandez-Boussard group** | **Operates at the cohort/population temporal drift level (training vs validation cohorts over years, feature distribution shifts); we operate at the per-patient trajectory plausibility level with versioned clinical rule packs. Different unit of analysis. Complementary, not overlapping.** |
| **Jian et al. 2025 TimeFlow (arXiv 2501.08667; IEEE TMI 2025/2026)** | **Temporal conditioning for longitudinal brain MRI registration; U-Net + temporal conditioning estimating deformation fields between two scans, with future-state extrapolation; Wachinger group, TUM** | **Image registration task (deformation fields), not classification output audit. Operates on raw images; we operate on per-visit prediction outputs. Different task entirely.** |
| AUDIT (Aumente-Maestro, Cabezas et al. 2025, DOI 10.1016/j.cmpb.2025.108991, PMID 40795618) | Open-source Python library for AI segmentation model evaluation, with use cases in MRI brain tumor segmentation. Computer Methods and Programs in Biomedicine 271:108991 | Single-timepoint segmentation evaluation, not longitudinal trajectory audit; naming collision avoided by `temporalmetric` name |
| MONAI ecosystem | Model packaging + segmentation | Complementary; we contribute a MONAI bundle as dissemination |
| Rad AI (private, US) | Radiology workflow + AI ops | Workflow automation, not post-hoc audit; complementary |
| Aidoc internal monitoring tools | Vendor-internal QA | Single-vendor, single-disease; we are cross-vendor cross-disease |
| Centaur Labs | Annotation quality + crowd labeling | Labeling QA, not deployed-model audit |
| Vara (Germany) | Breast imaging AI ops | Single-disease + workflow, not framework |
| Babic et al. 2025 framework (npj Digit Med 8:328) | Academic governance framework | Conceptual framework, not deployable tool — we cite as supporting evidence |
| FDA OSEL post-market monitoring program | FDA research effort | Government R&D effort identifying the unmet need; positions us as solution |
| Ouyang 2021, Cho ICML 2024, Yang Med Phys 2025, Adilina LMID 2025, Sorino Brain Inform 2025 | Various training-time + label-noise methods (mostly AD) | All training-time or single-task; we are post-hoc + cross-disease |

No stealth-mode startup directly competing identified as of May 2026. Closest adjacent companies are radiology AI ops platforms (Rad AI, Blackford, EnvoyAI/Change Healthcare imaging AI marketplace) — opportunity for integration partnerships, not direct competition. Closest adjacent academic work is **Schuessler 2025 for model-agnostic temporal validation** (different unit of analysis: cohort drift over years vs per-patient trajectory across visits) and **Jian 2025 TimeFlow for temporal coherence in brain MRI** (different task: registration deformation fields vs classification output audit). Neither preempts `temporalmetric`'s claim; both strengthen the case that the field recognizes temporal aspects of medical AI as an important, unresolved problem.

---

## F. Awards (14 active venues)

| Award | Sponsor | Eligibility | Deadline | Notes |
|---|---|---|---|---|
| RSNA Resident/Fellow Research Grant | RSNA R&E Foundation | Resident/fellow + RSNA member | Next cycle ~Jan 22, 2027 | $30K/yr; Maruf eligible as ESOR fellow |
| RSNA Harwood-Nash International / Education Project Award | RSNA R&E | International welcomed | ~Jan 15, 2027 | Strong fit for educational arm |
| RSNA Trainee Research Prize | RSNA Annual Meeting | RSNA trainees | Abstract April; meeting late Nov | Aim for RSNA 2027 |
| ASFNR Outstanding Research/Project Award | ASFNR | Member, fellows encouraged | ASFNR annual cycle | Direct fit Newport Beach Oct 2026 |
| ASNR Annual Meeting Resident/Fellow Awards | ASNR | Trainee member | ~Oct–Nov for May meeting | ASNR 2027 |
| MICCAI LMID 2026 Workshop Best Paper | MICCAI 2026 (Strasbourg 27 Sep–1 Oct) | Workshop authors | LMID CFP per ldtm-miccai.github.io | Direct fit |
| MICCAI EMERGE 2026 Best Paper | MICCAI 2026 | Workshop authors | EMERGE 2026 CFP | $300/$200/$100 + LNCS |
| NEJM AI Editor's Pick | NEJM AI | Published authors | Rolling curatorial | Backup to Nature Med / Lancet DH |
| SIIM Annual Meeting Awards | SIIM | Trainee member | ~Dec/Jan for June meeting | Strong informatics fit |
| AAIC Junior Investigator Awards | Alzheimer's Association | Junior researcher | ~Feb for July meeting | ALZ-NET tie-in |
| MIDL 2026 Best Paper / Oral | MIDL | Any author | midl.io CFP | Disease-agnostic framework fit |
| NeurIPS 2026 Workshops (TS4H / Med-AI Safety / ML4H) | NeurIPS | Workshop authors | Aug–Sep | Med-AI Safety aligned |
| ASCO Annual Meeting Trainee Award (Informatics) | ASCO | Trainee | ~Feb for May/June | Unlocks once oncology RECIST rulepack ships |
| RSNA Quantitative Imaging Award | RSNA | RSNA member | Per RSNA cycle | Direct fit |

**Priority sequence**: (1) MICCAI LMID 2026 workshop submission; (2) ASFNR Newport Beach Oct 2026 oral + poster; (3) Nature Medicine primary; (4) RSNA 2027 abstract + R&E Grant; (5) MIDL 2026 secondary; (6) ASCO 2027 Informatics post-v0.2.

---

## G. Risk Register

P/I scored 1–5. Trigger = observable signal mitigation fires.

| # | Risk | P | I | Mitigation | Owner | Trigger |
|---|---|---|---|---|---|---|
| R1 | Ouyang reimpl fails/exceeds 4wk | 3 | 4 | LP-only fallback; Zhang 2025 L2C-FNN as primary longitudinal benchmark | ML eng #1 | <60% reproduced by W7 |
| R2 | DUA delays beyond W8 | 3 | 5 | File all 4 DUAs week of ASNR; ClinicaDL + synthetic dev loop independent | Maruf | Any DUA pending W4 |
| R3 | MONAI Zoo has no AD bundle | 4 | 2 | Confirmed May 2026; route via ClinicaDL; contribute MONAI bundle as dissemination | ML eng #2 | Confirmed W1 |
| R4 | ClinicaDL weights broken | 1 | 4 | Mirror Zenodo 3491003 day 1; retrain fallback 1–2wk | ML eng #1 | Load failure W5 |
| R5 | Novelty challenged | 4 | 4 | Differentiation table §E.8; "to our knowledge" language; cite Schuessler 2025 (cohort-drift level) and Jian 2025 TimeFlow (registration level) as adjacent prior art with precise unit-of-analysis differentiation; cite Babic 2025 framework as supporting evidence | Maruf | Reviewer comment R1 |
| R6 | Biostatistician unavailable | 3 | 3 | ≥2 candidates by W4; KIUT support; R `mediation` + Imai cookbook reproducible | Maruf | No collaborator by W4 |
| R7 | Neuroradiologist review slip | 3 | 2 | 4-wk budget; RedCap; $200/rater | Maruf | <50% by W17 |
| R8 | MIRIAD N too small | 2 | 3 | Pre-specified pooling; bootstrap CI widens honestly | Biostatistician | N<10 per interval |
| R9 | FDA pushes higher-risk class | 3 | 4 | Q-Sub non-binding; pivot to CDS carve-out §3060; pursue Breakthrough Device designation if warranted | Reg counsel | Written FDA response |
| R10 | GPU bottleneck | 2 | 3 | Lambda Labs / AWS spot; $50K budget; only Ouyang reimpl needs heavy GPU (~4 A100-40GB days) | ML eng #1 | ETA >2wk |
| R11 | Naming collision with AUDIT | 5 | 5 | Confirmed (Aumente-Maestro, Cabezas et al. 2025, Comput Methods Programs Biomed 271:108991, DOI 10.1016/j.cmpb.2025.108991); use `temporalmetric` + NeuroTCS; reserve PyPI W0 | Maruf | PyPI unavailable |
| R12 | Patent disclosure issue | 3 | 4 | File provisional within 8wk; broad disease-agnostic claims | Patent counsel | OSF preregistration prepared |
| R13 | Manuscript rushed | 3 | 3 | 2wk buffer; pivot to Lancet DH if needed | Maruf | Demo prep >15hr/wk W18–20 |
| R14 | ALZ-NET DAUR denied | 3 | 2 | Aim 6 deferred; future-work hook | Maruf | DAUR pending >12wk |
| R15 | Multi-disease portability null | 3 | 3 | Aim 5 supplementary; null result publishable as "framework portable but field's AD models do not generalize" | Maruf + ML eng #2 | By W19, no usable non-AD model |
| R16 | MS specialist unrecruited | 3 | 2 | MS is v0.2 (Q1 2027); defer to v0.3 if no specialist | Maruf | No specialist by W12 |
| R17 | Q-Sub response delayed beyond Q1 2027 | 3 | 3 | Plan B: parallel pre-engagement with MDR Notified Body for CE-MDR Technical File; do not block product launch on Q-Sub; pursue limited research-use beta with academic-medical-center BAA partners | Maruf + Reg counsel | No FDA meeting confirmation by W30 |
| R18 | EU AI Act conformity assessment cost > $120K budget | 2 | 3 | Defer EU launch to year 2; US market sufficient for seed-stage validation; coordinate with Notified Body early to scope minimum viable Technical File | Reg counsel | Quoted Notified Body fees >$150K |
| R19 | Uzbekistan ZRU-547 cross-border consent friction | 2 | 2 | Default dashboard accepts only US/EU sites at launch; Uzbek sites use library locally (Layer 1) without dashboard until ZRU-547 compliance reviewed | Maruf + local counsel | Local counsel flags ambiguity |
| R20 | Babic 2025 framework or similar academic competitor releases a toolkit | 3 | 3 | Babic 2025 is governance framework, not tool — different artifact. Monitor npj Digit Med, JAMIA, JBI quarterly; if academic toolkit released, position `temporalmetric` as production-grade, FDA-aligned, multi-disease alternative | Maruf | New audit-tool paper in top-tier journal |

---

## H. Best-Ever Additions

1. Multi-disease platform is CORE. v0.1 ships **AD AA 2024 (Jack 2024) as primary + TRAC handling (La Joie 2025) + NIA-AA 2018 legacy compatibility + ADNI translation layer**, all in production, plus YAML skeletons for PD/MS/oncology/stroke/lung-nodule. v0.2 (Q1 2027) ships all six neuro+oncology rulepacks in production; disease-specialist sign-off is logged in the schema's `reviewers` field (additive and non-blocking per the §B.6 authority model: clinical authority resides in the cited published guideline). v0.3+ extends to prostate (Epstein), DR (ETDRS), NYHA heart failure, METAVIR liver fibrosis, RANO neuro-oncology, BI-RADS longitudinal.
2. Federated learning hooks — accept hashed per-subject TCS summaries for multi-site aggregation without raw data sharing; aligns with NIH Bridge2AI privacy standards.
3. DICOM router + structured report integration via ACR Common Data Elements.
4. Patient-facing trajectory dashboard (Flutter — Maruf's stack) supporting shared decision-making for anti-amyloid eligibility.
5. MyRehab integration — TCS module for stroke and post-treatment cognitive trajectories (mRS rulepack maps to existing MyRehab use case).
6. Synthetic longitudinal data generation via MONAI Generative Models for stress-testing rare transitions.
7. Counterfactual analysis: "what would cTCS have been if model X trained on cohort Y?"
8. TCS-over-time drift detector aligned with FDA PCCP impact assessments.
9. Educational open-source teaching version — Jupyter notebooks in EN/RU/UZ; KIUT + ESNR residency partnership.
10. Hugging Face Space TCS leaderboard for community submissions; multi-disease tracks post-v0.2.
11. Multi-language docs: EN, RU, UZ first; ES, Mandarin later.
12. Regulatory affairs subscription tier — premium SaaS auto-generates PCCP impact-assessment reports + quarterly drift detection.
13. Strategic dataset partnerships: ALZ-NET, ENABLE-AD (lecanemab real-world), PD-GENEration, MSBase (90,000+ MS patients), TCIA Longitudinal Lung Imaging.

---

## I. Verification Log

### I.1 Verified citations (May 2026)

**AD core:**
- Jack 2018 NIA-AA Research Framework. Alzheimer's & Dementia 14:535-562. PMID 29653606.
- Jack CR Jr, Andrews JS, Beach TG, Buracchio T, Dunn B, Graf A, et al. Revised criteria for diagnosis and staging of Alzheimer's disease: Alzheimer's Association Workgroup. Alzheimer's & Dementia 2024;20(8):5143-5169. DOI 10.1002/alz.13859. PMID 38934362. Published online 27 June 2024.
- Salemme et al. 2025. Alzheimer's & Dementia: DADM 17:e70074. DOI 10.1002/dad2.70074.

**Multi-disease anchors:**
- Hoehn MM, Yahr MD. Neurology 1967;17(5):427-442.
- Goetz CG et al. MDS-UPDRS. Movement Disorders 2008;23(15):2129-2170.
- Kurtzke JF. EDSS. Neurology 1983;33(11):1444-1452.
- Montalban X, Lebrun-Frénay C, Oh J, et al. Diagnosis of multiple sclerosis: 2024 revisions of the McDonald criteria. Lancet Neurology 2025;24(10):850-865. DOI 10.1016/S1474-4422(25)00270-4. Published online 17 Sep 2025.
- Eisenhauer EA et al. RECIST 1.1. European Journal of Cancer 2009;45(2):228-247. DOI 10.1016/j.ejca.2008.10.026. PMID 19097774.
- Seymour L et al. iRECIST. Lancet Oncology 2017;18(3):e143-e152. DOI 10.1016/S1470-2045(17)30074-8. PMID 28271869.
- MacMahon H et al. Fleischner 2017. Radiology 2017;284(1):228-243. DOI 10.1148/radiol.2017161659.
- Banks JL, Marotta CA. mRS. Stroke 2007;38(3):1091-1096.

**Datasets:**
- ADNI: adni.loni.usc.edu
- OASIS-3: 1,378 participants, 2,842 MR sessions, FreeSurfer outputs; central.xnat.org; LaMontagne 2019 medRxiv 2019.12.13.19014902
- MIRIAD: Malone 2013 NeuroImage. DOI 10.1016/j.neuroimage.2012.12.044. PMID 23274184. 46 AD + 23 CN, 708 scans.
- ALZ-NET: 118 active clinical sites + 93 imaging centers; >3,600 enrolled patients; subset of >600 receiving anti-amyloid therapies; CTAD 3 Dec 2025 readout; CMS-approved CED study managed by ACR; alz-net.org/participate-alz-net
- PPMI: ppmi-info.org/access-data-specimens; 2,000+ subjects, 50 sites, 12 countries; MDS-UPDRS, H&Y, DaTSCAN, MRI, DTI
- RIDER Lung PET-CT: 244 longitudinal subjects; designed for therapy response evaluation; TCIA. Zhao 2015 DOI 10.7937/k9/tcia.2015.u1x8a5nr (CT subset). PMC4938843 (project paper).

**Reporting guidelines:**
- CLAIM 2024: Tejani et al. Radiology AI 2024;6:e240300.
- TRIPOD+AI: Collins et al. BMJ 2024;385:e078378. DOI 10.1136/bmj-2023-078378.
- STARD-AI 2025: Sounderajah et al. Nature Medicine 2025;31(10):3283-3289. DOI 10.1038/s41591-025-03953-8. Published online 15 Sep 2025.
- DECIDE-AI: Vasey et al. Nature Medicine 2022;28:924-933.

**Regulatory:**
- FDA Final PCCP Guidance: 4 Dec 2024.
- FDA Q-Sub Final Guidance: 29 May 2025.
- FDA AI-DSF Draft Guidance: 6 Jan 2025.
- FDORA 2022 §515C (21 USC 360e-4), Pub L. 117-328.
- FDA + Health Canada + UK MHRA Five Guiding Principles for PCCPs: August 2025.
- FDA OSEL post-market monitoring research program: confirmed active.
- EU AI Act (Regulation 2024/1689): entered into force Aug 2024; phased application 2025–2026.
- EU MDR (Regulation 2017/745); Rule 11 classifies AI clinical decision software as Class IIa.
- Uzbekistan Law ZRU-547 "On Personal Data": effective Oct 2019, amended 2021.

**Methodology and prior art:**
- Ouyang 2021. IEEE JBHI. PMID 33270567. PMC8221531. arXiv 2003.13958. Repo github.com/ouyangjiahong/longitudinal-pooling README-only.
- Cho et al. ICML 2024 AGT. PMLR 235:8593-8608.
- Sorino et al. Brain Informatics 12:15 (2025). DOI 10.1186/s40708-025-00261-2.
- Yang et al. Medical Physics 2025;52:5064-5080. DOI 10.1002/mp.17767.
- Adilina et al. LMID 2025. DOI 10.1007/978-3-032-16128-4_8.
- Zhang et al. L2C-FNN. Human Brain Mapping 2025;46(11). DOI 10.1002/hbm.70280. PMC12315237.
- AUDIT — Aumente-Maestro C, Cabezas M, et al. "AUDIT: An open-source Python library for AI model evaluation with use cases in MRI brain tumor segmentation." Computer Methods and Programs in Biomedicine 2025;271:108991. DOI 10.1016/j.cmpb.2025.108991. PMID 40795618. Single-timepoint segmentation evaluation toolkit. **Naming collision: do not name our library AUDIT.**
- Babic B, Cohen IG, Stern AD, et al. A general framework for governing marketed AI/ML medical devices. npj Digital Medicine 2025;8:328. DOI 10.1038/s41746-025-01717-9.
- **Schuessler M, Fleming S, Meyer S, Seto T, Hernandez-Boussard T. Diagnostic framework to validate clinical machine learning models locally on temporally stamped data. Communications Medicine 2025;5(1):261. DOI 10.1038/s43856-025-00965-w. PMID 40596645. Published 1 July 2025. Stanford Hernandez-Boussard group. Model-agnostic temporal validation framework demonstrated on oncology ACU (acute care utilization) prediction in 24,000+ cancer patients from EHR 2010–2022. Cohort/population drift level — different unit of analysis from `temporalmetric`'s per-patient trajectory audit.** ✓ Added v1.4 from external audit.
- **Jian B, Pan J, Li Y, Bongratz F, Li R, Rueckert D, Wiestler B, Wachinger C. TimeFlow: Temporal Conditioning for Longitudinal Brain MRI Registration and Aging Analysis. arXiv 2501.08667 (v1 15 Jan 2025; v3 26 Aug 2025); targeted at IEEE Transactions on Medical Imaging 2025/2026. Wachinger group, TUM. U-Net + temporal conditioning estimating deformation fields between two scans, supporting future-state extrapolation. Image registration task — different from classification output audit.** ✓ Added v1.4 from external audit.
- Sivakumar 2025 FDA AI/ML Review. JAMA Network Open. PMC12595527.
- Thulasidasan 2019 OE / Mixup. arXiv 1905.11001.
- Imai 2010 mediation. Psychological Methods 15:309-334.
- Fritz MS, MacKinnon DP. Required sample size to detect the mediated effect. Psychological Science 2007;18(3):233-239.
- Selvaraju 2017 GradCAM. ICCV 2017.
- Lundberg & Lee 2017 SHAP. NeurIPS 2017.
- Mitchell et al. 2019 Model Cards. FAT* '19.
- Gebru et al. 2018 Datasheets for Datasets. arXiv 1803.09010.
- Tzourio-Mazoyer 2002 AAL atlas. NeuroImage 15:273-289.
- Hansson O, Jack CR Jr. A clinical perspective on the revised criteria for diagnosis and staging of Alzheimer's disease. Nature Aging 2024;4(8):1029-1031. DOI 10.1038/s43587-024-00675-3.
- **La Joie R, Cummings JL, Dage JL, et al. Treatment-related amyloid clearance (TRAC): a framework to characterize patients in the era of anti-amyloid therapies. Alzheimer's & Dementia 2025;21(11):e70997. DOI 10.1002/alz.70997. PMC12657122. Alzheimer's Association-convened workgroup led by UCSF (R. La Joie). Defines TRAC as biomarker-confirmed Aβ clearance after anti-Aβ therapy. Full TRAC < 11 CL (Centiloid); partial TRAC = significant Centiloid drop above threshold. Integrated into NeuroTCS `ad/aa_2024_trac.yaml` rulepack v0.1.** ✓ Added v1.6.
- Jacobson NC, Berkman LF. Clustering effects in multi-site research. Quality of Life Research 2010;19:533-541.

**Added v1.7 — Trustworthy-AI frameworks and methodology (all verified May 2026 against primary sources):**
- **Lekadir K, Frangi AF, Porras AR, et al. FUTURE-AI: international consensus guideline for trustworthy and deployable artificial intelligence in healthcare. BMJ 2025;388:e081554. DOI 10.1136/bmj-2024-081554. PMID 39909534. 117-expert consortium from 50 countries; six principles (Fairness, Universality, Traceability, Usability, Robustness, Explainability); 30 best-practice recommendations.**
- **Haller S, Van Cauter S, Federau C, et al. The R-AI-DIOLOGY checklist: a practical checklist for evaluation of artificial intelligence tools in clinical neuroradiology. Neuroradiology 2022;64(5):851-864. DOI 10.1007/s00234-021-02890-w. PMID 35098343. 10-aspect neuroradiology-specific AI evaluation checklist.**
- **ACR-SIIM Practice Parameter for Imaging Artificial Intelligence. Approved by American College of Radiology Council 5 May 2026 at ACR 2026 annual meeting, Washington DC. Joint with Society for Imaging Informatics in Medicine. Covers AI tool selection, predeployment evaluation, ongoing performance monitoring with drift detection and stop rules, patient privacy. Practices implementing per the parameter earn ARCH-AI (ACR Recognized Center for Healthcare-AI) designation; Assess-AI is the companion quality registry.**
- **Larson DB, Bhargavan-Chatfield M, Tilkin M, Coombs L, Wald C. The Road Map for ACR Practice Accreditation for Radiology Artificial Intelligence. Journal of the American College of Radiology 2025;22(5):586-592. DOI 10.1016/j.jacr.2025.02.008. PMID 40057886.**
- **Riley RD, Snell KIE, Archer L, et al. Evaluation of clinical prediction models (part 3): calculating the sample size required for an external validation study. BMJ 2024;385:e074821. DOI 10.1136/bmj-2023-074821. Primary methods source for Aim 1, 2, 3, 5 sample size calculations replacing ad hoc minima.**
- **Riley RD, Debray TPA, Collins GS, et al. Minimum sample size for external validation of a clinical prediction model with a binary outcome. Statistics in Medicine 2021;40(19):4230-4251. DOI 10.1002/sim.9025. PMID 34031906.**
- **Archer L, Snell KIE, Ensor J, Hudda MT, Collins GS, Riley RD. Minimum sample size for external validation of a clinical prediction model with a continuous outcome. Statistics in Medicine 2021;40(1):133-146. DOI 10.1002/sim.8766. PMID 33150684.**
- **Riley RD, Collins GS, Ensor J, et al. Minimum sample size calculations for external validation of a clinical prediction model with a time-to-event outcome. Statistics in Medicine 2022;41(7):1280-1295. DOI 10.1002/sim.9275.**
- **Threshold optimization in AI chest radiography analysis: integrating real-world data and clinical subgroups. PMC12454861, 2025. Operational threshold (OT) methodology used in §A.10 alert-threshold derivation.**
- **Conformal Triage for Medical Imaging AI Deployment. medRxiv 2024.02.09.24302543. Learn-then-Test conformal prediction methodology for distribution-free PPV/NPV guarantees on AI classifiers at site-specific calibration; basis for optional `temporalmetric.conformal` wrapper v0.2.**

### I.2 Action items for Maruf in W1

1. Run `python -m monai.bundle list` to confirm AD bundle status.
2. Confirm PyPI name `temporalmetric` is available; reserve immediately.
3. Confirm KIUT IRB exemption pathway in writing.
4. Fresh PubMed search "temporal consistency Alzheimer audit" filtered to 2026 for preprints after May 12, 2026.
5. ClinicalTrials.gov search "Alzheimer artificial intelligence audit" — document result.
6. Confirm PPMI DAUR turnaround time per ppmi-info.org.
7. Confirm TCIA RIDER Lung PET-CT access process.
8. Verify AAIC 2026 abstract deadline (alz.org/aaic).
9. Verify MICCAI LMID 2026 CFP date (ldtm-miccai.github.io).
10. Engage US patent counsel for provisional within 8 weeks; flag broad-claim strategy.
11. Engage health regulatory counsel (Hogan Lovells or Ropes & Gray) for Q-Sub scoping.
12. Uzbekistan ZRU-547 local counsel review.
13. Cho 2024 / Dao 2024 / TAMME code release availability — direct author email if absent.

---

## J. Bibliography

### AD core and reporting
- Babic B, Cohen IG, Stern AD, et al. A general framework for governing marketed AI/ML medical devices. npj Digital Medicine 2025;8:328. DOI 10.1038/s41746-025-01717-9.
- Collins GS, et al. TRIPOD+AI statement. BMJ 2024;385:e078378. DOI 10.1136/bmj-2023-078378.
- Hansson O, Jack CR Jr. A clinical perspective on the revised criteria for diagnosis and staging of Alzheimer's disease. Nature Aging 2024;4(8):1029-1031. DOI 10.1038/s43587-024-00675-3.
- Jack CR Jr, Andrews JS, Beach TG, Buracchio T, Dunn B, Graf A, et al. Revised criteria for diagnosis and staging of Alzheimer's disease: Alzheimer's Association Workgroup. Alzheimer's & Dementia 2024;20(8):5143-5169. DOI 10.1002/alz.13859. PMID 38934362.
- Jack CR Jr, Bennett DA, Blennow K, et al. NIA-AA Research Framework: Toward a biological definition of Alzheimer's disease. Alzheimer's & Dementia 2018;14(4):535-562. PMID 29653606.
- **La Joie R, Cummings JL, Dage JL, et al. Treatment-related amyloid clearance (TRAC): a framework to characterize patients in the era of anti-amyloid therapies. Alzheimer's & Dementia 2025;21(11):e70997. DOI 10.1002/alz.70997. PMC12657122.**
- Salemme S, Lombardo FL, Lacorte E, et al. The prognosis of mild cognitive impairment: a systematic review and meta-analysis. Alzheimer's & Dementia: DADM 2025;17(1):e70074. DOI 10.1002/dad2.70074.
- Sounderajah V, Guni A, Liu X, et al. The STARD-AI reporting guideline for diagnostic accuracy studies using artificial intelligence. Nature Medicine 2025;31(10):3283-3289. DOI 10.1038/s41591-025-03953-8.
- Tejani AS, Klontzas ME, Gatti AA, Mongan JT, Moy L, Park SH, et al. Checklist for AI in Medical Imaging (CLAIM): 2024 update. Radiology: Artificial Intelligence 2024;6(4):e240300. DOI 10.1148/ryai.240300.
- Vasey B, Nagendran M, Campbell B, et al. DECIDE-AI: reporting guideline for early-stage clinical evaluation of decision-support systems driven by artificial intelligence. Nature Medicine 2022;28(5):924-933. DOI 10.1038/s41591-022-01772-9.

### Multi-disease clinical criteria
- Banks JL, Marotta CA. Outcomes validity and reliability of the modified Rankin Scale: implications for stroke clinical trials. Stroke 2007;38(3):1091-1096.
- Eisenhauer EA, Therasse P, Bogaerts J, et al. New response evaluation criteria in solid tumours: revised RECIST guideline (version 1.1). European Journal of Cancer 2009;45(2):228-247. DOI 10.1016/j.ejca.2008.10.026. PMID 19097774.
- Goetz CG, Tilley BC, Shaftman SR, et al. MDS-UPDRS: Scale presentation and clinimetric testing results. Movement Disorders 2008;23(15):2129-2170.
- Hoehn MM, Yahr MD. Parkinsonism: onset, progression and mortality. Neurology 1967;17(5):427-442.
- Kurtzke JF. Rating neurologic impairment in multiple sclerosis: an Expanded Disability Status Scale (EDSS). Neurology 1983;33(11):1444-1452.
- MacMahon H, Naidich DP, Goo JM, et al. Guidelines for Management of Incidental Pulmonary Nodules Detected on CT Images: From the Fleischner Society 2017. Radiology 2017;284(1):228-243. DOI 10.1148/radiol.2017161659.
- Montalban X, Lebrun-Frénay C, Oh J, Arrambide G, Moccia M, Pia Amato M, et al. Diagnosis of multiple sclerosis: 2024 revisions of the McDonald criteria. Lancet Neurology 2025;24(10):850-865. DOI 10.1016/S1474-4422(25)00270-4.
- Seymour L, Bogaerts J, Perrone A, et al. iRECIST: guidelines for response criteria for use in trials testing immunotherapeutics. Lancet Oncology 2017;18(3):e143-e152. DOI 10.1016/S1470-2045(17)30074-8. PMID 28271869.

### Datasets
- LaMontagne PJ, et al. OASIS-3: Longitudinal Neuroimaging Dataset for Normal Aging and AD. medRxiv 2019.12.13.19014902.
- Malone IB, Cash D, Ridgway GR, et al. MIRIAD — Public release of a multiple time point Alzheimer's MR imaging dataset. NeuroImage 2013;70:33-36. DOI 10.1016/j.neuroimage.2012.12.044. PMID 23274184.
- Marek K, et al. The Parkinson Progression Marker Initiative (PPMI). PMC9014725. ppmi-info.org.
- The Cancer Imaging Archive: NSCLC-Radiomics (Lung1, 422 NSCLC pretreatment); RIDER Lung CT (32 subjects, same-day repeat + longitudinal); RIDER Lung PET-CT (244 longitudinal subjects); TCIA project paper Zhao B, Schwartz LH, Kris MG. PMC4938843.
- ALZ-NET. alz-net.org/participate-alz-net. Managed by American College of Radiology. 118 sites + 93 imaging centers + >3,600 patients per Alzheimer's Association press release 3 Dec 2025.

### Trustworthy-AI frameworks and practice parameters
- **Lekadir K, Frangi AF, Porras AR, et al. FUTURE-AI: international consensus guideline for trustworthy and deployable artificial intelligence in healthcare. BMJ 2025;388:e081554. DOI 10.1136/bmj-2024-081554. PMID 39909534.**
- **Haller S, Van Cauter S, Federau C, et al. The R-AI-DIOLOGY checklist: a practical checklist for evaluation of artificial intelligence tools in clinical neuroradiology. Neuroradiology 2022;64(5):851-864. DOI 10.1007/s00234-021-02890-w. PMID 35098343.**
- **ACR-SIIM Practice Parameter for Imaging Artificial Intelligence. American College of Radiology and Society for Imaging Informatics in Medicine. Approved by ACR Council 5 May 2026, Washington DC.** acr.org/News-and-Publications/Media-Center/2026/first-practice-parameter-for-imaging-ai
- **Larson DB, Bhargavan-Chatfield M, Tilkin M, Coombs L, Wald C. The Road Map for ACR Practice Accreditation for Radiology Artificial Intelligence. Journal of the American College of Radiology 2025;22(5):586-592. DOI 10.1016/j.jacr.2025.02.008. PMID 40057886.**

### Sample size methodology (Riley framework)
- **Riley RD, Snell KIE, Archer L, et al. Evaluation of clinical prediction models (part 3): calculating the sample size required for an external validation study. BMJ 2024;385:e074821. DOI 10.1136/bmj-2023-074821.**
- **Riley RD, Debray TPA, Collins GS, et al. Minimum sample size for external validation of a clinical prediction model with a binary outcome. Statistics in Medicine 2021;40(19):4230-4251. DOI 10.1002/sim.9025. PMID 34031906.**
- **Archer L, Snell KIE, Ensor J, Hudda MT, Collins GS, Riley RD. Minimum sample size for external validation of a clinical prediction model with a continuous outcome. Statistics in Medicine 2021;40(1):133-146. DOI 10.1002/sim.8766. PMID 33150684.**
- **Riley RD, Collins GS, Ensor J, et al. Minimum sample size calculations for external validation of a clinical prediction model with a time-to-event outcome. Statistics in Medicine 2022;41(7):1280-1295. DOI 10.1002/sim.9275.**

### Threshold optimization and conformal prediction
- **Threshold optimization in AI chest radiography analysis: integrating real-world data and clinical subgroups. PMC12454861, 2025.**
- **Conformal Triage for Medical Imaging AI Deployment. medRxiv 2024.02.09.24302543.**

### Methodology and prior art
- Adilina S, et al. Longitudinal Brain Segmentation with Temporal Consistency for Neurodegenerative Analysis. LMID 2025. LNCS 16184. DOI 10.1007/978-3-032-16128-4_8.
- Aghdam MA, Bozdag S, Saeed F. ML for AD diagnosis: survey, reproducibility, generalizability. Brain Informatics 2025;12:8.
- Aumente-Maestro C, Cabezas M, et al. AUDIT: An open-source Python library for AI model evaluation with use cases in MRI brain tumor segmentation. Computer Methods and Programs in Biomedicine 2025;271:108991. DOI 10.1016/j.cmpb.2025.108991. PMID 40795618.
- Cho H, Sim J, Wu G, Kim WH. Neurodegenerative Brain Network Classification via Adaptive Diffusion with Temporal Regularization. ICML 2024. PMLR 235:8593-8608.
- Efron B, Tibshirani RJ. An Introduction to the Bootstrap. Chapman & Hall, 1993.
- Fritz MS, MacKinnon DP. Required sample size to detect the mediated effect. Psychological Science 2007;18(3):233-239.
- Gebru T, Morgenstern J, Vecchione B, et al. Datasheets for Datasets. arXiv 1803.09010.
- Imai K, Keele L, Tingley D. A general approach to causal mediation analysis. Psychological Methods 2010;15(4):309-334.
- Jacobson NC, Berkman LF. Clustering effects in multi-site research. Quality of Life Research 2010;19:533-541.
- **Jian B, Pan J, Li Y, Bongratz F, Li R, Rueckert D, Wiestler B, Wachinger C. TimeFlow: Temporal Conditioning for Longitudinal Brain MRI Registration and Aging Analysis. arXiv 2501.08667 (15 Jan 2025; v3 26 Aug 2025). Submitted IEEE Transactions on Medical Imaging.**
- Lundberg SM, Lee SI. A Unified Approach to Interpreting Model Predictions. NeurIPS 2017.
- Mitchell M, Wu S, Zaldivar A, et al. Model Cards for Model Reporting. FAT* '19.
- Ouyang J, Adeli E, Pohl KM, Zhao Q, Zaharchuk G. Longitudinal Pooling & Consistency Regularization to Model Disease Progression from MRIs. IEEE Journal of Biomedical and Health Informatics 2021. PMID 33270567; PMC8221531; arXiv 2003.13958.
- Salazar JC, et al. Markov-chain modeling of AD progression. PMC2830381.
- **Schuessler M, Fleming S, Meyer S, Seto T, Hernandez-Boussard T. Diagnostic framework to validate clinical machine learning models locally on temporally stamped data. Communications Medicine 2025;5(1):261. DOI 10.1038/s43856-025-00965-w. PMID 40596645. Published 1 July 2025.**
- Selvaraju RR, et al. Grad-CAM. ICCV 2017.
- Sivakumar R, et al. FDA Approval of AI/ML Devices in Radiology: A Systematic Review. JAMA Network Open 2025. PMC12595527.
- Sorino P, Lombardi A, Lofù D, et al. Detecting label noise in longitudinal Alzheimer's data with explainable AI. Brain Informatics 2025;12:15. DOI 10.1186/s40708-025-00261-2.
- Thibeau-Sutre E, et al. ClinicaDL: open-source deep learning software for reproducible neuroimaging processing. HAL-03351976.
- Thulasidasan S, et al. On Mixup Training: Improved Calibration and Predictive Uncertainty for Deep Neural Networks. NeurIPS 2019. arXiv 1905.11001.
- Tzourio-Mazoyer N, et al. AAL atlas. NeuroImage 2002;15(1):273-289.
- Wang Q, et al. Estimating Transition Probabilities Across the AD Continuum Using a Nationally Representative Real-World Database. Neurology and Therapy 2023. DOI 10.1007/s40120-023-00498-1.
- Wen J, Samper-González J, et al. CNNs for AD Classification: Overview and Reproducible Evaluation. Zenodo record 3491003.
- Yang P-A, et al. Temporal-multimodal consistency alignment for AD cognitive assessment prediction. Medical Physics 2025;52:5064-5080. DOI 10.1002/mp.17767.
- Zhang C, An L, Wulan N, et al. Cross-Dataset Evaluation of Dementia Longitudinal Progression Prediction Models. Human Brain Mapping 2025;46(11). DOI 10.1002/hbm.70280. PMC12315237.

### Regulatory
- FDA. Marketing Submission Recommendations for a Predetermined Change Control Plan for AI-Enabled Device Software Functions. Final Guidance, 4 December 2024.
- FDA. Requests for Feedback and Meetings for Medical Device Submissions: The Q-Submission Program. Final Guidance, 29 May 2025.
- FDA. Artificial Intelligence-Enabled Device Software Functions: Lifecycle Management and Marketing Submission Recommendations. Draft Guidance, 6 January 2025.
- FDA. Methods and Tools for Effective Postmarket Monitoring of AI-Enabled Medical Devices. OSEL Research Program.
- FDA, Health Canada, UK MHRA. Five Guiding Principles for PCCPs for ML-Enabled Medical Devices. August 2025.
- FDORA 2022 §515C (21 USC 360e-4), Pub L. 117-328.
- European Parliament. Regulation 2024/1689 (EU AI Act). Aug 2024 entry into force; phased application 2025–2026.
- European Parliament. Regulation 2017/745 (EU MDR). Rule 11 classifies AI clinical decision software as Class IIa.
- Republic of Uzbekistan. Law ZRU-547 "On Personal Data". Effective Oct 2019, amended 2021.

---

Document v1.7 FINAL. 12 May 2026. Apache-2.0 / CC-BY-4.0.

**v1.7 changes (external auditor integration, all five gaps closed at world-class level):**
1. §A.8 — Sample size calculations replaced with Riley framework (BMJ 2024;385:e074821) across Aims 1, 2, 3, 5; methodology papers Riley 2021/2022 and Archer 2021 cited. Aim 4 mediation power retained with Fritz/MacKinnon 2007 + Imai 2010 fallback.
2. §A.10 — New section: operational alert threshold derivation methodology (NOT predetermined values); thresholds empirically calibrated from Aim 1 data per ACR-SIIM Practice Parameter "stop rules" + conformal prediction wrapper.
3. §B.4.2 — Trustworthy-AI framework alignment added: FUTURE-AI six principles (Lekadir 2025 BMJ), R-AI-DIOLOGY 10-aspect neuroradiology checklist (Haller 2022 Neuroradiology), ACR-SIIM Practice Parameter (approved 5 May 2026) with Assess-AI + ARCH-AI + Larson 2025 JACR roadmap.
4. §B.4.4 — Full subgroup fairness audit panel: 7 dimensions (sex × age × race/ethnicity × scanner vendor × field strength × disease stage × treatment status); equalized-odds disparity metric; two-level audit (base model + temporalmetric itself).
5. §B.4.5 — Factorial stress test matrix: scanner vendor × field strength × interval length × acquisition protocol × slice thickness × pipeline; pre-specified pass thresholds.
6. §B.5.3 — Silent-deployment phase explicit (Kwong 2022 silent-trial methodology + DECIDE-AI reporting items): KIUT + 1 EU site, W17–W20, no clinical decisions changed, stop rules per ACR-SIIM Practice Parameter, extends through Q1 2027 for FDA Q-Sub data package.
7. §B.5.4 — Optional conformal prediction wrapper (v0.2) for distribution-free PPV/NPV guarantees.

**v1.6 content preserved:** AA 2024 (Jack 2024 PMID 38934362) primary + TRAC handling (La Joie 2025 Alzheimer's & Dementia 21(11):e70997, DOI 10.1002/alz.70997) + ADNI translation layer + AUDIT citation correction (Aumente-Maestro et al. 2025 Comput Methods Programs Biomed 271:108991) + Schuessler 2025 + Jian 2025 TimeFlow differentiation.

**Defensibility:** Spec is now defensible at ASFNR Newport Beach Oct 2026 against any reviewer who reads CLAIM 2024, TRIPOD+AI, STARD-AI, DECIDE-AI, FUTURE-AI, R-AI-DIOLOGY, or the ACR-SIIM Practice Parameter. All sample sizes are Riley-framework derived. All thresholds are methodology-stated (not number-hallucinated). All subgroup analyses are panel-defined. All silent-deployment endpoints align with Kwong 2022 silent-trial methodology and are reported on the DECIDE-AI checklist. Nature Medicine W22 submission ready.

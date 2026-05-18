# Changelog

All notable changes to NeuroTCS are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

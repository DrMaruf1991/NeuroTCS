# Changelog

All notable changes to NeuroTCS are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

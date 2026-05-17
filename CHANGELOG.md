# Changelog

All notable changes to NeuroTCS are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-05-17

### Added
- **Umbrella repo structure.** Single `NeuroTCS/` Python package with `src/` layout. All seven pieces of the temporalmetric v1.6 FINAL generalization layer now live under `src/neurotcs/`.
- **Piece 3 — Rule pack format v1.1 (`src/neurotcs/rulepack/`).** Citation-locked, version-stamped, fail-closed clinical rule packs.
  - Schema v1.1 adds `transcribed_by`, `clinical_source_authority`, and per-transition `guideline_section` fields. Authority model: clinical authority lives in the cited published guideline; the transcriber attests the YAML faithfully encodes that guideline.
  - **All 8 rule packs ship as PRODUCTION** via verbatim transcription from anchor publications:
    - `ad/niaaa_2018@1.1.0` — Jack 2018 NIA-AA Research Framework
    - `ad/aa_2024@1.1.0` — Jack 2024 AA Revised Criteria
    - `pd/hoehn_yahr@1.0.0` — Goetz 2008 MDS-UPDRS Appendix C
    - `ms/mcdonald_2024@1.0.0` — Montalban 2025 + Lublin 2014 (relapse-remission biology)
    - `oncology/recist_1_1@1.0.0` — Eisenhauer 2009 (4-week confirmation rule)
    - `oncology/irecist@1.0.0` — Seymour 2017 (pseudoprogression resolution explicit)
    - `stroke/mrs_followup@1.0.0` — Banks 2007 + Winstein 2016 (bidirectional recovery + death absorbing)
    - `lung_nodule/fleischner_2017@1.0.0` — MacMahon 2017 (growth + shrinkage with override)
  - 8 transcription-audit MD files in `docs/transcription_audit/` showing side-by-side YAML ↔ source verification.
- **Piece 2 — Input contract v1.1 (`src/neurotcs/input_contract/v1_1/`).** Continuous-biomarker support, UCUM unit allowlist, value_type enum, reference_range metadata. Backward-compatible with v1.0. Production-validated on real ADNI UCSFFSX7 (9,536 predictions / 1,772 patients / 19,072 volumetric measurements).
- **Piece 1 — Input contract v1.0 (`src/neurotcs/input_contract/v1_0/`).** Categorical predictions, 8-step validation pipeline. Production-validated on real ADNI (14,958 visits / 2,955 patients).
- **Pieces 4–7 — Placeholders** with `NotImplementedError` stubs and module docstrings describing planned APIs.
- **Repo hygiene.** `pyproject.toml` (PEP 621), `LICENSE` (Apache-2.0), `.gitignore`, `CITATION.cff`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/workflows/ci.yml` (multi-Python CI on 3.10/3.11/3.12 + ruff + mypy + build).
- **Documentation.** `docs/spec/temporalmetric_v1.6_FINAL.md` (canonical spec, 9,859 words) committed.

### Validated
- Real ADNI re-validation against v1.1 `ad/niaaa_2018` pack: **12,006 transitions audited, 65 flagged (0.54%)** — identical to v1.0 result. All flags clinically interpretable (MCI→CN reversions below 180-day minimum + AD→MCI reversions documented inadmissible).
- Test suite: **24/24 passing** for rule pack v1.1; all v1.0 and v1.1 input-contract tests carried forward.

### Strategic
- Adopted **published-guideline-as-authority** model. Skeleton rule packs are no longer required to await disease-specialist co-authors; instead, the transcriber (board-certified physician) attests that the YAML faithfully encodes the cited internationally endorsed guideline. Specialist `reviewers` remain available as additive non-blocking sign-off.

---

## [1.0.0] — 2026-05-13 (input contract + rule pack v1.0, separate repos)

### Added
- Input contract v1.0 (categorical predictions, 10/10 tests).
- Input contract v1.1 (continuous biomarkers, UCUM, 23/23 tests).
- Rule pack v1.0 (33/33 tests, 2 AD production + 6 disease skeletons).

Note: v1.0 lived in separate repos that are now consolidated into this umbrella repo.

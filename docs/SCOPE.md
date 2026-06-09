# NeuroTCS v1.x Scope Statement

**Effective:** v1.10.0 (2026-05-25) onward (v1.9.0 first AD-only release; v1.10.0 first multi-layer release)
**Status:** Canonical — supersedes any conflicting statements in older docs

## Scope: Alzheimer's disease only; multi-layer audit family

NeuroTCS v1.x is a citation-locked, fail-closed **audit-layer family** for longitudinal medical AI **in Alzheimer's disease**. The v1.x release series will not ship rule packs or audit infrastructure for any other disease domain.

As of v1.10.0, NeuroTCS ships **two parallel audit layers**:

| Layer | Question | Shipped | Status |
|---|---|---|---|
| **Layer 1 · Temporal coherence** | Are the model's predicted disease-stage transitions clinically plausible? | v1.0+ | Production (5-cohort byte-exact locked) |
| **Layer 2 · Clinical range validation** | Do the per-visit clinical measurements fall within published biologically-plausible ranges? | v1.10.0 | Production (6 packs, 55 measurements) |
| Layer 3 · Cross-sheet consistency | Are signals across different domains (genetics / labs / imaging / cognition) internally consistent? | v1.11.0 roadmap | Planned |
| Layer 4 · Inclusion / protocol | Does each patient and visit comply with the trial protocol? | v1.18.0 design (`docs/design/LAYER_4_DESIGN.md`) / v1.19.0 first pack | Designed |

The Layer Contract that all layers adhere to is documented at [`docs/clinical_ranges/LAYER_CONTRACT.md`](clinical_ranges/LAYER_CONTRACT.md).

## What this means in practice

| Question | Answer |
|---|---|
| What rule packs ship in v1.x? | **Layer 1:** Exactly 3 AD packs: `ad/niaaa_2018`, `ad/aa_2024`, `ad/aa_2024_trac`<br>**Layer 2 (v1.10.0):** Exactly 6 range packs covering vitals, CSF/plasma biomarkers, MRI volumetrics, PET amyloid, AD genetics |
| What cohorts are audited under the four-cohort triangulation lock? | ADNI, OASIS-3, NACC, MIRIAD (plus MIRIAD test-retest) — all AD, Layer 1 only |
| Will Parkinson's, MS, oncology, stroke, or lung-nodule rule packs be added in v1.x? | No |
| What if I have a non-AD rule pack? | The schema (`DiseaseDomain` enum) accepts only `alzheimers` and `custom`; non-AD packs will fail validation |
| Where did the non-AD rule packs go? | Extracted at v1.9.0 (see [v1.9.0 CHANGELOG entry](../CHANGELOG.md#190--2026-05-24)). They are recoverable from git history at tag v1.8.1 or from the offline archive `NeuroTCS-non-AD-extracted-v1.8.1.zip`. NeuroTCS itself is and remains Alzheimer's-disease only; it does not roadmap non-AD coverage. |
| Will non-AD coverage return to NeuroTCS? | No. NeuroTCS is an Alzheimer's-disease tool. The historical extracted packs are preserved as archival seed material only; whether any separate non-AD project is ever built is outside NeuroTCS's scope and is not a commitment of this repository. |
| What about Aim 5 multi-disease portability (in the v1.7 spec)? | Out of scope for NeuroTCS. The v1.7 spec retains the description as historical design intent only, flagged out-of-scope via a top-of-document override notice. |

## Why this scope decision

NeuroTCS was originally designed as a multi-disease platform. As of v1.8.x, the AD validation surface had achieved byte-exact four-cohort triangulation (OASIS-3 cTCS = 0.994191, ADNI = 0.994575, NACC = 0.991502, MIRIAD = 0.985369, all 6 pairwise deltacTCS <=0.01 -- our pre-specified threshold), while the 5 non-AD rule packs were citation-locked transcriptions but had no cohort runs and no DUAs filed.

The decision to scope-narrow to AD for v1.x was made on 2026-05-24 by Dr. Marufjon Salokhiddinov (NeuroTCS lead). The reasons:

1. **Cohesion.** A single-disease scope yields a tight, cohesive AD audit framework rather than a sprawling multi-disease library where most packs would lack cohort runs. Should any regulatory pathway be pursued, a focused AD tool is the cleaner subject; that is an aspiration, not a current claim or commitment (see Regulatory status below).
2. **Substantive validation.** The AD validation surface is empirically demonstrated; non-AD packs are unvalidated. Shipping them mixed together blurs the distinction.
3. **Cohesion and validation focus.** A single-disease framework keeps the validation surface, cohort adapters, and clinical-specialist review focused on Alzheimer's disease. NeuroTCS does not attempt to be a multi-disease library; that focus is a deliberate design choice, not a staging area for other diseases.

## What was preserved

- The 5 non-AD rule pack YAMLs + 6 transcription audit docs are preserved in git history at tag `v1.8.1` (commit `d2865af`) and in an offline archive `NeuroTCS-non-AD-extracted-v1.8.1.zip` with per-disease seed READMEs.
- All historical CHANGELOG and ERRATA entries describing the non-AD work are kept verbatim (e.g., ERRATA E-2026-003 on the Marras 2002 PD citation correction). History is immutable.
- The `DiseaseDomain` enum retains `CUSTOM` so vendor-specific or research-only AD variants can still be validated.

## What was removed in v1.9.0

| Removed | Path in v1.8.1 | Replacement / where it went |
|---|---|---|
| PD/Hoehn-Yahr rule pack | `src/neurotcs/rulepack/rules/pd/hoehn_yahr.yaml` | `NeuroTCS-non-AD-extracted-v1.8.1.zip:parkinsons/` (archival only) |
| MS/McDonald 2024 rule pack | `src/neurotcs/rulepack/rules/ms/mcdonald_2024.yaml` | Same archive `multiple_sclerosis/` (archival only) |
| Oncology RECIST 1.1 + iRECIST | `src/neurotcs/rulepack/rules/oncology/` | Same archive `oncology/` (archival only) |
| Stroke mRS follow-up | `src/neurotcs/rulepack/rules/stroke/mrs_followup.yaml` | Same archive `stroke/` (archival only) |
| Lung-nodule Fleischner 2017 | `src/neurotcs/rulepack/rules/lung_nodule/fleischner_2017.yaml` | Same archive `lung_nodule/` (archival only) |
| 6 transcription audit docs | `docs/transcription_audit/{pd_hoehn_yahr,ms_mcdonald_2024,oncology_recist_1_1,oncology_irecist,stroke_mrs_followup,lung_nodule_fleischner_2017}.md` | Same archive per-disease subdirs |
| `DiseaseDomain` enum non-AD values | `src/neurotcs/rulepack/schema.py` (`PARKINSONS`, `MULTIPLE_SCLEROSIS`, `GLIOBLASTOMA`, `STROKE`, `CARDIOLOGY`, `ONCOLOGY`, `PULMONOLOGY`) | Removed; not part of NeuroTCS (archival history only) |
| 6 non-AD-specific tests | `tests/rulepack/test_rulepack.py` (`test_pd_behaviors`, `test_ms_relapse_remission`, `test_recist_bidirectional_with_confirmation`, `test_irecist_pseudoprogression`, `test_stroke_recovery_and_death`, `test_fleischner_growth_and_shrinkage`) | Preserved in git history only (archival) |
| PPMI + RIDER from `__planned__` adapters | `src/neurotcs/adapters/__init__.py` | Removed; archival history only |

## What was NOT touched

- `src/neurotcs/audit_core/` — the audit pipeline is disease-agnostic. Untouched.
- `src/neurotcs/input_contract/v1_1/adapters/adapter_{oasis3,nacc,adni_canonical,miriad}.py` — the four AD cohort adapters. Untouched.
- The 5 locked audit_id values (OASIS-3 `92df5429...`, ADNI `7a973f7b...`, NACC `58329c65...`, MIRIAD `abda26cb...`, MIRIAD test-retest `80430399...`) — verified byte-exact under v1.9.0.
- Historical CHANGELOG and ERRATA entries that describe the non-AD work in v1.7.x and v1.8.x — these remain as historical record.

## Scope permanence

NeuroTCS is an Alzheimer's-disease tool, and the AD-only scope is not a
temporary staging state pending a multi-disease expansion. The repository makes
no commitment to add non-AD disease coverage. Any regulatory pathway NeuroTCS
might pursue (see the Regulatory status section below) concerns the AD tool
itself; it is not a gate that "unlocks" other diseases inside this repository.

## Version markers

- v1.8.1 — last release with non-AD rule packs (tag `v1.8.1`, commit `d2865af`)
- **v1.9.0 — first AD-only release**

## Regulatory status

This section states NeuroTCS's regulatory positioning plainly, so no reader
overstates what the tool is today.

- **NeuroTCS is a research instrument.** It is not an FDA-cleared or
  CE-marked medical device, and it is not authorized for clinical use. It is a
  reproducibility and data-quality auditing tool for longitudinal AD research
  and trial data. Its outputs are cohort-level audit flags, not diagnoses,
  treatment recommendations, or per-patient clinical determinations.
- **No GxP / 21 CFR Part 11 package is claimed.** NeuroTCS does not ship an
  Installation/Operational/Performance Qualification (IQ/OQ/PQ) package, a
  validated electronic-records/electronic-signatures implementation, or a
  formal quality-management-system (QMS) dossier. None of those artifacts
  currently exist, and the tool should not be represented as GxP-compliant or
  Part 11-compliant.
- **What a regulatory pathway would require (if ever pursued).** Positioning
  NeuroTCS as software in a regulated workflow would require, at minimum: a
  defined intended-use / indications-for-use statement at device granularity; a
  QMS (e.g., ISO 13485) with design controls; risk management (ISO 14971); a
  software lifecycle process (IEC 62304); IQ/OQ/PQ qualification of each
  deployment; a Part 11-conformant audit-trail and access-control
  implementation if used for GxP records; and a clinical validation package
  including the ground-truth flag-precision study designed in
  [`VALIDATION_PROTOCOL.md`](VALIDATION_PROTOCOL.md). These are substantial,
  separate bodies of work; this repository does not assert any of them are
  complete.
- **Honest aspiration vs. claim.** Any mention elsewhere of a future FDA
  submission is an aspiration, not a current status, milestone, or commitment.
  Nothing in this repository should be read as evidence of clearance,
  submission, or regulatory engagement.

## See also

- [`CHANGELOG.md`](../CHANGELOG.md) — v1.9.0 entry for full scope-contraction patch notes
- [`docs/spec/temporalmetric_v1.7_FINAL.md`](spec/temporalmetric_v1.7_FINAL.md) — original multi-disease spec with v1.9.0 scope-override notice at top
- [`README.md`](../README.md) — public-facing 3-AD-pack table

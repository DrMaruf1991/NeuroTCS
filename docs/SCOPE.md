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
| Layer 4 · Inclusion / protocol | Does each patient and visit comply with the trial protocol? | v1.12.0 roadmap | Planned |

The Layer Contract that all layers adhere to is documented at [`docs/clinical_ranges/LAYER_CONTRACT.md`](clinical_ranges/LAYER_CONTRACT.md).

## What this means in practice

| Question | Answer |
|---|---|
| What rule packs ship in v1.x? | **Layer 1:** Exactly 3 AD packs: `ad/niaaa_2018`, `ad/aa_2024`, `ad/aa_2024_trac`<br>**Layer 2 (v1.10.0):** Exactly 6 range packs covering vitals, CSF/plasma biomarkers, MRI volumetrics, PET amyloid, AD genetics |
| What cohorts are audited under the four-cohort triangulation lock? | ADNI, OASIS-3, NACC, MIRIAD (plus MIRIAD test-retest) — all AD, Layer 1 only |
| Will Parkinson's, MS, oncology, stroke, or lung-nodule rule packs be added in v1.x? | No |
| What if I have a non-AD rule pack? | The schema (`DiseaseDomain` enum) accepts only `alzheimers` and `custom`; non-AD packs will fail validation |
| Where did the non-AD rule packs go? | Extracted at v1.9.0 to seed future per-disease repos (see [v1.9.0 CHANGELOG entry](../CHANGELOG.md#190--2026-05-24)). Recoverable from git history at tag v1.8.1 or from the offline archive `NeuroTCS-non-AD-extracted-v1.8.1.zip` |
| When will non-AD coverage return? | Each disease will get its own repository (`NeuroTCS-PD`, `NeuroTCS-MS`, `NeuroTCS-Oncology`, `NeuroTCS-Stroke`, `NeuroTCS-LungNodule`) **after** the AD core achieves FDA clearance (target Q1 2027) |
| What about Aim 5 multi-disease portability (in the v1.7 spec)? | Deferred to future per-disease repos; the v1.7 spec retains the description as historical design intent but flags it as out-of-scope for v1.x via a top-of-document override notice |

## Why this scope decision

NeuroTCS was originally designed as a multi-disease platform. As of v1.8.x, the AD validation surface had achieved byte-exact four-cohort triangulation (OASIS-3 cTCS = 0.994191, ADNI = 0.994575, NACC = 0.991502, MIRIAD = 0.985369, all 6 pairwise ΔcTCS ≤ 0.01 — the world-class threshold), while the 5 non-AD rule packs were citation-locked transcriptions but had no cohort runs and no DUAs filed.

The decision to scope-narrow to AD for v1.x was made on 2026-05-24 by Dr. Marufjon Salokhiddinov (NeuroTCS lead). The reasons:

1. **FDA clarity.** A regulator examining the Q-Submission Q1 2027 will see a tight, cohesive AD audit framework rather than a sprawling multi-disease library where 5 of 8 packs lack cohort runs.
2. **Substantive validation.** The AD validation surface is empirically demonstrated; non-AD packs are unvalidated. Shipping them mixed together blurs the distinction.
3. **Future modularity.** Each disease eventually deserves its own framework repo with its own cohort adapters, DUAs, and clinical-specialist review process — exactly the pattern of FHIR profiles or SNOMED extensions. The v1.x AD-focused product is the foundation; the per-disease repos extend it after FDA clearance.

## What was preserved

- The 5 non-AD rule pack YAMLs + 6 transcription audit docs are preserved in git history at tag `v1.8.1` (commit `d2865af`) and in an offline archive `NeuroTCS-non-AD-extracted-v1.8.1.zip` with per-disease seed READMEs.
- All historical CHANGELOG and ERRATA entries describing the non-AD work are kept verbatim (e.g., ERRATA E-2026-003 on the Marras 2002 PD citation correction). History is immutable.
- The `DiseaseDomain` enum retains `CUSTOM` so vendor-specific or research-only AD variants can still be validated.

## What was removed in v1.9.0

| Removed | Path in v1.8.1 | Replacement / where it went |
|---|---|---|
| PD/Hoehn-Yahr rule pack | `src/neurotcs/rulepack/rules/pd/hoehn_yahr.yaml` | `NeuroTCS-non-AD-extracted-v1.8.1.zip:parkinsons/`; future `NeuroTCS-PD` repo |
| MS/McDonald 2024 rule pack | `src/neurotcs/rulepack/rules/ms/mcdonald_2024.yaml` | Same archive `multiple_sclerosis/`; future `NeuroTCS-MS` |
| Oncology RECIST 1.1 + iRECIST | `src/neurotcs/rulepack/rules/oncology/` | Same archive `oncology/`; future `NeuroTCS-Oncology` |
| Stroke mRS follow-up | `src/neurotcs/rulepack/rules/stroke/mrs_followup.yaml` | Same archive `stroke/`; future `NeuroTCS-Stroke` |
| Lung-nodule Fleischner 2017 | `src/neurotcs/rulepack/rules/lung_nodule/fleischner_2017.yaml` | Same archive `lung_nodule/`; future `NeuroTCS-LungNodule` |
| 6 transcription audit docs | `docs/transcription_audit/{pd_hoehn_yahr,ms_mcdonald_2024,oncology_recist_1_1,oncology_irecist,stroke_mrs_followup,lung_nodule_fleischner_2017}.md` | Same archive per-disease subdirs |
| `DiseaseDomain` enum non-AD values | `src/neurotcs/rulepack/schema.py` (`PARKINSONS`, `MULTIPLE_SCLEROSIS`, `GLIOBLASTOMA`, `STROKE`, `CARDIOLOGY`, `ONCOLOGY`, `PULMONOLOGY`) | Future repos will ship their own enums or import from `neurotcs-core` |
| 6 non-AD-specific tests | `tests/rulepack/test_rulepack.py` (`test_pd_behaviors`, `test_ms_relapse_remission`, `test_recist_bidirectional_with_confirmation`, `test_irecist_pseudoprogression`, `test_stroke_recovery_and_death`, `test_fleischner_growth_and_shrinkage`) | Will be re-implemented in each future per-disease repo |
| PPMI + RIDER from `__planned__` adapters | `src/neurotcs/adapters/__init__.py` | Deferred to future per-disease repos |

## What was NOT touched

- `src/neurotcs/audit_core/` — the audit pipeline is disease-agnostic. Untouched.
- `src/neurotcs/input_contract/v1_1/adapters/adapter_{oasis3,nacc,adni_canonical,miriad}.py` — the four AD cohort adapters. Untouched.
- The 5 locked audit_id values (OASIS-3 `766ffc5f...`, ADNI `9e708f2e...`, NACC `def60e68...`, MIRIAD `947ab24e...`, MIRIAD test-retest `80430399...`) — verified byte-exact under v1.9.0.
- Historical CHANGELOG and ERRATA entries that describe the non-AD work in v1.7.x and v1.8.x — these remain as historical record.

## When this scope expands

The v1.x AD-only scope is in effect through:

1. v1.0.0 release at FDA Q-Submission (target Q1 2027)
2. FDA Q-Submission response and any iteration
3. FDA 510(k) or De Novo authorization, whichever the regulatory pathway determines

After FDA clearance of the AD core, future per-disease repositories will be launched independently using the v1.8.1 git history + offline archive as seed material. Each will go through its own validation, DUA filing, and clinical-specialist review independent of NeuroTCS-AD.

## Version markers

- v1.8.1 — last release with non-AD rule packs (tag `v1.8.1`, commit `d2865af`)
- **v1.9.0 — first AD-only release (this version)**
- v1.0.0 — FDA-cleared AD release (target Q1 2027, reserved)

## See also

- [`CHANGELOG.md`](../CHANGELOG.md) — v1.9.0 entry for full scope-contraction patch notes
- [`docs/spec/temporalmetric_v1.7_FINAL.md`](spec/temporalmetric_v1.7_FINAL.md) — original multi-disease spec with v1.9.0 scope-override notice at top
- [`README.md`](../README.md) — public-facing 3-AD-pack table

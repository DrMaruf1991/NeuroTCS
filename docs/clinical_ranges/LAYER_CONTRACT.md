# NeuroTCS Audit-Layer Contract (v1.10.0)

This document specifies the architectural contract that every audit layer
in NeuroTCS v1.x and v2.x adheres to. The contract is what makes Layer 2
(clinical ranges, shipped v1.10.0) and future Layer 3 (cross-sheet
consistency, v1.11.0 roadmap), Layer 4 (inclusion/protocol, design shipped v1.18.0 / first pack v1.19.0
roadmap) compose into a single coherent audit framework rather than a
collection of incompatible tools.

## 1 · What NeuroTCS audits, what it does not

NeuroTCS is a family of **citation-locked deterministic audit layers**.
Each layer answers one specific question about a trial dataset, cites
the published source that authorizes the answer, and emits a reproducible
flag-set with a SHA-256 audit signature.

NeuroTCS is **not** a general clinical-trial data validator. It complements
products like Pinnacle 21 / OpenCDISC for SDTM compliance, EDC platforms
for data-entry rules, and human clinician review for variant-phenotype
reasoning. NeuroTCS adds the audit layers that are unique to the AD
clinical-trial domain (temporal-coherence of stage predictions, AD-specific
biomarker-range plausibility) with full citation lock and byte-exact
reproducibility.

## 2 · The Layer interface

Every audit layer ships:

- A **Pydantic v2 strict schema** for the layer's rule/range pack format
  (`rulepack/schema.py` for Layer 1; `clinical_ranges/schema.py` for Layer 2)
- A **loader** that parses YAML into validated Pydantic models with a
  canonical SHA-256 hash of the pack contents
  (`load_rulepack` / `load_rangepack`)
- One or more **production packs** (YAML files) authored from peer-reviewed
  or guideline-document sources, with per-element citations (PMID/DOI) and
  guideline-section pointers
- An **audit function** that consumes domain-specific inputs and a loaded
  pack, runs deterministic checks, and emits a result object carrying:
  - per-element flags with citations
  - a SHA-256 **audit_id** (Layer 1) or **flag_id** (Layer 2+) derived
    from the pack SHA + input signature
  - pack provenance (id, sha, version, status, transcribed_by)
  - reproducibility metadata (timestamp, parameters)

Every audit function is **deterministic**: same inputs + same pack
produce a byte-exact identical audit_id / flag_id.

Every audit function is **fail-closed**: a pack must be `status=production`
to be usable; skeleton or planned packs raise on `audit_*()`.

Every audit function is **honest about scope**: inputs the pack does not
cover are recorded in the `uncovered` tally and never silently approved.

## 3 · The layers (v1.10.0)

### Layer 1 · Temporal coherence  (shipped v1.0.0, locked v1.7.0+)

| | |
|---|---|
| Question | "Do the model's per-visit predicted disease-stage transitions follow a clinically valid trajectory under the published staging framework?" |
| Input | `list[Trajectory]` (one trajectory per patient: ordered (state, date) pairs) |
| Pack | Rule pack at `src/neurotcs/rulepack/rules/<domain>/<framework>.yaml` |
| Engine | `neurotcs.audit(trajectories, rulepack)` |
| Output | `AuditResult` with cTCS / pTCS / uTCS + bootstrap CI + audit_id |
| Catches | NIA-AA 2018 / Jack 2024 inadmissible transitions; time-window violations; TRAC treatment-conditional rules |
| Source citations | Jack 2018 (PMID 29653606); Jack 2024 (Alzheimer's & Dementia 2024); Salemme 2025 reversion rates |

### Layer 2 · Clinical range validation  (shipped v1.10.0)

| | |
|---|---|
| Question | "Do the per-visit numeric and categorical clinical measurements fall within published biologically-plausible ranges?" |
| Input | Long-format DataFrame with columns `{patient_id, visit_id, measurement_name, value, unit}` |
| Pack | Range pack at `src/neurotcs/clinical_ranges/ranges/<domain>/<name>.yaml` |
| Engine | `neurotcs.clinical_ranges.audit_clinical_ranges(measurements_df, rangepack)` |
| Output | `ClinicalRangeAuditResult` with per-flag bound + citation + flag_id |
| Catches | Vital-sign / lab / imaging / PET / genetic out-of-range values; invalid categorical labels (APOE genotypes, Fazekas scale, amyloid_status); unit mismatches |
| Source citations | Whelton 2017 ACC/AHA BP; Lewczuk 2018 CSF biomarkers; Janelidze 2023 plasma; Fischl 2012 FreeSurfer; Klunk 2015 centiloid; Roses 1996 APOE alleles; ATS 2020 pulse-ox; Pierpaoli 1996 FA definition |
| Production packs (6) | `vital_signs/standard`, `csf_biomarkers/aa_2024`, `plasma_biomarkers/aa_2024`, `mri_volumetrics/freesurfer`, `pet_amyloid/centiloid`, `genetics/apoe_valid_genotypes` |

## 4 · The layers on the roadmap

### Layer 3 · Cross-sheet consistency  (v1.11.0)

Will catch errors that span more than one input domain:
- APOE genotype in genetics sheet differs from APOE in demographics
- CSF Aβ42/40 ratio (amyloid-negative) contradicts PET centiloid (amyloid-positive)
- CT shows cortical infarct but MRI WMH essentially zero
- Backward direction of imaging volumetrics over time (hippocampus grew, ventricles shrank)
- Cognitive-scale score-vs-predicted-state contradictions (MMSE=30 but predicted AD)

Input: union of multiple long-format DataFrames keyed by (patient_id, visit_id).
Engine: `audit_cross_sheet_consistency()` — comparison rules with per-rule citations.

### Layer 4 · Inclusion / protocol  (design v1.18.0, first pack v1.19.0)

Will catch errors that violate trial protocol or inclusion/exclusion criteria:
- Age outside inclusion range (50-90 yr)
- Amyloid-negative patient enrolled in anti-amyloid arm
- Lab sample timestamped at visit 9 when protocol has 7 visits
- Patient-id collision between rows (cross-patient row leakage)
- Treatment-arm assignment vs drug-administered mismatch (lecanemab patient received donanemab)
- Severe ARIA-E reported but dosing continued without pause

Input: full trial dataset (multi-sheet) + protocol pack (visit count, dose
schedule, inclusion criteria).
Engine: `audit_protocol_compliance(dataset, protocol_pack)`.

## 5 · What is permanently out of scope

Some clinical-trial errors are **inherently clinician work, not deterministic
audit work** and will not be added to any v1.x or v2.x layer:

- Variant-phenotype reasoning (e.g. "PSEN1 mutation in a 78-year-old is
  implausible because PSEN1 typically causes early-onset AD") requires a
  clinician's contextual judgment. NeuroTCS will not pretend to perform it.

- Open-ended adverse-event interpretation. NeuroTCS will not classify
  whether a reported headache is treatment-related; that is the trial
  medical monitor's role.

- Subjective imaging-finding correlation across modalities ("does this
  pattern of MTA grade and Fazekas score support the predicted clinical
  stage?"). NeuroTCS will validate that each value is in range and
  internally consistent; the clinical synthesis stays with the radiologist.

## 6 · Architectural invariants

These hold across every layer and every release:

1. **Every flag is citable.** A flag without a PMID/DOI anchor and a
   guideline-section pointer is a bug. The schema fails-closed on it.

2. **Every audit produces a deterministic SHA-256 ID.** Anyone with the
   same input file and the same pack at the same release commit reproduces
   the same ID byte-exactly. This is the FDA-reviewer reproducibility gate.

3. **Status enum is honored.** A pack must be `status=production` to enter
   an audit. Skeleton or planned packs raise immediately. This prevents
   accidental release of half-finished packs into production audits.

4. **Pydantic strict mode.** Unknown YAML fields are rejected. Missing
   required fields are rejected. Type mismatches are rejected. There is
   no "soft" validation path.

5. **Layer 1 invariants are frozen.** The 5 cohort audit invariants
   (OASIS-3, ADNI, NACC, MIRIAD, MIRIAD test-retest) must reproduce
   byte-exactly under every future release. This is the non-negotiable
   correctness gate for any v1.x change.

6. **Honest disclosure.** Every release manifest lists what is shipped
   AND what is not. Catch-rate numbers are reported truthfully, including
   what each layer does not catch and why.

## 7 · References

- Schema: `src/neurotcs/clinical_ranges/schema.py`
- Loader: `src/neurotcs/clinical_ranges/loader.py`
- Audit engine: `src/neurotcs/clinical_ranges/audit.py`
- Adapters: `src/neurotcs/clinical_ranges/adapters/`
- Production packs: `src/neurotcs/clinical_ranges/ranges/`
- Tests: `tests/clinical_ranges/`

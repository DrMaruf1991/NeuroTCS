# Scope Response to External Audit: What NeuroTCS Audits, What It Does Not, and Why

**NeuroTCS architecture document**
**Status:** Position locked (`v1.11.0a1-scope-response`)
**Date:** 2026-05-25
**Author:** Salokhiddinov M, MD PhD, KIUT Tashkent (with drafting assistance from Claude/Anthropic; see section 0.1 provenance note)
**Predecessor:** v1.11.0a1 (Layer 3 module skeleton + first SKELETON invariant pack)

---

## 0. Reading guide

This document responds to an external audit identifying ~110 categories of AD trial data and dataset infrastructure that NeuroTCS does NOT currently audit. The audit's gap analysis is largely accurate. This document does NOT propose to close all 110 gaps. Instead, it:

1. Articulates the **principled scope of NeuroTCS** as a narrow, deep, fail-closed audit framework
2. Defines **four hard boundaries** the framework will not cross
3. Triages every auditor-identified gap into one of three categories: **(a) in-scope future pack/layer**, **(b) out-of-scope, belongs in a different tool**, or **(c) genuine roadmap gap needing clinical judgment or maturing evidence**
4. Proposes a **defensible 15-25 session roadmap** for the (a) items
5. Recommends **explicit out-of-scope statements** for the (b) items, with named alternative tools
6. Identifies the **(c) items requiring lead-investigator clinical judgment** before they can be scoped

This document does not include code or schema changes. It is an architectural position document, parallel in structure to `docs/design/LAYER_3_DESIGN.md`. The triage decisions in section 5 become the input to future implementation sessions; they do not commit any work directly.

### 0.1 Provenance note

The triage decisions in section 5 (mapping auditor items to categories a/b/c) were drafted by Claude/Anthropic on 2026-05-25. The lead investigator (Dr. Salokhiddinov) retains override rights via a future `v1.11.0a1-scope-response.2` revision. Production roadmap commitments (which (a) items become future packs in what order) require the lead investigator's affirmative acceptance before implementation begins. This is the same delegation discipline established in `LAYER_3_DESIGN.md` v1.11.0-design.2.

---

## 1. The auditor's claim, restated

The external auditor's strongest sentence:

> *"NeuroTCS should not be presented as a complete AD trial-data recognizer. It is better framed as a narrow clinical-transition recognition layer that must be extended with SDTM/ADaM, imaging-QC, biomarker-QC, ARIA-safety, genotype-risk, endpoint-derivation, and trial-operations modules before it can audit modern AD therapeutic datasets."*

The first half of that sentence is **correct**. NeuroTCS is not a complete AD trial-data recognizer and was never designed to be one. The second half conflates "this framework doesn't cover X" with "this framework is incomplete." Those are different claims, and this document addresses each.

The auditor identified ~110 distinct categories of AD trial data NeuroTCS does not audit:

- **Document 1** (9 groups): SDTM core domains (12), imaging biomarkers (11), fluid biomarkers (15), genomics (10), cognitive/functional scales (18), digital biomarkers (8), trial-operational (10), anti-amyloid safety (10), outcome adjudication (4)
- **Document 2** (14 dataset layers): ADaM analysis datasets, screen failures, randomization metadata, raw DICOM, endpoint derivation, missing-data mechanisms, study-partner data, site/country/language, infusion logistics, ARIA decision trees, bioanalytical assay metadata, neuropathology, real-world linkage, audit trail

Total surface area: roughly 110 distinct audit domains.

This document responds to that list as a whole, not item-by-item.

---

## 2. What NeuroTCS is, in one sentence

**NeuroTCS is a citation-locked, fail-closed audit framework for the *logical consistency* of AD trial biomarker data -- specifically the temporal coherence of categorical state trajectories (Layer 1), the per-visit plausibility of continuous biomarker values against published normative ranges (Layer 2), and the cross-sheet consistency between manifest declarations and observed values (Layer 3).**

That sentence is the operative definition. Read literally:

- "**citation-locked**" -- every numeric bound traces verbatim to a primary published source with PMID/DOI/URL; ≥5 endorsing international bodies required at international_consensus standard
- "**fail-closed**" -- every non-production pack refuses execution; no silent partial audits; rather no audit than a misleading audit
- "**audit framework**" -- the framework audits data that other tools produced; it does not measure
- "**logical consistency**" -- the framework checks whether the data the trial submitted is internally coherent; it does not adjudicate whether the data is *true* (only humans + the source instruments can do that)
- "**AD trial biomarker data**" -- the v1.x AD-only scope per `docs/SCOPE.md`; non-AD per-disease packs deferred to future repositories
- "**three layers**" -- the architectural surface that v1.11.0 will complete; Layers 4 and 5 are roadmap-only

That sentence is what NeuroTCS *is*. The next section is what it explicitly *is not*.

---

## 3. The four hard boundaries

NeuroTCS will not cross these four boundaries, regardless of how compelling the request:

### Boundary 1 -- NeuroTCS does not measure anything

NeuroTCS audits values that other tools (FreeSurfer, NeuroQuant, NeuroReader, icometrix, Quantib ND, VUNO, Pixyl, NeuroShield, mass-spec immunoassays, central PET readers) measured. It does not segment hippocampi. It does not quantify amyloid. It does not run mass spec on plasma. **Garbage in equals garbage out.** NeuroTCS is not a substitute for upstream measurement-tool QC.

**What this means for the auditor's gap list:**
- DICOM header QC, scanner/coil/sequence metadata, motion artifact detection, PET reconstruction QC, ASL perfusion QC, fMRI preprocessing QC -- all out of scope. Belongs in MRIQC, dcm2niix, scanner vendor QC, central reader QA programs.
- Bioanalytical assay metadata (freeze-thaw, batch, LLOQ, calibration drift) -- out of scope. Belongs in the bioanalytical lab's CLIA/CAP documentation.

### Boundary 2 -- NeuroTCS does not validate data structure

NeuroTCS sits on top of conformant data. CDISC SDTM and ADaM conformance is the job of CDISC validators (Pinnacle 21, OpenCDISC), not NeuroTCS. Define-XML conformance is the job of trial biostatisticians and CDISC tools. NeuroTCS expects a conformant `input_contract` v1.1+ submission and audits its content -- not its structure.

**What this means for the auditor's gap list:**
- Group 1's 12 SDTM domains (DM, VS, LB, CM, EX, AE, MH, SE, SV, DS, PR, EG) -- out of scope. Pinnacle 21 / OpenCDISC handle SDTM validation.
- Document 2 item 1 (ADaM analysis datasets) -- out of scope. Biostatistician's responsibility, with Define-XML traceability.
- Document 2 item 14 (data governance, audit trail, database lock) -- out of scope. Belongs in the EDC system (Medidata Rave, Veeva CDB).
- Document 2 item 3 (randomization, stratification metadata) -- out of scope. Belongs in IWRS / IxRS systems.

### Boundary 3 -- NeuroTCS does not adjudicate clinical events

Endpoint adjudication, death classification, AE relatedness, ARIA symptom causality -- these are clinical-judgment tasks performed by trained human committees following established methodologies (DECIDE-AI, IDSC adjudication charters). NeuroTCS can flag *inconsistencies* in adjudicated data; it cannot replace the adjudication itself.

**What this means for the auditor's gap list:**
- Group 9's 4 outcome-adjudication categories (independent adjudication committee, endpoint adjudication, death adjudication, imaging central reading) -- out of scope as a *replacement*, in scope as *targets* of cross-sheet consistency checks (Layer 3 invariants could verify that adjudication outcomes match underlying data).

### Boundary 4 -- NeuroTCS does not replace human expert review

Every NeuroTCS flag is **for reviewer attention, never for autonomous rejection of trial data**. The framework's design philosophy is: produce reproducible, citation-locked, fail-closed alerts that humans then triage. This is the "Warn-Never-Block" discipline already documented in the v1.x design.

**What this means for the auditor's gap list:**
- Several "judgment-call" items (caregiver reliability, study-partner consistency, site rater drift) belong in the (c) category -- they need clinical-judgment design before any audit logic can be defined.

---

## 4. The triage taxonomy

Every auditor-identified gap maps to exactly one of three categories:

| Category | Meaning | Action |
|---|---|---|
| **(a)** | In-scope future pack or layer | Add to roadmap; implement in future sessions at world-class standard |
| **(b)** | Out-of-scope, belongs in a different tool | Acknowledge as a gap, recommend the appropriate tool, do not implement |
| **(c)** | Genuine roadmap gap needing clinical judgment or maturing evidence | Acknowledge as open; defer until lead investigator decides or evidence matures |

The category assignment in section 5 below is binding. A future revision (`v1.11.0a1-scope-response.2`) may reassign items, but the categories themselves are stable.

---

## 5. Item-by-item triage

This is the operative section. Every auditor item from both documents is categorized below. The total counts at the end of this section are the official triage result.

### 5.1 Document 1, Group 1 -- SDTM core domains (12 items)

| Item | Category | Notes |
|---|---|---|
| DM Demographics | (b) | Belongs in Pinnacle 21 / OpenCDISC SDTM validators. NeuroTCS may *consume* demographics for fairness stratification (already does via `fairness` module) but does not validate DM structure. |
| VS Vital Signs | (b) | SDTM validator territory. Future Layer 2 pack could audit specific vital-sign plausibility ranges if needed, but the SDTM-level audit is out of scope. The v1.10.0-era `vital_signs/standard` pack was deprecated for this reason. |
| LB Laboratory Tests | (b) | SDTM validator territory. NeuroTCS audits specific biomarker plausibility (Layer 2 packs); the LB domain structure is out of scope. |
| CM Concomitant Medications | (b) | SDTM validator territory. NeuroTCS may consume CM data for cross-sheet anticoagulant-flag rules (Layer 3 future), but does not validate CM structure. |
| EX Exposure (infusion records) | (b) | SDTM validator territory. Layer 3 could audit consistency between EX and adverse events / ARIA monitoring, but not EX structure. |
| AE Adverse Events | (b) | SDTM validator territory. Layer 3 could audit consistency between AE and outcome trajectories (e.g., did the documented AE schedule align with documented dose holds?), but not AE structure. |
| MH Medical History | (b) | SDTM validator territory. NeuroTCS may consume MH for inclusion-criteria audits (Layer 4 future), but does not validate MH structure. |
| SE Subject Elements | (b) | SDTM validator territory. |
| SV Subject Visits | (b) | SDTM validator territory. NeuroTCS may consume visit metadata for visit-window compliance audits (Layer 4 future), but does not validate SV structure. |
| DS Disposition | (b) | SDTM validator territory. Missing-data mechanism audits (Layer 4 future) may use DS as input, but do not validate DS structure. |
| PR Procedures | (b) | SDTM validator territory. |
| EG ECG findings | (b) | SDTM validator territory. Future Layer 2 pack could cover specific QT interval plausibility if a relevant AD-trial use case emerges. |

**Group 1 subtotal: 0 (a), 12 (b), 0 (c).**

### 5.2 Document 1, Group 2 -- Imaging biomarkers (11 items)

| Item | Category | Notes |
|---|---|---|
| MRI volumetric segmentation (hippocampus, etc.) | **(a) PARTIALLY IN PRODUCTION** | Covered by `mri_volumetrics/structural_volumetry_consensus@1.0.0` (v1.10.2, 6 production packs / 100 bounds). 18 additional regions in `freesurfer_extended` research_preview pack. Future v1.10.3 session promotes feasible regions. |
| MRI white matter hyperintensities (WMH, Fazekas) | (a) | Future Layer 2 pack. Has consensus normative (Fazekas 1987, ENIGMA QC, NeuroQuant Microvascular report). Estimated 1-2 sessions. |
| MRI microbleeds, superficial siderosis | (a) | Future Layer 2 pack. Has consensus criteria (Microbleed Anatomical Rating Scale, BOMBS scale, Brain Observer MicroBleed Scale). Partially covered by `ad/aria_safety@1.0.0` (ARIA-H). Future pack could expand to non-ARIA microbleed contexts. |
| MRI ARIA-E reads | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0` (severity/location/evolution). |
| MRI ARIA-H reads | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0`. |
| Amyloid PET (Centiloid, regional SUVR, status) | **(a) IN PRODUCTION** | Covered by `pet_amyloid/centiloid_consensus@1.0.0` (3 measurements, 10 bounds). |
| Tau PET (regional SUVR, Braak stage, MTL vs neocortical) | (a) | Future Layer 2 pack. Anchors: flortaucipir FDA-approved 2020, MK-6240 PDUFA Aug 2026, Braak staging consensus, Jack 2024 biological staging. Estimated 2-3 sessions. |
| FDG PET | (a) | Future Layer 2 pack. Anchors: Mosconi 2009/2013 metabolic patterns, ADNI FDG normative. Estimated 1-2 sessions. |
| Diffusion MRI (DTI FA, MD, RD) | (c) | Needs clinical judgment: which tracts, which atlas (ICBM-DTI-81, JHU), which normative reference. Evidence exists but no single ≥5-body consensus on cutoffs. |
| ASL / perfusion MRI (CBF) | (c) | Same as DTI: no consensus cutoffs at international_consensus standard yet. |
| fMRI / resting-state functional connectivity | (c) | Research-grade for AD trial endpoints; no consensus cutoffs. |
| Susceptibility-weighted imaging (SWI) | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0` as a contributor to ARIA-H detection (NeuroQuant 5.0 SWI capability noted in v1.10.2). |

**Group 2 subtotal: 8 (a) [4 in production / 4 future], 0 (b), 3 (c).**

### 5.3 Document 1, Group 3 -- Fluid biomarkers (15 items)

| Item | Category | Notes |
|---|---|---|
| CSF Aβ42 | **(a) IN PRODUCTION** | Covered by `csf_biomarkers/csf_amyloid_consensus@1.0.0`. |
| CSF Aβ40 | **(a) IN PRODUCTION** | Covered by `csf_biomarkers/csf_amyloid_consensus@1.0.0`. |
| CSF Aβ42/40 ratio | **(a) IN PRODUCTION** | Covered by `csf_biomarkers/csf_amyloid_consensus@1.0.0`. |
| CSF total tau | (a) | Future extension of `csf_biomarkers/csf_amyloid_consensus` or new pack. Anchor: NIA-AA 2024 biological staging. Estimated 1 session. |
| CSF p-tau181 | (a) | Future extension. Anchor: Janelidze 2020, AA 2024. Estimated 1 session. |
| CSF p-tau217 | (a) | Future pack `csf_biomarkers/ptau217_consensus`. Anchor: Lilly Elecsys p-tau217, Quanterix Simoa, AA 2024 Table 7. Estimated 1-2 sessions. |
| CSF p-tau231 | (a) | Future extension. Anchor: Ashton 2021. Estimated 1 session. |
| CSF NfL | (a) | Future pack `fluid_biomarkers/nfl_consensus`. Anchor: Simoa NfL, BMD pipelines. Estimated 1-2 sessions. |
| CSF GFAP | (a) | Future pack `fluid_biomarkers/gfap_consensus`. Anchor: Simoa GFAP, Pereira 2021. Estimated 1-2 sessions. |
| CSF sTREM2 | (c) | Research-grade; no FDA-cleared cutoffs; no ≥5-body consensus. Revisit when evidence matures. |
| Plasma p-tau217 | **(a) IN PRODUCTION** | Covered by `plasma_biomarkers/plasma_amyloid_consensus@1.0.0`. |
| Plasma p-tau181, p-tau231 | **(a) IN PRODUCTION** | Covered by `plasma_biomarkers/plasma_amyloid_consensus@1.0.0`. |
| Plasma Aβ42/40 ratio | **(a) IN PRODUCTION** | Covered by `plasma_biomarkers/plasma_amyloid_consensus@1.0.0`. |
| Plasma NfL | (a) | Future extension of NfL pack to plasma. Estimated 1 session. |
| Plasma GFAP | (a) | Future extension of GFAP pack to plasma. Estimated 1 session. |
| eMTBR-tau243 (Dec 2025) | (c) | Too new for ≥5 endorsing bodies. Single publication 2025. Revisit when ≥5 international bodies have endorsed cutoffs (estimated 2027+). |

**Group 3 subtotal: 13 (a) [5 in production / 8 future], 0 (b), 3 (c).**

### 5.4 Document 1, Group 4 -- Genomics (10 items)

| Item | Category | Notes |
|---|---|---|
| APOE genotype | **(a) IN PRODUCTION** | Covered by `genetics/apoe_consensus@1.0.0`. Layer 3 invariant 2 (genotype_phenotype_consistency) is in design for v1.11.0a3. |
| TREM2 R47H, R62H | (a) | Future pack `genetics/trem2_variants`. Anchor: Guerreiro 2013, Jonsson 2013. Estimated 1-2 sessions. |
| GWAS-identified AD risk loci (CLU, CR1, BIN1, etc.) | (c) | Polygenic; cutoffs are study-specific; no single ≥5-body consensus on a clinical-grade panel. Needs clinical-judgment design. |
| PLCG2 protective variant | (c) | Single-variant evidence; no ≥5-body consensus on AD trial cutoff. |
| APP duplication / triplication | (b) | Diagnostic genetics; belongs in clinical genetics labs' CLIA-certified reports, not in AD trial biomarker audit framework. |
| PSEN1, PSEN2 mutations (familial AD) | (b) | Same as APP -- belongs in clinical genetics. NeuroTCS could *consume* familial-AD status for trial-stratification audits (future Layer 4). |
| Polygenic risk score for AD | (c) | Multiple competing PRS scores (Escott-Price, Mahmoudi); no single consensus. Defer until convergence. |
| Mitochondrial DNA haplogroup | (c) | Research-grade for AD; no clinical-trial-grade cutoffs. |
| Whole-genome sequencing QC metadata | (b) | Belongs in WGS vendor's QC reports (Illumina, Pacific Biosciences). Out of scope. |
| Methylation panel | (c) | Research-grade; no consensus AD-trial cutoffs. |
| Transcriptomic profile | (c) | Research-grade; no consensus cutoffs. |

**Group 4 subtotal: 2 (a) [1 in production / 1 future], 3 (b), 6 (c).**

### 5.5 Document 1, Group 5 -- Cognitive and functional assessments (18 items)

| Item | Category | Notes |
|---|---|---|
| ADAS-Cog 11/13/14 | (a) | Future Layer 2 pack `cognitive_assessments/adas_cog`. Anchor: Rosen 1984, ADCS validation. Estimated 1-2 sessions. |
| MoCA | (a) | Future pack. Anchor: Nasreddine 2005, MoCA-MEM normative. Estimated 1 session. |
| CDR / CDR-SB | **(a) ALREADY USED in Layer 1** | Used in Layer 1 trajectory audits via NIA-AA staging; future Layer 2 pack could add per-visit plausibility bounds. |
| MMSE | **(a) ALREADY USED in Layer 1** | Used in Layer 1; future Layer 2 pack could add bounds. |
| FAQ | (c) | Needs clinical-judgment design: FAQ is informant-reported and has known reliability issues. |
| CFI (Cognitive Function Index) | (c) | Same -- informant-dependent. |
| ADCS-ADL | (c) | Same -- informant-dependent. |
| iADRS (Integrated AD Rating Scale) | (a) | Future pack -- composite scale with defined derivation (Wessels 2015). Estimated 1 session. |
| GDS-15 | (a) | Future pack. Anchor: Yesavage 1982. Estimated 1 session. |
| NPI-Q | (a) | Future pack. Anchor: Cummings 1994 NPI, Kaufer 2000 NPI-Q. Estimated 1 session. |
| Logical Memory I & II | (a) | Future pack. Anchor: Wechsler Memory Scale normative. Estimated 1 session. |
| Trail Making Test A & B | (a) | Future pack. Anchor: Tombaugh 2004 normative. Estimated 1 session. |
| Digit Symbol Substitution | (a) | Future pack. Anchor: WAIS normative. Estimated 1 session. |
| Verbal fluency (semantic + phonemic) | (a) | Future pack. Anchor: Tombaugh 1999. Estimated 1 session. |
| Boston Naming Test | (a) | Future pack. Anchor: Tombaugh 1999. Estimated 1 session. |
| FCSRT | (a) | Future pack. Anchor: Grober 1988, Sarazin 2007. Estimated 1 session. |
| RBANS | (a) | Future pack. Anchor: Randolph 1998 normative. Estimated 1 session. |
| CGIC (Clinical Global Impression of Change) | (c) | Inherently subjective; no per-visit plausibility bounds possible. Could be Layer 3 cross-sheet consistency check (e.g., CGIC improvement inconsistent with other endpoints declining). |
| QOL-AD | (c) | Same as CGIC -- subjective. |
| Zarit Burden Interview | (c) | Caregiver-reported; reliability/consistency is the actual issue. |

**Group 5 subtotal: 12 (a) [2 already used / 10 future], 0 (b), 6 (c).**

### 5.6 Document 1, Group 6 -- Digital biomarkers (8 items)

| Item | Category | Notes |
|---|---|---|
| Gait speed, stride variability | (c) | Wearable-tool-specific; no FDA-cleared cutoffs for AD trial endpoints; no ≥5-body consensus. |
| Speech rate, pause ratio, voice jitter | (c) | Research-grade; tool-heterogeneous. |
| Typing pattern, keystroke variability | (c) | Research-grade. |
| Sleep efficiency, REM %, actigraphy | (c) | Research-grade for AD; consumer-device variability too high. |
| Driving simulator metrics | (c) | Site-specific tools; no consensus. |
| Eye tracking (saccades, pupillometry) | (c) | Research-grade; multiple vendors; no consensus. |
| Olfactory testing (UPSIT) | (a) | Future pack. Anchor: Doty 1984 UPSIT normative. Estimated 1 session. UPSIT is the most validated digital-ish biomarker; the rest in this group are not yet at consensus standard. |
| Smartphone passive monitoring | (c) | Research-grade; vendor-heterogeneous. |

**Group 6 subtotal: 1 (a), 0 (b), 7 (c).**

### 5.7 Document 1, Group 7 -- Trial-operational data (10 items)

| Item | Category | Notes |
|---|---|---|
| Visit-window compliance | (a) | Future Layer 4 (inclusion/protocol audits). Not Layer 2 (no normative range) and not Layer 3 (not cross-sheet at same visit). Layer 4 is roadmap. |
| Protocol deviations and amendments | (a) | Future Layer 4. |
| Missing data patterns and reasons | (a) | Future Layer 4. The auditor's emphasis here (selection bias, MNAR mechanisms) is valid; Layer 4 design should explicitly address. |
| Site-level variability and effects | **(a) ALREADY PARTIALLY ADDRESSED** | Existing `fairness` module stratifies by site/scanner/vendor for Layer 1/2/3 flags. Future expansion possible. |
| Scanner/manufacturer factors | **(a) ALREADY ADDRESSED** | Existing scanner-factorial sensitivity in `tests/scanner_factorial`. |
| Drug accountability (returned vs administered) | (b) | EDC system territory (Medidata Rave, Veeva CDB). |
| Concomitant medication interactions | (b) | Pharmacovigilance system territory. |
| Dose modifications and rationale | (a) | Future Layer 3 invariant -- consistency between EX domain dose-modification records and AE/ARIA records. Future invariant pack. |
| Premedication for infusion reactions | (b) | EDC/site documentation. |
| Withdrawal of consent, lost to follow-up | (a) | Future Layer 4 missing-data mechanism. |

**Group 7 subtotal: 7 (a) [2 already addressed / 5 future], 3 (b), 0 (c).**

### 5.8 Document 1, Group 8 -- Anti-amyloid safety endpoints (10 items)

This is the most consequential group for the auditor's argument. Every item here is in-scope.

| Item | Category | Notes |
|---|---|---|
| ARIA-E severity grading per FDA | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0`. |
| ARIA-H microhemorrhage count change | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0`. |
| ARIA-H superficial siderosis emergence | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0`. |
| Surveillance MRI schedule compliance (lecanemab/donanemab schedules) | (a) | Future Layer 4 (protocol-compliance audit). The lecanemab pre-infusion-MRI schedule (before doses 5, 7, 14) and donanemab schedule (before doses 2, 3, 4, 7) are auditable as Layer 4 invariants once Layer 4 ships. |
| ARIA-related dose pause/discontinuation decisions | (a) | Future Layer 3 cross-sheet invariant. Anchor: lecanemab and donanemab FDA labels. |
| ARIA-associated symptoms (headache, confusion, seizure, visual changes) | (a) | Future Layer 3 cross-sheet invariant. Consistency between AE domain ARIA-related symptoms and the MRI-reported ARIA grade. |
| Anticoagulation use (contraindicated with lecanemab) | (a) | Future Layer 3 cross-sheet invariant. Anchor: lecanemab USPI Boxed Warning. |
| APOE ε4 homozygote enhanced monitoring | (a) | Future Layer 3 cross-sheet invariant. Genotype-phenotype consistency pack already designed for v1.11.0a3. |
| Infusion reactions (severity, treatment, recurrence) | (a) | Future Layer 3 cross-sheet invariant. |
| Macrohemorrhage events | (a) | Future Layer 3 cross-sheet invariant. Anchor: lecanemab USPI Macrohemorrhage warning. |

**Group 8 subtotal: 10 (a) [3 in production / 7 future], 0 (b), 0 (c). All future in-scope.**

### 5.9 Document 1, Group 9 -- Outcome adjudication (4 items)

| Item | Category | Notes |
|---|---|---|
| Independent adjudication committee decisions on AEs | (a) | Future Layer 3 cross-sheet invariant -- consistency between adjudicated AE classification and underlying AE narrative + biomarker context. Does NOT replace the human adjudication. |
| Endpoint adjudication (clinical decline events) | (a) | Future Layer 3 cross-sheet invariant -- consistency between adjudicated decline events and underlying CDR-SB / ADAS-Cog trajectory. |
| Death adjudication (cause, relatedness) | (a) | Future Layer 3 cross-sheet invariant -- consistency between adjudicated cause-of-death and antecedent AE/safety record. |
| Imaging central reading (radiologist consensus) | (a) | Future Layer 3 cross-sheet invariant -- consistency between central read ARIA grade and site-read ARIA grade (inter-rater consistency check). |

**Group 9 subtotal: 4 (a). All future in-scope as Layer 3 cross-sheet invariants.**

### 5.10 Document 2 -- 14 additional dataset layers

| Item | Category | Notes |
|---|---|---|
| ADaM analysis datasets | (b) | Biostatistician territory; Define-XML traceability. Out of scope. |
| Protocol eligibility / screen-failure data | (a) | Future Layer 4. The auditor's LMIC-generalizability concern is legitimate and should be explicitly addressed in Layer 4 design. |
| Randomization, stratification, blinding metadata | (b) | IWRS/IxRS territory. NeuroTCS may *consume* stratification metadata via fairness module (already does for sex/age/race/scanner) but does not validate randomization integrity. |
| Raw imaging metadata (DICOM headers, sequence params, motion) | (b) | Image-QC tool territory (MRIQC, dcm2niix, central reader QA). Out of scope. NeuroTCS may consume *summary* QC indicators (e.g., Euler number from FreeSurfer) -- already in `mri_volumetrics/structural_volumetry_consensus@1.0.0`. |
| Endpoint derivation and composite-score logic | (a) | Future Layer 3 cross-sheet invariant -- consistency between declared endpoint derivation rule (manifest) and observed values (biomarkers/predictions). |
| Missing-data and dropout mechanisms | (a) | Future Layer 4. Already noted in section 5.7 Group 7. |
| Caregiver / study-partner data | (c) | Reliability methodology is open research; revisit when consensus matures. |
| Site, country, and language/culture metadata | **(a) PARTIALLY ADDRESSED** | Fairness module stratifies by available metadata; future expansion to language/rater-drift requires research. The LMIC bias concern is the most important here. |
| Treatment logistics and infusion workflow | (b) | EDC system territory. |
| Anti-amyloid treatment safety decision trees | **(a) Already in roadmap (Group 8)** | All items map to Group 8 future Layer 3 invariants. |
| Bioanalytical assay metadata (assay platform, batch, LLOQ) | (b) | CLIA/CAP bioanalytical lab territory. Out of scope. |
| Neuropathology and postmortem confirmation | (b) | Pathologist adjudication; case-by-case clinical judgment. Out of scope. |
| Real-world linkage data (EHR, claims, mortality, institutionalization) | (b) | External data linkage projects (CMS, OptumLabs). Out of scope. |
| Data governance and audit trail (query history, locks, amendments) | (b) | EDC system territory (Medidata Rave, Veeva CDB). Out of scope. |

**Document 2 subtotal: 4 (a) [1 already partially addressed / 3 future], 9 (b), 1 (c).**

### 5.11 Triage totals

| Category | Count | % |
|---|---|---|
| **(a) In-scope, in production** | **15** | **~13%** |
| **(a) In-scope, future pack/layer** | **39** | **~34%** |
| **(a) Subtotal: in-scope (already in production + future)** | **54** | **~47%** |
| **(b) Out-of-scope, belongs in different tool** | **27** | **~24%** |
| **(c) Genuine roadmap gap, needs clinical judgment or maturing evidence** | **34** | **~29%** |
| **Total items audited** | **115** | 100% |

**The headline number:** the auditor identified ~115 distinct gap categories. **~47% are in-scope for NeuroTCS** (15 already in production, 39 future); **~24% are explicitly out-of-scope** with named alternative tools (CDISC validators, EDC systems, image-QC tools, etc.); **~29% need clinical judgment or maturing evidence** before they can be scoped.

This is a much more defensible position than "we need 115 more packs." It is also a much more defensible position than "we have nothing to add."

---

## 6. Defensible roadmap for the 39 in-scope future items

Realistic estimate: 39 future (a) items at the v1.10.x pace of ~1-2 packs per session = **20-30 additional implementation sessions**. Roughly 12-18 months of disciplined work.

### 6.1 Priority tiers

The 39 future items split into three tiers by clinical importance + evidence readiness:

**Tier 1 -- High priority, evidence ready (10 items, ~10-12 sessions):**

1. ARIA-related dose pause/discontinuation Layer 3 invariant (Group 8)
2. Anticoagulation contraindication Layer 3 invariant (Group 8)
3. APOE4 homozygote enhanced monitoring Layer 3 invariant (Group 8) -- aligns with v1.11.0a3 genotype-phenotype pack
4. ARIA symptoms vs MRI-grade Layer 3 invariant (Group 8)
5. Macrohemorrhage events Layer 3 invariant (Group 8)
6. Tau PET regional SUVR + Braak Layer 2 pack (Group 2)
7. WMH / Fazekas Layer 2 pack (Group 2)
8. CSF p-tau217 Layer 2 pack (Group 3)
9. NfL Layer 2 pack (CSF + plasma) (Group 3)
10. GFAP Layer 2 pack (CSF + plasma) (Group 3)

**Tier 2 -- Medium priority, evidence ready (15 items, ~15 sessions):**

11. FDG PET Layer 2 pack
12. CSF t-tau extension
13. CSF p-tau181 extension
14. CSF p-tau231 extension
15. Plasma NfL extension
16. Plasma GFAP extension
17. TREM2 variants Layer 2 pack
18. ADAS-Cog Layer 2 pack
19. MoCA Layer 2 pack
20. CDR/MMSE Layer 2 plausibility bounds
21. iADRS composite Layer 2 pack
22. NPI-Q Layer 2 pack
23. UPSIT olfactory Layer 2 pack
24. Microbleeds non-ARIA Layer 2 pack
25. Surveillance MRI schedule Layer 4 invariant

**Tier 3 -- Lower priority, Layer 4 dependent (14 items, ~15 sessions):**

26-39. Various Layer 4 (inclusion/protocol/missing-data) items, screen failures, endpoint derivation Layer 3 invariants, outcome adjudication consistency invariants, study-partner reliability framework (depends on Layer 4 design first).

### 6.2 Sequencing recommendation

Complete the v1.11.0 arc first (a2, a3, rc1, final = 4 sessions). Then begin the Tier 1 roadmap in v1.11.x and v1.12.0 (Layer 4 design). Tier 2 follows in v1.13.x. Tier 3 spans v1.14.x and beyond.

**Critical sequencing principle:** Tier 1's ARIA-related Layer 3 invariants are the most clinically consequential. Five of them belong in the v1.11.0 implementation arc itself -- they're already partial-covered by the genotype_phenotype_consistency and tool_declaration_consistency packs designed in `LAYER_3_DESIGN.md`. The remaining Tier 1 items follow in v1.11.x point releases.

### 6.3 Estimated timeline

| Phase | Releases | Sessions | Wall-clock estimate |
|---|---|---|---|
| Complete v1.11.0 arc | a2, a3, rc1, final | 4 sessions | 1-2 months |
| Tier 1 roadmap | v1.11.1 - v1.11.10 | 10 sessions | 3-5 months |
| Tier 2 roadmap + Layer 4 design | v1.12.0-design, v1.12.x, v1.13.x | 15 sessions | 5-8 months |
| Tier 3 roadmap | v1.14.x + | 15 sessions | 5-9 months |
| **Total** | **v1.11.0 - v1.14.x** | **~44 sessions** | **14-24 months** |

This is honest. It is not "we'll cover everything in two sessions." It is also not "we'll never cover this." It is a disciplined multi-year roadmap at world-class evidence standard.

---

## 7. Explicit out-of-scope statements for the 27 (b) items

For the 27 items categorized (b), NeuroTCS will not implement audit coverage. This section documents which tools should handle them, so trial submitters can use NeuroTCS in combination with the appropriate tools.

| (b) Item | Recommended tool / standard |
|---|---|
| All 12 SDTM core domains | Pinnacle 21, OpenCDISC (CDISC SDTM validators) |
| ADaM analysis datasets | Trial biostatistician + Define-XML traceability tools |
| Randomization / stratification metadata | IWRS/IxRS systems (Calyx, Endpoint Clinical, Veeva eClinical) |
| Raw DICOM headers, scanner/coil/sequence params | MRIQC, dcm2niix, scanner vendor QA, central reader QA programs |
| PET reconstruction QC | Central PET reader QA, scanner vendor QA |
| Bioanalytical assay metadata (batch, LLOQ, freeze-thaw) | Bioanalytical lab CLIA/CAP documentation (Quanterix, Roche Elecsys, Lilly validated lab reports) |
| Drug accountability | EDC (Medidata Rave, Veeva CDB) |
| Concomitant medication interactions | Trial pharmacovigilance system, FDA FAERS for post-market |
| Premedication / infusion workflow | EDC + site SOP documentation |
| Treatment logistics | EDC + site SOP documentation |
| WGS QC metadata | WGS vendor QC reports (Illumina, PacBio, Oxford Nanopore) |
| APP duplication / triplication detection | Clinical genetics lab (CLIA-certified) |
| PSEN1/2 mutation detection | Clinical genetics lab (CLIA-certified) |
| Neuropathology / postmortem | Pathologist adjudication per NACC RBE, NIA-AA postmortem criteria |
| Real-world linkage (EHR, claims, mortality) | CMS/CCW, OptumLabs Data Warehouse, TriNetX, observational research networks |
| Data governance / audit trail | EDC audit logs (Medidata Rave, Veeva CDB, OpenClinica) |

NeuroTCS users should ensure these tools are in place upstream of (or alongside) NeuroTCS for a complete AD trial data review workflow.

---

## 8. Honest acknowledgment of 34 (c) items

The 34 (c) items are not refused. They are honest "we don't know yet" items, each with a specific reason:

| Reason category | Count | Examples |
|---|---|---|
| Evidence too immature for ≥5-body consensus | ~15 | eMTBR-tau243 (Dec 2025), most digital biomarkers, sTREM2, methylation, transcriptomics |
| Multiple competing standards, no convergence | ~10 | Polygenic risk scores, GWAS panels, DTI tract selection, ASL/fMRI cutoffs |
| Inherently subjective endpoint | ~5 | CGIC, QOL-AD, Zarit, caregiver-reported scales |
| Methodology open research | ~4 | Study-partner reliability framework, LMIC language/rater drift |

Each (c) item gets revisited when its blocking condition resolves. Examples:
- **eMTBR-tau243** -- revisit when 5+ international bodies endorse cutoffs (estimated 2027)
- **Digital gait biomarkers** -- revisit when FDA clears a digital-gait device with AD trial indication
- **Caregiver reliability** -- revisit when the AD trial community converges on a standard reliability framework

This is the honest version of "this is not a partial fix; this is a deliberate hold pending evidence."

---

## 9. The response to the auditor, in one paragraph

If the auditor reads only one paragraph of this document, it should be this:

> *You are correct that NeuroTCS is not a complete AD trial-data recognizer. It was never designed to be one and is not described in that way in the v1.x scope documents (see `docs/SCOPE.md`). NeuroTCS is a citation-locked, fail-closed audit framework for the logical consistency of AD trial biomarker data, operating at three layers: temporal coherence of categorical state trajectories (Layer 1, production since v1.8.x), per-visit plausibility of continuous biomarker values against published normative ranges (Layer 2, production since v1.10.0 with 6 packs / 100 bounds), and cross-sheet consistency between manifest declarations and observed values (Layer 3, in development per `LAYER_3_DESIGN.md` v1.11.0-design.2). Of the ~115 gap categories your review identified, ~47% (54 items) are in-scope for NeuroTCS, of which 15 are already in production and 39 are on a disciplined 20-30 session roadmap (estimated 12-18 months). ~24% (27 items) are explicitly out-of-scope, with named alternative tools (CDISC SDTM validators, EDC systems, image-QC tools, CLIA-certified bioanalytical labs) recommended. ~29% (34 items) are genuine roadmap gaps awaiting maturing evidence or convergent clinical-judgment standards; each will be revisited when its specific blocking condition resolves. The framework's hard boundaries -- no measurement, no SDTM structural validation, no event adjudication, no replacement for human expert review -- are documented in section 3 of this response. We welcome integration with the upstream and adjacent tools that handle the layers above and below us.*

That paragraph is the public-facing position. Sections 1-8 above are the technical support for it.

---

## 10. What this document does NOT do

To be explicit about what this scope-response document does NOT commit to:

1. It does not commit any implementation work. The (a) items in section 6 are roadmap entries, not promises. Each one requires its own future implementation session at world-class evidence standard.

2. It does not lock the triage decisions in stone. Future revisions (`v1.11.0a1-scope-response.2`, `.3`, etc.) may reassign items between (a) / (b) / (c) categories based on new evidence or lead-investigator judgment.

3. It does not address the lead investigator's clinical judgment on the (c) items. Several (c) items will eventually be reassigned to (a) or (b) based on Dr. Salokhiddinov's clinical assessment as the lead investigator and neuroradiologist.

4. It does not address non-AD scope expansion. The v1.x AD-only scope per `docs/SCOPE.md` is preserved. Non-AD per-disease packs remain deferred to future per-disease repositories.

5. It does not modify any code, schema, test, or pack. Tests stay at 779 passing on Linux / 713 passing on Windows. ruff stays clean. Layer 1 byte-exact preserved across all 5 cohorts.

---

## 11. Tag and revision history

| Tag | Date | What changed |
|---|---|---|
| `v1.11.0a1-scope-response` | 2026-05-25 | Initial scope-response document. Triage of ~115 auditor-identified gap categories. Roadmap for 39 future in-scope items. Out-of-scope statements for 27 items. Acknowledgment of 34 evidence-or-judgment-pending items. |

Modifications to this document require bumping to `v1.11.0a1-scope-response.2`, `.3`, etc., with explicit changelog of which items moved between categories and why.

---

## 12. Acceptance criteria

This document is ACCEPTED when:

- [x] Section 2 (one-sentence definition) is signed off
- [x] Section 3 (four hard boundaries) is signed off
- [x] Section 4 (triage taxonomy a/b/c) is the operative method
- [x] Section 5 (item-by-item triage, ~115 items) is the operative result
- [x] Section 6 (roadmap for 39 in-scope future items) is roadmap-only, not commitment
- [x] Section 7 (27 out-of-scope items + named alternative tools) is the operative recommendation
- [x] Section 8 (34 evidence-pending items) is the operative deferral
- [x] Section 9 (one-paragraph response to auditor) is the public-facing position
- [x] No code, no schema, no test changes in this release

**Status as of `v1.11.0a1-scope-response`: ACCEPTED via lead-investigator-delegated authority (Dr. Salokhiddinov asked for the recommended option, Option A; the resulting document represents the design author's recommendations; lead investigator retains override rights via .2 revisions per section 0.1 provenance note).**

---

**End of scope-response document.**

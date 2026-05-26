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

### 5.2 Document 1, Group 2 -- Imaging biomarkers (12 items)

| Item | Category | Notes |
|---|---|---|
| MRI volumetric segmentation (hippocampus, etc.) | **(a) PARTIALLY IN PRODUCTION** | Covered by `mri_volumetrics/structural_volumetry_consensus@1.0.0` (v1.10.2, 6 production packs / 100 bounds). 18 additional regions in `freesurfer_extended` research_preview pack. Future v1.10.3 session promotes feasible regions. |
| MRI white matter hyperintensities (WMH, Fazekas) | **(a) IN PRODUCTION** | Covered by `mri_volumetrics/wmh_fazekas_consensus@1.0.0` (v1.13.0, 6 measurements / 13 bounds). Anchors: Fazekas 1987 (PMID 3496763), STRIVE-2 (Duering 2023, PMID 37236211), Meta VCI Map (de Kort 2024, PMID 39602940, n=14,876), NeuroQuant FDA 510(k). |
| MRI microbleeds, superficial siderosis | (a) | Future Layer 2 pack. Has consensus criteria (Microbleed Anatomical Rating Scale, BOMBS scale, Brain Observer MicroBleed Scale). Partially covered by `ad/aria_safety@1.0.0` (ARIA-H). Future pack could expand to non-ARIA microbleed contexts. |
| MRI ARIA-E reads | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0` (severity/location/evolution). |
| MRI ARIA-H reads | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0`. |
| Amyloid PET (Centiloid, regional SUVR, status) | **(a) IN PRODUCTION** | Covered by `pet_amyloid/centiloid_consensus@1.0.0` (3 measurements, 10 bounds). |
| Tau PET (regional SUVR, Braak stage, MTL vs neocortical) | **(a) IN PRODUCTION** | Covered by **dual-pack family** (v1.15.0): `tau_pet/tau_consensus@1.0.0` (production, 6 measurements / 13 bounds, FDA Tauvid (flortaucipir) PI §2.4 verbatim visual interpretation criteria including the 1.65× cerebellar threshold; anchor Mattay 2020 J Nucl Med PMID 32709695) AND `tau_pet/tau_research_preview@1.0.0` (research_preview, 6 measurements / 16 bounds, Schöll 2016 / Maass 2017 / Pascoal 2021 SUVR cutoffs + PET-Braak 0-VI staging + Villemagne 2023 CenTauR universal scale). Tracer scope: flortaucipir only. MK-6240 PDUFA Aug 13 2026 not yet approved; future v2.0.0 will add MK-6240 after FDA action. |
| FDG PET | **(a) IN PRODUCTION** | Covered by `fdg_pet/fdg_consensus@1.0.0` (v1.16.0, 7 measurements / 18 bounds). Anchors: FDA Fludeoxyglucose F-18 Injection PI (74-370 MBq), CMS NCD 220.6.13 AD/FTD differential diagnosis (Sept 15 2004), AA-2024 NIA-AA Core 2 N-marker classification (Jack 2024), SNMMI Procedure Standard/EANM Practice Guideline v2.0 (Arbizu Oct 2024), EANM Brain FDG-PET v3 (2022), Mosconi 2008 J Nucl Med multicenter standardization (PMID 18287270, n=548 across 7 sites), Bailly 2015 BioMed Res Int (PMC4539420, precuneus/PCC SUVR anchors). |
| Diffusion MRI (DTI FA, MD, RD) | (c) | Needs clinical judgment: which tracts, which atlas (ICBM-DTI-81, JHU), which normative reference. Evidence exists but no single ≥5-body consensus on cutoffs. |
| ASL / perfusion MRI (CBF) | (c) | Same as DTI: no consensus cutoffs at international_consensus standard yet. |
| fMRI / resting-state functional connectivity | (c) | Research-grade for AD trial endpoints; no consensus cutoffs. |
| Susceptibility-weighted imaging (SWI) | **(a) IN PRODUCTION** | Covered by `ad/aria_safety@1.0.0` as a contributor to ARIA-H detection (NeuroQuant 5.0 SWI capability noted in v1.10.2). |

**Group 2 subtotal: 9 (a) [7 in production / 2 future], 0 (b), 3 (c).**

*Change from v1.13.1: Tau PET moved from "(a) future" to "(a) IN PRODUCTION" with the v1.15.0 ship of the `tau_pet/tau_consensus@1.0.0` + `tau_pet/tau_research_preview@1.0.0` dual pack family. In-production count: 5 → 6; future count: 4 → 3. Group totals 9/0/3 unchanged.*

*Change from v1.15.2: FDG PET moved from "(a) future" to "(a) IN PRODUCTION" with the v1.16.0 ship of `fdg_pet/fdg_consensus@1.0.0` (FDA + CMS + AA-2024 Core 2 N + SNMMI/EANM 2024 v2.0 + EANM Brain FDG-PET v3 + Mosconi 2008 multicenter + Bailly 2015 SUVR anchors; 7 measurements, 18 bounds, 7-8 endorsers per bound). In-production count: 6 → 7; future count: 3 → 2. Group totals 9/0/3 unchanged.*

### 5.3 Document 1, Group 3 -- Fluid biomarkers (16 items)

| Item | Category | Notes |
|---|---|---|
| CSF Aβ42 | **(a) IN PRODUCTION** | Covered by `csf_biomarkers/csf_amyloid_consensus@1.0.0`. |
| CSF Aβ40 | **(a) IN PRODUCTION** | Covered by `csf_biomarkers/csf_amyloid_consensus@1.0.0`. |
| CSF Aβ42/40 ratio | **(a) IN PRODUCTION** | Covered by `csf_biomarkers/csf_amyloid_consensus@1.0.0`. |
| CSF total tau | (a) | Future extension of `csf_biomarkers/csf_amyloid_consensus` or new pack. Anchor: NIA-AA 2024 biological staging. Estimated 1 session. |
| CSF p-tau181 | (a) | Future extension. Anchor: Janelidze 2020, AA 2024. Estimated 1 session. |
| CSF p-tau217 | (c) | **DOWNGRADED from (a) in v1.13.1.** During v1.13.0 primary-source research, three findings forced this reclassification: (1) No FDA-cleared CSF p-tau217 cutoff exists; the May 2025 FDA 510(k) clearance is the Lumipulse G pTau217/Aβ42 **plasma** ratio, not CSF. (2) Plasma p-tau217 is already shipping in `plasma_biomarkers/plasma_amyloid_consensus@1.1.0` (measurements: `plasma_ptau217_pgml`, `plasma_ptau217_abeta42_ratio_lumipulse`, `plasma_amyloid_status`); a CSF-only pack would be redundant for the modality that has regulatory standardization. (3) Cross-platform CSF p-tau217 cutoffs (Lilly MSD, Quanterix Simoa, Roche Elecsys) lack a single ≥5-body consensus; each platform reports different absolute pg/mL ranges with no harmonized conversion factor. Revisit when (a) FDA clears a CSF p-tau217 assay, OR (b) AA/IWG/EAN/EFNS/SNMMI converge on a single cross-platform CSF cutoff. Estimated revisit: 2027+. |
| CSF p-tau231 | (a) | Future extension. Anchor: Ashton 2021. Estimated 1 session. |
| CSF NfL | (c) | **DOWNGRADED from (a) in v1.15.2** following the v1.13.1 CSF p-tau217 precedent. Three findings during v1.15.0 primary-source research: (1) No FDA-cleared NfL assay for AD-specific indication exists (Quanterix Simoa NfL has FDA Breakthrough Designation for multiple sclerosis only; LDT status "for research use only"). (2) Cross-platform NfL cutoffs (Quanterix Simoa, Roche Elecsys NfL, Mesoscale Discovery) report numerically different values that correlate but require platform-specific reference values; no harmonized conversion factor or unified clinical cutoff. (3) NfL is non-specific (elevated in MS, ALS, TBI, stroke, peripheral neuropathy, normal aging) — even with FDA action it would not be an AD-specific biomarker without context-specific cutoff stratification. Revisit when (a) FDA clears an NfL assay with explicit AD trial indication, OR (b) ≥5 international bodies endorse cross-platform AD-specific NfL cutoffs. Estimated revisit: 2027+. |
| CSF GFAP | (c) | **DOWNGRADED from (a) in v1.15.2** following the same pattern as CSF NfL. Three findings: (1) No FDA-cleared GFAP assay for AD-specific indication (Pereira 2021 BMJ Neurology elevation pattern is well-described but not regulatorily standardized). (2) Cross-platform GFAP cutoffs (Quanterix Simoa, Roche Elecsys, Mesoscale) lack harmonization. (3) GFAP elevation is reactive-astrocyte-non-specific — elevated in TBI, stroke, MS, prion disease as well as AD. Revisit conditions identical to NfL. Estimated revisit: 2027+. |
| CSF sTREM2 | (c) | Research-grade; no FDA-cleared cutoffs; no ≥5-body consensus. Revisit when evidence matures. |
| Plasma p-tau217 | **(a) IN PRODUCTION** | Covered by `plasma_biomarkers/plasma_amyloid_consensus@1.1.0`. |
| Plasma p-tau181, p-tau231 | **(a) IN PRODUCTION (p-tau181) / (a) future (p-tau231)** | Plasma p-tau181 Elecsys (Roche, FDA 510(k) K252163 cleared October 13, 2025) is now in production at `plasma_biomarkers/plasma_amyloid_consensus@1.1.0` (measurement `plasma_ptau181_pgml_elecsys`, FDA-verbatim cutoff 0.722 pg/mL, 97.9% NPV in 312-participant primary-care submission cohort). Plasma p-tau231 remains future extension; anchor Ashton 2021. |
| Plasma Aβ42/40 ratio | **(a) IN PRODUCTION** | Covered by `plasma_biomarkers/plasma_amyloid_consensus@1.1.0`. |
| Plasma NfL | (c) | **DOWNGRADED from (a) in v1.15.2** for the same reasons as CSF NfL above (no FDA AD-specific clearance, cross-platform inconsistency, non-specific to AD). Revisit conditions identical. Estimated revisit: 2027+. |
| Plasma GFAP | (c) | **DOWNGRADED from (a) in v1.15.2** for the same reasons as CSF GFAP above. Revisit conditions identical. Estimated revisit: 2027+. |
| eMTBR-tau243 (Dec 2025) | (c) | Too new for ≥5 endorsing bodies. Single publication 2025. Revisit when ≥5 international bodies have endorsed cutoffs (estimated 2027+). |

**Group 3 subtotal: 9 (a) [6 in production / 3 future], 0 (b), 7 (c).**

*Change from v1.13.1: (i) Plasma p-tau181 Elecsys moved from "implicit (a) future" to "(a) IN PRODUCTION" with the v1.14.0 ship of `plasma_amyloid_consensus@1.1.0` (note: v1.13.1 documentation incorrectly claimed plasma p-tau181 was in `@1.0.0`; this is corrected here). (ii) Plasma p-tau217 / Plasma Aβ42/40 citations updated from `@1.0.0` to `@1.1.0` (cosmetic, pack extended in v1.14.0). (iii) CSF NfL, CSF GFAP, Plasma NfL, Plasma GFAP — 4 items DOWNGRADED from "(a) future" to "(c) needs maturing evidence" following the v1.13.1 CSF p-tau217 precedent: no FDA-cleared AD-specific assays exist; cross-platform inconsistency; non-specific to AD. Net effect on Group 3: (a) 13 → 9 [5 in-prod / 8 future → 6 in-prod / 3 future]; (c) 3 → 7; total 16 unchanged. This downgrade was documented as a "future scope downgrade following p-tau217 pattern" in v1.13.1 / v1.14.0 CHANGELOGs but not actually executed in the scope doc until v1.15.2 — closing that documentation gap is the purpose of this revision.*

### 5.4 Document 1, Group 4 -- Genomics (11 items)

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

### 5.5 Document 1, Group 5 -- Cognitive and functional assessments (20 items)

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

**Group 5 subtotal: 14 (a) [2 already used / 12 future], 0 (b), 6 (c).**

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

**Document 2 subtotal: 5 (a) [1 already partially addressed / 4 future], 8 (b), 1 (c).**

### 5.11 Triage totals

**Errata note (2026-05-27, NeuroTCS v1.12.1):** Independent ground-truth
recount of Sections 5.1 through 5.10 corrected the totals in this section.
The original v1.11.0a1-scope-response numbers (54/27/34/115) reflected
arithmetic errors in five group subtotals (5.2, 5.3, 5.5, 5.10) and four
group header item counts (5.2, 5.3, 5.4, 5.5). The v1.12.1 verified
ground-truth recount was: **66 (a) / 26 (b) / 25 (c) / 117 items.**
See CHANGELOG.md v1.12.1 entry for the full reconciliation.

**Update note (2026-05-28, NeuroTCS v1.16.0):** One item reclassified
since v1.15.2, originating from v1.16.0 development:

1. **FDG PET (Group 2, Section 5.2):** Moved from "(a) future" to
   "(a) IN PRODUCTION" with the v1.16.0 ship of `fdg_pet/fdg_consensus@1.0.0`.
   The pack encodes brain [18F]FDG PET clinical-grade parameters for AD
   differential diagnosis at world-class evidence standard:
   FDA Fludeoxyglucose F-18 Injection Prescribing Information verbatim
   dose envelope (74-370 MBq); CMS National Coverage Determination 220.6.13
   regulatory-grade AD/FTD differential diagnosis coverage (Sept 15, 2004;
   reviewed Sept 10, 2024); AA-2024 NIA-AA Revised Criteria Core 2 N-marker
   classification (Jack et al. PMID 38934362); SNMMI Procedure Standard/
   EANM Practice Guideline for Brain [18F]FDG PET Imaging Version 2.0
   (Arbizu et al., J Nucl Med Oct 2024); EANM Brain FDG-PET Procedure
   Guideline Version 3 (2022, PMID 35094103); Mosconi 2008 J Nucl Med
   multicenter standardization across 7 sites (PMID 18287270, n=548);
   Bailly 2015 BioMed Res Int multi-site French validation cohort
   (PMC4539420, n=47, cerebellum-referenced precuneus and posterior
   cingulate SUVR anchors). 7 measurements, 18 bounds, 7-8 endorsers
   per bound. All bounds pass the v1.15.1 reconciled world-class gate
   (endorser floor + valid strength form + multi-source markers for
   derived bounds).

Net effect on totals: **(a) 61 unchanged**, **in-production 23 → 24**,
**future (a) 38 → 37**. (b) 26 unchanged. (c) 30 unchanged. Total 117
unchanged.

Note: FDG PET is the first Tier 2 item shipped from the v1.15.2 roadmap
(was Tier 2 item #6 = FDG PET Layer 2 pack). It qualified for production
not via FDA AD-specific indication (FDG is FDA-approved for epilepsy/
oncology/cardiology, NOT AD) but via the regulatory-grade CMS NCD 220.6.13
coverage decision + AA-2024 Core 2 N-marker international consensus +
SNMMI/EANM 2024 v2.0 joint procedure standard. This is the same evidence
architecture pattern as wmh_fazekas_consensus (Fazekas 1987 verbatim +
Meta VCI Map derived): mixed citation_strength forms unified by ≥5-body
endorsement and multi-source derivation.

**Update note (2026-05-28, NeuroTCS v1.15.2):** Five additional items
reclassified since v1.13.1, originating from v1.14.0 + v1.15.0 + v1.15.1
development work and the v1.15.2 documentation reconciliation:

1. **Tau PET (Group 2, Section 5.2):** Moved from "(a) future" to
   "(a) IN PRODUCTION" with the v1.15.0 ship of the dual pack family
   `tau_pet/tau_consensus@1.0.0` (production, FDA Tauvid verbatim 1.65×
   cerebellar threshold) + `tau_pet/tau_research_preview@1.0.0` (Schöll/
   Maass/Pascoal/CenTauR). Group 2 in-production count: 5 → 6; future
   count: 4 → 3. Item count unchanged.

2. **CSF NfL (Group 3, Section 5.3):** DOWNGRADED from "(a) future" to
   "(c) needs maturing evidence" following the v1.13.1 CSF p-tau217
   precedent. No FDA-cleared NfL assay for AD-specific indication exists;
   Quanterix Simoa NfL FDA Breakthrough Designation is MS-only. Cross-
   platform inconsistency (Simoa vs Elecsys vs MSD report different
   absolute values). NfL is non-specific to AD.

3. **CSF GFAP (Group 3, Section 5.3):** DOWNGRADED from "(a) future" to
   "(c)" following identical pattern as CSF NfL. No FDA AD-specific
   clearance; cross-platform inconsistency; reactive-astrocyte-non-specific.

4. **Plasma NfL (Group 3, Section 5.3):** DOWNGRADED from "(a) future" to
   "(c)" following the same logic as CSF NfL.

5. **Plasma GFAP (Group 3, Section 5.3):** DOWNGRADED from "(a) future" to
   "(c)" following the same logic as CSF GFAP.

The NfL/GFAP downgrades were documented as "future scope downgrade
following p-tau217 pattern" in v1.13.1 and v1.14.0 CHANGELOGs but not
actually executed in the scope doc until v1.15.2. Closing that
documentation gap is the purpose of this revision.

Net effect on totals: **(a) 65 → 61** (Tau PET in-prod, 4 NfL/GFAP items
moved to (c)), **(c) 26 → 30**, **(b) 26 unchanged**, **total 117
unchanged**. In-production count: **22 → 23** (Tau PET added; Plasma
p-tau181 Elecsys was de-facto in-prod in v1.14.0 but shared the row
"Plasma p-tau181, p-tau231" so it doesn't add a row count). Future (a)
count: **43 → 38** (Tau PET shipped, 4 NfL/GFAP items moved to (c)).

Plasma pack citation updated across the document: `@1.0.0` → `@1.1.0`
(v1.14.0 extended the pack with the FDA-cleared Elecsys pTau181
measurement; the old `@1.0.0` citation was stale).

| Category | Count | % |
|---|---|---|
| **(a) In-scope, in production / already used / partially addressed** | **24** | **~21%** |
| **(a) In-scope, future pack/layer** | **37** | **~31%** |
| **(a) Subtotal: in-scope (in production + future)** | **61** | **~52%** |
| **(b) Out-of-scope, belongs in different tool** | **26** | **~22%** |
| **(c) Genuine roadmap gap, needs clinical judgment or maturing evidence** | **30** | **~26%** |
| **Total items audited** | **117** | 100% |

**Per-group ground-truth recount (post-v1.15.2):**

| Section | Group | Total | (a) | (b) | (c) |
|---|---|---|---|---|---|
| 5.1 | Document 1, Group 1 -- SDTM core domains | 12 | 0 | 12 | 0 |
| 5.2 | Document 1, Group 2 -- Imaging biomarkers | 12 | 9 | 0 | 3 |
| 5.3 | Document 1, Group 3 -- Fluid biomarkers | 16 | 9 | 0 | 7 |
| 5.4 | Document 1, Group 4 -- Genomics | 11 | 2 | 3 | 6 |
| 5.5 | Document 1, Group 5 -- Cognitive and functional assessments | 20 | 14 | 0 | 6 |
| 5.6 | Document 1, Group 6 -- Digital biomarkers | 8 | 1 | 0 | 7 |
| 5.7 | Document 1, Group 7 -- Trial-operational data | 10 | 7 | 3 | 0 |
| 5.8 | Document 1, Group 8 -- Anti-amyloid safety endpoints | 10 | 10 | 0 | 0 |
| 5.9 | Document 1, Group 9 -- Outcome adjudication | 4 | 4 | 0 | 0 |
| 5.10 | Document 2 -- 14 additional dataset layers | 14 | 5 | 8 | 1 |
| **Total** | | **117** | **61** | **26** | **30** |

*Note on Section 5.10:* one row in Document 2 ("Anti-amyloid treatment
safety decision trees") is annotated **(a) Already in roadmap (Group 8)**
and is a cross-reference to items counted separately in Section 5.8.
This is preserved in the 117-row count (it appears as a distinct row in
the auditor's Document 2 table). The duplicate is acknowledged here so
downstream consumers can adjust the totals if they prefer to deduplicate.

**The headline number (post-v1.16.0):** the auditor identified 117 distinct
gap rows across Documents 1 and 2. **~52% are in-scope for NeuroTCS** (24
already in production or addressed, 37 future); **~22% are explicitly
out-of-scope** with named alternative tools (CDISC validators, EDC systems,
image-QC tools, etc.); **~26% need clinical judgment or maturing evidence**
before they can be scoped.

This is a much more defensible position than "we need 117 more packs." It
is also a much more defensible position than "we have nothing to add."

The shift from 56% in-scope (v1.13.1) to 52% in-scope (v1.15.2) reflects
HONEST scope reduction: NfL/GFAP were aspirationally classified as future
(a) packs but on primary-source research did not meet world-class evidence
standards. Moving them to (c) is the same discipline the v1.13.1 release
applied to CSF p-tau217. No partial fix; no aspiration without evidence.

---

## 6. Defensible roadmap for the 37 in-scope future items

Realistic estimate: 37 future (a) items at the v1.10.x pace of ~1-2 packs per session = **19-28 additional implementation sessions**. Roughly 10-18 months of disciplined work.

*Change from v1.13.1: 43 → 38 future items. Tau PET dual pack shipped in v1.15.0 (`tau_pet/tau_consensus@1.0.0` + `tau_pet/tau_research_preview@1.0.0`, now in-production). CSF NfL, CSF GFAP, Plasma NfL, Plasma GFAP downgraded to (c) in v1.15.2 (no FDA AD-specific clearance, cross-platform inconsistency, non-specific to AD — same world-class evidence standard that drove the v1.13.1 CSF p-tau217 downgrade).*

*Change from v1.15.2: 38 → 37 future items. FDG PET Layer 2 pack shipped in v1.16.0 as `fdg_pet/fdg_consensus@1.0.0` — the first Tier 2 item closed from the v1.15.2 roadmap. Anchored to FDA + CMS + AA-2024 + SNMMI/EANM + Mosconi 2008 multicenter + Bailly 2015 multi-site cohort.*

### 6.1 Priority tiers

The 38 future items split into three tiers by clinical importance + evidence readiness:

**Tier 1 -- High priority, evidence ready (5 items, ~5-7 sessions):**

1. ARIA-related dose pause/discontinuation Layer 3 invariant (Group 8)
2. Anticoagulation contraindication Layer 3 invariant (Group 8)
3. APOE4 homozygote enhanced monitoring Layer 3 invariant (Group 8) -- aligns with v1.11.0a3 genotype-phenotype pack
4. ARIA symptoms vs MRI-grade Layer 3 invariant (Group 8)
5. Macrohemorrhage events Layer 3 invariant (Group 8)

*Change from v1.13.1: 8 items → 5 items. Item 6 (Tau PET regional SUVR + Braak Layer 2 pack) DONE in v1.15.0 as a dual-pack family. Items 7 (NfL Layer 2 pack) and 8 (GFAP Layer 2 pack) DOWNGRADED to (c) in v1.15.2 after primary-source research found no FDA AD-specific clearance, cross-platform inconsistency, and non-AD-specific elevation patterns. All 5 remaining Tier 1 items are Layer 3 invariants from Group 8 (anti-amyloid safety endpoints) — partially covered by the existing `genotype_phenotype_consistency` and `tool_declaration_consistency` Layer 3 packs designed in `LAYER_3_DESIGN.md`.*

**Tier 2 -- Medium priority, evidence ready (12 items, ~12 sessions):**

6. CSF t-tau extension
7. CSF p-tau181 extension
8. CSF p-tau231 extension
9. Plasma p-tau231 extension (in shared `plasma_amyloid_consensus` row)
10. TREM2 variants Layer 2 pack
11. ADAS-Cog Layer 2 pack
12. MoCA Layer 2 pack
13. CDR/MMSE Layer 2 plausibility bounds
14. iADRS composite Layer 2 pack
15. NPI-Q Layer 2 pack
16. UPSIT olfactory Layer 2 pack
17. Microbleeds non-ARIA Layer 2 pack

*Change from v1.13.1: Tier 2 was 15 items (numbered 11-25 in v1.13.1). Plasma NfL and Plasma GFAP removed (downgraded to (c) in v1.15.2). FDG PET shipped in v1.16.0 (was item 6). Tier 2 now 12 items.*

**Tier 3 -- Lower priority, Layer 4 dependent (20 items, ~18-20 sessions):**

19-38. Various Layer 4 (inclusion/protocol/missing-data) items, screen failures, endpoint derivation Layer 3 invariants, outcome adjudication consistency invariants, study-partner reliability framework, and additional in-scope (a) items from the corrected ground-truth recount (depends on Layer 4 design first).

*Tier 3 numbering note: cumulative numbering is 5 + 12 + 20 = 37 (v1.16.0). (v1.13.1: 8 + 15 + 20 = 43; v1.15.2: minus 1 Tier 1 (Tau PET done), minus 2 Tier 1 (NfL/GFAP downgraded), minus 2 Tier 2 (Plasma NfL/GFAP downgraded) = 38.)*

### 6.2 Sequencing recommendation

Complete the v1.11.0 arc first (a2, a3, rc1, final = 4 sessions). Then begin the Tier 1 roadmap in v1.11.x and v1.12.0 (Layer 4 design). Tier 2 follows in v1.13.x. Tier 3 spans v1.14.x and beyond.

**Critical sequencing principle:** All 5 remaining Tier 1 items are ARIA-related Layer 3 invariants — the most clinically consequential. They're already partial-covered by the genotype_phenotype_consistency and tool_declaration_consistency packs designed in `LAYER_3_DESIGN.md`. v1.11.x point releases complete them.

### 6.3 Estimated timeline

| Phase | Releases | Sessions | Wall-clock estimate |
|---|---|---|---|
| Complete v1.11.0 arc | a2, a3, rc1, final | 4 sessions | 1-2 months |
| Tier 1 roadmap | v1.11.1 - v1.11.7 | 5-7 sessions | 2-3 months |
| Tier 2 roadmap + Layer 4 design | v1.12.0-design, v1.12.x, v1.13.x | 13 sessions | 5-7 months |
| Tier 3 roadmap | v1.14.x + | 18-20 sessions | 6-11 months |
| **Total** | **v1.11.0 - v1.14.x** | **~39-43 sessions** | **13-22 months** |

*Tier 1 reduced from 8-10 to 5-7 sessions in v1.15.2: Tau PET done in v1.15.0; NfL/GFAP downgraded to (c). Tier 2 reduced from 15 to 13 sessions in v1.15.2 (Plasma NfL/GFAP downgraded), then from 13 to 12 sessions in v1.16.0 (FDG PET shipped). Total session estimate reduced accordingly (45-49 → 39-43).*

This is honest. It is not "we'll cover everything in two sessions." It is also not "we'll never cover this." It is a disciplined multi-year roadmap at world-class evidence standard.

---

## 7. Explicit out-of-scope statements for the 26 (b) items

For the 26 items categorized (b), NeuroTCS will not implement audit coverage. This section documents which tools should handle them, so trial submitters can use NeuroTCS in combination with the appropriate tools.

| (b) Item | Recommended tool / standard |
|---|---|
| All 12 SDTM core domains | Pinnacle 21, OpenCDISC (CDISC SDTM validators) |
| ADaM analysis datasets | Trial biostatistician + Define-XML traceability tools |
| Randomization / stratification metadata | IWRS/IxRS systems (Calyx, Endpoint Clinical, Veeva eClinical) |
| Raw DICOM headers, scanner/coil/sequence params | MRIQC, dcm2niix, scanner vendor QA, central reader QA programs |
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

## 8. Honest acknowledgment of 30 (c) items

The 30 (c) items are not refused. They are honest "we don't know yet" items, each with a specific reason:

| Reason category | Count | Examples |
|---|---|---|
| Evidence too immature for ≥5-body consensus | 12 | eMTBR-tau243 (Dec 2025), 7 digital biomarkers (gait, speech, typing, sleep, driving, eye-tracking, smartphone), CSF sTREM2, methylation panel, transcriptomic profile, mitochondrial DNA haplogroup |
| Multiple competing standards, no convergence | 11 | GWAS panels, PLCG2 protective variant, polygenic risk scores, DTI tract selection, ASL perfusion cutoffs, fMRI/resting-state cutoffs, CSF p-tau217 cross-platform (added v1.13.1), **CSF NfL cross-platform (added v1.15.2)**, **CSF GFAP cross-platform (added v1.15.2)**, **Plasma NfL cross-platform (added v1.15.2)**, **Plasma GFAP cross-platform (added v1.15.2)** |
| Inherently subjective endpoint | 6 | FAQ, CFI, ADCS-ADL (all informant-reported), CGIC, QOL-AD, Zarit (all subjective) |
| Methodology open research | 1 | Caregiver / study-partner data reliability framework |
| **Total** | **30** | |

Each (c) item gets revisited when its blocking condition resolves. Examples:
- **eMTBR-tau243** -- revisit when 5+ international bodies endorse cutoffs (estimated 2027)
- **Digital gait biomarkers** -- revisit when FDA clears a digital-gait device with AD trial indication
- **Caregiver reliability** -- revisit when the AD trial community converges on a standard reliability framework
- **CSF p-tau217 (new v1.13.1)** -- revisit when (a) FDA clears a CSF p-tau217 assay (the May 2025 Lumipulse clearance is plasma-only), OR (b) AA/IWG/EAN/EFNS/SNMMI converge on a single cross-platform CSF cutoff harmonizing Lilly MSD, Quanterix Simoa, and Roche Elecsys. Estimated 2027+.
- **CSF + Plasma NfL (new v1.15.2)** -- revisit when (a) FDA clears an NfL assay with explicit AD trial indication (current Quanterix Simoa Breakthrough Designation is MS-only), OR (b) ≥5 international bodies endorse cross-platform AD-specific NfL cutoffs that account for NfL's non-specificity to AD (elevated in MS, ALS, TBI, stroke, peripheral neuropathy, normal aging). Estimated 2027+.
- **CSF + Plasma GFAP (new v1.15.2)** -- revisit conditions identical to NfL (no FDA AD-specific clearance, cross-platform inconsistency, reactive-astrocyte-non-specificity). Estimated 2027+.

This is the honest version of "this is not a partial fix; this is a deliberate hold pending evidence."

---

## 9. The response to the auditor, in one paragraph

If the auditor reads only one paragraph of this document, it should be this:

> *You are correct that NeuroTCS is not a complete AD trial-data recognizer. It was never designed to be one and is not described in that way in the v1.x scope documents (see `docs/SCOPE.md`). NeuroTCS is a citation-locked, fail-closed audit framework for the logical consistency of AD trial biomarker data, operating at three layers: temporal coherence of categorical state trajectories (Layer 1, production since v1.8.x), per-visit plausibility of continuous biomarker values against published normative ranges (Layer 2, production since v1.10.0 with 9 packs as of v1.16.0 — ad/aria_safety, pet_amyloid/centiloid_consensus, genetics/apoe_consensus, csf_biomarkers/csf_amyloid_consensus, plasma_biomarkers/plasma_amyloid_consensus, mri_volumetrics/structural_volumetry_consensus, mri_volumetrics/wmh_fazekas_consensus, tau_pet/tau_consensus, fdg_pet/fdg_consensus, plus 2 research_preview packs), and cross-sheet consistency between manifest declarations and observed values (Layer 3, in development per `LAYER_3_DESIGN.md` v1.11.0-design.2). Of the 117 gap rows your review identified, ~52% (61 items) are in-scope for NeuroTCS, of which 24 are already in production or addressed and 37 are on a disciplined 19-28 session roadmap (estimated 10-18 months). ~22% (26 items) are explicitly out-of-scope, with named alternative tools (CDISC SDTM validators, EDC systems, image-QC tools, CLIA-certified bioanalytical labs) recommended. ~26% (30 items) are genuine roadmap gaps awaiting maturing evidence or convergent clinical-judgment standards; each will be revisited when its specific blocking condition resolves. The framework's hard boundaries -- no measurement, no SDTM structural validation, no event adjudication, no replacement for human expert review -- are documented in section 3 of this response. We welcome integration with the upstream and adjacent tools that handle the layers above and below us.*

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
| `v1.11.0a1-scope-response` | 2026-05-25 | Initial scope-response document. Triage of 117 auditor-identified gap rows. Roadmap for in-scope future items. Out-of-scope statements. Acknowledgment of evidence-or-judgment-pending items. (NOTE: original v1.11.0a1-scope-response numbers (54/27/34/115) reflected arithmetic errors corrected in NeuroTCS v1.12.1 — see CHANGELOG.md.) |
| `v1.12.1` | 2026-05-27 | Section 5.11 arithmetic corrected via independent Python text-parser recount. Old totals 54/27/34/115 → verified 66/26/25/117. Section header counts 5.2/5.3/5.4/5.5 fixed. Subtotals in 5.2/5.3/5.5/5.10 fixed. In-scope split corrected (15+39=54 → 21+45=66). Downstream references in sections 6, 7, 8, 9 updated to match. Phantom "PET reconstruction QC" row removed from section 7. |
| `v1.13.1` | 2026-05-28 | Two items reclassified after v1.13.0 work: (1) WMH/Fazekas moved from "(a) future" to "(a) IN PRODUCTION" with the v1.13.0 ship of `mri_volumetrics/wmh_fazekas_consensus@1.0.0` (Fazekas 1987 + STRIVE-2 + Meta VCI Map). (2) CSF p-tau217 reclassified from "(a) future" to "(c) needs maturing evidence" after primary-source research found no FDA-cleared CSF cutoff exists, plasma p-tau217 is already in production, and cross-platform CSF cutoffs lack ≥5-body consensus. Net: (a) 66 → 65, (c) 25 → 26, in-production 21 → 22, future 45 → 43. Sections 5.2, 5.3, 5.11, 6 header, 6.1 Tier 1, 8, 9 updated. |
| `v1.16.0` | 2026-05-28 | **First Tier 2 forward pack shipped.** FDG PET Layer 2 pack shipped as `fdg_pet/fdg_consensus@1.0.0` (7 measurements / 18 bounds at world-class evidence standard). Anchored to FDA Fludeoxyglucose F-18 Injection PI verbatim dose envelope (74-370 MBq) + CMS NCD 220.6.13 regulatory-grade AD/FTD coverage + AA-2024 NIA-AA Core 2 N-marker classification + SNMMI/EANM 2024 v2.0 joint procedure standard + EANM Brain FDG-PET Guideline v3 (2022) + Mosconi 2008 J Nucl Med multicenter (n=548 across 7 sites) + Bailly 2015 BioMed Res Int multi-site validation cohort. All bounds clear the v1.15.1 reconciled world-class gate (endorser floor + valid strength form + multi-source markers for derived bounds). FDG PET qualifies for production status not via FDA AD-specific indication (FDG is FDA-approved for epilepsy/oncology/cardiology, NOT AD-specific) but via the multi-body international consensus (CMS + AA-2024 + SNMMI + EANM + ADNI + Mosconi + Bailly). Net effect: (a) 61 unchanged, in-production 23 → 24, future (a) 38 → 37, (b)/(c) unchanged, total 117 unchanged. Tier 2 dropped from 13 to 12 items. Section 5.2, 5.11, 6 header, 6.1, 6.3, 9 updated. NO existing YAML/code/schema touched; 1 NEW pack added cleanly with byte-exact invariance preserved on all 12 pre-existing active packs and all 5 Layer 1 cohort audit_ids. |
| `v1.15.2` | 2026-05-28 | **Documentation reconciliation closing four releases of stale content.** Five items reclassified: (1) Tau PET moved from "(a) future" to "(a) IN PRODUCTION" with v1.15.0 dual pack family `tau_pet/tau_consensus@1.0.0` (FDA Tauvid PI §2.4 verbatim 1.65× cerebellar threshold) + `tau_pet/tau_research_preview@1.0.0` (Schöll/Maass/Pascoal/CenTauR). (2-5) CSF NfL, CSF GFAP, Plasma NfL, Plasma GFAP all DOWNGRADED from "(a) future" to "(c) needs maturing evidence" following the v1.13.1 CSF p-tau217 precedent: no FDA AD-specific clearance exists (Quanterix Simoa NfL FDA Breakthrough Designation is MS-only), cross-platform inconsistency (Simoa vs Elecsys vs MSD), and non-AD-specificity (NfL elevated in MS/ALS/TBI/stroke/aging; GFAP elevated in TBI/stroke/MS/prion disease). All four downgrades were documented in v1.13.1/v1.14.0 CHANGELOGs as "future scope downgrade following p-tau217 pattern" but not actually executed in the scope doc until v1.15.2. Net: (a) 65 → 61 (1 to in-prod, 4 to (c)), (c) 26 → 30, in-production 22 → 23, future 43 → 38. Tier 1 dropped from 8 items to 5 items (Tau PET done, NfL/GFAP downgraded). Plasma pack citations updated `@1.0.0` → `@1.1.0` (cosmetic, pack extended in v1.14.0 with FDA-cleared Elecsys pTau181). Sections 5.2, 5.3, 5.11, 6 header, 6.1, 6.3, 8, 9 updated. No code, schema, or test changes. |

Modifications to this document require bumping to `v1.11.0a1-scope-response.2`, `.3`, etc., with explicit changelog of which items moved between categories and why.

---

## 12. Acceptance criteria

This document is ACCEPTED when:

- [x] Section 2 (one-sentence definition) is signed off
- [x] Section 3 (four hard boundaries) is signed off
- [x] Section 4 (triage taxonomy a/b/c) is the operative method
- [x] Section 5 (item-by-item triage, 117 items) is the operative result
- [x] Section 6 (roadmap for 43 in-scope future items) is roadmap-only, not commitment
- [x] Section 7 (26 out-of-scope items + named alternative tools) is the operative recommendation
- [x] Section 8 (26 evidence-pending items) is the operative deferral
- [x] Section 9 (one-paragraph response to auditor) is the public-facing position
- [x] No code, no schema, no test changes in this release

**Status as of `v1.11.0a1-scope-response`: ACCEPTED via lead-investigator-delegated authority (Dr. Salokhiddinov asked for the recommended option, Option A; the resulting document represents the design author's recommendations; lead investigator retains override rights via .2 revisions per section 0.1 provenance note).**

---

**End of scope-response document.**

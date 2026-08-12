# Transcription Audit: AD NIA-AA 2018 Rule Pack

**Rule pack:** `ad/niaaa_2018@1.4.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:** NIA-AA Research Framework (Jack et al. 2018, *Alzheimer's & Dementia* 14:535-562, PMID 29653606)

This document is the side-by-side audit of every YAML transition against its source paragraph in the cited publications. A reviewer can verify each row by opening the publication to the section indicated.

## State space

| State | Description | Source |
|---|---|---|
| CN | Cognitively normal / unimpaired | Jack 2018 §"Clinical staging" (p. 547) |
| MCI | Mild Cognitive Impairment | Jack 2018 §"Clinical staging" (p. 547) |
| AD | Alzheimer's disease dementia | Jack 2018 §"Clinical staging" (p. 547-548) |

## Admissible transitions

| From → To | Min Δt | Source claim transcribed | Section |
|---|---|---|---|
| CN → MCI | none | "Progression from cognitively unimpaired to MCI is the expected sequence within the AD continuum" | Jack 2018 pp. 547-549, Table 4 |
| MCI → AD | none | "MCI→dementia is the expected trajectory in the AD continuum" + Salemme 2025 41.5% pooled progression | Jack 2018 Table 4; Salemme 2025 Table 2 |
| CN → AD | ≥365d | "CN→AD trajectory traverses a prolonged biomarker-positive preclinical phase" — direct short-interval transition is implausible | Jack 2018 §"Biomarker-clinical staging", Fig. 1 (p. 541) |
| MCI → CN | ≥180d | Reversion 8.7% clinical / 28.2% population; minimum interval to distinguish biology from model flicker | Salemme 2025 Table 3 |

## Documented inadmissible transitions

| From → To | Reason | Attribution | Source |
|---|---|---|---|
| AD → MCI | AD dementia not expected to revert to MCI under standard care | **clinical_inference** (E-2026-011) | Informed by Jack 2018 pp. 547-549 + Salemme 2025 reversion epidemiology; NOT stated verbatim in Jack 2018 |
| AD → CN | AD dementia not expected to revert to CN | **clinical_inference** (E-2026-011) | Informed by Jack 2018 pp. 547-549; NOT stated verbatim in Jack 2018 |

**Attribution correction (ERRATA E-2026-011, external expert review 2026-08).**
Jack 2018 describes the AD continuum and syndromal staging (CN/MCI/dementia)
but does **not** state a one-way CN→MCI→AD state-transition model, and does
not address dementia→MCI reversion as an explicit transition rule. Both
inadmissible entries are therefore transcriber clinical inferences — encoded
because dementia reversion is substantially rarer than MCI reversion in the
cited epidemiology — and are declared `attribution_type: clinical_inference`
with a full bridging rationale in the YAML (`inference_rationale`). Documented
benign causes of apparent reversion (diagnostic reclassification at consensus
review, resolved delirium/depression, medication effects, label-mapping
artifacts) are listed there. A flag on these transitions means "inadmissible
under this rule pack — requires adjudication"; flag precision against expert
adjudication is measured per `docs/VALIDATION_PROTOCOL.md`.

## Transition priors

All priors transcribed from Salemme 2025 (DOI 10.1002/dad2.70074) Table 2 (progression) and Table 3 (reversion). Both clinical-cohort and population-cohort values provided for sensitivity analyses.

## Verification protocol

To verify this transcription:
1. Open Jack 2018 PMID 29653606 (free full text via PMC).
2. For each transition in the YAML, navigate to the section listed in the `guideline_section` field.
3. Confirm the cited source supports the encoded rule.
4. Open Salemme 2025 DOI 10.1002/dad2.70074 for the reversion-rate priors.

Any discrepancy found should be filed as a GitHub issue and triggers a rule pack version bump.

# Transcription Audit: PD Hoehn-Yahr Rule Pack

**Rule pack:** `pd/hoehn_yahr@1.0.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:**
- Hoehn-Yahr Staging: Hoehn MM, Yahr MD. *Neurology* 1967;17(5):427-442
- MDS-UPDRS (modified H&Y): Goetz CG et al. *Movement Disorders* 2008;23(15):2129-2170 (**PMID 19025984**)
- Natural-history transition pace: Marras C, Rochon P, Lang AE. *Archives of Neurology* 2002;59(11):**1724-1728** (**PMID 12433259**, **DOI 10.1001/archneur.59.11.1724**) — note: this is a **systematic review** of motor-decline predictors in early PD, not a primary-data table of stage-transition intervals (corrected per **ERRATA E-2026-003**).

## State space

All states from **Goetz 2008 Appendix C** (modified Hoehn-Yahr staging).

| Stage | Definition |
|---|---|
| HY_1 | Unilateral involvement only |
| HY_1_5 | Unilateral and axial involvement |
| HY_2 | Bilateral involvement without balance impairment |
| HY_2_5 | Mild bilateral with recovery on pull test |
| HY_3 | Mild-to-moderate bilateral; postural instability; physically independent |
| HY_4 | Severe disability; still walks/stands unassisted |
| HY_5 | Wheelchair-bound or bedridden unless aided |

## Admissible transitions

Single-step H&Y transitions are direct quotations from Goetz 2008 Appendix C
(`attribution_type: guideline_quote`). Multi-step transitions carry a
clinical-inference minimum-Δt floor informed by the Marras 2002 systematic
review (`attribution_type: clinical_inference` per schema v1.3.0).

| From → To | Min Δt | Attribution | Source / rationale |
|---|---|---|---|
| HY_1 → HY_1_5 | none | guideline_quote | Goetz 2008 Appendix C |
| HY_1_5 → HY_2 | none | guideline_quote | Goetz 2008 Appendix C |
| HY_2 → HY_2_5 | none | guideline_quote | Goetz 2008 Appendix C |
| HY_2_5 → HY_3 | none | guideline_quote | Goetz 2008 Appendix C |
| HY_3 → HY_4 | none | guideline_quote | Goetz 2008 Appendix C |
| HY_4 → HY_5 | none | guideline_quote | Goetz 2008 Appendix C |
| HY_1 → HY_2 (2-step) | ≥365d | clinical_inference | Marras 2002 establishes ~1 stage / 2-3 years natural-history pace; two-stage progression under 12 months is implausible by that benchmark |
| HY_1_5 → HY_2_5 (2-step) | ≥365d | clinical_inference | Same rationale |
| HY_2 → HY_3 (2-step) | ≥365d | clinical_inference | Same rationale |
| HY_2_5 → HY_4 (2-step) | ≥365d | clinical_inference | Same rationale |
| HY_3 → HY_5 (2-step) | ≥365d | clinical_inference | Same rationale |
| HY_1 → HY_2_5 (3-step) | ≥730d | clinical_inference | Three-stage progression in under 24 months is implausible at the published natural-history pace |
| HY_2 → HY_4 (3-step) | ≥730d | clinical_inference | Same rationale |

All clinical_inference transitions carry `override_allowed=true` to remain
fail-soft for treatment-related rapid improvement (DBS, levodopa response) or
atypical-parkinsonism contexts; an override requires an explicit citation in
the audit log.

## Inadmissible (natural history)

H&Y is monotone non-decreasing in natural history. Backward transitions
(HY_2→HY_1, HY_3→HY_2, HY_4→HY_3) are documented inadmissible by default;
treatment-driven improvement (levodopa, DBS) handled via `override_allowed=true`
with explicit citation in audit log.

## Verification protocol

1. Open Goetz 2008 (DOI 10.1002/mds.22340, PMID 19025984) Appendix C,
   "Modified Hoehn and Yahr Staging". Confirm state definitions match.
2. Open Marras 2002 via PubMed PMID **12433259** (NOT 12473781 — that
   PMID points to an unrelated paper). The paper is at
   *Arch Neurol* 2002;59(11):1724-1728, DOI 10.1001/archneur.59.11.1724.
3. Verify that Marras 2002 is a **systematic review** of motor-decline
   predictors in early PD covering literature 1966–2002. It synthesises
   natural-history pace estimates from multiple primary cohorts but does
   NOT publish a per-transition table of admissibility windows.
4. Confirm that every two-step or three-step transition in the YAML
   carries `attribution_type: "clinical_inference"` with a non-empty
   `inference_rationale` explaining the bridging logic. The schema
   validator at v1.3.0+ enforces this automatically.

## Errata cross-reference

- **E-2026-003**: Prior versions (≤ v1.7.0) cited Marras 2002 with the
  wrong journal (Neurology), wrong pages (1730), wrong PMID (12473781),
  wrong DOI (a Neurology pattern), and attributed multi-step Δt floors
  to a non-existent "Table 2 (stage-transition intervals)". The paper
  is a systematic review without such a table; the floors are clinical
  inferences. Schema v1.3.0 makes this distinction explicit.

# Transcription Audit: PD Hoehn-Yahr Rule Pack

**Rule pack:** `pd/hoehn_yahr@1.0.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:**
- Hoehn-Yahr Staging: Hoehn MM, Yahr MD. *Neurology* 1967;17(5):427-442
- MDS-UPDRS (modified H&Y): Goetz CG et al. *Movement Disorders* 2008;23(15):2129-2170
- Natural-history transition rates: Marras C et al. *Neurology* 2002;59:1724-1730 (PMID 12473781)

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

| From → To | Min Δt | Source |
|---|---|---|
| HY_1 → HY_1_5 | none | Goetz 2008 Appendix C |
| HY_1_5 → HY_2 | none | Goetz 2008 Appendix C |
| HY_2 → HY_2_5 | none | Goetz 2008 Appendix C |
| HY_2_5 → HY_3 | none | Goetz 2008 Appendix C |
| HY_3 → HY_4 | none | Goetz 2008 Appendix C |
| HY_4 → HY_5 | none | Goetz 2008 Appendix C |
| HY_1 → HY_2 (2-step) | ≥365d | Marras 2002 Table 2 (stage-transition intervals) |
| HY_1_5 → HY_2_5 (2-step) | ≥365d | Marras 2002 Table 2 |
| HY_2 → HY_3 (2-step) | ≥365d | Marras 2002 Table 2 |
| HY_2_5 → HY_4 (2-step) | ≥365d | Marras 2002 Table 2 |
| HY_3 → HY_5 (2-step) | ≥365d | Marras 2002 Table 2 |
| HY_1 → HY_2_5 (3-step) | ≥730d | Marras 2002 Table 2 |
| HY_2 → HY_4 (3-step) | ≥730d | Marras 2002 Table 2 |

## Inadmissible (natural history)

H&Y is monotone non-decreasing in natural history. Backward transitions (HY_2→HY_1, HY_3→HY_2, HY_4→HY_3) are documented inadmissible by default; treatment-driven improvement (levodopa, DBS) handled via `override_allowed=true` with explicit citation in audit log.

## Verification protocol

1. Open Goetz 2008 (DOI 10.1002/mds.22340) Appendix C, "Modified Hoehn and Yahr Staging".
2. Confirm state definitions match.
3. Open Marras 2002 (PMID 12473781) Table 2 for natural-history transition rates (~1 stage / 2-3 years).

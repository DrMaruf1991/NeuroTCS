# Transcription Audit: Stroke mRS Rule Pack

**Rule pack:** `stroke/mrs_followup@1.0.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:**
- mRS reliability/validity: Banks JL & Marotta CA. *Stroke* 2007;38(3):1091-1096 (DOI 10.1161/01.STR.0000258355.23810.c6)
- Rehabilitation trajectory: Winstein CJ et al. AHA/ASA Guidelines for Adult Stroke Rehabilitation and Recovery. *Stroke* 2016;47:e98-e169 (DOI 10.1161/STR.0000000000000098)

## State space

mRS 0-6, definitions from Banks 2007 (also primary source for mRS in clinical trials).

| State | Definition |
|---|---|
| mRS_0 | No symptoms |
| mRS_1 | No significant disability despite symptoms; able to carry out all usual duties and activities |
| mRS_2 | Slight disability; unable to carry out all previous activities, but able to look after own affairs without assistance |
| mRS_3 | Moderate disability; requires some help, but able to walk without assistance |
| mRS_4 | Moderately severe disability; unable to walk without assistance and unable to attend to own bodily needs without assistance |
| mRS_5 | Severe disability; bedridden, incontinent, requires constant nursing care and attention |
| mRS_6 | Dead (absorbing) |

## Admissible transitions

**Improvement (post-stroke recovery, Winstein 2016 §2):**

All adjacent backward transitions admissible at any interval (mRS_5→mRS_4, mRS_4→mRS_3, mRS_3→mRS_2, mRS_2→mRS_1, mRS_1→mRS_0).

Two-band improvement admissible ≥30 days (mRS_5→mRS_3, mRS_4→mRS_2, mRS_3→mRS_1) — rehabilitation timeline.

**Worsening (recurrent stroke or complication, Banks 2007):**

All adjacent forward transitions admissible at any interval (mRS_0→mRS_1, ..., mRS_4→mRS_5).

**Death (any state → mRS_6):**

Admissible from any non-absorbing state at any interval.

## Inadmissible

| From → To | Reason |
|---|---|
| mRS_6 → anything | mRS_6 (death) is terminal absorbing state |

## Verification protocol

1. Open Banks 2007 (DOI 10.1161/01.STR.0000258355.23810.c6) for mRS definitions and reliability discussion.
2. Open Winstein 2016 (DOI 10.1161/STR.0000000000000098) §2 for stroke recovery trajectory model (improvement expected first 90-180 days).

## Cross-product note

This rule pack maps directly to MyRehab's existing mRS use case (Maruf's clinical AI platform). Cross-product integration: the audit core library can score MyRehab's longitudinal mRS predictions against this rule pack.

# Transcription Audit: RECIST 1.1 Rule Pack

**Rule pack:** `oncology/recist_1_1@1.0.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:** RECIST 1.1 (Eisenhauer EA et al., *European Journal of Cancer* 2009;45(2):228-247, DOI 10.1016/j.ejca.2008.10.026, PMID 19097774) — RECIST Working Group at EORTC. ESMO/FDA/EMA-endorsed.

## State space

All states from **Eisenhauer 2009 §3.3 "Evaluation of response"**:

| State | Definition (verbatim) |
|---|---|
| CR | "Disappearance of all target lesions. Any pathological lymph nodes (whether target or non-target) must have reduction in short axis to <10 mm." |
| PR | "At least a 30% decrease in the sum of diameters of target lesions, taking as reference the baseline sum diameters." |
| SD | "Neither sufficient shrinkage to qualify for PR nor sufficient increase to qualify for PD, taking as reference the smallest sum diameters while on study." |
| PD | "At least a 20% increase in the sum of diameters of target lesions, taking as reference the smallest sum on study. In addition... the sum must also demonstrate an absolute increase of at least 5 mm. The appearance of one or more new lesions is also considered progression." |

## Admissible transitions

**Forward (worsening), 4-week confirmation per §3.4:**
- CR → PR (min 28d) — re-emergence of measurable disease
- CR → SD (min 28d)
- CR → PD (min 56d) — direct CR→PD implausible in single scan
- PR → SD (min 28d)
- PR → PD (any) — §3.3.4 admits at any interval if criteria met
- SD → PD (any) — standard progression

**Backward (response), 4-week confirmation per §3.4 "Confirmation":**

> "In non-randomised trials where response is the primary endpoint, confirmation of PR and CR is required... Confirmatory measurements should be performed not less than 4 weeks after the criteria for response are first met."

- SD → PR (min 28d)
- SD → CR (min 28d)
- PR → CR (min 28d) — deepening response

**Post-progression response (override-required) per §3.5 "Special notes":**

> "Patients with PD in target lesions then later have PR or CR after additional therapy — this is recorded as new response, not transition."

- PD → PR (min 56d, override-allowed)
- PD → SD (min 56d, override-allowed)

## Inadmissible

| From → To | Reason | Source |
|---|---|---|
| CR → PD (over <56 days) | Single-scan CR→PD without intervening assessment is implausible | Eisenhauer 2009 §3.3.4 |

## Verification protocol

Open Eisenhauer 2009 (PMID 19097774) and verify:
1. §3.3.4 "Time point response" — response category definitions
2. §3.4 "Confirmation" — 4-week confirmation rule for CR/PR
3. §3.5 "Special notes" — handling of post-progression response

## Validation cohort

RIDER Lung PET-CT (244 longitudinal NSCLC subjects, TCIA) — designed for therapy response evaluation. Aim 5 oncology portability target.

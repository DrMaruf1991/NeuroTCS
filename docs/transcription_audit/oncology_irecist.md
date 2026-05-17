# Transcription Audit: iRECIST Rule Pack

**Rule pack:** `oncology/irecist@1.0.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:** iRECIST (Seymour L et al., *Lancet Oncology* 2017;18(3):e143-e152, DOI 10.1016/S1470-2045(17)30074-8, PMID 28271869) — RECIST Working Group with immuno-oncology trialist input.

**KEY:** iRECIST exists specifically to handle **pseudoprogression** — transient apparent progression followed by response, observed in ~10% of immunotherapy responders (Hodi 2016 Clin Cancer Res 22:5487-5496).

## State space

All states from **Seymour 2017 Figure 1 ("iRECIST timepoint response assessment")**:

| State | Definition |
|---|---|
| iCR | Immune Complete Response (RECIST 1.1 CR criteria met) |
| iPR | Immune Partial Response (RECIST 1.1 PR criteria met) |
| iSD | Immune Stable Disease (RECIST 1.1 SD criteria met) |
| iUPD | Immune Unconfirmed Progressive Disease (tentative PD, pending 4-8 week confirmation; may resolve as pseudoprogression) |
| iCPD | Immune Confirmed Progressive Disease (absorbing) |

## Admissible transitions

**Bidirectional iCR/iPR/iSD with 4-week confirmation:**
- iSD ↔ iPR, iSD ↔ iCR, iPR ↔ iCR (all min 28d per RECIST 1.1 §3.4 / Seymour 2017 §"Response confirmation")

**First-progression transitions to iUPD (any interval):**
- iCR → iUPD
- iPR → iUPD
- iSD → iUPD

**iUPD → iCPD (4-8 week confirmation window per Seymour 2017 §"Definition of iCPD"):**

> "iCPD requires confirmation imaging 4-8 weeks after iUPD with further increase ≥5 mm in target lesions OR new lesions OR progressive non-target disease"

- iUPD → iCPD (min 28d, **max 56d** — outside this window, iUPD resets)

**iUPD → resolution (PSEUDOPROGRESSION) — the defining iRECIST feature:**

- iUPD → iSD: pseudoprogression resolved to stable
- iUPD → iPR: pseudoprogression resolved to response (canonical delayed-response pattern)
- iUPD → iCR: deep pseudoprogression resolution

Source: Seymour 2017 §"iUPD resolution", Figure 1 (resolution arrows).

## Inadmissible

| From → To | Reason |
|---|---|
| iCPD → iUPD | iCPD is absorbing terminal state |
| iCPD → iSD | iCPD is absorbing |

## Verification protocol

1. Open Seymour 2017 (PMID 28271869) Figure 1 ("iRECIST timepoint response assessment").
2. Confirm:
   - iUPD has resolution arrows to iSD, iPR, iCR (pseudoprogression).
   - iCPD has no exit arrows (absorbing).
   - iUPD→iCPD confirmation window is 4-8 weeks.

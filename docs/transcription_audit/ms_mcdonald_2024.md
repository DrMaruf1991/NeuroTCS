# Transcription Audit: MS McDonald 2024 + EDSS Rule Pack

**Rule pack:** `ms/mcdonald_2024@1.0.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:**
- EDSS: Kurtzke JF. *Neurology* 1983;33(11):1444-1452
- Diagnostic criteria: McDonald 2024 (Montalban X et al., *Lancet Neurology* 2025;24(10):850-865, DOI 10.1016/S1474-4422(25)00270-4)
- Phenotype / relapse-remission biology: Lublin FD et al. *Neurology* 2014;83:278-286, DOI 10.1212/WNL.0000000000000560

**KEY DIFFERENCE FROM OTHER RULE PACKS:** MS is relapsing-remitting in 85% of cases. Reversion within EDSS bands is admissible biology, not model error.

## State space (EDSS bands)

All states from **Kurtzke 1983 Table 1** (EDSS definitions), banded for audit-level granularity.

| Band | EDSS | Definition |
|---|---|---|
| EDSS_0 | 0 | Normal neurological exam |
| EDSS_1_0_2_5 | 1.0-2.5 | Minimal-to-mild disability; no ambulation impairment |
| EDSS_3_0_4_5 | 3.0-4.5 | Moderate disability; fully ambulatory |
| EDSS_5_0_6_5 | 5.0-6.5 | Walking assistance required |
| EDSS_7_0_8_5 | 7.0-8.5 | Wheelchair/bed restricted |
| EDSS_9_0_9_5 | 9.0-9.5 | Helpless bed patient |
| EDSS_10 | 10 | Death due to MS (absorbing) |

## Admissible transitions

**Forward (worsening) - adjacent bands, any interval:**
- EDSS_0 → EDSS_1_0_2_5
- EDSS_1_0_2_5 → EDSS_3_0_4_5
- EDSS_3_0_4_5 → EDSS_5_0_6_5
- EDSS_5_0_6_5 → EDSS_7_0_8_5
- EDSS_7_0_8_5 → EDSS_9_0_9_5
- EDSS_9_0_9_5 → EDSS_10

Source: Lublin 2014 Figure 1, MS disease activity model — relapses can produce abrupt worsening at any interval.

**Backward (improvement) - adjacent bands, RRMS biology:**
- EDSS_1_0_2_5 → EDSS_0
- EDSS_3_0_4_5 → EDSS_1_0_2_5
- EDSS_5_0_6_5 → EDSS_3_0_4_5
- EDSS_7_0_8_5 → EDSS_5_0_6_5 (min 90 days, override-allowed; less common but possible)

Source: Lublin 2014 §"Disease course", Figure 1 — relapse remission is the defining feature of RRMS.

**Two-band forward jumps (sustained progression) ≥180 days:**
- EDSS_0 → EDSS_3_0_4_5
- EDSS_1_0_2_5 → EDSS_5_0_6_5
- EDSS_3_0_4_5 → EDSS_7_0_8_5

Source: Lublin 2014 §"Confirmed disability progression" — sustained progression requires ≥6 months confirmation.

## Inadmissible

| From → To | Reason |
|---|---|
| EDSS_10 → anything | EDSS_10 is absorbing (death) |

## Verification protocol

1. Open Lublin 2014 (DOI 10.1212/WNL.0000000000000560) Figure 1 (MS disease activity and progression model). Confirm relapse-remission and sustained-progression arrows.
2. Open Kurtzke 1983 (Neurology 33:1444-1452) for EDSS band definitions.
3. Open Montalban 2025 (DOI 10.1016/S1474-4422(25)00270-4) for current McDonald 2024 diagnostic context.

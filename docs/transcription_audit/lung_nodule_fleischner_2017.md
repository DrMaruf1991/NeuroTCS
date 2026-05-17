# Transcription Audit: Fleischner 2017 Lung Nodule Rule Pack

**Rule pack:** `lung_nodule/fleischner_2017@1.0.0`
**Transcribed by:** Salokhiddinov M, MD PhD
**Clinical source authority:** Fleischner Society 2017 Guidelines (MacMahon H et al., *Radiology* 2017;284(1):228-243, DOI 10.1148/radiol.2017161659). ACR/STR/ATS endorsed.

## State space

| State | Source | Definition |
|---|---|---|
| Nodule_lt_6mm | MacMahon 2017 Table 1 | Solid nodule <6 mm mean diameter |
| Nodule_6_8mm | MacMahon 2017 Table 1 | Solid nodule 6-8 mm mean diameter |
| Nodule_gt_8mm | MacMahon 2017 Table 1 | Solid nodule >8 mm mean diameter |
| Nodule_subsolid_lt_6mm | MacMahon 2017 Table 2 | Subsolid (ground-glass or part-solid) nodule <6 mm |
| Nodule_subsolid_gte_6mm | MacMahon 2017 Table 2 | Subsolid nodule ≥6 mm |

## Admissible transitions

**Solid nodule growth (malignancy pattern):**

| From → To | Min Δt | Source |
|---|---|---|
| Nodule_lt_6mm → Nodule_6_8mm | ≥90d | MacMahon 2017 Table 1 + §"Follow-up intervals" |
| Nodule_6_8mm → Nodule_gt_8mm | ≥90d | MacMahon 2017 Table 1 |
| Nodule_lt_6mm → Nodule_gt_8mm | ≥180d | MacMahon 2017 §"Doubling time" — adenocarcinoma doubling >400 days makes two-band growth in <6 months implausible |

**Subsolid progression:**

| From → To | Min Δt | Source |
|---|---|---|
| Nodule_subsolid_lt_6mm → Nodule_subsolid_gte_6mm | ≥90d | MacMahon 2017 Table 2 |
| Nodule_subsolid_gte_6mm → Nodule_gt_8mm | ≥180d | MacMahon 2017 Table 2 + §"Subsolid nodules" (solid-component development indicates invasive progression) |

**Reduction (suggests non-malignancy), override-allowed:**

| From → To | Min Δt | Source |
|---|---|---|
| Nodule_6_8mm → Nodule_lt_6mm | ≥90d | MacMahon 2017 §"Nodule shrinkage and resolution" (organizing pneumonia, granuloma resolution) |
| Nodule_gt_8mm → Nodule_6_8mm | ≥90d | MacMahon 2017 §"Nodule shrinkage and resolution" |
| Nodule_subsolid_gte_6mm → Nodule_subsolid_lt_6mm | ≥90d | MacMahon 2017 §"Subsolid nodule resolution" (often infection or hemorrhage) |

## Inadmissible

| From → To | Reason |
|---|---|
| Nodule_lt_6mm → Nodule_gt_8mm (over <180 days) | Three-band growth incompatible with typical adenocarcinoma doubling times. Aggressive histology (e.g., small cell) handled via override on the admissible 180-day transition. |

## Verification protocol

1. Open MacMahon 2017 (DOI 10.1148/radiol.2017161659) Tables 1 (solid) and 2 (subsolid).
2. Confirm size bands and recommended follow-up intervals.
3. Open §"Doubling time" for biological constraints on growth rates.
4. Open §"Nodule shrinkage and resolution" + §"Subsolid nodule resolution" for benign-pattern documentation.

## Forward note (v1.1 upgrade path)

The categorical-band encoding here serves vendors emitting size-classified output. A v1.1 update will use the **continuous-biomarker channel** of the input contract (`mean_diameter_mm` as UCUM-typed `mm`) and replace bands with monotone-growth bounds, removing the discretization. This is precisely the use case for input contract v1.1's `continuous_biomarkers` field.

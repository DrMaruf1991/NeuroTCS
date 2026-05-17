# NeuroTCS Input Contract Specification

**Version:** 1.1.0
**Status:** Released
**Previous version:** 1.0.0 (backward compatible — all v1.0 submissions remain valid)
**Author:** Marufjon Salokhiddinov, MD, PhD · KIUT Tashkent
**Date:** May 2026
**License:** CC-BY-4.0 (specification) / MIT (reference implementation)

---

## 1. Purpose

This document specifies the **input contract** that any longitudinal medical AI system must satisfy in order to be audited by NeuroTCS. The contract is **disease-agnostic, model-agnostic, and vendor-agnostic**.

Version 1.1 extends v1.0 to support **continuous biomarker outputs** alongside categorical states. This addresses the most common gap reported by AI vendors: real products emit volumes, percentages, scores, and measurements — not only discrete categories.

The contract is the boundary between the AI being audited and the audit framework. Everything upstream (model architecture, training data, inference pipeline, vendor stack) is opaque to NeuroTCS. Everything downstream (rule packs, audit logic, scoring, fairness analysis) is opaque to the AI.

---

## 2. What's new in v1.1

| Change | Type | Detail |
|---|---|---|
| Continuous biomarkers | Additive | New `continuous_biomarkers` field on each prediction row |
| `predicted_state` now conditional | Relaxed | Required *unless* at least one continuous biomarker is present |
| `value_type` enum | New | `continuous`, `ordinal`, `count`, `percentage` |
| UCUM unit validation | New | Numeric units must conform to UCUM common subset |
| Reference range field | New | Optional `[low, high]` per biomarker |
| Long-format biomarker table | New | Alternative file `biomarkers.parquet` for high-cardinality cases |
| Three new disease domains | Additive | cardiology, oncology (general), pulmonology |
| Three new validation steps | New | Biomarker structural, UCUM, state-or-biomarker presence |

**Backward compatibility:** Every valid v1.0 submission remains valid under v1.1 with no changes. The `neurotcs_contract_version` field accepts both `"1.0.0"` and `"1.1.0"`.

---

## 3. Conformance levels (unchanged from v1.0)

| Level | Description | Auditable? |
|---|---|---|
| **L1 — minimum** | Required fields only. Patient ID, visit timestamp, predicted state OR continuous biomarker. | Yes, reduced features |
| **L2 — standard** | L1 plus uncertainty, treatment flags, patients table, and rule-pack reference. | Yes, full audit |
| **L3 — extended** | L2 plus anatomical attribution, source-image references, and provenance. | Yes, full audit + traceback |

The reserved words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in this document are used as defined in RFC 2119.

---

## 4. Submission structure

```
submission/
├── manifest.json          # required
├── predictions.parquet    # required (or predictions.json / predictions.csv)
├── patients.parquet       # required at L2+
├── biomarkers.parquet     # optional alternative for high-cardinality biomarkers
├── rule_pack.yaml         # optional — may reference a registered pack by ID
└── attribution/           # optional — required only at L3
    └── <patient_id>/
        └── <visit_id>.json
```

---

## 5. Manifest schema

### 5.1 Required fields

```json
{
  "neurotcs_contract_version": "1.1.0",
  "conformance_level": "L2",
  "submission_id": "string, globally unique",
  "submission_timestamp": "ISO 8601 UTC",
  "source_system": {
    "name": "string",
    "version": "string (semver)",
    "vendor": "string"
  },
  "disease_domain": "alzheimers|parkinsons|multiple_sclerosis|glioblastoma|stroke|cardiology|oncology|pulmonology|custom",
  "rule_pack": {"id": "string", "source": "registry|inline"},
  "data_files": {
    "predictions": "string — relative path",
    "patients":    "string — relative path (required at L2+)",
    "biomarkers":  "string — optional long-format biomarker table"
  },
  "cohort_summary": {
    "n_patients": "integer",
    "n_visits_total": "integer",
    "date_range": ["ISO 8601 date", "ISO 8601 date"]
  }
}
```

### 5.2 New disease domains in v1.1

`cardiology`, `oncology` (general), and `pulmonology` are added to support cardiac function AI, RECIST-based tumor measurement AI, and lung-disease tracking AI.

`custom` remains the escape hatch for domains not yet enumerated. Submissions using `custom` MUST provide an inline rule pack.

---

## 6. Predictions table

### 6.1 Required columns (L1)

| Column | Type | Description |
|---|---|---|
| `patient_id` | string | Stable patient identifier within the submission |
| `visit_id` | string | Stable visit identifier within the patient |
| `visit_timestamp` | ISO 8601 datetime | When this visit occurred |

### 6.2 Conditional requirement (v1.1)

**At least one of the following MUST be present and non-null for every row:**

- `predicted_state` (categorical, as in v1.0)
- At least one continuous biomarker (either inline in `continuous_biomarkers` field, or in `biomarkers.parquet` joined by patient_id and visit_id)

A row that has neither is rejected with `MISSING_STATE_AND_BIOMARKER`.

### 6.3 Categorical state

| Column | Type | Description |
|---|---|---|
| `predicted_state` | string \| null | Discrete clinical state. MUST match a state in the rule pack. NULL permitted iff at least one continuous biomarker is present for this row. |

### 6.4 Continuous biomarkers — inline format

| Column | Type | Description |
|---|---|---|
| `continuous_biomarkers` | array of objects | Zero or more biomarker measurements for this visit. |

Each biomarker object:

```json
{
  "name": "string — biomarker identifier (e.g. 'hippocampal_volume')",
  "value": "number",
  "unit": "string — UCUM common subset",
  "value_type": "continuous|ordinal|count|percentage",
  "reference_range": ["number", "number"] | null,
  "uncertainty": "number in [0,1] | null"
}
```

### 6.5 Continuous biomarkers — long format (alternative)

`biomarkers.parquet` columns:

| Column | Type | Description |
|---|---|---|
| `patient_id` | string | MUST match a row in predictions |
| `visit_id` | string | MUST match a row in predictions |
| `biomarker_name` | string | Stable identifier |
| `value` | number | The measurement |
| `unit` | string | UCUM-compliant |
| `value_type` | string | continuous \| ordinal \| count \| percentage |
| `ref_low` | number \| null | Lower bound of reference range |
| `ref_high` | number \| null | Upper bound of reference range |
| `uncertainty` | number in [0,1] \| null | Model confidence in the value |

A submission MAY use either inline OR long-format, but NOT both. If both, rejected with `BIOMARKER_FORMAT_CONFLICT`.

### 6.6 L2+ additional columns (unchanged from v1.0)

| Column | Type | Description |
|---|---|---|
| `uncertainty` | float in [0,1] \| null | Model confidence in `predicted_state` |
| `treatment_flags` | array of strings | Active treatment exception flags |

---

## 7. UCUM unit validation

To prevent unit-confusion errors that have caused real patient harm in clinical AI, v1.1 mandates that biomarker units conform to a **common subset of the UCUM standard**.

### 7.1 Permitted units

The reference validator ships with a curated allowlist:

- **Volume:** `mL`, `cm3`, `L`, `uL`, `mm3`
- **Length / area:** `mm`, `cm`, `m`, `mm2`, `cm2`
- **Mass:** `g`, `mg`, `kg`, `ug`, `ng`
- **Time:** `s`, `min`, `h`, `d`, `wk`, `mo`, `a`
- **Concentration:** `mg/dL`, `mmol/L`, `umol/L`, `ng/mL`, `pg/mL`, `IU/mL`, `g/L`
- **Pressure:** `mm[Hg]`, `cm[H2O]`, `kPa`
- **Dimensionless:** `%`, `1`, `score`
- **Counts:** `{count}`, `{events}/a`
- **Composite:** `mL/min/{1.73_m2}`, `m2`, `kg/m2`

### 7.2 Custom units

A submission MAY use a unit outside the allowlist by prefixing with `x-` (e.g. `x-custom_score`). Custom units bypass validation but generate a `CUSTOM_UNIT_USED` warning.

### 7.3 Unit consistency

The same biomarker name within a single submission MUST use a consistent unit. Mixing `mL` and `cm3` for `hippocampal_volume` is rejected with `INCONSISTENT_UNITS` even though dimensionally equivalent.

---

## 8. Reference range semantics

The `reference_range` field is **optional metadata**, not a rule. Reference ranges are NOT used by the audit to flag transitions. The audit uses only the rule pack.

If both the submission and the rule pack define a reference range for the same biomarker, **the rule pack takes precedence**.

---

## 9. Patients table (L2+, unchanged from v1.0)

Required columns: `patient_id`, `sex`, `age_at_baseline`, `race_ethnicity`, `site_id`, `scanner_vendor`. Disease-specific columns MAY be required by individual rule packs.

---

## 10. Identifier policy (unchanged from v1.0)

- No PHI in `patient_id` or `visit_id`
- Identifiers stable within submission
- PHI pattern scan applied to identifier columns

---

## 11. Time policy (unchanged from v1.0)

- Timestamps SHOULD be UTC
- Date-only visits use `00:00:00`
- Future timestamps rejected
- Ties generate `TIE_TIMESTAMP` warning

---

## 12. Validation pipeline

Eleven steps, three new in v1.1:

```
[1]  Schema validation against manifest.schema.json
[2]  File presence check
[3]  Predictions table structural validation
[4]  Patient ID cross-reference
[5]  PHI pattern scan
[6]  Categorical state vocabulary check
[7]  Temporal sanity check
[8]  Cohort summary cross-check
[9]  *** v1.1 *** Biomarker structural validation
[10] *** v1.1 *** UCUM unit validation and consistency
[11] *** v1.1 *** State-or-biomarker presence check
```

### Error codes (v1.1)

| Code | Severity | Trigger |
|---|---|---|
| `MISSING_STATE_AND_BIOMARKER` | ERROR | Row has neither `predicted_state` nor any biomarker |
| `INVALID_UCUM_UNIT` | ERROR | Unit not in allowlist and not `x-`-prefixed |
| `INCONSISTENT_UNITS` | ERROR | Same biomarker name uses different units across rows |
| `BIOMARKER_FORMAT_CONFLICT` | ERROR | Both inline AND long-format biomarkers present |
| `INVALID_VALUE_TYPE` | ERROR | `value_type` not in the four enumerated values |
| `NEGATIVE_VALUE_FOR_NONNEGATIVE_BIOMARKER` | WARNING | Volume/length/concentration is negative |
| `CUSTOM_UNIT_USED` | WARNING | `x-`-prefixed custom unit |
| `BIOMARKER_ORPHAN` | ERROR | Long-format row has no matching predictions row |
| `REFERENCE_RANGE_INVERTED` | WARNING | `ref_low > ref_high` |

---

## 13. Versioning policy

Semantic versioning. v1.1.0 is a **MINOR** release. All v1.0 submissions remain valid. NeuroTCS supports the current major version and the previous major version for at least 24 months.

---

## 14. Scope boundaries (unchanged from v1.0)

The contract does NOT specify:
- AI architecture or training
- Imaging acquisition
- Patient enrollment or consent
- Upstream clinical diagnosis
- Audit result display
- Rule pack authoring (separate spec)
- Numeric tolerances for biologically allowed continuous changes (rule pack territory)

---

## 15. Reference examples (v1.1)

1. **ADNI clinical → NeuroTCS** (categorical, L2) — from v1.0
2. **LUMIERE → NeuroTCS** (categorical, L2) — from v1.0
3. **ADNI volumetric → NeuroTCS** (continuous biomarkers from UCSFFSX7, L2) — new in v1.1

---

## 16. Open issues for v1.2

- Probabilistic state distributions
- Streaming submissions (REST API)
- Multi-modal predictions
- FHIR Observation output
- Cross-cohort federation
- Time-varying treatment_flags

---

## Appendix A — JSON Schema

Normative JSON Schema in `schemas/manifest.schema.json`. The schema file is authoritative.

## Appendix B — Glossary

- **Patient** — single human subject
- **Visit** — single longitudinal assessment
- **Transition** — directed edge between consecutive visits
- **State** — discrete clinical category
- **Biomarker** — continuous, ordinal, count, or percentage measurement
- **Rule pack** — YAML declaring allowed transitions/changes
- **Flag** — audit finding of rule violation
- **cTCS** — categorical Temporal Coherence Score
- **UCUM** — Unified Code for Units of Measure

## Appendix C — Change log

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-05-17 | Initial draft. Categorical states only. |
| 1.1.0 | 2026-05-17 | Continuous biomarkers. UCUM validation. Long-format option. Backward-compatible. |

---

*End of specification.*

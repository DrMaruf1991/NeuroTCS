# NeuroTCS Input Contract Specification

**Version:** 1.0.0
**Status:** Draft for review
**Author:** Marufjon Salokhiddinov, MD, PhD · KIUT Tashkent
**Date:** May 2026
**License:** CC-BY-4.0 (specification) / MIT (reference implementation)

---

## 1. Purpose

This document specifies the **input contract** that any longitudinal medical AI system must satisfy in order to be audited by NeuroTCS. The contract is **disease-agnostic, model-agnostic, and vendor-agnostic**. Any AI system whose output conforms to this contract can be audited without code changes to NeuroTCS itself.

The contract is the boundary between the AI being audited and the audit framework. Everything upstream (model architecture, training data, inference pipeline, vendor stack) is opaque to NeuroTCS. Everything downstream (rule packs, audit logic, scoring, fairness analysis) is opaque to the AI.

This separation is what makes the framework portable across diseases and across vendors.

---

## 2. Conformance levels

A submission to NeuroTCS conforms to this contract at one of three levels:

| Level | Description | Auditable? |
|---|---|---|
| **L1 — minimum** | Required fields only. Patient ID, visit timestamp, predicted state. | Yes, with reduced features |
| **L2 — standard** | L1 plus uncertainty, treatment flags, and rule-pack reference. | Yes, full audit |
| **L3 — extended** | L2 plus anatomical attribution, source-image references, and provenance. | Yes, full audit + traceback |

A conforming submission MUST declare its level in the manifest. NeuroTCS will refuse to audit submissions that fail validation at their declared level.

The reserved words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in this document are used as defined in RFC 2119.

---

## 3. Submission structure

A NeuroTCS submission is a directory or archive containing:

```
submission/
├── manifest.json          # required
├── predictions.parquet    # required (or predictions.json or predictions.csv)
├── patients.parquet       # required at L2+
├── rule_pack.yaml         # optional — may reference a registered pack by ID
└── attribution/           # optional — required only at L3
    └── <patient_id>/
        └── <visit_id>.json
```

The submission format is **deliberately simple**: a manifest + tabular predictions + optional patient metadata. No proprietary serialization. No vendor-specific binaries.

---

## 4. Manifest schema

The manifest declares what the submission contains and how it should be audited.

### 4.1 Required fields

```json
{
  "neurotcs_contract_version": "1.0.0",
  "conformance_level": "L2",
  "submission_id": "string, globally unique",
  "submission_timestamp": "ISO 8601 UTC, e.g. 2026-05-17T13:45:00Z",
  "source_system": {
    "name": "string — name of the AI system or pipeline",
    "version": "string — semver of the AI system",
    "vendor": "string — organization name; 'self' if internal"
  },
  "disease_domain": "string — one of {alzheimers, parkinsons, multiple_sclerosis, glioblastoma, stroke, custom}",
  "rule_pack": {
    "id": "string — registered rule pack ID, e.g. 'aa2024+trac@1.0'",
    "source": "string — 'registry' or 'inline'"
  },
  "data_files": {
    "predictions": "string — relative path",
    "patients": "string — relative path (required at L2+)"
  },
  "cohort_summary": {
    "n_patients": "integer",
    "n_visits_total": "integer",
    "date_range": ["ISO 8601 date", "ISO 8601 date"]
  }
}
```

### 4.2 Validation

The manifest MUST validate against the JSON Schema in `schemas/manifest.schema.json`. NeuroTCS refuses to audit submissions whose manifest fails schema validation. This is fail-closed by design.

---

## 5. Predictions table

The predictions table is the **core** of the submission. One row per (patient, visit, prediction).

### 5.1 Required columns (L1)

| Column | Type | Description | Constraints |
|---|---|---|---|
| `patient_id` | string | Stable patient identifier within the submission | non-empty, ≤64 chars, no PHI |
| `visit_id` | string | Stable visit identifier within the patient | non-empty, unique per (patient_id, visit_id) |
| `visit_timestamp` | ISO 8601 datetime | When this visit occurred | UTC; date-only acceptable if time unknown |
| `predicted_state` | string | Discrete clinical state predicted by the AI | MUST match a state defined in the rule pack |

### 5.2 Required columns (L2+)

| Column | Type | Description |
|---|---|---|
| `uncertainty` | float in [0, 1] | Model confidence in predicted_state (1.0 = certain). May be NULL if model doesn't produce uncertainty. |
| `treatment_flags` | array of strings | Active treatment exception flags at this visit (e.g. `["anti_amyloid"]`, `["pseudoprogression_window"]`). Empty array if none. |

### 5.3 Recommended columns (L3)

| Column | Type | Description |
|---|---|---|
| `attribution_ref` | string | Relative path to JSON file with anatomical attribution |
| `source_image_ref` | string | Reference to source imaging (DICOM SeriesInstanceUID, file path, etc.) |
| `model_provenance` | object | `{model_hash, training_data_hash, inference_timestamp}` |

### 5.4 Format

Predictions MUST be provided in **one of**:
- Apache Parquet (preferred, columnar, typed)
- JSON Lines (one JSON object per line)
- CSV with UTF-8 encoding and RFC 4180 quoting

Parquet is strongly preferred for cohorts >1,000 patients due to type safety and compression.

### 5.5 Ordering

The predictions table SHOULD be sorted by `(patient_id, visit_timestamp)` but is not required to be. NeuroTCS performs its own canonical sort before auditing. Sort stability is the **patient's** responsibility — if two visits have identical timestamps, the audit refuses to score that pair and emits a `TIE_TIMESTAMP` warning.

---

## 6. Patients table (L2+)

The patients table provides per-patient metadata required for subgroup fairness analysis.

### 6.1 Required columns

| Column | Type | Description |
|---|---|---|
| `patient_id` | string | MUST match values in predictions table |
| `sex` | enum | `{female, male, other, unknown}` |
| `age_at_baseline` | integer | Years at first visit |
| `race_ethnicity` | string | Free text or controlled vocabulary; `unknown` permitted |
| `site_id` | string | Stable imaging site identifier |
| `scanner_vendor` | string | e.g. `siemens`, `philips`, `ge`, `unknown` |

### 6.2 Disease-specific columns

The rule pack MAY require additional patient-level columns. For Alzheimer's, the AA 2024 rule pack requires:

| Column | Type | Description |
|---|---|---|
| `apoe_e4_status` | enum | `{negative, heterozygote, homozygote, unknown}` |
| `education_years` | integer | Years of formal education; `null` if unknown |

If the rule pack requires a column that is absent or all-null, NeuroTCS emits a `FAIRNESS_DIMENSION_UNAVAILABLE` warning and continues. Fairness analysis on that dimension is skipped, but the audit completes.

---

## 7. Anatomical attribution (L3 only)

When `attribution_ref` is provided, the referenced JSON file contains per-flag anatomical localization:

```json
{
  "patient_id": "string",
  "visit_id": "string",
  "method": "grad_cam | shap | integrated_gradients | other",
  "regions": [
    {
      "atlas": "AAL3 | Brainnetome | custom",
      "region_id": "string",
      "region_name": "string",
      "attribution_score": "float in [0, 1]"
    }
  ]
}
```

This is the **only** field that requires neuroimaging-specific format. Everything else in the contract is general enough to apply to oncology, neurology, or any other longitudinal AI domain.

---

## 8. Identifier policy

### 8.1 No PHI

`patient_id` and `visit_id` MUST NOT contain protected health information. Acceptable forms:
- Random UUIDs (`a8f3c91d-...`)
- Cohort-internal sequential IDs (`STUDY01_P0001`)
- Hashed identifiers (SHA-256 of MRN with cohort-specific salt)

Unacceptable:
- Patient names, initials, or partial names
- Medical record numbers (MRN) in plaintext
- Dates of birth in identifier strings
- Any field defined as direct or quasi-identifier under HIPAA Safe Harbor or GDPR Article 4(1)

NeuroTCS performs a pattern-based PHI scan on identifier columns. If a probable PHI pattern is detected (e.g. names matching a US Census top-1000 surname list combined with a numeric suffix), the audit refuses to proceed and emits a `PHI_PATTERN_DETECTED` error.

### 8.2 Stability

`patient_id` MUST be stable within the submission. The same physical patient MUST NOT appear under two different IDs in the same submission. Cross-submission stability is not required.

---

## 9. Time policy

### 9.1 Timezones

All timestamps SHOULD be in UTC. If a submission uses local time, the manifest MUST declare `"timezone": "..."` (IANA name, e.g. `Asia/Tashkent`).

### 9.2 Date-only visits

If only a date is known (no time), use 00:00:00 UTC. NeuroTCS will not infer intra-day ordering from anything other than `visit_timestamp`. Submitters who need finer ordering MUST provide actual times.

### 9.3 Future timestamps

Visits with timestamps in the future relative to `submission_timestamp` are rejected. Reason: prevents accidental ingestion of synthetic data labeled as real.

---

## 10. Validation behavior

NeuroTCS validation is a separate phase that runs **before** any audit logic.

### 10.1 Validation pipeline

```
submission
    ↓ [1] Schema validation against manifest.schema.json
    ↓ [2] File presence check (declared files must exist)
    ↓ [3] Predictions table structural validation
    ↓ [4] Patient ID cross-reference (predictions ↔ patients)
    ↓ [5] PHI pattern scan on identifier columns
    ↓ [6] Rule pack compatibility check (states declared in predictions must exist in rule pack)
    ↓ [7] Temporal sanity check (no future timestamps, no negative time deltas after sort)
    ↓ [8] Cohort summary cross-check (manifest counts must match actual data)
    ↓
[pass] → audit phase
[fail] → ValidationReport with all errors (NOT just the first)
```

### 10.2 Fail-closed

Validation failures HALT the audit. There is no "best effort" mode. If the contract is violated, NeuroTCS refuses to run.

### 10.3 Warnings vs errors

- **ERROR** — audit cannot proceed. Examples: missing required column, unknown state in predictions, PHI detected.
- **WARNING** — audit proceeds but flags a concern. Examples: a fairness dimension is fully NULL, a single uncertainty value is out of range while others are valid.

All errors and warnings are returned together in a single `ValidationReport` so submitters can fix everything at once.

---

## 11. Versioning policy

The contract uses semantic versioning (`MAJOR.MINOR.PATCH`):

- **MAJOR** — breaking changes. Old submissions will not validate. Migration guide required.
- **MINOR** — backward-compatible additions. New optional fields, new conformance levels.
- **PATCH** — clarifications, typo fixes, no field changes.

NeuroTCS maintains support for the **current major version** and the **previous major version** for at least 24 months. Older versions are deprecated with at least 12 months notice.

The current version is **1.0.0**.

---

## 12. What this contract does NOT specify

To prevent scope creep, the contract is explicit about its boundaries.

The contract does NOT specify:
- How the AI generates its predictions (architecture, training, hyperparameters)
- How the imaging is acquired (modality, protocol, scanner)
- How patients are enrolled or consented
- How clinical states are diagnosed upstream of the AI
- How the audit results are displayed to clinicians
- How rule packs are authored (separate spec)
- How NeuroTCS itself is implemented (separate spec)

These boundaries are deliberate. The contract is a **wire format**, not a methodology.

---

## 13. Reference examples

Three reference adapter examples are provided in the companion package:

1. **ADNI → NeuroTCS** — adapter converting ADNIMERGE2 DXSUM and demographics to a conforming submission (L2)
2. **LUMIERE → NeuroTCS** — adapter converting LUMIERE ExpertRating CSV to a conforming submission (L2)
3. **MU-Glioma-Post → NeuroTCS** — adapter using row-order-as-chronology with the validated 88.4% agreement (L2)

Each reference adapter is <200 lines of Python and demonstrates exactly what a vendor would write to integrate.

---

## 14. Open issues for v1.1

The following items are scoped out of v1.0 but identified for the next minor version:

- **Multi-modal predictions** — what if an AI emits a single prediction derived from MRI + CSF + cognitive testing? Need a `prediction_source` enum.
- **Probabilistic state assignments** — currently `predicted_state` is categorical. Should we accept `predicted_state_distribution` as `{CN: 0.1, MCI: 0.75, Dementia: 0.15}`?
- **Streaming submissions** — current contract is batch. Real-time submission protocol is a v2.0 candidate.
- **Adjudicated ground truth** — separate `ground_truth.parquet` for validation studies. Currently out of scope.
- **Cross-cohort federation** — submitting from multiple sites to a central audit. Requires authentication layer. Out of scope.

---

## Appendix A — JSON Schema

The normative JSON Schema for the manifest is in `schemas/manifest.schema.json`. The schema in this document is illustrative; the JSON Schema file is authoritative.

## Appendix B — Glossary

- **Patient** — a single human subject in the cohort
- **Visit** — a single longitudinal assessment of that patient
- **Transition** — a directed edge between two consecutive visits for the same patient
- **State** — a discrete clinical category (e.g. CN, MCI, Dementia)
- **Rule pack** — a YAML file declaring which transitions are biologically allowed
- **Flag** — an audit finding that a specific transition violates the rule pack
- **cTCS** — categorical Temporal Coherence Score = valid transitions ÷ total transitions

## Appendix C — Change log

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-05-17 | Initial draft |

---

*End of specification.*

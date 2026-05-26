# LAYER 4 DESIGN: PROTOCOL-COMPLIANCE AUDIT

**Status:** Design doc shipped in v1.18.0. Implementation begins v1.19.0.
**Design lock revision:** v1.18.0-design.1 (initial release).
**Authoring discipline:** mirrors LAYER_3_DESIGN.md v1.11.0-design.2.

---

## 0. Reading guide

Layer 4 audits **protocol compliance**: the question "does each patient
and each visit obey the trial protocol the manifest declares?" It is
the fourth and final tier of the NeuroTCS layered-audit architecture
(Layers 1-4 are documented in `docs/clinical_ranges/LAYER_CONTRACT.md`
section 4):

  - **Layer 1** -- temporal coherence (admissible state transitions)
  - **Layer 2** -- per-measurement plausibility (clinical-range packs)
  - **Layer 3** -- cross-sheet consistency (e.g., declared tool ↔ observed
    values; manifest claim ↔ on-disk contents)
  - **Layer 4** -- inclusion / protocol compliance (THIS DOC)

This document specifies what Layer 4 is, what it explicitly is NOT,
the schema for "protocol packs", the engine signature, the failure
semantics, the v1.19.0 first-shipment scope, and the deferred items.

The pattern follows LAYER_3_DESIGN.md exactly so engineers and
auditors can context-switch between layers without learning new
conventions.

---

## 1. The problem Layer 4 solves

A submission can be temporally coherent (Layer 1 green), have every
measurement in plausible range (Layer 2 green), and have every
manifest claim match the sheets (Layer 3 green) yet still violate the
trial protocol the submitter declared. Examples that ONLY Layer 4 can
catch:

1. The `manifest.protocol_pack_id` declares `clarity_ad_2022` (CLARITY-AD,
   lecanemab Phase 3, NCT03887455) whose inclusion range is age 50-90,
   amyloid-positive by CSF or PET, MMSE ≥ 22. The `patients.parquet`
   contains a patient aged 45. **Inclusion-criterion violation across
   manifest + patient sheet.**
2. The `manifest.treatment_arm` declares `lecanemab_10mg_per_kg_q2w` for
   patient P1 but `adherence.parquet` shows infusion records labeled
   `donanemab_700mg_q4w`. **Treatment-arm assignment ↔ drug-administered
   mismatch.**
3. The protocol pack `clarity_ad_2022` declares a visit schedule of 18
   bi-weekly visits over 18 months. `predictions.parquet` for patient
   P2 contains visit_id `V19` with a timestamp 21 months post-baseline.
   **Out-of-window visit; either a protocol deviation or a data-entry
   error.**
4. `predictions.parquet` records two distinct patients (`P3` and `P4`)
   sharing the same `subject_uid` field. **Patient-id collision /
   cross-patient row leakage.**
5. `predictions.parquet` shows that patient P5 received infusion #7 at
   day 84, the day after MRI showed ARIA-E radiographic severity
   grade 3 (severe), with concurrent symptomatic ARIA reported. Per
   the lecanemab label Table 2 and the AAN ARIA AUR, severe ARIA-E
   with symptoms requires suspending dosing. **Continued dosing across
   a label-mandated pause.**
6. The patient is enrolled in the `lecanemab` arm of CLARITY-AD but
   pretreatment amyloid PET Centiloid value is 12 (below the trial's
   declared positivity threshold of 22). **Amyloid-negative patient
   enrolled in an anti-amyloid arm.**

These violations are not detectable by Layers 1, 2, or 3 alone because
they require the **trial protocol** itself as a data input. The
manifest declares which protocol the submission targets; the protocol
pack provides the criteria the audit checks against.

---

## 2. Scope discipline — what Layer 4 is and isn't

### 2.1 Layer 4 IS

- A schema-validated, YAML-encoded **protocol pack** module that
  declares the inclusion criteria, exclusion criteria, treatment arms,
  visit schedule, dose schedule, and safety-stop rules of a single
  named clinical-trial protocol (one pack per trial).
- An execution function `audit_protocol_compliance(submission,
  protocol_pack)` that runs the protocol pack against a multi-sheet
  submission (manifest + patients + predictions + adherence +
  attribution) and emits citation-locked Layer 4 flags.
- A per-patient, per-visit audit. Each violation is one flag with
  deterministic `flag_id` (same SHA-256-over-canonical-JSON discipline
  as Layer 3 section 6).
- Anchored on **public regulatory primary sources**: the trial's
  ClinicalTrials.gov registration, the published Phase 3 protocol
  (e.g., supplementary appendix of the primary efficacy paper), the
  FDA label / EMA SmPC for the approved drug, the FDA Risk Evaluation
  and Mitigation Strategy (REMS) where present, the AAN Appropriate
  Use Recommendations (AUR) for that therapeutic class.
- Integrated with Layer 3's manifest-anchor discipline: Layer 4 relies
  on `cross_sheet/manifest_data_consistency@1.0.0` invariant
  `rulepack_reference_consistency` (and a parallel
  `protocolpack_reference_consistency` to be added in v1.20.0) to
  confirm the declared `protocol_pack_id` is a loadable pack before
  Layer 4 runs.

### 2.2 Layer 4 is NOT

- **NOT a protocol-document parser.** Layer 4 does NOT read a PDF
  protocol and infer rules. The rules are transcribed by hand from the
  primary source into a YAML protocol pack with full citation lock
  (PMID + DOI + public URL + ≥5 endorsing bodies), identical to the
  Layer 1 / Layer 2 / Layer 3 transcription discipline.
- **NOT a real-time monitor.** Layer 4 audits a snapshot. Live REMS
  reporting, pharmacovigilance, or trial-master-file generation are
  separate concerns.
- **NOT a regulatory submission tool.** Layer 4 produces a structured
  flag report. Whether that report becomes part of an FDA Form 1571 /
  Form 3500A workflow is downstream of NeuroTCS.
- **NOT inference of intent.** If the manifest declares treatment_arm
  `lecanemab_10mg_per_kg_q2w` and `adherence.parquet` shows a single
  off-protocol dose, Layer 4 emits the flag; it does NOT decide
  whether the deviation was intentional, harmless, or reportable.
  Adjudication is a human discipline.

### 2.3 What the v1.19.0 release will ship

To respect the "no partial fix" mandate, v1.19.0 will ship **the
infrastructure plus ONE world-class protocol pack**:

1. The `ProtocolPack` schema (`src/neurotcs/protocol_compliance/schema.py`),
   the loader (`src/neurotcs/protocol_compliance/loader.py`), and the
   execution function (`src/neurotcs/protocol_compliance/audit.py`).
2. **`protocols/lecanemab/clarity_ad_2022@1.0.0`** -- the first
   production protocol pack, transcribed from:
   - van Dyck CH, Swanson CJ, Aisen P, et al. Lecanemab in Early
     Alzheimer's Disease. NEJM 2023;388:9-21. PMID 36449413,
     DOI 10.1056/NEJMoa2212948. Supplementary appendix protocol.
   - ClinicalTrials.gov NCT03887455 (Phase 3 CLARITY-AD).
   - FDA lecanemab label (Leqembi BLA 761269, current revision).
   - AAN Appropriate Use Recommendations for lecanemab (Cummings 2023,
     J Prev Alz Dis, DOI 10.14283/jpad.2023.30).

CLARITY-AD is chosen as the first pack because it is (1) fully
published in NEJM with verbatim inclusion/exclusion criteria, (2) has
an active FDA-approved drug with a public label, (3) has a publicly
available AAN AUR, and (4) is the protocol most submissions to
NeuroTCS will target for amyloid-clearance audits today.

Subsequent protocol packs (TRAILBLAZER-ALZ 2, A4, AHEAD 3-45, DIAN-TU
NexGen) ship one per session in v1.20.0+, each at the same citation
discipline. The v1.18.0 SCOPE doc will track them as Tier 3 items.

The fourth-tier audit_all_layers() wrapper (LAYER_3_DESIGN.md §7.2)
will be extended in v1.19.0 to add a Layer 4 stage. The byte-exact
invariants of Layer 1 (cTCS, audit_id) and the existing Layer 2 / 3
golden hashes remain unchanged: Layer 4 is independent.

---

## 3. Conceptual model

The conceptual model mirrors Layer 3 closely. A `ProtocolPack` encodes:

- **identity** (`protocolpack_id`, `pack_version`, `effective_date`,
  `status`)
- **anchor citation** (the published trial paper + ClinicalTrials.gov
  ID + FDA label, with ≥5 endorsing bodies)
- **trial metadata** (sponsor, phase, drug, indication, target
  population)
- **inclusion criteria** (a list of named criteria, each a
  `CriterionSpec`)
- **exclusion criteria** (same shape; emit-on-match instead of
  emit-on-miss)
- **treatment arms** (declared arm names, dose, frequency, route)
- **visit schedule** (count, spacing, window tolerance)
- **safety stop rules** (e.g., ARIA-E grade-3 with symptoms → suspend
  dose; grade-3 macrohemorrhage → discontinue)
- **invariants** -- the cross-sheet checks that compose the above
  into actual Layer 4 flags

Each invariant has a `condition` (a `ProtocolConditionSpec`) drawn
from a fixed taxonomy of condition types (parallel to Layer 3's
`ConditionSpec`):

  1. **`age_in_inclusion_range`** -- check patient age at baseline is
     within `[lo, hi]` declared in the protocol pack.
  2. **`amyloid_status_consistent_with_treatment_arm`** -- if arm is
     anti-amyloid, pretreatment amyloid biomarker must be positive
     per the trial's declared threshold.
  3. **`visit_id_within_protocol_window`** -- visit timestamp must fall
     within `protocol_day +/- window_days`.
  4. **`treatment_arm_matches_drug_administered`** -- the
     `manifest.treatment_arm` declaration for each patient must agree
     with every infusion record in `adherence.parquet`.
  5. **`severe_aria_then_dose_suspension_recorded`** -- if predictions
     records ARIA-E grade 3 (or symptomatic ARIA), the next adherence
     row for that patient must be a paused or discontinued dose
     within the label-mandated grace window.
  6. **`patient_id_no_cross_row_collision`** -- patient_id values must
     uniquely partition the predictions sheet (no two distinct
     biological patients share the same id).

These six condition types cover the six examples in section 1. The
taxonomy is closed (extra: forbid, frozen) for v1.19.0; new condition
types require a design-doc amendment and a session-tagged engine
extension.

---

## 4. Protocol pack schema

### 4.1 Top-level pack

```yaml
schema_version: "1.0.0"
protocolpack_id: "protocols/lecanemab/clarity_ad_2022@1.0.0"
pack_version: "1.0.0"
effective_date: "2026-MM-DD"
status: "production"           # production | research_preview | deprecated
domain: "clarity_ad_2022"
framework_name: "CLARITY-AD lecanemab Phase 3 protocol compliance audit"
transcribed_by: "Salokhiddinov M, MD PhD ..."

anchor_citation:               # mirrors LAYER_3_DESIGN section 4.1
  citation_pmid: "36449413"
  citation_doi: "10.1056/NEJMoa2212948"
  citation_text: |
    van Dyck CH, Swanson CJ, Aisen P, et al. Lecanemab in Early
    Alzheimer's Disease. NEJM 2023;388(1):9-21.
  public_url: "https://www.nejm.org/doi/full/10.1056/NEJMoa2212948"
  registration_id: "NCT03887455"
  fda_application: "BLA 761269"
  endorsing_bodies:
    - "Eisai/Biogen (sponsor)"
    - "U.S. Food and Drug Administration (FDA, Leqembi BLA 761269)"
    - "European Medicines Agency (EMA, Leqembi SmPC)"
    - "Alzheimer's Association"
    - "AAN Appropriate Use Recommendations (Cummings 2023)"
    - "ICH-GCP E6(R3)"
    - "21 CFR 312.50/56 (Investigational New Drug regulations)"

trial_metadata:
  sponsor: "Eisai / Biogen"
  phase: 3
  drug: "lecanemab"
  indication: "Early Alzheimer's disease (MCI due to AD or mild AD dementia)"
  target_n: 1795
  start_date: "2019-03"
  primary_completion: "2022-09"
  drug_class: "anti-amyloid monoclonal antibody"

inclusion_criteria:
  - name: "age_50_90"
    criterion: "Age >= 50 and <= 90 at baseline"
    condition:
      type: "age_in_inclusion_range"
      lo: 50
      hi: 90
    citation: {...}
  - name: "amyloid_positive"
    criterion: "Pretreatment amyloid PET Centiloid >= 22 OR CSF Aβ42:Aβ40 < 0.067"
    condition:
      type: "amyloid_status_consistent_with_treatment_arm"
      pretreatment_centiloid_threshold: 22
      csf_abeta_ratio_threshold: 0.067
    citation: {...}
  - name: "mmse_22_30"
    criterion: "MMSE 22-30 at screening"
    condition: {...}
    citation: {...}

exclusion_criteria:
  - name: "concomitant_anticoagulant_at_screen"
    criterion: "Receiving warfarin or DOAC at screen"
    condition: {...}
    citation: {...}

treatment_arms:
  - name: "lecanemab_10mg_per_kg_q2w"
    drug: "lecanemab"
    dose_mg_per_kg: 10
    frequency_weeks: 2
    route: "intravenous"
  - name: "placebo"
    drug: "placebo"

visit_schedule:
  total_visits: 18
  spacing_weeks: 2
  window_days: 7

safety_stop_rules:
  - name: "aria_e_grade_3_symptomatic_suspend"
    condition: "ARIA-E radiographic grade 3 with concurrent symptoms"
    action: "suspend_dose"
    citation: {...}

invariants:
  - name: "age_within_inclusion_range"
    condition: {type: "age_in_inclusion_range", lo: 50, hi: 90}
    flag_severity: "error"
    citation: {...}
  # ...one invariant per protocol promise
```

### 4.2 `CriterionSpec`

Each inclusion / exclusion criterion is a frozen pydantic model with:

  - `name: str` (snake_case, unique within the pack)
  - `criterion: str` (verbatim text from the protocol document)
  - `condition: ProtocolConditionSpec` (one of the six condition types)
  - `citation: Citation` (PMID + DOI + ≥5 endorsing bodies)

Inclusion criteria emit a flag when the condition FAILS for a patient.
Exclusion criteria emit a flag when the condition SUCCEEDS for a
patient (the patient should have been excluded; they weren't).

### 4.3 `ProtocolConditionSpec`

The six condition types listed in section 3 are formalized as:

```python
class AgeInInclusionRangeCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["age_in_inclusion_range"]
    lo: float = Field(..., ge=0)
    hi: float = Field(..., le=130)
    age_source_field: str = Field(default="age_at_baseline")

class AmyloidStatusConsistentWithTreatmentArmCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["amyloid_status_consistent_with_treatment_arm"]
    pretreatment_centiloid_threshold: float | None = None
    csf_abeta_ratio_threshold: float | None = None
    arm_names_requiring_positive: list[str] = Field(..., min_length=1)

class VisitIdWithinProtocolWindowCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["visit_id_within_protocol_window"]
    expected_day: int = Field(..., ge=0)
    window_days: int = Field(..., ge=0)
    visit_id_pattern: str  # regex matching the visit_id label, e.g. "^V(\\d+)$"

class TreatmentArmMatchesDrugAdministeredCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["treatment_arm_matches_drug_administered"]
    arm_to_drug_map: dict[str, str]      # arm_name -> drug_name
    permitted_alias_map: dict[str, list[str]] = Field(default_factory=dict)

class SevereAriaThenDoseSuspensionCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["severe_aria_then_dose_suspension_recorded"]
    aria_severity_field: str = Field(default="aria_e_grade")
    severe_grade_value: int = 3
    grace_window_days: int = 14
    expected_action: Literal["suspend", "discontinue"] = "suspend"

class PatientIdNoCrossRowCollisionCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: Literal["patient_id_no_cross_row_collision"]
    primary_key_field: str = Field(default="patient_id")
    secondary_uniqueness_fields: list[str] = Field(default_factory=list)
```

Each condition type has a dedicated `_evaluate_*()` function in
`src/neurotcs/protocol_compliance/audit.py`, mirroring the per-type
implementation structure in Layer 3's audit.py.

### 4.4 No code execution in YAML

Same discipline as Layer 3 section 4.5: protocol packs are static
YAML/JSON-Schema-validated data. No regex compilation, no Python eval,
no function references in the pack itself. The condition types
enumerate the closed set of behaviors the engine knows how to execute.

---

## 5. Input contract impact

### 5.1 New manifest fields (v1.3.0 input contract)

Layer 4 requires two new manifest fields, shipped in input contract
v1.3.0 (to be released alongside the v1.19.0 protocol-compliance
module):

- **`protocol_pack.id`** (string) -- the loadable `protocolpack_id` the
  submitter targets. Required when Layer 4 audit is requested.
- **`patient_arm_assignments`** (object: patient_id → arm_name) -- the
  declared treatment-arm assignment per patient. Required when the
  protocol pack declares treatment_arms.

These fields are OPTIONAL for v1.2.0-conforming submissions; Layer 4
audit is opt-in. Submissions without these fields receive a Layer 4
status of `not_audited`, not a failure.

### 5.2 New optional sheet: `adherence`

Existing sheets (`predictions`, `patients`, `biomarkers`, `attribution`)
are unchanged. v1.3.0 adds a new optional sheet:

- **`adherence`** -- per-dose record. Columns: `patient_id`, `visit_id`,
  `infusion_date`, `drug_administered`, `dose_amount`,
  `dose_unit`, `infusion_status` (one of: `completed`, `partial`,
  `held`, `discontinued`).

Required when the protocol pack declares treatment_arms AND the
manifest opts in to Layer 4 audit. Without an `adherence` sheet, the
treatment-arm-related invariants emit `info`-severity coverage-gap
flags rather than `error`.

---

## 6. Flag-ID derivation

Identical discipline to Layer 3 section 6. The `flag_id` is SHA-256
over canonical-JSON of:

  - the loaded protocol pack's `yaml_sha256` (covers the pack
    content)
  - the invariant `name`
  - the source-sheet input hashes (canonical-JSON of the affected
    rows)
  - the observed value(s) that produced the flag
  - the join_key_values (e.g., `{patient_id: P1, visit_id: V7}`)

This makes Layer 4 flag IDs reproducible across machines and time. A
re-run on the same submission with the same protocol pack produces
the same flag_id; a different submission, different pack, or
different observed values produces a different flag_id.

Excluded from flag_id (parallel to Layer 3 section 6.3):

  - The audit timestamp
  - The auditor identity
  - The order of flags in the audit report

---

## 7. Integration with Layers 1, 2, 3

### 7.1 The composite audit pipeline (extended)

```
Layer 1 (temporal coherence)   ->  Layer1Result (audit_id, cTCS)
Layer 2 (per-measurement)      ->  Layer2Result (range flags)
Layer 3 (cross-sheet)          ->  Layer3Result (cross-sheet flags)
Layer 4 (protocol compliance)  ->  Layer4Result (protocol flags)   <-- NEW
```

### 7.2 `audit_all_layers()` extension

The convenience wrapper in `src/neurotcs/__init__.py` will gain a
`layer_4_protocol_pack: ProtocolPack | None = None` keyword arg in
v1.19.0. When None, Layer 4 is skipped. When provided, Layer 4 runs
after Layers 1-3 and its flags are appended to the unified ledger
under `audit_layer = "layer_4_protocol_compliance"`.

### 7.3 Byte-exact preservation

Layer 4 does NOT modify the Layer 1 audit_id calculation, the Layer 2
clinical_ranges pack contents, or the Layer 3 cross-sheet flag IDs.
The byte-exact invariants captured in the existing test golden tables
(`tests/clinical_ranges/test_yaml_sha256_cross_platform.py`,
`tests/audit_core/test_real_*_audit.py`) remain unchanged through the
v1.19.0 release.

### 7.4 Fairness audit integration

Layer 4 flags participate in the fairness audit (MIRIAD invariants):
disparate flag rates by site, sex, or APOE genotype trigger the same
fairness-flag pipeline that Layer 2 / 3 flags do. The fairness module
treats Layer 4 flags as ordinary audit findings tagged with
`audit_layer = "layer_4_protocol_compliance"`.

---

## 8. Fail-closed semantics

Same five-rule discipline as Layer 3 section 8:

1. **Missing required sheets** -- if `protocol_pack` declares arms and
   `adherence` is missing, Layer 4 emits an `info`-severity coverage
   flag per invariant that needed the sheet. Audit continues.
2. **Schema-invalid input sheets** -- Layer 4 refuses to run if the
   submission failed v1.3.0 input-contract validation. No partial
   audit.
3. **Non-production protocol pack** -- `audit_protocol_compliance()`
   refuses to run a research_preview / deprecated protocol pack
   against a production submission (the call raises
   `ProtocolPackNotProduction`). research_preview packs run in
   dry-run mode for development only.
4. **Protocol pack schema invalid** -- pydantic strict-mode failure
   raises at pack load time. The framework cannot run an invalid pack.
5. **Citation strength below international_consensus** -- production
   protocol packs require every invariant at
   `citation_strength: international_consensus` with ≥5 endorsing
   bodies and a public URL. Bounds at `derived` strength are allowed
   only in research_preview packs.

---

## 9. The exact v1.19.0 protocol pack

### 9.1 `protocols/lecanemab/clarity_ad_2022@1.0.0` (production)

**Anchor:** van Dyck CH et al. NEJM 2023;388:9-21 (PMID 36449413),
ClinicalTrials.gov NCT03887455, FDA Leqembi label BLA 761269, AAN
AUR (Cummings 2023, DOI 10.14283/jpad.2023.30).

**Invariants (6):**

1. **`age_within_50_to_90`** -- inclusion criterion 1 (age range).
   Type: `age_in_inclusion_range` with lo=50, hi=90.
2. **`amyloid_positive_pretreatment_for_lecanemab_arm`** -- inclusion
   criterion 2 (biomarker positivity).
   Type: `amyloid_status_consistent_with_treatment_arm` with
   centiloid_threshold=22, csf_abeta_ratio_threshold=0.067,
   arm_names_requiring_positive=["lecanemab_10mg_per_kg_q2w"].
3. **`visit_id_within_2_week_window`** -- bi-weekly visit schedule.
   Type: `visit_id_within_protocol_window` with expected_day per visit
   index and window_days=7.
4. **`treatment_arm_matches_drug_administered`** -- arm-to-drug
   consistency.
   Type: `treatment_arm_matches_drug_administered` with arm_to_drug_map
   = {lecanemab_10mg_per_kg_q2w: "lecanemab", placebo: "placebo"}.
5. **`severe_aria_e_with_symptoms_requires_dose_suspension`** -- AAN
   AUR and Leqembi label Table 2.
   Type: `severe_aria_then_dose_suspension_recorded` with
   severe_grade_value=3, expected_action="suspend".
6. **`patient_id_no_cross_row_collision`** -- per-row uniqueness.
   Type: `patient_id_no_cross_row_collision`.

**Citation strength:** all 6 at `international_consensus`, anchored on
the NEJM primary paper + FDA label + EMA SmPC + AAN AUR + ICH-GCP +
21 CFR 312.

### 9.2 Total v1.19.0 invariant count

6 invariants in 1 production protocol pack. All at
international_consensus standard. Every invariant cites a primary
source. Every invariant has ≥5 endorsing bodies (sponsor + FDA + EMA
+ AAN AUR + ICH-GCP + AA where applicable).

### 9.3 What is NOT in v1.19.0 (honest exclusion)

- **TRAILBLAZER-ALZ 2 (donanemab) pack** -- deferred to v1.20.0 (one
  pack per session keeps the citation discipline tight).
- **A4 / AHEAD 3-45 (pre-symptomatic prevention trials) packs** --
  deferred to v1.21.0+.
- **DIAN-TU (autosomal-dominant AD) pack** -- deferred indefinitely;
  ADAD cohort integration is a separate roadmap item.
- **REMS reporting integration** -- Layer 4 emits flags only; the
  REMS submission workflow is downstream.
- **Adjudication of intent** -- per-case flag review remains a human
  task; Layer 4 reports the structural violation.
- **PK/PD modeling** -- Layer 4 does not model drug exposure curves;
  the dose-window check is a structural-compliance check only.

---

## 10. Test strategy

Mirrors LAYER_3_DESIGN.md section 10:

- **Schema tests** -- every condition type round-trips through
  pydantic; invalid packs raise; extra fields are rejected.
- **Per-invariant unit tests** -- one fire-case and one silent-case
  per invariant in the v1.19.0 pack (so 12 tests for the 6 invariants).
- **Pack yaml_sha256 lock** -- new test file
  `tests/protocol_compliance/test_yaml_sha256_cross_platform.py`
  parallel to the Layer 2 / 3 golden tables.
- **Cross-platform LF/CRLF lock** -- protocol pack hashes match
  byte-for-byte across Linux + Windows.
- **Production gate test** -- attempting to run a non-production pack
  against a production submission raises `ProtocolPackNotProduction`.
- **Integration test** -- `audit_all_layers()` with the v1.19.0
  pack against a synthetic CLARITY-AD-shaped submission, asserting
  Layer 1 byte-exact invariants are preserved.

Target: 30+ Layer-4-specific tests in the v1.19.0 release.

---

## 11. Migration path for Tier 3 backlog (20 items)

The SCOPE_RESPONSE_TO_EXTERNAL_AUDIT.md document tracks 20 Tier 3
items that were previously blocked on Layer 4. With this design doc
shipped, the 20 items are now categorized into v1.19.0 / v1.20.0 /
v1.21.0 / deferred buckets based on which protocol pack they map to:

  - **v1.19.0 (CLARITY-AD pack covers):** 6 items (age, amyloid status,
    visit window, arm-drug match, ARIA suspension, patient_id
    collision).
  - **v1.20.0 (TRAILBLAZER-ALZ 2 pack covers):** 5 items (donanemab-
    specific safety stops, MTC integration, plaque-clearance discon
    criterion, ApoE4 dose-modification subset, infusion-reaction
    handling).
  - **v1.21.0 (A4 / AHEAD pack covers):** 4 items (pre-symptomatic
    eligibility, screen failure rate, prevention-trial visit
    spacing, pre-symptomatic biomarker thresholds).
  - **Deferred (require new condition types or external cohorts):** 5
    items (open-label extension semantics, post-marketing REMS
    reporting, pediatric-protocol subset, ADAD-DIAN integration,
    HIPAA-de-identification cross-check). These remain in the SCOPE
    document as "v1.x backlog".

---

## 12. Open design questions for v1.19.0 implementation

The following questions are deliberately deferred to v1.19.0
implementation (will be resolved with session-numbered design.2 update):

- **Q1.** Should the `amyloid_status_consistent_with_treatment_arm`
  condition accept the v1.4.0 NIA-AA Core 1 plasma threshold (e.g.
  Lumipulse pTau217 / Aβ42 ratio per FDA 510(k) May 2025) as a third
  positivity pathway, or restrict to CSF and PET per the original
  CLARITY-AD protocol?
- **Q2.** Should `visit_id_within_protocol_window` accept clock-time
  drift up to the EMA-permitted 7-day window, or use the stricter
  FDA-typical 3-day window?
- **Q3.** Should `severe_aria_then_dose_suspension_recorded` differentiate
  symptomatic vs. asymptomatic ARIA-E grade 3? The Leqembi label
  Table 2 differentiates; the AAN AUR collapses for clarity.
- **Q4.** Should Layer 4 emit a separate `Layer4Result` object or
  fold into the existing `Layer3Result` via the unified ledger? The
  ledger discipline favors a single result type with audit_layer
  field; the original LAYER_3_DESIGN section 7.1 already established
  this pattern.

These are tracked in `docs/design/LAYER_4_DESIGN_QUESTIONS.md` and
will receive verbatim citation-locked answers before v1.19.0 ships.

---

## 13. Design lock signature

**Design status:** Design doc shipped in v1.18.0. Implementation has
not begun.

**Lock revision:** v1.18.0-design.1 (initial release).

**Authored by:** Dr. Marufjon Salokhiddinov (KIUT, Uzbekistan),
2026-05-29, v1.18.0 session.

**Next revision:** v1.19.0-design.2 will lock open design questions
Q1-Q4 above before any code is written. No partial implementation;
the protocol pack schema must be complete before the first pack is
transcribed.

This document mirrors LAYER_3_DESIGN.md v1.11.0-design.2 in structure
and discipline. Any deviation is intentional and is documented inline
with a "v1.18.0-design.1 deviation:" comment.

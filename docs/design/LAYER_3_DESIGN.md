# Layer 3 -- Cross-Sheet Consistency Audits: Design Document

**NeuroTCS architecture spec**
**Status:** DESIGN LOCKED (do not modify without bumping `v1.11.0-design.N`)
**Target release:** v1.11.0
**Design author:** Salokhiddinov M, MD PhD, KIUT Tashkent, 2026-05-25
**Predecessor:** v1.10.2 (production: 6 packs / 100 bounds; research_preview: 1 pack; deprecated: 6 packs; Layer 1 byte-exact preserved across 5 cohorts)

---

## 0. Reading guide

This document is the **architectural lock** for Layer 3. It does NOT contain implementation code. It specifies:

- What Layer 3 audits and what it does NOT audit (scope discipline)
- The schema for cross-sheet invariants (the Layer 3 analog of rulepacks / range packs)
- The multi-sheet input contract extension (relative to v1.1.0)
- The `flag_id` derivation rule (the Layer 3 analog of `audit_id`)
- Integration with the existing Layer 1 and Layer 2 audit pipelines
- Fail-closed semantics
- Test strategy (golden values, parametrization, fail-closed verification)
- The exact set of cross-sheet rules that v1.11.0 will ship (the world-class scope)
- Honest exclusions: rules NOT in v1.11.0 and why

When implementation begins (v1.11.0-rc1, separate session), every code change MUST trace to a specific section of this document. Implementation drift from this design requires a new design-lock release (`v1.11.0-design.2`) with explicit changelog of what changed and why.

---

## 1. The problem Layer 3 solves

Layer 1 (rulepacks, since v1.8.x) audits **temporal coherence**: do the categorical disease-state transitions across a patient's visits respect the rules of a published staging framework (NIA-AA 2018 for AD)?

Layer 2 (clinical_ranges, since v1.10.0) audits **per-measurement plausibility**: does each numeric measurement fall within published biologically-plausible bounds, with citation-locked thresholds at international_consensus standard?

Both Layer 1 and Layer 2 operate **within a single sheet** at a time. Layer 1 looks at `predictions.parquet` only. Layer 2 looks at `predictions.parquet` (or `biomarkers.parquet`) only. Neither layer can detect inconsistencies that span multiple sheets of the same submission.

**Examples of cross-sheet inconsistencies that no current layer can detect:**

1. The `manifest.json` declares `upstream_volumetry_tool: "neuroquant_5.0"` but values in `biomarkers.parquet` are outside the NeuroQuant 5.0 normative range and within the FreeSurfer-recon-all output range. **The submission is internally inconsistent: the declared tool did not produce the values.**

2. The `patients.parquet` declares `apoe_genotype: "e4/e4"` (homozygous) but the `predictions.parquet` shows the patient never enters MCI or AD states across 10 years of follow-up. **The cross-sheet claim is biologically implausible** (E4/E4 carries ~12x AD risk vs E3/E3 per the v1.10.0 genetics/apoe_consensus pack).

3. The `manifest.json` declares `study_inclusion_age_range: [60, 85]` but `patients.parquet` contains a patient with `age_at_baseline: 45`. **Protocol violation across sheets.**

4. The `predictions.parquet` shows a patient transitioning from "AD" back to "CN" between visits, AND the `biomarkers.parquet` shows the patient's hippocampal volume increased by 40% between the same visits. **Both Layer 1 (Layer 1 already flags the categorical reversal as a TRAC violation) and the biomarker direction agree that this is impossible; the cross-sheet evidence is what makes it conclusive.**

5. The submission declares `conformance_level: "L3"` in `manifest.json` but the `attribution/` directory is missing files for patients listed in `predictions.parquet`. **Internal inconsistency between manifest claim and on-disk evidence.**

These are not edge cases. (1)-(3) appear in real trial submissions; (4) is the kind of inconsistency that catches mis-merged datasets; (5) is the kind of inconsistency that catches an incomplete export.

**Layer 3 audits the joins.** It is the framework's first layer that operates on the submission as a whole rather than on a single sheet at a time.

---

## 2. Scope discipline -- what Layer 3 is and isn't

### 2.1 Layer 3 IS

A new audit layer that:

- Loads multiple sheets from a single conformant input-contract submission
- Applies citation-locked **cross-sheet invariant rules** ("invariants" hereafter)
- Emits **cross-sheet flags** with deterministic `flag_id` derived from the input + the invariant pack
- Refuses to flag against non-production invariant packs (parallel to Layer 1 / Layer 2 status discipline)
- Integrates with the existing fairness audit so cross-sheet flags can be stratified by sex, age band, race, scanner, etc.
- Preserves the existing Layer 1 and Layer 2 audit pipelines exactly (no breakage; their `audit_id` invariants remain byte-exact)

### 2.2 Layer 3 is NOT

Explicitly out of scope for v1.11.0 to preserve world-class discipline:

- **Not a protocol-document parser.** Layer 3 reads structured cross-sheet declarations from the submission. Parsing a trial protocol PDF to extract inclusion criteria is Layer 4 (v1.12.0+).
- **Not a fuzzy matcher.** Cross-sheet rules are exact: declared-tool-X means values-must-be-in-tool-X-range. No probabilistic "this looks like NeuroQuant" inference.
- **Not a vendor identifier.** Layer 3 trusts the manifest's `upstream_volumetry_tool` declaration. If the trial lies about the tool, Layer 3 detects the inconsistency between declared tool and observed values, but it does not attempt to fingerprint the tool from value patterns.
- **Not a multi-submission auditor.** Layer 3 audits one submission at a time. Cross-trial comparisons (meta-audit) are out of scope.
- **Not a replacement for Layer 1 or Layer 2.** Layer 3 adds cross-sheet rules; the existing within-sheet audits continue to run unchanged.

### 2.3 What the v1.11.0 release will ship

To respect the "no partial fix" mandate, v1.11.0 will ship **three world-class invariant packs**, each at `international_consensus` standard with verbatim citation lock:

1. **`cross_sheet/tool_declaration_consistency@1.0.0`** -- anchors on the `upstream_volumetry_tool` field already present in `mri_volumetrics/structural_volumetry_consensus@1.0.0` (v1.10.2). Verifies that declared-tool-X implies values are consistent with tool-X's normative range.
2. **`cross_sheet/genotype_phenotype_consistency@1.0.0`** -- verifies that the APOE genotype declaration in `patients.parquet` is consistent with the temporal trajectory in `predictions.parquet` over the appropriate evidence window. Note: this is *consistency*, not deterministic prediction. APOE4/4 + lifelong CN is rare but not impossible; this pack flags for review, not for rejection.
3. **`cross_sheet/manifest_data_consistency@1.0.0`** -- verifies that manifest-level declarations (conformance_level, age range if declared, biomarker-presence flag) are consistent with the actual contents of the parquet sheets.

The fourth candidate -- temporal reversal cross-checked against biomarker direction -- is deferred to v1.11.1 because it requires a new test cohort to derive golden values. v1.11.0 will not ship without golden values.

---

## 3. Conceptual model

Layer 3 introduces a single new abstraction: the **cross-sheet invariant pack** (`InvariantPack`).

```
LAYER 1: RulePack       <-->   audits within one sheet (predictions)
LAYER 2: RangePack      <-->   audits within one sheet (predictions or biomarkers)
LAYER 3: InvariantPack  <-->   audits across multiple sheets (any combination)
```

The three pack types share architectural primitives by deliberate parallel design:

| Primitive | RulePack (L1) | RangePack (L2) | InvariantPack (L3) |
|---|---|---|---|
| YAML location | `src/neurotcs/rulepack/rules/<framework>.yaml` | `src/neurotcs/clinical_ranges/ranges/<domain>/<name>.yaml` | `src/neurotcs/cross_sheet/invariants/<domain>/<name>.yaml` |
| Pydantic schema | `rulepack/schema.py` | `clinical_ranges/schema.py` | `cross_sheet/schema.py` (new) |
| Status enum | production / draft | production / research_preview / deprecated / skeleton / planned | **production / research_preview / deprecated / skeleton / planned** (identical to L2) |
| Hash | `rulepack.canonical_sha256` | `rangepack.canonical_sha256` + `yaml_sha256` | **`invariantpack.canonical_sha256` + `yaml_sha256`** (parallel to L2) |
| Audit ID | `audit_id` | `flag_id` | **`flag_id`** (parallel to L2; L3 flags carry their own derivation) |
| Per-bound citation | per-rule | per-bound | **per-invariant** |
| Endorsing-body floor | n/a | >=5 for international_consensus | **>=5 for international_consensus** |
| Fail-closed | refuses non-production pack | refuses non-production pack | **refuses non-production pack** (identical) |

This parallel design is intentional. A reviewer who understands Layer 2 can read Layer 3 code in 10 minutes.

---

## 4. Cross-sheet invariant pack schema

### 4.1 Top-level pack

An `InvariantPack` has the same top-level fields as a `RangePack` (schema_version, rangepack_id->invariantpack_id, pack_version, effective_date, status, domain, framework_name, transcribed_by, clinical_source_authority, anchor_citation, notes, deprecated_in_favor_of, deprecation_reason) PLUS:

- `invariants: list[CrossSheetInvariant]` (>=1, parallel to `measurements: list[MeasurementRange]`)

Identifier format: `cross_sheet/<domain>/<name>@<version>` (e.g. `cross_sheet/tool_declaration_consistency@1.0.0`).

### 4.2 The `CrossSheetInvariant`

Each `CrossSheetInvariant` declares which sheets it joins, what condition it checks, and what flag severity to emit on violation.

Conceptually:

```
invariant = {
  name: str                          # stable identifier within the pack
  description: str                   # human-readable
  sheets_required: list[SheetSpec]   # which sheets must be present; type-tagged
  join_keys: list[str]               # how to align rows across sheets (e.g. patient_id)
  condition: ConditionSpec           # the actual check
  flag_severity: Literal["error", "warning", "info"]
  citation: Citation                 # same Citation type as L2
  citation_strength: CitationStrength  # same enum as L2 (verbatim / derived / international_consensus)
  guideline_section: str             # source section reference
}
```

### 4.3 `SheetSpec` (which sheets are required)

```
SheetSpec = {
  role: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"]
  required: bool                     # true if invariant cannot run without this sheet
}
```

Layer 3 will not invent sheets. The roles correspond exactly to the existing v1.1.0 input contract submission structure (manifest.json, predictions.parquet, patients.parquet, biomarkers.parquet, attribution/).

### 4.4 `ConditionSpec` (the actual check)

This is the only meaningfully new piece of schema. v1.11.0 supports exactly **four** condition types -- no more. Each is a closed, finite specification with no free-form code execution. This is critical for safety and for citation-locking the rule.

#### 4.4.1 `categorical_implies_range`

For a row joined across two sheets: if `categorical_field` in sheet A equals `value`, then `numeric_field` in sheet B must be within `[lo, hi]`.

```
condition = {
  type: "categorical_implies_range"
  source_sheet: "manifest"           # role from SheetSpec
  source_field: "upstream_volumetry_tool"
  source_value: "neuroquant_5.0"     # the trigger value
  target_sheet: "biomarkers"
  target_field: "hippocampal_volume_total_mm3"
  target_range: { lo: 2800, hi: 5000 }  # tool-specific normative
}
```

This is the formalism for "if the trial declares NeuroQuant 5.0, hippocampal values should be in NeuroQuant 5.0's normative range." If a violation is found, the flag includes the actual value, the declared tool, and the tool-specific range that was violated.

#### 4.4.2 `field_presence_consistency`

If a manifest field declares X, the corresponding sheet must (or must not) contain feature Y.

```
condition = {
  type: "field_presence_consistency"
  source_sheet: "manifest"
  source_field: "conformance_level"
  source_value: "L3"
  required_sheet: "attribution"       # must exist as directory
  required_per_row_in_sheet: "predictions"  # one attribution file per prediction row
}
```

This is the formalism for "if the manifest declares L3 conformance, every prediction must have a matching attribution file on disk."

#### 4.4.3 `value_range_conditional`

A numeric field in one sheet has different valid bounds depending on a categorical field in another sheet.

```
condition = {
  type: "value_range_conditional"
  source_sheet: "patients"
  source_field: "age_band"           # categorical e.g. "young_adult" | "elderly"
  cases: [
    { source_value: "young_adult", target_sheet: "biomarkers",
      target_field: "lateral_ventricle_volume_total_mm3",
      target_range: { lo: 2000, hi: 30000 } },
    { source_value: "elderly", target_sheet: "biomarkers",
      target_field: "lateral_ventricle_volume_total_mm3",
      target_range: { lo: 2000, hi: 120000 } }
  ]
}
```

This is the formalism for age-conditional normative ranges. Note: v1.11.0 will use this sparingly. Age-conditional bounds are already partially handled by Layer 2's wide plausibility ranges; this condition type exists for cases where the within-sheet bound is too wide to be useful without the cross-sheet context.

#### 4.4.4 `categorical_implies_trajectory_pattern`

A categorical field in `patients.parquet` implies expected (or rejected) trajectory pattern in `predictions.parquet` over the temporal window.

```
condition = {
  type: "categorical_implies_trajectory_pattern"
  source_sheet: "patients"
  source_field: "apoe_genotype"
  source_value: "e4/e4"
  trajectory_sheet: "predictions"
  pattern: {
    kind: "elevated_risk_marker"     # taxonomy below
    population_baseline_rate: 0.50   # expected MCI/AD entry rate over 10y for e4/e4 carriers
    flag_threshold: "none_observed_after_age_75_with_10y_followup"
  }
}
```

This is the formalism for genotype-phenotype consistency. **Critically:** the `flag_threshold` is conservative -- it only flags when the pattern is extreme (e.g., e4/e4 carriers who reach age 85+ with no MCI/AD entry). Single-patient violations are flagged for review, not rejection, because rare biological outliers exist. The pack will declare `flag_severity: "info"` (advisory only) for v1.11.0; whether to raise this to "warning" or "error" is deferred to v1.11.1+ based on observed false-positive rates.

Pattern taxonomy is closed for v1.11.0:
- `elevated_risk_marker` -- categorical value associated with higher trajectory transition rate
- `protective_marker` -- categorical value associated with lower trajectory transition rate
- `population_baseline` -- the categorical value is unselected; no specific expected pattern

Each pattern's `flag_threshold` is closed and citation-locked.

### 4.5 No code execution in YAML

A core safety principle: invariant YAML files contain **declarations only**, never code. There is no eval, no jq expressions, no Python lambdas. The four `ConditionSpec` types above exhaust v1.11.0's expressive capability. If a new check is needed, a new `type` value gets added to the schema in v1.11.x with explicit pydantic validation.

This makes invariant packs **citation-lockable in the same way as bound packs**: a reviewer can trace every check to the source document that justifies it, with no hidden behavior.

---

## 5. Input contract impact

### 5.1 Input contract version

Layer 3 introduces input contract **v1.2.0**, which is a backward-compatible additive extension of v1.1.0.

What v1.2.0 adds:

- A new optional manifest field: `cross_sheet_audit_request: list[str]` -- list of `invariantpack_id`s the submitter explicitly requests. If absent, Layer 3 will run the default production set against the submission.
- A new optional manifest field: `cross_sheet_audit_skip: list[str]` -- list of invariant pack IDs to skip (e.g., a trial that legitimately uses a non-FDA-cleared volumetric tool may skip `tool_declaration_consistency`). Skipping requires an explicit `cross_sheet_audit_skip_reason: str` per skipped pack.

What v1.2.0 does NOT change:

- All v1.0.0 and v1.1.0 submissions remain valid.
- Layer 1 and Layer 2 still work on v1.0.0/v1.1.0 submissions.
- Layer 3 simply does not run on submissions that don't declare cross-sheet content; this is not an error.

### 5.2 Submission structure (unchanged)

```
submission/
+-- manifest.json                # required (v1.1.0); v1.2.0 adds optional cross_sheet_audit_* fields
+-- predictions.parquet          # required
+-- patients.parquet             # required at L2+
+-- biomarkers.parquet           # optional alternative for high-cardinality biomarkers
+-- rule_pack.yaml               # optional reference
+-- attribution/                 # optional, required at L3
    +-- <patient_id>/
        +-- <visit_id>.json
```

Layer 3 reads all four parquet/json files into a `CrossSheetView` (an in-memory join structure) and applies invariants. The `CrossSheetView` is the Layer 3 analog of the `predictions` DataFrame consumed by Layer 1 and 2.

---

## 6. Flag-ID derivation

### 6.1 Deterministic, reproducible, citation-lockable

A Layer 3 `flag_id` is a SHA-256 hash over the canonical-JSON form of:

```
{
  invariantpack_yaml_sha256: str,    # the v1.10.1 cross-platform-stable hash
  invariant_name: str,
  source_sheet_input_sha256: str,     # SHA-256 of the source sheet's relevant bytes
  target_sheet_input_sha256: str,     # SHA-256 of the target sheet's relevant bytes
  join_keys: list[str],
  observed_values: list[ObservedValue],  # canonical-ordered
  contract_version: str               # "1.2.0"
}
```

This means:
- Same input + same invariant pack -> same flag_id, byte-exact, on Linux/Windows/macOS
- A change in the invariant pack content (new bound, citation update) changes flag_id (this is correct; the rule changed)
- A change in the input data changes flag_id (this is correct; the evidence changed)

Layer 3 will use the v1.10.1 `yaml_sha256` (normalized YAML byte hash) for the pack hash, **not** the legacy `canonical_sha256` -- because we already learned in v1.10.1 that pydantic-based hashing is cross-platform brittle.

### 6.2 What gets included in `observed_values`

For each flagged invariant violation, the exact field values that triggered the flag are recorded in canonical order. This is what makes a Layer 3 audit reproducible: a reviewer can see exactly which patient/visit/value triggered which invariant. No reconstruction needed.

### 6.3 What does NOT get included in `flag_id`

- Wall-clock time
- Hostname / username
- Random seeds (Layer 3 has no random components)
- Any non-deterministic value

This guarantees byte-exact reproducibility -- same as Layer 1 / Layer 2.

---

## 7. Integration with Layer 1 and Layer 2

### 7.1 The composite audit pipeline

A v1.11.0 audit run on a submission produces three independent result objects:

1. `Layer1Result` -- temporal coherence (audit_id, cTCS, CI)
2. `Layer2Result` -- per-measurement plausibility (list of flags with flag_id)
3. **`Layer3Result`** -- cross-sheet consistency (list of flags with flag_id) **(NEW)**

Each layer runs independently. A Layer 3 failure does not prevent Layer 1 or Layer 2 from completing.

### 7.2 The `audit_all_layers()` convenience function

```python
def audit_all_layers(
    submission_path: str,
    rulepack: LoadedRulePack,
    rangepacks: list[LoadedRangePack],
    invariantpacks: list[LoadedInvariantPack],
    ...
) -> CompositeAuditResult:
    ...
```

This composes the three layers but does NOT replace them. Calling `audit()` (Layer 1) alone still works. Calling `audit_clinical_ranges()` (Layer 2) alone still works. Layer 3 has its own `audit_cross_sheet()` function. The composite is a convenience, not a coupling.

### 7.3 What this means for Layer 1 byte-exact invariants

**The 5 locked Layer 1 audit_ids (OASIS-3, ADNI, NACC, MIRIAD, MIRIAD test-retest) MUST remain byte-exact under v1.11.0.** Adding Layer 3 does not alter Layer 1's derivation, code path, or output. This is a hard non-negotiable. The implementation session will include the 5-cohort Layer 1 byte-exact verification as the final gate, exactly as v1.10.1 and v1.10.2 did.

### 7.4 Fairness audit integration

The existing fairness audit (sex / age-band / race / scanner / field-strength / disease-stage stratification) currently operates on Layer 1 flags and Layer 2 flags. v1.11.0 extends it to Layer 3 flags: cross-sheet flag rates can be stratified, same as within-sheet flag rates. This requires no new statistical methodology -- just adding Layer 3 flags to the existing stratification function.

---

## 8. Fail-closed semantics

Layer 3 inherits the fail-closed discipline from Layer 1 and Layer 2:

1. **Missing required sheets** -- if an invariant's `sheets_required` are not all present, the invariant cannot run. It does NOT raise an error or skip silently. It emits a `flag` with `flag_severity: "info"` and `flag_reason: "missing_required_sheet"`. The audit continues.

2. **Schema-invalid input sheets** -- if a sheet exists but fails input-contract validation, Layer 3 refuses to run cross-sheet audits on that submission and propagates the input-contract `ValidationReport` errors. No partial audit.

3. **Non-production invariant pack** -- `audit_cross_sheet()` refuses to run a research_preview / skeleton / deprecated invariant pack. This is identical to `audit_clinical_ranges()`'s discipline.

4. **Invariant pack schema invalid** -- pydantic strict-mode failure raises at pack load time. The framework cannot run an invalid pack.

5. **Citation strength below international_consensus** -- v1.11.0 production invariant packs require every invariant at `citation_strength: international_consensus` with >=5 endorsing bodies and a public URL. Bounds at `derived` strength are allowed only in `research_preview` packs.

---

## 9. The exact v1.11.0 invariant packs

This section is the **content lock** for v1.11.0. Implementation MUST produce exactly these packs at production status (no more, no less; additional invariants are deferred to v1.11.1+).

### 9.1 `cross_sheet/tool_declaration_consistency@1.0.0` (production)

**Anchor:** the `upstream_volumetry_tool` field in `mri_volumetrics/structural_volumetry_consensus@1.0.0` (v1.10.2) plus the FDA 510(k) clearance summaries.

**Invariants (5):**

1. **`neuroquant_5.0_implies_normative_range`** -- if `manifest.upstream_volumetry_tool == "neuroquant_5.0"`, then hippocampal/amygdala/lateral-ventricle/eTIV values in `biomarkers.parquet` must be within the NeuroQuant 5.0 normative reference range (Cortechs.ai FDA 510(k) K243016, ages 3-100, 5th-95th centile).

2. **`neuroreader_implies_normative_range`** -- if `manifest.upstream_volumetry_tool == "neuroreader"`, then volumetric values must be within the NeuroReader normative range (Brainreader FDA 510(k), ADNI-derived normative, ages 60-90).

3. **`icometrix_implies_normative_range`** -- similar for icometrix icobrain (FDA 510(k)).

4. **`quantib_nd_implies_normative_range`** -- similar for Quantib ND (RadNet, Rotterdam Study normative).

5. **`tool_value_outside_all_known_tool_ranges_warning`** -- if the declared tool is `"other_validated"` AND values are outside the union of all known FDA-tool ranges, emit a warning. This is a catch-all for tools that aren't yet enumerated.

**Citation strength:** all 5 at `international_consensus`, anchored on FDA 510(k) clearance summaries + the v1.10.2 `structural_volumetry_consensus` pack.

**Endorsing bodies per invariant:** FDA, the specific tool vendor (Cortechs.ai / Brainreader / icometrix / Quantib / etc), Bethlehem 2022 Brain Chart Consortium, ENIGMA Consortium, ADNI, Potvin Normative Working Group, FreeSurfer canonical pipeline.

### 9.2 `cross_sheet/genotype_phenotype_consistency@1.0.0` (production)

**Anchor:** the `genetics/apoe_consensus@1.0.0` pack (v1.10.0) plus Corder 1993 (PMID 8346443), Farrer 1997 APOE meta-analysis (PMID 9343467), and the 2024 NIA-AA biological staging framework.

**Invariants (3):**

1. **`apoe44_lifelong_cn_at_age_85_advisory`** -- if `patients.apoe_genotype == "e4/e4"` AND patient reached age 85+ with no MCI/AD entry recorded in `predictions.parquet` across observed visits, emit `flag_severity: "info"` advisory flag. Conservative: this is a rare-but-not-impossible biological outlier; flag for review, not for rejection.

2. **`apoe22_early_onset_ad_advisory`** -- if `patients.apoe_genotype == "e2/e2"` (most protective) AND patient enters AD state before age 65, emit `flag_severity: "info"` advisory flag. e2/e2 is protective; early AD with this genotype warrants documentation.

3. **`apoe_genotype_missing_when_ad_declared_warning`** -- if `predictions.parquet` shows the patient entered AD state but `patients.parquet` has no APOE genotype recorded, emit `flag_severity: "warning"`. APOE is a standard part of modern AD trial submissions; missing it is a data-completeness issue, not necessarily an error.

**Citation strength:** all 3 at `international_consensus`, anchored on Corder 1993 + Farrer 1997 + NIA-AA 2024 framework + genetics/apoe_consensus@1.0.0.

### 9.3 `cross_sheet/manifest_data_consistency@1.0.0` (production)

**Anchor:** the v1.2.0 input contract specification.

**Invariants (3):**

1. **`L3_conformance_requires_complete_attribution`** -- if `manifest.conformance_level == "L3"`, then every patient_id in `predictions.parquet` must have a corresponding directory in `attribution/`, and every visit_id must have a JSON file. Any missing file is `flag_severity: "error"`.

2. **`continuous_biomarkers_declared_then_units_required`** -- if `manifest.declares_continuous_biomarkers == true` (or if `biomarkers.parquet` exists), then every numeric biomarker row must have a UCUM-conformant `unit` field. Already partially enforced by v1.1.0 input contract validator; Layer 3 reinforces at cross-sheet level.

3. **`rulepack_reference_consistency`** -- if `manifest.rule_pack_id` is declared, it must match a loadable rulepack in the framework. If `rule_pack.yaml` is bundled, its `rulepack_id` must match `manifest.rule_pack_id`. Mismatches are `flag_severity: "error"`.

**Citation strength:** all 3 at `international_consensus`, anchored on v1.2.0 input contract spec + UCUM (Unified Code for Units of Measure, NIH/NLM endorsed).

### 9.4 Total v1.11.0 invariant count

11 invariants across 3 production packs. All at international_consensus standard. Every invariant cites a primary source. Every invariant has >=5 endorsing international bodies.

This is a tight, world-class scope. It is deliberately smaller than the brainstorm in section 1, because each invariant must clear the evidence bar.

### 9.5 What is NOT in v1.11.0 (honest exclusion)

- **Temporal-reversal cross-checked against biomarker direction** -- deferred to v1.11.1 because golden values need a derivation cohort
- **Inclusion/exclusion criteria audits** -- deferred to v1.12.0 (Layer 4); requires protocol-document parsing
- **Cross-cohort meta-audits** -- deferred indefinitely; out of scope for v1.x
- **Vendor-specific lot/serial-number cross-checks** -- requires manufacturer cooperation; deferred
- **Image-level cross-checks** (e.g., DICOM header vs declared scanner) -- deferred; image-level audit is a separate concern
- **PET-MRI cross-modality consistency** -- requires PET pack expansion; deferred to v1.11.2+

---

## 10. Test strategy

### 10.1 Golden values

For each of the 11 invariants, the implementation phase (v1.11.0-rc1) will produce:

- A synthetic test submission that triggers the invariant in a known way -> locked `flag_id` golden value
- A synthetic test submission that satisfies the invariant -> no flag emitted
- A real-cohort sanity check: run Layer 3 against OASIS-3 + ADNI + NACC + MIRIAD as available, record observed flag counts, confirm reasonableness (e.g., e4/e4 lifelong-CN-at-85 flags should be rare)

The Layer 1 5-cohort byte-exact invariants are preserved; Layer 3 golden values are an ADDITIONAL test surface, not a replacement.

### 10.2 Schema discipline tests (parallel to Layer 2)

For each production invariant pack:
- All invariants at `citation_strength: international_consensus`
- All invariants have >=5 endorsing bodies
- All invariants have a public URL
- Anchor citation has the right PMID/DOI/URL
- `yaml_sha256` matches the locked golden value
- Pack refuses to load with malformed YAML (pydantic strict mode)
- Pack refuses to run audit when status is not production

### 10.3 Cross-platform stability

Per v1.10.1's lesson, every invariant pack ships with a locked `yaml_sha256` golden value pinned in `tests/cross_sheet/test_yaml_sha256_cross_platform.py`. The normalized-YAML hashing infrastructure (from v1.10.1's `yaml_hash.py`) is reused as-is.

### 10.4 Test count target

Estimated test additions for v1.11.0-rc1: ~80 tests. Total project test count target: 726 (v1.10.2) + ~80 = ~806 tests passing.

### 10.5 Fail-closed verification tests

- A research_preview invariant pack must refuse audit
- A skeleton invariant pack must refuse audit
- A deprecated invariant pack must refuse audit with successor pointer in error message
- Missing required sheet must emit a `missing_required_sheet` info flag, not raise
- Invalid input contract must propagate ValidationReport errors

---

## 11. Implementation roadmap (NOT in this design session)

This is a multi-session arc. Each session has a tight scope:

- **v1.11.0-rc1** -- Implement the `cross_sheet/` module (schema, loader, audit function, yaml_hash reuse). Build the 3 production invariant packs. Wire into the existing `clinical_ranges` test patterns. Run the new ~80 tests + the full existing suite. Layer 1 byte-exact gate. Ship rc1 zip.
- **v1.11.0-rc2** -- Address any rc1 reviewer feedback. Add fairness-audit integration if not already in rc1. Lock golden values against synthetic + real cohorts. Layer 1 byte-exact gate. Ship rc2 zip.
- **v1.11.0 final** -- Cleanups, documentation polish, CHANGELOG, release manifest, deploy script. Tag and push.

Each rc release ships its own zip + manifest + deploy script, exactly like v1.10.x.

Estimated total: 3 sessions for full Layer 3 implementation. **None of this happens until the design lock in this document is reviewed and accepted.**

---

## 12. Open questions for review

The following are explicit open questions that the designer (Dr. Salokhiddinov) should resolve before implementation begins:

1. **Genotype-phenotype thresholds**: the proposed `apoe44_lifelong_cn_at_age_85_advisory` uses age 85 and 10-year follow-up as the threshold. Is this conservative enough to avoid false-positives in healthy super-aging cohorts (e.g., 90+ Wisconsin Registry for Alzheimer's Prevention sub-cohort)? Recommendation: hold age=85 for v1.11.0; revisit in v1.11.1 with real-cohort data.

2. **Tool-declaration tolerance**: when `manifest.upstream_volumetry_tool == "neuroquant_5.0"`, how strictly should values match NeuroQuant 5.0's range vs. the tool-agnostic Bethlehem 2022 range? Recommendation: tool-specific range with 10% tolerance to accommodate site-to-site variation; values outside both the tool range AND the Bethlehem 2022 range are stronger flags than values outside just the tool range.

3. **Default invariant-pack set**: should `audit_cross_sheet()` run all 3 production packs by default, or require explicit opt-in via `manifest.cross_sheet_audit_request`? Recommendation: run all 3 by default; skipping requires explicit `cross_sheet_audit_skip` declaration with reason.

4. **Layer 3 flag IDs in the audit ledger**: should Layer 3 flag IDs appear alongside Layer 1 audit_ids and Layer 2 flag_ids in the audit ledger, or be a separate ledger? Recommendation: same ledger, distinguished by `audit_layer` field (already structured for this).

These four questions block implementation. They should be answered (yes/no or with explicit alternative) before v1.11.0-rc1 begins.

---

## 13. What this design protects against

This section documents the failure modes this design explicitly defends against, so reviewers can verify the design holds:

| Failure mode | Defense |
|---|---|
| Free-form code execution in YAML | Closed `ConditionSpec` taxonomy; pydantic strict; no eval |
| Cross-platform hash drift | Reuses v1.10.1 `yaml_sha256` normalized-byte hashing |
| Hidden behavior changes between rc1 and final | Design-lock document; implementation traces to design sections |
| Layer 1 byte-exact regression | 5-cohort Layer 1 byte-exact gate at every release |
| Hallucinated bound values | Every invariant cites primary source with PMID/DOI/URL; pydantic validator enforces |
| Insufficient endorsement | Schema requires >=5 endorsing_bodies for international_consensus |
| False positives from rare biology | Genotype-phenotype invariants ship at `flag_severity: "info"` (advisory) |
| Fuzzy / probabilistic checks | Closed condition taxonomy; no probabilistic conditions in v1.11.0 |
| Scope creep into Layer 4 | Explicit exclusion in section 9.5; protocol-document parsing is Layer 4 |
| Coupling that breaks Layer 1 or Layer 2 | Three layers are independent objects; composite is convenience |
| Russian-locale PowerShell deploy script bugs | All future deploy scripts ASCII-only + UTF-8 BOM |

---

## 14. Acceptance criteria for this design lock

This design document is ACCEPTED for implementation when:

- [x] Section 1 (problem statement) is signed off
- [x] Section 2 (scope discipline) explicitly excludes protocol parsing
- [x] Section 4 (schema) declares exactly 4 condition types -- no more
- [x] Section 9 (v1.11.0 content lock) declares exactly 3 production packs / 11 invariants -- no more
- [x] Section 10 (test strategy) requires Layer 1 byte-exact preservation
- [x] Section 12 (open questions) lists explicit blockers for implementation
- [x] No code path in this document
- [x] Every cited paper has PMID/DOI/URL
- [x] All YAML examples in sections 4.4.1 - 4.4.4 are declarative, not executable

When the dr (Salokhiddinov) signs off on the four open questions in section 12, implementation may begin.

---

## 15. Tag

This document is tagged `v1.11.0-design` in the repository. Modifications require bumping to `v1.11.0-design.2`, `.3`, etc., with explicit changelog of what changed. The implementation phase (v1.11.0-rc1) traces to this tag.

---

**End of Layer 3 design document.**

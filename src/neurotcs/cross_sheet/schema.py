"""
neurotcs.cross_sheet.schema -- Layer 3 (cross-sheet consistency) schema.

This is the third audit layer added to NeuroTCS, parallel to and
architecturally identical to the rulepack layer (Layer 1) and the
clinical_ranges layer (Layer 2). Where Layer 1 audits temporal
coherence within a single sheet and Layer 2 audits per-visit numeric
plausibility within a single sheet, Layer 3 audits CONSISTENCY ACROSS
MULTIPLE SHEETS of a single conformant input-contract submission.

Architectural design lock: `docs/design/LAYER_3_DESIGN.md` at
revision `v1.11.0-design.2` (section 4 specifies the schema in full).

This module implements only the SCHEMA and pydantic validation. The
audit execution logic (`audit_cross_sheet()`) is deferred to a
subsequent session in the v1.11.0 rc1 multi-session arc. Packs loaded
through this schema can be inspected and validated but cannot be
executed against a submission yet -- the framework will refuse with
NotImplementedError until session #2 ships.

Schema version 1.0.0. Future schema versions will be additive. Existing
packs at schema 1.0.0 continue to load under future schemas.

Per the v1.11.0-design.2 lock:
  - Citation-locked YAML packs with anchor_citation (PMID or DOI required)
  - Pydantic v2 strict mode (no extra fields, fail-closed on schema violations)
  - SHA-256 hashing of canonical-JSON form (legacy) + normalized YAML bytes
    (the v1.10.1 yaml_sha256 mechanism is reused as-is)
  - status enum (production / research_preview / skeleton / planned / deprecated)
    identical to Layer 2
  - per-invariant citation (citation_pmid or citation_doi) + guideline_section
  - closed taxonomy of exactly 5 ConditionSpec types -- no code execution in YAML
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Reuse Layer 2's Citation and CitationStrength types directly. This is
# deliberate: a Layer 3 invariant's evidence anchoring uses the same
# citation discipline as a Layer 2 bound. Cross-layer references are
# stable because Layer 2 is now production since v1.10.0.
from neurotcs.clinical_ranges.schema import Citation, CitationStrength

# ============================================================
# Schema version
# ============================================================

SCHEMA_VERSION = "1.0.0"
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0.0"})


# ============================================================
# Status enum (parallel to RangePackStatus)
# ============================================================

class InvariantPackStatus(str, Enum):
    """Lifecycle status of a cross-sheet invariant pack.

    Identical taxonomy to RangePackStatus to maintain cross-layer
    discipline. The audit gate refuses to run a non-production pack.
    """

    PRODUCTION = "production"
    """Citation-locked, peer-reviewed, ready for audit. Default for ships.

    Per v1.11.0-design.2 section 9: a production cross-sheet pack must
    meet the world-class evidence bar -- every invariant traces verbatim
    to a publicly accessible source document, AND the invariant has at
    least 5 endorsing international specialty bodies or regulatory
    authorities (parallel to Layer 2's >=5 endorsing_bodies floor)."""

    RESEARCH_PREVIEW = "research_preview"
    """Citation-informed but invariant thresholds derived from broader
    literature rather than verbatim guideline tables. Loadable for
    experimentation, but `audit_cross_sheet()` refuses to run a
    research_preview pack (when implemented in rc1 session #2+)."""

    SKELETON = "skeleton"
    """Structurally valid YAML but invariants are placeholders /
    incomplete. Loadable but the audit gate refuses.

    The v1.11.0a1 first invariant pack is shipped at this status
    because session #1 implements only schema + loader, not the
    audit execution logic. Promotion to production happens in
    session #3 of the rc1 arc when all 5 invariants ship and
    audit_cross_sheet() exists."""

    PLANNED = "planned"
    """Roadmap-only. Reserved for future packs."""

    DEPRECATED = "deprecated"
    """Pack formally retired in favor of a successor (parallel to Layer 2).
    Must declare either deprecated_in_favor_of or deprecation_reason."""


# ============================================================
# SheetSpec - which sheets an invariant requires
# ============================================================

class SheetSpec(BaseModel):
    """Specification of one sheet required by an invariant.

    Per v1.11.0-design.2 section 4.3: the role names correspond exactly
    to the existing v1.1.0 input contract submission structure. Layer 3
    does not invent new sheets.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ...,
        description="Sheet role in the v1.1.0+ input contract submission structure.",
    )
    required: bool = Field(
        default=True,
        description="True if the invariant cannot run without this sheet. "
                    "False if the sheet's absence is itself the trigger condition.",
    )


# ============================================================
# ConditionSpec - the 4 closed condition types
# ============================================================
#
# Per v1.11.0-design.2 section 4.4: v1.11.0 supports EXACTLY 4 condition
# types. Adding a 5th requires a new schema version with explicit
# pydantic validation and a new design tag.
#
# Each condition type is declarative. No code execution. No eval. No
# Python lambdas. This is the safety property that makes invariant
# packs citation-lockable in the same way as bound packs.

class NumericRange(BaseModel):
    """An inclusive numeric range [lo, hi]."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lo: float = Field(..., description="Lower bound (inclusive).")
    hi: float = Field(..., description="Upper bound (inclusive).")

    @model_validator(mode="after")
    def _check_ordering(self) -> NumericRange:
        if self.lo > self.hi:
            raise ValueError(
                f"NumericRange lo ({self.lo}) > hi ({self.hi}); "
                f"lower bound must be <= upper bound."
            )
        return self


# --- Condition type 1: categorical_implies_range -----------------------

class CategoricalImpliesRangeCondition(BaseModel):
    """If a categorical field in sheet A equals `source_value`, then a
    numeric field in sheet B must be within `target_range`.

    Per v1.11.0-design.2 section 4.4.1: the formalism for "if the trial
    declares tool X, the values should be in tool X's normative range."
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["categorical_implies_range"] = "categorical_implies_range"
    source_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ..., description="Sheet containing the trigger categorical field.")
    source_field: str = Field(
        ..., min_length=1, description="Categorical field name in source_sheet.")
    source_value: str = Field(
        ..., min_length=1, description="Value of source_field that triggers the rule.")
    target_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ..., description="Sheet containing the numeric target field.")
    target_field: str = Field(
        ..., min_length=1, description="Numeric field name in target_sheet.")
    target_range: NumericRange = Field(
        ..., description="Inclusive range [lo, hi] target_field must fall within.")
    target_unit: str | None = Field(
        default=None,
        description="UCUM-conformant unit of target_field (optional; documentation only).",
    )


# --- Condition type 2: field_presence_consistency ----------------------

class FieldPresenceConsistencyCondition(BaseModel):
    """If a manifest field declares `source_value`, then a sheet/feature
    must (or must not) be present.

    Per v1.11.0-design.2 section 4.4.2: the formalism for "if the manifest
    declares L3 conformance, attribution/ must exist with one file per
    prediction row."
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["field_presence_consistency"] = "field_presence_consistency"
    source_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ..., description="Sheet containing the trigger field.")
    source_field: str = Field(..., min_length=1)
    source_value: str = Field(..., min_length=1)
    required_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ..., description="Sheet that must be present.")
    required_per_row_in_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] | None = Field(
        default=None,
        description="Optional: each row in this sheet must have a matching "
                    "entry in required_sheet (e.g., attribution file per prediction).",
    )


# --- Condition type 3: value_range_conditional -------------------------

class ConditionalRangeCase(BaseModel):
    """One case within a value_range_conditional condition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_value: str = Field(..., min_length=1)
    target_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"]
    target_field: str = Field(..., min_length=1)
    target_range: NumericRange


class ValueRangeConditionalCondition(BaseModel):
    """A numeric field's valid bounds depend on a categorical field in
    another sheet.

    Per v1.11.0-design.2 section 4.4.3: the formalism for age-conditional
    normative ranges. Used sparingly in v1.11.0; age-conditional bounds
    are partially handled by Layer 2's wide plausibility ranges.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["value_range_conditional"] = "value_range_conditional"
    source_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ..., description="Sheet containing the conditional categorical field.")
    source_field: str = Field(..., min_length=1)
    cases: list[ConditionalRangeCase] = Field(
        ..., min_length=1,
        description="One case per possible source_value. Order matters for documentation only.",
    )


# --- Condition type 4: categorical_implies_trajectory_pattern ----------

class TrajectoryPattern(BaseModel):
    """Pattern specification for trajectory-pattern conditions.

    Pattern taxonomy is CLOSED for v1.11.0 (3 kinds, per design section 4.4.4).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["elevated_risk_marker", "protective_marker", "population_baseline"] = Field(
        ..., description="Pattern kind (closed taxonomy).")
    population_baseline_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="Expected population-level rate (0-1) of the transition over the observation window.",
    )
    flag_threshold: str = Field(
        ..., min_length=10,
        description="Citation-locked flag-trigger description "
                    "(e.g., 'none_observed_after_age_75_with_10y_followup').",
    )


class CategoricalImpliesTrajectoryPatternCondition(BaseModel):
    """A categorical field in `patients.parquet` implies an expected
    trajectory pattern in `predictions.parquet`.

    Per v1.11.0-design.2 section 4.4.4: the formalism for genotype-phenotype
    consistency. Conservative by design: v1.11.0 packs ship these at
    `flag_severity: "info"` (advisory only); promotion to "warning" or
    "error" is deferred until observed false-positive rates are known.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["categorical_implies_trajectory_pattern"] = "categorical_implies_trajectory_pattern"
    source_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ..., description="Sheet containing the categorical field (typically 'patients').")
    source_field: str = Field(..., min_length=1)
    source_value: str = Field(..., min_length=1)
    trajectory_sheet: Literal["predictions"] = Field(
        default="predictions",
        description="Sheet containing the longitudinal trajectory (always predictions in v1.11.0).",
    )
    pattern: TrajectoryPattern


# --- Condition type 5: categorical_not_in_known_set --------------------

class CategoricalNotInKnownSetCondition(BaseModel):
    """If a categorical field in source_sheet is set but its value is
    NOT in the known_values set, emit a flag.

    Per v1.11.0a8 extension to design section 4.4: this condition type
    encodes "coverage gap" semantics -- the invariant author declares
    the taxonomy of values they can validate, and the audit flags
    submissions that declare values outside that taxonomy. The audit
    is not asserting the value is wrong; it is asserting the audit
    cannot validate it. Flag severity should typically be "info".

    Canonical use case: the manifest declares an upstream_volumetry_tool
    that is not one of the known tools whose normative ranges are
    encoded elsewhere in the same pack. The audit flags the submission
    so reviewers know that downstream value-range checks for that tool
    are unreachable.

    Trigger semantics:
    - If source_sheet does not contain source_field, no flag (silent).
    - If source_sheet.source_field is null or empty string, no flag.
    - If source_sheet.source_field is in known_values, no flag.
    - Otherwise: emit one flag describing the unknown value.

    The known_values list is part of the invariant's declared yaml
    content and is therefore covered by the pack's yaml_sha256. Adding
    a value to known_values requires bumping the pack version.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["categorical_not_in_known_set"] = "categorical_not_in_known_set"
    source_sheet: Literal["manifest", "predictions", "patients", "biomarkers", "attribution"] = Field(
        ..., description="Sheet containing the categorical field to check.")
    source_field: str = Field(
        ..., min_length=1, description="Categorical field name in source_sheet.")
    known_values: list[str] = Field(
        ..., min_length=1,
        description="Closed taxonomy of values this pack can validate. "
                    "If source_field value is set but not in this list, the "
                    "invariant fires. Ordering is documentation-only; "
                    "values must be unique.",
    )

    @model_validator(mode="after")
    def _check_known_values_unique(self) -> CategoricalNotInKnownSetCondition:
        if len(set(self.known_values)) != len(self.known_values):
            seen: set[str] = set()
            dupes: list[str] = []
            for v in self.known_values:
                if v in seen and v not in dupes:
                    dupes.append(v)
                seen.add(v)
            raise ValueError(
                f"CategoricalNotInKnownSetCondition.known_values must be "
                f"unique; duplicates: {dupes}"
            )
        for v in self.known_values:
            if not v or not v.strip():
                raise ValueError(
                    "CategoricalNotInKnownSetCondition.known_values entries "
                    "must be non-empty strings."
                )
        return self


# Discriminated union for the 5 condition types
ConditionSpec = (
    CategoricalImpliesRangeCondition
    | FieldPresenceConsistencyCondition
    | ValueRangeConditionalCondition
    | CategoricalImpliesTrajectoryPatternCondition
    | CategoricalNotInKnownSetCondition
)


# ============================================================
# CrossSheetInvariant
# ============================================================

class CrossSheetInvariant(BaseModel):
    """One cross-sheet invariant rule.

    Per v1.11.0-design.2 section 4.2: an invariant declares which sheets
    it joins, what condition it checks, what flag severity to emit on
    violation, and the citation that anchors the rule.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        ..., min_length=3,
        description="Stable identifier within the pack (snake_case).",
    )
    description: str = Field(..., min_length=10)
    sheets_required: list[SheetSpec] = Field(
        ..., min_length=1,
        description="Which sheets must be present; type-tagged.",
    )
    join_keys: list[str] = Field(
        default_factory=list,
        description="How to align rows across sheets (e.g. ['patient_id']).",
    )
    condition: ConditionSpec = Field(
        ...,
        discriminator="type",
        description="The actual check (one of 4 closed types per design section 4.4).",
    )
    flag_severity: Literal["error", "warning", "info"] = Field(
        ...,
        description="Severity emitted on violation. Genotype-phenotype invariants "
                    "MUST be 'info' (advisory) in v1.11.0 per design section 4.4.4 / "
                    "section 12 Q1 resolution.",
    )
    citation: Citation = Field(
        ..., description="Primary citation anchoring this invariant.")
    citation_strength: CitationStrength = Field(
        ..., description="How directly the citation supports the rule.")
    guideline_section: str = Field(
        ..., min_length=3,
        description="Pointer to source-document section (e.g., 'Cortechs FDA 510(k) K243016').",
    )


# ============================================================
# InvariantPack - top-level pack
# ============================================================

class InvariantPack(BaseModel):
    """A citation-locked cross-sheet invariant pack.

    One InvariantPack covers a coherent cross-sheet consistency domain
    (e.g., tool-declaration consistency, genotype-phenotype consistency,
    manifest-data consistency). Each pack ships with an anchor citation
    that establishes the authority for the whole document, plus
    per-invariant citations.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(
        ...,
        description=f"Schema version. Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}.",
    )
    invariantpack_id: str = Field(
        ..., min_length=3,
        description="Stable identifier 'cross_sheet/<domain>/<name>@<version>' "
                    "(e.g., 'cross_sheet/tool_declaration_consistency@1.0.0').",
    )
    pack_version: str = Field(
        ...,
        description="SemVer of this pack's contents (independent of schema_version).",
    )
    effective_date: date = Field(
        ..., description="Date the pack contents were locked.",
    )
    status: InvariantPackStatus = Field(..., description="Lifecycle status.")
    domain: str = Field(..., min_length=1)
    framework_name: str = Field(..., min_length=5)
    transcribed_by: str = Field(..., min_length=5)
    clinical_source_authority: str = Field(..., min_length=10)
    anchor_citation: Citation = Field(...)
    invariants: list[CrossSheetInvariant] = Field(
        ..., min_length=1,
        description="The cross-sheet invariants this pack defines.",
    )
    notes: str | None = Field(default=None)
    deprecated_in_favor_of: str | None = Field(
        default=None,
        description="When status=DEPRECATED, successor pack ID. "
                    "Either this or deprecation_reason required when deprecated.",
    )
    deprecation_reason: str | None = Field(
        default=None,
        description="When status=DEPRECATED and no successor exists, human-readable "
                    "reason. Either this or deprecated_in_favor_of required when deprecated.",
        min_length=10,
    )

    @model_validator(mode="after")
    def _schema_supported_and_status_gate(self) -> InvariantPack:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version={self.schema_version!r}; "
                f"supported set is {sorted(SUPPORTED_SCHEMA_VERSIONS)}."
            )
        # Unique invariant names within a pack
        names = [inv.name for inv in self.invariants]
        if len(names) != len(set(names)):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(
                f"Duplicate invariant name(s) in pack {self.invariantpack_id}: {dupes}"
            )
        # Deprecation discipline: identical to RangePack's
        if self.status == InvariantPackStatus.DEPRECATED:
            if not (self.deprecated_in_favor_of or self.deprecation_reason):
                raise ValueError(
                    f"Pack {self.invariantpack_id} has status=deprecated but neither "
                    f"deprecated_in_favor_of nor deprecation_reason is set. "
                    f"Every deprecated pack must declare either a successor pack ID "
                    f"or a human-readable reason for deprecation."
                )
        return self

    # ------------------------------------------------------------
    # Canonical hashing (parallel to RangePack)
    # ------------------------------------------------------------

    def canonical_sha256(self) -> str:
        """Legacy SHA-256 over canonical-JSON of this pack.

        Kept for parallel structure with Layer 2; the v1.10.1 yaml_sha256
        (computed in loader.py against the normalized YAML bytes) is the
        cross-platform-stable hash that Layer 3 audit_id derivation will
        use when audit_cross_sheet() ships.
        """
        payload = self.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------
    # Usability gate (parallel to RangePack)
    # ------------------------------------------------------------

    def assert_usable_for_audit(self) -> None:
        """Raise if this pack should not be used in production audit.

        Identical fail-closed discipline to RangePack.assert_usable_for_audit().
        """
        if self.status == InvariantPackStatus.DEPRECATED:
            if self.deprecated_in_favor_of:
                raise ValueError(
                    f"InvariantPack {self.invariantpack_id} is DEPRECATED. "
                    f"Use {self.deprecated_in_favor_of!r} instead. "
                    f"Deprecated packs cannot be used in audit_cross_sheet()."
                )
            else:
                raise ValueError(
                    f"InvariantPack {self.invariantpack_id} is DEPRECATED. "
                    f"Reason: {self.deprecation_reason}. "
                    f"This pack has no successor and cannot be used in audit_cross_sheet()."
                )
        if self.status != InvariantPackStatus.PRODUCTION:
            raise ValueError(
                f"InvariantPack {self.invariantpack_id} has status="
                f"{self.status.value!r}; only 'production' packs may be used "
                f"in audit_cross_sheet()."
            )

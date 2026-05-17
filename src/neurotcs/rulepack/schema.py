"""
NeuroTCS Rule Pack Schema v1.1.0.

Citation-locked, version-stamped, fail-closed Pydantic specification for
clinical rule packs.

v1.1.0 changes vs v1.0.0:
  - Renamed `clinician_author` -> `transcribed_by` to reflect that the named
    person attests that the YAML faithfully encodes the cited published
    guideline; they are NOT inventing the clinical rules.
  - Added required `clinical_source_authority` field: names the peer-reviewed
    publication and endorsing professional society that authoritatively
    define the rules being transcribed.
  - Added required `guideline_section` per Transition: exact section / table /
    figure pointer in the cited publication. Reviewers can verify the
    transcription by opening the publication to that section.
  - Schema enforces that production rule packs reference a real publication
    via the anchor_citation (must have at least one of citation_pmid /
    citation_doi).

Authority model: clinical authority lives in the cited published guideline
(e.g. Jack 2018, Eisenhauer 2009, Montalban 2025). The `transcribed_by`
field names the board-certified physician who certifies that this YAML
faithfully encodes those rules. The `reviewers` field is for additive
specialist sign-off (non-blocking).

Reference: NeuroTCS / temporalmetric v1.6 FINAL spec, §B.6 + §C.2 + §C.6.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ============================================================
# Schema version
# ============================================================

SCHEMA_VERSION = "1.1.0"


# ============================================================
# Enums
# ============================================================

class RulePackStatus(str, Enum):
    """Production = ready for audit. Skeleton = schema-valid but blocks audit."""
    PRODUCTION = "production"
    SKELETON = "skeleton"


class DiseaseDomain(str, Enum):
    """Disease domain. Matches input contract v1.1 domains."""
    ALZHEIMERS = "alzheimers"
    PARKINSONS = "parkinsons"
    MULTIPLE_SCLEROSIS = "multiple_sclerosis"
    GLIOBLASTOMA = "glioblastoma"
    STROKE = "stroke"
    CARDIOLOGY = "cardiology"
    ONCOLOGY = "oncology"
    PULMONOLOGY = "pulmonology"
    CUSTOM = "custom"


# ============================================================
# State
# ============================================================

class State(BaseModel):
    """One discrete clinical state in the rule pack's state space.

    States are ordered: position in the state_space list is meaningful for
    ordinal scales (H&Y, EDSS, mRS, AA 2024 stages, RECIST CR<PR<SD<PD).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., min_length=1, max_length=64,
                      description="Stable identifier (e.g. 'CN', 'MCI', 'AD')")
    description: str = Field(..., min_length=1, max_length=1024,
                             description="Human-readable description")
    ordinal_rank: int | None = Field(
        None,
        description="0-indexed position on an ordinal scale; null for purely "
                    "categorical states. When set, used to compute monotonicity."
    )


# ============================================================
# Citation
# ============================================================

class Citation(BaseModel):
    """Citation evidence for a clinical rule.

    At least one of citation_pmid or citation_doi MUST be non-empty.
    Free-text citation_text alone is NOT sufficient.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    citation_pmid: str | None = Field(None, max_length=32,
                                          description="PubMed ID (numeric string)")
    citation_doi: str | None = Field(None, max_length=128,
                                         description="DOI (e.g. '10.1002/alz.13859')")
    citation_text: str = Field(..., min_length=1, max_length=1024,
                                description="Human-readable reference text")

    @model_validator(mode="after")
    def at_least_one_id(self) -> Citation:
        if not self.citation_pmid and not self.citation_doi:
            raise ValueError(
                "Every citation MUST have at least one of citation_pmid or "
                "citation_doi. Free-text citation_text alone is not sufficient."
            )
        return self


# ============================================================
# Transition (v1.1: adds guideline_section)
# ============================================================

class Transition(BaseModel):
    """A single admissible transition between two states.

    Each transition encodes a rule transcribed directly from a published
    clinical guideline. The `guideline_section` field gives the exact
    pointer (section / table / figure) in the cited paper so any reviewer
    can verify the transcription.

    Inadmissible transitions are NOT listed (absent = inadmissible by default).
    For documentation purposes, explicit `Inadmissible` entries can be added
    via the `inadmissible_transitions` field on the RulePack.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_state: str = Field(..., min_length=1, max_length=64)
    to_state: str = Field(..., min_length=1, max_length=64)
    min_delta_t_days: float | None = Field(
        None, ge=0.0,
        description="Minimum interval for this transition to be admissible. "
                    "Null means no minimum."
    )
    max_delta_t_days: float | None = Field(
        None, ge=0.0,
        description="Maximum interval. Null means no maximum."
    )
    citation: Citation = Field(...,
                                description="Citation backing this transition rule")
    guideline_section: str = Field(
        ..., min_length=1, max_length=512,
        description="Exact section/table/figure pointer in the cited "
                    "publication (e.g. 'Eisenhauer 2009 §3.3.4, Table 1'). "
                    "Reviewers verify the transcription by opening this section."
    )
    override_allowed: bool = Field(
        False,
        description="Whether this rule can be overridden via CLI with explicit "
                    "citation. Defaults to false (strict)."
    )
    notes: str | None = Field(None, max_length=2048)

    @model_validator(mode="after")
    def check_delta_t_ordering(self) -> Transition:
        if (self.min_delta_t_days is not None
                and self.max_delta_t_days is not None
                and self.min_delta_t_days > self.max_delta_t_days):
            raise ValueError(
                f"min_delta_t_days ({self.min_delta_t_days}) > "
                f"max_delta_t_days ({self.max_delta_t_days}) for "
                f"{self.from_state} -> {self.to_state}"
            )
        return self


class InadmissibleTransition(BaseModel):
    """Documented inadmissible transition (for reviewer clarity)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_state: str = Field(..., min_length=1, max_length=64)
    to_state: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=1, max_length=1024)
    citation: Citation
    guideline_section: str | None = Field(
        None, max_length=512,
        description="Optional section pointer documenting where the "
                    "publication states this transition is not expected."
    )


# ============================================================
# Priors (optional, for pTCS)
# ============================================================

class TransitionPrior(BaseModel):
    """Annual transition probability between two states (for pTCS scoring)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_state: str = Field(..., min_length=1, max_length=64)
    to_state: str = Field(..., min_length=1, max_length=64)
    annual_probability: float = Field(..., ge=0.0, le=1.0)
    confidence_interval_95: tuple[float, float] | None = Field(
        None, description="95% CI as (low, high). Optional."
    )
    citation: Citation
    prior_type: str = Field(
        "clinical",
        description="'clinical' (clinic-attending) or 'population' (general). "
                    "Sensitivity analyses contrast these."
    )


# ============================================================
# Rule Pack (v1.1: transcribed_by + clinical_source_authority)
# ============================================================

class RulePack(BaseModel):
    """A versioned, citation-locked clinical rule pack.

    v1.1 authority model:
      - `clinical_source_authority` names the published guideline + endorsing
        professional society. This is where clinical authority lives.
      - `transcribed_by` names the board-certified physician who attests that
        this YAML faithfully encodes the cited guideline.
      - `reviewers` is for additive specialist sign-off (non-blocking).

    Loading fails closed if:
      - Any required field is missing
      - Any unknown field is present (strict mode)
      - Any admissible transition lacks a citation or guideline_section
      - Any state referenced in a transition is not in state_space
      - State ordinal_ranks are inconsistent
      - Production status with empty admissible_transitions
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Schema version (helps with future migrations)
    schema_version: str = Field(
        SCHEMA_VERSION, min_length=1, max_length=16,
        description=f"Schema version (current: {SCHEMA_VERSION})"
    )

    # Identification
    rulepack_id: str = Field(
        ..., min_length=1, max_length=128,
        pattern=r"^[a-z0-9_+-]+/[a-z0-9_+-]+@\d+\.\d+(\.\d+)?$",
        description="'domain/framework@major.minor[.patch]' "
                    "(e.g. 'ad/niaaa_2018@1.0.0')"
    )
    ruleset_version: str = Field(
        ..., min_length=1, max_length=32,
        pattern=r"^\d+\.\d+(\.\d+)?(-[a-z0-9.-]+)?$",
    )
    effective_date: date = Field(...)
    status: RulePackStatus = Field(...)
    disease_domain: DiseaseDomain = Field(...)
    framework_name: str = Field(..., min_length=1, max_length=256)

    # v1.1 authorship model
    transcribed_by: str = Field(
        ..., min_length=1, max_length=512,
        description="Board-certified physician who attests this YAML "
                    "faithfully encodes the cited published guideline. "
                    "Format: 'Name, Credentials, Institution'."
    )
    clinical_source_authority: str = Field(
        ..., min_length=1, max_length=1024,
        description="The published guideline + endorsing professional society "
                    "where clinical authority resides. Example: "
                    "'RECIST 1.1 (Eisenhauer 2009, EJC 45:228-247) - RECIST "
                    "Working Group at EORTC; endorsed by ESMO Clinical Practice "
                    "Guidelines for solid tumor response assessment.'"
    )
    reviewers: list[str] = Field(
        default_factory=list,
        description="Additional specialist reviewers (additive, non-blocking)"
    )

    # Anchor citation for the framework as a whole
    anchor_citation: Citation = Field(...)

    # State space
    state_space: list[State] = Field(..., min_length=2, max_length=64)

    # Transitions
    admissible_transitions: list[Transition] = Field(default_factory=list)
    inadmissible_transitions: list[InadmissibleTransition] = Field(default_factory=list)

    # Priors (optional)
    transition_priors: list[TransitionPrior] = Field(default_factory=list)

    # Notes
    notes: str | None = Field(None, max_length=8192)
    override_allowed_default: bool = Field(False)

    # ============================================================
    # Cross-validators
    # ============================================================

    @model_validator(mode="after")
    def check_state_consistency(self) -> RulePack:
        state_names = {s.name for s in self.state_space}
        if len(state_names) != len(self.state_space):
            raise ValueError("Duplicate state names in state_space")

        for t in self.admissible_transitions:
            if t.from_state not in state_names:
                raise ValueError(
                    f"Transition from_state '{t.from_state}' not in state_space"
                )
            if t.to_state not in state_names:
                raise ValueError(
                    f"Transition to_state '{t.to_state}' not in state_space"
                )
        for t in self.inadmissible_transitions:
            if t.from_state not in state_names:
                raise ValueError(
                    f"Inadmissible from_state '{t.from_state}' not in state_space"
                )
            if t.to_state not in state_names:
                raise ValueError(
                    f"Inadmissible to_state '{t.to_state}' not in state_space"
                )
        for p in self.transition_priors:
            if p.from_state not in state_names:
                raise ValueError(
                    f"Prior from_state '{p.from_state}' not in state_space"
                )
            if p.to_state not in state_names:
                raise ValueError(
                    f"Prior to_state '{p.to_state}' not in state_space"
                )
        return self

    @model_validator(mode="after")
    def check_ordinal_consistency(self) -> RulePack:
        ranks = [s.ordinal_rank for s in self.state_space]
        defined = [r for r in ranks if r is not None]
        if defined:
            if len(defined) != len(self.state_space):
                raise ValueError(
                    "If any state has ordinal_rank set, all states must"
                )
            if sorted(defined) != defined:
                raise ValueError(
                    "States must be listed in ascending ordinal_rank order"
                )
            if len(set(defined)) != len(defined):
                raise ValueError("Duplicate ordinal_rank values")
        return self

    @model_validator(mode="after")
    def check_no_duplicate_transitions(self) -> RulePack:
        seen = set()
        for t in self.admissible_transitions:
            key = (t.from_state, t.to_state)
            if key in seen:
                raise ValueError(
                    f"Duplicate transition: {t.from_state} -> {t.to_state}"
                )
            seen.add(key)
        return self

    @model_validator(mode="after")
    def check_skeleton_consistency(self) -> RulePack:
        if (self.status == RulePackStatus.PRODUCTION
                and len(self.admissible_transitions) == 0):
            raise ValueError(
                f"RulePack '{self.rulepack_id}' is PRODUCTION but has no "
                f"admissible_transitions. Either populate transitions or "
                f"mark as SKELETON."
            )
        return self

    # ============================================================
    # API
    # ============================================================

    def is_admissible(self, from_state: str, to_state: str,
                      delta_t_days: float) -> tuple[bool, Transition | None]:
        """Check if a transition is admissible under this rule pack.

        Returns (admissible, matching_transition_or_None).
        Self-loops are admissible by convention (state unchanged).
        """
        if from_state == to_state:
            return True, None
        for t in self.admissible_transitions:
            if t.from_state == from_state and t.to_state == to_state:
                if (t.min_delta_t_days is not None
                        and delta_t_days < t.min_delta_t_days):
                    return False, t
                if (t.max_delta_t_days is not None
                        and delta_t_days > t.max_delta_t_days):
                    return False, t
                return True, t
        return False, None

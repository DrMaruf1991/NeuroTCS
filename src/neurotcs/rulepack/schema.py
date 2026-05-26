"""
NeuroTCS Rule Pack Schema v1.4.0.

Citation-locked, version-stamped, fail-closed Pydantic specification for
clinical rule packs.

Schema-version declaration policy (MANDATORY for every rule pack)
-----------------------------------------------------------------
Each rule pack MUST declare the MINIMUM schema version whose features it
actually uses, not the latest schema version available. This produces
honest, audit-friendly version tracking:

  - A pack that uses ONLY 1.1.0-era fields (states, transitions, citations,
    transcribed_by, clinical_source_authority, guideline_section) declares
    `schema_version: "1.1.0"`.
  - A pack that uses `required_conditions` or `conditions_evaluated_at`
    (context-conditional admissibility) declares `schema_version: "1.2.0"`.
  - A pack that uses `attribution_type == "clinical_inference"` (or sets
    `inference_rationale` on any transition) declares `schema_version: "1.3.0"`.
  - A pack that uses the pack-level `endorsing_bodies` field (added in 1.4.0)
    declares `schema_version: "1.4.0"`.

Rationale: an external reviewer or AI-vendor auditor inspecting the YAML
can immediately tell which schema features are in play. A pack that
"over-declares" (e.g. claims 1.4.0 but uses no 1.4.0 features) wastes
reviewer attention. A pack that "under-declares" (e.g. claims 1.3.0 but
uses endorsing_bodies) will fail validation at load time.

`tests/rulepack/test_schema_version_declaration.py` enforces this policy
automatically across every shipped rule pack — under-declaring will be
caught at CI time before it reaches a reviewer.

Supported schema versions for loading: {1.1.0, 1.2.0, 1.3.0, 1.4.0}. The
loader accepts any of these and applies feature gating per-field.

v1.4.0 changes vs v1.3.0 (shipped in v1.12.0):
  - Added optional pack-level `endorsing_bodies: list[str]` field to
    RulePack, parallel to the Layer 2 rangepack and Layer 3 invariant pack
    `endorsing_bodies` lists. Names the international specialty bodies,
    regulatory authorities, official consortia, or named research-cohort
    institutions that have published, ratified, or implementing-by-protocol
    endorsed the framework this rulepack transcribes.
  - Added two-stage `status: production` validator (motivated by the
    v1.11.0 gap-check Finding A):
        * HARD ERROR: production rulepacks must HAVE the field (non-empty
          list). Loading fails fast if a production rulepack lacks it.
        * WARNING: production rulepacks SHOULD have >=5 unique endorsing
          bodies. Loading succeeds with <5 entries but emits a runtime
          warning naming the pack and the actual count.
  - The two-stage design matches existing Layer 2 / Layer 3 discipline:
    Layer 2 rangepack `citation_strength: international_consensus` requires
    >=5 endorsing_bodies (hard error); other citation strengths allow
    fewer. This brings Layer 1 to the same standard, scoped to production
    status so research_preview and skeleton rulepacks are unaffected.
  - Motivation: NeuroTCS gap-check 2026-05-26 (Finding A) verified that
    the 3 production AD trajectory rulepacks (ad/aa_2024@2.0.0,
    ad/aa_2024_trac@1.0.0, ad/niaaa_2018@1.2.0) carry production status
    but lack the structured endorsing_bodies metadata field, while
    Layer 2 rangepacks and Layer 3 invariant packs already require it.
    This schema extension closes that gap.
  - Backward compatible: research_preview and skeleton rulepacks are
    unaffected. Production rulepacks declared at schema_version 1.1.0,
    1.2.0, or 1.3.0 are required to declare the field even if they don't
    use other 1.4.0 features (this is how the gap is closed — the field
    becomes mandatory for any production rulepack).

v1.3.0 changes vs v1.2.0 (shipped in v1.7.1, per ERRATA E-2026-003):
  - Added optional `attribution_type` field to Transition with two values:
    `guideline_quote` (default — citation_text reproduces a verbatim
    statement from the cited section) and `clinical_inference` (the rule
    structure is a board-certified clinical inference applied on top of
    the cited evidence, not directly quoted from it).
  - Added optional `inference_rationale` field to Transition, required
    when `attribution_type == clinical_inference`, explaining the
    clinical reasoning that bridges the cited evidence to the encoded rule.
  - Motivation: ERRATA E-2026-003 surfaced cases where the YAML's
    `citation_text` field paraphrased a clinical inference applied to a
    cited paper, rather than reproducing a verbatim quote from that paper.
    The new field forces explicit disambiguation between the two, so a
    reviewer reading the YAML can immediately tell whether the rule is
    "transcribed from §X table Y" or "transcriber's clinical judgment
    informed by §X".
  - Backward compatible: default `guideline_quote` preserves prior
    behavior. Rule packs that do not set the field load identically.

v1.2.0 changes vs v1.1.0:
  - Added optional `required_conditions` field to Transition for
    context-conditional admissibility. Enables encoding rules like the
    Treatment-Related Amyloid Clearance (TRAC) framework (La Joie et al.,
    Alzheimer's & Dementia 2025;21:e70997, DOI 10.1002/alz.70997, PMID
    via PMCID PMC12657122), where biomarker reversals (A+ -> A-) are
    admissible ONLY when the patient is on anti-amyloid therapy.
  - Added `conditions_evaluated_at` field controlling whether to check
    the from-visit, to-visit, or either visit's context.
  - Backward compatible: rule packs without these fields behave identically.

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
(e.g. Jack 2018, Eisenhauer 2009, Montalban 2025, La Joie 2025). The
`transcribed_by` field names the board-certified physician who certifies
that this YAML faithfully encodes those rules. The `reviewers` field is
for additive specialist sign-off (non-blocking).

Reference: NeuroTCS / temporalmetric v1.7 FINAL spec, §B.6 + §C.2 + §C.6.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ============================================================
# Schema version
# ============================================================

SCHEMA_VERSION = "1.4.0"


# Schema versions that the loader accepts (backward compatible).
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.1.0", "1.2.0", "1.3.0", "1.4.0"})


# ============================================================
# Enums
# ============================================================

class RulePackStatus(str, Enum):
    """Production = ready for audit. Skeleton = schema-valid but blocks audit."""
    PRODUCTION = "production"
    SKELETON = "skeleton"


class DiseaseDomain(str, Enum):
    """Disease domain (v1.9.0+ scope-narrowed to AD).

    NeuroTCS v1.x is scope-narrowed to Alzheimer's disease in preparation for
    FDA Q-Submission (target Q1 2027). The enum is intentionally restricted
    to ALZHEIMERS + CUSTOM; non-AD domains that previously shipped in v1.7.x
    have been extracted to seed future per-disease repositories. See
    docs/SCOPE.md.

    ``CUSTOM`` remains so vendor-specific or unreleased Alzheimer's variants
    (e.g., research-only sub-staging schemas) can be validated. Note: a
    rule pack declaring a non-AD domain such as ``parkinsons`` will fail
    validation under v1.9.0; the future per-disease repos will ship their
    own DiseaseDomain enums or import from a shared ``neurotcs-core``
    package once that is split out.
    """
    ALZHEIMERS = "alzheimers"
    CUSTOM = "custom"


class AttributionType(str, Enum):
    """How the citation_text relates to the encoded rule.

    Added in schema v1.3.0 per ERRATA E-2026-003.

    - GUIDELINE_QUOTE (default): the citation_text reproduces a verbatim
      statement from the cited section of the cited publication. The rule's
      structure (state pair, min/max delta_t) follows directly from the
      cited text without interpretive bridging.

    - CLINICAL_INFERENCE: the rule structure is a board-certified clinical
      inference informed by the cited publication, NOT a verbatim
      transcription. The cited paper supports the clinical reasoning but
      does not state the encoded rule in the form encoded. Requires
      `inference_rationale` to be set, explaining the bridging logic.

    Example clinical_inference uses:
      - RECIST 1.1 CR -> PD with min_delta_t_days=56: Eisenhauer 2009 does
        not state "CR -> PD requires >= 8 weeks" verbatim. The transcriber
        applies the clinical inference that a direct CR -> PD transition
        in a single scan is implausible given measurement noise, and
        encodes a min interval informed by RECIST's 8-week response
        confirmation window (§3.3.4).
      - PD Hoehn-Yahr two-step jumps with min_delta_t_days=365: anchored
        to the Marras 2002 systematic review's finding that natural-history
        progression averages roughly 1 stage per 2-3 years (the review does
        NOT publish a "Table 2 of stage-transition intervals"; the 365-day
        floor is the transcriber's conservative clinical inference).
    """
    GUIDELINE_QUOTE = "guideline_quote"
    CLINICAL_INFERENCE = "clinical_inference"


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
    required_conditions: dict[str, list[str]] | None = Field(
        None,
        description="Optional context-conditional admissibility constraints "
                    "(schema v1.2+). Maps context field name (e.g. "
                    "'treatment_status') to allowed values (e.g. "
                    "['anti_amyloid_active', 'anti_amyloid_discontinued']). "
                    "If specified, this transition is admissible ONLY when "
                    "the trajectory's per-visit context field matches at "
                    "least one allowed value at the visit selected by "
                    "`conditions_evaluated_at`. Example use: the TRAC "
                    "framework (La Joie 2025, doi:10.1002/alz.70997) "
                    "where A+ -> A- amyloid clearance is admissible only "
                    "under anti-amyloid therapy."
    )
    conditions_evaluated_at: Literal["from_visit", "to_visit", "either"] = (
        Field(
            "either",
            description="When `required_conditions` is set, this controls "
                        "which visit's context is checked. 'from_visit' = "
                        "the earlier visit only; 'to_visit' = the later "
                        "visit only (typical for TRAC, since the follow-up "
                        "scan is what proves clearance); 'either' = passes "
                        "if either endpoint matches. Default 'either' is "
                        "the most permissive."
        )
    )
    attribution_type: AttributionType = Field(
        AttributionType.GUIDELINE_QUOTE,
        description="How the citation_text relates to the encoded rule. "
                    "Default 'guideline_quote' (verbatim from cited section). "
                    "'clinical_inference' marks a transcriber's clinical "
                    "judgment informed by the citation rather than reproduced "
                    "from it; requires `inference_rationale` to be set. "
                    "Added schema v1.3.0 per ERRATA E-2026-003."
    )
    inference_rationale: str | None = Field(
        None, max_length=2048,
        description="When `attribution_type == clinical_inference`, this "
                    "field MUST be set and should explain the clinical "
                    "reasoning that bridges the cited evidence to the "
                    "encoded rule. Reviewers reading the YAML can audit "
                    "the inference separately from the citation. Added "
                    "schema v1.3.0 per ERRATA E-2026-003."
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

    @model_validator(mode="after")
    def check_inference_rationale_required(self) -> Transition:
        if (self.attribution_type == AttributionType.CLINICAL_INFERENCE
                and (self.inference_rationale is None
                     or not self.inference_rationale.strip())):
            raise ValueError(
                f"Transition {self.from_state} -> {self.to_state} has "
                f"attribution_type='clinical_inference' but no "
                f"inference_rationale. Clinical inferences MUST carry an "
                f"explicit rationale so reviewers can audit the bridging "
                f"reasoning separately from the citation. Added schema "
                f"v1.3.0 per ERRATA E-2026-003."
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
    endorsing_bodies: list[str] = Field(
        default_factory=list,
        description="International specialty bodies, regulatory authorities, "
                    "official consortia, or named research-cohort institutions "
                    "that have published, ratified, or implementing-by-protocol "
                    "endorsed the framework this rulepack transcribes. "
                    "Examples: 'Alzheimer's Association', 'National Institute "
                    "on Aging (NIA)', 'FDA Office of Neuroscience', 'European "
                    "Academy of Neurology (EAN)', 'Mayo Clinic Department of "
                    "Radiology', 'Washington University Knight ADRC', 'UCSF "
                    "Memory and Aging Center', 'Amsterdam UMC', 'Lund "
                    "University BioFINDER', 'Banner Sun Health Research "
                    "Institute'. "
                    "Parallel to Layer 2 (RangePack) and Layer 3 (InvariantPack) "
                    "endorsing_bodies fields. Required (>=1 entry, >=5 unique "
                    "entries warned) for production status; optional for "
                    "research_preview and skeleton statuses. Added in "
                    "schema_version 1.4.0 per gap-check Finding A 2026-05-26."
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
    def check_schema_version_supported(self) -> RulePack:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version '{self.schema_version}' is not supported. "
                f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}. "
                f"Current: {SCHEMA_VERSION}."
            )
        return self

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

    @model_validator(mode="after")
    def check_endorsing_bodies_for_production(self) -> RulePack:
        """Two-stage endorsement check (added in schema_version 1.4.0).

        HARD ERROR: production rulepacks must HAVE endorsing_bodies as a
        non-empty list. Loading fails fast if absent.

        WARNING: production rulepacks SHOULD have >=5 unique endorsing
        bodies (parallel to Layer 2 international_consensus floor and
        Layer 3 invariantpack discipline). Loading succeeds with <5
        entries but emits a runtime warning naming the pack.

        Research_preview and skeleton statuses are unaffected.
        Motivation: gap-check Finding A 2026-05-26.
        """
        import warnings as _warnings

        if self.status != RulePackStatus.PRODUCTION:
            return self

        # Hard error: production must have the field non-empty
        if not self.endorsing_bodies:
            raise ValueError(
                f"RulePack '{self.rulepack_id}' is PRODUCTION but has no "
                f"endorsing_bodies. Production rulepacks must declare the "
                f"international specialty bodies, regulatory authorities, "
                f"or official consortia that have endorsed the framework "
                f"this rulepack transcribes. Field added in schema_version "
                f"1.4.0 per gap-check Finding A 2026-05-26. To remediate: "
                f"add a non-empty `endorsing_bodies` list to the YAML."
            )

        # Reject empty or whitespace-only entries
        cleaned = [e.strip() for e in self.endorsing_bodies if isinstance(e, str)]
        non_empty = [e for e in cleaned if e]
        if len(non_empty) != len(self.endorsing_bodies):
            raise ValueError(
                f"RulePack '{self.rulepack_id}' endorsing_bodies contains "
                f"empty or whitespace-only entries. All entries must be "
                f"non-empty strings."
            )

        # Warning: production should have >=5 unique entries
        unique = set(non_empty)
        if len(unique) < 5:
            _warnings.warn(
                f"RulePack '{self.rulepack_id}' is PRODUCTION with only "
                f"{len(unique)} unique endorsing_bodies (>=5 recommended "
                f"for production-status international consensus). "
                f"Parallel to Layer 2 international_consensus floor.",
                UserWarning,
                stacklevel=2,
            )

        return self

    # ============================================================
    # API
    # ============================================================

    def is_admissible(
        self,
        from_state: str,
        to_state: str,
        delta_t_days: float,
        from_context: dict[str, str] | None = None,
        to_context: dict[str, str] | None = None,
    ) -> tuple[bool, Transition | None]:
        """Check if a transition is admissible under this rule pack.

        Args:
            from_state, to_state: The categorical states at the two visits.
            delta_t_days: Days between the visits.
            from_context: Optional per-visit context at the FROM visit
                (e.g. {"treatment_status": "anti_amyloid_active"}). Required
                when matching a transition that carries `required_conditions`
                and `conditions_evaluated_at` in {"from_visit", "either"}.
            to_context: Optional per-visit context at the TO visit. Required
                when matching a transition that carries `required_conditions`
                and `conditions_evaluated_at` in {"to_visit", "either"}.

        Returns (admissible, matching_transition_or_None).
        Self-loops are admissible by convention (state unchanged).
        """
        if from_state == to_state:
            return True, None
        for t in self.admissible_transitions:
            if t.from_state == from_state and t.to_state == to_state:
                # Time-window check
                if (t.min_delta_t_days is not None
                        and delta_t_days < t.min_delta_t_days):
                    return False, t
                if (t.max_delta_t_days is not None
                        and delta_t_days > t.max_delta_t_days):
                    return False, t
                # Conditional admissibility (schema v1.2+)
                if t.required_conditions:
                    if not _check_required_conditions(
                        t.required_conditions,
                        t.conditions_evaluated_at,
                        from_context,
                        to_context,
                    ):
                        return False, t
                return True, t
        return False, None


def _check_required_conditions(
    required: dict[str, list[str]],
    evaluated_at: str,
    from_context: dict[str, str] | None,
    to_context: dict[str, str] | None,
) -> bool:
    """Evaluate per-visit context fields against required conditions.

    For each (key, allowed_values) pair in `required`, the chosen context
    visit must carry a value for `key` that is in `allowed_values`. ALL
    keys must match (AND). For "either", a single visit satisfying all
    keys is sufficient.
    """
    def context_satisfies(ctx: dict[str, str] | None) -> bool:
        if ctx is None:
            return False
        for key, allowed_values in required.items():
            actual = ctx.get(key)
            if actual is None or actual not in allowed_values:
                return False
        return True

    if evaluated_at == "from_visit":
        return context_satisfies(from_context)
    if evaluated_at == "to_visit":
        return context_satisfies(to_context)
    # "either"
    return context_satisfies(from_context) or context_satisfies(to_context)

"""
neurotcs.clinical_ranges.schema — Layer 2 (clinical range validation) schema.

This is the second audit layer added to NeuroTCS, parallel to and architecturally
identical to the rulepack layer. Where the rulepack layer (Layer 1) checks
temporal coherence of categorical disease-stage trajectories, the clinical_ranges
layer (Layer 2) checks that per-visit clinical measurements (vitals, labs,
imaging volumetrics, PET, genetics) fall within published normative or
biologically-plausible ranges.

The architectural primitives are deliberately identical to rulepack:
  - Citation-locked YAML packs with anchor_citation (PMID or DOI required)
  - Pydantic v2 strict mode (no extra fields, fail-closed on schema violations)
  - SHA-256 canonical-JSON hash of the pack (rangepack_sha) for audit_id derivation
  - status enum (production / skeleton / planned) so a partially-built pack
    cannot be used in a production audit by accident
  - per-bound citation (citation_pmid or citation_doi) + guideline_section pointer

Schema version 1.0.0. Future schema versions will be additive (extra optional
fields). Existing packs at schema 1.0.0 continue to load under future schemas.

Per the v1.x AD-only scope (docs/SCOPE.md), the production range packs ship
with v1.10.0 cover the measurement domains that appear in AD anti-amyloid
trials. Non-AD range packs (e.g. PD UPDRS scores, oncology RECIST measurements)
are deferred to the future per-disease repositories.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ============================================================
# Schema version
# ============================================================

SCHEMA_VERSION = "1.0.0"
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0.0"})


class RangePackStatus(str, Enum):
    """Lifecycle status of a range pack."""

    PRODUCTION = "production"
    """Citation-locked, peer-reviewed, ready for audit. Default for ships.

    A production pack must meet the world-class evidence bar: every numeric
    bound traces verbatim to at least one publicly accessible source
    document, and the pack as a whole is endorsed by at least 5 international
    specialty bodies or regulatory authorities (see RangePack.endorsing_bodies)."""

    RESEARCH_PREVIEW = "research_preview"
    """Citation-informed but bounds are derived from broader literature rather
    than verbatim guideline tables. Loadable for experimentation, but
    `audit_clinical_ranges()` refuses to run a research_preview pack."""

    SKELETON = "skeleton"
    """Structurally valid YAML but bounds are placeholders. Loadable but
    `audit_clinical_ranges()` refuses to run with a skeleton pack."""

    PLANNED = "planned"
    """Roadmap-only; not present on disk. Reserved for future packs."""

    DEPRECATED = "deprecated"
    """The pack has been formally retired in favor of a successor pack
    (typically a world-class production pack covering the same domain at
    a higher evidence bar). A deprecated pack MUST declare its successor
    via the `deprecated_in_favor_of` field. Loadable for historical
    reference, but `audit_clinical_ranges()` refuses to run a deprecated
    pack. Introduced in v1.10.1."""


class CitationStrength(str, Enum):
    """How directly a numeric bound traces to its cited source.

    This is the discipline gate that distinguishes world-class
    citation-lock from citation-informed synthesis.
    """

    VERBATIM = "verbatim"
    """The cited source contains the EXACT numeric bound in a table,
    figure caption, or explicit statement. The citation_text field
    quotes the source directly."""

    DERIVED = "derived"
    """The cited source contains data (e.g. cohort distribution) from
    which the bound is derived (e.g. 99.5 percentile). The
    citation_text field explains the derivation."""

    INTERNATIONAL_CONSENSUS = "international_consensus"
    """At least 5 international specialty bodies have published agreeing
    numeric criteria. The Citation.endorsing_bodies list must contain
    those bodies."""


class BoundType(str, Enum):
    """How a bound is interpreted relative to the observed value."""

    HARD_MIN = "hard_min"
    """Below this is physically/biologically impossible. Always flagged."""

    HARD_MAX = "hard_max"
    """Above this is physically/biologically impossible. Always flagged."""

    PLAUSIBLE_MIN = "plausible_min"
    """Below this is biologically implausible in the target population.
    Flagged as 'implausible_low'."""

    PLAUSIBLE_MAX = "plausible_max"
    """Above this is biologically implausible in the target population.
    Flagged as 'implausible_high'."""


# ============================================================
# Citation (identical shape to rulepack.schema.Citation)
# ============================================================

class Citation(BaseModel):
    """Citation for a normative bound or a range pack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    citation_pmid: str | None = Field(
        default=None,
        description="PubMed PMID (string of digits). One of pmid/doi/pmid_pending required.",
    )
    citation_doi: str | None = Field(
        default=None,
        description="DOI (e.g. '10.1016/j.jalz.2018.02.018'). One of pmid/doi/pmid_pending required.",
    )
    pmid_pending: bool = Field(
        default=False,
        description="Set to True if the cited paper is too recent for PubMed indexing. "
                    "If True, citation_doi must be provided.",
    )
    citation_text: str = Field(
        ...,
        min_length=20,
        description="Short verbatim or near-verbatim quote anchoring this bound. "
                    "Must be at least 20 chars (no empty placeholders).",
    )
    public_url: str | None = Field(
        default=None,
        description="Publicly accessible URL where the cited document can be "
                    "read in full. Required for citation_strength=verbatim or "
                    "international_consensus. Should be a stable URL (FDA/PMC/"
                    "publisher/society website), not a search result link.",
    )
    endorsing_bodies: list[str] = Field(
        default_factory=list,
        description="International specialty bodies, regulatory authorities, or "
                    "official consortia that have endorsed this specific bound. "
                    "Required to have ≥5 entries for citation_strength="
                    "'international_consensus'. Examples: 'FDA', 'EMA', 'ASNR', "
                    "'AAN', 'EAN', 'Alzheimer's Association', 'NICE', "
                    "'EANM', 'SNMMI', 'ACMG', 'CPIC', 'ClinGen', 'HUGO', "
                    "'IFCC', 'NIA-AA 2024 Workgroup', 'GA4GH'.",
    )

    @model_validator(mode="after")
    def _at_least_one_anchor(self) -> Citation:
        if not (self.citation_pmid or self.citation_doi or self.pmid_pending):
            raise ValueError(
                "Citation requires at least one of: citation_pmid, citation_doi, "
                "or pmid_pending=True (with citation_doi)."
            )
        if self.pmid_pending and not self.citation_doi:
            raise ValueError(
                "pmid_pending=True requires citation_doi to be set "
                "(no DOI to fall back on if PubMed indexing is delayed)."
            )
        return self


# ============================================================
# Range bound
# ============================================================

class RangeBound(BaseModel):
    """One bound (min or max, hard or plausible) on a measurement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bound_type: BoundType = Field(
        ...,
        description="One of hard_min, hard_max, plausible_min, plausible_max.",
    )
    value: float = Field(
        ...,
        description="The numeric bound. Inclusive: value >= hard_min, value <= hard_max.",
    )
    citation: Citation = Field(
        ...,
        description="The published source that establishes this bound.",
    )
    citation_strength: CitationStrength = Field(
        default=CitationStrength.DERIVED,
        description="How directly the bound traces to its cited source. "
                    "verbatim: cited source contains the exact bound. "
                    "derived: bound is computed from data in the cited source. "
                    "international_consensus: 5+ international bodies agree "
                    "(Citation.endorsing_bodies must list them).",
    )
    guideline_section: str = Field(
        ...,
        min_length=5,
        description="Section/table/figure pointer into the cited document "
                    "(e.g. 'Klunk 2015, Table 2'). At least 5 chars.",
    )
    bound_semantic: str = Field(
        default="diagnostic_threshold",
        description="Meaning of a PLAUSIBLE bound (ignored for hard bounds): "
                    "'physiological_envelope' = the value lies outside the "
                    "physiologically plausible range for this measurement, so "
                    "crossing it is an implausibility (implausible tier); "
                    "'diagnostic_threshold' = the bound marks a clinical / "
                    "diagnostic cutpoint whose crossing is expected in a real "
                    "cohort and is informational, not an error. Defaults to "
                    "'diagnostic_threshold' (the conservative, no-false-alarm "
                    "choice).",
    )
    notes: str | None = Field(
        default=None,
        description="Optional clarification (e.g. 'lower bound for adult patients').",
    )

    @model_validator(mode="after")
    def _consensus_requires_endorsing_bodies(self) -> RangeBound:
        # v1.30.0 evidence-model revision: the production endorser floor was
        # lowered from 5 to 2. Rationale: as of 2026, clinical adoption of a
        # biomarker/criterion coalesces around one or two AUTHORITATIVE sources
        # (an FDA/EMA clearance, a flagship CPG such as the Alzheimer's
        # Association CPG, or an NIA-AA/IWG/FNIH consensus), not five separate
        # societies. The compensating controls are unchanged: every production
        # bound still requires citation_strength in {international_consensus,
        # verbatim, derived}, a public_url, and a traceable citation. This makes
        # the bar "authoritative-source-traceable" rather than "5-body".
        _ENDORSER_FLOOR = 2
        if self.citation_strength == CitationStrength.INTERNATIONAL_CONSENSUS:
            if len(self.citation.endorsing_bodies) < _ENDORSER_FLOOR:
                raise ValueError(
                    f"RangeBound with citation_strength='international_consensus' "
                    f"requires Citation.endorsing_bodies to list at least "
                    f"{_ENDORSER_FLOOR} endorsing bodies. Got "
                    f"{len(self.citation.endorsing_bodies)}: "
                    f"{self.citation.endorsing_bodies!r}."
                )
            if not self.citation.public_url:
                raise ValueError(
                    "RangeBound with citation_strength='international_consensus' "
                    "requires Citation.public_url to be set."
                )
        if self.citation_strength == CitationStrength.VERBATIM:
            if not self.citation.public_url:
                raise ValueError(
                    "RangeBound with citation_strength='verbatim' requires "
                    "Citation.public_url to be set (so the verbatim claim "
                    "can be independently verified)."
                )
        return self


# ============================================================
# Measurement range (one measurement, all its bounds)
# ============================================================

class MeasurementRange(BaseModel):
    """All bounds for a single named measurement.

    A measurement is identified by `name` (e.g. 'sbp', 'centiloid', 'ab42_pg_ml').
    A measurement carries 1-4 bounds (any subset of hard_min/max + plausible_min/max).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Canonical measurement name (snake_case). Must match the "
                    "measurement_name column emitted by the adapter for this domain.",
    )
    unit: str = Field(
        ...,
        min_length=1,
        description="UCUM common-subset unit string (e.g. 'mmHg', 'pg/mL', 'mm3', "
                    "'centiloid', 'categorical'). Used for fail-fast unit consistency.",
    )
    description: str = Field(
        ...,
        min_length=5,
        description="Human-readable description of what this measurement is.",
    )
    bounds: list[RangeBound] = Field(
        ...,
        min_length=1,
        description="One or more bounds. At least one required (else what's the point?).",
    )
    measurement_kind: Literal["numeric", "categorical_set"] = Field(
        default="numeric",
        description="numeric (default) for continuous values; "
                    "categorical_set if the value is a label from valid_values.",
    )
    valid_values: list[str] | None = Field(
        default=None,
        description="For measurement_kind=categorical_set: the allowed labels. "
                    "Any observed value outside this set is flagged.",
    )

    @model_validator(mode="after")
    def _bounds_consistent_with_kind(self) -> MeasurementRange:
        if self.measurement_kind == "categorical_set":
            if not self.valid_values:
                raise ValueError(
                    f"MeasurementRange '{self.name}': measurement_kind="
                    f"'categorical_set' requires non-empty valid_values."
                )
        # For numeric: enforce that hard_min <= plausible_min and
        # plausible_max <= hard_max where both exist (the bounds must
        # be internally consistent, not contradict each other).
        bounds_by_type: dict[BoundType, float] = {b.bound_type: b.value for b in self.bounds}
        if (
            BoundType.HARD_MIN in bounds_by_type
            and BoundType.PLAUSIBLE_MIN in bounds_by_type
            and bounds_by_type[BoundType.HARD_MIN] > bounds_by_type[BoundType.PLAUSIBLE_MIN]
        ):
            raise ValueError(
                f"MeasurementRange '{self.name}': hard_min "
                f"({bounds_by_type[BoundType.HARD_MIN]}) > plausible_min "
                f"({bounds_by_type[BoundType.PLAUSIBLE_MIN]}); bounds inconsistent."
            )
        if (
            BoundType.HARD_MAX in bounds_by_type
            and BoundType.PLAUSIBLE_MAX in bounds_by_type
            and bounds_by_type[BoundType.HARD_MAX] < bounds_by_type[BoundType.PLAUSIBLE_MAX]
        ):
            raise ValueError(
                f"MeasurementRange '{self.name}': hard_max "
                f"({bounds_by_type[BoundType.HARD_MAX]}) < plausible_max "
                f"({bounds_by_type[BoundType.PLAUSIBLE_MAX]}); bounds inconsistent."
            )
        return self


# ============================================================
# Range pack (top-level document)
# ============================================================

#: Fields that constitute the SCIENTIFIC, citation-locked audited record of a
#: RangePack -- the only fields that feed canonical_sha256 (and thus flag_id).
#: All other RangePack fields are descriptive/lifecycle header metadata that the
#: audit engine never reads or emits; editing them must NOT drift flag_ids.
#: Module-level (not a class attr) to avoid Pydantic private-attribute handling.
#: See RangePack.canonical_sha256 docstring + ERRATA E-2026-007.
_RANGEPACK_SCIENTIFIC_FIELDS = ("rangepack_id", "anchor_citation", "measurements")


class RangePack(BaseModel):
    """A citation-locked clinical-range pack.

    One RangePack covers a coherent measurement domain (e.g. vital signs,
    CSF biomarkers, MRI volumetrics). Each pack ships with an anchor citation
    that establishes the authority for the whole document, plus per-bound
    citations for individual numeric bounds.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(
        ...,
        description=f"Range-pack schema version. Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}.",
    )
    rangepack_id: str = Field(
        ...,
        min_length=3,
        description="Stable identifier '<domain>/<name>@<version>' (e.g. 'vital_signs/standard@1.0.0').",
    )
    pack_version: str = Field(
        ...,
        description="SemVer of this pack's contents (independent of schema_version).",
    )
    effective_date: date = Field(
        ...,
        description="Date the pack contents were locked.",
    )
    status: RangePackStatus = Field(
        ...,
        description="production / skeleton / planned.",
    )
    domain: str = Field(
        ...,
        min_length=1,
        description="Measurement domain (e.g. 'vital_signs', 'csf_biomarkers').",
    )
    framework_name: str = Field(
        ...,
        min_length=5,
        description="Human-readable name of the framework this pack encodes.",
    )
    transcribed_by: str = Field(
        ...,
        min_length=5,
        description="Who transcribed this pack from source documents.",
    )
    clinical_source_authority: str = Field(
        ...,
        min_length=10,
        description="The organization or peer-reviewed body whose pronouncement "
                    "establishes the bounds (e.g. 'FDA / AHA / ATS', 'Alzheimer's "
                    "Association Biofluid Biomarker Standardization Initiative').",
    )
    anchor_citation: Citation = Field(
        ...,
        description="The single primary citation for this pack as a whole.",
    )
    measurements: list[MeasurementRange] = Field(
        ...,
        min_length=1,
        description="The measurements covered by this pack. At least one required.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional pack-level notes (e.g. assumed adult population).",
    )
    deprecated_in_favor_of: str | None = Field(
        default=None,
        description="When status=DEPRECATED, the rangepack_id of the successor "
                    "pack that supersedes this one (e.g. "
                    "'csf_biomarkers/csf_amyloid_consensus@1.0.0'). Either "
                    "this OR `deprecation_reason` must be set when status=DEPRECATED. "
                    "Introduced in v1.10.1.",
    )
    deprecation_reason: str | None = Field(
        default=None,
        description="When status=DEPRECATED and no direct successor exists "
                    "(e.g. the pack falls outside the project's current scope), "
                    "a human-readable reason for deprecation. Either this OR "
                    "`deprecated_in_favor_of` must be set when status=DEPRECATED. "
                    "Introduced in v1.10.1.",
        min_length=10,
    )

    @model_validator(mode="after")
    def _schema_supported_and_status_gate(self) -> RangePack:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version={self.schema_version!r}; "
                f"supported set is {sorted(SUPPORTED_SCHEMA_VERSIONS)}."
            )
        # Production packs must have unique measurement names
        names = [m.name for m in self.measurements]
        if len(names) != len(set(names)):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(
                f"Duplicate measurement name(s) in pack {self.rangepack_id}: {dupes}"
            )
        # Deprecation discipline: status=DEPRECATED requires either a successor
        # pointer OR an explicit reason (for scope-based deprecation).
        if self.status == RangePackStatus.DEPRECATED:
            if not (self.deprecated_in_favor_of or self.deprecation_reason):
                raise ValueError(
                    f"Pack {self.rangepack_id} has status=deprecated but neither "
                    f"deprecated_in_favor_of nor deprecation_reason is set. "
                    f"Every deprecated pack must declare either a successor "
                    f"pack ID or a human-readable reason for deprecation."
                )
        return self

    # ------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------

    def get_measurement(self, name: str) -> MeasurementRange | None:
        """Return the MeasurementRange for `name`, or None if not covered."""
        for m in self.measurements:
            if m.name == name:
                return m
        return None

    def covered_names(self) -> frozenset[str]:
        """Set of measurement names this pack covers."""
        return frozenset(m.name for m in self.measurements)

    # ------------------------------------------------------------
    # Canonical hashing (identical pattern to rulepack)
    # ------------------------------------------------------------

    def canonical_sha256(self) -> str:
        """Stable SHA-256 over the SCIENTIFIC content only.

        Hashes the citation-locked audited record: pack identity
        (``rangepack_id``), the ``anchor_citation``, and all
        ``measurements`` (bounds, values, units, valid_values, and the
        per-bound citations / guideline_sections that the audit engine reads
        and emits into every flag). Descriptive header metadata
        (framework_name, transcribed_by, clinical_source_authority, notes,
        status, domain, effective_date, schema_version, pack_version,
        deprecation fields) is EXCLUDED, so editing pack prose cannot drift
        the flag_id reproducibility fingerprint.

        Same principle as ``RulePack._canonical_serialize`` (ERRATA
        E-2026-006). The keep-set differs from the rulepack one because
        rangepack citations live per-bound and are emitted into flags, and
        the spec defines citation-locking as part of the regulated,
        reproducible record (temporalmetric v1.7 spec L239 traceability;
        proposed FDA Special Control (ii) citation-locked YAML). When in
        doubt a field is kept IN the fingerprint (fail-closed), never
        silently dropped.

        Two packs with identical scientific content produce identical
        hashes regardless of YAML key ordering, whitespace, or header prose.
        """
        dump = self.model_dump(mode="json")
        scientific = {k: dump[k] for k in _RANGEPACK_SCIENTIFIC_FIELDS if k in dump}
        canonical = json.dumps(scientific, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------
    # Usability gate
    # ------------------------------------------------------------

    def assert_usable_for_audit(self) -> None:
        """Raise if this pack should not be used in production.

        Mirrors LoadedRulePack.assert_usable_for_audit() — the framework
        refuses to silently emit flags from a non-production pack.

        Deprecated packs (introduced in v1.10.1) raise a more specific
        error pointing to the successor pack or deprecation reason.
        """
        if self.status == RangePackStatus.DEPRECATED:
            if self.deprecated_in_favor_of:
                raise ValueError(
                    f"RangePack {self.rangepack_id} is DEPRECATED. "
                    f"Use {self.deprecated_in_favor_of!r} instead. "
                    f"Deprecated packs are kept on disk for historical "
                    f"reference but cannot be used in audit_clinical_ranges()."
                )
            else:
                raise ValueError(
                    f"RangePack {self.rangepack_id} is DEPRECATED. "
                    f"Reason: {self.deprecation_reason}. "
                    f"This pack has no successor and is kept on disk for "
                    f"historical reference only."
                )
        if self.status != RangePackStatus.PRODUCTION:
            raise ValueError(
                f"RangePack {self.rangepack_id} has status={self.status.value!r}; "
                f"only 'production' packs may be used in audit_clinical_ranges()."
            )


# ============================================================
# Numeric-bound check (the core admissibility logic)
# ============================================================

def evaluate_value_against_bounds(
    value: float,
    bounds: list[RangeBound],
) -> tuple[bool, list[tuple[BoundType, RangeBound]]]:
    """Check a numeric value against a measurement's bounds.

    Returns:
        (admissible, violations) where `admissible` is True iff the value
        violates NO bound (neither hard nor plausible). `violations` is a
        list of (BoundType, RangeBound) for every bound the value failed,
        in pack order. An empty violations list means the value is admissible.
    """
    violations: list[tuple[BoundType, RangeBound]] = []
    for b in bounds:
        if b.bound_type == BoundType.HARD_MIN and value < b.value:
            violations.append((b.bound_type, b))
        elif b.bound_type == BoundType.HARD_MAX and value > b.value:
            violations.append((b.bound_type, b))
        elif b.bound_type == BoundType.PLAUSIBLE_MIN and value < b.value:
            violations.append((b.bound_type, b))
        elif b.bound_type == BoundType.PLAUSIBLE_MAX and value > b.value:
            violations.append((b.bound_type, b))
    return (len(violations) == 0, violations)


def evaluate_categorical_against_valid_set(
    value: str,
    valid_values: list[str],
) -> bool:
    """Categorical version: value must appear in valid_values to be admissible."""
    return value in valid_values

"""
neurotcs.clinical_ranges — Layer 2 audit: clinical-range validation.

Architecture: parallel to neurotcs.rulepack (Layer 1, temporal coherence).
Where Layer 1 audits the sequence of categorical disease states against a
published staging framework, Layer 2 audits the individual numeric and
categorical clinical measurements (vitals, labs, imaging volumetrics,
PET, genetics) against published biologically-plausible ranges.

Both layers share architectural primitives:
  - Citation-locked YAML packs with PMID/DOI anchors
  - Pydantic v2 strict schema with SHA-256 canonical-JSON hash
  - Deterministic audit IDs over inputs (audit_id for Layer 1, flag_id for Layer 2)
  - Fail-closed semantics
  - status enum: production / skeleton / planned

Public surface:
    from neurotcs.clinical_ranges import (
        audit_clinical_ranges,
        audit_clinical_ranges_multi,
        load_rangepack,
        list_rangepacks,
        ClinicalRangeAuditResult,
        ClinicalRangeFlag,
        MultiPackResult,
        RangePack,
        RangePackStatus,
    )
"""

from neurotcs.clinical_ranges.audit import (  # noqa: F401
    ClinicalRangeAuditResult,
    ClinicalRangeFlag,
    MultiPackResult,
    audit_clinical_ranges,
    audit_clinical_ranges_multi,
)
from neurotcs.clinical_ranges.loader import (  # noqa: F401
    LoadedRangePack,
    list_rangepacks,
    load_rangepack,
)
from neurotcs.clinical_ranges.schema import (  # noqa: F401
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    BoundType,
    Citation,
    CitationStrength,
    MeasurementRange,
    RangeBound,
    RangePack,
    RangePackStatus,
)

__status__ = "production"

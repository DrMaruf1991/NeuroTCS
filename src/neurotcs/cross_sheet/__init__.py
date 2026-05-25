"""
neurotcs.cross_sheet -- Layer 3 audit: cross-sheet consistency.

Architecture: parallel to neurotcs.clinical_ranges (Layer 2, per-visit
plausibility) and neurotcs.rulepack (Layer 1, temporal coherence).
Where Layer 1 audits within a sheet (predictions) and Layer 2 audits
within a sheet (predictions or biomarkers), Layer 3 audits CONSISTENCY
ACROSS MULTIPLE SHEETS of a single conformant submission.

Design lock: `docs/design/LAYER_3_DESIGN.md` at revision `v1.11.0-design.2`.

v1.11.0a1 status:
  - Schema and loader: SHIPPED (this session)
  - audit_cross_sheet(): NOT YET IMPLEMENTED (rc1 session #2+)
  - First invariant pack: SKELETON status (1 invariant, NeuroQuant 5.0
    hippocampus; refuses audit per fail-closed discipline)
  - Promotion to production: rc1 session #3 when all 5 invariants ship

Public surface:
    from neurotcs.cross_sheet import (
        load_invariantpack,
        list_invariantpacks,
        InvariantPack,
        InvariantPackStatus,
        CrossSheetInvariant,
        SheetSpec,
        NumericRange,
        CategoricalImpliesRangeCondition,
        FieldPresenceConsistencyCondition,
        ValueRangeConditionalCondition,
        CategoricalImpliesTrajectoryPatternCondition,
        TrajectoryPattern,
        ConditionalRangeCase,
    )

NOT YET EXPORTED (deferred to rc1 session #2+):
  - audit_cross_sheet
  - CrossSheetAuditResult
  - CrossSheetFlag
"""

from neurotcs.cross_sheet.loader import (  # noqa: F401
    LoadedInvariantPack,
    list_invariantpacks,
    load_invariantpack,
)
from neurotcs.cross_sheet.schema import (  # noqa: F401
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    CategoricalImpliesRangeCondition,
    CategoricalImpliesTrajectoryPatternCondition,
    ConditionalRangeCase,
    CrossSheetInvariant,
    FieldPresenceConsistencyCondition,
    InvariantPack,
    InvariantPackStatus,
    NumericRange,
    SheetSpec,
    TrajectoryPattern,
    ValueRangeConditionalCondition,
)

__status__ = "alpha"  # v1.11.0a1: schema + loader only; audit not yet implemented

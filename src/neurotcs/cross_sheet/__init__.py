"""
neurotcs.cross_sheet -- Layer 3 audit: cross-sheet consistency.

Architecture: parallel to neurotcs.clinical_ranges (Layer 2, per-visit
plausibility) and neurotcs.rulepack (Layer 1, temporal coherence).

Design lock: `docs/design/LAYER_3_DESIGN.md` at revision `v1.11.0-design.2`.

v1.11.0a2 status:
  - Schema and loader: SHIPPED in v1.11.0a1
  - audit_cross_sheet(): SHIPPED in this release
  - First invariant pack: RESEARCH_PREVIEW status (3 invariants:
    NeuroQuant 5.0, NeuroReader, icometrix icobrain)
  - Promotion to production: v1.11.0a3 (remaining 2 invariants + e2e validation)

Public surface:
    from neurotcs.cross_sheet import (
        load_invariantpack, list_invariantpacks,
        audit_cross_sheet, CrossSheetAuditResult, CrossSheetFlag,
        InvariantPack, InvariantPackStatus, CrossSheetInvariant,
        SheetSpec, NumericRange,
        CategoricalImpliesRangeCondition,
        FieldPresenceConsistencyCondition,
        ValueRangeConditionalCondition,
        CategoricalImpliesTrajectoryPatternCondition,
        TrajectoryPattern, ConditionalRangeCase,
    )
"""

from neurotcs.cross_sheet.audit import (  # noqa: F401
    CrossSheetAuditResult,
    CrossSheetFlag,
    audit_cross_sheet,
)
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

__status__ = "alpha"  # v1.11.0a2: schema + loader + audit; 3 invariants at research_preview

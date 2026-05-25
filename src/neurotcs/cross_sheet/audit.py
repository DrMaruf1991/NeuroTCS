"""
neurotcs.cross_sheet.audit -- Layer 3 audit execution.

Implements `audit_cross_sheet()`: applies one or more loaded invariant
packs against a multi-sheet submission and emits citation-locked flags
with deterministic `flag_id` derivation.

Design lock trace: `docs/design/LAYER_3_DESIGN.md` v1.11.0-design.2
  - Section 6: flag_id derivation (SHA-256 over canonical-JSON of pack
    hash + invariant name + sheet input hashes + observed values)
  - Section 7: integration with Layer 1 / Layer 2 (Layer 3 is independent;
    Layer 1 byte-exact preserved)
  - Section 8: fail-closed semantics (research_preview accepted in
    dry-run mode for development; production audit requires status=production)
  - Section 12 Q2: two-tier flag severity (Tier 1 warning within Bethlehem
    +/-10%; Tier 2 error outside both) -- ENCODED IN PACK YAML per
    invariant flag_severity field
  - Section 12 Q3: run all production packs by default; skip requires
    explicit manifest declaration -- IMPLEMENTED HERE
  - Section 12 Q4: unified ledger with audit_layer field -- IMPLEMENTED
    HERE via CrossSheetFlag.audit_layer = 'layer_3_cross_sheet'

v1.11.0a2 scope: only categorical_implies_range condition type is
executable. The other 3 condition types (field_presence_consistency,
value_range_conditional, categorical_implies_trajectory_pattern) are
schema-validated but raise NotImplementedError at audit time pending
v1.11.0a3 (genotype_phenotype_consistency pack) and v1.11.0rc1
(manifest_data_consistency pack).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from neurotcs.cross_sheet.loader import LoadedInvariantPack
from neurotcs.cross_sheet.schema import (
    CategoricalImpliesRangeCondition,
    CategoricalImpliesTrajectoryPatternCondition,
    CrossSheetInvariant,
    FieldPresenceConsistencyCondition,
    InvariantPackStatus,
    ValueRangeConditionalCondition,
)

# ============================================================
# Public flag and result types
# ============================================================

@dataclass(frozen=True)
class CrossSheetFlag:
    """A single Layer 3 cross-sheet consistency flag.

    Per LAYER_3_DESIGN.md section 12 Q4 resolution: Layer 3 flags share
    the unified audit ledger with Layer 1 and Layer 2 flags, distinguished
    by the `audit_layer` field.
    """
    flag_id: str
    audit_layer: Literal["layer_3_cross_sheet"] = field(default="layer_3_cross_sheet")
    pack_id: str = ""
    invariant_name: str = ""
    severity: Literal["error", "warning", "info"] = "warning"
    join_key_values: dict[str, Any] = field(default_factory=dict)
    observed_value: Any = None
    expected_range_lo: float | None = None
    expected_range_hi: float | None = None
    declared_tool: str | None = None
    flag_reason: str = ""
    citation_pmid: str | None = None
    citation_doi: str | None = None
    citation_public_url: str | None = None


@dataclass
class CrossSheetAuditResult:
    """Result of running audit_cross_sheet() against a submission.

    Contains the list of flags emitted plus diagnostic counters that
    surface what the audit actually did (so a reviewer can verify
    coverage).
    """
    flags: list[CrossSheetFlag] = field(default_factory=list)
    packs_run: list[str] = field(default_factory=list)
    packs_skipped: list[tuple[str, str]] = field(default_factory=list)  # (pack_id, reason)
    n_rows_audited: int = 0
    n_invariants_evaluated: int = 0
    n_dry_run: bool = False  # True if any research_preview pack was accepted in dry-run mode


# ============================================================
# Public API
# ============================================================

def audit_cross_sheet(
    submission: dict[str, Any],
    invariant_packs: list[LoadedInvariantPack],
    *,
    dry_run: bool = False,
    skip_packs: list[str] | None = None,
    skip_reasons: dict[str, str] | None = None,
) -> CrossSheetAuditResult:
    """Run Layer 3 cross-sheet audit against a submission.

    Parameters
    ----------
    submission : dict
        A submission dictionary with sheet roles as keys:
            {
                "manifest": dict,
                "predictions": list[dict] | DataFrame-equivalent,
                "patients": list[dict] | DataFrame-equivalent,
                "biomarkers": list[dict] | DataFrame-equivalent,
                "attribution": dict | None,
            }
        Sheets may be absent; invariants that require them will be
        skipped with a 'missing_required_sheet' info flag (per
        LAYER_3_DESIGN.md section 8 fail-closed semantics rule 1).

    invariant_packs : list[LoadedInvariantPack]
        Packs to evaluate. Per LAYER_3_DESIGN.md section 12 Q3
        resolution: all production packs run by default; skipping
        requires explicit skip_packs + skip_reasons.

    dry_run : bool, default False
        If True, accept research_preview packs (and emit flags) for
        development purposes. If False (production audit), refuse
        non-production packs per fail-closed discipline.

    skip_packs : list[str] | None
        Optional list of pack_ids to skip. Must be accompanied by
        skip_reasons entries.

    skip_reasons : dict[str, str] | None
        pack_id -> human-readable skip reason (min 20 chars).

    Returns
    -------
    CrossSheetAuditResult
        Aggregated flags + diagnostic counters.

    Raises
    ------
    ValueError
        If a pack is non-production and dry_run is False, OR if
        skip_packs is provided without matching skip_reasons.
    NotImplementedError
        If the audit encounters a condition type that is not yet
        implemented (v1.11.0a2 only supports categorical_implies_range).
    """
    result = CrossSheetAuditResult()
    skip_packs = skip_packs or []
    skip_reasons = skip_reasons or {}

    # Validate skip discipline (section 12 Q3 resolution)
    for skip_id in skip_packs:
        if skip_id not in skip_reasons:
            raise ValueError(
                f"Pack {skip_id!r} listed in skip_packs without a "
                f"corresponding skip_reasons entry. Per LAYER_3_DESIGN.md "
                f"section 12 Q3 resolution, skipping requires an explicit "
                f"human-readable reason (min 20 chars)."
            )
        reason = skip_reasons[skip_id]
        if len(reason) < 20:
            raise ValueError(
                f"skip_reasons[{skip_id!r}] = {reason!r} is too short "
                f"(min 20 chars required for transparency)."
            )

    for lp in invariant_packs:
        pack_id = lp.invariantpack.invariantpack_id

        # Honor skip list
        if pack_id in skip_packs:
            result.packs_skipped.append((pack_id, skip_reasons[pack_id]))
            continue

        # Status gate (section 8 fail-closed)
        if lp.status == InvariantPackStatus.PRODUCTION:
            pass  # always OK
        elif lp.status == InvariantPackStatus.RESEARCH_PREVIEW:
            if not dry_run:
                raise ValueError(
                    f"Pack {pack_id} has status='research_preview'; "
                    f"audit_cross_sheet refuses to run a non-production "
                    f"pack in production mode. Pass dry_run=True to "
                    f"accept research_preview packs for development."
                )
            result.n_dry_run = True
        else:
            # skeleton / planned / deprecated
            raise ValueError(
                f"Pack {pack_id} has status={lp.status.value!r}; "
                f"only production (or research_preview with dry_run=True) "
                f"packs may be used in audit_cross_sheet."
            )

        result.packs_run.append(pack_id)

        # Evaluate each invariant
        for invariant in lp.invariantpack.invariants:
            inv_flags = _evaluate_invariant(invariant, submission, lp)
            result.flags.extend(inv_flags)
            result.n_invariants_evaluated += 1

    # Count total rows audited (best-effort across biomarkers sheet)
    biomarkers = submission.get("biomarkers", [])
    if isinstance(biomarkers, list):
        result.n_rows_audited = len(biomarkers)

    return result


# ============================================================
# Per-invariant evaluation
# ============================================================

def _evaluate_invariant(
    invariant: CrossSheetInvariant,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate one invariant against the submission, returning 0+ flags.

    Per LAYER_3_DESIGN.md section 8 rule 1: missing required sheets
    produce an info flag, not an exception.
    """
    flags: list[CrossSheetFlag] = []

    # Check sheet presence
    missing_required = []
    for sheet_spec in invariant.sheets_required:
        if sheet_spec.required and sheet_spec.role not in submission:
            missing_required.append(sheet_spec.role)
    if missing_required:
        flags.append(_make_missing_sheet_flag(invariant, lp, missing_required))
        return flags

    cond = invariant.condition

    if isinstance(cond, CategoricalImpliesRangeCondition):
        flags.extend(_evaluate_categorical_implies_range(invariant, cond, submission, lp))
    elif isinstance(cond, FieldPresenceConsistencyCondition):
        raise NotImplementedError(
            f"FieldPresenceConsistencyCondition (invariant {invariant.name!r}) "
            f"is not yet implemented in v1.11.0a2. It is schema-validated only. "
            f"Execution lands in v1.11.0rc1 with the manifest_data_consistency pack."
        )
    elif isinstance(cond, ValueRangeConditionalCondition):
        raise NotImplementedError(
            f"ValueRangeConditionalCondition (invariant {invariant.name!r}) "
            f"is not yet implemented in v1.11.0a2. It is schema-validated only."
        )
    elif isinstance(cond, CategoricalImpliesTrajectoryPatternCondition):
        raise NotImplementedError(
            f"CategoricalImpliesTrajectoryPatternCondition (invariant "
            f"{invariant.name!r}) is not yet implemented in v1.11.0a2. "
            f"Execution lands in v1.11.0a3 with the genotype_phenotype_consistency pack."
        )
    else:
        raise NotImplementedError(
            f"Unknown condition type for invariant {invariant.name!r}: "
            f"{type(cond).__name__}"
        )

    return flags


def _evaluate_categorical_implies_range(
    invariant: CrossSheetInvariant,
    cond: CategoricalImpliesRangeCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a categorical_implies_range condition.

    Semantics: if source_sheet.source_field == source_value, then
    every row in target_sheet must have target_field within target_range.
    """
    flags: list[CrossSheetFlag] = []

    # Resolve trigger value from source sheet
    source = submission.get(cond.source_sheet)
    if source is None:
        # missing required sheet already handled in _evaluate_invariant
        return flags

    declared_value = _get_scalar_from_sheet(source, cond.source_field)
    if declared_value is None:
        # Source field not declared in this submission: invariant doesn't apply
        return flags
    if declared_value != cond.source_value:
        # Source field declared but doesn't match this invariant's trigger
        return flags

    # Invariant applies; check target sheet
    target = submission.get(cond.target_sheet)
    if target is None:
        return flags  # shouldn't happen if sheets_required is honored

    rows = _iter_rows(target)
    for row in rows:
        observed = row.get(cond.target_field)
        if observed is None:
            continue  # row doesn't carry this field; not an error
        try:
            observed_num = float(observed)
        except (TypeError, ValueError):
            continue  # non-numeric value; not this invariant's concern
        if observed_num < cond.target_range.lo or observed_num > cond.target_range.hi:
            # Violation: emit flag
            join_key_values = {k: row.get(k) for k in invariant.join_keys if k in row}
            flag = _make_range_violation_flag(
                invariant=invariant,
                lp=lp,
                declared_value=declared_value,
                observed=observed_num,
                join_key_values=join_key_values,
                lo=cond.target_range.lo,
                hi=cond.target_range.hi,
            )
            flags.append(flag)

    return flags


# ============================================================
# Helpers
# ============================================================

def _get_scalar_from_sheet(sheet: Any, field_name: str) -> Any:
    """Extract a single scalar value from a sheet (typically manifest)."""
    if isinstance(sheet, dict):
        return sheet.get(field_name)
    if isinstance(sheet, list) and sheet:
        # First row's value (manifest is typically a single-row dict, but
        # tolerate list-of-one-row form)
        first = sheet[0]
        if isinstance(first, dict):
            return first.get(field_name)
    return None


def _iter_rows(sheet: Any) -> list[dict[str, Any]]:
    """Normalize a sheet to a list of row dicts."""
    if isinstance(sheet, list):
        return [r for r in sheet if isinstance(r, dict)]
    if isinstance(sheet, dict):
        return [sheet]
    return []


def _make_missing_sheet_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    missing: list[str],
) -> CrossSheetFlag:
    """Emit a 'missing_required_sheet' info flag (section 8 rule 1)."""
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "missing_required_sheet",
        "missing_sheets": sorted(missing),
    }
    flag_id = _derive_flag_id(payload)
    return CrossSheetFlag(
        flag_id=flag_id,
        pack_id=lp.invariantpack.invariantpack_id,
        invariant_name=invariant.name,
        severity="info",
        flag_reason=f"missing_required_sheet: {sorted(missing)}",
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _make_range_violation_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    declared_value: Any,
    observed: float,
    join_key_values: dict[str, Any],
    lo: float,
    hi: float,
) -> CrossSheetFlag:
    """Emit a range-violation flag with deterministic flag_id derivation.

    Per LAYER_3_DESIGN.md section 6: flag_id = SHA-256 over canonical-JSON
    of (yaml_sha256, invariant_name, observed_values, join_keys).
    """
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "categorical_implies_range_violation",
        "declared_value": str(declared_value),
        "observed": float(observed),
        "lo": float(lo),
        "hi": float(hi),
        "join_key_values": _stringify_for_hash(join_key_values),
        "contract_version": "1.2.0",
    }
    flag_id = _derive_flag_id(payload)
    return CrossSheetFlag(
        flag_id=flag_id,
        pack_id=lp.invariantpack.invariantpack_id,
        invariant_name=invariant.name,
        severity=invariant.flag_severity,
        join_key_values=dict(join_key_values),
        observed_value=observed,
        expected_range_lo=lo,
        expected_range_hi=hi,
        declared_tool=str(declared_value),
        flag_reason=(
            f"observed {observed} outside declared-tool range [{lo}, {hi}] "
            f"(tool={declared_value!r})"
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _stringify_for_hash(d: dict[str, Any]) -> dict[str, str]:
    """Convert join key values to strings for stable hashing."""
    return {str(k): "" if v is None else str(v) for k, v in d.items()}


def _derive_flag_id(payload: dict[str, Any]) -> str:
    """SHA-256 over canonical-JSON form of the payload.

    Per LAYER_3_DESIGN.md section 6: deterministic, cross-platform-stable.
    Uses sort_keys=True and separators=(',', ':') for byte-exact
    canonical JSON across Linux/Windows/macOS.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

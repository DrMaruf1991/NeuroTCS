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
    CategoricalImpliesRangeRowwiseCondition,
    CategoricalImpliesTrajectoryPatternCondition,
    CategoricalNotInKnownSetCondition,
    ConditionalRangeCase,
    CrossSheetInvariant,
    FieldPresenceConsistencyCondition,
    InvariantPackStatus,
    NumericConflictCondition,
    ReferentialIntegrityCondition,
    RowwiseConjunctionAdvisoryCondition,
    SubfieldRankConstraintCondition,
    TrajectoryMonotonicityCondition,
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
        flags.extend(_evaluate_field_presence_consistency(invariant, cond, submission, lp))
    elif isinstance(cond, ValueRangeConditionalCondition):
        flags.extend(_evaluate_value_range_conditional(invariant, cond, submission, lp))
    elif isinstance(cond, CategoricalImpliesTrajectoryPatternCondition):
        flags.extend(_evaluate_trajectory_pattern(invariant, cond, submission, lp))
    elif isinstance(cond, CategoricalNotInKnownSetCondition):
        flags.extend(_evaluate_categorical_not_in_known_set(invariant, cond, submission, lp))
    elif isinstance(cond, NumericConflictCondition):
        flags.extend(_evaluate_numeric_conflict(invariant, cond, submission, lp))
    elif isinstance(cond, TrajectoryMonotonicityCondition):
        flags.extend(_evaluate_trajectory_monotonicity(invariant, cond, submission, lp))
    elif isinstance(cond, CategoricalImpliesRangeRowwiseCondition):
        flags.extend(_evaluate_categorical_implies_range_rowwise(invariant, cond, submission, lp))
    elif isinstance(cond, ReferentialIntegrityCondition):
        flags.extend(_evaluate_referential_integrity(invariant, cond, submission, lp))
    elif isinstance(cond, SubfieldRankConstraintCondition):
        flags.extend(_evaluate_subfield_rank_constraint(invariant, cond, submission, lp))
    elif isinstance(cond, RowwiseConjunctionAdvisoryCondition):
        flags.extend(_evaluate_rowwise_conjunction_advisory(invariant, cond, submission, lp))
    else:
        raise NotImplementedError(
            f"Unknown condition type for invariant {invariant.name!r}: "
            f"{type(cond).__name__}"
        )

    return flags


def _evaluate_trajectory_pattern(
    invariant: CrossSheetInvariant,
    cond: CategoricalImpliesTrajectoryPatternCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a categorical_implies_trajectory_pattern condition.

    Semantics (per LAYER_3_DESIGN.md section 4.4.4 + section 12 Q1 resolution):
    For each patient row in source_sheet whose source_field == source_value
    (e.g., apoe_genotype == 'e4/e4'), find that patient's longitudinal
    trajectory in trajectory_sheet (typically 'predictions') and check
    whether the observed pattern matches expectations from
    pattern.flag_threshold.

    v1.11.0a3 implements ONE flag_threshold pattern:
      'none_observed_after_age_X_with_Y_followup'

    This pattern fires when:
      - The patient is over age X at the last observed visit
      - The follow-up duration spans >= Y years
      - The expected outcome (the population-baseline-rate event,
        e.g., AD dementia for elevated_risk_marker kind) was NOT
        observed

    The flag is emitted at the severity declared by the invariant
    (per Q1 resolution, v1.11.0 packs use 'info' severity for these
    advisory-only invariants -- 'warning' or 'error' deferred until
    observed false-positive rates are known).

    Other flag_threshold strings are accepted by the schema but
    raise NotImplementedError at execution time, with a pointer to
    the future session that ships them.
    """
    flags: list[CrossSheetFlag] = []

    source = submission.get(cond.source_sheet)
    if source is None:
        return flags

    trajectory = submission.get(cond.trajectory_sheet)
    if trajectory is None:
        return flags

    # Parse the flag_threshold pattern string to extract age threshold
    # and followup duration.
    pattern_parsed = _parse_trajectory_threshold(cond.pattern.flag_threshold)
    if pattern_parsed is None:
        raise NotImplementedError(
            f"flag_threshold pattern {cond.pattern.flag_threshold!r} "
            f"(invariant {invariant.name!r}) is not yet implemented "
            f"in v1.11.0a3. Supported patterns: "
            f"'none_observed_after_age_X_with_Y_followup'."
        )
    age_threshold, followup_years = pattern_parsed

    # For each matching source row, find their trajectory and evaluate
    patient_rows = _iter_rows(source)
    trajectory_rows = _iter_rows(trajectory)

    for patient_row in patient_rows:
        declared = patient_row.get(cond.source_field)
        if declared is None or declared != cond.source_value:
            continue

        patient_id = patient_row.get("patient_id")
        if patient_id is None:
            continue

        # Find this patient's trajectory rows
        their_rows = [r for r in trajectory_rows if r.get("patient_id") == patient_id]
        if not their_rows:
            continue

        # Extract ages and outcomes
        ages = []
        outcomes = []
        for r in their_rows:
            age = r.get("age_years")
            outcome = r.get("ad_dementia_status")  # truthy if AD dementia observed
            if age is None:
                continue
            try:
                ages.append(float(age))
            except (TypeError, ValueError):
                continue
            outcomes.append(outcome)

        if not ages:
            continue

        last_age = max(ages)
        first_age = min(ages)
        followup_span = last_age - first_age

        # Check the trigger conditions
        any_outcome_observed = any(o for o in outcomes if o)

        if (
            last_age >= age_threshold
            and followup_span >= followup_years
            and not any_outcome_observed
        ):
            # Pattern: elevated risk marker but no event observed -> flag
            join_keys_values = {"patient_id": patient_id}
            flag = _make_trajectory_pattern_flag(
                invariant=invariant,
                lp=lp,
                cond=cond,
                patient_id=patient_id,
                last_age=last_age,
                followup_span=followup_span,
                age_threshold=age_threshold,
                followup_threshold=followup_years,
                join_key_values=join_keys_values,
            )
            flags.append(flag)

    return flags


def _parse_trajectory_threshold(threshold: str) -> tuple[float, float] | None:
    """Parse flag_threshold patterns like
    'none_observed_after_age_85_with_10y_followup'.

    Returns (age_threshold, followup_years) or None if the pattern is
    not one of the v1.11.0a3-supported forms.
    """
    import re
    m = re.match(
        r"^none_observed_after_age_(\d+)_with_(\d+)y_followup$",
        threshold,
    )
    if m is None:
        return None
    return float(m.group(1)), float(m.group(2))


def _make_trajectory_pattern_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    cond: CategoricalImpliesTrajectoryPatternCondition,
    patient_id: Any,
    last_age: float,
    followup_span: float,
    age_threshold: float,
    followup_threshold: float,
    join_key_values: dict[str, Any],
) -> CrossSheetFlag:
    """Emit a trajectory-pattern flag (typically 'info' severity)."""
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "trajectory_pattern_deviation",
        "source_value": cond.source_value,
        "last_age": float(last_age),
        "followup_span_years": float(followup_span),
        "age_threshold": float(age_threshold),
        "followup_threshold_years": float(followup_threshold),
        "expected_baseline_rate": float(cond.pattern.population_baseline_rate),
        "pattern_kind": cond.pattern.kind,
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
        observed_value=last_age,
        declared_tool=cond.source_value,
        flag_reason=(
            f"Patient with {cond.source_field}={cond.source_value!r} "
            f"observed cognitively normal at age {last_age} with "
            f"{followup_span:.1f}y follow-up; population baseline rate for "
            f"AD dementia in this group is {cond.pattern.population_baseline_rate:.0%} "
            f"by age {age_threshold:.0f} (Fortea 2024); pattern deviation "
            f"flagged for review (advisory only)."
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _evaluate_field_presence_consistency(
    invariant: CrossSheetInvariant,
    cond: FieldPresenceConsistencyCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a field_presence_consistency condition.

    Per v1.11.0-design.2 section 4.4.2: "if the manifest declares L3
    conformance, attribution/ must exist with one file per prediction row."

    Two modes:

    MODE A (sheet-presence only, required_per_row_in_sheet is None):
        If source_sheet.source_field == source_value, then required_sheet
        must be present in the submission AND non-empty (at least one row,
        or for the manifest sheet, a non-empty dict).
        On failure, emit exactly ONE flag describing the missing sheet.

    MODE B (per-row matching, required_per_row_in_sheet is set):
        If source_sheet.source_field == source_value, then:
          (1) required_sheet must be present and non-empty (Mode A check), AND
          (2) for each row in required_per_row_in_sheet, there must be a
              matching entry in required_sheet keyed by the invariant's
              join_keys (e.g., one attribution file per prediction row,
              matched on patient_id + visit_id).
        On failure of (1), emit ONE flag for the missing required_sheet.
        On failure of (2), emit ONE flag PER unmatched row in
              required_per_row_in_sheet, with join_key_values populated.

    A row in the manifest sheet is the manifest dict itself (the manifest
    is dict-shaped, not list-shaped). Other sheets are list-of-dicts.

    The trigger evaluation: source_sheet.source_field == source_value is
    checked against:
      - The manifest dict directly if source_sheet == "manifest"
      - The first row of source_sheet if it's a list (sheet-level metadata
        check; row-level checks belong to other condition types)

    If the trigger condition is not met (source value not matching),
    emit no flags -- the invariant simply does not apply to this submission.

    If the source_sheet itself is missing or empty, also emit no flags --
    the trigger cannot be evaluated, and other invariants in the pack are
    responsible for missing-source-sheet checks.
    """
    flags: list[CrossSheetFlag] = []

    source = submission.get(cond.source_sheet)
    if source is None:
        return flags

    # Extract the field value from the source sheet
    source_field_value = _extract_source_field_value(source, cond.source_field)
    if source_field_value is None:
        return flags

    # Check trigger: does the source field match the declared source value?
    # v1.18.0: coerce native booleans to lowercase "true"/"false" so a YAML
    # source_value: "true" matches a manifest-declared Python True. This is
    # the cross-sheet anchor for v1.2.0 input contract field
    # `declares_continuous_biomarkers` and any future boolean-valued manifest
    # field. Strings, ints, floats, and other types are compared by raw
    # equality (no change for existing v1.11.0 packs).
    _normalized_source_field_value = (
        ("true" if source_field_value else "false")
        if isinstance(source_field_value, bool)
        else source_field_value
    )
    if _normalized_source_field_value != cond.source_value:
        return flags

    # Trigger matched. Now check required_sheet presence + non-emptiness.
    required = submission.get(cond.required_sheet)
    if required is None or _is_empty_sheet(required):
        flag = _make_field_presence_missing_sheet_flag(
            invariant=invariant,
            lp=lp,
            cond=cond,
            source_field_value=source_field_value,
        )
        flags.append(flag)
        return flags  # No point checking per-row if the sheet is missing

    # If Mode A (no per-row check), we're done.
    if cond.required_per_row_in_sheet is None:
        return flags

    # Mode B: each row in required_per_row_in_sheet must have a matching
    # entry in required_sheet, matched on the invariant's join_keys.
    per_row_sheet = submission.get(cond.required_per_row_in_sheet)
    if per_row_sheet is None or _is_empty_sheet(per_row_sheet):
        # Nothing to match against; no flags.
        return flags

    per_row_rows = _iter_rows(per_row_sheet)
    required_rows = _iter_rows(required)

    # Build an index of required_sheet by the invariant's join_keys
    join_keys = invariant.join_keys
    required_index: set[tuple[Any, ...]] = set()
    for r in required_rows:
        key = tuple(r.get(k) for k in join_keys)
        if all(v is not None for v in key):
            required_index.add(key)

    # For each row in per_row_sheet, check whether its key is in the index
    for row in per_row_rows:
        key = tuple(row.get(k) for k in join_keys)
        if any(v is None for v in key):
            continue  # Can't match a row missing its join key
        if key not in required_index:
            join_key_values = dict(zip(join_keys, key, strict=True))
            flag = _make_field_presence_unmatched_row_flag(
                invariant=invariant,
                lp=lp,
                cond=cond,
                source_field_value=source_field_value,
                join_key_values=join_key_values,
            )
            flags.append(flag)

    return flags


def _extract_source_field_value(source: Any, source_field: str) -> Any:
    """Extract a field value from a source sheet.

    The manifest is dict-shaped; other sheets are list-of-dicts and we
    take the first row as representing sheet-level metadata.

    v1.18.0: source_field may contain dot-separated segments to traverse
    nested objects (e.g. "rule_pack.id" on the manifest). Each segment
    must be present and map to a dict (intermediate segments) or a
    terminal value (final segment); missing or non-dict intermediates
    return None.
    """
    def _traverse(d: Any, path: str) -> Any:
        segments = path.split(".") if "." in path else [path]
        current: Any = d
        for seg in segments:
            if not isinstance(current, dict):
                return None
            current = current.get(seg)
            if current is None:
                return None
        return current

    if isinstance(source, dict):
        return _traverse(source, source_field)
    if isinstance(source, list) and source:
        first_row = source[0]
        if isinstance(first_row, dict):
            return _traverse(first_row, source_field)
    return None


def _is_empty_sheet(sheet: Any) -> bool:
    """A sheet is empty if it's an empty dict, empty list, or None."""
    if sheet is None:
        return True
    if isinstance(sheet, dict):
        return len(sheet) == 0
    if isinstance(sheet, list):
        return len(sheet) == 0
    return False


def _make_field_presence_missing_sheet_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    cond: FieldPresenceConsistencyCondition,
    source_field_value: Any,
) -> CrossSheetFlag:
    """Emit a flag for a missing required_sheet."""
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "field_presence_missing_sheet",
        "source_value": cond.source_value,
        "source_sheet": cond.source_sheet,
        "source_field": cond.source_field,
        "observed_source_value": _stringify_for_hash({"v": source_field_value})["v"],
        "required_sheet": cond.required_sheet,
        "contract_version": "1.2.0",
    }
    flag_id = _derive_flag_id(payload)
    return CrossSheetFlag(
        flag_id=flag_id,
        pack_id=lp.invariantpack.invariantpack_id,
        invariant_name=invariant.name,
        severity=invariant.flag_severity,
        join_key_values={},
        observed_value=None,
        declared_tool=str(source_field_value),
        flag_reason=(
            f"{cond.source_sheet}.{cond.source_field}={source_field_value!r} "
            f"requires sheet {cond.required_sheet!r} to be present and non-empty, "
            f"but {cond.required_sheet!r} is missing or empty in this submission."
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _make_field_presence_unmatched_row_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    cond: FieldPresenceConsistencyCondition,
    source_field_value: Any,
    join_key_values: dict[str, Any],
) -> CrossSheetFlag:
    """Emit a flag for a row in required_per_row_in_sheet that has no
    matching entry in required_sheet."""
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "field_presence_unmatched_row",
        "source_value": cond.source_value,
        "source_sheet": cond.source_sheet,
        "source_field": cond.source_field,
        "observed_source_value": _stringify_for_hash({"v": source_field_value})["v"],
        "required_sheet": cond.required_sheet,
        "required_per_row_in_sheet": cond.required_per_row_in_sheet,
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
        observed_value=None,
        declared_tool=str(source_field_value),
        flag_reason=(
            f"{cond.source_sheet}.{cond.source_field}={source_field_value!r} "
            f"requires each row in {cond.required_per_row_in_sheet!r} to have "
            f"a matching entry in {cond.required_sheet!r} (keyed on {invariant.join_keys}), "
            f"but row with {join_key_values} has no matching entry."
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _evaluate_value_range_conditional(
    invariant: CrossSheetInvariant,
    cond: ValueRangeConditionalCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a value_range_conditional condition.

    Per v1.11.0-design.2 section 4.4.3: "A numeric field's valid bounds
    depend on a categorical field in another sheet."

    Canonical use case: age-conditional normative ranges. E.g., if
    patients.age_band == "pediatric", biomarkers.hippocampal_volume must
    be in [1.5, 3.5]; if "adult", in [2.8, 5.0]; if "geriatric", in [2.2, 4.5].

    Semantics:
    - source_sheet must be a row-shaped sheet (NOT manifest).
      For each row in source_sheet, look up the source_field value and
      find the matching case in cases. If no case matches, the row is
      skipped (no flag -- absence of a case is not a violation; if the
      invariant author wants to flag unknown values, they declare a
      catch-all case or use a different condition type).
    - For each matched source row:
        * If target_sheet == source_sheet: same-row check.
          The target_field is read from the same row; the range check
          applies in place.
        * If target_sheet != source_sheet: cross-sheet check.
          The source row is joined to target rows via the invariant's
          join_keys; for each matching target row, target_field is
          checked against the case's target_range.
    - Range bounds are inclusive (consistent with categorical_implies_range
      and the NumericRange schema).
    - Source rows with incomplete join keys are skipped in the cross-sheet
      case (same discipline as field_presence_consistency Mode B).
    - manifest as source_sheet is NOT supported in v1.11.0a7. If encountered,
      raises NotImplementedError pointing the author to
      categorical_implies_range (which handles whole-submission triggers).

    On violation: one flag per (source_row, target_row, case) violation.
    """
    flags: list[CrossSheetFlag] = []

    source = submission.get(cond.source_sheet)
    if source is None:
        return flags

    if cond.source_sheet == "manifest":
        raise NotImplementedError(
            f"value_range_conditional with source_sheet='manifest' is not "
            f"supported in v1.11.0a7 (invariant {invariant.name!r}). The "
            f"manifest-source semantics (one trigger value applies to all "
            f"target rows) are already handled by the "
            f"categorical_implies_range condition type. Use "
            f"categorical_implies_range for manifest-trigger checks."
        )

    # Build case index: source_value -> case
    case_index = {case.source_value: case for case in cond.cases}

    source_rows = _iter_rows(source)
    if not source_rows:
        return flags

    # Determine target rows
    same_sheet = (cond.cases[0].target_sheet == cond.source_sheet)
    # Note: all cases must reference the same target_sheet (it's part of the
    # condition's semantic contract). The schema does not enforce this, but
    # an invariant where cases point at different target sheets is malformed.
    # We sanity-check it.
    target_sheets = {case.target_sheet for case in cond.cases}
    if len(target_sheets) > 1:
        raise NotImplementedError(
            f"value_range_conditional with cases pointing at multiple "
            f"target_sheets ({sorted(target_sheets)}) is not supported in "
            f"v1.11.0a7 (invariant {invariant.name!r}). All cases must "
            f"reference the same target_sheet."
        )

    target_sheet_name = cond.cases[0].target_sheet
    target = submission.get(target_sheet_name)
    if target is None:
        # No target data; nothing to check.
        return flags

    target_rows = _iter_rows(target)
    if not target_rows:
        return flags

    # For each source row, find matching case and matching target row(s)
    join_keys = invariant.join_keys

    for src_row in source_rows:
        src_value = src_row.get(cond.source_field)
        if src_value is None:
            continue  # No trigger value on this row

        case = case_index.get(str(src_value))
        if case is None:
            continue  # No matching case; row is silent

        if same_sheet:
            # Same-row check: target_field is on this same row
            tgt_value = src_row.get(case.target_field)
            if tgt_value is None:
                continue
            try:
                tgt_value_f = float(tgt_value)
            except (TypeError, ValueError):
                continue

            if not (case.target_range.lo <= tgt_value_f <= case.target_range.hi):
                join_key_values = {k: src_row.get(k) for k in join_keys}
                # Drop None join values for cleaner flag identity
                join_key_values = {k: v for k, v in join_key_values.items() if v is not None}
                flag = _make_value_range_conditional_flag(
                    invariant=invariant,
                    lp=lp,
                    cond=cond,
                    case=case,
                    observed=tgt_value_f,
                    join_key_values=join_key_values,
                    source_value=str(src_value),
                )
                flags.append(flag)
        else:
            # Cross-sheet check: join src_row to target rows via join_keys
            src_key = tuple(src_row.get(k) for k in join_keys)
            if any(v is None for v in src_key):
                continue  # Incomplete source key, skip

            # Find matching target rows
            for tgt_row in target_rows:
                tgt_key = tuple(tgt_row.get(k) for k in join_keys)
                if tgt_key != src_key:
                    continue

                tgt_value = tgt_row.get(case.target_field)
                if tgt_value is None:
                    continue
                try:
                    tgt_value_f = float(tgt_value)
                except (TypeError, ValueError):
                    continue

                if not (case.target_range.lo <= tgt_value_f <= case.target_range.hi):
                    join_key_values = dict(zip(join_keys, src_key, strict=True))
                    flag = _make_value_range_conditional_flag(
                        invariant=invariant,
                        lp=lp,
                        cond=cond,
                        case=case,
                        observed=tgt_value_f,
                        join_key_values=join_key_values,
                        source_value=str(src_value),
                    )
                    flags.append(flag)

    return flags


def _make_value_range_conditional_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    cond: ValueRangeConditionalCondition,
    case: ConditionalRangeCase,
    observed: float,
    join_key_values: dict[str, Any],
    source_value: str,
) -> CrossSheetFlag:
    """Emit a value-range-conditional violation flag."""
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "value_range_conditional",
        "source_sheet": cond.source_sheet,
        "source_field": cond.source_field,
        "source_value": source_value,
        "target_sheet": case.target_sheet,
        "target_field": case.target_field,
        "target_range_lo": case.target_range.lo,
        "target_range_hi": case.target_range.hi,
        "observed_value": observed,
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
        declared_tool=source_value,
        expected_range_lo=case.target_range.lo,
        expected_range_hi=case.target_range.hi,
        flag_reason=(
            f"{cond.source_sheet}.{cond.source_field}={source_value!r} requires "
            f"{case.target_sheet}.{case.target_field} in "
            f"[{case.target_range.lo}, {case.target_range.hi}], "
            f"observed {observed}."
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _evaluate_categorical_not_in_known_set(
    invariant: CrossSheetInvariant,
    cond: CategoricalNotInKnownSetCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a categorical_not_in_known_set condition.

    Per v1.11.0a8 extension to design section 4.4: encodes coverage-gap
    semantics. If source_sheet.source_field is set but its value is not
    in cond.known_values, emit one flag per occurrence.

    Silent on:
    - source_sheet missing from submission
    - source_field missing from source row
    - source_field value is None or empty string
    - source_field value IS in known_values

    The manifest case (source_sheet=='manifest') checks the manifest
    dict directly (single occurrence). For row-shaped sheets, each
    row is checked independently and emits its own flag if violating.

    Flag IDs include the observed unknown value so distinct unknowns
    in different rows produce distinct flag_ids (deterministic).
    """
    flags: list[CrossSheetFlag] = []

    source = submission.get(cond.source_sheet)
    if source is None:
        return flags

    known_set = set(cond.known_values)

    if isinstance(source, dict):
        # Manifest case: single occurrence check.
        # v1.18.0: use _extract_source_field_value to support dotted paths
        # like "rule_pack.id" for nested manifest objects.
        value = _extract_source_field_value(source, cond.source_field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return flags
        if str(value) in known_set:
            return flags
        # Unknown value -> flag
        flags.append(_make_not_in_known_set_flag(
            invariant=invariant, lp=lp, cond=cond,
            observed_value=str(value), join_key_values={},
        ))
        return flags

    # Row-shaped sheet: per-row check
    rows = _iter_rows(source)
    for row in rows:
        value = row.get(cond.source_field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if str(value) in known_set:
            continue
        # Unknown value on this row -> flag
        join_key_values = {k: row.get(k) for k in invariant.join_keys}
        join_key_values = {k: v for k, v in join_key_values.items() if v is not None}
        flags.append(_make_not_in_known_set_flag(
            invariant=invariant, lp=lp, cond=cond,
            observed_value=str(value), join_key_values=join_key_values,
        ))

    return flags


def _make_not_in_known_set_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    cond: CategoricalNotInKnownSetCondition,
    observed_value: str,
    join_key_values: dict[str, Any],
) -> CrossSheetFlag:
    """Emit a not-in-known-set coverage-gap flag."""
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "categorical_not_in_known_set",
        "source_sheet": cond.source_sheet,
        "source_field": cond.source_field,
        "observed_value": observed_value,
        "known_values": sorted(cond.known_values),
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
        observed_value=None,
        declared_tool=observed_value,
        flag_reason=(
            f"{cond.source_sheet}.{cond.source_field}={observed_value!r} is "
            f"not in the known taxonomy of this pack "
            f"({sorted(cond.known_values)}). The audit cannot validate "
            f"submissions declaring this value against vendor-specific "
            f"normative ranges; reviewer should verify the declaration."
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


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


def _cmp(value: float, threshold: float, direction: str) -> bool:
    """Return True if `value <direction> threshold`."""
    if direction == "ge":
        return value >= threshold
    if direction == "gt":
        return value > threshold
    if direction == "le":
        return value <= threshold
    if direction == "lt":
        return value < threshold
    raise ValueError(f"unknown direction {direction!r}")


def _evaluate_numeric_conflict(
    invariant: CrossSheetInvariant,
    cond: NumericConflictCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a numeric_conflict condition.

    For each row joined across source/target sheets on invariant.join_keys,
    if BOTH the source and target numeric conditions trip, the pair is
    biomarker-discordant and a flag is emitted.
    """
    flags: list[CrossSheetFlag] = []

    source_rows = _iter_rows(submission.get(cond.source_sheet))
    target_rows = _iter_rows(submission.get(cond.target_sheet))
    if not source_rows or not target_rows:
        return flags

    join_keys = invariant.join_keys or ["patient_id"]

    # Index target rows by join-key tuple for alignment.
    def _key(row: dict[str, Any]) -> tuple:
        return tuple(str(row.get(k)) for k in join_keys)

    target_index: dict[tuple, list[dict[str, Any]]] = {}
    for trow in target_rows:
        target_index.setdefault(_key(trow), []).append(trow)

    # Wide-into-long fan-out guard: when a wide source row joins a long target
    # (many rows per join key, e.g. CDISC --TESTCD long format), the same
    # genuine conflict would otherwise be emitted once per target row -- N
    # byte-identical copies. Dedup on (join-key tuple, source value, target
    # value) so each distinct conflict is reported once, at the granularity the
    # invariant declares via its join_keys. A genuinely different conflict (a
    # different join key or different values) is preserved.
    seen: set[tuple] = set()

    for srow in source_rows:
        s_raw = srow.get(cond.source_field)
        if s_raw is None:
            continue
        try:
            s_val = float(s_raw)
        except (TypeError, ValueError):
            continue
        if not _cmp(s_val, cond.source_threshold, cond.source_direction):
            continue  # source side not tripped

        for trow in target_index.get(_key(srow), []):
            t_raw = trow.get(cond.target_field)
            if t_raw is None:
                continue
            try:
                t_val = float(t_raw)
            except (TypeError, ValueError):
                continue
            if not _cmp(t_val, cond.target_threshold, cond.target_direction):
                continue  # target side not tripped -> no conflict

            dedup_key = (_key(srow), s_val, t_val)
            if dedup_key in seen:
                continue  # identical conflict already emitted (fan-out copy)
            seen.add(dedup_key)

            join_key_values = {k: srow.get(k) for k in join_keys if k in srow}
            flags.append(
                _make_numeric_conflict_flag(
                    invariant=invariant, lp=lp,
                    source_val=s_val, target_val=t_val,
                    join_key_values=join_key_values, cond=cond,
                )
            )
    return flags


def _evaluate_trajectory_monotonicity(
    invariant: CrossSheetInvariant,
    cond: TrajectoryMonotonicityCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a trajectory_monotonicity condition.

    Groups the series sheet by patient_key, sorts by order_field, and
    checks the value_field series for the required monotonic direction
    within tolerance. Treatment-gated steps are exempt.
    """
    flags: list[CrossSheetFlag] = []
    rows = _iter_rows(submission.get(cond.series_sheet))
    if not rows:
        return flags

    # group by patient
    by_patient: dict[Any, list[dict[str, Any]]] = {}
    for r in rows:
        pid = r.get(cond.patient_key)
        if pid is None:
            continue
        by_patient.setdefault(pid, []).append(r)

    for pid, prows in by_patient.items():
        # need order + value present
        usable = []
        for r in prows:
            o = r.get(cond.order_field)
            v = r.get(cond.value_field)
            if o is None or v is None:
                continue
            try:
                vv = float(v)
            except (TypeError, ValueError):
                continue
            usable.append((o, vv, r))
        if len(usable) < cond.min_visits:
            continue
        # sort by order_field (works for ints and ISO date strings)
        try:
            usable.sort(key=lambda t: t[0])
        except TypeError:
            usable.sort(key=lambda t: str(t[0]))

        for i in range(1, len(usable)):
            (_o_prev, v_prev, _r_prev) = usable[i - 1]
            (o_cur, v_cur, r_cur) = usable[i]
            delta = v_cur - v_prev
            violated = False
            if cond.direction == "non_increasing" and delta > cond.tolerance:
                violated = True
            elif cond.direction == "non_decreasing" and -delta > cond.tolerance:
                violated = True
            if not violated:
                continue
            # treatment gate: exempt if treatment truthy at the current visit
            if cond.treatment_gate_field is not None:
                gate = r_cur.get(cond.treatment_gate_field)
                if _is_truthy(gate):
                    continue
            join_key_values = {cond.patient_key: pid, cond.order_field: o_cur}
            flags.append(
                _make_monotonicity_flag(
                    invariant=invariant, lp=lp,
                    v_prev=v_prev, v_cur=v_cur, delta=delta,
                    join_key_values=join_key_values, cond=cond,
                )
            )
    return flags


def _is_truthy(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    return s not in ("", "0", "false", "none", "nan", "no")


def _make_numeric_conflict_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    source_val: float,
    target_val: float,
    join_key_values: dict[str, Any],
    cond: NumericConflictCondition,
) -> CrossSheetFlag:
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "numeric_conflict_violation",
        "source_field": cond.source_field,
        "source_val": float(source_val),
        "target_field": cond.target_field,
        "target_val": float(target_val),
        "join_key_values": _stringify_for_hash(join_key_values),
        "contract_version": "1.2.0",
    }
    return CrossSheetFlag(
        flag_id=_derive_flag_id(payload),
        pack_id=lp.invariantpack.invariantpack_id,
        invariant_name=invariant.name,
        severity=invariant.flag_severity,
        join_key_values=dict(join_key_values),
        observed_value=source_val,
        declared_tool=None,
        flag_reason=(
            f"biomarker discordance: {cond.source_field}={source_val} "
            f"({cond.source_direction} {cond.source_threshold}) WITH "
            f"{cond.target_field}={target_val} "
            f"({cond.target_direction} {cond.target_threshold})"
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _evaluate_rowwise_conjunction_advisory(
    invariant: CrossSheetInvariant,
    cond: RowwiseConjunctionAdvisoryCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Flag each row of cond.sheet where ALL predicates hold (logical AND).

    A row is evaluated only if every predicate's field is present and, for
    numeric predicates, coercible to float. Missing/uncoercible -> the row is
    skipped (the conjunction cannot be established), never flagged on a guess.
    """
    flags: list[CrossSheetFlag] = []
    rows = _iter_rows(submission.get(cond.sheet))
    if not rows:
        return flags

    join_keys = invariant.join_keys or ["patient_id"]

    for row in rows:
        all_hold = True
        for pred in cond.predicates:
            if pred.field not in row or row.get(pred.field) is None:
                all_hold = False
                break
            raw = row.get(pred.field)
            if pred.operator in ("eq", "ne"):
                hit = str(raw) == str(pred.value)
                if pred.operator == "ne":
                    hit = not hit
                if not hit:
                    all_hold = False
                    break
            else:  # numeric
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    all_hold = False
                    break
                if not _cmp(val, float(pred.threshold), pred.operator):
                    all_hold = False
                    break
        if all_hold:
            join_key_values = {k: row.get(k) for k in join_keys if k in row}
            flags.append(
                _make_rowwise_conjunction_flag(
                    invariant=invariant, lp=lp, cond=cond,
                    join_key_values=join_key_values, row=row,
                )
            )
    return flags


def _make_rowwise_conjunction_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    cond: RowwiseConjunctionAdvisoryCondition,
    join_key_values: dict[str, Any],
    row: dict[str, Any],
) -> CrossSheetFlag:
    observed = {p.field: row.get(p.field) for p in cond.predicates}
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "rowwise_conjunction_advisory",
        "sheet": cond.sheet,
        "predicates": [
            {"field": p.field, "operator": p.operator,
             "value": p.value, "threshold": p.threshold}
            for p in cond.predicates
        ],
        "observed": _stringify_for_hash(observed),
        "join_key_values": _stringify_for_hash(join_key_values),
        "contract_version": "1.2.0",
    }
    cond_str = " AND ".join(
        f"{p.field} {p.operator} "
        f"{p.value if p.value is not None else p.threshold}"
        for p in cond.predicates
    )
    return CrossSheetFlag(
        flag_id=_derive_flag_id(payload),
        pack_id=lp.invariantpack.invariantpack_id,
        invariant_name=invariant.name,
        severity=invariant.flag_severity,
        join_key_values=dict(join_key_values),
        observed_value=None,
        declared_tool=None,
        flag_reason=f"{cond.advisory_message} (matched: {cond_str})",
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _make_monotonicity_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    v_prev: float,
    v_cur: float,
    delta: float,
    join_key_values: dict[str, Any],
    cond: TrajectoryMonotonicityCondition,
) -> CrossSheetFlag:
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "trajectory_monotonicity_violation",
        "value_field": cond.value_field,
        "direction": cond.direction,
        "v_prev": float(v_prev),
        "v_cur": float(v_cur),
        "delta": float(delta),
        "join_key_values": _stringify_for_hash(join_key_values),
        "contract_version": "1.2.0",
    }
    return CrossSheetFlag(
        flag_id=_derive_flag_id(payload),
        pack_id=lp.invariantpack.invariantpack_id,
        invariant_name=invariant.name,
        severity=invariant.flag_severity,
        join_key_values=dict(join_key_values),
        observed_value=v_cur,
        flag_reason=(
            f"{cond.value_field} violated {cond.direction}: "
            f"{v_prev} -> {v_cur} (delta {delta:+.4g}, tol {cond.tolerance})"
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )


def _evaluate_categorical_implies_range_rowwise(
    invariant: CrossSheetInvariant,
    cond: CategoricalImpliesRangeRowwiseCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Per-row categorical->range concordance within one sheet (E014).

    For each row: if row[source_field] == source_value, then
    row[target_field] must be within target_range, else flag the row.
    """
    flags: list[CrossSheetFlag] = []
    for row in _iter_rows(submission.get(cond.sheet)):
        cat = row.get(cond.source_field)
        if cat is None or str(cat) != cond.source_value:
            continue  # trigger not met for this row
        obs = row.get(cond.target_field)
        if obs is None:
            continue
        try:
            obs_num = float(obs)
        except (TypeError, ValueError):
            continue
        if obs_num < cond.target_range.lo or obs_num > cond.target_range.hi:
            join_key_values = {k: row.get(k) for k in (invariant.join_keys or ["patient_id"]) if k in row}
            payload = {
                "yaml_sha256": lp.yaml_sha256,
                "invariant_name": invariant.name,
                "kind": "categorical_implies_range_rowwise_violation",
                "source_field": cond.source_field,
                "source_value": cond.source_value,
                "target_field": cond.target_field,
                "observed": float(obs_num),
                "lo": float(cond.target_range.lo),
                "hi": float(cond.target_range.hi),
                "join_key_values": _stringify_for_hash(join_key_values),
                "contract_version": "1.2.0",
            }
            flags.append(CrossSheetFlag(
                flag_id=_derive_flag_id(payload),
                pack_id=lp.invariantpack.invariantpack_id,
                invariant_name=invariant.name,
                severity=invariant.flag_severity,
                join_key_values=dict(join_key_values),
                observed_value=obs_num,
                expected_range_lo=cond.target_range.lo,
                expected_range_hi=cond.target_range.hi,
                declared_tool=str(cat),
                flag_reason=(
                    f"{cond.source_field}={cond.source_value!r} requires "
                    f"{cond.target_field} in [{cond.target_range.lo}, {cond.target_range.hi}], "
                    f"observed {obs_num}"
                ),
                citation_pmid=invariant.citation.citation_pmid,
                citation_doi=invariant.citation.citation_doi,
                citation_public_url=invariant.citation.public_url,
            ))
    return flags


def _evaluate_referential_integrity(
    invariant: CrossSheetInvariant,
    cond: ReferentialIntegrityCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Flag child rows whose child_field value is absent from the parent
    sheet's parent_field values (orphan records, E022)."""
    flags: list[CrossSheetFlag] = []
    parent_rows = _iter_rows(submission.get(cond.parent_sheet))
    child_rows = _iter_rows(submission.get(cond.child_sheet))
    if not child_rows:
        return flags
    parent_ids = {
        str(r.get(cond.parent_field))
        for r in parent_rows
        if r.get(cond.parent_field) is not None
    }
    seen_orphans: set[str] = set()
    for row in child_rows:
        cid = row.get(cond.child_field)
        if cid is None:
            continue
        cid_s = str(cid)
        if cid_s in parent_ids or cid_s in seen_orphans:
            continue
        seen_orphans.add(cid_s)
        payload = {
            "yaml_sha256": lp.yaml_sha256,
            "invariant_name": invariant.name,
            "kind": "referential_integrity_violation",
            "child_sheet": cond.child_sheet,
            "child_field": cond.child_field,
            "orphan_value": cid_s,
            "parent_sheet": cond.parent_sheet,
            "parent_field": cond.parent_field,
            "contract_version": "1.2.0",
        }
        flags.append(CrossSheetFlag(
            flag_id=_derive_flag_id(payload),
            pack_id=lp.invariantpack.invariantpack_id,
            invariant_name=invariant.name,
            severity=invariant.flag_severity,
            join_key_values={cond.child_field: cid_s},
            flag_reason=(
                f"orphan record: {cond.child_sheet}.{cond.child_field}="
                f"{cid_s!r} has no matching {cond.parent_sheet}.{cond.parent_field}"
            ),
            citation_pmid=invariant.citation.citation_pmid,
            citation_doi=invariant.citation.citation_doi,
            citation_public_url=invariant.citation.public_url,
        ))
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


def _evaluate_subfield_rank_constraint(
    invariant: CrossSheetInvariant,
    cond: SubfieldRankConstraintCondition,
    submission: dict[str, Any],
    lp: LoadedInvariantPack,
) -> list[CrossSheetFlag]:
    """Evaluate a subfield_rank_constraint condition.

    For each row of cond.sheet in which every value_field is present and
    numeric, rank the value_fields by descending value (ties broken by
    field name ascending, so flag_id is reproducible). Each ENABLED rule
    asserts the rank of one field; violations emit a flag. Rows missing
    any value_field are skipped (missingness is an input-contract concern).
    """
    flags: list[CrossSheetFlag] = []

    rows = _iter_rows(submission.get(cond.sheet))
    if not rows:
        return flags

    enabled_rules = [r for r in cond.rules if r.enabled]
    if not enabled_rules:
        return flags

    join_keys = invariant.join_keys or ["patient_id"]

    for row in rows:
        vals: dict[str, float] = {}
        complete = True
        for fld in cond.value_fields:
            raw = row.get(fld)
            if raw is None or isinstance(raw, bool):
                complete = False
                break
            try:
                vals[fld] = float(raw)
            except (TypeError, ValueError):
                complete = False
                break
        if not complete:
            continue  # cannot rank a partial row; skip honestly

        # Deterministic ranking: largest first; ties broken by field name.
        ordered = sorted(cond.value_fields, key=lambda f: (-vals[f], f))
        rank_of = {fld: i + 1 for i, fld in enumerate(ordered)}

        for rule in enabled_rules:
            actual = rank_of[rule.field]
            if rule.operator == "eq":
                violated = actual != rule.rank
            elif rule.operator == "le":
                violated = actual > rule.rank
            else:  # "ge"
                violated = actual < rule.rank
            if violated:
                jkv = {k: row.get(k) for k in join_keys if k in row}
                flags.append(
                    _make_subfield_rank_flag(
                        invariant=invariant, lp=lp, cond=cond, rule=rule,
                        actual_rank=actual, field_value=vals[rule.field],
                        join_key_values=jkv,
                    )
                )
    return flags


def _make_subfield_rank_flag(
    invariant: CrossSheetInvariant,
    lp: LoadedInvariantPack,
    cond: SubfieldRankConstraintCondition,
    rule: Any,
    actual_rank: int,
    field_value: float,
    join_key_values: dict[str, Any],
) -> CrossSheetFlag:
    payload = {
        "yaml_sha256": lp.yaml_sha256,
        "invariant_name": invariant.name,
        "kind": "subfield_rank_violation",
        "sheet": cond.sheet,
        "field": rule.field,
        "operator": rule.operator,
        "expected_rank": int(rule.rank),
        "actual_rank": int(actual_rank),
        "join_key_values": _stringify_for_hash(join_key_values),
        "contract_version": "1.2.0",
    }
    op_word = {"eq": "==", "le": "<=", "ge": ">="}[rule.operator]
    return CrossSheetFlag(
        flag_id=_derive_flag_id(payload),
        pack_id=lp.invariantpack.invariantpack_id,
        invariant_name=invariant.name,
        severity=invariant.flag_severity,
        join_key_values=dict(join_key_values),
        observed_value=field_value,
        flag_reason=(
            f"subfield rank violation: {rule.field} ranked #{actual_rank} by "
            f"volume but rule requires rank {op_word} {rule.rank}"
        ),
        citation_pmid=invariant.citation.citation_pmid,
        citation_doi=invariant.citation.citation_doi,
        citation_public_url=invariant.citation.public_url,
    )

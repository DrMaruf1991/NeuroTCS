"""
neurotcs.clinical_ranges.audit — Layer 2 audit engine.

The single public entry point `audit_clinical_ranges(measurements_df, rangepack)`
takes a long-format DataFrame of clinical measurements and a loaded range pack
and emits a deterministic ClinicalRangeAuditResult:

  - n_measurements_checked  (total rows fed through the engine)
  - n_measurements_covered  (rows whose measurement_name is in the pack)
  - n_measurements_uncovered (rows the pack has no opinion about)
  - n_flagged               (rows that violated at least one bound)
  - flags                   (per-row flag details with citation)
  - flag_id                 (SHA-256 over rangepack_sha + canonical(flags))
  - rangepack provenance    (id, sha, version, status)

flag_id is the Layer 2 analogue of Layer 1's audit_id. Two runs of
audit_clinical_ranges() on byte-identical inputs with the same range pack
produce identical flag_ids — the canonical reproducibility signature.

The engine NEVER silently approves uncovered measurements: if a row's
measurement_name is not in the pack, it goes into the "uncovered" tally
and the result carries that count. Downstream consumers (and FDA reviewers)
can see exactly what was audited and what was passed through unchecked.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from neurotcs.clinical_ranges.loader import LoadedRangePack
from neurotcs.clinical_ranges.schema import (
    BoundType,
    evaluate_categorical_against_valid_set,
    evaluate_value_against_bounds,
)

# ============================================================
# Result types
# ============================================================

@dataclass(frozen=True)
class ClinicalRangeFlag:
    """One flagged measurement.

    Attributes:
        patient_id: The patient identifier from the row.
        visit_id: The visit identifier from the row (string, may be visit
            number, visit name, or date — the engine preserves whatever
            the adapter emitted).
        measurement_name: The canonical measurement name.
        observed_value: The value that failed.
        unit: The unit from the input row.
        bound_type: hard_min / hard_max / plausible_min / plausible_max
            or 'invalid_categorical' / 'unit_mismatch'.
        bound_value: The numeric bound that was violated (or None for
            categorical / unit mismatches).
        citation_pmid: PMID anchoring the bound.
        citation_doi: DOI anchoring the bound.
        citation_text: Verbatim or near-verbatim quote.
        guideline_section: Pointer into the cited document.
        flag_severity: 'hard' (physically/biologically impossible) or
            'plausible' (within physical limits but biologically implausible
            in the target population) or 'invalid_category' or 'unit_mismatch'.
    """
    patient_id: str
    visit_id: str
    measurement_name: str
    observed_value: float | str
    unit: str
    bound_type: str
    bound_value: float | None
    citation_pmid: str | None
    citation_doi: str | None
    citation_text: str
    guideline_section: str
    flag_severity: str
    bound_semantic: str = "diagnostic_threshold"

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "visit_id": self.visit_id,
            "measurement_name": self.measurement_name,
            "observed_value": self.observed_value,
            "unit": self.unit,
            "bound_type": self.bound_type,
            "bound_value": self.bound_value,
            "citation_pmid": self.citation_pmid,
            "citation_doi": self.citation_doi,
            "citation_text": self.citation_text,
            "guideline_section": self.guideline_section,
            "flag_severity": self.flag_severity,
            "bound_semantic": self.bound_semantic,
        }


@dataclass(frozen=True)
class ClinicalRangeAuditResult:
    """The result of one Layer 2 audit pass.

    Attributes match audit_core.AuditResult in shape so downstream consumers
    can stitch Layer 1 + Layer 2 results into one combined report.
    """
    rangepack_name: str
    rangepack_id: str
    rangepack_sha256: str
    rangepack_schema_version: str
    rangepack_pack_version: str
    n_measurements_checked: int
    n_measurements_covered: int
    n_measurements_uncovered: int
    uncovered_measurement_names: tuple[str, ...]
    n_flagged: int
    flags: tuple[ClinicalRangeFlag, ...]
    flag_id: str
    timestamp_utc: str
    layer: str = "Layer 2 (clinical_ranges)"

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "rangepack_name": self.rangepack_name,
            "rangepack_id": self.rangepack_id,
            "rangepack_sha256": self.rangepack_sha256,
            "rangepack_schema_version": self.rangepack_schema_version,
            "rangepack_pack_version": self.rangepack_pack_version,
            "n_measurements_checked": self.n_measurements_checked,
            "n_measurements_covered": self.n_measurements_covered,
            "n_measurements_uncovered": self.n_measurements_uncovered,
            "uncovered_measurement_names": list(self.uncovered_measurement_names),
            "n_flagged": self.n_flagged,
            "flag_id": self.flag_id,
            "timestamp_utc": self.timestamp_utc,
            "flags": [f.to_dict() for f in self.flags],
        }


# ============================================================
# Adapter-side schema for the input DataFrame
# ============================================================

REQUIRED_COLUMNS: tuple[str, ...] = (
    "patient_id",
    "visit_id",
    "measurement_name",
    "value",
    "unit",
)


def _validate_input_dataframe(df: pd.DataFrame) -> None:
    """Strict structural validation of the long-format measurements DataFrame."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"audit_clinical_ranges: input DataFrame missing required column(s): "
            f"{missing}. Expected long-format with columns {list(REQUIRED_COLUMNS)}."
        )


# ============================================================
# The audit
# ============================================================

def audit_clinical_ranges(
    measurements_df: pd.DataFrame,
    rangepack: LoadedRangePack,
    *,
    drop_nan_values: bool = True,
) -> ClinicalRangeAuditResult:
    """Run Layer 2 clinical-range validation on a measurements DataFrame.

    Args:
        measurements_df: Long-format DataFrame with columns
            {patient_id, visit_id, measurement_name, value, unit}.
            One row per (patient, visit, measurement).
        rangepack: A LoadedRangePack with status=production.
        drop_nan_values: If True (default), rows with NaN `value` are
            silently dropped (they cannot be checked against bounds).
            Set False to raise on NaN.

    Returns:
        ClinicalRangeAuditResult with deterministic flag_id.

    The flag_id is computed as SHA-256 over a canonical JSON document
    that contains:
      - rangepack_sha256
      - sorted list of (patient_id, visit_id, measurement_name) keys
        that produced flags
      - per-key list of bound_types violated
    This makes flag_id sensitive to which measurements were flagged and
    why, but stable across re-orderings of the input DataFrame.
    """
    rangepack.assert_usable_for_audit()
    _validate_input_dataframe(measurements_df)

    df = measurements_df.copy()
    if drop_nan_values:
        df = df.dropna(subset=["value", "measurement_name", "patient_id"])
    else:
        if df["value"].isna().any() or df["measurement_name"].isna().any():
            raise ValueError(
                "audit_clinical_ranges: NaN values present and drop_nan_values=False. "
                "Either pre-filter, or set drop_nan_values=True."
            )

    n_checked = len(df)

    covered_names = rangepack.rangepack.covered_names()
    df_covered = df[df["measurement_name"].isin(covered_names)]
    df_uncovered = df[~df["measurement_name"].isin(covered_names)]

    n_covered = len(df_covered)
    n_uncovered = len(df_uncovered)
    uncovered_names = tuple(sorted(set(df_uncovered["measurement_name"].astype(str).tolist())))

    flags: list[ClinicalRangeFlag] = []

    for _, row in df_covered.iterrows():
        name = str(row["measurement_name"])
        measurement = rangepack.rangepack.get_measurement(name)
        if measurement is None:  # belt-and-braces; covered_names ensured this
            continue

        pid = str(row["patient_id"])
        vid = str(row["visit_id"])
        raw_value = row["value"]
        observed_unit = str(row.get("unit", ""))

        # Unit consistency check (fail-fast on declared-vs-expected unit mismatch)
        if observed_unit and observed_unit != measurement.unit:
            flags.append(ClinicalRangeFlag(
                patient_id=pid,
                visit_id=vid,
                measurement_name=name,
                observed_value=raw_value if not isinstance(raw_value, str) else str(raw_value),
                unit=observed_unit,
                bound_type="unit_mismatch",
                bound_value=None,
                citation_pmid=rangepack.rangepack.anchor_citation.citation_pmid,
                citation_doi=rangepack.rangepack.anchor_citation.citation_doi,
                citation_text=(
                    f"Unit mismatch: pack expects {measurement.unit!r} but row "
                    f"declared {observed_unit!r}."
                ),
                guideline_section=f"{rangepack.rangepack.rangepack_id} unit declaration",
                flag_severity="unit_mismatch",
            ))
            continue  # Don't compare values across incompatible units

        if measurement.measurement_kind == "categorical_set":
            value_str = str(raw_value)
            valid = measurement.valid_values or []
            if not evaluate_categorical_against_valid_set(value_str, valid):
                flags.append(ClinicalRangeFlag(
                    patient_id=pid,
                    visit_id=vid,
                    measurement_name=name,
                    observed_value=value_str,
                    unit=measurement.unit,
                    bound_type="invalid_categorical",
                    bound_value=None,
                    citation_pmid=measurement.bounds[0].citation.citation_pmid,
                    citation_doi=measurement.bounds[0].citation.citation_doi,
                    citation_text=measurement.bounds[0].citation.citation_text,
                    guideline_section=measurement.bounds[0].guideline_section,
                    flag_severity="invalid_category",
                ))
            continue

        # Numeric path
        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            # Non-numeric on a numeric measurement is itself a flag.
            flags.append(ClinicalRangeFlag(
                patient_id=pid,
                visit_id=vid,
                measurement_name=name,
                observed_value=str(raw_value),
                unit=observed_unit or measurement.unit,
                bound_type="non_numeric",
                bound_value=None,
                citation_pmid=rangepack.rangepack.anchor_citation.citation_pmid,
                citation_doi=rangepack.rangepack.anchor_citation.citation_doi,
                citation_text=(
                    f"Measurement {name!r} is declared numeric in the pack but "
                    f"observed value {raw_value!r} is non-numeric."
                ),
                guideline_section=f"{rangepack.rangepack.rangepack_id} measurement schema",
                flag_severity="non_numeric",
            ))
            continue

        ok, violations = evaluate_value_against_bounds(value, measurement.bounds)
        if not ok:
            for bound_type, bound in violations:
                flags.append(ClinicalRangeFlag(
                    patient_id=pid,
                    visit_id=vid,
                    measurement_name=name,
                    observed_value=value,
                    unit=measurement.unit,
                    bound_type=bound_type.value,
                    bound_value=bound.value,
                    citation_pmid=bound.citation.citation_pmid,
                    citation_doi=bound.citation.citation_doi,
                    citation_text=bound.citation.citation_text,
                    guideline_section=bound.guideline_section,
                    flag_severity=(
                        "hard" if bound_type in (BoundType.HARD_MIN, BoundType.HARD_MAX)
                        else "plausible"
                    ),
                    bound_semantic=getattr(bound, "bound_semantic", "diagnostic_threshold"),
                ))

    n_flagged = len(flags)

    # Stable flag_id over the canonical signature of the result.
    # Sort by (patient_id, visit_id, measurement_name, bound_type) so two
    # runs over the same underlying measurements produce the same flag_id
    # regardless of input row ordering.
    canonical_flags = sorted(
        [
            (f.patient_id, f.visit_id, f.measurement_name, f.bound_type)
            for f in flags
        ]
    )
    canonical = json.dumps(
        {
            "rangepack_sha256": rangepack.canonical_sha256,
            "rangepack_id": rangepack.rangepack.rangepack_id,
            "n_checked": n_checked,
            "n_covered": n_covered,
            "n_flagged": n_flagged,
            "canonical_flags": canonical_flags,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    flag_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return ClinicalRangeAuditResult(
        rangepack_name=rangepack.name,
        rangepack_id=rangepack.rangepack.rangepack_id,
        rangepack_sha256=rangepack.canonical_sha256,
        rangepack_schema_version=rangepack.rangepack.schema_version,
        rangepack_pack_version=rangepack.rangepack.pack_version,
        n_measurements_checked=n_checked,
        n_measurements_covered=n_covered,
        n_measurements_uncovered=n_uncovered,
        uncovered_measurement_names=uncovered_names,
        n_flagged=n_flagged,
        flags=tuple(flags),
        flag_id=flag_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


# ============================================================
# Multi-pack convenience
# ============================================================

@dataclass(frozen=True)
class MultiPackResult:
    """Aggregate result of running a measurements DataFrame through multiple
    range packs (one per measurement domain).

    Each per-pack result keeps its own flag_id; a combined_flag_id is also
    computed for citing the entire Layer-2 pass in one ID.
    """
    per_pack: tuple[ClinicalRangeAuditResult, ...]
    combined_flag_id: str

    @property
    def total_flagged(self) -> int:
        return sum(r.n_flagged for r in self.per_pack)

    @property
    def total_checked(self) -> int:
        # Each measurement is checked by exactly one pack (the one that
        # covers its measurement_name). So total is the sum, NOT the sum
        # of per-pack covered counts.
        return sum(r.n_measurements_covered for r in self.per_pack)

    def all_flags(self) -> list[ClinicalRangeFlag]:
        out: list[ClinicalRangeFlag] = []
        for r in self.per_pack:
            out.extend(r.flags)
        return out


def audit_clinical_ranges_multi(
    measurements_df: pd.DataFrame,
    rangepacks: list[LoadedRangePack],
    *,
    drop_nan_values: bool = True,
) -> MultiPackResult:
    """Run Layer 2 across multiple range packs.

    Each measurement row is checked against the FIRST pack in `rangepacks`
    that covers its measurement_name. Rows whose measurement is not covered
    by any pack land in each pack's uncovered tally (deduplicated at the
    combined-result level).

    Returns a MultiPackResult with per-pack flag_ids and a combined_flag_id.
    """
    _validate_input_dataframe(measurements_df)

    # Build a lookup: measurement_name -> rangepack
    name_to_pack: dict[str, LoadedRangePack] = {}
    for rp in rangepacks:
        for name in rp.rangepack.covered_names():
            if name in name_to_pack:
                raise ValueError(
                    f"Measurement {name!r} is covered by both "
                    f"{name_to_pack[name].name!r} and {rp.name!r}. "
                    f"Range packs in one audit must be disjoint."
                )
            name_to_pack[name] = rp

    per_pack_results: list[ClinicalRangeAuditResult] = []
    for rp in rangepacks:
        # Slice the input DataFrame to rows the pack covers
        pack_covered_mask = measurements_df["measurement_name"].isin(rp.rangepack.covered_names())
        df_for_pack = measurements_df[pack_covered_mask]
        result = audit_clinical_ranges(df_for_pack, rp, drop_nan_values=drop_nan_values)
        per_pack_results.append(result)

    canonical = json.dumps(
        {
            "per_pack_flag_ids": sorted([r.flag_id for r in per_pack_results]),
            "n_packs": len(per_pack_results),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    combined = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return MultiPackResult(
        per_pack=tuple(per_pack_results),
        combined_flag_id=combined,
    )

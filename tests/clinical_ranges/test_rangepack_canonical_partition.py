"""Two-directional proof for RangePack.canonical_sha256 scientific partition.

The rangepack canonical_sha256 (which feeds every flag_id) must hash ONLY the
citation-locked scientific record -- rangepack_id, anchor_citation, measurements
-- and must EXCLUDE descriptive/lifecycle header metadata (framework_name,
transcribed_by, clinical_source_authority, notes, status, domain, dates,
versions, deprecation fields).

This is the rangepack analogue of tests/rulepack/test_canonical_serialization_
partition.py (ERRATA E-2026-006), closing the same metadata-in-hash defect for
rangepacks (ERRATA E-2026-007). The keep-set differs because rangepack citations
live per-bound and are emitted into flags, and the spec defines citation-locking
as part of the regulated reproducible record (temporalmetric v1.7 spec L239).
"""
from __future__ import annotations

import hashlib
import json

from neurotcs.clinical_ranges.loader import load_rangepack
from neurotcs.clinical_ranges.schema import (
    _RANGEPACK_SCIENTIFIC_FIELDS,
    RangePack,
)

_PACK = "ad/aria_safety"

# Every top-level RangePack field, partitioned by expectation.
_METADATA_FIELDS = (
    "schema_version", "pack_version", "effective_date", "status", "domain",
    "framework_name", "transcribed_by", "clinical_source_authority", "notes",
    "deprecated_in_favor_of", "deprecation_reason",
)


def _rp() -> RangePack:
    return load_rangepack(_PACK).rangepack


def test_partition_covers_all_top_level_fields():
    """Keep-set + metadata-set must equal the full RangePack field set, with no
    overlap and nothing forgotten (guards against a new field silently landing
    in neither bucket)."""
    model_fields = set(RangePack.model_fields.keys())
    keep = set(_RANGEPACK_SCIENTIFIC_FIELDS)
    meta = set(_METADATA_FIELDS)
    assert keep & meta == set(), f"overlap: {keep & meta}"
    assert keep | meta == model_fields, (
        f"unpartitioned fields: {model_fields - (keep | meta)}; "
        f"unknown in partition: {(keep | meta) - model_fields}"
    )


def test_metadata_changes_do_NOT_drift_hash():
    """Editing any descriptive/lifecycle header field must NOT change the hash."""
    rp = _rp()
    base = rp.canonical_sha256()
    samples = {
        "framework_name": "Totally different framework description text",
        "transcribed_by": "Someone Else, MD, 2099-01-01",
        "clinical_source_authority": "Rewritten authority prose for the test.",
        "notes": "an added note",
        "domain": "different_domain",
    }
    for field, val in samples.items():
        mutated = rp.model_copy(update={field: val})
        assert mutated.canonical_sha256() == base, (
            f"changing metadata field {field!r} drifted the hash -- it must not"
        )


def test_scientific_changes_DO_drift_hash():
    """Changing a bound value OR a bound citation must change the hash."""
    rp = _rp()
    base = rp.canonical_sha256()

    # (a) bound value
    d = rp.model_dump()
    for m in d["measurements"]:
        for b in m.get("bounds", []):
            if b.get("value") is not None:
                b["value"] = float(b["value"]) + 999.0
                break
        else:
            continue
        break
    assert RangePack(**d).canonical_sha256() != base, "value change must drift hash"

    # (b) bound citation pmid (citation-locked record)
    d2 = rp.model_dump()
    touched = False
    for m in d2["measurements"]:
        for b in m.get("bounds", []):
            cit = b.get("citation")
            if isinstance(cit, dict):
                cit["citation_pmid"] = "99999999"
                touched = True
                break
        if touched:
            break
    if touched:
        assert RangePack(**d2).canonical_sha256() != base, (
            "citation change must drift hash (citation-locked record)"
        )


def test_production_helper_matches_method():
    """The dict-comprehension partition equals what the production method hashes
    (no divergence between proof and production)."""
    rp = _rp()
    dump = rp.model_dump(mode="json")
    scientific = {k: dump[k] for k in _RANGEPACK_SCIENTIFIC_FIELDS if k in dump}
    canonical = json.dumps(scientific, sort_keys=True, separators=(",", ":"), default=str)
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert rp.canonical_sha256() == expected

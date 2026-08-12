"""Two-directional proof of the audit_id scientific/metadata partition (v1.20.0).

Contract (ERRATA E-2026-006):
  audit_id depends on, and ONLY on, the rule-pack fields the scoring engine
  reads. Therefore:
    - Mutating any METADATA field MUST NOT change the canonical SHA.
    - Mutating any SCIENTIFIC field MUST change the canonical SHA.

Strategy: serialize the model_dump dict directly using the SAME canonical
JSON rules as loader._canonical_serialize, restricted to _SCIENTIFIC_FIELDS.
This tests the partition without forcing full RulePack re-validation (which
would reject otherwise-valid mutations due to unrelated field constraints
like schema_version max_length). The serialization rules mirror the
production function exactly.
"""
from __future__ import annotations

import copy
import json

from neurotcs.rulepack.loader import (
    _SCIENTIFIC_FIELDS,
    _canonical_serialize,
    load_rulepack,
)

METADATA_FIELDS = (
    "schema_version",
    "rulepack_id",
    "ruleset_version",
    "effective_date",
    "status",
    "disease_domain",
    "framework_name",
    "transcribed_by",
    "clinical_source_authority",
    "reviewers",
    "endorsing_bodies",
    "source_author_affiliations",
    "anchor_citation",
    "notes",
    "override_allowed_default",
)


def _serialize_dump(dump: dict) -> bytes:
    """Mirror loader._canonical_serialize but operate on a dump dict directly.

    Must stay byte-identical to the production logic: same field restriction,
    same nested provenance stripping (schema v1.5.0 inadmissible attribution
    fields, ERRATA E-2026-011), same json.dumps parameters.
    """
    scientific = {
        k: copy.deepcopy(dump[k]) for k in _SCIENTIFIC_FIELDS if k in dump
    }
    for entry in scientific.get("inadmissible_transitions", []):
        if isinstance(entry, dict):  # _mutate may append a sentinel string
            entry.pop("attribution_type", None)
            entry.pop("inference_rationale", None)
    return json.dumps(
        scientific, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _mutate(dump: dict, field):
    d = copy.deepcopy(dump)
    v = d.get(field)
    if isinstance(v, bool):
        d[field] = not v
    elif isinstance(v, str):
        # constraint-safe: prepend Z, keep length <= original+1 by trimming if needed
        d[field] = ("Z" + v)[:16] if field == "schema_version" else "Z" + v
    elif isinstance(v, list):
        d[field] = list(v) + ["__SENTINEL__"]
    elif isinstance(v, dict):
        d[field] = {**v, "__sentinel__": "x"}
    elif v is None:
        d[field] = "__FROM_NONE__"
    elif isinstance(v, (int, float)):
        d[field] = v + 1
    else:
        d[field] = "__FALLBACK__"
    return d


def test_production_function_matches_helper():
    """The dict-level helper must produce byte-identical output to the real
    _canonical_serialize on the unmutated pack -- otherwise the proof below is
    testing the wrong thing."""
    pack = load_rulepack("ad/niaaa_2018")
    dump = pack.rulepack.model_dump(mode="json")
    assert _serialize_dump(dump) == _canonical_serialize(pack.rulepack), (
        "Helper diverged from production _canonical_serialize -- proof invalid."
    )


def test_partition_covers_all_fields():
    pack = load_rulepack("ad/niaaa_2018")
    all_fields = set(pack.rulepack.model_dump(mode="json").keys())
    declared = set(_SCIENTIFIC_FIELDS) | set(METADATA_FIELDS)
    missing = all_fields - declared
    extra = declared - all_fields
    assert not missing, f"Unclassified fields in model: {sorted(missing)}"
    assert not extra, f"Declared fields not in model: {sorted(extra)}"
    assert not (set(_SCIENTIFIC_FIELDS) & set(METADATA_FIELDS)), "overlap!"


def test_metadata_changes_do_not_drift_sha():
    """Direction 1: mutating ANY metadata field must NOT change the SHA."""
    pack = load_rulepack("ad/niaaa_2018")
    base_dump = pack.rulepack.model_dump(mode="json")
    base_sha = _serialize_dump(base_dump)
    for field in METADATA_FIELDS:
        sha = _serialize_dump(_mutate(base_dump, field))
        assert sha == base_sha, (
            f"METADATA field {field!r} changed the canonical SHA -- "
            f"it is leaking into audit_id. Partition is wrong."
        )


def test_scientific_changes_do_drift_sha():
    """Direction 2: mutating ANY scientific field MUST change the SHA."""
    pack = load_rulepack("ad/niaaa_2018")
    base_dump = pack.rulepack.model_dump(mode="json")
    base_sha = _serialize_dump(base_dump)
    for field in _SCIENTIFIC_FIELDS:
        sha = _serialize_dump(_mutate(base_dump, field))
        assert sha != base_sha, (
            f"SCIENTIFIC field {field!r} did NOT change the canonical SHA -- "
            f"a real rule change would be invisible to audit_id. Partition is wrong."
        )

"""v1.83.0 -- visit is OPTIONAL in scaffolding (defects 2 & 3).

Defect 2 (emit self-rejection): describe --emit-mapping emitted <FILL:visit> for the
now-optional visit field, which the audit validator then refused -- the tool rejected
its own output.
Defect 3 (auto-detect bailout): a clean subject/date/state file (no visit column)
scaffolded a mapping with a blocking <FILL:visit>, so zero-config auto-detect gave up.

Both share one root: optional fields (visit, visit_date) were emitted as required
<FILL:> placeholders. Fix: only required fields (sheet, subject_id, state) get a
<FILL:> on miss; optional fields get null (the audit path derives them).
"""
from __future__ import annotations

import pandas as pd

from neurotcs.cli import (
    _has_placeholder,
    _optional_null,
    _required_fill,
    _scaffold_mapping,
)
from neurotcs.io import describe_tables


# ----- defect 3: clean subject/date/state file auto-detects COMPLETE ---------- #
def test_no_visit_column_scaffolds_complete_no_blocking_fill():
    """A file with subject_id + visit_date + state but NO visit column must
    scaffold a COMPLETE mapping (visit=null, not <FILL:visit>) so auto-detect
    succeeds instead of bailing out."""
    tables = {
        "AUDIT_CLINICAL": pd.DataFrame({
            "subject_id": ["S1", "S1", "S2"],
            "visit_date": ["2020-01-01", "2021-01-01", "2020-06-01"],
            "diagnosis": ["CN", "MCI", "CN"],
            # NO visit column
        }),
    }
    spec = _scaffold_mapping(describe_tables(tables))["clinical"]
    assert spec["subject_id"] == "subject_id"
    assert spec["state"] == "diagnosis"
    assert spec["visit_date"] == "visit_date"
    # visit not detected -> null, NOT a blocking placeholder
    assert spec["visit"] is None
    # the whole mapping must have NO placeholder (auto-detect would succeed)
    assert not _has_placeholder({"clinical": spec})


# ----- defect 2: emitted mapping does not self-reject ------------------------- #
def test_emitted_mapping_for_no_visit_file_passes_placeholder_gate():
    """The mapping scaffolded for a no-visit file must pass _has_placeholder
    (the gate that previously rejected the tool's own emit output)."""
    tables = {
        "cdr": pd.DataFrame({
            "subject_id": ["B1", "B1", "B2"],
            "visit_date": ["2000-01-01", "2001-01-01", "2000-06-01"],
            "clinical_stage": ["CN", "MCI", "CN"],
        }),
    }
    mapping = _scaffold_mapping(describe_tables(tables))
    # clinical detected, no placeholder -> audit path would accept it
    assert "clinical" in mapping
    assert not _has_placeholder({k: v for k, v in mapping.items()
                                 if not k.startswith("_")})


# ----- fail-closed preserved: missing REQUIRED still blocks ------------------- #
def test_missing_state_still_emits_blocking_fill():
    """A sheet with no recognizable state must still fall back to required-FILL
    (fail-closed preserved -- we did NOT make required fields optional)."""
    tables = {
        "EN": pd.DataFrame({
            "subject_id": ["S1"], "enrollment_date": ["2020-01-01"], "site": ["A"],
        }),
    }
    m = _scaffold_mapping(describe_tables(tables))
    # no state anywhere -> clinical falls back to the required-FILL template
    assert m["clinical"]["sheet"] == "<FILL:sheet>"
    assert _has_placeholder(m["clinical"])  # still blocks, by design


# ----- the required/optional split is correct -------------------------------- #
def test_required_fill_and_optional_null_partition():
    req = _required_fill()
    opt = _optional_null()
    assert set(req) == {"sheet", "subject_id", "state"}
    assert all(v.startswith("<FILL:") for v in req.values())
    assert set(opt) == {"visit", "visit_date"}
    assert all(v is None for v in opt.values())
    # required and optional are disjoint and cover the staging contract
    assert set(req).isdisjoint(opt)


# ----- empty-desc fallback uses the same partition --------------------------- #
def test_empty_desc_fallback_visit_is_null_not_fill():
    """Empty input -> fallback template: required FILL, optional null."""
    m = _scaffold_mapping({})
    clin = m["clinical"]
    assert clin["sheet"] == "<FILL:sheet>"
    assert clin["subject_id"] == "<FILL:subject_id>"
    assert clin["state"] == "<FILL:state>"
    assert clin["visit"] is None
    assert clin["visit_date"] is None

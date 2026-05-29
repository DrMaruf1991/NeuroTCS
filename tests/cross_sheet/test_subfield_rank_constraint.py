"""
Behavior tests for the subfield_rank_constraint cross-sheet condition type
and the cross_sheet/hippocampal_subfield_ranking research_preview pack.

Encodes the ENIGMA hippocampal-subfield ranking-violation QC rules
(Saemann 2022, Human Brain Mapping 43(1):207-233, DOI 10.1002/hbm.25326):
  - CA1 must be rank #1 by volume   (DISABLED by default, per ENIGMA)
  - hippocampal tail must rank <= #3
  - subiculum must rank == #4

NeuroTCS does not measure subfields; it audits the rank order of values
another tool produced. The pack is research_preview, so audit_cross_sheet
refuses it unless dry_run=True (fail-closed / scope-honest).
"""

from __future__ import annotations

import pytest

from neurotcs.cross_sheet.audit import audit_cross_sheet
from neurotcs.cross_sheet.loader import load_invariantpack
from neurotcs.cross_sheet.schema import (
    InvariantPackStatus,
    SubfieldRankConstraintCondition,
)

PACK_NAME = "cross_sheet/hippocampal_subfield_ranking"
_SIDE = "left"


@pytest.fixture(scope="module")
def pack():
    return load_invariantpack(PACK_NAME)


def _row(**vols):
    """Build a biomarkers row with left-hemisphere subfield volumes."""
    row = {"patient_id": "p1", "visit_id": "v1"}
    for k, v in vols.items():
        row[f"{k}_volume_{_SIDE}_mm3"] = v
    return row


# A clean, realistic left-hemisphere ranking (grounded in FreeSurfer output
# magnitudes): CA1 > tail > molecular_layer > subiculum > ...
_CLEAN = dict(
    ca1=625.0, hippocampal_tail=618.0, molecular_layer_hp=562.0,
    subiculum=454.0, presubiculum=351.0, gc_ml_dg=337.0, ca4=300.0,
    ca3=225.0, fimbria=85.0, parasubiculum=75.0, hata=61.0,
)


def _audit_one(pack, row):
    return audit_cross_sheet({"biomarkers": [row]}, [pack], dry_run=True)


# ---- structure ----

def test_pack_is_research_preview(pack):
    assert pack.invariantpack.status == InvariantPackStatus.RESEARCH_PREVIEW


def test_pack_has_two_invariants_of_rank_type(pack):
    invs = pack.invariantpack.invariants
    assert len(invs) == 2
    for inv in invs:
        assert isinstance(inv.condition, SubfieldRankConstraintCondition)


def test_ca1_rule_is_disabled_by_default(pack):
    left = next(i for i in pack.invariantpack.invariants if i.name.startswith("left"))
    ca1_rule = next(r for r in left.condition.rules if r.field.startswith("ca1"))
    assert ca1_rule.enabled is False


# ---- fail-closed / scope-honest ----

def test_audit_refuses_research_preview_without_dry_run(pack):
    with pytest.raises(ValueError):
        audit_cross_sheet({"biomarkers": [_row(**_CLEAN)]}, [pack])


# ---- behavior ----

def test_clean_ranking_no_flags(pack):
    res = _audit_one(pack, _row(**_CLEAN))
    assert res.flags == []


def test_subiculum_not_rank_4_flags(pack):
    # Push presubiculum and gc above subiculum so subiculum falls to rank 6.
    v = dict(_CLEAN, presubiculum=500.0, gc_ml_dg=480.0)
    res = _audit_one(pack, _row(**v))
    reasons = [f.flag_reason for f in res.flags]
    assert len(res.flags) == 1, reasons
    assert "subiculum" in res.flags[0].flag_reason
    assert res.flags[0].severity == "warning"


def test_tail_below_rank_3_flags(pack):
    # presubiculum above tail; tail drops to rank 7, subiculum stays at rank 4.
    v = dict(_CLEAN, presubiculum=500.0, hippocampal_tail=290.0)
    res = _audit_one(pack, _row(**v))
    assert len(res.flags) == 1, [f.flag_reason for f in res.flags]
    assert "hippocampal_tail" in res.flags[0].flag_reason


def test_ca1_not_largest_does_not_flag_because_rule_disabled(pack):
    # molecular_layer largest; CA1 rank 2; tail #3, subiculum #4 still hold.
    v = dict(_CLEAN, molecular_layer_hp=700.0)
    res = _audit_one(pack, _row(**v))
    assert res.flags == [], [f.flag_reason for f in res.flags]


def test_partial_row_is_skipped(pack):
    # Drop one required field -> row cannot be ranked -> skipped, no flags.
    v = dict(_CLEAN)
    del v["hata"]
    res = _audit_one(pack, _row(**v))
    assert res.flags == []


def test_flag_carries_enigma_citation(pack):
    v = dict(_CLEAN, presubiculum=500.0, gc_ml_dg=480.0)
    res = _audit_one(pack, _row(**v))
    assert res.flags[0].citation_doi == "10.1002/hbm.25326"


# ---- determinism (property #1) ----

def test_flag_id_is_deterministic(pack):
    v = dict(_CLEAN, presubiculum=500.0, gc_ml_dg=480.0)
    r1 = _audit_one(pack, _row(**v))
    r2 = _audit_one(pack, _row(**v))
    assert [f.flag_id for f in r1.flags] == [f.flag_id for f in r2.flags]
    assert r1.flags[0].flag_id  # non-empty


# ---- schema guards ----

def test_rule_referencing_unknown_field_rejected():
    with pytest.raises(ValueError):
        SubfieldRankConstraintCondition(
            value_fields=["a_mm3", "b_mm3"],
            rules=[{"field": "c_mm3", "operator": "eq", "rank": 1}],
        )


def test_rank_exceeding_field_count_rejected():
    with pytest.raises(ValueError):
        SubfieldRankConstraintCondition(
            value_fields=["a_mm3", "b_mm3"],
            rules=[{"field": "a_mm3", "operator": "eq", "rank": 5}],
        )

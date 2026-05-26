"""Tests for the v1.7.10 PerTransitionFlags audit detail.

These tests verify the additive `return_per_transition` machinery introduced
for AD-lock Step 2.2 (demographic fairness slicing). Key invariants:

1. Existing audit_id and audit_id_v2 must be byte-identical with or without
   `return_per_transition=True`. The per-transition data is metadata only;
   it must NOT enter either hash.
2. When True, the returned `PerTransitionFlags` arrays must be aligned and
   self-consistent: lengths match, flag count matches AuditResult.n_flagged,
   per-trajectory iteration order is preserved.
3. Trajectory.metadata flows through to PerTransitionFlags.trajectory_metadata
   per transition (one dict per transition; same dict shared by all
   transitions from one trajectory).
4. The `attribute_array()` convenience returns a 1-D numpy array with
   missing-value handling for trajectories that don't carry the attribute.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from neurotcs import (
    PerTransitionFlags,
    Trajectory,
    audit,
    load_rulepack,
)


def _simple_trajectories() -> list[Trajectory]:
    """Three deterministic AD trajectories with demographic metadata.

    Layouts (using NIA-AA 2018 states CN / MCI / AD-dementia):
      - P1: CN -> MCI -> AD          (2 transitions, both admissible)
      - P2: CN -> AD                 (1 transition, INADMISSIBLE: skips MCI)
      - P3: MCI -> MCI               (1 transition, admissible self-loop)
    """
    return [
        Trajectory(
            patient_id="P1",
            states=("CN", "MCI", "AD-dementia"),
            dates=(date(2024, 1, 1), date(2024, 7, 1), date(2025, 1, 1)),
            metadata={"sex": "F", "age_band": "60-69",
                      "apoe4_status": "noncarrier"},
        ),
        Trajectory(
            patient_id="P2",
            states=("CN", "AD-dementia"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "M", "age_band": "70-79",
                      "apoe4_status": "heterozygote"},
        ),
        Trajectory(
            patient_id="P3",
            states=("MCI", "MCI"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "F", "age_band": "70-79",
                      "apoe4_status": "homozygote"},
        ),
    ]


def test_audit_id_unchanged_with_return_per_transition_true():
    """The audit_id and audit_id_v2 must be identical regardless of whether
    return_per_transition is requested. This is the critical no-breakage
    invariant — locked invariants like 947ab24e... must reproduce.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()

    result_default = audit(trajs, pack, bootstrap_B=200, seed=42)
    result_extra = audit(trajs, pack, bootstrap_B=200, seed=42,
                          return_per_transition=True)

    assert result_default.audit_id == result_extra.audit_id, (
        f"audit_id changed: {result_default.audit_id} -> "
        f"{result_extra.audit_id}. PerTransitionFlags must be additive only."
    )
    assert result_default.audit_id_v2 == result_extra.audit_id_v2, (
        "audit_id_v2 changed when return_per_transition=True"
    )


def test_per_transition_is_none_by_default():
    """When return_per_transition is False (the default), the field must
    be None — no surprise allocation for callers that don't ask for it.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42)
    assert result.per_transition is None


def test_per_transition_arrays_aligned_and_self_consistent():
    """When return_per_transition=True, the arrays must be aligned and the
    flag count must match AuditResult.n_flagged.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42,
                    return_per_transition=True)

    pt = result.per_transition
    assert pt is not None
    assert isinstance(pt, PerTransitionFlags)

    n = pt.n_transitions
    # P1 contributes 2, P2 contributes 1, P3 contributes 1 = 4 total
    assert n == 4
    assert n == result.n_transitions
    assert pt.n_flagged == result.n_flagged
    assert len(pt.patient_ids) == n
    assert pt.flags.shape == (n,)
    assert len(pt.from_states) == n
    assert len(pt.to_states) == n
    assert pt.delta_days.shape == (n,)
    assert len(pt.trajectory_metadata) == n


def test_per_transition_iteration_order_is_trajectory_then_chronological():
    """Per-transition arrays iterate trajectories in input order, then
    transitions within each trajectory in chronological (date) order.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42,
                    return_per_transition=True)
    pt = result.per_transition

    # Expected order: P1's two transitions, then P2's one, then P3's one.
    assert pt.patient_ids == ("P1", "P1", "P2", "P3")
    # P1: CN->MCI, MCI->AD-dementia
    # P2: CN->AD-dementia
    # P3: MCI->MCI
    assert pt.from_states == ("CN", "MCI", "CN", "MCI")
    assert pt.to_states == ("MCI", "AD-dementia", "AD-dementia", "MCI")


def test_per_transition_metadata_flows_through():
    """Each transition carries a copy of its source trajectory's metadata.
    Both transitions from P1 must carry P1's metadata dict.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42,
                    return_per_transition=True)
    pt = result.per_transition

    # Both of P1's transitions carry P1's metadata
    assert pt.trajectory_metadata[0] == {
        "sex": "F", "age_band": "60-69", "apoe4_status": "noncarrier",
    }
    assert pt.trajectory_metadata[1] == pt.trajectory_metadata[0]
    # P2's transition carries P2's metadata
    assert pt.trajectory_metadata[2] == {
        "sex": "M", "age_band": "70-79", "apoe4_status": "heterozygote",
    }
    # P3's transition carries P3's metadata
    assert pt.trajectory_metadata[3] == {
        "sex": "F", "age_band": "70-79", "apoe4_status": "homozygote",
    }


def test_per_transition_metadata_defensive_copy():
    """Mutating the returned metadata dict must NOT corrupt the source
    Trajectory's metadata. This is a defense-in-depth guarantee.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()
    p1_original = dict(trajs[0].metadata)
    result = audit(trajs, pack, bootstrap_B=200, seed=42,
                    return_per_transition=True)
    pt = result.per_transition

    # Mutate the per-transition dict
    pt.trajectory_metadata[0]["sex"] = "MUTATED"
    # Source trajectory must be untouched
    assert trajs[0].metadata == p1_original


def test_attribute_array_handles_present_and_missing():
    """attribute_array() returns a 1-D numpy array with the requested
    attribute pulled from each transition's metadata. Missing entries use
    the `missing` sentinel.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42,
                    return_per_transition=True)
    pt = result.per_transition

    sex_array = pt.attribute_array("sex")
    assert sex_array.tolist() == ["F", "F", "M", "F"]

    # Attribute that doesn't exist on any trajectory → all missing sentinel
    missing_array = pt.attribute_array("does_not_exist", missing="unknown")
    assert missing_array.tolist() == ["unknown"] * 4


def test_attribute_array_partial_missing():
    """Trajectories that lack a specific attribute key use the sentinel
    while others pass through their value."""
    pack = load_rulepack("ad/niaaa_2018")
    trajs = [
        Trajectory(
            patient_id="A",
            states=("CN", "MCI"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "F"},  # no apoe4_status
        ),
        Trajectory(
            patient_id="B",
            states=("CN", "MCI"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "M", "apoe4_status": "homozygote"},
        ),
    ]
    result = audit(trajs, pack, bootstrap_B=100, seed=42,
                    return_per_transition=True)
    pt = result.per_transition
    apoe_array = pt.attribute_array("apoe4_status", missing="unknown")
    assert apoe_array.tolist() == ["unknown", "homozygote"]


def test_per_transition_with_empty_trajectory():
    """A trajectory of length 1 (no transitions) contributes 0 rows to
    per_transition. The arrays must still be self-consistent.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = [
        Trajectory(
            patient_id="P1",
            states=("CN",),
            dates=(date(2024, 1, 1),),
            metadata={"sex": "F"},
        ),
        Trajectory(
            patient_id="P2",
            states=("CN", "MCI"),
            dates=(date(2024, 1, 1), date(2024, 7, 1)),
            metadata={"sex": "M"},
        ),
    ]
    result = audit(trajs, pack, bootstrap_B=100, seed=42,
                    return_per_transition=True)
    pt = result.per_transition
    # Only P2 contributes a transition
    assert pt.n_transitions == 1
    assert pt.patient_ids == ("P2",)


def test_per_transition_flag_count_matches_audit_n_flagged():
    """A sanity check that the cohort-level n_flagged (computed in the
    same loop as the per-transition data) matches the per-transition
    boolean array sum.
    """
    pack = load_rulepack("ad/niaaa_2018")
    trajs = _simple_trajectories()
    result = audit(trajs, pack, bootstrap_B=200, seed=42,
                    return_per_transition=True)
    assert result.per_transition.n_flagged == result.n_flagged
    assert int(result.per_transition.flags.sum()) == result.n_flagged


def test_per_transition_arrays_validate_at_construction():
    """PerTransitionFlags __post_init__ raises if arrays are misaligned."""
    with pytest.raises(ValueError, match="flags shape"):
        PerTransitionFlags(
            patient_ids=("A", "B"),
            flags=np.array([True], dtype=bool),  # too short
            from_states=("CN", "CN"),
            to_states=("MCI", "MCI"),
            delta_days=np.array([180.0, 180.0]),
            trajectory_metadata=({}, {}),
        )

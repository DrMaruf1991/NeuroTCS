"""Always-on synthetic drift sentinel (v1.20.0, ERRATA E-2026-006).

WHY THIS EXISTS
---------------
The metadata-drift bug (canonical SHA aaac92fb..., introduced v1.12.0) went
undetected from v1.13 through v1.19 because CI runs framework-only pytest with
the real-cohort locked-invariant tests SKIPPED (they require NEUROTCS_*_DIR /
*_CSV / *_RDA env vars that CI never sets). No locked-fingerprint test ran in
CI, so a shifted audit_id was invisible until a maintainer ran the real-data
suite locally.

This test closes that gap permanently. It builds a fully deterministic
synthetic cohort IN-PROCESS (no env vars, no external files), runs the real
ad/niaaa_2018 audit, and locks the resulting audit_id, audit_id_v2, and the
metadata-independent rulepack canonical SHA prefix. It therefore runs on EVERY
CI invocation. Any future change that alters the scientific fingerprint --
serializer, scoring kernel, RNG-affecting dependency upgrade -- turns CI red
on the next push, rather than hiding for six versions.

Pair with tests/rulepack/test_canonical_serialization_partition.py, which
proves (two-directionally) that metadata changes do NOT drift the SHA while
scientific changes DO. Together they make "no silent drift" structural.
"""
from __future__ import annotations

from datetime import date, timedelta

from neurotcs import load_rulepack
from neurotcs.audit_core import Trajectory, audit

# v1.20.0 metadata-independent canonical SHA prefix (scientific content only).
LOCKED_RULEPACK_SHA_PREFIX = "97811e3f1a145e47"

# Locked synthetic-cohort fingerprints under the v1.20.0 serializer.
LOCKED_AUDIT_ID = (
    "f5721b92cd3bf68cffc1c423d96f084655ec1834ab6753a2cc0610e6b8f20c52"
)
LOCKED_AUDIT_ID_V2 = (
    "d8adbb8040fa8e23f35deb5f0ad73d660e01c8fd10d8d26d62380c05ff2fc32b"
)
LOCKED_N_TRANSITIONS = 50
LOCKED_N_FLAGGED = 5
LOCKED_CTCS = 0.9

_START = date(2020, 1, 1)


def _make_traj(pid, states, intervals_days):
    dates = [_START]
    for d in intervals_days:
        dates.append(dates[-1] + timedelta(days=d))
    return Trajectory(patient_id=pid, states=tuple(states), dates=tuple(dates))


def _synthetic_cohort():
    """Fixed, deterministic cohort. DO NOT change without re-locking and
    documenting in ERRATA -- this is a frozen fingerprint reference."""
    trajs = []
    for i in range(20):
        trajs.append(_make_traj(f"p{i}", ["CN", "MCI", "AD"], [400, 400]))
    for i in range(20, 25):
        trajs.append(_make_traj(f"p{i}", ["AD", "MCI", "CN"], [400, 400]))
    return trajs


def test_synthetic_ci_invariant():
    """Locked synthetic fingerprint -- runs in CI with NO env vars."""
    pack = load_rulepack("ad/niaaa_2018")

    assert pack.sha256.startswith(LOCKED_RULEPACK_SHA_PREFIX), (
        f"Rulepack canonical SHA drift: got {pack.sha256[:16]}, "
        f"expected {LOCKED_RULEPACK_SHA_PREFIX}. The metadata-independent "
        f"serialization (ERRATA E-2026-006) changed -- investigate before "
        f"re-locking."
    )

    result = audit(_synthetic_cohort(), pack, bootstrap_B=500, seed=42)

    assert result.n_transitions == LOCKED_N_TRANSITIONS, (
        f"synthetic n_transitions: got {result.n_transitions}, "
        f"expected {LOCKED_N_TRANSITIONS}"
    )
    assert result.n_flagged == LOCKED_N_FLAGGED, (
        f"synthetic n_flagged: got {result.n_flagged}, "
        f"expected {LOCKED_N_FLAGGED}"
    )
    assert abs(result.ctcs.ci.point - LOCKED_CTCS) < 1e-9, (
        f"synthetic cTCS: got {result.ctcs.ci.point}, expected {LOCKED_CTCS}"
    )
    assert result.audit_id == LOCKED_AUDIT_ID, (
        f"SYNTHETIC audit_id DRIFT: got {result.audit_id}, "
        f"expected {LOCKED_AUDIT_ID}. The scientific fingerprint changed. If "
        f"intentional (rule/engine change), re-lock + document in ERRATA; if "
        f"not, this is the drift sentinel doing its job -- investigate."
    )
    assert result.audit_id_v2 == LOCKED_AUDIT_ID_V2, (
        f"SYNTHETIC audit_id_v2 DRIFT: got {result.audit_id_v2}, "
        f"expected {LOCKED_AUDIT_ID_V2}."
    )

"""
End-to-end audit pipeline.

The single entry point `audit(trajectories, rulepack, ...)` consumes a list
of patient trajectories and a loaded rule pack, runs the three TCS scorers
through cluster bootstrap, and returns a single `AuditResult` carrying:

  - cTCS / pTCS / uTCS each with mean, Huber estimate, BCa 95% CI
  - per-patient scores (aligned across the three metrics)
  - audit_id: SHA-256 over (rule pack SHA, score vectors, B, seed)
  - rulepack provenance (id, sha, schema_version, transcribed_by)
  - reproducibility metadata (timestamp, seed, B, ci_method)

The audit_id makes results citable and rerunnable: anyone with the same
rule pack and predictions reproduces the exact ID. This is the audit trail
the FDA Q-Sub will reference.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from neurotcs.audit_core.bootstrap import (
    BootstrapCI,
    cluster_bootstrap,
)
from neurotcs.audit_core.scoring import (
    PerPatientScores,
    score_cohort,
)
from neurotcs.audit_core.trajectory import Trajectory
from neurotcs.rulepack.loader import LoadedRulePack

# ============================================================
# Result types
# ============================================================

@dataclass(frozen=True)
class MetricResult:
    """Cohort-level result for one TCS metric."""
    name: str
    ci: BootstrapCI
    available: bool = True
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if not self.available:
            return {
                "name": self.name,
                "available": False,
                "skipped_reason": self.skipped_reason,
            }
        return {
            "name": self.name,
            "available": True,
            "point": self.ci.point,
            "huber": self.ci.huber,
            "ci_95_low": self.ci.ci_low,
            "ci_95_high": self.ci.ci_high,
            "ci_method": self.ci.ci_method,
            "B": self.ci.B,
            "n_clusters": self.ci.n_clusters,
            "seed": self.ci.seed,
        }


@dataclass(frozen=True)
class PerTransitionFlags:
    """Per-transition admissibility verdicts aligned to trajectory order.

    Produced only when `audit()` is called with `return_per_transition=True`.
    Used by `neurotcs.fairness.fairness_audit()` to stratify the cohort flag
    rate by demographic / clinical attributes per FUTURE-AI BMJ 2025.

    Attributes:
        patient_ids: Per-transition patient identifier (length = n_transitions).
            One trajectory contributing T-1 transitions appears T-1 times here.
        flags: Boolean array (length = n_transitions). True = the audit
            kernel marked this transition as inadmissible.
        from_states: Per-transition `from_state` label.
        to_states: Per-transition `to_state` label.
        delta_days: Per-transition delta-t in days (float).
        trajectory_metadata: Per-transition metadata dict copied from each
            transition's source trajectory. Carries demographic and clinical
            attributes like "sex", "age_band", "apoe4_status" that are
            recognised by `fairness_audit()`. Empty dicts for trajectories
            with no metadata supplied.

    The order is: iterate trajectories in input order, then transitions
    within each trajectory in chronological order. This is deterministic
    and reproducible — running the same input twice produces identical
    arrays. Does NOT influence audit_id (additive field; audit_id is
    derived from per-patient scores only, by design).
    """
    patient_ids: tuple[str, ...]
    flags: np.ndarray
    from_states: tuple[str, ...]
    to_states: tuple[str, ...]
    delta_days: np.ndarray
    trajectory_metadata: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        n = len(self.patient_ids)
        if self.flags.shape != (n,):
            raise ValueError(
                f"PerTransitionFlags: flags shape {self.flags.shape} does not "
                f"match patient_ids length {n}"
            )
        if len(self.from_states) != n or len(self.to_states) != n:
            raise ValueError(
                f"PerTransitionFlags: from_states ({len(self.from_states)}) "
                f"and to_states ({len(self.to_states)}) must equal patient_ids "
                f"length {n}"
            )
        if self.delta_days.shape != (n,):
            raise ValueError(
                f"PerTransitionFlags: delta_days shape {self.delta_days.shape} "
                f"does not match patient_ids length {n}"
            )
        if len(self.trajectory_metadata) != n:
            raise ValueError(
                f"PerTransitionFlags: trajectory_metadata "
                f"({len(self.trajectory_metadata)}) must equal patient_ids "
                f"length {n}"
            )

    @property
    def n_transitions(self) -> int:
        return len(self.patient_ids)

    @property
    def n_flagged(self) -> int:
        return int(self.flags.sum())

    def attribute_array(self, name: str,
                        missing: str = "unknown") -> np.ndarray:
        """Extract a single demographic attribute as a 1-D array.

        Convenience for handing a column to `fairness_audit()`. Missing or
        absent metadata entries are filled with the `missing` sentinel so
        downstream stratification treats them as their own group rather
        than crashing.
        """
        return np.array(
            [md.get(name, missing) if md else missing
             for md in self.trajectory_metadata],
            dtype=object,
        )


@dataclass(frozen=True)
class AuditResult:
    """End-to-end audit output.

    Attributes:
        audit_id: SHA-256 of the canonical result content. Stable across
            reruns with the same inputs.
        timestamp_utc: ISO-8601 UTC timestamp of the audit.
        rulepack_id: Loaded rule pack ID (e.g. "ad/niaaa_2018@1.1.0").
        rulepack_sha256: Canonical SHA-256 of the rule pack content.
        rulepack_schema_version: Schema version string.
        rulepack_transcribed_by: Who attested the rule pack.
        n_patients: Number of patients in input.
        n_patients_scored: Number that contributed >= 1 transition.
        n_transitions: Total transitions audited.
        n_flagged: Transitions whose K kernel returned 0 (inadmissible).
        ctcs: cTCS cohort result.
        ptcs: pTCS cohort result (may be unavailable if no priors).
        utcs: uTCS cohort result.
        prior_type: "clinical" or "population" used for pTCS.
        per_patient: PerPatientScores (full per-patient arrays).
        bootstrap_B: Number of bootstrap resamples used.
        ci_method: "bca" or "percentile".
        seed: Reproducibility seed.
    """
    audit_id: str
    timestamp_utc: str
    rulepack_id: str
    rulepack_sha256: str
    rulepack_schema_version: str
    rulepack_transcribed_by: str
    n_patients: int
    n_patients_scored: int
    n_transitions: int
    n_flagged: int
    ctcs: MetricResult
    ptcs: MetricResult
    utcs: MetricResult
    prior_type: str
    per_patient: PerPatientScores = field(repr=False)
    bootstrap_B: int
    ci_method: str
    seed: int
    # v1.7.1: optional augmented audit_id that ALSO hashes input trajectories.
    # Default "" preserves backward compatibility for any code that
    # constructs AuditResult manually (e.g. tests, downstream consumers).
    audit_id_v2: str = ""
    # v1.7.10 (AD-lock Step 2.2): optional per-transition flag detail for
    # demographic fairness stratification (FUTURE-AI BMJ 2025 panel B.4.4).
    # Populated only when audit() is called with `return_per_transition=True`.
    # Default None preserves backward compatibility — existing audit_ids and
    # serialisation are byte-identical to v1.7.9.
    per_transition: PerTransitionFlags | None = field(default=None, repr=False)

    @property
    def flagged_rate(self) -> float:
        if self.n_transitions == 0:
            return 0.0
        return self.n_flagged / self.n_transitions

    def to_dict(self, include_per_patient: bool = False) -> dict[str, Any]:
        """Serializable summary. Per-patient arrays optionally included."""
        out: dict[str, Any] = {
            "audit_id": self.audit_id,
            "audit_id_v2": self.audit_id_v2,
            "timestamp_utc": self.timestamp_utc,
            "rulepack": {
                "id": self.rulepack_id,
                "sha256": self.rulepack_sha256,
                "schema_version": self.rulepack_schema_version,
                "transcribed_by": self.rulepack_transcribed_by,
            },
            "cohort": {
                "n_patients": self.n_patients,
                "n_patients_scored": self.n_patients_scored,
                "n_transitions": self.n_transitions,
                "n_flagged": self.n_flagged,
                "flagged_rate": self.flagged_rate,
            },
            "bootstrap": {
                "B": self.bootstrap_B,
                "ci_method": self.ci_method,
                "seed": self.seed,
            },
            "metrics": {
                "ctcs": self.ctcs.to_dict(),
                "ptcs": self.ptcs.to_dict(),
                "utcs": self.utcs.to_dict(),
                "prior_type": self.prior_type,
            },
        }
        if include_per_patient:
            out["per_patient"] = {
                "patients": list(self.per_patient.patients),
                "ctcs": [float(x) for x in self.per_patient.ctcs],
                "ptcs": ([float(x) for x in self.per_patient.ptcs]
                         if self.per_patient.ptcs is not None else None),
                "utcs": [float(x) for x in self.per_patient.utcs],
                "n_transitions": [int(x) for x in self.per_patient.n_transitions],
            }
        return out

    def to_json(self, *, indent: int = 2,
                include_per_patient: bool = False) -> str:
        return json.dumps(
            self.to_dict(include_per_patient=include_per_patient),
            indent=indent,
            ensure_ascii=False,
            sort_keys=True,
        )

    def summary(self) -> str:
        """Human-readable summary string."""
        lines = [
            "NeuroTCS Audit Result",
            f"  audit_id:         {self.audit_id}",
            f"  audit_id_v2:      {self.audit_id_v2 or '(not computed)'}",
            f"  rulepack:         {self.rulepack_id}",
            f"  rulepack_sha:     {self.rulepack_sha256[:16]}...",
            f"  patients:         {self.n_patients_scored} scored "
            f"/ {self.n_patients} total",
            f"  transitions:      {self.n_transitions:,} "
            f"({self.n_flagged} flagged, {100 * self.flagged_rate:.2f}%)",
            f"  bootstrap:        B={self.bootstrap_B}, "
            f"CI={self.ci_method.upper()}, seed={self.seed}",
            "",
            f"  cTCS  {self.ctcs.ci}",
        ]
        if self.ptcs.available:
            lines.append(f"  pTCS  {self.ptcs.ci}  (priors: {self.prior_type})")
        else:
            lines.append(f"  pTCS  N/A ({self.ptcs.skipped_reason})")
        lines.append(f"  uTCS  {self.utcs.ci}")
        return "\n".join(lines)


# ============================================================
# Internal: audit_id construction
# ============================================================

def _compute_audit_id(
    rulepack_sha: str,
    per_patient: PerPatientScores,
    B: int,
    seed: int,
    ci_method: str,
    prior_type: str,
) -> str:
    """Stable SHA-256 over the canonical audit content.

    Same inputs → same audit_id, every time, anywhere — including across
    big-endian and little-endian machines. v1.7.1 explicitly forces the
    numpy arrays to little-endian byte order before hashing
    (`.astype('<f8')` for floats, `.astype('<i8')` for the int64
    n_transitions counter); prior versions used the platform's native
    byte order via `.tobytes()`, which would produce a different
    audit_id on a big-endian machine for identical numerical inputs.

    For FDA Q-Sub audit-trail portability, the v1.7.1 hash is the
    canonical going-forward form. Locked invariants from v1.7.0 and
    earlier will compute to a new audit_id under v1.7.1+; re-derive
    them on first audit and capture the new locked value (see
    `tests/audit_core/test_real_oasis3_audit.py` for the
    re-derivation pattern).
    """
    h = hashlib.sha256()
    h.update(rulepack_sha.encode())
    h.update(b"|")
    # Per-patient signature: round to 1e-6 to be robust to numpy/scipy
    # microscopic drift across platforms while preserving correctness.
    # Force little-endian explicit byte order so the hash is identical
    # across platforms with different native endianness (C5 fix).
    h.update(np.round(per_patient.ctcs, 6).astype("<f8").tobytes())
    if per_patient.ptcs is not None:
        h.update(np.round(per_patient.ptcs, 6).astype("<f8").tobytes())
    h.update(np.round(per_patient.utcs, 6).astype("<f8").tobytes())
    h.update(per_patient.n_transitions.astype("<i8").tobytes())
    h.update(f"|B={B}|seed={seed}|ci={ci_method}|prior={prior_type}".encode())
    return h.hexdigest()


def _trajectory_canonical_signature(
    trajectories: list[Trajectory],
) -> bytes:
    """Build a deterministic byte signature of the input trajectories.

    Used by `_compute_audit_id_v2` (C6 fix). Two distinct trajectories
    that happen to produce identical rounded per-patient scores can
    collide under the v1 audit_id; this signature makes that collision
    cryptographically improbable by including the raw `(patient_id,
    sorted dates, states)` content.

    The signature is canonical:
      - trajectories sorted by patient_id (lexicographic)
      - dates rendered as ISO 8601 strings
      - states joined with ``\\x1f`` (unit separator) so a state name
        containing a pipe cannot break framing
    """
    parts: list[bytes] = []
    for traj in sorted(trajectories, key=lambda t: t.patient_id):
        date_strs = "|".join(
            d.isoformat() if hasattr(d, "isoformat") else str(d)
            for d in traj.dates
        )
        state_strs = "\x1f".join(traj.states)
        parts.append(
            f"{traj.patient_id}\x1e{date_strs}\x1e{state_strs}".encode()
        )
    return b"\x1d".join(parts)


def _compute_audit_id_v2(
    rulepack_sha: str,
    per_patient: PerPatientScores,
    B: int,
    seed: int,
    ci_method: str,
    prior_type: str,
    trajectory_signature: bytes,
) -> str:
    """Augmented SHA-256 audit_id that ALSO hashes the input trajectories.

    The v1 audit_id hashes the rule pack + per-patient scores + bootstrap
    parameters. Two distinct trajectories producing identical rounded
    scores can therefore collide. v2 closes this gap by including a
    canonical signature of the input trajectories in the hash. Added
    v1.7.1 (C6 fix) per FDA Q-Sub audit-trail integrity requirements.

    Available alongside the v1 audit_id (`AuditResult.audit_id_v2`); the
    primary `AuditResult.audit_id` remains the v1 hash for backward
    compatibility with locked invariants.
    """
    h = hashlib.sha256()
    h.update(b"v2|")
    h.update(rulepack_sha.encode())
    h.update(b"|")
    h.update(np.round(per_patient.ctcs, 6).astype("<f8").tobytes())
    if per_patient.ptcs is not None:
        h.update(np.round(per_patient.ptcs, 6).astype("<f8").tobytes())
    h.update(np.round(per_patient.utcs, 6).astype("<f8").tobytes())
    h.update(per_patient.n_transitions.astype("<i8").tobytes())
    h.update(f"|B={B}|seed={seed}|ci={ci_method}|prior={prior_type}".encode())
    h.update(b"|trajectories|")
    h.update(hashlib.sha256(trajectory_signature).digest())
    return h.hexdigest()


# ============================================================
# Public audit entry point
# ============================================================

def audit(
    trajectories: list[Trajectory],
    rulepack: LoadedRulePack,
    *,
    bootstrap_B: int = 10_000,
    seed: int = 42,
    ci_method: str = "bca",
    prior_type: str = "clinical",
    return_per_transition: bool = False,
) -> AuditResult:
    """Run the full audit pipeline on a cohort of trajectories.

    Args:
        trajectories: Patient trajectories (1 per patient).
        rulepack: A LoadedRulePack with `status=production`. The audit raises
            if the rule pack is a skeleton.
        bootstrap_B: Number of cluster-bootstrap resamples (default 10,000,
            per spec §A.5).
        seed: Reproducibility seed for the bootstrap.
        ci_method: "bca" (default) or "percentile".
        prior_type: "clinical" or "population" priors for pTCS scoring.
        return_per_transition: If True, attach a `PerTransitionFlags` object
            to the result with per-transition admissibility verdicts and
            trajectory metadata. Used by the fairness audit (FUTURE-AI
            BMJ 2025 panel B.4.4). Default False keeps memory low for
            large cohorts. Does NOT influence audit_id or audit_id_v2.

    Returns:
        AuditResult with cTCS / pTCS / uTCS each fully scored.
    """
    rulepack.assert_usable_for_audit()

    n_patients_total = len(trajectories)

    # Score the cohort: per-patient cTCS / pTCS / uTCS aligned arrays
    per_patient = score_cohort(trajectories, rulepack, prior_type=prior_type)
    n_patients_scored = len(per_patient.patients)
    n_transitions = int(per_patient.n_transitions.sum())

    # Count flagged transitions: rebuild the running tally directly.
    # Uses transitions_with_context so schema v1.2 conditional admissibility
    # (e.g. TRAC pack) flags treatment-untreated A+ -> A- correctly.
    #
    # When return_per_transition is True, also accumulate per-transition
    # arrays in the SAME loop. This guarantees the per-transition output
    # is bit-identical to the cohort flag count: same loop order, same
    # admissibility call, same context handling.
    n_flagged = 0
    _pt_patient_ids: list[str] = []
    _pt_flags: list[bool] = []
    _pt_from: list[str] = []
    _pt_to: list[str] = []
    _pt_dt: list[float] = []
    _pt_meta: list[dict[str, Any]] = []
    for traj in trajectories:
        rp = rulepack.rulepack
        for from_s, to_s, dt, from_ctx, to_ctx in traj.transitions_with_context():
            ok, _ = rp.is_admissible(
                from_s, to_s, dt,
                from_context=from_ctx,
                to_context=to_ctx,
            )
            if not ok:
                n_flagged += 1
            if return_per_transition:
                _pt_patient_ids.append(traj.patient_id)
                _pt_flags.append(not ok)
                _pt_from.append(from_s)
                _pt_to.append(to_s)
                _pt_dt.append(float(dt))
                # Defensive copy so downstream mutation can't corrupt history
                _pt_meta.append(dict(traj.metadata) if traj.metadata else {})

    if return_per_transition:
        per_transition = PerTransitionFlags(
            patient_ids=tuple(_pt_patient_ids),
            flags=np.asarray(_pt_flags, dtype=bool),
            from_states=tuple(_pt_from),
            to_states=tuple(_pt_to),
            delta_days=np.asarray(_pt_dt, dtype=float),
            trajectory_metadata=tuple(_pt_meta),
        )
    else:
        per_transition = None

    # cTCS bootstrap
    if per_patient.ctcs.size > 0:
        ctcs_ci = cluster_bootstrap(
            per_patient.ctcs, B=bootstrap_B, seed=seed, ci_method=ci_method,
        )
        ctcs_result = MetricResult(name="cTCS", ci=ctcs_ci, available=True)
    else:
        ctcs_ci = None
        ctcs_result = MetricResult(
            name="cTCS",
            ci=BootstrapCI(0.0, 0.0, 0.0, 0.0, ci_method, None,
                            bootstrap_B, 0, seed),
            available=False,
            skipped_reason="no scored patients",
        )

    # pTCS bootstrap (skip if no priors)
    if per_patient.ptcs is not None and per_patient.ptcs.size > 0:
        ptcs_ci = cluster_bootstrap(
            per_patient.ptcs, B=bootstrap_B, seed=seed, ci_method=ci_method,
        )
        ptcs_result = MetricResult(name="pTCS", ci=ptcs_ci, available=True)
    else:
        ptcs_result = MetricResult(
            name="pTCS",
            ci=BootstrapCI(float("nan"), float("nan"),
                            float("nan"), float("nan"),
                            ci_method, None, bootstrap_B, 0, seed),
            available=False,
            skipped_reason=(
                "rule pack has no transition_priors of type "
                f"'{prior_type}'"
            ),
        )

    # uTCS bootstrap
    if per_patient.utcs.size > 0:
        utcs_ci = cluster_bootstrap(
            per_patient.utcs, B=bootstrap_B, seed=seed, ci_method=ci_method,
        )
        utcs_result = MetricResult(name="uTCS", ci=utcs_ci, available=True)
    else:
        utcs_result = MetricResult(
            name="uTCS",
            ci=BootstrapCI(0.0, 0.0, 0.0, 0.0, ci_method, None,
                            bootstrap_B, 0, seed),
            available=False,
            skipped_reason="no scored patients",
        )

    audit_id = _compute_audit_id(
        rulepack.sha256, per_patient, bootstrap_B, seed, ci_method, prior_type,
    )
    audit_id_v2 = _compute_audit_id_v2(
        rulepack.sha256, per_patient, bootstrap_B, seed, ci_method, prior_type,
        _trajectory_canonical_signature(trajectories),
    )

    return AuditResult(
        audit_id=audit_id,
        audit_id_v2=audit_id_v2,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        rulepack_id=rulepack.rulepack_id,
        rulepack_sha256=rulepack.sha256,
        rulepack_schema_version=rulepack.rulepack.schema_version,
        rulepack_transcribed_by=rulepack.rulepack.transcribed_by,
        n_patients=n_patients_total,
        n_patients_scored=n_patients_scored,
        n_transitions=n_transitions,
        n_flagged=n_flagged,
        ctcs=ctcs_result,
        ptcs=ptcs_result,
        utcs=utcs_result,
        prior_type=prior_type,
        per_patient=per_patient,
        bootstrap_B=bootstrap_B,
        ci_method=ci_method,
        seed=seed,
        per_transition=per_transition,
    )

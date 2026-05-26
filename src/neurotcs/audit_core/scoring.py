"""
NeuroTCS scoring engine: cTCS, pTCS, uTCS.

Per temporalmetric v1.7 FINAL spec §A.2 - §A.4:

  cTCS  Categorical Temporal Consistency Score
        cTCSᵢ = (1 / (Tᵢ − 1)) · Σₜ K(ŷᵢ,ₜ, ŷᵢ,ₜ₊₁, Δτ)
        K is a binary clinical-plausibility kernel from a versioned rulepack.
        Cohort cTCS = mean over patients ∈ [0, 1].

  pTCS  Probabilistic Temporal Consistency Score
        pTCSᵢ = (1 / (Tᵢ − 1)) · Σₜ log Mŷᵢ,ₜ, ŷᵢ,ₜ₊₁(Δτ)
        Time-aware Markov log-likelihood with matrix exponential
        M(Δτ) = exp(Q · Δτ / 365)
        Q is the generator built from rule pack `transition_priors`.

  uTCS  Uncertainty-weighted TCS (extends Thulasidasan 2019 to transitions)
        uTCSᵢ = (1 / (Tᵢ − 1)) · Σₜ wᵢ,ₜ · K(ŷᵢ,ₜ, ŷᵢ,ₜ₊₁, Δτ)
        wᵢ,ₜ = max(p̂ᵢ,ₜ) · max(p̂ᵢ,ₜ₊₁). Confident clinically-implausible
        flips penalized hardest.

Scoring is pure (no I/O, no global state). Inputs are Trajectory objects +
a LoadedRulePack; outputs are per-patient float arrays for the bootstrap
to consume.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from neurotcs.audit_core.trajectory import Trajectory
from neurotcs.rulepack.loader import LoadedRulePack

# Floor for log(M[i,j]) in pTCS to avoid log(0) on biologically inadmissible
# transitions. 1e-9 corresponds to log = -20.7, a strong penalty without
# being numerically unbounded.
_PTCS_FLOOR = 1e-9


# ============================================================
# Generator Q from rule pack
# ============================================================

@dataclass(frozen=True)
class GeneratorMatrix:
    """Continuous-time Markov generator built from a rule pack.

    Q[i, j] (i ≠ j) = annual rate of transition state_i → state_j (in years⁻¹)
    Q[i, i] = -sum_{j ≠ i} Q[i, j]   (rows sum to zero)

    P(state_t+Δτ = j | state_t = i) = (exp(Q · Δτ/365))[i, j]
    where Δτ is in days.

    Attributes:
        Q:           (K, K) generator matrix (years⁻¹).
        state_index: Maps state name → row/col index.
        prior_type:  "clinical" or "population" (per spec sensitivity analyses).
        priors_covered:  Number of off-diagonal entries actually backed by a
                         rule pack prior (vs implicit zero).
    """
    Q: np.ndarray
    state_index: dict[str, int]
    prior_type: str
    priors_covered: int

    @property
    def states(self) -> list[str]:
        return [s for s, _ in sorted(self.state_index.items(),
                                       key=lambda kv: kv[1])]

    def transition_probability(self, from_state: str, to_state: str,
                                 delta_t_days: float) -> float:
        """Compute M(Δτ)[from, to] = exp(Q · Δτ/365)[from, to]."""
        if delta_t_days < 0:
            raise ValueError(f"delta_t_days must be >= 0, got {delta_t_days}")
        if from_state not in self.state_index:
            return _PTCS_FLOOR
        if to_state not in self.state_index:
            return _PTCS_FLOOR
        M = expm(self.Q * (delta_t_days / 365.0))
        i = self.state_index[from_state]
        j = self.state_index[to_state]
        # Clip tiny negative entries that can arise from expm numerics
        p = max(float(M[i, j]), 0.0)
        return p


def build_generator(rulepack: LoadedRulePack,
                     prior_type: str = "clinical") -> GeneratorMatrix | None:
    """Build the continuous-time Markov generator Q from a rule pack.

    Reads `transition_priors` from the rule pack and constructs a valid
    generator matrix (off-diagonal nonnegative, rows sum to zero).

    Returns None if the rule pack has no priors of the requested type
    (pTCS is not computable for that pack/prior).
    """
    rp = rulepack.rulepack
    state_names = [s.name for s in rp.state_space]
    K = len(state_names)
    state_index = {s: i for i, s in enumerate(state_names)}

    relevant = [p for p in rp.transition_priors if p.prior_type == prior_type]
    if not relevant:
        return None

    Q = np.zeros((K, K), dtype=float)
    covered = 0
    for prior in relevant:
        if prior.from_state == prior.to_state:
            # Self-transition rates do not enter Q off-diagonal; they are
            # implied by row sum. Skip with a soft warning policy: a stable
            # self-loop probability is encoded by absence of off-diagonal mass.
            continue
        i = state_index[prior.from_state]
        j = state_index[prior.to_state]
        if Q[i, j] != 0.0:
            # Duplicate entry — rule packs should not have these (loader
            # already checks transitions). For priors we permit multiple
            # entries only for distinct prior_types; if we somehow got
            # here, sum them rather than overwriting.
            pass
        Q[i, j] += float(prior.annual_probability)
        covered += 1

    # Diagonal: row sums = 0
    for i in range(K):
        Q[i, i] = -float(Q[i, :].sum())

    return GeneratorMatrix(
        Q=Q,
        state_index=state_index,
        prior_type=prior_type,
        priors_covered=covered,
    )


# ============================================================
# cTCS — categorical kernel scoring
# ============================================================

def ctcs_per_patient(
    trajectory: Trajectory,
    rulepack: LoadedRulePack,
) -> float | None:
    """Compute per-patient cTCS for one trajectory.

    Returns None if the trajectory has fewer than 2 visits (no transitions).

    Uses `transitions_with_context()` so schema v1.2+ rule packs that declare
    `required_conditions` on transitions (e.g. the TRAC pack
    `ad/aa_2024_trac@1.0.0`) can evaluate treatment_status against the
    trajectory's per-visit context. Trajectories without `treatment_status`
    pass `None` contexts; rule packs treat that as fail-closed for
    conditional transitions (correct behavior — we cannot certify a
    treatment-dependent transition without treatment evidence).
    """
    n = trajectory.num_transitions
    if n == 0:
        return None
    rp = rulepack.rulepack
    K_sum = 0
    for from_s, to_s, dt, from_ctx, to_ctx in trajectory.transitions_with_context():
        ok, _ = rp.is_admissible(
            from_s, to_s, dt,
            from_context=from_ctx,
            to_context=to_ctx,
        )
        if ok:
            K_sum += 1
    return K_sum / n


def ctcs_per_patient_array(
    trajectories: list[Trajectory],
    rulepack: LoadedRulePack,
) -> tuple[np.ndarray, list[Trajectory]]:
    """Compute per-patient cTCS across a cohort.

    Returns:
        (scores, scored_trajectories)
        - `scores`: (N_scored,) float array
        - `scored_trajectories`: the trajectories that contributed (those
          with >= 1 transition). Order is preserved.
    """
    scores: list[float] = []
    scored: list[Trajectory] = []
    for traj in trajectories:
        s = ctcs_per_patient(traj, rulepack)
        if s is not None:
            scores.append(s)
            scored.append(traj)
    return np.asarray(scores, dtype=float), scored


# ============================================================
# pTCS — time-aware Markov log-likelihood
# ============================================================

def ptcs_per_patient(
    trajectory: Trajectory,
    generator: GeneratorMatrix,
) -> float | None:
    """Compute per-patient pTCS for one trajectory.

    Returns None if the trajectory has fewer than 2 visits.
    """
    n = trajectory.num_transitions
    if n == 0:
        return None
    log_sum = 0.0
    for from_s, to_s, dt in trajectory.transitions():
        p = generator.transition_probability(from_s, to_s, dt)
        if p < _PTCS_FLOOR:
            p = _PTCS_FLOOR
        log_sum += float(np.log(p))
    return log_sum / n


def ptcs_per_patient_array(
    trajectories: list[Trajectory],
    generator: GeneratorMatrix,
) -> tuple[np.ndarray, list[Trajectory]]:
    """Compute per-patient pTCS across a cohort."""
    scores: list[float] = []
    scored: list[Trajectory] = []
    for traj in trajectories:
        s = ptcs_per_patient(traj, generator)
        if s is not None:
            scores.append(s)
            scored.append(traj)
    return np.asarray(scores, dtype=float), scored


# ============================================================
# uTCS — uncertainty-weighted kernel scoring
# ============================================================

def utcs_per_patient(
    trajectory: Trajectory,
    rulepack: LoadedRulePack,
) -> float | None:
    """Compute per-patient uTCS for one trajectory.

    If the trajectory carries no probabilities, all weights default to 1.0
    and uTCS == cTCS for that patient.

    Returns None if the trajectory has fewer than 2 visits.
    """
    n = trajectory.num_transitions
    if n == 0:
        return None
    rp = rulepack.rulepack
    transitions_ctx = trajectory.transitions_with_context()
    weights = trajectory.transition_confidences()
    weighted_sum = 0.0
    for (from_s, to_s, dt, from_ctx, to_ctx), (p_t, p_t1) in zip(
        transitions_ctx, weights, strict=True
    ):
        ok, _ = rp.is_admissible(
            from_s, to_s, dt,
            from_context=from_ctx,
            to_context=to_ctx,
        )
        K = 1.0 if ok else 0.0
        weighted_sum += (p_t * p_t1) * K
    return weighted_sum / n


def utcs_per_patient_array(
    trajectories: list[Trajectory],
    rulepack: LoadedRulePack,
) -> tuple[np.ndarray, list[Trajectory]]:
    """Compute per-patient uTCS across a cohort."""
    scores: list[float] = []
    scored: list[Trajectory] = []
    for traj in trajectories:
        s = utcs_per_patient(traj, rulepack)
        if s is not None:
            scores.append(s)
            scored.append(traj)
    return np.asarray(scores, dtype=float), scored


# ============================================================
# Convenience: all three at once
# ============================================================

@dataclass(frozen=True)
class PerPatientScores:
    """Per-patient TCS scores aligned across the three metrics.

    Attributes:
        patients: Tuple of N patient IDs (those with >= 1 transition).
        ctcs: (N,) float array of per-patient cTCS in [0, 1].
        ptcs: Optional (N,) float array of per-patient pTCS (log-likelihood,
              typically negative). None if the rule pack carries no usable
              priors for the requested prior_type.
        utcs: (N,) float array of per-patient uTCS in [0, 1] (or matching
              cTCS if no probabilities supplied).
        n_transitions: (N,) int array of transitions contributed per patient.
        generator: The GeneratorMatrix used for pTCS, or None.
    """
    patients: tuple[str, ...]
    ctcs: np.ndarray
    ptcs: np.ndarray | None
    utcs: np.ndarray
    n_transitions: np.ndarray
    generator: GeneratorMatrix | None


def score_cohort(
    trajectories: list[Trajectory],
    rulepack: LoadedRulePack,
    *,
    prior_type: str = "clinical",
) -> PerPatientScores:
    """Score every trajectory against the rule pack, returning aligned arrays.

    Args:
        trajectories: List of patient trajectories.
        rulepack: Loaded production rule pack (assert_usable_for_audit()
                   is enforced).
        prior_type: "clinical" or "population" priors for pTCS.

    Returns:
        PerPatientScores with cTCS / pTCS / uTCS arrays of equal length N
        (where N is the number of trajectories with >= 1 transition).
    """
    rulepack.assert_usable_for_audit()

    # cTCS sets the canonical patient ordering
    ctcs_arr, scored = ctcs_per_patient_array(trajectories, rulepack)

    # pTCS: build generator and score
    gen = build_generator(rulepack, prior_type=prior_type)
    if gen is not None:
        ptcs_vals = np.asarray(
            [ptcs_per_patient(t, gen) for t in scored], dtype=float
        )
    else:
        ptcs_vals = None

    # uTCS: same ordering as scored
    utcs_vals = np.asarray(
        [utcs_per_patient(t, rulepack) for t in scored], dtype=float
    )

    n_tx = np.asarray([t.num_transitions for t in scored], dtype=int)
    patient_ids = tuple(t.patient_id for t in scored)

    return PerPatientScores(
        patients=patient_ids,
        ctcs=ctcs_arr,
        ptcs=ptcs_vals,
        utcs=utcs_vals,
        n_transitions=n_tx,
        generator=gen,
    )

"""Synthetic longitudinal AD cohort generator for the NeuroTCS Colab demo.

NOT FOR CLINICAL USE. Generates fake but biologically-plausible NIA-AA 2018
longitudinal trajectories so reviewers can see the audit pipeline run
end-to-end without needing DUA-controlled cohort data.

The synthetic data is designed to:
  1. Have known clinical-state structure (CN, MCI, AD) following Jack 2018
  2. Mostly admissible transitions (so cTCS should be high, ~0.95-0.99)
  3. A few deliberately implausible transitions seeded for visibility
  4. Be fully deterministic given a seed

What this proves:
  - The framework loads, audits, and emits an audit_id
  - cTCS falls in the expected clinical range (0.95-1.00)
  - Two runs with the same seed produce identical audit_ids (determinism)

What this does NOT prove:
  - Anything about real cohort reproducibility (those need real DUA data
    and the v2 protocol on a local machine)

Usage:
    from synthetic_demo_data import generate_synthetic_trajectories
    trajs = generate_synthetic_trajectories(n_subjects=200, seed=42)

License: Apache-2.0 to match the NeuroTCS framework.
"""

from __future__ import annotations

import datetime as _dt
import hashlib as _hashlib
import random as _random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neurotcs.audit_core import Trajectory


# Jack 2018 NIA-AA Research Framework states (canonical)
_STATES = ["CN", "MCI", "AD"]

# Admissible transitions per NIA-AA 2018 rulepack (forward + lateral stable)
_ADMISSIBLE = {
    ("CN", "CN"), ("CN", "MCI"),
    ("MCI", "MCI"), ("MCI", "AD"), ("MCI", "CN"),  # CN backslide rare but admissible
    ("AD", "AD"),
}


def _hash_id(idx: int, salt: str = "synthetic_demo_v1") -> str:
    """Deterministic synthetic subject ID via SHA-256."""
    return _hashlib.sha256(f"{salt}_{idx:06d}".encode()).hexdigest()[:16]


def generate_synthetic_trajectories(
    n_subjects: int = 200,
    seed: int = 42,
    n_implausible_seeded: int = 3,
) -> "list[Trajectory]":
    """Generate synthetic longitudinal AD trajectories.

    Args:
        n_subjects: number of synthetic subjects. Each gets 2-5 visits.
        seed: RNG seed for reproducibility.
        n_implausible_seeded: number of deliberately implausible transitions
            to seed (e.g. CN -> AD with no MCI intermediate; AD -> CN).
            Set to 0 for a fully-admissible synthetic cohort.

    Returns:
        list of Trajectory objects ready for neurotcs.audit(...).
    """
    from neurotcs.audit_core import Trajectory

    rng = _random.Random(seed)
    base_date = _dt.date(2020, 1, 1)
    trajectories: list[Trajectory] = []

    for subj_idx in range(n_subjects):
        n_visits = rng.randint(2, 5)
        # Pick a starting state biased toward CN/MCI (clinical-cohort realism)
        start = rng.choices(_STATES, weights=[0.5, 0.4, 0.1], k=1)[0]

        states = [start]
        dates = [base_date + _dt.timedelta(days=rng.randint(0, 365))]

        for _ in range(n_visits - 1):
            current = states[-1]
            # Admissible next-state distribution
            admissible_next = [s for s in _STATES if (current, s) in _ADMISSIBLE]
            if not admissible_next:
                admissible_next = [current]  # fallback stay
            # Slight bias toward progression
            weights = []
            for nxt in admissible_next:
                if nxt == current:
                    weights.append(0.6)
                elif _STATES.index(nxt) > _STATES.index(current):
                    weights.append(0.3)
                else:
                    weights.append(0.1)  # backslide rare
            nxt_state = rng.choices(admissible_next, weights=weights, k=1)[0]
            states.append(nxt_state)
            dates.append(dates[-1] + _dt.timedelta(days=rng.randint(180, 540)))

        trajectories.append(
            Trajectory(
                patient_id=_hash_id(subj_idx),
                states=tuple(states),
                dates=tuple(dates),
            )
        )

    # Seed deliberately implausible transitions for audit visibility
    for k in range(n_implausible_seeded):
        idx = (k * 37 + 11) % len(trajectories)  # deterministic spread
        t = trajectories[idx]
        if len(t.states) >= 2:
            # Force an inadmissible transition: AD -> CN
            new_states = list(t.states)
            new_states[-1] = "CN" if new_states[0] != "CN" else "AD"
            trajectories[idx] = Trajectory(
                patient_id=t.patient_id,
                states=tuple(new_states),
                dates=t.dates,
            )

    return trajectories


if __name__ == "__main__":
    # Standalone smoke test
    trajs = generate_synthetic_trajectories(n_subjects=200, seed=42)
    n_transitions = sum(len(t.states) - 1 for t in trajs)
    print(f"Generated {len(trajs)} synthetic subjects, {n_transitions} transitions")
    print(f"First trajectory: {trajs[0].subject_id} states={trajs[0].states}")

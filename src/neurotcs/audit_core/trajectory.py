"""
Trajectory data structures for the NeuroTCS audit engine.

A `Trajectory` is one patient's longitudinal prediction sequence: ordered
states with timestamps and (optionally) per-state probability vectors and
treatment-status flags. The audit engine consumes lists of trajectories;
each trajectory contributes its per-patient TCS scores to the cohort
bootstrap.

Per temporalmetric v1.7 FINAL spec §A.2 - §A.4 + §C.5.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Trajectory:
    """One patient's longitudinal prediction trajectory.

    A trajectory of length T contributes T - 1 transitions to the cohort
    audit. Trajectories of length 0 or 1 are valid but contribute zero
    transitions; they do not break the audit pipeline.

    Attributes:
        patient_id: Stable identifier (string for portability).
        states: Ordered list of predicted states (T entries).
        dates: Ordered list of visit dates (T entries, ascending).
        probabilities: Optional (T, K) array of per-state probabilities.
            Required for uTCS scoring; if absent, uTCS falls back to
            unweighted (uTCS == cTCS).
        state_labels: Ordered list of K state names that map to the columns
            of `probabilities`. Must be supplied iff probabilities are.
        treatment_status: Optional per-visit treatment flags
            (e.g. "none" / "anti_amyloid_active") per spec §A.2.1 TRAC.
        metadata: Free-form per-trajectory metadata that does NOT influence
            scoring (e.g. site, scanner, APOE).
    """
    patient_id: str
    states: tuple[str, ...]
    dates: tuple[date, ...]
    probabilities: np.ndarray | None = None
    state_labels: tuple[str, ...] | None = None
    treatment_status: tuple[str, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Length consistency
        T = len(self.states)
        if len(self.dates) != T:
            raise ValueError(
                f"Trajectory {self.patient_id}: states ({T}) and dates "
                f"({len(self.dates)}) must have equal length"
            )

        # Dates ascending (allow ties — same-day re-read)
        for i in range(1, T):
            if self.dates[i] < self.dates[i - 1]:
                raise ValueError(
                    f"Trajectory {self.patient_id}: dates not ascending at "
                    f"index {i} ({self.dates[i - 1]} -> {self.dates[i]})"
                )

        # Probabilities consistency
        if self.probabilities is not None:
            if self.state_labels is None:
                raise ValueError(
                    f"Trajectory {self.patient_id}: probabilities given "
                    f"but state_labels missing"
                )
            if self.probabilities.shape[0] != T:
                raise ValueError(
                    f"Trajectory {self.patient_id}: probabilities row count "
                    f"({self.probabilities.shape[0]}) != T ({T})"
                )
            if self.probabilities.shape[1] != len(self.state_labels):
                raise ValueError(
                    f"Trajectory {self.patient_id}: probabilities col count "
                    f"({self.probabilities.shape[1]}) != len(state_labels) "
                    f"({len(self.state_labels)})"
                )
            # Probabilities should each be in [0, 1]; we don't require strict
            # row-sum-to-1 (some models emit unnormalized scores). uTCS uses
            # max per row, which is robust to the absence of normalization.
            if (self.probabilities < 0).any() or (self.probabilities > 1).any():
                raise ValueError(
                    f"Trajectory {self.patient_id}: probabilities outside "
                    f"[0, 1] — must be normalized or clipped before audit"
                )

        # Treatment status consistency
        if self.treatment_status is not None and len(self.treatment_status) != T:
            raise ValueError(
                f"Trajectory {self.patient_id}: treatment_status length "
                f"({len(self.treatment_status)}) != T ({T})"
            )

    @property
    def length(self) -> int:
        return len(self.states)

    @property
    def num_transitions(self) -> int:
        return max(self.length - 1, 0)

    def transitions(self) -> list[tuple[str, str, float]]:
        """Iterate (from_state, to_state, delta_t_days) over this trajectory."""
        out: list[tuple[str, str, float]] = []
        for t in range(self.num_transitions):
            dt = (self.dates[t + 1] - self.dates[t]).days
            out.append((self.states[t], self.states[t + 1], float(dt)))
        return out

    def transitions_with_context(
        self,
    ) -> list[tuple[str, str, float, dict[str, str] | None, dict[str, str] | None]]:
        """Iterate (from_state, to_state, delta_t_days, from_context, to_context).

        Per-visit context dicts carry the trajectory's per-visit fields
        (currently `treatment_status`) for use with schema v1.2+ rule packs
        that declare `required_conditions` on transitions. Returns None
        for context dicts on trajectories that don't carry treatment_status,
        which the rule pack treats as fail-closed for conditional transitions.
        """
        out: list[tuple[str, str, float, dict[str, str] | None, dict[str, str] | None]] = []
        for t in range(self.num_transitions):
            dt = (self.dates[t + 1] - self.dates[t]).days
            from_ctx: dict[str, str] | None = None
            to_ctx: dict[str, str] | None = None
            if self.treatment_status is not None:
                from_ctx = {"treatment_status": self.treatment_status[t]}
                to_ctx = {"treatment_status": self.treatment_status[t + 1]}
            out.append((
                self.states[t],
                self.states[t + 1],
                float(dt),
                from_ctx,
                to_ctx,
            ))
        return out

    def transition_confidences(self) -> list[tuple[float, float]]:
        """Iterate (max_p_t, max_p_{t+1}) pairs for uTCS scoring.

        Returns [(1.0, 1.0), ...] if probabilities are not present, which
        gives uTCS == cTCS.
        """
        if self.probabilities is None:
            return [(1.0, 1.0)] * self.num_transitions
        max_p = self.probabilities.max(axis=1)
        return [(float(max_p[t]), float(max_p[t + 1]))
                for t in range(self.num_transitions)]


def trajectories_from_dataframe(
    df: pd.DataFrame,
    *,
    patient_id_col: str,
    visit_date_col: str,
    state_col: str,
    probability_cols: Sequence[str] | None = None,
    state_label_map: dict[str, str] | None = None,
    treatment_status_col: str | None = None,
    metadata_cols: Sequence[str] | None = None,
    skip_invalid: bool = False,
) -> list[Trajectory]:
    """Build a list of Trajectories from a long-format DataFrame.

    The DataFrame must have one row per (patient, visit). Rows are grouped
    by `patient_id_col`, sorted by `visit_date_col`, and packed into one
    Trajectory per patient.

    Args:
        df: Long-format DataFrame.
        patient_id_col: Column with patient identifiers.
        visit_date_col: Column with visit dates (datetime-castable).
        state_col: Column with predicted state labels.
        probability_cols: Optional ordered list of K probability columns.
            If given, the resulting trajectories carry a (T, K) probability
            matrix and uTCS is computable.
        state_label_map: Optional dict to remap raw labels in `state_col`
            (e.g. ADNI's "Dementia" -> "AD"). Applied before trajectory
            construction.
        treatment_status_col: Optional column for treatment flags.
        metadata_cols: Optional list of column names whose per-patient
            values are stored on Trajectory.metadata. These columns are
            assumed to be patient-level constants (sex, APOE4 status,
            age band, etc.) and the FIRST row's value is used per
            patient. If a per-patient value varies across visits in the
            input, only the first encountered value is preserved (and
            no warning is emitted — assume the caller has pre-normalised).
            Used downstream by `neurotcs.fairness.fairness_audit()` for
            demographic stratification (FUTURE-AI BMJ 2025 panel B.4.4).
        skip_invalid: If True, patients whose data fails Trajectory
            construction (e.g. unsortable dates, malformed probability rows)
            are silently dropped from the returned list. The total number of
            skipped patients is logged at INFO level via the
            ``neurotcs.audit_core.trajectory`` logger (configure with
            ``logging.getLogger('neurotcs.audit_core.trajectory').setLevel(
            logging.INFO)`` to surface it). If False (default), the first
            invalid patient raises ``ValueError``.

    Returns:
        List of Trajectory objects, one per unique patient_id.
    """
    if patient_id_col not in df.columns:
        raise KeyError(f"Missing patient_id column: {patient_id_col}")
    if visit_date_col not in df.columns:
        raise KeyError(f"Missing visit_date column: {visit_date_col}")
    if state_col not in df.columns:
        raise KeyError(f"Missing state column: {state_col}")

    work = df.copy()

    # Coerce dates
    work[visit_date_col] = pd.to_datetime(work[visit_date_col], errors="coerce")
    work = work.dropna(subset=[visit_date_col, patient_id_col, state_col])

    # Apply state-label remap
    if state_label_map is not None:
        work[state_col] = work[state_col].replace(state_label_map)

    # Sort within patients
    work = work.sort_values([patient_id_col, visit_date_col])

    # Validate metadata columns up front
    if metadata_cols is not None:
        missing_meta = [c for c in metadata_cols if c not in work.columns]
        if missing_meta:
            raise KeyError(
                f"metadata_cols not found in DataFrame: {missing_meta}"
            )

    trajectories: list[Trajectory] = []
    n_skipped = 0
    for pid, group in work.groupby(patient_id_col, sort=False):
        states = tuple(group[state_col].astype(str).tolist())
        dates = tuple(d.date() if isinstance(d, (pd.Timestamp, datetime))
                       else d for d in group[visit_date_col].tolist())

        probs: np.ndarray | None = None
        labels: tuple[str, ...] | None = None
        if probability_cols is not None:
            missing = [c for c in probability_cols if c not in group.columns]
            if missing:
                raise KeyError(f"Probability columns not in DataFrame: {missing}")
            probs = group[list(probability_cols)].to_numpy(dtype=float)
            labels = tuple(probability_cols)

        tx: tuple[str, ...] | None = None
        if treatment_status_col is not None and treatment_status_col in group.columns:
            tx = tuple(group[treatment_status_col].astype(str).tolist())

        meta: dict[str, Any] = {}
        if metadata_cols is not None:
            for col in metadata_cols:
                # Take the first visit's value as the patient-level constant.
                first_val = group[col].iloc[0]
                # Preserve None/NaN as None for clean fairness handling
                if pd.isna(first_val):
                    meta[col] = None
                else:
                    meta[col] = first_val

        try:
            trajectories.append(Trajectory(
                patient_id=str(pid),
                states=states,
                dates=dates,
                probabilities=probs,
                state_labels=labels,
                treatment_status=tx,
                metadata=meta,
            ))
        except ValueError as e:
            if skip_invalid:
                n_skipped += 1
                continue
            raise ValueError(
                f"Trajectory construction failed for patient {pid}: {e}. "
                f"Pass skip_invalid=True to drop and continue."
            ) from e

    if skip_invalid and n_skipped > 0:
        _logger.info(
            "trajectories_from_dataframe: skipped %d invalid patient "
            "trajectory(ies); returning %d valid trajectories.",
            n_skipped, len(trajectories),
        )

    return trajectories

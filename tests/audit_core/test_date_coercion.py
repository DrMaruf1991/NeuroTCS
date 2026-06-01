"""Tests for warning-free, value-preserving visit-date coercion (v1.50).

The bare pd.to_datetime(s, errors='coerce') warns when pandas cannot infer a
single format and silently falls back to per-element dateutil parsing. The
_coerce_visit_dates helper makes the intent explicit (ISO8601, then mixed) so
the warning is gone AND the parsed values are byte-identical to the old path.
"""
from __future__ import annotations

import warnings

import pandas as pd

from neurotcs.audit_core.trajectory import (
    _coerce_visit_dates,
    trajectories_from_dataframe,
)


class TestDateCoercion:

    def test_iso_dates_no_warning(self):
        s = pd.Series(["2018-01-01", "2019-06-15", "2020-12-31"])
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning -> failure
            out = _coerce_visit_dates(s)
        assert out.notna().all()

    def test_values_identical_to_legacy_path(self):
        # For ISO data the new path must equal the old format-less parse exactly.
        s = pd.Series(["2018-01-01", "2019-06-15", "2020-12-31", "bad"])
        new = _coerce_visit_dates(s)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            old = pd.to_datetime(s, errors="coerce")
        # NaT positions and timestamps must match
        assert (new.isna() == old.isna()).all()
        assert (new.dropna().values == old.dropna().values).all()

    def test_mixed_formats_no_warning(self):
        s = pd.Series(["2018-01-01", "06/15/2019", "2020-12-31"])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            out = _coerce_visit_dates(s)
        assert out.notna().sum() >= 2

    def test_bad_dates_coerced_to_nat(self):
        s = pd.Series(["2018-01-01", "not-a-date", "2020-12-31"])
        out = _coerce_visit_dates(s)
        assert out.isna().sum() == 1

    def test_trajectory_build_no_warning(self):
        df = pd.DataFrame({
            "subject_id": ["A", "A", "B", "B"],
            "visit_date": ["2018-01-01", "2019-06-15", "2018-03-01", "2020-12-31"],
            "state": ["CN", "MCI", "MCI", "AD"],
        })
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            trajs = trajectories_from_dataframe(
                df, patient_id_col="subject_id", visit_date_col="visit_date",
                state_col="state")
        assert len(trajs) == 2

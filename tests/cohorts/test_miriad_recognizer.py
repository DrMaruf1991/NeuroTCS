"""v1.85.0 -- MIRIAD cohort recognizer tests.

MIRIAD is the multi-file exception: recognition detects the three XNAT export
roles by HEADER content (clinical = subject+MMSE; sessions = subject+age+scans;
subjects = subject, no MMSE, with YOB/education/MR-count). The mapping reuses
load_miriad_trajectories WHOLE and flattens its trajectories to a submission --
no clinical logic re-implemented. These tests lock role detection, no-false-match,
and fail-closed when required roles are absent. The cTCS=0.985369 reproduction is
proven manually on real DUA data (the loader is the single source of truth).
"""
from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.cohorts import recognize_cohort
from neurotcs.cohorts.miriad import (
    _identify_roles,
    _is_clinical,
    _is_sessions,
    _is_subjects,
    recognize_miriad,
)


def _sessions_df():
    return pd.DataFrame(columns=[
        "Label", "Project", "Date", "Subject", "M/F", "Age", "Type",
        "Scanner", "Scans"])


def _subjects_df():
    return pd.DataFrame(columns=[
        "Subject", "Gender", "Hand", "YOB", "Education", "Ses", "MR Count"])


def _clinical_df():
    return pd.DataFrame(columns=[
        "id", "Label", "Subject", "Gender", "MMSE", "memory", "orientation",
        "rating"])


def _miriad_tables():
    return {
        "f24": _sessions_df(),
        "f33": _subjects_df(),
        "f7": _clinical_df(),
    }


# ----- role detectors ------------------------------------------------------ #
def test_is_clinical():
    assert _is_clinical(_clinical_df()) is True
    assert _is_clinical(_sessions_df()) is False  # no MMSE
    assert _is_clinical(_subjects_df()) is False


def test_is_sessions():
    assert _is_sessions(_sessions_df()) is True
    assert _is_sessions(_clinical_df()) is False  # no age/scans
    assert _is_sessions(_subjects_df()) is False


def test_is_subjects():
    assert _is_subjects(_subjects_df()) is True
    assert _is_subjects(_clinical_df()) is False  # has MMSE
    assert _is_subjects(_sessions_df()) is False  # has Age (MR Sessions)


def test_identify_roles():
    clin, sess, subj = _identify_roles(_miriad_tables())
    assert clin == "f7"
    assert sess == "f24"
    assert subj == "f33"


# ----- recognition --------------------------------------------------------- #
def test_recognizes_miriad():
    m = recognize_cohort(_miriad_tables())
    assert m is not None
    assert m.cohort_id == "miriad"
    assert m.confidence >= 0.9
    assert m.sheet == "f7"  # clinical anchor


def test_subjects_optional():
    """clinical + sessions are enough (subjects is optional in the loader)."""
    tables = {"f24": _sessions_df(), "f7": _clinical_df()}
    m = recognize_miriad(tables)
    assert m is not None
    assert m.cohort_id == "miriad"


def test_missing_sessions_not_recognized():
    """Without the sessions table (age-at-scan) MIRIAD cannot be assembled."""
    tables = {"f7": _clinical_df(), "f33": _subjects_df()}
    assert recognize_miriad(tables) is None


def test_non_miriad_not_recognized():
    df = pd.DataFrame({"subject_id": ["S1"], "state": ["CN"]})
    assert recognize_miriad({"clinical": df}) is None


def test_build_mapping_fail_closed_without_roles():
    from neurotcs.cohorts.miriad import _build_miriad_mapping
    # only a subjects table -> no clinical, no sessions -> must raise
    with pytest.raises(ValueError):
        _build_miriad_mapping({"f33": _subjects_df()})

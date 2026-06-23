"""v1.83.0 -- A4/LEARN cohort recognizer + --cohort wiring (Phase 2A).

Recognize-then-confirm: recognize_cohort SUGGESTS by column signature; the mapping
(CDGLOBAL crosswalk, -99 sentinel handling, day-offset ordering) is built only on
confirmation. These tests lock recognition, mapping correctness, fail-closed on
junk, and that a non-A4 file is NOT recognized.
"""
from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.cohorts import recognize_cohort
from neurotcs.cohorts.a4 import _build_a4_mapping, _cdglobal_to_state, recognize_a4


def _a4_table():
    return pd.DataFrame({
        "BID": ["B1", "B1", "B1", "B2", "B2", "B3"],
        "VISCODE": ["v1", "v2", "v3", "v1", "v2", "v1"],
        "CDGLOBAL": [0.0, 0.0, 0.5, 0.0, 1.0, 0.0],
        "CDADTC_DAYS_T0": [0, 365, 730, 0, 365, -99],  # B3 sentinel
        "CDRSB": [0, 0, 1, 0, 2, 0], "EPOCH": ["x"] * 6, "AVISIT": ["a"] * 6,
    })


# ----- recognition --------------------------------------------------------- #
def test_recognizes_a4_signature():
    m = recognize_cohort({"cdr": _a4_table()})
    assert m is not None
    assert m.cohort_id == "a4"
    assert m.display_name == "A4/LEARN"
    assert m.confidence >= 0.9  # exact triple + companions
    assert m.sheet == "cdr"


def test_non_a4_file_not_recognized():
    """A generic clinical file must NOT be recognized as A4 (no false positive)."""
    df = pd.DataFrame({
        "subject_id": ["S1", "S1"], "visit": [0, 1],
        "visit_date": ["2020-01-01", "2021-01-01"], "state": ["CN", "MCI"],
    })
    assert recognize_cohort({"clinical": df}) is None


def test_partial_signature_not_recognized():
    """BID + CDGLOBAL but NO CDADTC_DAYS_T0 -> not the full A4 signature."""
    df = pd.DataFrame({"BID": ["B1"], "CDGLOBAL": [0.0], "other": [1]})
    assert recognize_a4({"x": df}) is None


# ----- CDGLOBAL crosswalk -------------------------------------------------- #
def test_cdglobal_crosswalk():
    assert _cdglobal_to_state(0.0) == "CN"
    assert _cdglobal_to_state(0.5) == "MCI"
    assert _cdglobal_to_state(1.0) == "AD"
    assert _cdglobal_to_state(2.0) == "AD"
    assert _cdglobal_to_state(3.0) == "AD"
    assert _cdglobal_to_state("junk") is None
    assert _cdglobal_to_state(None) is None


# ----- mapping build ------------------------------------------------------- #
def test_build_mapping_shape_and_derivation():
    tables = {"cdr": _a4_table()}
    mapping = _build_a4_mapping(tables)
    clin = mapping["clinical"]
    assert clin["subject_id"] == "BID"
    assert clin["state"] == "__a4_state__"
    assert clin["visit_date"] == "__a4_visit_date__"
    assert "visit" not in clin  # omitted -> derived downstream
    # derived sheet now carries the crosswalked state + synthetic date
    work = tables["cdr"]
    assert "__a4_state__" in work.columns
    assert set(work["__a4_state__"]).issubset({"CN", "MCI", "AD"})


def test_sentinel_row_dropped():
    """B3's only visit has CDADTC_DAYS_T0 == -99 (sentinel) -> dropped, so B3
    has no rows in the derived staging frame."""
    tables = {"cdr": _a4_table()}
    _build_a4_mapping(tables)
    work = tables["cdr"]
    assert "B3" not in set(work["BID"]), "sentinel-only subject must be dropped"
    # B1 and B2 (real days) remain
    assert {"B1", "B2"} <= set(work["BID"])


def test_build_mapping_fail_closed_on_all_sentinel():
    """If every row is sentinel/unmappable, building raises (nothing to audit)."""
    df = pd.DataFrame({
        "BID": ["B1", "B1"], "CDGLOBAL": [0.0, 0.5],
        "CDADTC_DAYS_T0": [-99, -99], "VISCODE": ["v1", "v2"],
    })
    with pytest.raises(ValueError):
        _build_a4_mapping({"cdr": df})


# ----- end-to-end via the audit submission path ----------------------------- #
def test_a4_mapping_audits_via_tables_to_submission():
    from neurotcs.io import tables_to_submission
    tables = {"cdr": _a4_table()}
    mapping = _build_a4_mapping(tables)
    warns: list[str] = []
    sub = tables_to_submission(tables, mapping, warnings=warns)
    assert "clinical" in sub
    out = sub["clinical"]
    assert list(out.columns)[:4] == ["subject_id", "visit", "visit_date", "state"]
    # B1: CN, CN, MCI ; B2: CN, AD  (B3 dropped)
    assert set(out["subject_id"]) == {"B1", "B2"}
    assert set(out["state"]).issubset({"CN", "MCI", "AD"})

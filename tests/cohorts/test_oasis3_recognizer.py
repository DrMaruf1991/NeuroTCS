"""v1.84.0 -- OASIS-3 cohort recognizer tests.

Signature: OASISID + days_to_visit + CDRTOT. Mapping reuses cdr_to_state +
hash_patient_id + SYNTHETIC_BASELINE day-offset conversion from the canonical
adapter. Locks recognition, crosswalk reuse, fail-closed, no false match.
"""
from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.cohorts import recognize_cohort
from neurotcs.cohorts.oasis3 import _build_oasis3_mapping, recognize_oasis3
from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import cdr_to_state


def _oasis3_table():
    return pd.DataFrame({
        "OASISID": ["O1", "O1", "O1", "O2", "O2"],
        "days_to_visit": [0, 365, 730, 0, 400],
        "CDRTOT": [0.0, 0.5, 1.0, 0.0, 2.0],
        "dx1": ["Cognitively normal"] * 5,
    })


def test_recognizes_oasis3_signature():
    m = recognize_cohort({"OASIS3_UDSb4_cdr": _oasis3_table()})
    assert m is not None
    assert m.cohort_id == "oasis3"
    assert m.confidence >= 0.85


def test_non_oasis3_not_recognized():
    df = pd.DataFrame({"subject_id": ["S1"], "state": ["CN"]})
    assert recognize_oasis3({"clinical": df}) is None


def test_partial_signature_not_recognized():
    df = pd.DataFrame({"OASISID": ["O1"], "CDRTOT": [0.0], "other": [1]})
    assert recognize_oasis3({"x": df}) is None  # missing days_to_visit


def test_crosswalk_reused_from_adapter():
    assert cdr_to_state(0.0) == "CN"
    assert cdr_to_state(0.5) == "MCI"
    assert cdr_to_state(1.0) == "AD"
    assert cdr_to_state(2.0) == "AD"


def test_build_mapping_shape_and_state():
    tables = {"OASIS3_UDSb4_cdr": _oasis3_table()}
    mapping = _build_oasis3_mapping(tables)
    clin = mapping["clinical"]
    assert clin["subject_id"] == "__o3_subject__"
    assert clin["state"] == "__o3_state__"
    assert clin["visit_date"] == "__o3_date__"
    work = tables["OASIS3_UDSb4_cdr"]
    assert set(work["__o3_state__"]).issubset({"CN", "MCI", "AD"})
    # dates are synthetic, ascending within subject (interval-preserving)
    assert work["__o3_date__"].notna().all()


def test_build_mapping_fail_closed_on_all_unmappable():
    df = pd.DataFrame({
        "OASISID": ["O1", "O1"], "days_to_visit": [0, 365],
        "CDRTOT": [None, None],
    })
    with pytest.raises(ValueError):
        _build_oasis3_mapping({"OASIS3_UDSb4_cdr": df})


def test_oasis3_mapping_audits_via_tables_to_submission():
    from neurotcs.io import tables_to_submission
    tables = {"OASIS3_UDSb4_cdr": _oasis3_table()}
    mapping = _build_oasis3_mapping(tables)
    warns: list[str] = []
    sub = tables_to_submission(tables, mapping, warnings=warns)
    out = sub["clinical"]
    assert list(out.columns)[:4] == ["subject_id", "visit", "visit_date", "state"]
    assert set(out["state"]).issubset({"CN", "MCI", "AD"})

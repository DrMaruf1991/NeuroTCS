"""v1.84.0 -- NACC cohort recognizer tests.

Recognize-then-confirm: recognize_cohort SUGGESTS by signature (NACCID + VISITDATE
+ NACCUDSD); the mapping (reusing naccudsd_to_state + hash_patient_id from the
canonical adapter) is built only on confirmation. Locks recognition, crosswalk
reuse, fail-closed on junk, and no false match on a non-NACC file.
"""
from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.cohorts import recognize_cohort
from neurotcs.cohorts.nacc import _build_nacc_mapping, recognize_nacc
from neurotcs.input_contract.v1_1.adapters.adapter_nacc import naccudsd_to_state


def _nacc_table():
    return pd.DataFrame({
        "NACCID": ["N1", "N1", "N1", "N2", "N2", "N3"],
        "VISITDATE": ["2018-01-01", "2019-01-01", "2020-01-01",
                      "2018-06-01", "2019-06-01", "2018-03-01"],
        "NACCUDSD": [1, 1, 3, 1, 4, 8],  # N3's only row is 8 -> dropped
        "NACCAGE": [70, 71, 72, 65, 66, 80],
    })


def test_recognizes_nacc_signature():
    m = recognize_cohort({"investigator_nacc73": _nacc_table()})
    assert m is not None
    assert m.cohort_id == "nacc"
    assert m.sheet == "investigator_nacc73"
    assert m.confidence >= 0.85


def test_non_nacc_file_not_recognized():
    df = pd.DataFrame({
        "subject_id": ["S1", "S1"], "visit": [0, 1],
        "visit_date": ["2020-01-01", "2021-01-01"], "state": ["CN", "MCI"],
    })
    assert recognize_nacc({"clinical": df}) is None


def test_partial_signature_not_recognized():
    df = pd.DataFrame({"NACCID": ["N1"], "NACCUDSD": [1], "other": [1]})
    assert recognize_nacc({"x": df}) is None


def test_crosswalk_reused_from_adapter():
    # the recognizer reuses the canonical adapter crosswalk (not a copy)
    assert naccudsd_to_state(1) == "CN"
    assert naccudsd_to_state(2) == "MCI"
    assert naccudsd_to_state(3) == "MCI"
    assert naccudsd_to_state(4) == "AD"
    assert naccudsd_to_state(8) is None  # dropped


def test_build_mapping_shape_and_state():
    tables = {"investigator_nacc73": _nacc_table()}
    mapping = _build_nacc_mapping(tables)
    clin = mapping["clinical"]
    assert clin["subject_id"] == "__nacc_subject__"
    assert clin["state"] == "__nacc_state__"
    assert clin["visit_date"] == "__nacc_date__"
    assert "visit" not in clin  # omitted -> derived downstream
    work = tables["investigator_nacc73"]
    assert set(work["__nacc_state__"]).issubset({"CN", "MCI", "AD"})


def test_naccudsd_8_dropped():
    tables = {"investigator_nacc73": _nacc_table()}
    _build_nacc_mapping(tables)
    work = tables["investigator_nacc73"]
    # N3 had only NACCUDSD=8 -> no mappable state -> subject gone
    subjects = set(work["NACCID"])
    assert "N3" not in subjects
    assert {"N1", "N2"} <= subjects


def test_build_mapping_fail_closed_on_all_unmappable():
    df = pd.DataFrame({
        "NACCID": ["N1", "N1"], "VISITDATE": ["2018-01-01", "2019-01-01"],
        "NACCUDSD": [8, 8],  # all unmappable
    })
    with pytest.raises(ValueError):
        _build_nacc_mapping({"investigator_nacc73": df})


def test_nacc_mapping_audits_via_tables_to_submission():
    from neurotcs.io import tables_to_submission
    tables = {"investigator_nacc73": _nacc_table()}
    mapping = _build_nacc_mapping(tables)
    warns: list[str] = []
    sub = tables_to_submission(tables, mapping, warnings=warns)
    assert "clinical" in sub
    out = sub["clinical"]
    assert list(out.columns)[:4] == ["subject_id", "visit", "visit_date", "state"]
    assert set(out["state"]).issubset({"CN", "MCI", "AD"})

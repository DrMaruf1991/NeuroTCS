"""v1.84.0 -- ADNI cohort recognizer tests.

Signature: RID + DIAGNOSIS + EXAMDATE (canonical DXSUM). Mapping reuses
DIAGNOSIS_MAP from the canonical adapter and keeps RAW RID (no hash) to reproduce
the locked v1.7.13 invariant. Locks recognition, crosswalk reuse, raw-RID, fail-
closed, no false match.
"""
from __future__ import annotations

import pandas as pd
import pytest

from neurotcs.cohorts import recognize_cohort
from neurotcs.cohorts.adni import _build_adni_mapping, recognize_adni
from neurotcs.input_contract.v1_1.adapters.adapter_adni_canonical import DIAGNOSIS_MAP


def _adni_table():
    return pd.DataFrame({
        "RID": [1, 1, 1, 2, 2],
        "DIAGNOSIS": ["CN", "CN", "MCI", "MCI", "Dementia"],
        "EXAMDATE": ["2018-01-01", "2019-01-01", "2020-01-01",
                     "2018-06-01", "2019-06-01"],
        "VISCODE": ["bl", "m12", "m24", "bl", "m12"],
    })


def test_recognizes_adni_signature():
    m = recognize_cohort({"DXSUM": _adni_table()})
    assert m is not None
    assert m.cohort_id == "adni"
    assert m.confidence >= 0.85


def test_non_adni_not_recognized():
    df = pd.DataFrame({"subject_id": ["S1"], "state": ["CN"]})
    assert recognize_adni({"clinical": df}) is None


def test_partial_signature_not_recognized():
    df = pd.DataFrame({"RID": [1], "DIAGNOSIS": ["CN"], "other": [1]})
    assert recognize_adni({"x": df}) is None  # missing EXAMDATE


def test_crosswalk_reused_from_adapter():
    assert DIAGNOSIS_MAP["CN"] == "CN"
    assert DIAGNOSIS_MAP["MCI"] == "MCI"
    assert DIAGNOSIS_MAP["Dementia"] == "AD"


def test_build_mapping_raw_rid_and_state():
    tables = {"DXSUM": _adni_table()}
    mapping = _build_adni_mapping(tables)
    clin = mapping["clinical"]
    assert clin["subject_id"] == "__adni_subject__"
    assert clin["state"] == "__adni_state__"
    work = tables["DXSUM"]
    # RAW RID preserved (string of the integer), NOT hashed
    assert set(work["__adni_subject__"]) == {"1", "2"}
    assert set(work["__adni_state__"]).issubset({"CN", "MCI", "AD"})
    # Dementia -> AD specifically
    assert "AD" in set(work["__adni_state__"])


def test_invalid_diagnosis_rows_dropped():
    df = pd.DataFrame({
        "RID": [1, 1, 1],
        "DIAGNOSIS": ["CN", "NL", "Dementia"],  # NL not in map -> dropped
        "EXAMDATE": ["2018-01-01", "2019-01-01", "2020-01-01"],
    })
    tables = {"DXSUM": df}
    _build_adni_mapping(tables)
    work = tables["DXSUM"]
    assert set(work["__adni_state__"]).issubset({"CN", "MCI", "AD"})
    assert len(work) == 2  # NL row dropped


def test_build_mapping_fail_closed_on_no_valid_dx():
    df = pd.DataFrame({
        "RID": [1, 1], "DIAGNOSIS": ["NL", "Unknown"],
        "EXAMDATE": ["2018-01-01", "2019-01-01"],
    })
    with pytest.raises(ValueError):
        _build_adni_mapping({"DXSUM": df})


def test_adni_mapping_audits_via_tables_to_submission():
    from neurotcs.io import tables_to_submission
    tables = {"DXSUM": _adni_table()}
    mapping = _build_adni_mapping(tables)
    warns: list[str] = []
    sub = tables_to_submission(tables, mapping, warnings=warns)
    out = sub["clinical"]
    assert list(out.columns)[:4] == ["subject_id", "visit", "visit_date", "state"]
    assert set(out["subject_id"]) == {"1", "2"}
    assert set(out["state"]).issubset({"CN", "MCI", "AD"})

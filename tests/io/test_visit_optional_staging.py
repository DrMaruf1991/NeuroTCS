"""v1.83.0 -- visit is OPTIONAL in staging.

tables_to_submission must accept a clinical/biological spec WITHOUT a 'visit'
column and derive visit ordering from the best available key:
  - derive-date path (no usable visit_date): order by visit (legacy) | visit_date | row
  - date-present path (real visit_date): synthesize visit index from chronological order

The visit-PRESENT paths must be byte-identical to the legacy behavior (this is the
invariant-safety guarantee: every existing cohort/adapter supplies visit, so their
audit_ids cannot drift).
"""
from __future__ import annotations

import pandas as pd

from neurotcs.io import tables_to_submission

_STAGING = ("subject_id", "visit", "visit_date", "state")


# ----- derive-date path (no real dates) ------------------------------------- #
def test_derive_visit_present_legacy_unchanged():
    """visit present + no dates -> legacy derive path; output well-formed."""
    df = pd.DataFrame({
        "sid": ["A", "A", "B"], "v": ["bl", "m12", "bl"], "st": ["CN", "MCI", "CN"],
    })
    m = {"clinical": {"sheet": "S", "subject_id": "sid", "visit": "v",
                      "visit_date": None, "state": "st"}}
    out = tables_to_submission({"S": df}, m)["clinical"]
    assert list(out.columns)[:4] == list(_STAGING)
    assert len(out) == 3
    # A's two visits ordered bl < m12 (natural sort), B has one
    a = out[out["subject_id"] == "A"].sort_values("visit_date")
    assert list(a["state"]) == ["CN", "MCI"]


def test_derive_visit_absent_with_date_orders_by_date():
    """no visit column, but a real visit_date -> order by date, derive index."""
    df = pd.DataFrame({
        "sid": ["A", "A", "A"],
        "dt": ["2021-01-01", "2020-01-01", "2022-01-01"],  # out of order on purpose
        "st": ["MCI", "CN", "AD"],
    })
    # visit_date present but we route via derive path by NOT declaring it as the
    # usable date (declare it absent so the derive branch picks it as ordering key)
    m = {"clinical": {"sheet": "S", "subject_id": "sid",
                      "visit_date": "dt", "state": "st"}}  # NO 'visit' key
    warns: list[str] = []
    out = tables_to_submission({"S": df}, m, warnings=warns)["clinical"]
    assert len(out) == 3
    # date-present path is taken (real dt) -> chronological CN, MCI, AD
    assert list(out.sort_values("visit_date")["state"]) == ["CN", "MCI", "AD"]


def test_derive_visit_absent_no_date_row_order():
    """no visit, no date -> derive path, row-order fallback."""
    df = pd.DataFrame({
        "sid": ["A", "A", "A"], "st": ["CN", "MCI", "AD"],
    })
    m = {"clinical": {"sheet": "S", "subject_id": "sid",
                      "visit_date": None, "state": "st"}}  # NO 'visit'
    warns: list[str] = []
    out = tables_to_submission({"S": df}, m, warnings=warns)["clinical"]
    assert len(out) == 3
    # row order preserved -> CN, MCI, AD
    assert list(out["state"]) == ["CN", "MCI", "AD"]
    assert any("derived" in w.lower() for w in warns)


# ----- date-present path (real dates) --------------------------------------- #
def test_datepresent_visit_present_legacy_unchanged():
    """visit + real dates -> legacy date-present path, byte-identical shape."""
    df = pd.DataFrame({
        "sid": ["A", "A"], "v": ["bl", "m12"],
        "dt": ["2020-01-01", "2021-01-01"], "st": ["CN", "MCI"],
    })
    m = {"clinical": {"sheet": "S", "subject_id": "sid", "visit": "v",
                      "visit_date": "dt", "state": "st"}}
    out = tables_to_submission({"S": df}, m)["clinical"]
    assert list(out["visit"]) == ["bl", "m12"]   # real visit preserved verbatim
    assert list(out["state"]) == ["CN", "MCI"]


def test_datepresent_visit_absent_synthesizes_index():
    """real dates, NO visit -> synthesize 1-based index from chronological order."""
    df = pd.DataFrame({
        "sid": ["A", "A", "B"],
        "dt": ["2021-01-01", "2020-01-01", "2020-06-01"],  # A out of order
        "st": ["MCI", "CN", "CN"],
    })
    m = {"clinical": {"sheet": "S", "subject_id": "sid",
                      "visit_date": "dt", "state": "st"}}  # NO 'visit'
    warns: list[str] = []
    out = tables_to_submission({"S": df}, m, warnings=warns)["clinical"]
    a = out[out["subject_id"] == "A"].sort_values("visit_date")
    assert list(a["visit"]) == [1, 2]           # synthesized index, chronological
    assert list(a["state"]) == ["CN", "MCI"]    # 2020 CN before 2021 MCI
    assert any("derived" in w.lower() for w in warns)


# ----- subject_id / state still required ------------------------------------ #
def test_missing_state_still_fails_closed():
    df = pd.DataFrame({"sid": ["A"], "dt": ["2020-01-01"]})
    m = {"clinical": {"sheet": "S", "subject_id": "sid",
                      "visit_date": "dt", "state": "nope"}}
    import pytest
    with pytest.raises(ValueError):
        tables_to_submission({"S": df}, m)


def test_missing_subject_still_fails_closed():
    df = pd.DataFrame({"v": ["bl"], "st": ["CN"]})
    m = {"clinical": {"sheet": "S", "subject_id": "nope",
                      "visit_date": None, "state": "st"}}
    import pytest
    with pytest.raises(ValueError):
        tables_to_submission({"S": df}, m)

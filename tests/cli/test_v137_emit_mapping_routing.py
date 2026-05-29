"""
v1.37.0 — `describe --emit-mapping` smart auto-routing.

The external audit caught: `_scaffold_mapping` previously did "first sheet wins".
On a 5-sheet file [Index, EN, AUDIT_CLINICAL, AUDIT_BIOLOGICAL, BIO], it routed
clinical -> Index (table of contents) and biological -> EN (enrollment, no
biological state). Users had to hand-edit the JSON to point at the right sheets.

These tests verify the v1.37 fix:
  1. Sheet name patterns auto-route AUDIT_CLINICAL -> clinical, AUDIT_BIOLOGICAL
     -> biological (the user's exact case).
  2. TOC / Index sheets are NEVER auto-routed to a data axis.
  3. Column synonyms are auto-detected (clinical_state, biological_stage_ATN,
     examdate, RID, visit_code, etc.).
  4. visit_date == null is GRACEFULLY HANDLED: tables_to_submission derives
     synthetic dates from visit ordering instead of demanding the user invent
     dates by hand.
  5. The legacy canonical-name path (csv with subject_id/visit/visit_date/state)
     keeps working -- no regression.
"""

from __future__ import annotations

import json
import warnings

import pandas as pd
import pytest

from neurotcs.cli import _is_toc_sheet, _scaffold_mapping, _score_sheet_for_axis
from neurotcs.io import describe_tables, tables_to_submission

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# Reproducer of the external-audit broken case
# --------------------------------------------------------------------------- #
def _user_broken_case_tables() -> dict[str, pd.DataFrame]:
    """Exactly the shape the external audit hit:
       - Index: TOC, shape (11, 3), columns [Sheet, Rows, Description]
       - EN: enrollment, no state columns
       - AUDIT_CLINICAL: clinical staging data
       - AUDIT_BIOLOGICAL: biological staging data
       - BIO: biomarker measurements (not staging)
    """
    return {
        "Index": pd.DataFrame({
            "Sheet": ["EN", "AUDIT_CLINICAL", "AUDIT_BIOLOGICAL", "BIO"],
            "Rows":  [120, 240, 240, 480],
            "Description": ["Enrollment", "Clinical staging audit",
                            "Biological staging audit", "Biomarker panel"],
        }),
        "EN": pd.DataFrame({
            "subject_id": ["S1", "S2"],
            "enrollment_date": ["2020-01-01", "2020-02-01"],
            "site": ["A", "B"],
        }),
        "AUDIT_CLINICAL": pd.DataFrame({
            "subject_id":     ["S1", "S1", "S2", "S2"],
            "visit":          [0, 1, 0, 1],
            "visit_date":     ["2020-01-01", "2021-01-01", "2020-02-01", "2021-02-01"],
            "clinical_state": ["CN", "MCI", "MCI", "AD"],
        }),
        "AUDIT_BIOLOGICAL": pd.DataFrame({
            "subject_id":              ["S1", "S1", "S2", "S2"],
            "visit":                   [0, 1, 0, 1],
            "visit_date":              ["2020-01-01", "2021-01-01", "2020-02-01", "2021-02-01"],
            "biological_stage_ATN":    ["A-T-N-", "A+T-N-", "A+T-N-", "A+T+N+"],
        }),
        "BIO": pd.DataFrame({
            "patient_id":       ["S1", "S1", "S2", "S2"],
            "visit_id":         ["v0", "v1", "v0", "v1"],
            "measurement_name": ["ab42", "ab42", "ab42", "ab42"],
            "value":            [500.0, 480.0, 350.0, 280.0],
            "unit":             ["pg/mL"] * 4,
        }),
    }


# --------------------------------------------------------------------------- #
# 1. TOC / Index detection
# --------------------------------------------------------------------------- #
def test_index_sheet_classified_as_toc_by_name():
    info = {"shape": [11, 3], "columns": ["Sheet", "Rows", "Description"]}
    assert _is_toc_sheet("Index", info) is True


def test_index_sheet_classified_as_toc_by_columns_even_if_named_differently():
    info = {"shape": [4, 3], "columns": ["sheet_name", "description"]}
    assert _is_toc_sheet("Manifest", info) is True


def test_audit_clinical_is_NOT_toc():
    info = {"shape": [240, 4],
            "columns": ["subject_id", "visit", "visit_date", "clinical_state"]}
    assert _is_toc_sheet("AUDIT_CLINICAL", info) is False


# --------------------------------------------------------------------------- #
# 2. Sheet name -> axis scoring
# --------------------------------------------------------------------------- #
def test_audit_clinical_scores_highest_for_clinical_axis():
    assert _score_sheet_for_axis("AUDIT_CLINICAL", "clinical") >= 90
    # AND scores 0 for biological -- "audit_clinical" should not match biological
    assert _score_sheet_for_axis("AUDIT_CLINICAL", "biological") == 0


def test_audit_biological_scores_highest_for_biological_axis():
    assert _score_sheet_for_axis("AUDIT_BIOLOGICAL", "biological") >= 90
    assert _score_sheet_for_axis("AUDIT_BIOLOGICAL", "clinical") == 0


def test_plain_bio_does_not_dominate_audit_biological():
    """'BIO' alone is too vague to be the biological staging sheet when
    'AUDIT_BIOLOGICAL' is also in the file. AUDIT_BIOLOGICAL must win."""
    bio_score = _score_sheet_for_axis("BIO", "biological")
    audit_bio_score = _score_sheet_for_axis("AUDIT_BIOLOGICAL", "biological")
    assert audit_bio_score > bio_score


def test_index_sheet_scores_0_for_both_axes():
    # not directly relevant to the scorer (which doesn't know about TOC), but
    # the scaffolder skips TOC sheets before scoring, so this stays defensive.
    # "Index" should not be a substring that the scorer happily matches against.
    assert _score_sheet_for_axis("Index", "clinical") == 0
    assert _score_sheet_for_axis("Index", "biological") == 0


# --------------------------------------------------------------------------- #
# 3. _scaffold_mapping on the EXACT broken case from the external audit
# --------------------------------------------------------------------------- #
def test_user_broken_case_routes_correctly():
    """The audit's exact failure: AUDIT_CLINICAL -> clinical, AUDIT_BIOLOGICAL ->
    biological. Index must NOT be the clinical sheet."""
    tables = _user_broken_case_tables()
    mapping = _scaffold_mapping(describe_tables(tables))

    assert mapping["clinical"]["sheet"] == "AUDIT_CLINICAL", (
        f"Expected AUDIT_CLINICAL, got {mapping['clinical']['sheet']!r}. "
        "This is the bug the external audit caught -- 'first sheet wins' "
        "would route to Index here."
    )
    assert mapping["biological"]["sheet"] == "AUDIT_BIOLOGICAL"
    # Index must not appear as a data axis sheet
    assert mapping["clinical"]["sheet"] != "Index"
    assert mapping["biological"]["sheet"] != "Index"


def test_user_broken_case_detects_clinical_state_column():
    tables = _user_broken_case_tables()
    mapping = _scaffold_mapping(describe_tables(tables))
    # clinical_state is a synonym of state -- auto-detection should find it
    assert mapping["clinical"]["state"] == "clinical_state"
    # subject_id is canonical -> exact match
    assert mapping["clinical"]["subject_id"] == "subject_id"


def test_user_broken_case_detects_biological_stage_ATN_column():
    tables = _user_broken_case_tables()
    mapping = _scaffold_mapping(describe_tables(tables))
    assert mapping["biological"]["state"] == "biological_stage_ATN"


def test_user_broken_case_no_FILL_placeholders_in_axes():
    """The whole point of v1.37: a typical user dataset should produce ZERO
    <FILL:...> placeholders in the clinical and biological specs."""
    tables = _user_broken_case_tables()
    mapping = _scaffold_mapping(describe_tables(tables))
    for axis in ("clinical", "biological"):
        for k, v in mapping[axis].items():
            if v is None:  # null visit_date is allowed (derivation will run)
                continue
            assert not (isinstance(v, str) and v.startswith("<FILL:")), (
                f"{axis}.{k} = {v!r} -- this is exactly the friction we removed in v1.37"
            )


# --------------------------------------------------------------------------- #
# 4. visit_date derivation when data has no date column
# --------------------------------------------------------------------------- #
def test_visit_date_null_in_scaffold_when_no_date_column():
    """A sheet with no date column produces visit_date=null in the scaffold,
    NOT a <FILL:visit_date> placeholder that demands manual editing."""
    tables = {
        "AUDIT_CLINICAL": pd.DataFrame({
            "RID": ["S1", "S1", "S2"],
            "visit_code": [0, 1, 0],
            "diagnosis": ["CN", "MCI", "CN"],
            # NO date column at all
        }),
    }
    mapping = _scaffold_mapping(describe_tables(tables))
    assert mapping["clinical"]["sheet"] == "AUDIT_CLINICAL"
    assert mapping["clinical"]["subject_id"] == "RID"  # synonym match
    assert mapping["clinical"]["visit"] == "visit_code"  # synonym match
    assert mapping["clinical"]["state"] == "diagnosis"  # synonym match
    # visit_date: no synonym matches -> null, NOT a FILL placeholder
    assert mapping["clinical"]["visit_date"] is None


def test_null_visit_date_derives_synthetic_dates_at_audit_time():
    """tables_to_submission must derive visit_date from visit ordering when null."""
    tables = {
        "AUDIT_CLINICAL": pd.DataFrame({
            "subject_id": ["S1", "S1", "S2", "S2"],
            "visit":      [0, 1, 0, 1],
            "state":      ["CN", "MCI", "MCI", "AD"],
            # NO visit_date column
        }),
    }
    mapping = {
        "clinical": {
            "sheet": "AUDIT_CLINICAL",
            "subject_id": "subject_id", "visit": "visit",
            "visit_date": None,  # signal: derive from visit order
            "state": "state",
        }
    }
    sub = tables_to_submission(tables, mapping)
    # visit_date must be present + a real date type + monotone within each subject
    clin = sub["clinical"]
    assert "visit_date" in clin.columns
    assert pd.api.types.is_datetime64_any_dtype(clin["visit_date"])
    for sid, grp in clin.groupby("subject_id"):
        dates = grp.sort_values("visit")["visit_date"].tolist()
        assert dates == sorted(dates), (
            f"Derived dates for {sid} not monotone with visit order: {dates}"
        )


def test_FILL_visit_date_placeholder_also_derives():
    """Even if the scaffolder wrote <FILL:visit_date> (older mapping or partial
    edit), tables_to_submission should derive rather than crash."""
    tables = {
        "S": pd.DataFrame({
            "subject_id": ["A", "A"], "visit": [0, 1], "state": ["CN", "MCI"],
        }),
    }
    mapping = {"clinical": {
        "sheet": "S", "subject_id": "subject_id", "visit": "visit",
        "visit_date": "<FILL:visit_date>", "state": "state",
    }}
    sub = tables_to_submission(tables, mapping)
    assert "clinical" in sub
    assert pd.api.types.is_datetime64_any_dtype(sub["clinical"]["visit_date"])


# --------------------------------------------------------------------------- #
# 5. Regression: legacy canonical-name path (existing test_cli.py case)
# --------------------------------------------------------------------------- #
def test_legacy_canonical_csv_still_works_no_regression():
    """A single-sheet CSV with canonical column names must still scaffold the
    same as before -- the existing test_describe_emits_mapping must keep passing."""
    tables = {
        "d": pd.DataFrame({
            "subject_id": ["P1"] * 3,
            "visit": [0, 1, 2],
            "visit_date": pd.date_range("2020-01-01", periods=3, freq="365D").astype(str),
            "state": ["CN", "MCI", "AD"],
        }),
    }
    mapping = _scaffold_mapping(describe_tables(tables))
    assert mapping["clinical"]["sheet"] == "d"
    assert mapping["clinical"]["subject_id"] == "subject_id"
    assert mapping["clinical"]["visit_date"] == "visit_date"  # not null -- exists in data
    assert mapping["clinical"]["state"] == "state"
    assert mapping["ranges"] == []


# --------------------------------------------------------------------------- #
# 6. _notes field documents what happened (so users understand the routing)
# --------------------------------------------------------------------------- #
def test_scaffold_emits_notes_documenting_auto_routing():
    tables = _user_broken_case_tables()
    mapping = _scaffold_mapping(describe_tables(tables))
    notes = mapping.get("_notes")
    assert isinstance(notes, list) and len(notes) >= 3
    joined = " ".join(notes).lower()
    # Notes should mention auto-routing happened
    assert "auto-rout" in joined or "auto rout" in joined
    # And mention TOC / Index exclusion
    assert "toc" in joined or "index" in joined


# --------------------------------------------------------------------------- #
# 7. End-to-end on the user's broken case via the CLI surface
# --------------------------------------------------------------------------- #
def test_end_to_end_describe_emits_correct_mapping_for_broken_case(tmp_path):
    """The bottom-line user test: dump the broken case to xlsx, run describe
    --emit-mapping, read the JSON, and confirm it points at the right sheets."""
    pytest.importorskip("openpyxl")  # for xlsx write
    tables = _user_broken_case_tables()
    xlsx_path = tmp_path / "user_data.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
        for name, df in tables.items():
            df.to_excel(xw, sheet_name=name, index=False)

    from neurotcs.cli import main
    map_path = tmp_path / "mapping.json"
    rc = main(["describe", str(xlsx_path), "--emit-mapping", str(map_path)])
    assert rc == 0
    loaded = json.loads(map_path.read_text())
    assert loaded["clinical"]["sheet"] == "AUDIT_CLINICAL"
    assert loaded["biological"]["sheet"] == "AUDIT_BIOLOGICAL"
    assert loaded["clinical"]["state"] == "clinical_state"
    assert loaded["biological"]["state"] == "biological_stage_ATN"

"""Tests for neurotcs.io.cross_sheet_autowire -- the universal, deterministic,
fail-closed resolver that maps raw cohort sheets to cross-sheet ROLE views."""
from __future__ import annotations

import pandas as pd

from neurotcs.io.cross_sheet_autowire import (
    CrossSheetResolution,
    build_cross_sheet_submission,
)


def _patients_sheet() -> pd.DataFrame:
    return pd.DataFrame({
        "subject_id": ["P1", "P2"],
        "apoe_genotype": ["e3/e4", "e3/e3"],
        "sex": ["M", "F"],
        "dx_group": ["AD", "CN"],
    })


def _clinical_sheet() -> pd.DataFrame:
    return pd.DataFrame({
        "subject_id": ["P1", "P1", "P2"],
        "visit": [0, 1, 0],
        "clinical_state": ["MCI", "AD", "CN"],
    })


def _amyloid_sheet() -> pd.DataFrame:
    return pd.DataFrame({
        "subject_id": ["P1", "P1", "P2"],
        "visit": [0, 1, 0],
        "centiloid_value": [88.0, 92.0, 4.0],
        "amyloid_status": ["positive", "positive", "negative"],
    })


def _tau_sheet() -> pd.DataFrame:
    return pd.DataFrame({
        "subject_id": ["P1", "P2"],
        "visit": [0, 0],
        "tau_pet_suvr": [1.8, 1.0],
        "tau_visual_read": ["negative", "negative"],
    })


class TestRoleClassification:

    def test_patient_sheet_becomes_patients_role(self):
        sub, res = build_cross_sheet_submission({"EN": _patients_sheet()})
        assert "patients" in sub
        assert "EN" in res.roles["patients"]
        # apoe_genotype canonicalized + identity -> patient_id
        assert "apoe_genotype" in sub["patients"][0]
        assert "patient_id" in sub["patients"][0]

    def test_clinical_state_sheet_becomes_predictions(self):
        sub, res = build_cross_sheet_submission({"QS": _clinical_sheet()})
        assert "predictions" in sub
        assert "QS" in res.roles["predictions"]
        # clinical_state canonicalized to predicted_state
        assert "predicted_state" in sub["predictions"][0]

    def test_measurement_sheet_becomes_biomarkers(self):
        sub, res = build_cross_sheet_submission({"AM": _amyloid_sheet()})
        assert "biomarkers" in sub
        assert "AM" in res.roles["biomarkers"]
        # centiloid_value canonicalized to amyloid_centiloid
        assert "amyloid_centiloid" in sub["biomarkers"][0]

    def test_biological_state_sheet_is_unresolved(self):
        bio = pd.DataFrame({
            "subject_id": ["P1", "P2"],
            "visit": [0, 0],
            "state": ["A+T+N+", "A-T-N-"],
        })
        sub, res = build_cross_sheet_submission({"BIO": bio})
        # biological A/T/N is audited by staging_biological, NOT cross-sheet
        assert "BIO" in [s for s, _ in res.unresolved]
        assert "predictions" not in sub or not sub.get("predictions")

    def test_index_sheet_is_recognized_non_data(self):
        idx = pd.DataFrame({"Sheet": ["EN"], "Rows": [2], "Description": ["x"]})
        _, res = build_cross_sheet_submission({"Index": idx})
        reasons = {s: r for s, r in res.unresolved}
        assert "Index" in reasons
        assert "non-data" in reasons["Index"]


class TestBiomarkerMerge:

    def test_multiple_measurement_sheets_merge_on_identity(self):
        tables = {"AM": _amyloid_sheet(), "TP": _tau_sheet()}
        sub, _ = build_cross_sheet_submission(tables)
        bio = sub["biomarkers"]
        # one row per (patient, visit); amyloid + tau columns coexist
        keys = set(bio[0].keys())
        assert "amyloid_centiloid" in keys
        assert "tau_pet_neocortical_uptake_ratio_flortaucipir" in keys
        # P1 visit 0 carries BOTH modalities
        p1v0 = [r for r in bio
                if r.get("patient_id") == "P1" and r.get("visit_id") == 0]
        assert len(p1v0) == 1
        assert p1v0[0]["amyloid_centiloid"] == 88.0
        assert p1v0[0]["tau_pet_neocortical_uptake_ratio_flortaucipir"] == 1.8

    def test_tau_visual_read_negative_flag_derived(self):
        sub, _ = build_cross_sheet_submission({"TP": _tau_sheet()})
        bio = sub["biomarkers"]
        p1 = [r for r in bio if r.get("patient_id") == "P1"][0]
        assert p1["tau_visual_read_negative_flag"] == 1.0


class TestFailClosedAndDeterminism:

    def test_output_is_list_of_dicts_not_dataframe(self):
        # The engine's _iter_rows accepts only list/dict; a DataFrame yields
        # zero rows. The resolver MUST emit records.
        sub, _ = build_cross_sheet_submission({"AM": _amyloid_sheet()})
        assert isinstance(sub["biomarkers"], list)
        assert all(isinstance(r, dict) for r in sub["biomarkers"])

    def test_resolution_is_audit_trail(self):
        _, res = build_cross_sheet_submission({"EN": _patients_sheet()})
        assert isinstance(res, CrossSheetResolution)
        assert any("patients" in line for line in res.summary_lines())

    def test_deterministic_same_input_same_roles(self):
        tables = {"EN": _patients_sheet(), "QS": _clinical_sheet(),
                  "AM": _amyloid_sheet()}
        s1, r1 = build_cross_sheet_submission(tables)
        s2, r2 = build_cross_sheet_submission(tables)
        assert r1.roles == r2.roles
        assert s1["biomarkers"] == s2["biomarkers"]

    def test_empty_sheet_surfaced_not_crashed(self):
        empty = pd.DataFrame()
        _, res = build_cross_sheet_submission({"EMPTY": empty})
        assert "EMPTY" in [s for s, _ in res.unresolved]

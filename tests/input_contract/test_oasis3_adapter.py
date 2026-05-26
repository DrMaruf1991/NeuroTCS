"""
Unit tests for the OASIS-3 adapter (NeuroTCS v1.3.0).

Tests cover:
  - cdr_to_state mapping correctness (Morris 1993)
  - dx1_to_state best-effort mapping
  - hash_patient_id determinism
  - load_oasis3_trajectories: dx1 disagreement counting, NaN handling,
    days_to_visit → interval preservation
  - End-to-end build of conforming predictions / patients / manifest

These do NOT require real OASIS-3 data; they synthesize fixtures.
For the locked-invariant real-data test see tests/audit_core/test_real_oasis3_audit.py.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

from neurotcs.input_contract.v1_1.adapters.adapter_oasis3 import (
    build_manifest,
    build_patients,
    build_predictions,
    cdr_to_state,
    dx1_to_state,
    hash_patient_id,
    load_oasis3_trajectories,
)

PASS = "\033[32m\u2713\033[0m"
FAIL = "\033[31m\u2717\033[0m"


# ------------------------------------------------------------------
# cdr_to_state tests (Morris 1993)
# ------------------------------------------------------------------

def test_cdr_zero_is_cn():
    assert cdr_to_state(0.0) == "CN"
    print(f"  {PASS} test_cdr_zero_is_cn")


def test_cdr_half_is_mci():
    assert cdr_to_state(0.5) == "MCI"
    print(f"  {PASS} test_cdr_half_is_mci")


def test_cdr_one_is_ad():
    assert cdr_to_state(1.0) == "AD"
    print(f"  {PASS} test_cdr_one_is_ad")


def test_cdr_two_is_ad():
    assert cdr_to_state(2.0) == "AD"
    print(f"  {PASS} test_cdr_two_is_ad")


def test_cdr_three_is_ad():
    assert cdr_to_state(3.0) == "AD"
    print(f"  {PASS} test_cdr_three_is_ad")


def test_cdr_nan_returns_none():
    assert cdr_to_state(float("nan")) is None
    print(f"  {PASS} test_cdr_nan_returns_none")


def test_cdr_none_returns_none():
    assert cdr_to_state(None) is None
    print(f"  {PASS} test_cdr_none_returns_none")


def test_cdr_negative_returns_none():
    assert cdr_to_state(-1.0) is None
    print(f"  {PASS} test_cdr_negative_returns_none")


def test_cdr_non_numeric_string_returns_none():
    assert cdr_to_state("unknown") is None
    print(f"  {PASS} test_cdr_non_numeric_string_returns_none")


# ------------------------------------------------------------------
# dx1_to_state tests
# ------------------------------------------------------------------

def test_dx1_cognitively_normal():
    assert dx1_to_state("Cognitively normal") == "CN"
    print(f"  {PASS} test_dx1_cognitively_normal")


def test_dx1_mci_variants():
    assert dx1_to_state("MCI") == "MCI"
    assert dx1_to_state("Amnestic MCI multi-domain") == "MCI"
    assert dx1_to_state("Mild Cognitive Impairment") == "MCI"
    print(f"  {PASS} test_dx1_mci_variants")


def test_dx1_ad_dementia():
    assert dx1_to_state("AD Dementia") == "AD"
    assert dx1_to_state("Alzheimer's disease") == "AD"
    print(f"  {PASS} test_dx1_ad_dementia")


def test_dx1_non_ad_dementia_returns_none():
    # Lewy body, frontotemporal etc. should NOT be coerced into AD staging
    assert dx1_to_state("Dementia with Lewy bodies") is None
    assert dx1_to_state("Frontotemporal dementia") is None
    assert dx1_to_state("Vascular dementia") is None
    print(f"  {PASS} test_dx1_non_ad_dementia_returns_none")


def test_dx1_missing_returns_none():
    assert dx1_to_state(None) is None
    assert dx1_to_state(".") is None
    assert dx1_to_state("") is None
    print(f"  {PASS} test_dx1_missing_returns_none")


# ------------------------------------------------------------------
# hash_patient_id tests
# ------------------------------------------------------------------

def test_hash_patient_id_deterministic():
    a = hash_patient_id("OAS30001")
    b = hash_patient_id("OAS30001")
    assert a == b
    print(f"  {PASS} test_hash_patient_id_deterministic ({a})")


def test_hash_patient_id_different_inputs_different_outputs():
    a = hash_patient_id("OAS30001")
    b = hash_patient_id("OAS30002")
    assert a != b
    print(f"  {PASS} test_hash_patient_id_different_inputs_different_outputs")


def test_hash_patient_id_format():
    h = hash_patient_id("OAS30001")
    assert h.startswith("OASIS3_")
    assert len(h) == len("OASIS3_") + 16
    print(f"  {PASS} test_hash_patient_id_format")


# ------------------------------------------------------------------
# load_oasis3_trajectories integration tests with synthetic fixture
# ------------------------------------------------------------------

def _write_synthetic_udsb4(tmpdir: Path) -> Path:
    """Write a minimal UDSb4-like CSV fixture for testing."""
    df = pd.DataFrame({
        "OASISID": [
            "OAS_TEST1", "OAS_TEST1", "OAS_TEST1",
            "OAS_TEST2", "OAS_TEST2",
            "OAS_TEST3", "OAS_TEST3",
            "OAS_TEST4",  # only 1 visit, no transitions
            "OAS_TEST5", "OAS_TEST5",  # disagreement case
        ],
        "days_to_visit": [
            0, 400, 800,
            0, 365,
            0, 500,
            0,
            0, 365,
        ],
        "CDRTOT": [
            0.0, 0.5, 1.0,    # CN -> MCI -> AD admissible
            0.5, 0.0,         # MCI -> CN with 365d (>180d threshold = admissible)
            0.0, 1.0,         # CN -> AD admissible (>=365d)
            0.0,              # singleton
            0.0, 0.5,         # CN -> MCI; but dx1 says CN for both = disagreement at visit 2
        ],
        "dx1": [
            "Cognitively normal", "MCI", "AD Dementia",
            "MCI", "Cognitively normal",
            "Cognitively normal", "AD Dementia",
            "Cognitively normal",
            "Cognitively normal", "Cognitively normal",  # 2nd row disagrees with CDR=0.5
        ],
    })
    p = tmpdir / "UDSb4_test.csv"
    df.to_csv(p, index=False)
    return p


def test_load_oasis3_trajectories_smoke():
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_synthetic_udsb4(Path(tmp))
        trajectories, report = load_oasis3_trajectories(p)
        assert report.raw_rows == 10
        assert report.raw_subjects == 5
        # Subject 4 has only 1 visit — dropped from trajectories (0 transitions)
        # Other 4 subjects scored
        assert report.n_trajectories == 5  # singleton kept but contributes 0 transitions
        # TEST1: 2 transitions, TEST2: 1, TEST3: 1, TEST4: 0 (singleton),
        # TEST5: 1 → total 5 transitions across 4 trajectories with >=1 transition
        # (singleton TEST4 contributes 0).
        total_tx = sum(t.num_transitions for t in trajectories)
        assert total_tx == 5, f"expected 5 transitions, got {total_tx}"
        print(f"  {PASS} test_load_oasis3_trajectories_smoke "
              f"({len(trajectories)} trajectories, {total_tx} transitions)")


def test_load_oasis3_flags_dx1_disagreement():
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_synthetic_udsb4(Path(tmp))
        _, report = load_oasis3_trajectories(p, flag_dx1_disagreement=True)
        # Subject 5 visit 2: CDR=0.5 (MCI) vs dx1="Cognitively normal" (CN) = 1 disagreement
        assert report.dx1_disagreements == 1
        assert len(report.dx1_disagreement_examples) == 1
        ex = report.dx1_disagreement_examples[0]
        assert ex["cdr_state"] == "MCI"
        assert ex["dx1_state"] == "CN"
        print(f"  {PASS} test_load_oasis3_flags_dx1_disagreement")


def test_load_oasis3_disagreement_does_not_drop_rows():
    """dx1 disagreement is diagnostic-only; CDR remains primary."""
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_synthetic_udsb4(Path(tmp))
        # Same row count whether or not flagging is enabled
        _, with_flag = load_oasis3_trajectories(p, flag_dx1_disagreement=True)
        _, no_flag = load_oasis3_trajectories(p, flag_dx1_disagreement=False)
        assert with_flag.n_transitions == no_flag.n_transitions
        print(f"  {PASS} test_load_oasis3_disagreement_does_not_drop_rows")


def test_load_oasis3_preserves_intervals():
    with tempfile.TemporaryDirectory() as tmp:
        p = _write_synthetic_udsb4(Path(tmp))
        trajectories, _ = load_oasis3_trajectories(p)
        # Find subject TEST1 (its hash-id)
        t1 = next(t for t in trajectories if t.num_transitions == 2 and t.states == ("CN", "MCI", "AD"))
        intervals = [
            (t1.dates[1] - t1.dates[0]).days,
            (t1.dates[2] - t1.dates[1]).days,
        ]
        assert intervals == [400, 400], f"got {intervals}"
        print(f"  {PASS} test_load_oasis3_preserves_intervals (intervals: {intervals})")


def test_load_oasis3_drops_nan_cdr():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        df = pd.DataFrame({
            "OASISID": ["OAS_X", "OAS_X", "OAS_X"],
            "days_to_visit": [0, 365, 730],
            "CDRTOT": [0.0, float("nan"), 0.5],
            "dx1": ["Cognitively normal", "Cognitively normal", "MCI"],
        })
        p = tmp / "UDSb4_nan.csv"
        df.to_csv(p, index=False)
        trajectories, report = load_oasis3_trajectories(p)
        # NaN row dropped; remaining 2 visits build 1 transition
        assert report.rows_after_dropna == 2
        assert sum(t.num_transitions for t in trajectories) == 1
        print(f"  {PASS} test_load_oasis3_drops_nan_cdr")


def test_load_oasis3_missing_file_raises():
    try:
        load_oasis3_trajectories("/nonexistent/path/UDSb4.csv")
        assert False
    except FileNotFoundError:
        pass
    print(f"  {PASS} test_load_oasis3_missing_file_raises")


def test_load_oasis3_missing_required_column_raises():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Missing CDRTOT
        df = pd.DataFrame({
            "OASISID": ["OAS_X"],
            "days_to_visit": [0],
        })
        p = tmp / "bad.csv"
        df.to_csv(p, index=False)
        try:
            load_oasis3_trajectories(p)
            assert False
        except KeyError as e:
            assert "CDRTOT" in str(e)
        print(f"  {PASS} test_load_oasis3_missing_required_column_raises")


# ------------------------------------------------------------------
# Submission-export tests (parallel to ADNI adapter)
# ------------------------------------------------------------------

def test_build_predictions_filters_to_ge2_visits():
    udsb4 = pd.DataFrame({
        "OASISID": ["A", "A", "B"],  # B has only 1 visit
        "days_to_visit": [0, 365, 0],
        "CDRTOT": [0.0, 0.5, 0.0],
    })
    preds = build_predictions(udsb4)
    assert preds["patient_id"].nunique() == 1  # only A retained
    print(f"  {PASS} test_build_predictions_filters_to_ge2_visits")


def test_build_predictions_has_required_columns():
    udsb4 = pd.DataFrame({
        "OASISID": ["A", "A"],
        "days_to_visit": [0, 365],
        "CDRTOT": [0.0, 0.5],
    })
    preds = build_predictions(udsb4)
    required = {"patient_id", "visit_id", "visit_timestamp",
                 "predicted_state", "uncertainty", "treatment_flags"}
    assert required.issubset(set(preds.columns))
    print(f"  {PASS} test_build_predictions_has_required_columns")


def test_build_manifest_has_citation_block():
    preds = pd.DataFrame({
        "patient_id": ["A", "A"],
        "visit_timestamp": ["2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z"],
    })
    m = build_manifest(preds, submission_id="test")
    assert m["neurotcs_contract_version"] == "1.1.0"
    assert "citation" in m
    assert "Morris" in m["citation"]["staging"]
    assert "LaMontagne" in m["citation"]["cohort"]
    print(f"  {PASS} test_build_manifest_has_citation_block")


def test_build_patients_minimal():
    preds = pd.DataFrame({"patient_id": ["A", "A", "B"]})
    pat = build_patients(preds)
    assert set(pat["patient_id"]) == {"A", "B"}
    assert "sex" in pat.columns
    assert "site_id" in pat.columns
    print(f"  {PASS} test_build_patients_minimal")


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

def run_all():
    tests = [
        # cdr_to_state
        test_cdr_zero_is_cn,
        test_cdr_half_is_mci,
        test_cdr_one_is_ad,
        test_cdr_two_is_ad,
        test_cdr_three_is_ad,
        test_cdr_nan_returns_none,
        test_cdr_none_returns_none,
        test_cdr_negative_returns_none,
        test_cdr_non_numeric_string_returns_none,
        # dx1_to_state
        test_dx1_cognitively_normal,
        test_dx1_mci_variants,
        test_dx1_ad_dementia,
        test_dx1_non_ad_dementia_returns_none,
        test_dx1_missing_returns_none,
        # hash_patient_id
        test_hash_patient_id_deterministic,
        test_hash_patient_id_different_inputs_different_outputs,
        test_hash_patient_id_format,
        # load_oasis3_trajectories
        test_load_oasis3_trajectories_smoke,
        test_load_oasis3_flags_dx1_disagreement,
        test_load_oasis3_disagreement_does_not_drop_rows,
        test_load_oasis3_preserves_intervals,
        test_load_oasis3_drops_nan_cdr,
        test_load_oasis3_missing_file_raises,
        test_load_oasis3_missing_required_column_raises,
        # submission export
        test_build_predictions_filters_to_ge2_visits,
        test_build_predictions_has_required_columns,
        test_build_manifest_has_citation_block,
        test_build_patients_minimal,
    ]
    print(f"\nNeuroTCS OASIS-3 adapter tests — running {len(tests)}:\n")
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  {FAIL} {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  {FAIL} {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)

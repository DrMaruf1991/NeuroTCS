"""Unit tests for the MIRIAD adapter.

Built with synthetic CSVs that mirror the column structure of real
MIRIAD exports from the XNAT database. Tests verify:

  - MMSE-based state staging (Folstein 1975 thresholds)
  - Group↔MMSE disagreement diagnostics (analogous to OASIS-3 dx1 flagging)
  - Same-session rescan detection and exclusion from longitudinal cohort
  - Test-retest pair construction with bit-identical state when MMSE
    is per-subject (zero noise → all pairs admissible)
  - Defensive column-name resolution (multiple XNAT export variants)
  - End-to-end audit pipeline integration
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from neurotcs import audit, load_rulepack
from neurotcs.input_contract.v1_1.adapters.adapter_miriad import (
    MMSE_THRESHOLD_AD,
    MMSE_THRESHOLD_CN,
    group_to_state,
    hash_patient_id,
    infer_miriad_group_from_subject_id,
    load_miriad_test_retest_pairs,
    load_miriad_trajectories,
    mmse_to_state,
    parse_miriad_visit_number,
)

PASS = "\033[32m\u2713\033[0m"


# ---------- Synthetic CSV builders ----------

def _write_clinical(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_sessions(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_subjects(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


# ---------- MMSE → state mapping tests ----------

def test_mmse_to_state_thresholds():
    """Folstein 1975 / Tombaugh & McIntyre 1992 thresholds."""
    assert mmse_to_state(30) == "CN"
    assert mmse_to_state(MMSE_THRESHOLD_CN) == "CN"
    assert mmse_to_state(MMSE_THRESHOLD_CN - 1) == "MCI"
    assert mmse_to_state(20) == "MCI"
    assert mmse_to_state(MMSE_THRESHOLD_AD) == "MCI"
    assert mmse_to_state(MMSE_THRESHOLD_AD - 1) == "AD"
    assert mmse_to_state(0) == "AD"


def test_mmse_to_state_invalid_inputs():
    """Out-of-range and NaN MMSE values must return None."""
    assert mmse_to_state(None) is None
    assert mmse_to_state(-1) is None
    assert mmse_to_state(31) is None
    assert mmse_to_state(float("nan")) is None
    assert mmse_to_state("not a number") is None


def test_group_to_state_recognition():
    """Group → state mapping recognizes standard MIRIAD labels."""
    assert group_to_state("AD") == "AD"
    assert group_to_state("ad") == "AD"
    assert group_to_state("Alzheimer") == "AD"
    assert group_to_state("control") == "CN"
    assert group_to_state("CONTROLS") == "CN"
    assert group_to_state("HC") == "CN"
    assert group_to_state("unknown") is None
    assert group_to_state(None) is None


def test_hash_patient_id_stable_and_prefixed():
    a = hash_patient_id("MIRIAD_001")
    b = hash_patient_id("MIRIAD_001")
    assert a == b
    assert a.startswith("MIRIAD_")
    assert hash_patient_id("MIRIAD_001") != hash_patient_id("MIRIAD_002")


# ---------- Longitudinal load tests ----------

def test_load_miriad_trajectories_basic(tmp_path: Path):
    """Minimal happy-path load with 2 AD subjects, 3 visits each."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    subjects_csv = tmp_path / "Subjects.csv"

    _write_sessions(sessions_csv, [
        {"Subject": "MIRIAD_001", "Age": 70.00, "Visit": "v1"},
        {"Subject": "MIRIAD_001", "Age": 70.50, "Visit": "v2"},
        {"Subject": "MIRIAD_001", "Age": 71.00, "Visit": "v3"},
        {"Subject": "MIRIAD_002", "Age": 65.00, "Visit": "v1"},
        {"Subject": "MIRIAD_002", "Age": 65.50, "Visit": "v2"},
        {"Subject": "MIRIAD_002", "Age": 66.00, "Visit": "v3"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "MIRIAD_001", "Visit": "v1", "MMSE": 22},
        {"Subject": "MIRIAD_001", "Visit": "v2", "MMSE": 18},
        {"Subject": "MIRIAD_001", "Visit": "v3", "MMSE": 14},
        {"Subject": "MIRIAD_002", "Visit": "v1", "MMSE": 29},
        {"Subject": "MIRIAD_002", "Visit": "v2", "MMSE": 28},
        {"Subject": "MIRIAD_002", "Visit": "v3", "MMSE": 29},
    ])
    _write_subjects(subjects_csv, [
        {"Subject": "MIRIAD_001", "Group": "AD"},
        {"Subject": "MIRIAD_002", "Group": "control"},
    ])

    trajectories, report = load_miriad_trajectories(
        clinical_csv, sessions_csv, subjects_csv,
    )
    assert len(trajectories) == 2
    assert report.n_transitions == 4  # 2 transitions per subject
    assert report.raw_sessions_rows == 6
    assert report.raw_clinical_rows == 6
    assert report.unmappable_mmse == 0


def test_load_miriad_excludes_test_retest_rescans_by_default(tmp_path: Path):
    """Same-visit-label scans are deduplicated from the longitudinal cohort."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    _write_sessions(sessions_csv, [
        # MIRIAD_001 visit v1 has TWO back-to-back scans
        {"Subject": "MIRIAD_001", "Age": 70.00, "Visit": "v1"},
        {"Subject": "MIRIAD_001", "Age": 70.00, "Visit": "v1"},  # rescan
        {"Subject": "MIRIAD_001", "Age": 70.50, "Visit": "v2"},
        {"Subject": "MIRIAD_001", "Age": 71.00, "Visit": "v3"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "MIRIAD_001", "Visit": "v1", "MMSE": 22},
        {"Subject": "MIRIAD_001", "Visit": "v2", "MMSE": 20},
        {"Subject": "MIRIAD_001", "Visit": "v3", "MMSE": 18},
    ])
    trajectories, report = load_miriad_trajectories(
        clinical_csv, sessions_csv,
    )
    # The rescan at v1 should be excluded → exactly 3 visits for MIRIAD_001
    assert report.n_test_retest_visits_excluded == 1
    assert len(trajectories) == 1
    assert trajectories[0].num_transitions == 2


def test_load_miriad_group_mmse_disagreement_flagged(tmp_path: Path):
    """When Subjects.group says AD but MMSE-derived state is CN, flag it."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    subjects_csv = tmp_path / "Subjects.csv"

    _write_sessions(sessions_csv, [
        # subject labeled AD has high MMSE (CN-equivalent)
        {"Subject": "MIRIAD_DISAGREE", "Age": 70.00, "Visit": "v1"},
        {"Subject": "MIRIAD_DISAGREE", "Age": 70.50, "Visit": "v2"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "MIRIAD_DISAGREE", "Visit": "v1", "MMSE": 29},
        {"Subject": "MIRIAD_DISAGREE", "Visit": "v2", "MMSE": 28},
    ])
    _write_subjects(subjects_csv, [
        {"Subject": "MIRIAD_DISAGREE", "Group": "AD"},
    ])

    _, report = load_miriad_trajectories(
        clinical_csv, sessions_csv, subjects_csv,
    )
    assert report.group_mmse_disagreements == 2  # both visits flagged
    assert len(report.group_mmse_disagreement_examples) >= 1
    ex = report.group_mmse_disagreement_examples[0]
    assert ex["group_state"] == "AD"
    assert ex["mmse_state"] == "CN"


def test_load_miriad_invalid_mmse_dropped(tmp_path: Path):
    """Out-of-range MMSE values are counted and the rows dropped."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    _write_sessions(sessions_csv, [
        {"Subject": "MIRIAD_001", "Age": 70.00, "Visit": "v1"},
        {"Subject": "MIRIAD_001", "Age": 70.50, "Visit": "v2"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "MIRIAD_001", "Visit": "v1", "MMSE": 99},   # invalid
        {"Subject": "MIRIAD_001", "Visit": "v2", "MMSE": 25},
    ])
    _, report = load_miriad_trajectories(clinical_csv, sessions_csv)
    assert report.out_of_range_mmse == 1
    assert report.unmappable_mmse >= 1


def test_load_miriad_alternative_column_names(tmp_path: Path):
    """Adapter must handle XNAT-export variants of column names."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    # Use lowercase / alternative names
    pd.DataFrame([
        {"subject_id": "MIRIAD_001", "age_at_scan": 70.00, "label": "v1"},
        {"subject_id": "MIRIAD_001", "age_at_scan": 70.50, "label": "v2"},
    ]).to_csv(sessions_csv, index=False)
    pd.DataFrame([
        {"subject_id": "MIRIAD_001", "label": "v1", "mmse_score": 22},
        {"subject_id": "MIRIAD_001", "label": "v2", "mmse_score": 20},
    ]).to_csv(clinical_csv, index=False)

    trajectories, _ = load_miriad_trajectories(clinical_csv, sessions_csv)
    assert len(trajectories) == 1
    assert trajectories[0].num_transitions == 1


# ---------- Test-retest pair tests ----------

def test_load_miriad_test_retest_pairs_basic(tmp_path: Path):
    """Same-day rescans surface as length-2 trajectories."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    _write_sessions(sessions_csv, [
        # 3 subjects, each with a back-to-back rescan at the same age
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S2", "Age": 65.00, "Visit": "v1"},
        {"Subject": "S2", "Age": 65.00, "Visit": "v1"},
        {"Subject": "S3", "Age": 75.00, "Visit": "v1"},
        {"Subject": "S3", "Age": 75.00, "Visit": "v1"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "S1", "Visit": "v1", "MMSE": 22},  # MCI
        {"Subject": "S2", "Visit": "v1", "MMSE": 29},  # CN
        {"Subject": "S3", "Visit": "v1", "MMSE": 14},  # AD
    ])

    pairs, report = load_miriad_test_retest_pairs(clinical_csv, sessions_csv)
    assert len(pairs) == 3  # 3 pairs, each as a length-2 trajectory
    assert report.n_rescan_pairs == 3
    assert report.n_pairs_state_identical == 3
    assert report.n_pairs_state_differs == 0
    # Every pair must be an admissible self-loop under niaaa_2018
    pack = load_rulepack("ad/niaaa_2018")
    result = audit(pairs, pack, bootstrap_B=100, seed=42)
    assert result.n_flagged == 0
    assert result.ctcs.ci.point == 1.0


def test_load_miriad_test_retest_pairs_no_rescans(tmp_path: Path):
    """If no back-to-back scans exist, return empty list cleanly."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    _write_sessions(sessions_csv, [
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S1", "Age": 70.50, "Visit": "v2"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "S1", "Visit": "v1", "MMSE": 22},
        {"Subject": "S1", "Visit": "v2", "MMSE": 22},
    ])

    pairs, report = load_miriad_test_retest_pairs(clinical_csv, sessions_csv)
    assert pairs == []
    assert report.n_rescan_pairs == 0


# ---------- End-to-end audit integration ----------

def test_load_miriad_end_to_end_audit_runs(tmp_path: Path):
    """Synthetic MIRIAD cohort flows through the full audit kernel."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    # 5 subjects, monotone-non-decreasing trajectories (all admissible)
    rows_s = []
    rows_c = []
    for i, mmse_series in enumerate([
        [29, 28, 27],   # CN -> CN -> CN
        [29, 24, 18],   # CN -> MCI -> MCI
        [22, 18, 14],   # MCI -> MCI -> AD
        [27, 22, 18],   # CN -> MCI -> MCI
        [18, 14, 12],   # AD -> AD -> AD
    ]):
        for v, mmse in enumerate(mmse_series):
            rows_s.append({
                "Subject": f"S{i}",
                "Age": 70.0 + v * 0.5,
                "Visit": f"v{v+1}",
            })
            rows_c.append({
                "Subject": f"S{i}",
                "Visit": f"v{v+1}",
                "MMSE": mmse,
            })
    _write_sessions(sessions_csv, rows_s)
    _write_clinical(clinical_csv, rows_c)

    trajectories, report = load_miriad_trajectories(
        clinical_csv, sessions_csv,
    )
    assert len(trajectories) == 5
    assert report.n_transitions == 10  # 2 transitions × 5 subjects

    pack = load_rulepack("ad/niaaa_2018")
    result = audit(trajectories, pack, bootstrap_B=200, seed=42)
    # All trajectories are monotone non-decreasing → fully admissible
    assert result.n_flagged == 0
    assert result.ctcs.ci.point == 1.0
    # audit_id_v2 should differ from v1 (C6 fix)
    assert result.audit_id != result.audit_id_v2


def test_load_miriad_missing_files_raises(tmp_path: Path):
    """Missing CSV raises FileNotFoundError with clear message."""
    with pytest.raises(FileNotFoundError, match="MIRIAD"):
        load_miriad_trajectories(
            tmp_path / "does_not_exist.csv",
            tmp_path / "also_not_there.csv",
        )


# ---------- MIRIAD XNAT Label parsing tests ----------

def test_parse_miriad_visit_number_basic():
    """Visit number extracted correctly from XNAT composite labels."""
    assert parse_miriad_visit_number("miriad_188_1_MR_1") == "1"
    assert parse_miriad_visit_number("miriad_188_2_MR_1") == "2"
    assert parse_miriad_visit_number("miriad_188_2_MR_2") == "2"  # rescan
    assert parse_miriad_visit_number("miriad_255_1_MMSE") == "1"
    assert parse_miriad_visit_number("miriad_188_9_MR_1") == "9"
    # Case insensitivity
    assert parse_miriad_visit_number("MIRIAD_188_3_MR_1") == "3"


def test_parse_miriad_visit_number_invalid():
    """Non-conforming labels return None."""
    assert parse_miriad_visit_number(None) is None
    assert parse_miriad_visit_number("") is None
    assert parse_miriad_visit_number("not_a_miriad_label") is None
    assert parse_miriad_visit_number(float("nan")) is None


def test_infer_miriad_group_from_subject_id():
    """Malone 2013 convention: ids 188-233 are AD, 234+ are controls."""
    assert infer_miriad_group_from_subject_id("miriad_188") == "AD"
    assert infer_miriad_group_from_subject_id("miriad_233") == "AD"
    assert infer_miriad_group_from_subject_id("miriad_234") == "CN"
    assert infer_miriad_group_from_subject_id("miriad_255") == "CN"
    # Bare numeric also accepted
    assert infer_miriad_group_from_subject_id("200") == "AD"
    assert infer_miriad_group_from_subject_id("250") == "CN"
    # Out-of-range
    assert infer_miriad_group_from_subject_id("miriad_999") is None
    assert infer_miriad_group_from_subject_id("not_an_id") is None
    assert infer_miriad_group_from_subject_id(None) is None


def test_load_miriad_xnat_label_format_end_to_end(tmp_path: Path):
    """Real XNAT export format with composite Labels parses correctly."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    # Mirror the EXACT column layout from the real MIRIAD XNAT export
    pd.DataFrame([
        # miriad_188 (AD): visits 1, 2 (with rescan), 3
        {"Label": "miriad_188_1_MR_1", "Project": "MIRIAD", "Date": "",
         "Subject": "miriad_188", "M/F": "M", "Age": 76.64,
         "Type": "", "Scanner": "", "Scans": "T1(1)"},
        {"Label": "miriad_188_2_MR_1", "Project": "MIRIAD", "Date": "",
         "Subject": "miriad_188", "M/F": "M", "Age": 76.79,
         "Type": "", "Scanner": "", "Scans": "T1(1)"},
        {"Label": "miriad_188_2_MR_2", "Project": "MIRIAD", "Date": "",
         "Subject": "miriad_188", "M/F": "M", "Age": 76.79,
         "Type": "", "Scanner": "", "Scans": "T1(1)"},  # rescan
        {"Label": "miriad_188_3_MR_1", "Project": "MIRIAD", "Date": "",
         "Subject": "miriad_188", "M/F": "M", "Age": 76.95,
         "Type": "", "Scanner": "", "Scans": "T1(1)"},
        # miriad_255 (control): visits 1, 2 with rescan
        {"Label": "miriad_255_1_MR_1", "Project": "MIRIAD", "Date": "",
         "Subject": "miriad_255", "M/F": "F", "Age": 72.10,
         "Type": "", "Scanner": "", "Scans": "T1(1)"},
        {"Label": "miriad_255_2_MR_1", "Project": "MIRIAD", "Date": "",
         "Subject": "miriad_255", "M/F": "F", "Age": 72.25,
         "Type": "", "Scanner": "", "Scans": "T1(1)"},
        {"Label": "miriad_255_2_MR_2", "Project": "MIRIAD", "Date": "",
         "Subject": "miriad_255", "M/F": "F", "Age": 72.25,
         "Type": "", "Scanner": "", "Scans": "T1(1)"},  # rescan
    ]).to_csv(sessions_csv, index=False)

    pd.DataFrame([
        {"id": "/@WEBAPP/images/r.gif", "Label": "miriad_188_1_MMSE",
         "Subject": "miriad_188", "Gender": "male", "MMSE": 21},
        {"id": "/@WEBAPP/images/r.gif", "Label": "miriad_188_2_MMSE",
         "Subject": "miriad_188", "Gender": "male", "MMSE": 19},
        {"id": "/@WEBAPP/images/r.gif", "Label": "miriad_188_3_MMSE",
         "Subject": "miriad_188", "Gender": "male", "MMSE": 17},
        {"id": "/@WEBAPP/images/r.gif", "Label": "miriad_255_1_MMSE",
         "Subject": "miriad_255", "Gender": "female", "MMSE": 29},
        {"id": "/@WEBAPP/images/r.gif", "Label": "miriad_255_2_MMSE",
         "Subject": "miriad_255", "Gender": "female", "MMSE": 28},
    ]).to_csv(clinical_csv, index=False)

    # No Subjects.csv — adapter must fall back to ID-based group inference.
    trajectories, report = load_miriad_trajectories(
        clinical_csv, sessions_csv,
    )

    # 2 subjects with 3 + 2 unique visits each, rescans excluded
    assert len(trajectories) == 2
    assert report.n_test_retest_visits_excluded == 2  # one per subject
    # miriad_188: 3 visits -> 2 transitions; miriad_255: 2 visits -> 1
    assert report.n_transitions == 3

    # Group disagreement detection via ID inference (Malone 2013):
    # - miriad_188 is AD by ID convention. MMSE: 21 (visit 1), 19 (visit 2),
    #   17 (visit 3) → MCI, MCI, AD. AD-MCI is the MIRIAD inclusion criterion
    #   so visits 1-2 are severity-consistent disagreements, NOT discordant.
    #   Visit 3 (AD/AD) matches exactly. So state-discordant = 0.
    # - miriad_255 is control by ID convention. MMSE: 29 (visit 1), 28 (v2)
    #   → CN, CN. Matches exactly.
    assert report.group_mmse_disagreements == 2   # broad count (severity)
    assert report.group_mmse_state_discordant == 0  # no true discordance


def test_load_miriad_xnat_label_format_test_retest(tmp_path: Path):
    """Same XNAT layout, exercise the test-retest pair path."""
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    pd.DataFrame([
        # Two back-to-back at visit 1 for miriad_188
        {"Label": "miriad_188_1_MR_1", "Subject": "miriad_188", "Age": 76.64},
        {"Label": "miriad_188_1_MR_2", "Subject": "miriad_188", "Age": 76.64},
        # Two back-to-back at visit 2 for miriad_255
        {"Label": "miriad_255_2_MR_1", "Subject": "miriad_255", "Age": 72.25},
        {"Label": "miriad_255_2_MR_2", "Subject": "miriad_255", "Age": 72.25},
    ]).to_csv(sessions_csv, index=False)

    pd.DataFrame([
        {"Label": "miriad_188_1_MMSE", "Subject": "miriad_188", "MMSE": 21},
        {"Label": "miriad_255_2_MMSE", "Subject": "miriad_255", "MMSE": 28},
    ]).to_csv(clinical_csv, index=False)

    pairs, report = load_miriad_test_retest_pairs(clinical_csv, sessions_csv)
    assert len(pairs) == 2
    assert report.n_rescan_pairs == 2
    assert report.n_pairs_state_identical == 2
    assert report.n_pairs_state_differs == 0
    # End-to-end: audit kernel sees admissible self-loops
    pack = load_rulepack("ad/niaaa_2018")
    result = audit(pairs, pack, bootstrap_B=100, seed=42)
    assert result.n_flagged == 0


# ---------- New: methodological-correctness tests (v1.7.4) ----------

def test_test_retest_pair_delta_t_is_zero(tmp_path: Path):
    """v1.7.4 (F8 fix): same-session rescans must encode delta_t = 0 days.

    Previous versions used a 1-day delta as a kernel-compatibility hack;
    Trajectory natively allows date ties, so the correct encoding is
    same-date for both scans (delta_t = 0).
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    _write_sessions(sessions_csv, [
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},  # rescan
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "S1", "Visit": "v1", "MMSE": 22},
    ])
    pairs, _ = load_miriad_test_retest_pairs(clinical_csv, sessions_csv)
    assert len(pairs) == 1
    p = pairs[0]
    assert p.dates[0] == p.dates[1], (
        f"Test-retest pair dates must be identical for delta_t=0; "
        f"got {p.dates[0]} and {p.dates[1]}"
    )
    for _fs, _ts, dt in p.transitions():
        assert dt == 0.0, f"Expected delta_t=0, got {dt}"


def test_mmse_forward_fill_per_subject(tmp_path: Path):
    """v1.7.4 (F11 fix): MIRIAD records MMSE only every 6 months.

    Scan visits without a per-visit MMSE row must inherit from the most
    recent prior assessment. This is the standard intermittent-assessment
    treatment and prevents trajectory truncation by ~40%.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    # Subject has 5 scan visits but only 2 MMSE assessments (at visits 1 and 5)
    _write_sessions(sessions_csv, [
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S1", "Age": 70.04, "Visit": "v2"},  # 2 weeks
        {"Subject": "S1", "Age": 70.12, "Visit": "v3"},  # 6 weeks
        {"Subject": "S1", "Age": 70.27, "Visit": "v4"},  # 14 weeks
        {"Subject": "S1", "Age": 70.50, "Visit": "v5"},  # 26 weeks
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "S1", "Visit": "v1", "MMSE": 22},   # baseline
        {"Subject": "S1", "Visit": "v5", "MMSE": 20},   # 6-month
    ])

    trajectories, report = load_miriad_trajectories(
        clinical_csv, sessions_csv,
    )
    # All 5 visits should land in the trajectory (none dropped for null MMSE)
    assert len(trajectories) == 1
    assert len(trajectories[0].states) == 5
    # Visits 1-4 inherit MMSE=22 (MCI), visit 5 = MMSE 20 (MCI)
    assert trajectories[0].states == ("MCI", "MCI", "MCI", "MCI", "MCI")
    # forward_fill_count tracks how many rows were filled
    assert report.mmse_forward_filled == 3   # visits 2, 3, 4 filled from v1


def test_state_discordant_distinct_from_severity(tmp_path: Path):
    """v1.7.4 (F2+F12 fix): AD-group + MCI-state is severity-consistent,
    NOT state-discordant. Only AD-group + CN-state or CN-group + AD-state
    counts as state-discordant.

    Per Malone 2013 MIRIAD inclusion criterion: AD subjects have MMSE
    12-26 at baseline, which is the MCI range under Folstein 1975
    thresholds. Counting these as "disagreements" over-reports noise
    by ~60% on the real cohort.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    subjects_csv = tmp_path / "Subjects.csv"

    _write_sessions(sessions_csv, [
        # AD subject (group=AD) with mild AD MMSE
        {"Subject": "MIRIAD_AD_MILD", "Age": 70.00, "Visit": "v1"},
        {"Subject": "MIRIAD_AD_MILD", "Age": 70.50, "Visit": "v2"},
        # AD subject (group=AD) with CN-range MMSE → discordant
        {"Subject": "MIRIAD_AD_NORMAL", "Age": 70.00, "Visit": "v1"},
        # CN subject (group=control) with AD-range MMSE → discordant
        {"Subject": "MIRIAD_CN_AD", "Age": 70.00, "Visit": "v1"},
        # CN subject (group=control) with normal MMSE
        {"Subject": "MIRIAD_CN_OK", "Age": 70.00, "Visit": "v1"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "MIRIAD_AD_MILD", "Visit": "v1", "MMSE": 22},   # MCI state
        {"Subject": "MIRIAD_AD_MILD", "Visit": "v2", "MMSE": 18},   # MCI state
        {"Subject": "MIRIAD_AD_NORMAL", "Visit": "v1", "MMSE": 29}, # CN state (discordant)
        {"Subject": "MIRIAD_CN_AD", "Visit": "v1", "MMSE": 15},     # AD state (discordant)
        {"Subject": "MIRIAD_CN_OK", "Visit": "v1", "MMSE": 28},     # CN state
    ])
    _write_subjects(subjects_csv, [
        {"Subject": "MIRIAD_AD_MILD", "Group": "AD"},
        {"Subject": "MIRIAD_AD_NORMAL", "Group": "AD"},
        {"Subject": "MIRIAD_CN_AD", "Group": "control"},
        {"Subject": "MIRIAD_CN_OK", "Group": "control"},
    ])

    _, report = load_miriad_trajectories(
        clinical_csv, sessions_csv, subjects_csv,
    )

    # Broad count: AD_MILD has 2 visits (both MCI vs AD-group),
    # AD_NORMAL has 1 visit (CN vs AD-group),
    # CN_AD has 1 visit (AD vs CN-group). Total = 4 broad disagreements.
    assert report.group_mmse_disagreements == 4

    # State-discordant count: only the 2 CN vs AD or AD vs CN cases.
    # AD_MILD's MCI states are severity-consistent with AD group, NOT
    # discordant.
    assert report.group_mmse_state_discordant == 2

    # Examples should contain only the state-discordant ones
    discordant_ids = [
        e["subject_id"] for e in report.group_mmse_disagreement_examples
    ]
    assert "MIRIAD_AD_NORMAL" in discordant_ids
    assert "MIRIAD_CN_AD" in discordant_ids
    assert "MIRIAD_AD_MILD" not in discordant_ids


def test_ci_attribute_names_match_BootstrapCI_dataclass(tmp_path: Path):
    """v1.7.4 (F1 fix): runner script and invariant test must use the
    canonical BootstrapCI field names (point/huber/ci_low/ci_high).

    A previous version used .lower/.upper which would crash at runtime
    on real data. This test verifies the attributes exist on the dataclass
    and the names are correct.
    """
    from neurotcs.audit_core.bootstrap import BootstrapCI
    fields = {f.name for f in BootstrapCI.__dataclass_fields__.values()}
    assert "point" in fields
    assert "ci_low" in fields
    assert "ci_high" in fields
    assert "huber" in fields
    # Negative check: the old wrong names must NOT exist
    assert "lower" not in fields
    assert "upper" not in fields


# ---------- v1.7.6 round-2 deep-audit regression tests ----------

def test_n_rescan_pairs_with_mmse_counts_both_valid_pairs(tmp_path: Path):
    """v1.7.6 (R1 fix): n_rescan_pairs_with_mmse must count pairs where
    BOTH scans have valid MMSE (i.e. pairs that proceed to audit), not
    pairs with at-least-one-valid.

    Previous implementation used `dropna().groupby().shape[0]` which
    counted groups with size 1 (one scan dropped, one kept). The audit
    cannot run on a singleton, so reporting it as "with mmse" was
    misleading.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    # Pair A: both visits have valid MMSE (will succeed)
    # Pair B: one visit has invalid MMSE (will be dropped during pairing)
    pd.DataFrame([
        {"Label": "miriad_188_1_MR_1", "Subject": "miriad_188", "Age": 70.00},
        {"Label": "miriad_188_1_MR_2", "Subject": "miriad_188", "Age": 70.00},
        {"Label": "miriad_188_2_MR_1", "Subject": "miriad_188", "Age": 70.50},
        {"Label": "miriad_188_2_MR_2", "Subject": "miriad_188", "Age": 70.50},
    ]).to_csv(sessions_csv, index=False)

    pd.DataFrame([
        {"Label": "miriad_188_1_MMSE", "Subject": "miriad_188", "MMSE": 22},
        {"Label": "miriad_188_2_MMSE", "Subject": "miriad_188", "MMSE": 99},
    ]).to_csv(clinical_csv, index=False)

    pairs, report = load_miriad_test_retest_pairs(clinical_csv, sessions_csv)
    assert report.n_rescan_pairs == 2          # 2 pairs identified
    assert report.n_rescan_pairs_with_mmse == 1  # only 1 has both valid
    assert len(pairs) == 1                       # only 1 enters audit


def test_median_mmse_fallback_filters_out_of_range(tmp_path: Path):
    """v1.7.6 (R2 fix): the per-subject median MMSE fallback must not be
    poisoned by out-of-range sentinels.

    Previously: clinical with [22, 99] → median = 60.5 → out of range →
    state = None → pair dropped. Now: filter to mappable values first,
    median([22]) = 22 → MCI.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    # Use raw Visit column (not Label) so the Label parser does NOT engage
    # and the median fallback path executes.
    pd.DataFrame([
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
    ]).to_csv(sessions_csv, index=False)

    pd.DataFrame([
        {"Subject": "S1", "Visit": "v1", "MMSE": 22},   # valid
        {"Subject": "S1", "Visit": "v2", "MMSE": 99},   # out of range sentinel
    ]).to_csv(clinical_csv, index=False)

    pairs, report = load_miriad_test_retest_pairs(clinical_csv, sessions_csv)
    # Filter discards the 99 → median([22]) = 22 → MCI → pair proceeds
    assert len(pairs) == 1
    assert pairs[0].states == ("MCI", "MCI")


def test_audit_id_deterministic_across_runs(tmp_path: Path):
    """v1.7.6 (R3): the same input must produce the same audit_id on
    every run. This guards against any non-determinism creeping into
    pandas operations (groupby ordering, dict insertion order, etc.).
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"

    _write_sessions(sessions_csv, [
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S1", "Age": 70.50, "Visit": "v2"},
        {"Subject": "S1", "Age": 71.00, "Visit": "v3"},
        {"Subject": "S2", "Age": 65.00, "Visit": "v1"},
        {"Subject": "S2", "Age": 65.50, "Visit": "v2"},
        {"Subject": "S2", "Age": 66.00, "Visit": "v3"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "S1", "Visit": "v1", "MMSE": 22},
        {"Subject": "S1", "Visit": "v2", "MMSE": 18},
        {"Subject": "S1", "Visit": "v3", "MMSE": 14},
        {"Subject": "S2", "Visit": "v1", "MMSE": 29},
        {"Subject": "S2", "Visit": "v2", "MMSE": 28},
        {"Subject": "S2", "Visit": "v3", "MMSE": 29},
    ])

    pack = load_rulepack("ad/niaaa_2018")

    # Run twice with fresh state
    t1, _ = load_miriad_trajectories(clinical_csv, sessions_csv)
    r1 = audit(t1, pack, bootstrap_B=200, seed=42)
    t2, _ = load_miriad_trajectories(clinical_csv, sessions_csv)
    r2 = audit(t2, pack, bootstrap_B=200, seed=42)

    assert r1.audit_id == r2.audit_id, (
        f"audit_id not reproducible: {r1.audit_id} vs {r2.audit_id}"
    )
    assert r1.audit_id_v2 == r2.audit_id_v2, (
        f"audit_id_v2 not reproducible"
    )


def test_out_of_range_mmse_counted_independent_of_forward_fill(tmp_path: Path):
    """v1.7.6 (R4): out_of_range_mmse must count values that are
    explicitly out-of-range (>30 or <0), regardless of forward-fill
    behaviour. Forward-fill only operates on NaN values, not on
    explicit invalid sentinels.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    _write_sessions(sessions_csv, [
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
        {"Subject": "S1", "Age": 70.50, "Visit": "v2"},
        {"Subject": "S1", "Age": 71.00, "Visit": "v3"},
    ])
    # Visit 1: invalid sentinel (99). Visit 2: valid. Visit 3: NaN (missing).
    _write_clinical(clinical_csv, [
        {"Subject": "S1", "Visit": "v1", "MMSE": 99},   # out of range
        {"Subject": "S1", "Visit": "v2", "MMSE": 22},
        {"Subject": "S1", "Visit": "v3", "MMSE": None}, # missing -> ffill from v2
    ])

    _, report = load_miriad_trajectories(clinical_csv, sessions_csv)
    # Out-of-range count is 1 (the 99). Forward-fill does NOT overwrite
    # the 99 because it's not NaN. Visit 3 IS filled from visit 2.
    assert report.out_of_range_mmse == 1
    assert report.mmse_forward_filled >= 1


def test_single_visit_subject_loads_as_zero_transition_trajectory(tmp_path: Path):
    """v1.7.6 (R5): a subject with only one scan visit must still load
    cleanly as a 1-state, 0-transition trajectory; not crash or be
    silently excluded.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    _write_sessions(sessions_csv, [
        {"Subject": "S1", "Age": 70.00, "Visit": "v1"},
    ])
    _write_clinical(clinical_csv, [
        {"Subject": "S1", "Visit": "v1", "MMSE": 22},
    ])
    trajectories, report = load_miriad_trajectories(clinical_csv, sessions_csv)
    assert len(trajectories) == 1
    assert trajectories[0].num_transitions == 0
    assert report.n_transitions == 0


def test_empty_cohort_returns_empty_clean(tmp_path: Path):
    """v1.7.6 (R6): an empty MIRIAD cohort must return empty results
    cleanly, not crash. Defensive behaviour for malformed exports.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    pd.DataFrame(columns=["Label", "Subject", "Age", "Visit"]).to_csv(
        sessions_csv, index=False,
    )
    pd.DataFrame(columns=["Label", "Subject", "MMSE", "Visit"]).to_csv(
        clinical_csv, index=False,
    )
    trajectories, report = load_miriad_trajectories(clinical_csv, sessions_csv)
    assert len(trajectories) == 0
    assert report.n_transitions == 0
    assert report.raw_sessions_rows == 0


def test_numeric_subject_ids_pandas_int_dtype(tmp_path: Path):
    """v1.7.6 (R7): pandas may infer integer dtype for purely numeric
    subject IDs. The adapter must handle this correctly by stringifying
    everywhere comparisons happen.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    pd.DataFrame([
        {"Label": "miriad_188_1_MR_1", "Subject": 188, "Age": 70.00},
        {"Label": "miriad_188_2_MR_1", "Subject": 188, "Age": 70.50},
    ]).to_csv(sessions_csv, index=False)
    pd.DataFrame([
        {"Label": "miriad_188_1_MMSE", "Subject": 188, "MMSE": 22},
        {"Label": "miriad_188_2_MMSE", "Subject": 188, "MMSE": 20},
    ]).to_csv(clinical_csv, index=False)

    trajectories, _ = load_miriad_trajectories(clinical_csv, sessions_csv)
    assert len(trajectories) == 1
    assert trajectories[0].num_transitions == 1


def test_triplet_scans_at_same_age_takes_first_two(tmp_path: Path):
    """v1.7.6 (R8): if 3+ scans exist at the same age (very rare but
    possible), only the first 2 are used as a test-retest pair. The
    third is ignored, not crashed on.
    """
    sessions_csv = tmp_path / "MR_Sessions.csv"
    clinical_csv = tmp_path / "ClinicalAssessment.csv"
    pd.DataFrame([
        {"Label": "miriad_188_1_MR_1", "Subject": "miriad_188", "Age": 70.00},
        {"Label": "miriad_188_1_MR_2", "Subject": "miriad_188", "Age": 70.00},
        {"Label": "miriad_188_1_MR_3", "Subject": "miriad_188", "Age": 70.00},
    ]).to_csv(sessions_csv, index=False)
    pd.DataFrame([
        {"Label": "miriad_188_1_MMSE", "Subject": "miriad_188", "MMSE": 22},
    ]).to_csv(clinical_csv, index=False)
    pairs, report = load_miriad_test_retest_pairs(clinical_csv, sessions_csv)
    assert len(pairs) == 1
    assert report.n_rescan_pairs == 1


# ---------- Runner ----------

def run_all() -> None:
    """Optional manual runner — pytest discovers each test automatically."""
    fns = [
        test_mmse_to_state_thresholds,
        test_mmse_to_state_invalid_inputs,
        test_group_to_state_recognition,
        test_hash_patient_id_stable_and_prefixed,
    ]
    for fn in fns:
        fn()
        print(f"  {PASS} {fn.__name__}")


if __name__ == "__main__":
    run_all()

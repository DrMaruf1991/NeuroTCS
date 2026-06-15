"""Tests for neurotcs.io.phi_gate (optional direct-identifier input gate).

The CENTERPIECE is the NEGATIVE suite: de-identified cohort data (ADNI/OASIS/
NACC shapes) must NEVER trigger a finding. Breaking the de-identified data the
tool exists for is a worse failure than missing some PHI, so those tests come
first and are the most important.
"""
from __future__ import annotations

import pandas as pd

from neurotcs.io.phi_gate import scan_tables


# --------------------------------------------------------------------------- #
# NEGATIVE (centerpiece): de-identified cohort data must produce ZERO findings.
# --------------------------------------------------------------------------- #
def test_adni_shaped_deidentified_data_triggers_nothing():
    """ADNI-style columns: subject_id/RID/PTID/VISCODE/AGE/DX/visit_date are all
    de-identified study fields and MUST NOT be flagged."""
    df = pd.DataFrame({
        "subject_id": ["941_S_1363", "941_S_1364"],
        "RID": [1363, 1364],
        "PTID": ["941_S_1363", "941_S_1364"],
        "VISCODE": ["bl", "m12"],
        "visit_date": ["2020-01-01", "2021-01-01"],
        "AGE": [72, 68],
        "DX": ["CN", "MCI"],
        "MMSE": [29, 27],
    })
    res = scan_tables({"ADNIMERGE": df})
    assert not res.has_findings, [f.reason for f in res.findings]


def test_oasis_nacc_shaped_columns_trigger_nothing():
    df = pd.DataFrame({
        "subject_id": ["OAS30001", "OAS30002"],
        "visit": [1, 2],
        "exam_date": ["2019-05-01", "2020-05-01"],
        "age": [75, 80],
        "sex": ["M", "F"],
        "education": [16, 12],
        "apoe": ["E3/E4", "E3/E3"],
        "clinical_state": ["CN", "AD"],
        "cdr_sb_sum_boxes": [0.0, 4.0],
    })
    res = scan_tables({"clinical": df})
    assert not res.has_findings, [f.reason for f in res.findings]


def test_patient_id_is_allowlisted_study_vocab():
    """'patient_id' is a STUDY id synonym in the tool -- de-identified, not a
    direct identifier. It must not trigger."""
    df = pd.DataFrame({"patient_id": ["P1", "P2"], "visit": [0, 1],
                       "state": ["CN", "MCI"]})
    res = scan_tables({"S": df})
    assert not res.has_findings, [f.reason for f in res.findings]


def test_visit_date_of_real_dates_is_not_treated_as_dob():
    df = pd.DataFrame({"subject_id": ["A", "B"], "visit": [0, 1],
                       "visit_date": ["2020-03-15", "2021-03-15"]})
    res = scan_tables({"S": df})
    assert not res.has_findings, [f.reason for f in res.findings]


# --------------------------------------------------------------------------- #
# POSITIVE: unambiguous direct identifiers MUST be detected.
# --------------------------------------------------------------------------- #
def test_patient_name_column_is_flagged():
    df = pd.DataFrame({"subject_id": ["A"], "patient_name": ["Jane Doe"],
                       "visit": [0]})
    res = scan_tables({"S": df})
    assert res.has_findings
    assert any("patient_name" in f.column for f in res.findings)


def test_mrn_and_ssn_and_dob_columns_flagged():
    df = pd.DataFrame({
        "subject_id": ["A"], "MRN": ["12345678"],
        "SSN": ["111-22-3333"], "DOB": ["1950-01-01"], "visit": [0],
    })
    res = scan_tables({"S": df})
    flagged = {f.column for f in res.findings}
    assert "MRN" in flagged and "SSN" in flagged and "DOB" in flagged


def test_ssn_value_pattern_flagged_even_with_neutral_column_name():
    """A column innocuously named 'extra' but full of SSN-shaped values fires on
    the VALUE pattern."""
    df = pd.DataFrame({
        "subject_id": ["A", "B", "C", "D"],
        "visit": [0, 1, 0, 1],
        "extra": ["111-22-3333", "222-33-4444", "333-44-5555", "444-55-6666"],
    })
    res = scan_tables({"S": df})
    assert any(f.column == "extra" for f in res.findings)


def test_email_value_pattern_flagged():
    df = pd.DataFrame({
        "subject_id": ["A", "B", "C"],
        "contact": ["a@x.com", "b@y.org", "c@z.net"],
    })
    res = scan_tables({"S": df})
    assert any(f.column == "contact" for f in res.findings)


# --------------------------------------------------------------------------- #
# Guard: 'id' inside 'rid' / 'ptid' must NOT trip the short-token exact match.
# --------------------------------------------------------------------------- #
def test_short_id_token_does_not_false_positive_on_rid_ptid():
    df = pd.DataFrame({"rid": [1, 2], "ptid": ["x", "y"], "visit": [0, 1]})
    res = scan_tables({"S": df})
    assert not res.has_findings, [f.reason for f in res.findings]


# --------------------------------------------------------------------------- #
# CLI INTEGRATION: prove the gate is WIRED into `neurotcs audit`.
# (Unit tests above prove the detector; these prove the integration -- without
# them a disconnected gate would still pass every test.)
# --------------------------------------------------------------------------- #
from neurotcs.cli import main as _cli_main  # noqa: E402


def _write_phi_csv(tmp_path):
    p = tmp_path / 'phi.csv'
    p.write_text(
        'subject_id,visit,visit_date,clinical_state,patient_name' + chr(10) +
        'S001,1,2020-01-01,CN,Jane Doe' + chr(10) +
        'S001,2,2021-01-01,MCI,Jane Doe' + chr(10),
        encoding='utf-8',
    )
    return p


def test_cli_phi_warn_mode_emits_note_but_audit_runs(tmp_path, capsys):
    """Default (warn) mode: the PHI note is emitted AND the audit still runs
    (exit code is not the input-refusal code)."""
    csv = _write_phi_csv(tmp_path)
    out = tmp_path / 'out'
    rc = _cli_main(['audit', str(csv), '-o', str(out)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # the gate fired ...
    assert 'patient_name' in combined
    assert 'direct identifier' in combined or 'PHI' in combined
    # ... but the audit completed (warn does not refuse): rc is CLEAN(0)/FLAGS(1).
    assert rc in (0, 1), f'warn mode must not block; got rc={rc}'
    assert (out / 'phi.bundle.json').exists()


def test_cli_refuse_phi_blocks_with_input_exit(tmp_path, capsys):
    """--refuse-phi turns the warning into a fail-closed refusal."""
    csv = _write_phi_csv(tmp_path)
    out = tmp_path / 'out2'
    rc = _cli_main(['audit', str(csv), '--refuse-phi', '-o', str(out)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert 'refusing' in combined.lower()
    # EXIT_INPUT is 4 in this CLI; assert non-zero refusal and no bundle written.
    assert rc == 4, f'--refuse-phi must return EXIT_INPUT (4); got rc={rc}'
    assert not (out / 'phi.bundle.json').exists()


def test_cli_clean_deidentified_data_no_phi_note(tmp_path, capsys):
    """A de-identified file emits NO PHI note and audits normally."""
    p = tmp_path / 'clean.csv'
    p.write_text(
        'subject_id,visit,visit_date,clinical_state' + chr(10) +
        'S001,1,2020-01-01,CN' + chr(10) +
        'S001,2,2021-01-01,MCI' + chr(10),
        encoding='utf-8',
    )
    out = tmp_path / 'outc'
    rc = _cli_main(['audit', str(p), '-o', str(out)])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert 'direct identifier' not in combined
    assert rc in (0, 1)

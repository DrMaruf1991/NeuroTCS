"""Tests for CDISC SDTM/ADaM ingestion (neurotcs.io.cdisc).

Locks the recognizer + normalizer contract:
  * SDTM and ADaM auto-detected by variable presence.
  * Identity/timing auto-mapped (USUBJID/VISITNUM/--DTC|ADT).
  * Structural-role classification: cognitive scales -> measurements,
    RS-domain / diagnosis codes -> state, unknown -> fail-closed.
  * Single clean state code auto-maps; ambiguity (multiple states, or unknown
    code present) requires explicit selection (no guessing).
  * Normalized output drives the existing orchestrator end-to-end.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.io.cdisc import (
    CdiscMappingError,
    normalize_cdisc_to_long,
    read_cdisc_submission,
    recognize_cdisc,
)
from neurotcs.orchestration.orchestrator import run_full_audit


def _sdtm_rs(states_by_subject):
    rows = []
    for sid, states in states_by_subject.items():
        for i, st in enumerate(states):
            rows.append({
                "STUDYID": "S", "DOMAIN": "RS", "USUBJID": sid,
                "VISITNUM": i + 1, "RSDTC": f"20{18 + i}-01-01",
                "RSTESTCD": "DXDECOD", "RSSTRESC": st,
            })
    return pd.DataFrame(rows)


class TestRecognition:

    def test_sdtm_findings_recognized(self):
        rec = recognize_cdisc(_sdtm_rs({"001": ["CN", "MCI"]}))
        assert rec.is_cdisc and rec.model == "SDTM"
        assert rec.domain == "RS"
        assert rec.subject_col == "USUBJID"
        assert rec.testcd_col == "RSTESTCD"

    def test_adam_bds_recognized(self):
        ad = pd.DataFrame({
            "STUDYID": ["S"], "USUBJID": ["1"], "VISITNUM": [1],
            "ADT": ["2018-01-01"], "PARAMCD": ["DIAG"], "AVALC": ["CN"],
            "AVAL": [0],
        })
        rec = recognize_cdisc(ad)
        assert rec.is_cdisc and rec.model == "ADaM"
        assert rec.testcd_col == "PARAMCD"
        assert rec.resultc_col == "AVALC"

    def test_non_cdisc_table_not_recognized(self):
        df = pd.DataFrame({"subject_id": ["a"], "state": ["CN"]})
        assert recognize_cdisc(df).is_cdisc is False

    def test_dm_subject_level_recognized_without_findings(self):
        dm = pd.DataFrame({"USUBJID": ["1"], "AGE": [72], "SEX": ["M"],
                           "DOMAIN": ["DM"]})
        rec = recognize_cdisc(dm)
        assert rec.is_cdisc is True
        assert rec.testcd_col is None  # no trajectory state


class TestStructuralRole:

    def test_cognitive_scales_are_measurements_not_state(self):
        qs = pd.DataFrame({
            "USUBJID": ["1", "1"], "VISITNUM": [1, 1], "QSDTC": ["2018", "2018"],
            "QSTESTCD": ["MMSE", "ADASCOG"], "QSSTRESN": [28, 15],
            "QSSTRESC": ["28", "15"],
        })
        rec = recognize_cdisc(qs)
        assert set(rec.measurement_codes) == {"MMSE", "ADASCOG"}
        assert rec.state_codes == ()

    def test_rs_domain_code_is_state(self):
        rec = recognize_cdisc(_sdtm_rs({"1": ["CN", "AD"]}))
        assert "DXDECOD" in rec.state_codes


class TestNormalization:

    def test_sdtm_rs_to_clinical_long(self):
        rs = _sdtm_rs({"001": ["CN", "MCI", "AD"]})
        rec = recognize_cdisc(rs)
        out = normalize_cdisc_to_long(rs, rec, [])
        cl = out["clinical"]
        assert list(cl.columns) == ["subject_id", "visit", "visit_date", "state"]
        assert cl["state"].tolist() == ["CN", "MCI", "AD"]

    def test_adam_diagnosis_to_clinical(self):
        ad = pd.DataFrame({
            "USUBJID": ["1", "1"], "VISITNUM": [1, 2], "ADT": ["2018", "2019"],
            "PARAMCD": ["DIAG", "DIAG"], "AVALC": ["MCI", "AD"], "AVAL": [1, 2],
        })
        rec = recognize_cdisc(ad)
        out = normalize_cdisc_to_long(ad, rec, [])
        assert out["clinical"]["state"].tolist() == ["MCI", "AD"]

    def test_cognitive_scales_pivot_to_measurements(self):
        qs = pd.DataFrame({
            "USUBJID": ["1", "1"], "VISITNUM": [1, 2], "QSDTC": ["2018", "2019"],
            "QSTESTCD": ["MMSE", "MMSE"], "QSSTRESN": [28, 26],
            "QSSTRESC": ["28", "26"],
        })
        rec = recognize_cdisc(qs)
        out = normalize_cdisc_to_long(qs, rec, [])
        assert "MMSE" in out["measurements"].columns
        assert "clinical" not in out


class TestFailClosed:

    def test_single_clean_state_auto_maps(self):
        rs = _sdtm_rs({"1": ["CN", "MCI"]})
        rec = recognize_cdisc(rs)
        out = normalize_cdisc_to_long(rs, rec, [])  # no state_code needed
        assert out["clinical"]["state"].tolist() == ["CN", "MCI"]

    def test_unknown_code_forces_explicit_selection(self):
        amb = pd.DataFrame({
            "USUBJID": ["1", "1"], "VISITNUM": [1, 1], "QSDTC": ["2018", "2018"],
            "QSTESTCD": ["DXDECOD", "FOOBAR"], "QSSTRESC": ["CN", "x"],
            "QSSTRESN": [0, 1],
        })
        rec = recognize_cdisc(amb)
        with pytest.raises(CdiscMappingError):
            normalize_cdisc_to_long(amb, rec, [])
        # explicit selection works
        out = normalize_cdisc_to_long(amb, rec, [], state_code="DXDECOD")
        assert out["clinical"]["state"].tolist() == ["CN"]

    def test_bad_state_code_rejected(self):
        rs = _sdtm_rs({"1": ["CN"]})
        rec = recognize_cdisc(rs)
        with pytest.raises(CdiscMappingError):
            normalize_cdisc_to_long(rs, rec, [], state_code="NOPE")


class TestEndToEnd:

    def test_cdisc_sdtm_drives_orchestrator_and_flags_error(self):
        # SUBJ-003 has AD->MCI (impossible); should be caught after normalization.
        rs = _sdtm_rs({
            "SUBJ-001": ["CN", "MCI", "AD"],
            "SUBJ-002": ["CN", "MCI", "MCI"],
            "SUBJ-003": ["AD", "MCI", "CN"],
        })
        rec = recognize_cdisc(rs)
        norm = normalize_cdisc_to_long(rs, rec, [])
        res = run_full_audit({"clinical": norm["clinical"]}, bootstrap_B=200)
        layer = next(L for L in res.layers if L.layer == "staging_clinical")
        assert layer.ran is True
        flagged = {(f["subject_id"], f["from"], f["to"]) for f in layer.flags}
        assert ("SUBJ-003", "AD", "MCI") in flagged

    def test_read_cdisc_submission_from_csv(self):
        rs = _sdtm_rs({"001": ["CN", "MCI", "AD"]})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rs.csv"
            rs.to_csv(p, index=False)
            dec: list[str] = []
            sub = read_cdisc_submission(str(p), dec)
            assert "clinical" in sub
            assert sub["clinical"]["state"].tolist() == ["CN", "MCI", "AD"]
            assert any("CDISC" in x for x in dec)


class TestMultiDomainJoin:
    """v1.49: join a full SDTM folder (DM + RS + QS) into one submission."""

    def _write_folder(self, d: Path):
        # DM demographics
        pd.DataFrame({
            "DOMAIN": ["DM"] * 3, "USUBJID": ["001", "002", "003"],
            "AGE": [72, 68, 81], "SEX": ["M", "F", "M"],
            "RACE": ["WHITE", "ASIAN", "WHITE"],
        }).to_csv(d / "dm.csv", index=False)
        # RS diagnosis per visit (SUBJ-003 has AD->MCI, an error)
        rs = []
        for sid, states in {"001": ["CN", "MCI", "AD"],
                            "002": ["CN", "MCI"],
                            "003": ["AD", "MCI"]}.items():
            for i, st in enumerate(states):
                rs.append({"DOMAIN": "RS", "USUBJID": sid, "VISITNUM": i + 1,
                           "RSDTC": f"20{18 + i}-01-01", "RSTESTCD": "DXDECOD",
                           "RSSTRESC": st})
        pd.DataFrame(rs).to_csv(d / "rs.csv", index=False)
        # QS scales
        qs = []
        for sid in ["001", "002", "003"]:
            for i, (mm, cdr) in enumerate([(28, 0.5), (26, 1.0)]):
                qs.append({"DOMAIN": "QS", "USUBJID": sid, "VISITNUM": i + 1,
                           "QSDTC": f"20{18 + i}-01-01", "QSTESTCD": "MMSE",
                           "QSSTRESN": mm, "QSSTRESC": str(mm)})
                qs.append({"DOMAIN": "QS", "USUBJID": sid, "VISITNUM": i + 1,
                           "QSDTC": f"20{18 + i}-01-01", "QSTESTCD": "CDRSB",
                           "QSSTRESN": cdr, "QSSTRESC": str(cdr)})
        pd.DataFrame(qs).to_csv(d / "qs.csv", index=False)

    def test_join_produces_all_three_sheets(self):
        from neurotcs.io.cdisc import join_cdisc_domains
        with tempfile.TemporaryDirectory() as d:
            self._write_folder(Path(d))
            sub = join_cdisc_domains(d, [])
            assert set(sub) == {"clinical", "measurements", "demographics"}
            assert "MMSE" in sub["measurements"].columns
            assert "CDRSB" in sub["measurements"].columns
            assert "age" in sub["demographics"].columns

    def test_join_clinical_state_from_rs(self):
        from neurotcs.io.cdisc import join_cdisc_domains
        with tempfile.TemporaryDirectory() as d:
            self._write_folder(Path(d))
            sub = join_cdisc_domains(d, [])
            assert sub["clinical"]["state"].tolist()[:3] == ["CN", "MCI", "AD"]

    def test_join_ids_consistent_across_sheets(self):
        from neurotcs.io.cdisc import join_cdisc_domains
        with tempfile.TemporaryDirectory() as d:
            self._write_folder(Path(d))
            sub = join_cdisc_domains(d, [])
            cl = set(sub["clinical"]["subject_id"])
            dm = set(sub["demographics"]["subject_id"])
            assert cl == dm  # join keys align

    def test_joined_submission_drives_orchestrator(self):
        from neurotcs.io.cdisc import join_cdisc_domains
        from neurotcs.io.data_integrity import audit_data_integrity
        with tempfile.TemporaryDirectory() as d:
            self._write_folder(Path(d))
            sub = join_cdisc_domains(d, [])
            osub = {"clinical": sub["clinical"]}
            di = audit_data_integrity({"demographics": sub["demographics"]})
            if di:
                osub["data_integrity"] = di
            res = run_full_audit(osub, bootstrap_B=200)
            layer = next(L for L in res.layers if L.layer == "staging_clinical")
            flagged = {(f["subject_id"], f["from"], f["to"]) for f in layer.flags}
            assert ("003", "AD", "MCI") in flagged

    def test_join_deterministic(self):
        from neurotcs.io.cdisc import join_cdisc_domains
        with tempfile.TemporaryDirectory() as d:
            self._write_folder(Path(d))
            a = join_cdisc_domains(d, [])
            b = join_cdisc_domains(d, [])
            assert a["clinical"].equals(b["clinical"])
            assert list(a["measurements"].columns) == list(b["measurements"].columns)

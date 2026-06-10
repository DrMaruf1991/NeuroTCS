"""Tests for neurotcs.io.data_integrity -- universal Layer-1 data-integrity
checks (deterministic, fail-closed, citation-locked where biological)."""
from __future__ import annotations

import pandas as pd

from neurotcs.io.data_integrity import audit_data_integrity


def _rules(flags):
    return {f["rule_id"] for f in flags}


class TestApoeGenotypeValidity:

    def test_nonexistent_allele_flagged(self):
        en = pd.DataFrame({"subject_id": ["P1"], "apoe_genotype": ["e3/e5"]})
        flags = audit_data_integrity({"EN": en})
        assert any(f["rule_id"] == "genomics_invalid" for f in flags)

    def test_triallelic_genotype_flagged(self):
        en = pd.DataFrame({"subject_id": ["P1"], "apoe_genotype": ["e4/e4/e4"]})
        flags = audit_data_integrity({"EN": en})
        assert any(f["rule_id"] == "genomics_invalid" for f in flags)

    def test_valid_genotypes_pass(self):
        en = pd.DataFrame({
            "subject_id": ["P1", "P2", "P3"],
            "apoe_genotype": ["e3/e4", "e2/e3", "e4/e4"],
        })
        flags = audit_data_integrity({"EN": en})
        assert not any(f["rule_id"] == "genomics_invalid" for f in flags)

    def test_epsilon_notation_accepted(self):
        en = pd.DataFrame({"subject_id": ["P1"], "apoe_genotype": ["\u03b53/\u03b54"]})
        flags = audit_data_integrity({"EN": en})
        assert not any(f["rule_id"] == "genomics_invalid" for f in flags)


class TestCategoricalDomains:

    def test_invalid_sex_flagged(self):
        en = pd.DataFrame({"subject_id": ["P1", "P2"], "sex": ["M", "Q"]})
        flags = audit_data_integrity({"EN": en})
        sx = [f for f in flags if f["rule_id"] == "categorical_invalid"]
        assert len(sx) == 1
        assert sx[0]["subject_id"] == "P2"

    def test_valid_sex_passes(self):
        en = pd.DataFrame({"subject_id": ["P1", "P2"], "sex": ["M", "F"]})
        flags = audit_data_integrity({"EN": en})
        assert not any(f["rule_id"] == "categorical_invalid" for f in flags)


class TestHardBounds:

    def test_negative_education_is_impossible(self):
        en = pd.DataFrame({"subject_id": ["P1"], "education_years": [-2]})
        flags = audit_data_integrity({"EN": en})
        f = [x for x in flags if x["field"].endswith("education_years")]
        assert f and f[0]["tier"] == "impossible"

    def test_excessive_education_is_implausible(self):
        en = pd.DataFrame({"subject_id": ["P1"], "education_years": [45]})
        flags = audit_data_integrity({"EN": en})
        f = [x for x in flags if x["field"].endswith("education_years")]
        assert f and f[0]["tier"] == "implausible"


class TestDuplicateAndOrphan:

    def test_duplicate_visit_flagged(self):
        qs = pd.DataFrame({
            "subject_id": ["P1", "P1", "P2"],
            "visit": [0, 0, 0],
            "clinical_state": ["CN", "CN", "MCI"],
        })
        flags = audit_data_integrity({"QS": qs})
        dups = [f for f in flags if f["rule_id"] == "duplicate_record"]
        assert dups and dups[0]["subject_id"] == "P1"

    def test_orphan_record_flagged(self):
        en = pd.DataFrame({"subject_id": ["P1", "P2"], "sex": ["M", "F"]})
        fl = pd.DataFrame({
            "subject_id": ["P1", "P9999"],
            "visit": [0, 0],
            "plasma_ptau217_pgml": [0.1, 0.2],
        })
        flags = audit_data_integrity({"EN": en, "FL": fl})
        orph = [f for f in flags if f["rule_id"] == "orphan_record"]
        assert orph and orph[0]["subject_id"] == "P9999"


class TestTemporalCadence:

    def test_cadence_break_flagged_not_wallclock(self):
        # 2-year cadence then a 7-year jump -> cadence break (the planted error
        # pattern). NOT flagged merely for being a future date.
        qs = pd.DataFrame({
            "subject_id": ["P1"] * 5,
            "visit": [0, 1, 2, 3, 4],
            "visit_date": ["2020-08-13", "2022-08-16", "2024-08-06",
                           "2026-08-10", "2033-06-15"],
            "clinical_state": ["CN"] * 5,
        })
        flags = audit_data_integrity({"QS": qs})
        ti = [f for f in flags if f["rule_id"] == "temporal_impossible"]
        assert ti and ti[0]["subject_id"] == "P1"

    def test_steady_future_cadence_not_flagged(self):
        # A forward-projected cohort with a steady 2-year cadence must NOT be
        # flagged just because dates are in the future.
        qs = pd.DataFrame({
            "subject_id": ["P1"] * 5,
            "visit": [0, 1, 2, 3, 4],
            "visit_date": ["2024-01-01", "2026-01-01", "2028-01-01",
                           "2030-01-01", "2032-01-01"],
            "clinical_state": ["CN"] * 5,
        })
        flags = audit_data_integrity({"QS": qs})
        assert not any(f["rule_id"] == "temporal_impossible" for f in flags)


class TestTemporalOrdering:
    """The backwards-in-time ordering check must only fire when a TRUSTWORTHY
    numeric visit ordinal exists. Non-numeric visit CODES (ADNI sc/bl/m06/4_sc)
    must NOT be lexically sorted and flagged (that produced thousands of false
    positives on real ADNI DXSUM data). A real numeric ordinal must still catch
    a genuine backwards date.
    """

    def test_nonnumeric_visit_codes_do_not_flag_ordering(self):
        # ADNI-style visit codes; dates are monotonic in true visit order but do
        # NOT sort chronologically as strings ('4_sc' < 'bl' < 'm06' < 'sc').
        df = pd.DataFrame({
            "RID": ["1", "1", "1", "1"],
            "VISCODE2": ["sc", "bl", "m06", "4_sc"],
            "EXAMDATE": ["2010-01-01", "2010-02-01", "2010-08-01", "2023-07-25"],
            "clinical_state": ["CN", "CN", "MCI", "AD"],
        })
        flags = audit_data_integrity({"DXSUM": df})
        assert not any(f["rule_id"] == "temporal_ordering" for f in flags)

    def test_numeric_ordinal_still_catches_backwards_date(self):
        # VISITNUM is a clean numeric ordinal; visit 3's date precedes visit 2.
        df = pd.DataFrame({
            "RID": ["1", "1", "1"],
            "VISITNUM": [1, 2, 3],
            "EXAMDATE": ["2010-01-01", "2010-08-01", "2010-03-01"],
            "clinical_state": ["CN", "CN", "CN"],
        })
        flags = audit_data_integrity({"DXSUM": df})
        to = [f for f in flags if f["rule_id"] == "temporal_ordering"]
        assert to and to[0]["subject_id"] == "1"

    def test_numeric_string_ordinal_is_trusted(self):
        # Visit column stored as numeric STRINGS ("1","2","3") is still a valid
        # ordinal; a backwards date must be caught.
        df = pd.DataFrame({
            "RID": ["1", "1", "1"],
            "visit": ["1", "2", "3"],
            "visit_date": ["2010-01-01", "2010-08-01", "2010-03-01"],
            "clinical_state": ["CN", "CN", "CN"],
        })
        flags = audit_data_integrity({"DX": df})
        assert any(f["rule_id"] == "temporal_ordering" for f in flags)

    def test_monotonic_numeric_ordinal_not_flagged(self):
        df = pd.DataFrame({
            "RID": ["1", "1", "1"],
            "VISITNUM": [1, 2, 3],
            "EXAMDATE": ["2010-01-01", "2010-08-01", "2011-01-01"],
            "clinical_state": ["CN", "CN", "CN"],
        })
        flags = audit_data_integrity({"DXSUM": df})
        assert not any(f["rule_id"] == "temporal_ordering" for f in flags)


class TestProtocolEligibility:

    def test_cn_on_anti_amyloid_flagged(self):
        en = pd.DataFrame({
            "subject_id": ["P1", "P2"],
            "dx_group": ["CN", "MCI"],
            "treatment_assignment": ["lecanemab", "lecanemab"],
        })
        flags = audit_data_integrity({"EN": en})
        pv = [f for f in flags if f["rule_id"] == "protocol_violation"]
        assert len(pv) == 1
        assert pv[0]["subject_id"] == "P1"

    def test_mci_on_anti_amyloid_ok(self):
        en = pd.DataFrame({
            "subject_id": ["P1"],
            "dx_group": ["MCI"],
            "treatment_assignment": ["lecanemab"],
        })
        flags = audit_data_integrity({"EN": en})
        assert not any(f["rule_id"] == "protocol_violation" for f in flags)


class TestDeterminismAndSerialization:

    def test_deterministic(self):
        en = pd.DataFrame({
            "subject_id": ["P1", "P2"],
            "apoe_genotype": ["e3/e5", "e3/e4"],
            "sex": ["M", "Q"],
        })
        f1 = audit_data_integrity({"EN": en})
        f2 = audit_data_integrity({"EN": en})
        assert _rules(f1) == _rules(f2)
        assert len(f1) == len(f2)

    def test_flags_are_json_native(self):
        import json
        en = pd.DataFrame({
            "subject_id": ["P1"],
            "visit": [0],
            "education_years": [-2],
        })
        # numeric int64 / float64 must serialize
        flags = audit_data_integrity({"EN": en})
        json.dumps(flags)  # must not raise


class TestLongFormatDuplicateAwareness:
    """v1.51: CDISC long-format duplicate detection must key on
    (subject, visit, measurement_code), not (subject, visit) -- so valid
    long-format sheets (one row per code per visit) are NOT falsely flagged,
    while a genuine duplicate (same code twice at a visit) IS still caught."""

    def _ndup(self, flags):
        return len([f for f in flags if f["rule_id"] == "duplicate_record"])

    def _long(self, extra=None):
        rows = [{"subject_id": s, "visit": v, "QSTESTCD": c, "QSSTRESN": x}
                for s in ["001", "002", "003"] for v in [1, 2]
                for c, x in [("MMSE", 28), ("CDRSB", 0.5), ("ADASCOG", 15)]]
        if extra:
            rows += extra
        return pd.DataFrame(rows)

    def test_valid_long_format_no_false_duplicate_flood(self):
        # one row per code per (subject, visit) is VALID -- must not flag.
        assert self._ndup(audit_data_integrity({"QS": self._long()})) == 0

    def test_genuine_long_format_duplicate_still_caught(self):
        # same code twice at the same (subject, visit) IS a real duplicate.
        extra = [{"subject_id": "001", "visit": 1, "QSTESTCD": "MMSE",
                  "QSSTRESN": 99}]
        assert self._ndup(audit_data_integrity({"QS": self._long(extra)})) == 1

    def test_wide_format_duplicate_still_caught(self):
        wide = pd.DataFrame({"subject_id": ["A", "A", "B"], "visit": [1, 1, 1],
                             "age": [70, 70, 68]})
        assert self._ndup(audit_data_integrity({"DEMO": wide})) == 1

    def test_paramcd_long_format_recognized(self):
        # ADaM PARAMCD long format must be recognized too.
        adam = pd.DataFrame({
            "subject_id": ["001", "001", "001"], "visit": [1, 1, 1],
            "PARAMCD": ["MMSE", "CDRSB", "ADASCOG"], "AVAL": [28, 0.5, 15]})
        assert self._ndup(audit_data_integrity({"ADQS": adam})) == 0

"""Tests for the typed-read contract (neurotcs.io.typed_read).

Locks the schema-on-read guarantees so a future edit cannot silently
reintroduce the three failure modes:
  * ID collapse (long/leading-zero IDs must stay string, full precision).
  * Locale misparse (EU decimal comma detected and applied; ambiguous stays
    string).
  * Sentinel-as-value (numeric missing codes KEPT, not auto-NA; reported).
Plus downstream-safety: numeric columns still receive numeric dtypes so the
is_numeric_dtype branches keep firing.
"""
from __future__ import annotations

import io

import pandas as pd
import pandas.api.types as ptypes

from neurotcs.io.typed_read import (
    apply_typed_read_contract,
    schema_fingerprint,
)


def _apply(df):
    dec: list[str] = []
    out = apply_typed_read_contract(df, "T", dec)
    return out, dec


class TestIdProtection:

    def test_leading_zero_id_preserved(self):
        df = pd.DataFrame({"subject_id": ["007", "012", "100"]})
        out, _ = _apply(df)
        assert out["subject_id"].tolist() == ["007", "012", "100"]
        assert not ptypes.is_numeric_dtype(out["subject_id"])

    def test_long_numeric_id_not_collapsed_to_float(self):
        # pandas may read a long numeric ID as float; the contract recovers it.
        df = pd.DataFrame({"RID": [1.00000000000123e14, 2.0e14]})
        out, _ = _apply(df)
        assert out["RID"].tolist() == ["100000000000123", "200000000000000"]

    def test_various_id_names_detected(self):
        for col in ["subject_id", "PTID", "USUBJID", "site_id", "record_id",
                    "visit_id", "MRN"]:
            df = pd.DataFrame({col: ["01", "02"]})
            out, _ = _apply(df)
            assert out[col].tolist() == ["01", "02"], col


class TestDecimalConvention:

    def test_eu_decimal_comma_applied(self):
        df = pd.DataFrame({"thickness_mm": ["2,5", "2,4", "2,6"]})
        out, dec = _apply(df)
        assert ptypes.is_numeric_dtype(out["thickness_mm"])
        assert out["thickness_mm"].tolist() == [2.5, 2.4, 2.6]
        assert any("decimal comma" in d for d in dec)

    def test_dot_decimal_default(self):
        df = pd.DataFrame({"val": ["2.5", "2.4"]})
        out, _ = _apply(df)
        assert out["val"].tolist() == [2.5, 2.4]

    def test_clean_integers_stay_integer(self):
        df = pd.DataFrame({"age": ["72", "68", "81"]})
        out, _ = _apply(df)
        assert ptypes.is_integer_dtype(out["age"])
        assert out["age"].tolist() == [72, 68, 81]


class TestSentinelDiscipline:

    def test_numeric_sentinel_kept_not_dropped(self):
        df = pd.DataFrame({"mmse": [28, -9, 30]})
        out, dec = _apply(df)
        # -9 is a real value here, NOT silently turned into NaN.
        assert -9 in out["mmse"].tolist()
        assert any("sentinel" in d.lower() for d in dec)

    def test_textual_na_tokens_become_missing(self):
        df = pd.DataFrame({"score": ["1.0", "NA", "3.0"]})
        out, _ = _apply(df)
        assert ptypes.is_numeric_dtype(out["score"])
        assert out["score"].isna().sum() == 1


class TestDownstreamSafety:

    def test_numeric_columns_remain_numeric(self):
        raw = "subject_id,visit,age,mmse,state\nS1,1,72,28,CN\nS2,1,68,30,MCI\n"
        df = pd.read_csv(io.StringIO(raw))
        out, _ = _apply(df)
        for c in ["visit", "age", "mmse"]:
            assert ptypes.is_numeric_dtype(out[c]), c
        # values intact
        assert out["age"].tolist() == [72, 68]

    def test_values_unchanged_for_clean_numeric(self):
        df = pd.DataFrame({"x": [1.5, 2.5, 3.5]})
        out, _ = _apply(df)
        assert out["x"].tolist() == [1.5, 2.5, 3.5]


class TestProvenance:

    def test_schema_fingerprint_deterministic(self):
        df = pd.DataFrame({"subject_id": ["01"], "age": [72], "v": [1.5]})
        out, _ = _apply(df)
        fp1 = schema_fingerprint(out)
        fp2 = schema_fingerprint(out)
        assert fp1 == fp2
        assert fp1["subject_id"] == "object"
        assert "int" in fp1["age"].lower() or fp1["age"] == "Int64"

    def test_decisions_record_id_typing(self):
        df = pd.DataFrame({"subject_id": ["01", "02"], "age": [1, 2]})
        _, dec = _apply(df)
        assert any("ID" in d and "subject_id" in d for d in dec)


class TestNumericSentinelAssertion:
    """v1.49: operator-asserted numeric missing codes (closes the loop)."""

    def test_default_keeps_sentinel(self):
        df = pd.DataFrame({"mmse": [28, -9, 30]})
        out, _ = _apply(df)
        assert -9 in out["mmse"].tolist()  # unchanged default behavior

    def test_per_column_assertion(self):
        df = pd.DataFrame({"mmse": [28, -9, 30], "temp": [36, -9, 37]})
        dec: list[str] = []
        out = apply_typed_read_contract(df, "T", dec, numeric_na_codes={"mmse": [-9]})
        assert out["mmse"].isna().sum() == 1          # mmse -9 -> NA
        assert -9 in out["temp"].tolist()             # temp untouched
        assert any("asserted" in d for d in dec)

    def test_wildcard_assertion(self):
        df = pd.DataFrame({"a": [1, -999, 3], "b": [-999, 5, 6]})
        out = apply_typed_read_contract(df, "T", [], numeric_na_codes={"*": [-999]})
        assert out["a"].isna().sum() == 1
        assert out["b"].isna().sum() == 1

    def test_assertion_on_coerced_column(self):
        # a string column coerced to numeric should also honor the assertion
        df = pd.DataFrame({"score": ["1.0", "-9", "3.0"]})
        out = apply_typed_read_contract(df, "T", [], numeric_na_codes={"score": [-9]})
        assert out["score"].isna().sum() == 1

    def test_id_columns_never_affected(self):
        df = pd.DataFrame({"subject_id": ["-9", "007"], "age": [-9, 70]})
        out = apply_typed_read_contract(df, "T", [], numeric_na_codes={"*": [-9]})
        # subject_id stays string '-9' (ID protection wins), age -9 -> NA
        assert out["subject_id"].tolist() == ["-9", "007"]
        assert out["age"].isna().sum() == 1


class TestIdColumnNamesHelper:
    """v1.49: read-time ID detection so numeric IDs keep leading zeros."""

    def test_detects_id_columns(self):
        from neurotcs.io.typed_read import id_columns_from_names
        cols = ["USUBJID", "subject_id", "AGE", "site_id", "mmse", "RID"]
        found = set(id_columns_from_names(cols))
        assert {"USUBJID", "subject_id", "site_id", "RID"} <= found
        assert "AGE" not in found and "mmse" not in found

    def test_numeric_id_keeps_leading_zeros_via_reader(self):
        import tempfile
        from pathlib import Path

        from neurotcs.io.readers import read_tables
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.csv"
            p.write_text("subject_id,age\n003,72\n012,68\n")
            tables = read_tables(str(p))
            df = next(iter(tables.values()))
            assert df["subject_id"].tolist() == ["003", "012"]

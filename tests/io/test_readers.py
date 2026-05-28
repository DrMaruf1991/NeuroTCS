"""Tests for neurotcs.io universal readers (v1.24.0)."""
from __future__ import annotations

import warnings

import pandas as pd
import pytest

from neurotcs.io import (
    UnsupportedFormatError,
    describe_tables,
    read_tables,
    tables_to_submission,
)

warnings.filterwarnings("ignore")


def _staging_df():
    return pd.DataFrame({
        "sid": ["P1", "P1", "P2", "P2"],
        "v": [0, 1, 0, 1],
        "date": ["2020-01-01", "2021-01-01", "2020-01-01", "2021-06-01"],
        "st": ["CN", "MCI", "AD", "MCI"],
    })


def test_read_csv(tmp_path):
    f = tmp_path / "d.csv"
    _staging_df().to_csv(f, index=False)
    t = read_tables(f)
    assert "d" in t and len(t["d"]) == 4


def test_read_tsv(tmp_path):
    f = tmp_path / "d.tsv"
    _staging_df().to_csv(f, sep="\t", index=False)
    assert len(read_tables(f)["d"]) == 4


def test_read_excel_all_sheets(tmp_path):
    f = tmp_path / "d.xlsx"
    with pd.ExcelWriter(f) as xl:
        _staging_df().to_excel(xl, sheet_name="A", index=False)
        _staging_df().to_excel(xl, sheet_name="B", index=False)
    t = read_tables(f)
    assert set(t) == {"A", "B"}


def test_read_parquet(tmp_path):
    f = tmp_path / "d.parquet"
    _staging_df().to_parquet(f)
    assert len(read_tables(f)["d"]) == 4


def test_unknown_format_raises(tmp_path):
    f = tmp_path / "d.docx"
    f.write_text("nope")
    with pytest.raises(UnsupportedFormatError):
        read_tables(f)


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        read_tables("/no/such/file.csv")


def test_pdf_off_by_default(tmp_path):
    f = tmp_path / "d.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(UnsupportedFormatError):
        read_tables(f)  # allow_pdf not set -> refuse, do not guess


def test_describe_tables(tmp_path):
    f = tmp_path / "d.csv"
    _staging_df().to_csv(f, index=False)
    desc = describe_tables(read_tables(f))
    assert desc["d"]["shape"] == [4, 4]
    assert "sid" in desc["d"]["columns"]


def test_mapping_builds_submission(tmp_path):
    f = tmp_path / "d.csv"
    _staging_df().to_csv(f, index=False)
    tables = read_tables(f)
    sub = tables_to_submission(tables, {
        "clinical": {"sheet": "d", "subject_id": "sid", "visit": "v",
                     "visit_date": "date", "state": "st"},
    })
    assert "clinical" in sub
    assert list(sub["clinical"].columns) == ["subject_id", "visit", "visit_date", "state"]


def test_mapping_missing_column_fails_closed(tmp_path):
    f = tmp_path / "d.csv"
    _staging_df().to_csv(f, index=False)
    tables = read_tables(f)
    with pytest.raises(ValueError):
        tables_to_submission(tables, {
            "clinical": {"sheet": "d", "subject_id": "WRONG", "visit": "v",
                         "visit_date": "date", "state": "st"},
        })


def test_mapping_missing_sheet_fails_closed(tmp_path):
    f = tmp_path / "d.csv"
    _staging_df().to_csv(f, index=False)
    with pytest.raises(ValueError):
        tables_to_submission(read_tables(f), {
            "clinical": {"sheet": "NOPE", "subject_id": "sid", "visit": "v",
                         "visit_date": "date", "state": "st"},
        })


def test_empty_mapping_fails_closed(tmp_path):
    f = tmp_path / "d.csv"
    _staging_df().to_csv(f, index=False)
    with pytest.raises(ValueError):
        tables_to_submission(read_tables(f), {})


def test_end_to_end_read_then_audit(tmp_path):
    # read a CSV with the universal reader, map it, and run the real audit
    from neurotcs import build_bundle, run_full_audit, verify_bundle
    f = tmp_path / "cohort.csv"
    _staging_df().to_csv(f, index=False)
    tables = read_tables(f)
    sub = tables_to_submission(tables, {
        "clinical": {"sheet": "cohort", "subject_id": "sid", "visit": "v",
                     "visit_date": "date", "state": "st"},
    })
    result = run_full_audit(sub)
    bundle = build_bundle(result)
    assert verify_bundle(bundle) is True
    assert "staging_clinical" in result.manifest.layers_run

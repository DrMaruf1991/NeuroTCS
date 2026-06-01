"""Tests for the universal multi-format / multi-file reader (v1.43.0).

Covers: folder ingestion, zip archives, gz single files, globs, lists,
encoding-honest CSV (utf-8-sig / cp1251 / latin-1 fallback), nested-JSON
refusal, statistical formats, and fail-closed surfacing of skipped files.
"""
from __future__ import annotations

import gzip
import zipfile

import pandas as pd
import pytest

from neurotcs.io.readers import (
    AmbiguousInputError,
    UnsupportedFormatError,
    read_tables,
)


def _write_csv(p, df):
    df.to_csv(p, index=False)


class TestFolderIngestion:

    def test_folder_of_csvs_becomes_multiple_tables(self, tmp_path):
        d = tmp_path / "cohort"
        d.mkdir()
        _write_csv(d / "enrollment.csv", pd.DataFrame({"subject_id": ["P1"]}))
        _write_csv(d / "amyloid.csv",
                   pd.DataFrame({"subject_id": ["P1"], "visit": [0]}))
        tables = read_tables(d)
        assert set(tables.keys()) == {"enrollment", "amyloid"}

    def test_readme_skipped_and_reported(self, tmp_path):
        d = tmp_path / "cohort"
        d.mkdir()
        _write_csv(d / "data.csv", pd.DataFrame({"subject_id": ["P1"]}))
        (d / "README.txt").write_text("notes")
        skipped: list[str] = []
        tables = read_tables(d, skipped=skipped)
        assert "data" in tables
        assert "README.txt" in skipped  # surfaced, not hidden

    def test_empty_folder_refuses(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        (d / "notes.txt").write_text("x")
        with pytest.raises(UnsupportedFormatError):
            read_tables(d)


class TestArchives:

    def test_zip_of_csvs(self, tmp_path):
        z = tmp_path / "c.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("enrollment.csv", "subject_id\nP1\n")
            zf.writestr("amyloid.csv", "subject_id,visit\nP1,0\n")
            zf.writestr("README.md", "notes")
        skipped: list[str] = []
        tables = read_tables(z, skipped=skipped)
        assert set(tables.keys()) == {"enrollment", "amyloid"}
        assert "README.md" in skipped

    def test_gz_single_file(self, tmp_path):
        g = tmp_path / "fl.csv.gz"
        with gzip.open(g, "wt") as fh:
            fh.write("subject_id,visit\nP1,0\n")
        tables = read_tables(g)
        assert "fl" in tables
        assert list(tables["fl"]["subject_id"]) == ["P1"]


class TestGlobAndList:

    def test_glob(self, tmp_path):
        _write_csv(tmp_path / "a.csv", pd.DataFrame({"x": [1]}))
        _write_csv(tmp_path / "b.csv", pd.DataFrame({"x": [2]}))
        tables = read_tables(str(tmp_path / "*.csv"))
        assert set(tables.keys()) == {"a", "b"}

    def test_list_of_files(self, tmp_path):
        f1 = tmp_path / "a.csv"; _write_csv(f1, pd.DataFrame({"x": [1]}))
        f2 = tmp_path / "b.csv"; _write_csv(f2, pd.DataFrame({"x": [2]}))
        tables = read_tables([str(f1), str(f2)])
        assert set(tables.keys()) == {"a", "b"}

    def test_name_collision_disambiguated(self, tmp_path):
        d1 = tmp_path / "s1"; d1.mkdir()
        d2 = tmp_path / "s2"; d2.mkdir()
        _write_csv(d1 / "data.csv", pd.DataFrame({"x": [1]}))
        _write_csv(d2 / "data.csv", pd.DataFrame({"x": [2]}))
        tables = read_tables([str(d1 / "data.csv"), str(d2 / "data.csv")])
        assert "data" in tables and "data_2" in tables


class TestEncodingHonesty:

    def test_cp1251_cyrillic_decoded_and_surfaced(self, tmp_path):
        f = tmp_path / "ru.csv"
        f.write_bytes("subject_id,state\nP1,\u043d\u043e\u0440\u043c\u0430\n".encode("cp1251"))
        decisions: list[str] = []
        tables = read_tables(f, decisions=decisions)
        assert tables["ru"]["state"].iloc[0] == "\u043d\u043e\u0440\u043c\u0430"
        assert any("cp1251" in d for d in decisions)

    def test_utf8_bom_handled(self, tmp_path):
        f = tmp_path / "b.csv"
        f.write_bytes("\ufeffsubject_id,x\nP1,1\n".encode("utf-8"))
        tables = read_tables(f)
        # BOM stripped -> first column name is clean
        assert "subject_id" in tables["b"].columns


class TestFailClosed:

    def test_nested_json_refused(self, tmp_path):
        f = tmp_path / "n.json"
        f.write_text('[{"subject_id":"P1","meta":{"k":1}}]')
        with pytest.raises(AmbiguousInputError):
            read_tables(f)

    def test_flat_json_ok(self, tmp_path):
        f = tmp_path / "flat.json"
        f.write_text('[{"subject_id":"P1","visit":0}]')
        tables = read_tables(f)
        assert "flat" in tables

    def test_unsupported_extension_refused(self, tmp_path):
        f = tmp_path / "x.docx"
        f.write_text("not data")
        with pytest.raises(UnsupportedFormatError):
            read_tables(f)

    def test_single_txt_read_directly(self, tmp_path):
        # a .txt pointed at DIRECTLY is read (only swept folders skip .txt)
        f = tmp_path / "data.txt"
        f.write_text("subject_id,visit\nP1,0\n")
        tables = read_tables(f)
        assert "data" in tables


class TestStatisticalFormats:

    def test_stata_roundtrip(self, tmp_path):
        f = tmp_path / "d.dta"
        df = pd.DataFrame({"subject_id": ["P1", "P2"], "age": [70, 72]})
        df.to_stata(f, write_index=False)
        tables = read_tables(f)
        assert list(tables["d"]["subject_id"]) == ["P1", "P2"]

    def test_spss_gated_when_absent(self, tmp_path, monkeypatch):
        # If pyreadstat is importable, skip; otherwise confirm the gated refusal.
        try:
            import pyreadstat  # noqa: F401
            pytest.skip("pyreadstat present; gating path not exercised")
        except ImportError:
            f = tmp_path / "d.sav"
            f.write_bytes(b"not a real sav")
            with pytest.raises(UnsupportedFormatError):
                read_tables(f)

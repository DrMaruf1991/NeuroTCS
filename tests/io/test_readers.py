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


# Detect whether a parquet engine (pyarrow or fastparquet) is installed.
# Without one, pandas.to_parquet/read_parquet raise ImportError. Skipping
# cleanly is the right behavior so the test suite reports an honest count
# in every environment (introduced v1.33.2 after an external audit caught
# README test-count drift on a parquet-engine-less Windows install).
try:
    import pyarrow  # noqa: F401
    _HAS_PARQUET_ENGINE = True
except ImportError:
    try:
        import fastparquet  # noqa: F401
        _HAS_PARQUET_ENGINE = True
    except ImportError:
        _HAS_PARQUET_ENGINE = False


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


@pytest.mark.skipif(
    not _HAS_PARQUET_ENGINE,
    reason="no parquet engine installed (pyarrow or fastparquet); skip rather than ImportError",
)
def test_read_parquet(tmp_path):
    f = tmp_path / "d.parquet"
    _staging_df().to_parquet(f)
    assert len(read_tables(f)["d"]) == 4


def test_unknown_format_raises(tmp_path):
    f = tmp_path / "d.docx"
    f.write_text("nope")
    with pytest.raises(UnsupportedFormatError):
        read_tables(f)


def test_natural_sort_key_orders_visit_codes_numerically():
    # Derived-date visit ordering must be NATURAL, not lexical: m6 < m12 < m24,
    # v2 < v10. A lexical sort would wrongly place m12 before m6.
    from neurotcs.io.readers import _natural_sort_key
    codes = ["m12", "m6", "bl", "m24", "v2", "v10"]
    ordered = sorted(codes, key=_natural_sort_key)
    assert ordered.index("m6") < ordered.index("m12") < ordered.index("m24")
    assert ordered.index("v2") < ordered.index("v10")
    assert _natural_sort_key("m6") < _natural_sort_key("m12")


def test_rda_extension_recognized(tmp_path):
    # R data packages (e.g. ADNIMERGE2) ship '.rda' files; '.rda' is the same
    # format as '.rdata' and must be read directly (no manual conversion).
    pyreadr = pytest.importorskip("pyreadr")
    df = pd.DataFrame({"RID": ["1", "2"], "DIAGNOSIS": ["CN", "MCI"]})
    f = tmp_path / "DXSUM.rda"
    pyreadr.write_rdata(str(f), df, df_name="DXSUM")
    tables = read_tables(f)
    assert tables, ".rda should be read, not rejected as unsupported"
    got = next(iter(tables.values()))
    assert list(got.columns) == ["RID", "DIAGNOSIS"]


def test_rda_without_pyreadr_gives_actionable_error(tmp_path, monkeypatch):
    # When pyreadr is absent, the error must name the exact install command.
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pyreadr":
            raise ImportError("no pyreadr")
        return real_import(name, *a, **k)

    f = tmp_path / "DXSUM.rda"
    f.write_bytes(b"fake")
    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(UnsupportedFormatError) as ei:
        read_tables(f)
    assert "radni" in str(ei.value) or "pyreadr" in str(ei.value)


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


def test_derived_dates_preserve_natural_visit_order(tmp_path):
    """End-to-end: a file with unpadded visit codes and no date column derives
    dates that preserve bl<m6<m12<m24, yielding a valid forward trajectory."""
    import pandas as pd
    df = pd.DataFrame({
        "subject_id": ["P1", "P1", "P1", "P1"],
        "visit": ["bl", "m6", "m12", "m24"],
        "clinical_state": ["CN", "CN", "MCI", "AD"],
    })
    sub = tables_to_submission({"s": df}, {
        "clinical": {"sheet": "s", "subject_id": "subject_id",
                     "visit": "visit", "state": "clinical_state"},
    })
    # the clinical staging frame must carry visits in natural order
    staged = sub["clinical"]
    visits = list(staged["visit"])
    assert visits == ["bl", "m6", "m12", "m24"], visits


class TestArchiveBombGuardrails:
    """Compressed inputs must fail CLOSED on decompression-bomb patterns
    (oversize member, excessive ratio, too many members, oversize gzip stream)
    rather than exhaust memory. Normal archives must still read. Limits are
    patched in place (no module reload) so no state leaks to sibling tests."""

    def _csv(self):
        return (b"subject_id,visit,visit_date,clinical_state\n"
                b"S1,bl,2010-01-01,CN\nS1,m06,2010-07-01,MCI\n")

    def test_normal_zip_reads(self, tmp_path):
        import zipfile
        z = tmp_path / "ok.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("cohort.csv", self._csv())
        tables = read_tables(z)
        assert next(iter(tables.values())).shape == (2, 4)

    def test_normal_gzip_reads(self, tmp_path):
        import gzip
        g = tmp_path / "cohort.csv.gz"
        with gzip.open(g, "wb") as f:
            f.write(self._csv())
        tables = read_tables(g)
        assert next(iter(tables.values())).shape == (2, 4)

    def test_zip_ratio_bomb_blocked(self, tmp_path, monkeypatch):
        import zipfile

        import neurotcs.io.readers as R
        monkeypatch.setattr(R, "MAX_COMPRESSION_RATIO", 50)
        z = tmp_path / "ratio.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.writestr("big.csv", b"A" * 5_000_000)  # ~1000x ratio
        with pytest.raises(R.ArchiveLimitError):
            read_tables(z)

    def test_zip_member_count_bomb_blocked(self, tmp_path, monkeypatch):
        import zipfile

        import neurotcs.io.readers as R
        monkeypatch.setattr(R, "MAX_ARCHIVE_MEMBERS", 5)
        z = tmp_path / "many.zip"
        with zipfile.ZipFile(z, "w") as zf:
            for i in range(20):
                zf.writestr(f"f{i}.csv", self._csv())
        with pytest.raises(R.ArchiveLimitError):
            read_tables(z)

    def test_zip_oversize_member_blocked(self, tmp_path, monkeypatch):
        import zipfile

        import neurotcs.io.readers as R
        monkeypatch.setattr(R, "MAX_DECOMPRESSED_BYTES", 1_000_000)
        z = tmp_path / "size.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.csv", b"A" * 5_000_000)
        with pytest.raises(R.ArchiveLimitError):
            read_tables(z)

    def test_gzip_oversize_stream_blocked(self, tmp_path, monkeypatch):
        import gzip

        import neurotcs.io.readers as R
        monkeypatch.setattr(R, "MAX_DECOMPRESSED_BYTES", 1_000_000)
        g = tmp_path / "bomb.csv.gz"
        with gzip.open(g, "wb") as f:
            f.write(b"A" * 5_000_000)
        with pytest.raises(R.ArchiveLimitError):
            read_tables(g)

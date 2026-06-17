"""Defect 1 regression: third-party binary parsers (parquet/xlsx/sas/dta/sav/rds)
raise their own exceptions on a corrupt, truncated, or mislabeled file. Those
must be converted to AmbiguousInputError (the input-error type the CLI maps to
EXIT_INPUT) rather than escaping as a raw traceback + exit 1 (FLAGS_PRESENT),
which would mis-report an unreadable file as a clinical finding. Valid files must
still read unchanged (the wrap is transparent on success).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from neurotcs.io.readers import AmbiguousInputError, read_tables

_GARBAGE = b"\x01\x02\x03 not a real binary file \x00\x00"


class TestCorruptBinaryInputsFailClosed:
    """Corrupt/mislabeled binary inputs -> AmbiguousInputError, not a raw crash."""

    def _write(self, tmp_path: Path, ext: str) -> Path:
        f = tmp_path / f"bad{ext}"
        f.write_bytes(_GARBAGE)
        return f

    def test_corrupt_parquet(self, tmp_path):
        with pytest.raises(AmbiguousInputError) as ei:
            read_tables(str(self._write(tmp_path, ".parquet")))
        assert "Parquet" in str(ei.value)
        # message is clean: no traceback object, names the file
        assert "bad.parquet" in str(ei.value)

    def test_corrupt_xlsx(self, tmp_path):
        with pytest.raises(AmbiguousInputError):
            read_tables(str(self._write(tmp_path, ".xlsx")))

    def test_corrupt_sas(self, tmp_path):
        with pytest.raises(AmbiguousInputError):
            read_tables(str(self._write(tmp_path, ".sas7bdat")))

    def test_corrupt_dta(self, tmp_path):
        with pytest.raises(AmbiguousInputError):
            read_tables(str(self._write(tmp_path, ".dta")))

    def test_corrupt_sav(self, tmp_path):
        with pytest.raises(AmbiguousInputError):
            read_tables(str(self._write(tmp_path, ".sav")))

    def test_corrupt_rds(self, tmp_path):
        with pytest.raises(AmbiguousInputError):
            read_tables(str(self._write(tmp_path, ".rds")))

    def test_mislabeled_csv_as_parquet(self, tmp_path):
        """A real-world mistake: CSV bytes saved with a .parquet extension."""
        f = tmp_path / "mislabeled.parquet"
        f.write_text("subject_id,visit,visit_date,clinical_stage\nS1,0,2020-01-01,CN\n",
                     encoding="utf-8")
        with pytest.raises(AmbiguousInputError):
            read_tables(str(f))

    def test_valid_parquet_still_reads(self, tmp_path):
        """Happy path: the wrap is transparent on success -- a valid parquet
        reads exactly as before (proves we wrapped only the parse, not the data)."""
        df = pd.DataFrame({"subject_id": ["S1", "S2"], "visit": [0, 1],
                           "clinical_stage": ["CN", "MCI"]})
        f = tmp_path / "good.parquet"
        df.to_parquet(f)
        tables = read_tables(str(f))
        assert "good" in tables
        assert list(tables["good"]["clinical_stage"]) == ["CN", "MCI"]

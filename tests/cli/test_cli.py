"""Tests for the neurotcs CLI: verbs, exit codes, fail-closed behavior."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import pytest

from neurotcs.cli import (
    EXIT_CLEAN,
    EXIT_FLAGS,
    EXIT_INPUT,
    EXIT_VERIFY,
    main,
)

warnings.filterwarnings("ignore")


def _csv(path: Path, states):
    n = len(states)
    pd.DataFrame({
        "subject_id": ["P1"] * n,
        "visit": list(range(n)),
        "visit_date": pd.date_range("2020-01-01", periods=n, freq="365D").astype(str),
        "state": states,
    }).to_csv(path, index=False)


def _mapping(path: Path, sheet: str):
    path.write_text(json.dumps({
        "clinical": {"sheet": sheet, "subject_id": "subject_id", "visit": "visit",
                     "visit_date": "visit_date", "state": "state"},
        "ranges": [],
    }))


def test_describe_runs(tmp_path, capsys):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI"])
    assert main(["describe", str(f)]) == EXIT_CLEAN
    assert "columns" in capsys.readouterr().out


def test_describe_emits_mapping(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI"])
    m = tmp_path / "map.json"
    assert main(["describe", str(f), "--emit-mapping", str(m)]) == EXIT_CLEAN
    assert m.exists()
    loaded = json.loads(m.read_text())
    assert "clinical" in loaded and loaded["ranges"] == []


def test_audit_clean_exit0(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI", "AD"])  # monotone -> clean
    m = tmp_path / "map.json"
    _mapping(m, "d")
    rc = main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"), "--quiet"])
    assert rc == EXIT_CLEAN
    assert (tmp_path / "out" / "d.bundle.json").exists()
    assert (tmp_path / "out" / "d.report.txt").exists()


def test_audit_flags_exit1(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI", "AD", "CN"])  # covers vocab; AD->CN impossible
    m = tmp_path / "map.json"
    _mapping(m, "d")
    rc = main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"), "--quiet"])
    assert rc == EXIT_FLAGS


def test_audit_optional_csv_svg(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI", "AD", "CN"])
    m = tmp_path / "map.json"
    _mapping(m, "d")
    main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"),
          "--csv", "--svg", "--quiet"])
    assert (tmp_path / "out" / "d.flags.csv").exists()
    assert (tmp_path / "out" / "d.summary.svg").exists()


def test_audit_missing_mapping_exit4(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI"])
    rc = main(["audit", str(f), "--mapping", str(tmp_path / "nope.json"),
               "-o", str(tmp_path / "out"), "--quiet"])
    assert rc == EXIT_INPUT


def test_audit_placeholder_mapping_fails_closed(tmp_path, capsys):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI"])
    m = tmp_path / "map.json"
    m.write_text(json.dumps({"clinical": {"sheet": "d", "subject_id": "<FILL:subject_id>",
                 "visit": "visit", "visit_date": "visit_date", "state": "state"}}))
    rc = main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"), "--quiet"])
    assert rc == EXIT_INPUT
    assert "placeholder" in capsys.readouterr().err.lower()


def test_audit_wrong_column_fails_closed(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI"])
    m = tmp_path / "map.json"
    m.write_text(json.dumps({"clinical": {"sheet": "d", "subject_id": "WRONG",
                 "visit": "visit", "visit_date": "visit_date", "state": "state"}}))
    rc = main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"), "--quiet"])
    assert rc == EXIT_INPUT


def test_audit_unknown_format_exit4(tmp_path):
    f = tmp_path / "d.docx"
    f.write_text("x")
    m = tmp_path / "map.json"
    _mapping(m, "d")
    rc = main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"), "--quiet"])
    assert rc == EXIT_INPUT


def test_verify_ok_and_tampered(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI", "AD", "CN"])
    m = tmp_path / "map.json"
    _mapping(m, "d")
    main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"), "--quiet"])
    bundle_path = tmp_path / "out" / "d.bundle.json"
    assert main(["verify", str(bundle_path)]) == EXIT_CLEAN
    b = json.loads(bundle_path.read_text())
    b["neurotcs_bundle"]["deterministic_core"]["severity_counts"]["impossible"] = 999
    tampered = tmp_path / "t.json"
    tampered.write_text(json.dumps(b))
    assert main(["verify", str(tampered)]) == EXIT_VERIFY


def test_verify_missing_file_exit4(tmp_path):
    assert main(["verify", str(tmp_path / "nope.json")]) == EXIT_INPUT


def test_no_subcommand_errors():
    with pytest.raises(SystemExit):
        main([])


def test_audit_pdf_flag(tmp_path):
    f = tmp_path / "d.csv"
    _csv(f, ["CN", "MCI", "AD", "CN"])
    m = tmp_path / "map.json"
    _mapping(m, "d")
    main(["audit", str(f), "--mapping", str(m), "-o", str(tmp_path / "out"),
          "--pdf", "--quiet"])
    pdf = tmp_path / "out" / "d.report.pdf"
    assert pdf.exists()
    assert pdf.read_bytes()[:5] == b"%PDF-"

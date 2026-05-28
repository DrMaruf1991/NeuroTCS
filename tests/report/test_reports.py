"""Tests for neurotcs.report renderers (pure views over the bundle)."""
from __future__ import annotations

import warnings
import xml.dom.minidom

import pandas as pd

from neurotcs import build_bundle, run_full_audit
from neurotcs.report import bundle_to_svg, flags_to_csv

warnings.filterwarnings("ignore")


def _bundle_with_flags():
    df = pd.DataFrame({
        "subject_id": ["P1", "P1", "P2", "P2"],
        "visit": [0, 1, 0, 1],
        "visit_date": pd.to_datetime(["2020-01-01", "2021-01-01",
                                      "2020-01-01", "2021-01-01"]),
        "state": ["MCI", "AD", "AD", "CN"],  # AD->CN is impossible
    })
    return build_bundle(run_full_audit({"clinical": df}))


def test_csv_has_header_and_rows():
    csv = flags_to_csv(_bundle_with_flags())
    lines = csv.strip().split("\n")
    assert lines[0] == "severity,layer,subject_id,visit,field,observed_value,rule_id,citation,details"
    assert len(lines) >= 2  # at least one flag row
    assert any("impossible" in ln for ln in lines[1:])


def test_csv_empty_when_clean():
    df = pd.DataFrame({
        "subject_id": ["P1", "P1"], "visit": [0, 1],
        "visit_date": pd.to_datetime(["2020-01-01", "2021-01-01"]),
        "state": ["CN", "MCI"],
    })
    csv = flags_to_csv(build_bundle(run_full_audit({"clinical": df})))
    assert csv.strip().split("\n") == [
        "severity,layer,subject_id,visit,field,observed_value,rule_id,citation,details"
    ]


def test_svg_is_well_formed_xml():
    svg = bundle_to_svg(_bundle_with_flags())
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    xml.dom.minidom.parseString(svg)  # raises if malformed


def test_svg_shows_status_and_ctcs():
    svg = bundle_to_svg(_bundle_with_flags())
    assert "FLAGS_PRESENT" in svg
    assert "cTCS" in svg


def test_pdf_is_written_and_valid(tmp_path):
    from neurotcs.report import bundle_to_pdf
    out = tmp_path / "r.pdf"
    p = bundle_to_pdf(_bundle_with_flags(), out)
    assert p == out and out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"  # real PDF header
    assert out.stat().st_size > 500


def test_pdf_clean_bundle(tmp_path):
    from neurotcs.report import bundle_to_pdf
    df = pd.DataFrame({
        "subject_id": ["P1", "P1", "P1"], "visit": [0, 1, 2],
        "visit_date": pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"]),
        "state": ["CN", "MCI", "AD"],
    })
    b = build_bundle(run_full_audit({"clinical": df}))
    out = tmp_path / "clean.pdf"
    bundle_to_pdf(b, out)
    assert out.read_bytes()[:5] == b"%PDF-"

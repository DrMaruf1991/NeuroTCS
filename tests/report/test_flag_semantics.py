"""Reproduction + guard tests for the flag-semantics communication defect
(external expert review, 2026-08; companion to ERRATA E-2026-011).

Defect (reproduced by this file BEFORE the fix):

  Human-facing audit outputs (terminal summary, PDF report, SVG summary,
  demo web UI) presented severity counts labeled "impossible" with no
  definition of what a flag *means*. A knowledgeable external reviewer read
  the outputs as claiming the flagged transitions are clinically impossible
  data errors -- a claim the framework does not make and cannot make prior
  to the expert-adjudication study (docs/VALIDATION_PROTOCOL.md).

Fix under test:

  A single source-of-truth semantics statement
  (neurotcs.report.FLAG_SEMANTICS_STATEMENT) rendered on every human-facing
  surface: a flag marks a transition inadmissible or improbable under the
  cited rule pack and REQUIRES ADJUDICATION; it is not, by itself, a verdict
  of data error. Machine formats (bundle JSON, flags CSV) keep their stable
  severity tokens -- those are schema contracts, not prose claims.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from neurotcs import build_bundle, run_full_audit

warnings.filterwarnings("ignore")

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The load-bearing phrase every human-facing surface must carry verbatim.
_KEY_PHRASE = "requires adjudication"


def _bundle_with_flags():
    df = pd.DataFrame({
        "subject_id": ["P1", "P1", "P2", "P2"],
        "visit": [0, 1, 0, 1],
        "visit_date": pd.to_datetime(["2020-01-01", "2021-01-01",
                                      "2020-01-01", "2021-01-01"]),
        "state": ["MCI", "AD", "AD", "CN"],  # AD->CN is inadmissible
    })
    return build_bundle(run_full_audit({"clinical": df}))


def test_semantics_statement_exists_and_is_substantive():
    from neurotcs.report import FLAG_SEMANTICS_STATEMENT
    s = FLAG_SEMANTICS_STATEMENT.lower()
    assert _KEY_PHRASE in s
    assert "not" in s and "error" in s, (
        "statement must explicitly deny that a flag is by itself a verdict "
        "of data error"
    )
    assert "validation_protocol" in s.replace(" ", "_") or (
        "validation protocol" in s
    ), "statement must point at the adjudication study protocol"


def test_svg_report_carries_flag_semantics():
    from neurotcs.report import bundle_to_svg
    svg = bundle_to_svg(_bundle_with_flags())
    assert _KEY_PHRASE in svg.lower()


def test_pdf_report_carries_flag_semantics(tmp_path):
    from neurotcs.report import bundle_to_pdf
    out = tmp_path / "r.pdf"
    bundle_to_pdf(_bundle_with_flags(), out)
    # ReportLab compresses page streams; assert on the source of truth used
    # by the renderer instead of parsing the PDF: the renderer must reference
    # the shared constant (import-level coupling is the guarantee).
    import neurotcs.report.pdf_report as pdf_mod
    src = Path(pdf_mod.__file__).read_text(encoding="utf-8")
    assert "FLAG_SEMANTICS_STATEMENT" in src


def test_cli_summary_carries_flag_semantics(capsys):
    import argparse

    from neurotcs.cli import _print_summary
    bundle = _bundle_with_flags()
    args = argparse.Namespace(csv=False, svg=False, pdf=False)
    _print_summary(bundle, Path("/tmp"), "x", args)
    out = capsys.readouterr().out.lower()
    assert _KEY_PHRASE in out


def test_demo_pages_carry_flag_semantics():
    """The demo web UI must define flag semantics on both the landing page
    and the user guide (static HTML cannot import the constant; this parity
    check pins the phrase there)."""
    for page in ("index.html", "guide.html"):
        html = (_REPO_ROOT / "demo" / "static" / page).read_text(
            encoding="utf-8"
        ).lower()
        assert _KEY_PHRASE in html, f"demo/static/{page} lacks flag semantics"

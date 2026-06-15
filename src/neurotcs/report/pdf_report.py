"""Render a bundle as a PDF report. Pure view over the fingerprinted core; no recompute.

Uses reportlab (a declared dependency). Lays out the verdict, per-axis cTCS with
its 95% CI, severity counts, a flags table, and provenance. If reportlab is ever
absent the function fails closed with a clear message rather than a cryptic error.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

_STATUS_RGB = {
    "CLEAN": (0.10, 0.56, 0.30),
    "FLAGS_PRESENT": (0.76, 0.37, 0.0),
    "INCOMPLETE_REFUSED": (0.69, 0.0, 0.13),
}


def _core(bundle: dict[str, Any]) -> dict[str, Any]:
    return bundle["neurotcs_bundle"]["deterministic_core"]


def _fmt(x: Any, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "n/a"


def bundle_to_pdf(bundle: dict[str, Any], path: str | Path) -> Path:
    """Write a PDF summary of the bundle to `path`; return the Path.

    Fail-closed: if reportlab is unavailable, raises ImportError with guidance
    rather than producing a partial/blank file.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as e:  # pragma: no cover - reportlab is a declared dep
        raise ImportError(
            "PDF reports need the 'reportlab' package (a declared NeuroTCS "
            "dependency). Install it with: pip install reportlab"
        ) from e

    out = Path(path)
    nb = bundle["neurotcs_bundle"]
    core = _core(bundle)
    status = core.get("status", "UNKNOWN")
    sev = core.get("severity_counts", {})
    axes = core.get("axes", [])
    flags = core.get("flags", {})
    bid = nb.get("bundle_id") or "(none - refused)"
    r, g, b = _STATUS_RGB.get(status, (0.27, 0.27, 0.27))

    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph("NeuroTCS &mdash; Audit Result", styles["Title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f'<font color="#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}">'
        f'<b>Status: {status}</b></font>', styles["Heading2"]))
    story.append(Paragraph(
        f"impossible {sev.get('impossible', 0)} &nbsp; | &nbsp; "
        f"implausible {sev.get('implausible', 0)} &nbsp; | &nbsp; "
        f"informational {sev.get('informational', 0)}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    # per-axis table
    axis_rows = [["Axis", "cTCS", "95% CI", "flagged", "pack"]]
    for ax in axes:
        lo, hi = ax.get("ctcs_ci_95_low"), ax.get("ctcs_ci_95_high")
        ci = f"{_fmt(lo)}-{_fmt(hi)}" if lo is not None and hi is not None else "n/a"
        axis_rows.append([
            str(ax.get("axis", "?")), _fmt(ax.get("ctcs")), ci,
            f"{ax.get('n_flagged', 0)}/{ax.get('n_transitions', 0)}",
            str(ax.get("pack", "")),
        ])
    if len(axis_rows) > 1:
        story.append(Paragraph("<b>Per-axis coherence (cTCS)</b>", styles["Heading3"]))
        t = Table(axis_rows, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f1b2d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2e0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5fa")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    # flags table (impossible + implausible; informational summarized as count)
    flag_rows = [["severity", "layer", "subject", "field", "observed", "rule/detail"]]
    for severity in ("impossible", "implausible"):
        for f in flags.get(severity, []):
            det = f.get("rule_id")
            if not det and f.get("details"):
                d = f["details"]
                det = (f"{d.get('from')}->{d.get('to')}" if "from" in d
                       else f"{d.get('bound_type', '')} {d.get('bound_value', '')}")
            flag_rows.append([
                severity, str(f.get("layer", "")),
                str(f.get("subject_id") or ""), str(f.get("field") or ""),
                str(f.get("observed_value") if f.get("observed_value") is not None else ""),
                str(det or ""),
            ])
    if len(flag_rows) > 1:
        story.append(Paragraph("<b>Flags (impossible &amp; implausible)</b>", styles["Heading3"]))
        ft = Table(flag_rows, hAlign="LEFT", colWidths=[22 * mm, 32 * mm, 20 * mm,
                                                        28 * mm, 22 * mm, 44 * mm])
        ft.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7a1d1d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e0c8c8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(ft)
        story.append(Spacer(1, 4 * mm))
    if sev.get("informational", 0):
        story.append(Paragraph(
            f"<i>{sev['informational']} informational flag(s) omitted from the "
            f"table (not errors). See the flags CSV for the full list.</i>",
            styles["Normal"]))
        story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f'<font size="7" color="#6c829e">bundle {str(bid)[:32]}... &nbsp;|&nbsp; '
        f'framework {core.get("framework_version", "?")} &nbsp;|&nbsp; '
        f'format {core.get("bundle_format_version", "?")}</font>', styles["Normal"]))

    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            title="NeuroTCS Audit Result")
    doc.build(story)
    return out

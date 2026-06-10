#!/usr/bin/env python3
"""NeuroTCS Audit Report -- professional PDF report generator.

Reads the outputs NeuroTCS already produces (the *.bundle.json signed result and
the *.flags.csv flag table) and renders a polished, presentation-grade PDF:

  - a summary dashboard (status, severity counts, per-axis cTCS with 95% CI);
  - a severity-tiered flag register with Patient ID, visit, column, observed
    value, rule, and citation -- every flag, scalable to thousands of rows;
  - an error-type / layer breakdown;
  - the coverage manifest (which layers ran, which were skipped and why);
  - optional benchmark reconciliation if an answer key + hard-negatives are
    supplied (caught / missed / false-positive accounting).

DESIGN NOTES (deliberate, world-class choices)
----------------------------------------------
* This is a PRESENTATION LAYER. It does not touch the verified NeuroTCS core or
  alter any value; it only reads and renders the signed bundle + flags. The
  bundle_id and audit_ids are reproduced verbatim so the report is traceable to
  the exact audit run.
* Visual language is PROFESSIONAL SCIENTIFIC ICONOGRAPHY, not playful emoji:
  severity is conveyed by color-coded badges and geometric glyphs (filled
  triangle = impossible, filled circle = implausible, hollow circle =
  informational). This keeps the report credible for journal/regulatory/clinical
  audiences -- the audience that matters for a tool moving toward validation.
* Nothing is fabricated: citations, values, and counts are reproduced exactly
  from the bundle/flags. The report adds no clinical interpretation of its own.

USAGE
-----
    python neurotcs_report.py --bundle audit/X.bundle.json --flags audit/X.flags.csv \
        --out NeuroTCS_Audit_Report.pdf [--title "..."] \
        [--answer-key key.csv --hard-negatives hn.csv]
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd
from reportlab.graphics.shapes import Circle, Drawing, Rect, String, Wedge
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------- #
# Palette -- a restrained, professional clinical-report scheme (dark navy +
# severity accents). Severity colors are colorblind-aware (red/amber/slate).
# --------------------------------------------------------------------------- #
NAVY = colors.HexColor("#0B1F3A")
NAVY_LIGHT = colors.HexColor("#16385F")
INK = colors.HexColor("#1A2330")
MUTED = colors.HexColor("#5B6675")
HAIRLINE = colors.HexColor("#D6DCE4")
PANEL_BG = colors.HexColor("#F4F7FB")
WHITE = colors.white

SEV = {
    "impossible": {
        "color": colors.HexColor("#B3261E"),   # deep red
        "bg": colors.HexColor("#FBE9E7"),
        "glyph": "\u25B2",                       # filled triangle
        "label": "IMPOSSIBLE",
    },
    "implausible": {
        "color": colors.HexColor("#B26A00"),    # amber
        "bg": colors.HexColor("#FFF3E0"),
        "glyph": "\u25CF",                       # filled circle
        "label": "IMPLAUSIBLE",
    },
    "informational": {
        "color": colors.HexColor("#37474F"),    # slate
        "bg": colors.HexColor("#ECEFF1"),
        "glyph": "\u25CB",                       # hollow circle
        "label": "INFORMATIONAL",
    },
}
SEV_ORDER = ["impossible", "implausible", "informational"]


def _styles():
    ss = getSampleStyleSheet()
    out = {}
    out["title"] = ParagraphStyle("t", parent=ss["Title"], textColor=WHITE,
                                  fontSize=22, leading=26, alignment=TA_LEFT,
                                  fontName="Helvetica-Bold")
    out["subtitle"] = ParagraphStyle("st", parent=ss["Normal"], textColor=colors.HexColor("#AFC2DA"),
                                     fontSize=10.5, leading=14, fontName="Helvetica")
    out["h2"] = ParagraphStyle("h2", parent=ss["Heading2"], textColor=NAVY,
                               fontSize=14, leading=18, spaceBefore=14, spaceAfter=6,
                               fontName="Helvetica-Bold")
    out["h3"] = ParagraphStyle("h3", parent=ss["Heading3"], textColor=NAVY_LIGHT,
                               fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=3,
                               fontName="Helvetica-Bold")
    out["body"] = ParagraphStyle("b", parent=ss["Normal"], textColor=INK,
                                 fontSize=9.5, leading=13, fontName="Helvetica")
    out["small"] = ParagraphStyle("s", parent=ss["Normal"], textColor=MUTED,
                                  fontSize=7.8, leading=10, fontName="Helvetica")
    out["cell"] = ParagraphStyle("c", parent=ss["Normal"], textColor=INK,
                                 fontSize=7.6, leading=9.5, fontName="Helvetica")
    out["cell_mono"] = ParagraphStyle("cm", parent=ss["Normal"], textColor=INK,
                                      fontSize=7.6, leading=9.5, fontName="Courier")
    out["cell_b"] = ParagraphStyle("cb", parent=ss["Normal"], textColor=NAVY,
                                   fontSize=7.6, leading=9.5, fontName="Helvetica-Bold")
    out["cell_h"] = ParagraphStyle("ch", parent=ss["Normal"], textColor=WHITE,
                                   fontSize=7.8, leading=10, fontName="Helvetica-Bold")
    out["kpi_num"] = ParagraphStyle("kn", parent=ss["Normal"], fontSize=26, leading=28,
                                    alignment=TA_CENTER, fontName="Helvetica-Bold")
    out["kpi_lab"] = ParagraphStyle("kl", parent=ss["Normal"], fontSize=8, leading=10,
                                    alignment=TA_CENTER, textColor=MUTED,
                                    fontName="Helvetica-Bold")
    return out


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #

def load_audit(bundle_path: str, flags_path: str) -> dict:
    with open(bundle_path) as fh:
        b = json.load(fh)
    nb = b.get("neurotcs_bundle", b)
    core = nb["deterministic_core"]
    flags = pd.read_csv(flags_path, dtype=str).fillna("")
    # split "field" -> sheet:column
    def col_of(x):
        return x.split(":", 1)[1] if ":" in x else x
    flags["column"] = flags["field"].map(col_of)
    # parse the reason out of details JSON when present
    def reason_of(d):
        if not d:
            return ""
        try:
            obj = json.loads(d)
            det = obj.get("details", {})
            if isinstance(det, dict):
                # common shapes: {"reason": ...} or {"from":..,"to":..}
                if "reason" in det:
                    return str(det["reason"])
                if "from" in det and "to" in det:
                    return f"transition {det.get('from')} -> {det.get('to')}"
            return ""
        except (ValueError, TypeError):
            return ""
    flags["reason"] = flags["details"].map(reason_of)
    return {
        "bundle_id": nb.get("bundle_id", ""),
        "status": core.get("status", ""),
        "severity_counts": core.get("severity_counts", {}),
        "axes": core.get("axes", []),
        "coverage": core.get("coverage", {}),
        "run_metadata": nb.get("run_metadata", {}),
        "flags": flags,
    }


# --------------------------------------------------------------------------- #
# Header / footer band
# --------------------------------------------------------------------------- #

def _make_header_footer(title_line: str):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = landscape(A4)
        # top navy band
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 14 * mm, w, 14 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(14 * mm, h - 9 * mm, "NeuroTCS Audit Report")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#AFC2DA"))
        canvas.drawRightString(w - 14 * mm, h - 9 * mm, title_line)
        # footer hairline + page no + provenance note
        canvas.setStrokeColor(HAIRLINE)
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 11 * mm, w - 14 * mm, 11 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(14 * mm, 7 * mm,
                          "Presentation layer over the signed NeuroTCS bundle; values and citations reproduced verbatim. "
                          "Software-audit output -- not clinical validation evidence.")
        canvas.drawRightString(w - 14 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def _sev_badge(sev: str, st) -> Table:
    s = SEV[sev]
    p = Paragraph(f'<font color="{s["color"].hexval()}">{s["glyph"]}</font> '
                  f'<font color="{s["color"].hexval()}"><b>{s["label"]}</b></font>',
                  ParagraphStyle("bd", fontSize=8, leading=10, fontName="Helvetica-Bold"))
    t = Table([[p]], colWidths=[34 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), s["bg"]),
        ("BOX", (0, 0), (-1, -1), 0.5, s["color"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _kpi_card(num, label, color, st):
    inner = Table([[Paragraph(f'<font color="{color.hexval()}">{num}</font>', st["kpi_num"])],
                   [Paragraph(label, st["kpi_lab"])]], colWidths=[42 * mm])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, HAIRLINE),
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 0), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return inner


def build_summary(data: dict, st, title: str) -> list:
    story = []
    sc = data["severity_counts"]
    total = sum(int(v) for v in sc.values())
    # title block on navy
    tb = Table([[Paragraph(title, st["title"])],
                [Paragraph("Citation-locked longitudinal disease-state audit &nbsp;&bull;&nbsp; "
                           "generated " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                           st["subtitle"])]], colWidths=[26 * cm])
    tb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, 0), 14), ("BOTTOMPADDING", (0, 1), (-1, 1), 14),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story += [tb, Spacer(1, 10)]

    # KPI row
    cards = [
        _kpi_card(str(total), "TOTAL FLAGS", NAVY, st),
        _kpi_card(str(sc.get("impossible", 0)), "IMPOSSIBLE", SEV["impossible"]["color"], st),
        _kpi_card(str(sc.get("implausible", 0)), "IMPLAUSIBLE", SEV["implausible"]["color"], st),
        _kpi_card(str(sc.get("informational", 0)), "INFORMATIONAL", SEV["informational"]["color"], st),
        _kpi_card(data["status"].replace("_", " ").title() or "-", "STATUS", NAVY_LIGHT, st),
    ]
    krow = Table([cards], colWidths=[5 * cm] * 5)
    krow.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 3),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    story += [krow, Spacer(1, 12)]

    # per-axis cTCS panel
    story.append(Paragraph("Trajectory coherence by axis (cTCS, 95% CI)", st["h3"]))
    rows = [[Paragraph("<b>Axis</b>", st["cell_h"]), Paragraph("<b>Rule pack</b>", st["cell_h"]),
             Paragraph("<b>cTCS</b>", st["cell_h"]), Paragraph("<b>95% CI</b>", st["cell_h"]),
             Paragraph("<b>Transitions</b>", st["cell_h"]), Paragraph("<b>Flagged</b>", st["cell_h"]),
             Paragraph("<b>audit_id</b>", st["cell_h"])]]
    for ax in data["axes"]:
        rows.append([
            Paragraph(ax.get("axis", ""), st["cell"]),
            Paragraph(ax.get("pack", ""), st["cell"]),
            Paragraph(f'{ax.get("ctcs", 0):.4f}', st["cell"]),
            Paragraph(f'{ax.get("ctcs_ci_95_low", 0):.4f}\u2013{ax.get("ctcs_ci_95_high", 0):.4f}', st["cell"]),
            Paragraph(str(ax.get("n_transitions", "")), st["cell"]),
            Paragraph(str(ax.get("n_flagged", "")), st["cell"]),
            Paragraph((ax.get("audit_id", "") or "")[:16] + "\u2026", st["cell_mono"]),
        ])
    t = Table(rows, colWidths=[3.6 * cm, 5.4 * cm, 2 * cm, 3.2 * cm, 2.6 * cm, 2 * cm, 3.6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, HAIRLINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [t, Spacer(1, 6)]
    story.append(Paragraph(
        "cTCS = citation-locked Trajectory Coherence Score (fraction of admissible transitions). "
        "bundle_id " + data["bundle_id"][:24] + "\u2026 &bull; CI by BCa bootstrap. "
        "A flag marks a record for human review; it is a candidate, not a confirmed error.",
        st["small"]))
    return story


def build_flag_register(data: dict, st) -> list:
    story = [PageBreak(), Paragraph("Flag register", st["h2"]),
             Paragraph("Every flag, grouped by severity tier. Columns: Patient ID, visit, data column, "
                       "observed value, rule, and the source citation (truncated; full text in the bundle).",
                       st["body"]), Spacer(1, 6)]
    flags = data["flags"]
    for sev in SEV_ORDER:
        sub = flags[flags["severity"] == sev]
        if sub.empty:
            continue
        story.append(Spacer(1, 4))
        story.append(_sev_badge(sev, st))
        story.append(Spacer(1, 3))
        header = [Paragraph("<b>Patient ID</b>", st["cell_h"]), Paragraph("<b>Visit</b>", st["cell_h"]),
                  Paragraph("<b>Column</b>", st["cell_h"]), Paragraph("<b>Observed</b>", st["cell_h"]),
                  Paragraph("<b>Layer / rule</b>", st["cell_h"]),
                  Paragraph("<b>Why (reason / citation)</b>", st["cell_h"])]
        rows = [header]
        for _, r in sub.iterrows():
            why = r["reason"] or r["citation"]
            why = (why[:240] + "\u2026") if len(why) > 240 else why
            rows.append([
                Paragraph(r["subject_id"], st["cell_mono"]),
                Paragraph(str(r["visit"]), st["cell"]),
                Paragraph(r["column"], st["cell_mono"]),
                Paragraph(str(r["observed_value"])[:24], st["cell"]),
                Paragraph(f'{r["layer"]}<br/><font size=6.5 color="#5B6675">{r["rule_id"]}</font>', st["cell"]),
                Paragraph(why, st["cell"]),
            ])
        t = Table(rows, colWidths=[2.7 * cm, 1.3 * cm, 3.2 * cm, 2.6 * cm, 4.2 * cm, 11.7 * cm],
                  repeatRows=1)
        sc = SEV[sev]["color"]
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), sc),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL_BG]),
            ("GRID", (0, 0), (-1, -1), 0.4, HAIRLINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [t, Spacer(1, 8)]
    return story


def build_breakdown(data: dict, st) -> list:
    flags = data["flags"]
    story = [PageBreak(), Paragraph("Breakdown by rule and layer", st["h2"])]
    # by rule_id x severity
    g = flags.groupby(["layer", "rule_id", "severity"]).size().reset_index(name="n")
    g = g.sort_values(["layer", "n"], ascending=[True, False])
    rows = [[Paragraph("<b>Layer</b>", st["cell_h"]), Paragraph("<b>Rule</b>", st["cell_h"]),
             Paragraph("<b>Severity</b>", st["cell_h"]), Paragraph("<b>Count</b>", st["cell_h"])]]
    for _, r in g.iterrows():
        s = SEV.get(r["severity"], SEV["informational"])
        rows.append([
            Paragraph(r["layer"], st["cell"]),
            Paragraph(r["rule_id"], st["cell_mono"]),
            Paragraph(f'<font color="{s["color"].hexval()}">{s["glyph"]} {r["severity"]}</font>', st["cell"]),
            Paragraph(str(r["n"]), st["cell_b"]),
        ])
    t = Table(rows, colWidths=[4 * cm, 8 * cm, 4 * cm, 2 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, HAIRLINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [t, Spacer(1, 12)]
    # coverage manifest
    cov = data["coverage"]
    story.append(Paragraph("Coverage manifest", st["h3"]))
    lr = ", ".join(cov.get("layers_run", []))
    sk = cov.get("layers_skipped", {})
    story.append(Paragraph(f"<b>Layers run:</b> {lr}", st["body"]))
    if sk:
        story.append(Paragraph("<b>Layers skipped:</b> "
                               + "; ".join(f"{k} ({v})" for k, v in sk.items()), st["body"]))
    else:
        story.append(Paragraph("<b>Layers skipped:</b> none \u2014 full coverage on the wired axes.", st["body"]))
    return story


def build_reconciliation(data: dict, key_path: str, hn_path: str, st) -> list:
    """Optional: if an answer key + hard-negatives are supplied (benchmark mode),
    reconcile flags against ground truth for the staging axes."""
    key = pd.read_csv(key_path, dtype=str).fillna("")
    hn = pd.read_csv(hn_path, dtype=str).fillna("")
    flags = data["flags"]
    fb = set(flags[flags["layer"] == "staging_biological"]["subject_id"])
    fc = set(flags[flags["layer"] == "staging_clinical"]["subject_id"])
    kb = set(key[key["error_type"] == "biological_stage_regression"]["subject_id"])
    kc = set(key[key["error_type"] == "clinical_stage_regression"]["subject_id"])
    hn_subj = set(hn["subject_id"])

    def line(axis, flagged, keyed):
        caught = len(flagged & keyed)
        missed = sorted(keyed - flagged)
        fp_hn = sorted(flagged & hn_subj)
        unexpected = sorted(flagged - keyed - hn_subj)
        return [axis, f"{caught}/{len(keyed)}", str(len(missed)),
                str(len(fp_hn)), str(len(unexpected))]

    story = [PageBreak(), Paragraph("Benchmark reconciliation (ground-truth)", st["h2"]),
             Paragraph("Staging flags vs. the seeded answer key and hard-negatives. "
                       "This section appears only when a benchmark key is supplied.", st["body"]),
             Spacer(1, 6)]
    rows = [[Paragraph("<b>Axis</b>", st["cell_h"]), Paragraph("<b>Caught</b>", st["cell_h"]),
             Paragraph("<b>Missed</b>", st["cell_h"]),
             Paragraph("<b>FP on hard-neg</b>", st["cell_h"]),
             Paragraph("<b>Unexpected</b>", st["cell_h"])]]
    for axis, fl, ky in [("staging_clinical", fc, kc), ("staging_biological", fb, kb)]:
        rows.append([Paragraph(c, st["cell"]) for c in line(axis, fl, ky)])
    t = Table(rows, colWidths=[5 * cm, 3 * cm, 3 * cm, 4 * cm, 3 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, HAIRLINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, Spacer(1, 8),
              Paragraph("FP on hard-neg = false positives on valid-but-suspicious rows (TRAC "
                        "clearance, pre-dementia reversion). Unexpected = flagged subjects neither "
                        "keyed nor hard-negative. Both should be 0 for a clean reconciliation.",
                        st["small"])]
    return story


def build(data: dict, out_path: str, title: str, key_path=None, hn_path=None):
    st = _styles()
    doc = SimpleDocTemplate(out_path, pagesize=landscape(A4),
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=18 * mm, bottomMargin=14 * mm,
                            title="NeuroTCS Audit Report")
    story = []
    story += build_summary(data, st, title)
    story += build_visual_summary(data, st)
    if key_path and hn_path and os.path.exists(key_path) and os.path.exists(hn_path):
        story += build_reconciliation(data, key_path, hn_path, st)
    story += build_per_subject(data, st)
    story += build_flag_register(data, st)
    story += build_breakdown(data, st)
    story += build_citations(data, st)
    story += build_methods_scope(data, st)
    hf = _make_header_footer(title)
    doc.build(story, onFirstPage=hf, onLaterPages=hf)


def main():
    ap = argparse.ArgumentParser(description="NeuroTCS professional PDF audit report")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--flags", required=True)
    ap.add_argument("--out", default="NeuroTCS_Audit_Report.pdf")
    ap.add_argument("--title", default="Alzheimer's Cohort Data Audit")
    ap.add_argument("--answer-key", default=None)
    ap.add_argument("--hard-negatives", default=None)
    args = ap.parse_args()
    data = load_audit(args.bundle, args.flags)
    build(data, args.out, args.title, args.answer_key, args.hard_negatives)
    print(f"wrote {args.out}  ({sum(int(v) for v in data['severity_counts'].values())} flags)")



# --------------------------------------------------------------------------- #
# Vector chart helpers (manual shapes -> robust, crisp, no external deps).
# --------------------------------------------------------------------------- #

def hbar_chart(items, width=240, bar_h=14, gap=8, max_label=26, title=None):
    """items: list of (label, value, color). Horizontal bars with value labels.
    Degrades gracefully on empty input."""
    items = [(str(lab), float(v), c) for lab, v, c in items if v is not None]
    n = len(items)
    label_w = 120
    plot_w = width - label_w - 36
    top_pad = 18 if title else 6
    h = top_pad + n * (bar_h + gap) + 6
    d = Drawing(width, max(h, 24))
    if title:
        d.add(String(0, h - 12, title, fontName="Helvetica-Bold", fontSize=9,
                     fillColor=NAVY))
    vmax = max((v for _, v, _ in items), default=1) or 1
    y = h - top_pad - bar_h
    for label, value, color in items:
        lab = label if len(label) <= max_label else label[:max_label - 1] + "\u2026"
        d.add(String(0, y + 3, lab, fontName="Helvetica", fontSize=7.5, fillColor=INK))
        bw = (value / vmax) * plot_w
        d.add(Rect(label_w, y, max(bw, 0.5), bar_h, fillColor=color, strokeColor=None))
        d.add(String(label_w + max(bw, 0.5) + 4, y + 3, str(int(value)),
                     fontName="Helvetica-Bold", fontSize=7.5, fillColor=MUTED))
        y -= (bar_h + gap)
    return d


def donut_chart(items, size=120, hole=0.55, title=None):
    """items: list of (label, value, color). Donut. Robust on zeros."""
    items = [(str(lab), float(v), c) for lab, v, c in items if (v or 0) > 0]
    total = sum(v for _, v, _ in items) or 1
    top_pad = 16 if title else 0
    d = Drawing(size, size + top_pad)
    if title:
        d.add(String(0, size + 2, title, fontName="Helvetica-Bold", fontSize=9, fillColor=NAVY))
    cx = cy = size / 2
    r = size / 2 - 2
    start = 90.0
    for _, value, color in items:
        sweep = 360.0 * (value / total)
        d.add(Wedge(cx, cy, r, start - sweep, start, fillColor=color, strokeColor=WHITE,
                    strokeWidth=1))
        start -= sweep
    d.add(Circle(cx, cy, r * hole, fillColor=WHITE, strokeColor=None))
    d.add(String(cx, cy + 2, str(int(total)), fontName="Helvetica-Bold", fontSize=16,
                 fillColor=NAVY, textAnchor="middle"))
    d.add(String(cx, cy - 11, "FLAGS", fontName="Helvetica-Bold", fontSize=6.5,
                 fillColor=MUTED, textAnchor="middle"))
    return d


def build_visual_summary(data: dict, st) -> list:
    flags = data["flags"]
    sc = data["severity_counts"]
    story = [PageBreak(), Paragraph("Visual summary", st["h2"]),
             Paragraph("Where the flags concentrate, by severity, audit layer, and rule.",
                       st["body"]), Spacer(1, 8)]
    # row 1: donut (severity) + by-layer bar
    donut = donut_chart([(SEV[s]["label"], int(sc.get(s, 0)), SEV[s]["color"]) for s in SEV_ORDER],
                        size=120, title="Severity distribution")
    by_layer = (flags.groupby("layer").size().sort_values(ascending=False))
    layer_bar = hbar_chart([(k, int(v), NAVY_LIGHT) for k, v in by_layer.items()],
                           width=300, title="Flags by audit layer")
    row1 = Table([[donut, layer_bar]], colWidths=[6 * cm, 11 * cm])
    row1.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [row1, Spacer(1, 10)]
    # row 2: top rules
    by_rule = flags.groupby("rule_id").size().sort_values(ascending=False).head(12)
    # color each rule bar by its dominant severity
    rule_sev = (flags.groupby("rule_id")["severity"]
                .agg(lambda s: s.value_counts().index[0]))
    rule_items = [(k, int(v), SEV.get(rule_sev.get(k, "informational"), SEV["informational"])["color"])
                  for k, v in by_rule.items()]
    story.append(Paragraph("Top rules by flag count", st["h3"]))
    story.append(hbar_chart(rule_items, width=520, max_label=40))
    return story


def build_per_subject(data: dict, st) -> list:
    """Per-subject triage view: one row per flagged subject, ranked worst-first
    (most impossible flags, then total), with per-tier counts and affected
    columns. Complements the by-severity register with a clinician's reading."""
    flags = data["flags"]
    story = [PageBreak(), Paragraph("Per-subject summary", st["h2"]),
             Paragraph("Every flagged subject, ranked worst-first (impossible flags, then total). "
                       "Use this to review one patient's full flag profile at a glance; the flag "
                       "register has the row-level detail.", st["body"]), Spacer(1, 6)]
    rows_data = []
    for sid, g in flags.groupby("subject_id"):
        n_imp = int((g["severity"] == "impossible").sum())
        n_impl = int((g["severity"] == "implausible").sum())
        n_info = int((g["severity"] == "informational").sum())
        cols = sorted(set(g["column"]))
        rows_data.append((sid, n_imp, n_impl, n_info, n_imp + n_impl + n_info, cols))
    rows_data.sort(key=lambda r: (-r[1], -r[4], r[0]))
    header = [Paragraph("<b>Patient ID</b>", st["cell_h"]),
              Paragraph("<b>Impossible</b>", st["cell_h"]),
              Paragraph("<b>Implausible</b>", st["cell_h"]),
              Paragraph("<b>Informational</b>", st["cell_h"]),
              Paragraph("<b>Total</b>", st["cell_h"]),
              Paragraph("<b>Columns affected</b>", st["cell_h"])]
    rows = [header]
    for sid, ni, nl, nf, tot, cols in rows_data:
        def cnt(n, sev):
            if n == 0:
                return Paragraph("\u2013", st["cell"])
            c = SEV[sev]["color"].hexval()
            return Paragraph(f'<font color="{c}"><b>{n}</b></font>', st["cell"])
        sid_disp = sid if str(sid).strip() else "(cohort-level / cross-sheet \u2014 no subject_id)"
        rows.append([
            Paragraph(sid_disp, st["cell_mono"] if str(sid).strip() else st["cell"]),
            cnt(ni, "impossible"), cnt(nl, "implausible"),
            cnt(nf, "informational"), Paragraph(f"<b>{tot}</b>", st["cell_b"]),
            Paragraph(", ".join(cols), st["cell"]),
        ])
    t = Table(rows, colWidths=[3 * cm, 2.4 * cm, 2.4 * cm, 2.6 * cm, 1.6 * cm, 14 * cm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, HAIRLINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (4, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    n_real = sum(1 for r in rows_data if str(r[0]).strip())
    story += [t, Spacer(1, 6),
              Paragraph(f"{n_real} subjects carry at least one subject-level flag "
                        "(cross-sheet/cohort-level flags without a subject_id are shown as a "
                        "single aggregate row).", st["small"])]
    return story


def build_citations(data: dict, st) -> list:
    """Citations appendix: one entry per UNIQUE rule (deduped), with the full
    citation text reproduced verbatim from the bundle."""
    flags = data["flags"]
    story = [PageBreak(), Paragraph("Citations appendix", st["h2"]),
             Paragraph("Every rule that fired, with its full source citation reproduced verbatim "
                       "from the signed bundle. One entry per rule (deduplicated).", st["body"]),
             Spacer(1, 6)]
    seen = {}
    for _, r in flags.iterrows():
        rid = r["rule_id"]
        if rid not in seen and r["citation"]:
            seen[rid] = (r["layer"], r["citation"])
    rows = [[Paragraph("<b>Rule</b>", st["cell_h"]), Paragraph("<b>Layer</b>", st["cell_h"]),
             Paragraph("<b>Citation (verbatim)</b>", st["cell_h"])]]
    for rid in sorted(seen):
        layer, cite = seen[rid]
        rows.append([Paragraph(rid, st["cell_mono"]), Paragraph(layer, st["cell"]),
                     Paragraph(cite, st["cell"])])
    t = Table(rows, colWidths=[4.5 * cm, 3.5 * cm, 18 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, HAIRLINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    return story


def build_methods_scope(data: dict, st) -> list:
    rm = data["run_metadata"]
    story = [PageBreak(), Paragraph("Methods, provenance & scope", st["h2"])]
    story.append(Paragraph("Provenance", st["h3"]))
    prov = [
        f"<b>Bundle ID:</b> {data['bundle_id']}",
        f"<b>Status:</b> {data['status']}",
        f"<b>Generated (audit):</b> {rm.get('generated_at_utc', '-')}",
        f"<b>Platform:</b> {rm.get('platform', '-')} &bull; Python {rm.get('python_version', '-')}",
    ]
    for p in prov:
        story.append(Paragraph(p, st["body"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("What a flag means", st["h3"]))
    story.append(Paragraph(
        "Each flag marks a record as a <b>candidate</b> for human review \u2014 it is one of three "
        "things: a genuine data-quality problem, legitimate-but-rare biology the rule did not "
        "anticipate, or an over-strict rule. NeuroTCS surfaces candidates; the reviewer adjudicates "
        "which is which. Severity tiers (impossible / implausible / informational) rank how strongly "
        "the rule was violated, not certainty of error.", st["body"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Scope and honest limitations", st["h3"]))
    story.append(Paragraph(
        "NeuroTCS is a reproducible, citation-locked <b>auditor</b>: it audits values other tools "
        "produced against published staging and coherence rules; it never measures biomarkers. "
        "This report is <b>software-audit output</b> \u2014 it demonstrates the tool behaves correctly "
        "against the encoded rules. It is <b>not clinical-validation evidence</b>: the flag precision "
        "(positive predictive value) of the tool on real cohorts requires a separate, pre-registered "
        "study with blinded board-certified adjudication (Arm A). A clean report here does not assert "
        "clinical validity.", st["body"]))
    return story


if __name__ == "__main__":
    main()


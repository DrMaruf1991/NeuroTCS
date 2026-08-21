"""Render a bundle as a self-contained summary SVG. Pure view; no recompute.

Dependency-free (emits an SVG string). Shows status, per-axis cTCS with its 95%
CI as an error bar, severity counts, and provenance. Colours are chosen for
projection legibility; all text is real <text> (not paths) so it stays
searchable/accessible.
"""
from __future__ import annotations

from html import escape
from typing import Any

_STATUS_COLOR = {
    "CLEAN": "#1a8f4c",
    "FLAGS_PRESENT": "#c25e00",
    "INCOMPLETE_REFUSED": "#b00020",
}


def _core(bundle: dict[str, Any]) -> dict[str, Any]:
    return bundle["neurotcs_bundle"]["deterministic_core"]


def _fmt(x: Any, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "n/a"


def bundle_to_svg(bundle: dict[str, Any], *, width: int = 720) -> str:
    """Return a standalone SVG (string) summarizing the bundle."""
    nb = bundle["neurotcs_bundle"]
    core = _core(bundle)
    status = core.get("status", "UNKNOWN")
    sev = core.get("severity_counts", {})
    axes = core.get("axes", [])
    bid = nb.get("bundle_id") or "(none - refused)"
    status_col = _STATUS_COLOR.get(status, "#444")

    # layout
    pad = 24
    row_h = 54
    header_h = 96
    foot_h = 110  # provenance line + wrapped flag-semantics statement
    plot_x = 230               # where the cTCS scale starts
    plot_w = width - plot_x - pad - 60
    height = header_h + max(1, len(axes)) * row_h + 70 + foot_h

    def x_of(v: float) -> float:
        v = max(0.0, min(1.0, v))
        return plot_x + v * plot_w

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="Segoe UI, Helvetica, Arial, sans-serif">'
    )
    out.append(f'<rect width="{width}" height="{height}" fill="#0f1b2d"/>')
    # header
    out.append(
        f'<text x="{pad}" y="40" fill="#e8eef7" font-size="22" '
        f'font-weight="700">NeuroTCS - Audit Result</text>'
    )
    out.append(
        f'<rect x="{pad}" y="56" rx="6" width="220" height="30" fill="{status_col}"/>'
    )
    out.append(
        f'<text x="{pad + 12}" y="76" fill="#fff" font-size="15" '
        f'font-weight="700">{escape(status)}</text>'
    )
    out.append(
        f'<text x="{pad + 250}" y="76" fill="#9fb3cc" font-size="13">'
        f'impossible {sev.get("impossible", 0)} / implausible '
        f'{sev.get("implausible", 0)} / informational '
        f'{sev.get("informational", 0)}</text>'
    )

    # scale gridlines 0..1
    base_y = header_h
    for t in (0.0, 0.5, 1.0):
        gx = x_of(t)
        out.append(
            f'<line x1="{gx:.1f}" y1="{base_y}" x2="{gx:.1f}" '
            f'y2="{base_y + len(axes) * row_h + 6}" stroke="#22344d" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{gx:.1f}" y="{base_y - 6}" fill="#6c829e" '
            f'font-size="11" text-anchor="middle">{t:.1f}</text>'
        )

    # one row per axis: label, CI error bar, point, value
    for i, ax in enumerate(axes):
        cy = base_y + i * row_h + row_h / 2
        name = escape(str(ax.get("axis", "?")))
        ctcs = ax.get("ctcs")
        lo = ax.get("ctcs_ci_95_low")
        hi = ax.get("ctcs_ci_95_high")
        out.append(
            f'<text x="{pad}" y="{cy - 4:.1f}" fill="#e8eef7" '
            f'font-size="14" font-weight="600">{name}</text>'
        )
        out.append(
            f'<text x="{pad}" y="{cy + 14:.1f}" fill="#7e93ad" font-size="11">'
            f'{ax.get("n_flagged", 0)}/{ax.get("n_transitions", 0)} flagged</text>'
        )
        if ctcs is not None:
            if lo is not None and hi is not None:
                out.append(
                    f'<line x1="{x_of(lo):.1f}" y1="{cy:.1f}" '
                    f'x2="{x_of(hi):.1f}" y2="{cy:.1f}" '
                    f'stroke="#4a90d9" stroke-width="4" stroke-linecap="round"/>'
                )
            out.append(
                f'<circle cx="{x_of(float(ctcs)):.1f}" cy="{cy:.1f}" r="6" '
                f'fill="#e8eef7" stroke="#4a90d9" stroke-width="2"/>'
            )
            ci_txt = (f"  [95% CI {_fmt(lo)}-{_fmt(hi)}]"
                      if lo is not None and hi is not None else "")
            out.append(
                f'<text x="{plot_x + plot_w + 10}" y="{cy + 4:.1f}" '
                f'fill="#e8eef7" font-size="12">cTCS {_fmt(ctcs)}</text>'
            )
            out.append(
                f'<text x="{pad + 120}" y="{cy + 14:.1f}" fill="#7e93ad" '
                f'font-size="10">{escape(ci_txt.strip())}</text>'
            )
        else:
            out.append(
                f'<text x="{plot_x}" y="{cy + 4:.1f}" fill="#7e93ad" '
                f'font-size="12">cTCS n/a</text>'
            )

    # footer / provenance
    fy = base_y + len(axes) * row_h + 40
    out.append(
        f'<text x="{pad}" y="{fy}" fill="#6c829e" font-size="11">'
        f'bundle {escape(str(bid)[:24])}... | framework '
        f'{escape(str(core.get("framework_version", "?")))} | format '
        f'{escape(str(core.get("bundle_format_version", "?")))}</text>'
    )
    # flag-semantics statement (expert review 2026-08): wrap to ~90 chars/line
    from neurotcs.report import FLAG_SEMANTICS_STATEMENT
    words = FLAG_SEMANTICS_STATEMENT.split()
    lines: list[str] = [""]
    for w in words:
        if len(lines[-1]) + len(w) + 1 > 92:
            lines.append(w)
        else:
            lines[-1] = (lines[-1] + " " + w).strip()
    for i, line in enumerate(lines):
        out.append(
            f'<text x="{pad}" y="{fy + 16 + i * 13}" fill="#8fa3bd" '
            f'font-size="10">{escape(line)}</text>'
        )
    out.append("</svg>")
    return "".join(out)

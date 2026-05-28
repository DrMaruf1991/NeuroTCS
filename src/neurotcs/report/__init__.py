"""Presentation renderers for a NeuroTCS signed bundle.

Every renderer here is a PURE VIEW over the signed deterministic core: it reads
the bundle and produces a human/tool-facing artifact (CSV, SVG, ...). Renderers
never recompute audit values and are never part of the hashed core -- the bundle
remains the single source of truth.
"""
from neurotcs.report.csv_report import flags_to_csv  # noqa: F401
from neurotcs.report.svg_report import bundle_to_svg  # noqa: F401

__all__ = ["flags_to_csv", "bundle_to_svg"]

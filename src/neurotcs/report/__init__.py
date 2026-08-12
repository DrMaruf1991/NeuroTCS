"""Presentation renderers for a NeuroTCS fingerprinted bundle.

Every renderer here is a PURE VIEW over the fingerprinted deterministic core: it reads
the bundle and produces a human/tool-facing artifact (CSV, SVG, ...). Renderers
never recompute audit values and are never part of the hashed core -- the bundle
remains the single source of truth.
"""
# Single source of truth for what a flag MEANS, rendered on every
# human-facing surface (terminal summary, PDF, SVG, demo UI). Added per the
# external expert review 2026-08 (companion to ERRATA E-2026-011): severity
# tokens like "impossible" are machine-schema tier names, not clinical
# verdicts, and outputs must say so. Machine formats (bundle JSON, flags
# CSV) keep their stable tokens; this statement is prose for humans.
FLAG_SEMANTICS_STATEMENT = (
    "A flag marks a transition that is inadmissible or improbable under the "
    "cited rule pack. Every flag requires adjudication: it is not, by "
    "itself, a verdict of data error. Flags may reflect true data errors, "
    "real but rare biology (e.g. diagnostic reclassification), or "
    "label-mapping artifacts; flag precision against expert review is "
    "measured per docs/VALIDATION_PROTOCOL.md."
)

from neurotcs.report.csv_report import flags_to_csv  # noqa: E402,F401
from neurotcs.report.pdf_report import bundle_to_pdf  # noqa: E402,F401
from neurotcs.report.svg_report import bundle_to_svg  # noqa: E402,F401

__all__ = [
    "FLAG_SEMANTICS_STATEMENT",
    "flags_to_csv",
    "bundle_to_svg",
    "bundle_to_pdf",
]

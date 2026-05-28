"""Render a bundle's flags as CSV (one row per flag). Pure view; no recompute."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

_COLUMNS = [
    "severity", "layer", "subject_id", "visit",
    "field", "observed_value", "rule_id", "citation", "details",
]


def _core(bundle: dict[str, Any]) -> dict[str, Any]:
    return bundle["neurotcs_bundle"]["deterministic_core"]


def flags_to_csv(bundle: dict[str, Any]) -> str:
    """Return a CSV string with one row per flag across all severities.

    Columns: severity, layer, subject_id, visit, field, observed_value,
    rule_id, citation, details (details serialized as compact JSON). Severities
    are emitted in fixed order (impossible, implausible, informational) so the
    output is deterministic. If there are no flags, returns the header only.
    """
    core = _core(bundle)
    flags = core.get("flags", {})
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(_COLUMNS)
    for severity in ("impossible", "implausible", "informational"):
        for f in flags.get(severity, []):
            details = f.get("details")
            w.writerow([
                severity,
                f.get("layer", ""),
                f.get("subject_id") if f.get("subject_id") is not None else "",
                f.get("visit") if f.get("visit") is not None else "",
                f.get("field") if f.get("field") is not None else "",
                f.get("observed_value") if f.get("observed_value") is not None else "",
                f.get("rule_id") if f.get("rule_id") is not None else "",
                f.get("citation") if f.get("citation") is not None else "",
                json.dumps(details, sort_keys=True, default=str) if details else "",
            ])
    return buf.getvalue()

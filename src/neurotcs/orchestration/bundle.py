"""neurotcs.orchestration.bundle -- the self-verifying result bundle.

This is the signed source-of-truth format a `pip install neurotcs` user gets
when they audit a dataset. PDF/CSV/SVG are derived views rendered FROM it and
are never part of the hash.

== DESIGN INVARIANTS ==

1. STATUS leads, not a score: CLEAN / FLAGS_PRESENT / INCOMPLETE_REFUSED.
   Scores are per staging axis (each with its own pack, SHA, cTCS, audit_id);
   there is no single collapsed cTCS.

2. The bundle_id hashes a DETERMINISTIC CORE only. Timings, wall-clock and
   hostname live in run_metadata, OUTSIDE the hash. Same input -> same id.

3. A partial run (INCOMPLETE_REFUSED) carries NO bundle_id and is therefore
   cryptographically distinguishable from a complete one.

== CANONICALIZATION (declared, not implied) ==

The bundle_id is sha256 over the canonical byte serialization of the
deterministic_core, where canonical bytes are defined as:

  * the core is NUMERICALLY NORMALIZED first (see _normalize): numpy scalars
    are cast to native Python; floats are reduced to <=12 significant digits
    (absorbs cross-platform / cross-numpy last-ULP variance); NaN/Inf -> null;
    dict keys -> str; dates/Decimals/other -> str();
  * then serialized with json.dumps(sort_keys=True, separators=(",",":"),
    ensure_ascii=True, allow_nan=False);
  * then UTF-8 encoded.

Because BOTH the stored core and the hashed core are the normalized object, the
stored values are exactly the hashed values. Two correct implementations on any
platform produce identical bundle_ids from the same audit. This declaration is
the contract; do not change it without bumping BUNDLE_FORMAT_VERSION.

The bundle_format_version and framework_version are INSIDE the deterministic
core, so they are covered by the hash -- a bundle's structure and engine are
bound to its id (no collision across schema/engine versions).
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
from datetime import datetime, timezone
from typing import Any

try:
    import numpy as _np
except Exception:  # noqa: BLE001 - numpy is a hard dep via pandas, but stay safe
    _np = None

from neurotcs import __version__ as _FRAMEWORK_VERSION
from neurotcs.orchestration.orchestrator import OrchestratorResult

# Envelope schema version. Bump when the bundle STRUCTURE or the canonicalization
# rule changes, independently of the framework version.
BUNDLE_FORMAT_VERSION = "1.3.0"

STATUS_CLEAN = "CLEAN"
STATUS_FLAGS_PRESENT = "FLAGS_PRESENT"
STATUS_INCOMPLETE_REFUSED = "INCOMPLETE_REFUSED"

# Float precision used during canonicalization (significant digits).
_FLOAT_SIG_DIGITS = 12

# Pinned canonical flag envelope. Every flag, from any layer, is normalized to
# exactly these top-level keys; layer-specific data is preserved under "details".
# v1.57.0: provenance (rule_id, pack_id, citation_pmid, citation_doi) promoted to
# first-class canonical keys so every flag is traceable to its source rule and
# citation directly from the bundle -- the GxP / 21 CFR Part 11 traceability bar
# -- rather than requiring a reader to dig through the free-form "details" blob.
_CANONICAL_FLAG_KEYS = (
    "tier", "layer", "subject_id", "visit",
    "field", "observed_value", "rule_id", "pack_id",
    "citation", "citation_pmid", "citation_doi",
)
# Source-key aliases each canonical field may be populated from (first hit wins).
_FLAG_ALIASES: dict[str, tuple[str, ...]] = {
    "subject_id": ("subject_id", "subject", "patient_id"),
    "visit": ("visit", "visit_id", "visit_no"),
    "field": ("field", "measurement_name", "measure"),
    "observed_value": ("observed_value", "value", "observed"),
    "rule_id": ("rule_id", "rule", "invariant", "invariant_id",
                "measurement_name"),
    "pack_id": ("pack_id", "rulepack_id", "rangepack_id", "invariantpack_id"),
    "citation": ("citation", "citation_text", "source"),
    "citation_pmid": ("citation_pmid", "pmid"),
    "citation_doi": ("citation_doi", "doi"),
}


class BundleVerificationError(RuntimeError):
    """Raised when a bundle's stored bundle_id does not match its content."""


# --------------------------------------------------------------------------- #
# Canonicalization
# --------------------------------------------------------------------------- #
def _normalize_scalar(v: Any) -> Any:
    if _np is not None and isinstance(v, _np.generic):
        v = v.item()  # numpy scalar -> native python
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        # reduce to fixed significant digits, deterministically, then re-parse
        return float(f"{v:.{_FLOAT_SIG_DIGITS}g}")
    if v is None or isinstance(v, str):
        return v
    return str(v)  # dates, Decimal, anything else -> stable string


def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _normalize(val) for k, val in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(x) for x in obj]
    return _normalize_scalar(obj)


def _canonical(obj: Any) -> str:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


def _compute_bundle_id(deterministic_core: dict[str, Any]) -> str:
    # core is already normalized when stored, so hashing it reproduces the id.
    return hashlib.sha256(_canonical(deterministic_core).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Result -> core projections
# --------------------------------------------------------------------------- #
def _status_for(result: OrchestratorResult) -> str:
    if not result.complete:
        return STATUS_INCOMPLETE_REFUSED
    sev = result.severity_summary
    errors = sev.get("impossible", 0) + sev.get("implausible", 0)
    return STATUS_FLAGS_PRESENT if errors > 0 else STATUS_CLEAN


def _axes_from(result: OrchestratorResult) -> list[dict[str, Any]]:
    axes: list[dict[str, Any]] = []
    for layer in result.layers:
        if not layer.layer.startswith("staging") or not layer.ran:
            continue
        s = layer.summary
        axes.append({
            "axis": layer.layer,
            "pack": s.get("pack"),
            "audit_id": layer.audit_id,
            "ctcs": s.get("ctcs"),
            "ctcs_ci_95_low": s.get("ctcs_ci_95_low"),
            "ctcs_ci_95_high": s.get("ctcs_ci_95_high"),
            "ctcs_ci_method": s.get("ctcs_ci_method"),
            "ctcs_huber": s.get("ctcs_huber"),
            "bootstrap_B": s.get("bootstrap_B"),
            "n_transitions": s.get("n_transitions"),
            "n_flagged": s.get("n_flagged"),
            "vocabulary_coverage": s.get("vocabulary_coverage"),
            "contamination_tokens": s.get("contamination_tokens", []),
        })
    return sorted(axes, key=lambda a: a["axis"])


def _normalize_flag(raw: dict[str, Any], layer: str) -> dict[str, Any]:
    """Project any layer's flag onto the pinned canonical envelope + details."""
    out: dict[str, Any] = {k: None for k in _CANONICAL_FLAG_KEYS}
    out["tier"] = raw.get("tier")
    out["layer"] = layer
    consumed: set[str] = {"tier"}
    for canon, aliases in _FLAG_ALIASES.items():
        for a in aliases:
            if a in raw and raw[a] is not None:
                out[canon] = raw[a]
                consumed.add(a)
                break
    # everything not mapped is preserved (stable via sort_keys at hash time)
    out["details"] = {k: v for k, v in raw.items() if k not in consumed}
    return out


def _flags_by_tier(result: OrchestratorResult) -> dict[str, list[dict[str, Any]]]:
    tiers: dict[str, list[dict[str, Any]]] = {
        "impossible": [], "implausible": [], "informational": [],
    }
    for layer in result.layers:
        for f in layer.flags:
            tier = f.get("tier", "impossible")
            tiers.setdefault(tier, []).append(_normalize_flag(f, layer.layer))
    for tier in tiers:
        tiers[tier] = sorted(tiers[tier], key=_canonical)
    return tiers


def _coverage_from(result: OrchestratorResult) -> dict[str, Any]:
    m = result.manifest
    return {
        "layers_run": sorted(m.layers_run),
        "layers_skipped": dict(sorted(m.layers_skipped.items())),
        "packs_applied": dict(sorted(m.packs_applied.items())),
        "columns_consumed": {k: sorted(v) for k, v in sorted(m.columns_consumed.items())},
        "columns_ignored": {k: sorted(v) for k, v in sorted(m.columns_ignored.items())},
        "sub_audit_ids": dict(sorted(m.sub_audit_ids.items())),
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_bundle(
    result: OrchestratorResult,
    *,
    input_fingerprint: str | None = None,
    input_fingerprint_kind: str = "normalized_data_sha256",
    timings_seconds: dict[str, float] | None = None,
    raw_input_sha256: str | None = None,
    input_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a self-verifying result bundle from an OrchestratorResult.

    input_fingerprint: SHA-256 of the NORMALIZED (post-parse) input -- proves
        "same logical input regardless of file formatting". Hashed into the id.
        Use fingerprint_dataframe() to produce it.
    input_fingerprint_kind: declares what input_fingerprint hashed (documented,
        and itself part of the deterministic core).
    raw_input_sha256: optional SHA-256 of the raw input FILE bytes -- proves
        "same file". Stored in run_metadata, OUTSIDE the hash (formatting-
        sensitive, so not suitable for the determinism guarantee).
    timings_seconds: per-layer wall-clock; run_metadata only, never hashed.
    """
    status = _status_for(result)

    raw_core: dict[str, Any] = {
        # version fields INSIDE the hash: structure+engine are bound to the id
        "bundle_format_version": BUNDLE_FORMAT_VERSION,
        "framework_version": _FRAMEWORK_VERSION,
        "canonicalization": f"json-sorted-utf8;float_sig={_FLOAT_SIG_DIGITS}",
        "status": status,
        "input_fingerprint": input_fingerprint,
        "input_fingerprint_kind": (
            input_fingerprint_kind if input_fingerprint is not None else None
        ),
        "axes": _axes_from(result),
        "severity_counts": {
            "impossible": result.severity_summary.get("impossible", 0),
            "implausible": result.severity_summary.get("implausible", 0),
            "informational": result.severity_summary.get("informational", 0),
        },
        "flags": _flags_by_tier(result),
        "coverage": _coverage_from(result),
        "refusal_reason": result.refusal_reason,
    }

    if status == STATUS_INCOMPLETE_REFUSED:
        raw_core["refusal_detail"] = {
            "reason": result.refusal_reason,
            "layers_run": sorted(result.manifest.layers_run),
            "remediation": (
                "Every applicable layer must either run or carry a recorded "
                "skip reason. Supply the missing layer's required data, or "
                "record an explicit reason for skipping it, then re-run."
            ),
        }

    # Normalize ONCE; store and hash the same normalized object.
    deterministic_core = _normalize(raw_core)
    bundle_id = (
        "" if status == STATUS_INCOMPLETE_REFUSED
        else _compute_bundle_id(deterministic_core)
    )

    run_metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "timings_seconds": timings_seconds or {},
        "raw_input_sha256": raw_input_sha256,
        # v1.39.0: input-handling warnings (e.g. derived visit_date) recorded in
        # the persistent bundle. In run_metadata, so NOT hashed -- the determinism
        # guarantee (bundle_id) is unaffected, but the note is part of the record.
        "input_warnings": list(input_warnings or []),
    }

    return {
        "neurotcs_bundle": {
            "format_version": BUNDLE_FORMAT_VERSION,  # envelope dispatch copy
            "bundle_id": bundle_id,
            "deterministic_core": deterministic_core,
            "run_metadata": run_metadata,
        }
    }


def verify_bundle(bundle: dict[str, Any]) -> bool:
    """Recompute the bundle_id over the deterministic core and confirm it matches.

    Raises BundleVerificationError on tampering, corruption, unknown format, or
    an envelope/core version disagreement.
    """
    try:
        nb = bundle["neurotcs_bundle"]
        fmt = nb["format_version"]
        stored_id = nb["bundle_id"]
        core = nb["deterministic_core"]
    except (KeyError, TypeError) as e:
        raise BundleVerificationError(
            f"not a recognizable neurotcs bundle: missing {e}"
        ) from e

    if fmt != BUNDLE_FORMAT_VERSION:
        raise BundleVerificationError(
            f"bundle format_version {fmt} != verifier {BUNDLE_FORMAT_VERSION}; "
            f"use a matching neurotcs version to verify."
        )
    # envelope copy must agree with the hashed copy inside the core
    if core.get("bundle_format_version") != fmt:
        raise BundleVerificationError(
            "envelope format_version disagrees with deterministic_core "
            "(bundle was altered)."
        )

    if core.get("status") == STATUS_INCOMPLETE_REFUSED:
        if stored_id != "":
            raise BundleVerificationError(
                "INCOMPLETE_REFUSED bundle must not carry a bundle_id."
            )
        return True

    recomputed = _compute_bundle_id(core)
    if recomputed != stored_id:
        raise BundleVerificationError(
            f"bundle_id mismatch: stored {str(stored_id)[:16]}... != "
            f"recomputed {recomputed[:16]}.... The deterministic core was "
            f"altered after signing (tampering or corruption)."
        )
    return True


def fingerprint_dataframe(df: Any) -> str:
    """SHA-256 of NORMALIZED DataFrame content (post-parse logical input).

    Proves "same logical input regardless of file formatting" -- trivial
    reformatting (column order aside, whitespace, dtypes) does not change it,
    because values pass through the same numeric normalization as the bundle.
    For a raw-file-bytes fingerprint instead, hash the file directly and pass it
    as raw_input_sha256 to build_bundle.
    """
    try:
        cols = list(map(str, df.columns))
        values = _normalize(df.values.tolist())
        payload = _canonical({"columns": cols, "shape": list(df.shape), "values": values})
    except Exception:  # noqa: BLE001 - non-DataFrame fallback
        payload = _canonical({"repr": repr(df)})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint_file(path: str) -> str:
    """SHA-256 of raw file bytes (proves 'same file'). For raw_input_sha256."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Human-readable rendered view (NOT part of the signed bundle)
# --------------------------------------------------------------------------- #
def render_report(bundle: dict[str, Any], *, use_symbols: bool = True) -> str:
    """Render a bundle as a human-readable text report.

    Presentation only: symbols/emoji and formatting live HERE, never in the
    signed JSON (which stays ASCII/emoji-free for cross-platform determinism).
    """
    nb = bundle["neurotcs_bundle"]
    core = nb["deterministic_core"]
    status = core["status"]

    if use_symbols:
        smap = {STATUS_CLEAN: "\u2705", STATUS_FLAGS_PRESENT: "\u26a0\ufe0f",
                STATUS_INCOMPLETE_REFUSED: "\u26d4"}
        tmap = {"impossible": "\U0001f534", "implausible": "\U0001f7e0",
                "informational": "\U0001f535"}
        sec = {"verdict": "\U0001f4cb", "flags": "\U0001f6a9",
               "coverage": "\U0001f5c2\ufe0f", "prov": "\U0001f50f"}
    else:
        smap = {STATUS_CLEAN: "[OK]", STATUS_FLAGS_PRESENT: "[!]",
                STATUS_INCOMPLETE_REFUSED: "[REFUSED]"}
        tmap = {"impossible": "(I)", "implausible": "(P)", "informational": "(i)"}
        sec = {"verdict": "", "flags": "", "coverage": "", "prov": ""}

    bar = "\u2550" * 64
    out: list[str] = [bar, "  NeuroTCS \u2014 Audit Result", bar]

    # 1. Verdict
    out.append(f"\n{sec['verdict']} Verdict")
    out.append(f"   {smap.get(status, '')} Status: {status}")
    for ax in core.get("axes", []):
        lo, hi = ax.get("ctcs_ci_95_low"), ax.get("ctcs_ci_95_high")
        ci = f" [95% CI {lo}\u2013{hi}]" if lo is not None and hi is not None else ""
        out.append(
            f"      \u2022 {ax['axis']}: cTCS {ax['ctcs']}{ci}  "
            f"(pack {ax['pack']}, audit_id {str(ax['audit_id'])[:12]}\u2026, "
            f"{ax['n_flagged']}/{ax['n_transitions']} flagged)"
        )
    bid = nb["bundle_id"]
    ellipsis = "\u2026"
    bid_display = (bid[:24] + ellipsis) if bid else "(none \u2014 refused)"
    out.append(f"   Bundle id: {bid_display}")

    # 2. Flag summary
    sc = core["severity_counts"]
    out.append(f"\n{sec['flags']} Flags By Severity")
    out.append(f"   {tmap['impossible']} Impossible (data-integrity):     {sc['impossible']}")
    out.append(f"   {tmap['implausible']} Implausible (out of range):      {sc['implausible']}")
    out.append(f"   {tmap['informational']} Informational (not errors):      {sc['informational']}")

    # 3. Coverage
    cov = core["coverage"]
    out.append(f"\n{sec['coverage']} Coverage Manifest")
    out.append(f"   Layers run:    {', '.join(cov['layers_run']) or '(none)'}")
    skipped = cov["layers_skipped"]
    out.append(f"   Skipped:       {skipped if skipped else 'none'}")
    out.append(f"   Packs applied: {', '.join(cov['packs_applied']) or '(none)'}")

    # 4. Provenance
    rm = nb["run_metadata"]
    out.append(f"\n{sec['prov']} Provenance")
    out.append(f"   Framework:   neurotcs {core['framework_version']}")
    out.append(f"   Format:      bundle {core['bundle_format_version']}")
    out.append(f"   Generated:   {rm['generated_at_utc']}")
    if status == STATUS_INCOMPLETE_REFUSED and "refusal_detail" in core:
        out.append(f"\n   {smap[status]} Refusal: {core['refusal_detail']['reason']}")
        out.append(f"   Fix: {core['refusal_detail']['remediation']}")

    out.append(bar)
    return "\n".join(out)

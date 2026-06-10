#!/usr/bin/env python3
"""Generate a CycloneDX SBOM for NeuroTCS, scoped to its OWN locked dependency
closure (not the whole ambient environment).

A Software Bill of Materials lists every component shipped/relied upon, with
versions and licenses, so a downstream consumer (or a regulator) can audit the
supply chain and cross-check against CVE feeds. We build it from the pinned
``requirements.lock`` so the SBOM matches exactly what a reproducible install
pulls -- a freeze of a shared dev machine would over-report (NeuroTCS does not
depend on FastAPI/Telegram/etc.).

Usage:
    python scripts/ci/generate_sbom.py [--lock requirements.lock] [--out sbom.json]

Exit codes: 0 on success, non-zero on failure. Deterministic given the lock.

This script has no network dependency for SBOM *construction*; pairing it with a
networked ``pip-audit`` step (see scripts/ci) closes the CVE-scan gap.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_PIN_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([^\s#]+)")


def _parse_lock(lock_path: Path) -> list[tuple[str, str]]:
    """Return [(name, version)] for every '==' pin in the lockfile, ignoring
    comments and blank lines. Deterministic (sorted by name)."""
    pins: list[tuple[str, str]] = []
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _PIN_RE.match(line)
        if m:
            pins.append((m.group(1), m.group(2)))
    # de-dup (last wins) then sort for determinism
    dedup: dict[str, str] = {}
    for name, ver in pins:
        dedup[name.lower()] = ver
    return sorted(dedup.items())


def _purl(name: str, version: str) -> str:
    return f"pkg:pypi/{name}@{version}"


def build_sbom(pins: list[tuple[str, str]], project_version: str) -> dict:
    """Build a minimal-but-valid CycloneDX 1.6 SBOM document."""
    components = [
        {
            "type": "library",
            "name": name,
            "version": version,
            "purl": _purl(name, version),
            "bom-ref": _purl(name, version),
        }
        for name, version in pins
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "neurotcs",
                "version": project_version,
                "purl": _purl("neurotcs", project_version),
                "bom-ref": _purl("neurotcs", project_version),
            },
            "properties": [
                {"name": "neurotcs:sbom_scope",
                 "value": "locked dependency closure (requirements.lock)"},
            ],
        },
        "components": components,
    }


def _read_project_version() -> str:
    try:
        import neurotcs
        return str(neurotcs.__version__)
    except Exception:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a NeuroTCS CycloneDX SBOM")
    ap.add_argument("--lock", default="requirements.lock",
                    help="path to the lockfile (default: requirements.lock)")
    ap.add_argument("--out", default="neurotcs_sbom.json",
                    help="output path (default: neurotcs_sbom.json)")
    args = ap.parse_args(argv)

    lock_path = Path(args.lock)
    if not lock_path.is_file():
        print(f"error: lockfile not found: {lock_path}", file=sys.stderr)
        return 2
    pins = _parse_lock(lock_path)
    if not pins:
        print(f"error: no '==' pins found in {lock_path}", file=sys.stderr)
        return 3
    sbom = build_sbom(pins, _read_project_version())
    Path(args.out).write_text(json.dumps(sbom, indent=2, sort_keys=True),
                              encoding="utf-8")
    print(f"wrote SBOM: {args.out}  ({len(pins)} components, "
          f"CycloneDX {sbom['specVersion']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

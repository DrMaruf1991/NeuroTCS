"""
neurotcs.clinical_ranges.loader — range-pack discovery + load.

Mirrors the architecture of neurotcs.rulepack.loader so that downstream
consumers (and reviewers) see one consistent pattern across all audit
layers.

Range packs ship under src/neurotcs/clinical_ranges/ranges/ in the same
on-disk hierarchy that rulepack uses: domain/<name>.yaml. They are
discovered, parsed through Pydantic-strict, and returned as
LoadedRangePack objects that carry the parsed pack plus its canonical
SHA-256.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from neurotcs.clinical_ranges.schema import RangePack, RangePackStatus

# ============================================================
# On-disk layout
# ============================================================

_RANGES_ROOT = Path(__file__).resolve().parent / "ranges"


@dataclass(frozen=True)
class LoadedRangePack:
    """A loaded range pack plus its derived hash and status.

    Attributes:
        name: The 'domain/name' identifier used by load_rangepack().
        rangepack: The parsed Pydantic RangePack model.
        canonical_sha256: SHA-256 of the canonical-JSON form (used as the
            rangepack_sha component in flag_id).
        status: Lifecycle status (production / skeleton / planned).
    """
    name: str
    rangepack: RangePack
    canonical_sha256: str
    status: RangePackStatus

    def assert_usable_for_audit(self) -> None:
        """Defer to the RangePack's own gate."""
        self.rangepack.assert_usable_for_audit()


# ============================================================
# Public API
# ============================================================

def load_rangepack(name: str) -> LoadedRangePack:
    """Load a range pack by its 'domain/name' identifier.

    Examples:
        load_rangepack("vital_signs/standard")
        load_rangepack("csf_biomarkers/aa_2024")

    Raises:
        FileNotFoundError: if no YAML matches that path.
        pydantic.ValidationError: if the YAML doesn't satisfy the schema
            (missing citation, missing transcribed_by, etc.).
    """
    yaml_path = _RANGES_ROOT / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Range pack not found at {yaml_path}. "
            f"Use list_rangepacks() to see available packs."
        )

    with open(yaml_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    pack = RangePack.model_validate(raw)
    sha = pack.canonical_sha256()
    return LoadedRangePack(
        name=name,
        rangepack=pack,
        canonical_sha256=sha,
        status=pack.status,
    )


def list_rangepacks() -> list[dict[str, Any]]:
    """Enumerate every range pack on disk with its load status.

    Returns a list of dicts with keys: name, status, schema_version,
    pack_version, n_measurements, sha256 (truncated to 16 chars).
    A pack that fails to parse is included with status='INVALID' and
    an error message; the loader does NOT raise on listing.
    """
    out: list[dict[str, Any]] = []
    if not _RANGES_ROOT.exists():
        return out
    for yaml_path in sorted(_RANGES_ROOT.glob("**/*.yaml")):
        name = str(yaml_path.relative_to(_RANGES_ROOT).with_suffix(""))
        # Normalize path separators (cross-platform: backslash on Windows)
        name = name.replace("\\", "/")
        try:
            lp = load_rangepack(name)
            out.append({
                "name": name,
                "status": lp.status.value,
                "schema_version": lp.rangepack.schema_version,
                "pack_version": lp.rangepack.pack_version,
                "n_measurements": len(lp.rangepack.measurements),
                "sha256": lp.canonical_sha256[:16],
            })
        except Exception as e:
            out.append({
                "name": name,
                "status": "INVALID",
                "error": str(e)[:200],
            })
    return out

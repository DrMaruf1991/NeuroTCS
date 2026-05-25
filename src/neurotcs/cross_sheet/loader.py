"""
neurotcs.cross_sheet.loader -- Layer 3 invariant pack discovery + load.

Architecturally identical to neurotcs.clinical_ranges.loader. Reuses
neurotcs.clinical_ranges.yaml_hash for cross-platform-stable SHA-256
hashing of normalized YAML bytes (the v1.10.1 mechanism).

Invariant packs ship under
  src/neurotcs/cross_sheet/invariants/<domain>/<name>.yaml
in the same on-disk hierarchy as rule packs and range packs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from neurotcs.clinical_ranges.yaml_hash import yaml_sha256_of_path
from neurotcs.cross_sheet.schema import InvariantPack, InvariantPackStatus

# ============================================================
# On-disk layout
# ============================================================

_INVARIANTS_ROOT = Path(__file__).resolve().parent / "invariants"


@dataclass(frozen=True)
class LoadedInvariantPack:
    """A loaded invariant pack plus its derived hashes and status.

    Mirrors LoadedRangePack from Layer 2.

    Attributes:
        name: 'domain/name' identifier used by load_invariantpack().
        invariantpack: The parsed Pydantic InvariantPack model.
        canonical_sha256: SHA-256 of canonical-JSON form (legacy hash,
            may vary across Python patch versions).
        yaml_sha256: SHA-256 of normalized YAML file bytes
            (cross-platform-stable, the v1.10.1 mechanism). Will be
            used in Layer 3 flag_id derivation when audit_cross_sheet()
            ships in rc1 session #2+.
        status: Lifecycle status (production / research_preview /
            skeleton / planned / deprecated).
    """
    name: str
    invariantpack: InvariantPack
    canonical_sha256: str
    yaml_sha256: str
    status: InvariantPackStatus

    def assert_usable_for_audit(self) -> None:
        """Defer to the InvariantPack's own gate."""
        self.invariantpack.assert_usable_for_audit()


# ============================================================
# Public API
# ============================================================

def load_invariantpack(name: str) -> LoadedInvariantPack:
    """Load an invariant pack by its 'domain/name' identifier.

    Examples:
        load_invariantpack("cross_sheet/tool_declaration_consistency")

    Raises:
        FileNotFoundError: if no YAML matches that path.
        pydantic.ValidationError: if the YAML doesn't satisfy the schema.
    """
    yaml_path = _INVARIANTS_ROOT / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Invariant pack not found at {yaml_path}. "
            f"Use list_invariantpacks() to see available packs."
        )

    with open(yaml_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    pack = InvariantPack.model_validate(raw)
    sha = pack.canonical_sha256()
    yaml_sha = yaml_sha256_of_path(yaml_path)
    return LoadedInvariantPack(
        name=name,
        invariantpack=pack,
        canonical_sha256=sha,
        yaml_sha256=yaml_sha,
        status=pack.status,
    )


def list_invariantpacks() -> list[dict[str, Any]]:
    """Enumerate every invariant pack on disk with its load status.

    Returns a list of dicts with keys: name, status, schema_version,
    pack_version, n_invariants, sha256 (truncated 16 chars from
    canonical_sha256), yaml_sha256 (truncated 16 chars).
    A pack that fails to parse is included with status='INVALID' and
    an error message; the loader does NOT raise on listing.
    """
    out: list[dict[str, Any]] = []
    if not _INVARIANTS_ROOT.exists():
        return out
    for yaml_path in sorted(_INVARIANTS_ROOT.glob("**/*.yaml")):
        name = str(yaml_path.relative_to(_INVARIANTS_ROOT).with_suffix(""))
        # Cross-platform path-separator normalization
        name = name.replace("\\", "/")
        try:
            lp = load_invariantpack(name)
            out.append({
                "name": name,
                "status": lp.status.value,
                "schema_version": lp.invariantpack.schema_version,
                "pack_version": lp.invariantpack.pack_version,
                "n_invariants": len(lp.invariantpack.invariants),
                "sha256": lp.canonical_sha256[:16],
                "yaml_sha256": lp.yaml_sha256[:16],
            })
        except Exception as e:
            out.append({
                "name": name,
                "status": "INVALID",
                "error": str(e)[:200],
            })
    return out

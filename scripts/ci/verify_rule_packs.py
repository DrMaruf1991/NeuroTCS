#!/usr/bin/env python3
"""
CI helper: verify the AD rule-pack registry is internally consistent.

Design note (v1.23.0, ERRATA E-2026-010 follow-up):
This check deliberately contains NO hard-coded pack count. A magic number
(`!= 3`, then `!= 4`) is a maintenance trap: every new pack silently breaks
CI until someone hunts down and edits the literal. Worse, a count check is
weak -- it cannot tell a *correct* set of N packs from a *wrong* set of N.

Instead this asserts a strictly stronger, self-updating invariant: the rule
pack REGISTRY (what `list_rulepacks()` exposes) must be exactly consistent
with the FILESYSTEM (the `.yaml` files under rules/), and every discoverable
pack must load cleanly, sit in the declared `ad/` scope, and be production.
Add or remove a pack and this check tracks reality automatically -- there is
no number to update, ever.

Asserts:
  1. Every `.yaml` under rules/ loads cleanly via the public load_rulepack().
  2. The registry set == the filesystem set (no drift in either direction).
  3. No pack is INVALID status.
  4. Every pack is in the declared `ad/` namespace (scope honesty, SCOPE.md).
  5. Every pack is usable for audit (assert_usable_for_audit does not raise).

Exits 0 on success, non-zero with a clear message on the first failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

from neurotcs.rulepack.loader import (
    DEFAULT_RULES_DIR,
    RulePackLoadError,
    list_rulepacks,
    load_rulepack,
)

# The declared scope namespace (see docs/SCOPE.md). Packs live under rules/<ns>/.
DECLARED_NAMESPACE = "ad"


def _filesystem_pack_names(rules_dir: Path) -> set[str]:
    """Every pack discoverable on disk, as 'disease/framework' names."""
    names: set[str] = set()
    for yaml_path in sorted(rules_dir.rglob("*.yaml")):
        rel = yaml_path.relative_to(rules_dir)
        names.add(str(rel.with_suffix("")).replace("\\", "/"))
    return names


def main() -> int:
    rules_dir = DEFAULT_RULES_DIR
    fs_names = _filesystem_pack_names(rules_dir)

    if not fs_names:
        print(
            f"FAIL: no rule-pack .yaml files found under {rules_dir}",
            file=sys.stderr,
        )
        return 1

    # 1. Every file on disk must load cleanly via the PUBLIC entry point.
    for name in sorted(fs_names):
        try:
            load_rulepack(name)
        except RulePackLoadError as e:
            print(
                f"FAIL: rule pack '{name}' does not load cleanly: "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return 1
        except Exception as e:  # noqa: BLE001 - CI must surface ANY load failure
            print(
                f"FAIL: rule pack '{name}' raised on load: "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return 1

    # 2. Registry must match the filesystem exactly (no drift either way).
    packs = list_rulepacks()
    registry_names = {p["name"] for p in packs}
    missing_from_registry = fs_names - registry_names
    missing_from_disk = registry_names - fs_names
    if missing_from_registry or missing_from_disk:
        print("FAIL: rule-pack registry/filesystem drift:", file=sys.stderr)
        if missing_from_registry:
            print(
                f"   on disk but not in registry: {sorted(missing_from_registry)}",
                file=sys.stderr,
            )
        if missing_from_disk:
            print(
                f"   in registry but no file: {sorted(missing_from_disk)}",
                file=sys.stderr,
            )
        return 1

    # 3. No INVALID packs.
    invalid = [p["name"] for p in packs if p.get("status") == "INVALID"]
    if invalid:
        print(f"FAIL: invalid packs detected: {invalid}", file=sys.stderr)
        return 1

    # 4. Scope honesty: every pack in the declared namespace (see docs/SCOPE.md).
    out_of_scope = [
        p["name"] for p in packs
        if not p["name"].startswith(f"{DECLARED_NAMESPACE}/")
    ]
    if out_of_scope:
        print(
            f"FAIL: packs outside the declared '{DECLARED_NAMESPACE}/' scope "
            f"(see docs/SCOPE.md): {out_of_scope}",
            file=sys.stderr,
        )
        return 1

    # 5. Every pack must be usable for audit (no skeletons).
    for name in sorted(fs_names):
        lp = load_rulepack(name)
        try:
            lp.assert_usable_for_audit()
        except Exception as e:  # noqa: BLE001 - surface ANY usability failure
            print(
                f"FAIL: rule pack '{name}' is not usable for audit: "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return 1

    print(
        f"OK: rule-pack registry is consistent with the filesystem "
        f"({len(fs_names)} packs, all production, all in '{DECLARED_NAMESPACE}/' scope)"
    )
    for p in sorted(packs, key=lambda x: x["name"]):
        print(f"   - {p['name']} (status: {p['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

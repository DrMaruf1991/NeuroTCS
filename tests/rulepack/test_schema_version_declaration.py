"""
Enforce the rule-pack schema-version declaration policy.

Policy (documented in src/neurotcs/rulepack/schema.py docstring):
    Each rule pack MUST declare the MINIMUM schema version whose features
    it actually uses, not the latest schema version available.

This module checks every shipped rule pack and asserts that the declared
`schema_version` is consistent with the features it uses:

  - 1.2.0 features (gates the pack to >= 1.2.0):
    * `required_conditions` on any transition
    * `conditions_evaluated_at` on any transition
  - 1.3.0 features (gates the pack to >= 1.3.0):
    * `attribution_type: "clinical_inference"` on any transition
    * `inference_rationale` set on any transition
  - Otherwise: 1.1.0 is sufficient.

A pack that DECLARES 1.2.0 but uses no 1.2.0 features over-declares.
A pack that DECLARES 1.1.0 but uses 1.2.0 features under-declares
(which is caught by Pydantic loading, but we test here for clarity too).

This test discovers all *.yaml under src/neurotcs/rulepack/rules/
automatically, so any newly added pack is checked without code change.
"""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest


# Source-of-truth root, found relative to this test file.
_RULES_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src" / "neurotcs" / "rulepack" / "rules"
)


def _all_rule_packs() -> list[Path]:
    """Discover every shipped rule pack YAML."""
    return sorted(_RULES_ROOT.rglob("*.yaml"))


def _all_transitions(doc: dict) -> list[dict]:
    """Return every transition entry across all three transition lists.

    Rule pack YAMLs use three top-level keys for transitions, not a flat
    `transitions` list:
      - admissible_transitions: clinically-allowed state changes
      - inadmissible_transitions: explicitly-forbidden changes
      - transition_priors: prior probabilities and base rates
    Any of these may carry schema-version-gated fields.
    """
    out: list[dict] = []
    for key in ("admissible_transitions", "inadmissible_transitions",
                "transition_priors"):
        items = doc.get(key) or []
        for entry in items:
            if isinstance(entry, dict):
                out.append(entry)
    return out


def _uses_1_3_0_feature(doc: dict) -> bool:
    """True if any transition uses a 1.3.0-only field."""
    for t in _all_transitions(doc):
        if t.get("attribution_type") == "clinical_inference":
            return True
        if t.get("inference_rationale") not in (None, ""):
            return True
    return False


def _uses_1_2_0_feature(doc: dict) -> bool:
    """True if any transition uses a 1.2.0-only field."""
    for t in _all_transitions(doc):
        if t.get("required_conditions"):
            return True
        # `conditions_evaluated_at` only becomes meaningful if
        # required_conditions is set, but the schema allows setting it.
        if t.get("conditions_evaluated_at") not in (None, ""):
            return True
    return False


def _minimum_required_schema(doc: dict) -> str:
    """Compute the minimum schema version this pack needs."""
    if _uses_1_3_0_feature(doc):
        return "1.3.0"
    if _uses_1_2_0_feature(doc):
        return "1.2.0"
    return "1.1.0"


@pytest.mark.parametrize("pack_path", _all_rule_packs(),
                         ids=lambda p: str(p.relative_to(_RULES_ROOT)))
def test_rulepack_declared_schema_version_matches_minimum_required(
    pack_path: Path,
):
    """For each shipped rule pack, declared schema_version == minimum required.

    This is the canonical enforcement of the schema-version declaration
    policy. Under-declaring would fail to load (Pydantic feature-gating);
    over-declaring would inflate the version without justification.
    Both directions are caught here.
    """
    doc = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    declared = doc.get("schema_version")
    required = _minimum_required_schema(doc)
    assert declared == required, (
        f"\n  Pack:      {pack_path.relative_to(_RULES_ROOT)}\n"
        f"  Declared:  schema_version = '{declared}'\n"
        f"  Required:  '{required}' (computed from features used)\n"
        f"  Fix:       set schema_version to '{required}' OR remove the\n"
        f"             feature that elevates the requirement."
    )


def test_at_least_one_rulepack_exists():
    """Sanity guard: the discovery glob must find at least one pack.

    Catches the case where the rules directory was relocated or accidentally
    excluded from packaging — without this test, an empty parametrize
    silently produces zero assertions and the suite would falsely pass.
    """
    packs = _all_rule_packs()
    assert len(packs) > 0, (
        f"Expected at least one rule pack under {_RULES_ROOT}; found none. "
        f"The rule-pack discovery glob is broken or the directory was moved."
    )

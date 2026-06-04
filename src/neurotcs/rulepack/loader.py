"""
NeuroTCS Rule Pack Loader v1.1.0.

Loads YAML rule packs, validates against schema v1.1 (fail-closed), computes
canonical SHA-256 hash, exposes registry API.

Every loaded RulePack carries:
  - .sha256          stable hash of canonical content (for audit reproducibility)
  - .source_path     YAML source path
  - .loaded_at_utc   load timestamp (for audit logs)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from neurotcs.rulepack.schema import RulePack, RulePackStatus


class RulePackLoadError(Exception):
    """Raised when a rule pack fails to load or validate (fail-closed)."""
    pass


@dataclass(frozen=True)
class LoadedRulePack:
    """A validated rule pack with provenance."""
    rulepack: RulePack
    sha256: str
    source_path: str
    loaded_at_utc: str

    @property
    def rulepack_id(self) -> str:
        return self.rulepack.rulepack_id

    @property
    def status(self) -> RulePackStatus:
        return self.rulepack.status

    @property
    def is_production(self) -> bool:
        return self.status == RulePackStatus.PRODUCTION

    def assert_usable_for_audit(self) -> None:
        """Raise RulePackLoadError if this pack cannot be used for audit."""
        if not self.is_production:
            raise RulePackLoadError(
                f"RulePack '{self.rulepack_id}' is status={self.status.value}; "
                f"only PRODUCTION rule packs can be used for audit."
            )


# Fields the scoring engine reads to compute the audit result. Derived
# empirically (v1.20.0 field-access trace; see
# docs/design/V1_20_0_audit_id_serialization.md). ONLY these enter the
# canonical SHA -> audit_id, so provenance/metadata changes (endorsing_bodies,
# source_author_affiliations, effective_date, schema_version, ruleset_version,
# rulepack_id, reviewers,
# anchor_citation, framework_name, disease_domain, clinical_source_authority,
# transcribed_by, status, notes, override_allowed_default) NEVER drift the
# scientific fingerprint. Per-transition override_allowed is nested inside the
# transition lists and is therefore already covered. See ERRATA E-2026-006.
_SCIENTIFIC_FIELDS = (
    "state_space",
    "admissible_transitions",
    "inadmissible_transitions",
    "transition_priors",
)


def _canonical_serialize(rp: RulePack) -> bytes:
    """Canonical JSON over SCIENTIFIC content only -- the audit_id input.

    Hashes exactly the rule-pack fields the scoring engine consumes. Metadata
    is intentionally excluded so that adding endorsements, refreshing dates, or
    bumping versions can never drift a cohort audit_id. Two-directional proof:
    tests/rulepack/test_canonical_serialization_partition.py.
    """
    dump = rp.model_dump(mode="json")
    scientific = {k: dump[k] for k in _SCIENTIFIC_FIELDS if k in dump}
    return json.dumps(
        scientific,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _compute_sha256(rp: RulePack) -> str:
    return hashlib.sha256(_canonical_serialize(rp)).hexdigest()


def load_rulepack_from_path(path: str | Path) -> LoadedRulePack:
    """Load a rule pack from a YAML file path. Fails closed on any error."""
    p = Path(path).resolve()
    if not p.exists():
        raise RulePackLoadError(f"Rule pack file not found: {p}")

    try:
        with open(p, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise RulePackLoadError(f"Invalid YAML in {p}: {e}") from e

    if raw is None:
        raise RulePackLoadError(f"Empty rule pack file: {p}")

    try:
        rp = RulePack(**raw)
    except ValidationError as e:
        raise RulePackLoadError(
            f"Rule pack {p.name} failed validation:\n{e}"
        ) from e

    sha = _compute_sha256(rp)
    return LoadedRulePack(
        rulepack=rp,
        sha256=sha,
        source_path=str(p),
        loaded_at_utc=datetime.now(timezone.utc).isoformat(),
    )


DEFAULT_RULES_DIR = Path(__file__).parent / "rules"


def load_rulepack(name: str,
                   rules_dir: Path | None = None) -> LoadedRulePack:
    """Load a rule pack by registry name 'disease/framework'."""
    rd = rules_dir or DEFAULT_RULES_DIR
    if "/" not in name:
        raise RulePackLoadError(
            f"Rule pack name must be 'disease/framework' format, got '{name}'"
        )
    disease, framework = name.split("/", 1)
    path = rd / disease / f"{framework}.yaml"
    return load_rulepack_from_path(path)


def list_rulepacks(rules_dir: Path | None = None) -> list[dict]:
    """List all registered rule packs with summary info."""
    rd = rules_dir or DEFAULT_RULES_DIR
    out: list[dict] = []
    for yaml_path in sorted(rd.rglob("*.yaml")):
        rel = yaml_path.relative_to(rd)
        name = str(rel.with_suffix("")).replace("\\", "/")
        try:
            loaded = load_rulepack_from_path(yaml_path)
            out.append({
                "name": name,
                "status": loaded.status.value,
                "framework": loaded.rulepack.framework_name,
                "disease_domain": loaded.rulepack.disease_domain.value,
                "ruleset_version": loaded.rulepack.ruleset_version,
                "effective_date": loaded.rulepack.effective_date.isoformat(),
                "sha256": loaded.sha256[:16],
                "transitions_count": len(loaded.rulepack.admissible_transitions),
                "transcribed_by": loaded.rulepack.transcribed_by,
                "clinical_source_authority": loaded.rulepack.clinical_source_authority[:100] + "...",
                "anchor_citation_pmid": loaded.rulepack.anchor_citation.citation_pmid,
                "anchor_citation_doi": loaded.rulepack.anchor_citation.citation_doi,
            })
        except RulePackLoadError as e:
            out.append({"name": name, "status": "INVALID", "error": str(e)})
    return out

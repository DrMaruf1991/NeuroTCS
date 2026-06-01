"""v1.59.0 -- subject-label synonym ontology (USIL increment 1).

Tests the citation-anchored label normalizer that maps raw clinical-stage labels
("cognitively normal", "early MCI", "Alzheimer's dementia", ...) onto the
canonical CN/SMC/EMCI/LMCI/MCI/AD vocabulary the staging packs consume.

Safety guarantees under test:
  * synonyms only -- maps strings for the SAME label; never collapses distinct
    categories (no SMC->CN, no EMCI->MCI),
  * never guess -- unrecognized tokens (incl. bare "dementia") pass through,
  * ambiguity-safe -- an inconsistent ontology fails closed at load,
  * citation-anchored -- every group carries a source,
  * canonical targets are exactly the staging-pack state names.
"""
from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest

from neurotcs.orchestration.label_normalization import (
    LabelOntologyError,
    load_label_ontology,
    normalize_labels,
)
from neurotcs.rulepack.loader import load_rulepack


def test_ontology_loads_and_is_collision_free():
    ont = load_label_ontology()
    assert ont.ontology_id
    assert ont.yaml_sha256 and len(ont.yaml_sha256) == 64
    # canonicals are exactly the clinical staging vocabulary
    assert set(ont.canonicals) == {"CN", "SMC", "EMCI", "LMCI", "MCI", "AD"}


def test_canonical_targets_match_staging_pack_states():
    """Every canonical target must be a real state in a staging pack -- the
    normalizer must never produce a label the packs do not recognize."""
    ont = load_label_ontology()
    pack_states = {s.name for s in
                   load_rulepack("ad/adni_clinical_stage").rulepack.state_space}
    assert set(ont.canonicals) <= pack_states


def test_real_world_variants_normalize_correctly():
    ont = load_label_ontology()
    raw = ["cognitively normal", "CU", "NC", "subjective memory complaint",
           "SCD", "early MCI", "late MCI", "aMCI", "Alzheimer's dementia",
           "probable AD"]
    r = normalize_labels(raw, ont)
    assert r.normalized == ["CN", "CN", "CN", "SMC", "SMC", "EMCI", "LMCI",
                            "MCI", "AD", "AD"]


def test_unrecognized_tokens_pass_through_unchanged():
    """Fail-honest: never guess. Unknown tokens are returned as-is and reported
    as unmatched (so they still surface as contamination downstream)."""
    ont = load_label_ontology()
    r = normalize_labels(["cognitively normal", "some_unknown_state", "dementia"], ont)
    assert r.normalized == ["CN", "some_unknown_state", "dementia"]
    assert "some_unknown_state" in r.unmatched
    # bare "dementia" is deliberately NOT an AD synonym (could be non-AD)
    assert "dementia" in r.unmatched


def test_does_not_collapse_distinct_categories():
    """SMC must NOT become CN, and EMCI/LMCI must NOT become MCI -- those are
    diagnostic reinterpretations, not synonyms."""
    ont = load_label_ontology()
    r = normalize_labels(["SMC", "EMCI", "LMCI", "subjective cognitive decline",
                          "early MCI", "late MCI"], ont)
    assert r.normalized == ["SMC", "EMCI", "LMCI", "SMC", "EMCI", "LMCI"]


def test_canonical_labels_are_idempotent():
    ont = load_label_ontology()
    canon = ["CN", "SMC", "EMCI", "LMCI", "MCI", "AD"]
    r = normalize_labels(canon, ont)
    assert r.normalized == canon
    assert r.mapping == {}  # nothing changed -> nothing reported


def test_every_group_is_citation_anchored():
    ont = load_label_ontology()
    for canonical in ont.canonicals:
        cit = ont.citation_for(canonical)
        # each canonical resolves to a citation with at least a doi or pmid
        assert cit.get("citation_doi") or cit.get("citation_pmid"), canonical


def test_mapping_carries_provenance():
    ont = load_label_ontology()
    r = normalize_labels(["cognitively normal"], ont)
    assert r.applied
    rec = r.applied[0]
    assert rec["raw"] == "cognitively normal" and rec["canonical"] == "CN"
    assert rec["citation_doi"] or rec["citation_pmid"]


def test_ambiguous_ontology_fails_closed():
    bad = textwrap.dedent("""
    schema_version: "1.0.0"
    ontology_id: "bad@1.0.0"
    domain: "x"
    status: "research_preview"
    citations: []
    groups:
      - canonical: "CN"
        synonyms: ["foo"]
      - canonical: "AD"
        synonyms: ["foo"]
    """)
    p = Path(tempfile.mktemp(suffix=".yaml"))
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(LabelOntologyError):
        load_label_ontology(p)


def test_nulls_preserved():
    ont = load_label_ontology()
    r = normalize_labels(["cognitively normal", None, "AD"], ont)
    assert r.normalized[0] == "CN"
    assert r.normalized[1] is None
    assert r.normalized[2] == "AD"

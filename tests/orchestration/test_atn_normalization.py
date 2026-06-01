"""v1.60.0 -- biological A/T/N notation synonym layer (USIL increment 2).

Tests the sign-preserving normalizer that maps prose / separator-variant AT(N)
profiles ("amyloid positive tau negative", "A+/T-/N+") onto the canonical
profile strings the biological staging packs consume (A+T-N+, A+T-, ...),
verified against the pack state sets so a reassembled profile is never invented.

The most important guarantee under test: A+T+N+ and A-T-N- must NOT collide
(the clinical normalizer would have collapsed both to 'a t n').
"""
from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest

from neurotcs.orchestration.atn_normalization import (
    AtnOntologyError,
    load_atn_ontology,
    normalize_atn_labels,
)
from neurotcs.rulepack.loader import load_rulepack

ATN8 = {s.name for s in load_rulepack("ad/atn_2018").rulepack.state_space}
AT3 = {s.name for s in load_rulepack("ad/at_biological").rulepack.state_space}


def test_ontology_loads_collision_free():
    ont = load_atn_ontology()
    assert ont.ontology_id
    assert len(ont.yaml_sha256) == 64
    assert ont.axis_index and ont.polarity_index


def test_positive_and_negative_profiles_do_not_collide():
    """The core safety property: A+T+N+ and A-T-N- are DISTINCT outputs."""
    ont = load_atn_ontology()
    r = normalize_atn_labels(["A+T+N+", "A-T-N-", "A+T-N+"], ATN8, ont)
    assert r.normalized == ["A+T+N+", "A-T-N-", "A+T-N+"]
    assert len(set(r.normalized)) == 3


def test_separator_variants_normalize():
    ont = load_atn_ontology()
    r = normalize_atn_labels(["A+/T-/N+", "A+ T- N+", "a+t-n+"], ATN8, ont)
    assert r.normalized == ["A+T-N+", "A+T-N+", "A+T-N+"]


def test_prose_forms_normalize():
    ont = load_atn_ontology()
    r = normalize_atn_labels(
        ["amyloid positive tau negative neurodegeneration positive",
         "amyloid negative tau negative neurodegeneration negative"], ATN8, ont)
    assert r.normalized == ["A+T-N+", "A-T-N-"]


def test_two_axis_pack_arity():
    ont = load_atn_ontology()
    r = normalize_atn_labels(["amyloid positive tau negative", "A+T+", "A-T-"],
                             AT3, ont)
    assert r.normalized == ["A+T-", "A+T+", "A-T-"]


def test_canonical_is_idempotent():
    ont = load_atn_ontology()
    canon = sorted(ATN8)
    r = normalize_atn_labels(canon, ATN8, ont)
    assert r.normalized == canon
    assert r.mapping == {}


def test_never_invents_a_profile_not_in_pack():
    """A cleanly-parsed profile that is not a member of the target pack's states
    is NOT emitted -- it passes through unchanged (never guess)."""
    ont = load_atn_ontology()
    # AT3 pack does NOT contain A-T+ (tau-positive without amyloid is not in the
    # 2-axis pack's 3 states); parsing succeeds but it must not be emitted.
    r = normalize_atn_labels(["amyloid negative tau positive"], AT3, ont)
    assert r.normalized == ["amyloid negative tau positive"]
    assert "amyloid negative tau positive" in r.unmatched


def test_unparseable_passes_through():
    ont = load_atn_ontology()
    raw = ["A+ only", "tau positive", "some_random_token", "A+T+N+X"]
    r = normalize_atn_labels(raw, ATN8, ont)
    assert r.normalized == raw
    assert set(r.unmatched) == set(raw)


def test_conflicting_duplicate_axis_not_mapped():
    """A token naming the same axis twice with opposite signs is ambiguous and
    must not be mapped."""
    ont = load_atn_ontology()
    r = normalize_atn_labels(["A+A-T+N+"], ATN8, ont)
    assert r.normalized == ["A+A-T+N+"]
    assert "A+A-T+N+" in r.unmatched


def test_mapping_carries_citation():
    ont = load_atn_ontology()
    r = normalize_atn_labels(["amyloid positive tau positive neurodegeneration positive"],
                             ATN8, ont)
    assert r.applied
    rec = r.applied[0]
    assert rec["canonical"] == "A+T+N+"
    assert rec["citation_doi"] or rec["citation_pmid"]


def test_nulls_preserved():
    ont = load_atn_ontology()
    r = normalize_atn_labels(["A+T+N+", None, "A-T-N-"], ATN8, ont)
    assert r.normalized[0] == "A+T+N+"
    assert r.normalized[1] is None
    assert r.normalized[2] == "A-T-N-"


def test_ambiguous_ontology_fails_closed():
    bad = textwrap.dedent("""
    ontology_id: "bad@1.0.0"
    axis_words:
      A: ["foo"]
      T: ["foo"]
    polarity_words:
      "+": ["pos"]
      "-": ["neg"]
    citations: []
    """)
    p = Path(tempfile.mktemp(suffix=".yaml"))
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(AtnOntologyError):
        load_atn_ontology(p)

"""v1.63.0 -- ARIA severity recognition (vocabulary) layer.

Companion of the numeric range pack ad/aria_safety: this layer maps free-text
ARIA labels to canonical (type, grade); the range pack validates measured values
against the verbatim FDA-label boundaries.
"""
from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest

from neurotcs.orchestration.aria_grade import (
    AriaGradeOntologyError,
    load_aria_grade_ontology,
    recognize_aria_grades,
)


def test_aria_ontology_loads():
    ont = load_aria_grade_ontology()
    assert ont.ontology_id
    assert len(ont.yaml_sha256) == 64


def test_aria_resolves_combined_labels():
    ont = load_aria_grade_ontology()
    assert ont.resolve("ARIA-E moderate") == ("aria_e", "moderate")
    assert ont.resolve("ARIA-H microhemorrhage severe") == (
        "aria_h_microhemorrhage", "severe")
    assert ont.resolve("aria-h siderosis mild") == ("aria_h_siderosis", "mild")


def test_aria_resolves_freetext_synonyms():
    ont = load_aria_grade_ontology()
    assert ont.resolve("moderate edema") == ("aria_e", "moderate")
    assert ont.resolve("mild microbleed") == ("aria_h_microhemorrhage", "mild")
    assert ont.resolve("severe superficial siderosis") == (
        "aria_h_siderosis", "severe")


def test_aria_none_label():
    ont = load_aria_grade_ontology()
    assert ont.resolve("no ARIA") == ("none", "none")
    assert ont.resolve("none") == ("none", "none")


def test_aria_macrohemorrhage_is_separate_finding_no_grade():
    """Macrohemorrhage is its own finding, never a graded ARIA-H tier."""
    ont = load_aria_grade_ontology()
    assert ont.resolve("macrohemorrhage") == ("macrohemorrhage", "")
    assert ont.resolve("intracerebral hemorrhage") == ("macrohemorrhage", "")


def test_aria_type_without_grade_not_resolved():
    """A finding type with no grade word is not resolved (never guess)."""
    ont = load_aria_grade_ontology()
    assert ont.resolve("ARIA-E") is None
    assert ont.resolve("microhemorrhage") is None


def test_aria_grade_without_type_not_resolved():
    ont = load_aria_grade_ontology()
    assert ont.resolve("severe") is None
    assert ont.resolve("moderate") is None


def test_aria_non_aria_label_passes_through():
    ont = load_aria_grade_ontology()
    assert ont.resolve("CN") is None
    assert ont.resolve("some_random_label") is None


def test_aria_two_findings_in_one_string_fail_closed():
    """A string naming two finding types is ambiguous -> never guessed."""
    ont = load_aria_grade_ontology()
    assert ont.resolve("ARIA-E and ARIA-H severe") is None
    assert ont.resolve("edema moderate microhemorrhage mild") is None


def test_aria_bare_aria_h_without_subtype_not_resolved():
    """Bare ARIA-H (no micro/siderosis subtype) is not resolved -- we never
    guess which hemorrhage subtype is meant."""
    ont = load_aria_grade_ontology()
    assert ont.resolve("aria-h severe") is None


def test_aria_conflicting_grades_not_resolved():
    ont = load_aria_grade_ontology()
    assert ont.resolve("severe mild aria-e") is None


def test_aria_recognized_carries_van_etten_2026_citation():
    ont = load_aria_grade_ontology()
    r = recognize_aria_grades([("S1", "ARIA-E moderate")], ont)
    rec = r.recognized["S1"]
    assert rec["type"] == "aria_e" and rec["grade"] == "moderate"
    assert rec["citation_pmid"] == "42015334"  # van Etten 2026
    assert rec["citation_doi"] == "10.1002/alz.71361"


def test_aria_recognize_partitions_by_type():
    ont = load_aria_grade_ontology()
    pairs = [("S1", "ARIA-E moderate"), ("S2", "severe superficial siderosis"),
             ("S3", "mild microbleed"), ("S4", "macrohemorrhage"),
             ("S5", "no ARIA"), ("S6", "CN")]
    r = recognize_aria_grades(pairs, ont)
    assert set(r.recognized) == {"S1", "S2", "S3", "S4", "S5"}  # S6 not ARIA
    assert "S6" not in r.recognized
    assert r.by_type["aria_e"] == ["S1"]
    assert r.by_type["aria_h_siderosis"] == ["S2"]
    assert r.by_type["aria_h_microhemorrhage"] == ["S3"]
    assert r.by_type["macrohemorrhage"] == ["S4"]


def test_aria_ontology_collision_fails_closed():
    bad = textwrap.dedent("""
    ontology_id: "bad@1.0.0"
    citations: []
    grade_synonyms:
      mild: ["foo"]
      severe: ["foo"]
    type_synonyms: {}
    canonical_labels: []
    """)
    p = Path(tempfile.mktemp(suffix=".yaml"))
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(AriaGradeOntologyError):
        load_aria_grade_ontology(p)


def test_aria_companion_range_pack_present():
    """The numeric companion pack ad/aria_safety must exist and carry the
    grade-boundary measurements this recognition layer pairs with."""
    from neurotcs.clinical_ranges.loader import list_rangepacks
    ids = [p["name"] for p in list_rangepacks()]
    assert "ad/aria_safety" in ids

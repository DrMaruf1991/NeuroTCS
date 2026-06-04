"""v1.61.0 -- disease-control ontology + longitudinal conversion auditor (USIL increment 3)."""
from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest

from neurotcs.orchestration.conversion_audit import audit_conversions
from neurotcs.orchestration.disease_control import (
    DiseaseControlOntologyError,
    load_disease_control_ontology,
    recognize_disease_controls,
)

# ---------------------------------------------------------------- disease-control


def test_dc_ontology_loads_collision_free():
    ont = load_disease_control_ontology()
    assert ont.ontology_id
    assert len(ont.yaml_sha256) == 64
    assert set(ont.canonicals) == {
        "VaD", "DLB", "PDD", "bvFTD", "PPA", "iNPH", "TES",
        "autoimmune_encephalitis", "mixed_dementia", "CBD", "PSP",
        "depression_cognitive"}


def test_dc_recognizes_non_ad_labels():
    ont = load_disease_control_ontology()
    labels = [("S1", "vascular dementia"), ("S2", "DLB"),
              ("S3", "Lewy body dementia"), ("S4", "bvFTD"),
              ("S5", "progressive supranuclear palsy"), ("S6", "pseudodementia")]
    r = recognize_disease_controls(labels, ont)
    cats = {k: v["category"] for k, v in r.recognized.items()}
    assert cats == {"S1": "VaD", "S2": "DLB", "S3": "DLB", "S4": "bvFTD",
                    "S5": "PSP", "S6": "depression_cognitive"}


def test_dc_passes_through_ad_and_unknown():
    """AD clinical-stage labels and unknown labels are NOT recognized as
    disease controls (never guess)."""
    ont = load_disease_control_ontology()
    r = recognize_disease_controls(
        [("S1", "CN"), ("S2", "MCI"), ("S3", "AD"), ("S4", "some_random")], ont)
    assert r.recognized == {}


def test_dc_every_category_citation_anchored():
    ont = load_disease_control_ontology()
    for cat in ont.canonicals:
        cit = ont.citation_for(cat)
        # every category has at least a DOI (Kiloh is DOI-only; others have PMID too)
        assert cit.get("citation_doi"), cat


def test_dc_kiloh_is_doi_only():
    ont = load_disease_control_ontology()
    cit = ont.citation_for("depression_cognitive")
    assert cit["citation_doi"].startswith("10.")
    assert cit["citation_pmid"] == ""  # no PMID fabricated


def test_dc_recognized_carries_citation():
    ont = load_disease_control_ontology()
    r = recognize_disease_controls([("S1", "DLB")], ont)
    rec = r.recognized["S1"]
    assert rec["category"] == "DLB"
    assert rec["citation_pmid"] and rec["citation_doi"]


def test_dc_ambiguous_ontology_fails_closed():
    bad = textwrap.dedent("""
    ontology_id: "bad@1.0.0"
    citations: []
    groups:
      - canonical: "VaD"
        synonyms: ["foo"]
      - canonical: "DLB"
        synonyms: ["foo"]
    """)
    p = Path(tempfile.mktemp(suffix=".yaml"))
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(DiseaseControlOntologyError):
        load_disease_control_ontology(p)


# ----------------------------------------------------------------- conversion


def test_conversion_forward_is_informational():
    r = audit_conversions([("S1", 0, "CN"), ("S1", 1, "MCI"), ("S1", 2, "AD")])
    assert r.severity_counts["informational"] == 2
    assert r.severity_counts["impossible"] == 0
    assert r.severity_counts["implausible"] == 0
    assert r.derived_labels["S1"] == "converter"
    for f in r.flags:
        assert f.direction == "forward"
        assert f.citation_pmid == "29653606"  # Jack 2018 continuum


def test_conversion_mci_to_cn_is_plausible_not_impossible():
    """MCI->CN reversion is documented (Canevelli 2016) -> informational, never
    rejected, never 'impossible'."""
    r = audit_conversions([("S1", 0, "MCI"), ("S1", 1, "CN")])
    assert r.severity_counts["informational"] == 1
    assert r.severity_counts["impossible"] == 0
    assert r.severity_counts["implausible"] == 0
    f = r.flags[0]
    assert f.direction == "reversion" and f.tier == "informational"
    assert f.citation_pmid == "27502450"  # Canevelli 2016
    assert r.derived_labels["S1"] == "reverter"


def test_conversion_ad_to_cn_is_implausible():
    r = audit_conversions([("S1", 0, "AD"), ("S1", 1, "CN")])
    assert r.severity_counts["implausible"] == 1
    f = r.flags[0]
    assert f.tier == "implausible"


def test_conversion_ad_to_mci_is_implausible():
    r = audit_conversions([("S1", 0, "AD"), ("S1", 1, "MCI")])
    assert r.severity_counts["implausible"] == 1


def test_conversion_within_mci_band_is_informational():
    r = audit_conversions([("S1", 0, "LMCI"), ("S1", 1, "EMCI")])
    assert r.severity_counts["informational"] == 1
    assert r.flags[0].direction == "within_band"


def test_conversion_single_visit_no_flag():
    r = audit_conversions([("S1", 0, "CN")])
    assert r.flags == []
    assert r.derived_labels == {}


def test_conversion_noncanonical_label_no_flag():
    """A non-canonical state produces no transition flag (never guess)."""
    r = audit_conversions([("S1", 0, "weird_label"), ("S1", 1, "AD")])
    # only one canonical state in the sequence -> < 2 canonical visits -> no flag
    assert r.flags == []


def test_conversion_stable_subject():
    r = audit_conversions([("S1", 0, "MCI"), ("S1", 1, "MCI"), ("S1", 2, "MCI")])
    assert r.flags == []
    assert r.derived_labels["S1"] == "stable"


def test_conversion_mixed_forward_and_reversion():
    r = audit_conversions([("S1", 0, "CN"), ("S1", 1, "MCI"), ("S1", 2, "CN")])
    assert r.derived_labels["S1"] == "mixed"

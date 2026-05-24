"""Structural regression tests for docs/datasheet/ad_neurotcs_datasheet.md.

This is the AD-lock Step 2.3 deliverable: a four-framework consolidation
document (Gebru Datasheet, Mitchell Model Card, FDA PCCP, EU AI Act Annex
IV) that must remain reviewer-verifiable across all future NeuroTCS
releases.

These tests do NOT verify the prose content (that's a human-review task).
They verify the STRUCTURAL skeleton: every required section header from
each source standard is present, every locked invariant from the
three-cohort AD validation appears, every citation DOI / PMID is intact.

If a future commit silently drops a section, mangles an audit_id, or
removes a framework citation, CI catches it before release.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOC_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs" / "datasheet" / "ad_neurotcs_datasheet.md"
)


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert DOC_PATH.exists(), f"Datasheet missing at {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
# Top-level framework sections
# -----------------------------------------------------------------------------

REQUIRED_TOP_SECTIONS = [
    "## A — Cryptographic anchors (locked invariants)",
    "## B — Datasheet for Datasets",
    "## C — Model Card for the cTCS metric",
    "## D — FDA PCCP three mandatory components",
    "## E — EU AI Act Annex IV technical documentation",
    "## F — Honest gaps acknowledged",
    "## G — NACC DUA acknowledgments",
    "## H — Version history",
    "## I — Citation",
]


@pytest.mark.parametrize("section", REQUIRED_TOP_SECTIONS)
def test_top_level_section_present(doc_text: str, section: str):
    """Each of the 8 top-level framework sections must be present, with the
    exact header text — a reviewer following the four source standards needs
    to know which section maps to which framework."""
    assert section in doc_text, (
        f"Top-level section missing from AD datasheet: '{section}'.\n"
        f"This is a required four-framework anchor. Re-add the section "
        f"with the canonical header and complete content; do not silently "
        f"drop framework coverage."
    )


# -----------------------------------------------------------------------------
# Gebru 2021 — 7 sections
# -----------------------------------------------------------------------------

GEBRU_SECTIONS = [
    "### B.1 — Motivation",
    "### B.2 — Composition",
    "### B.3 — Collection process",
    "### B.4 — Preprocessing / cleaning / labeling",
    "### B.5 — Uses",
    "### B.6 — Distribution",
    "### B.7 — Maintenance",
]


@pytest.mark.parametrize("section", GEBRU_SECTIONS)
def test_gebru_datasheet_section_present(doc_text: str, section: str):
    """All 7 sections of Datasheets for Datasets (Gebru et al., CACM 2021,
    DOI 10.1145/3458723) must be addressed in Section B."""
    assert section in doc_text, (
        f"Missing Gebru Datasheet section: {section}. "
        f"See DOI 10.1145/3458723 for the canonical 7-section list."
    )


# -----------------------------------------------------------------------------
# Mitchell 2019 — 9 sections
# -----------------------------------------------------------------------------

MITCHELL_SECTIONS = [
    "### C.1 — Model details",
    "### C.2 — Intended use",
    "### C.3 — Factors",
    "### C.4 — Metrics",
    "### C.5 — Evaluation data",
    "### C.6 — Training data",
    "### C.7 — Quantitative analyses",
    "### C.8 — Ethical considerations",
    "### C.9 — Caveats and recommendations",
]


@pytest.mark.parametrize("section", MITCHELL_SECTIONS)
def test_mitchell_model_card_section_present(doc_text: str, section: str):
    """All 9 sections of Model Cards (Mitchell et al., FAT* 2019,
    DOI 10.1145/3287560.3287596) must be addressed in Section C."""
    assert section in doc_text, (
        f"Missing Mitchell Model Card section: {section}. "
        f"See DOI 10.1145/3287560.3287596 for the canonical 9-section list."
    )


# -----------------------------------------------------------------------------
# FDA PCCP — 3 mandatory components
# -----------------------------------------------------------------------------

PCCP_COMPONENTS = [
    "### D.1 — Description of modifications",
    "### D.2 — Modification protocol",
    "### D.3 — Impact assessment",
]


@pytest.mark.parametrize("component", PCCP_COMPONENTS)
def test_fda_pccp_component_present(doc_text: str, component: str):
    """FDA's August 2025 PCCP final guidance ('Marketing Submission
    Recommendations for a Predetermined Change Control Plan for AI-Enabled
    Device Software Functions') requires three mandatory components.
    Legal basis: Section 515C of FD&C Act per FDORA 2022."""
    assert component in doc_text, (
        f"Missing FDA PCCP component: {component}. "
        f"The Aug 2025 final guidance requires all three."
    )


# -----------------------------------------------------------------------------
# EU AI Act Annex IV — 9 sections
# -----------------------------------------------------------------------------

EU_AI_ACT_SECTIONS = [
    "### E.1 — General description",
    "### E.2 — Detailed description",
    "### E.3 — Monitoring, functioning, control",
    "### E.4 — Performance metrics",
    "### E.5 — Risk management system",
    "### E.6 — Lifecycle changes",
    "### E.7 — Standards and specifications applied",
    "### E.8 — EU declaration of conformity",
    "### E.9 — Post-market monitoring plan",
]


@pytest.mark.parametrize("section", EU_AI_ACT_SECTIONS)
def test_eu_ai_act_annex_iv_section_present(doc_text: str, section: str):
    """EU AI Act (Regulation 2024/1689) Article 11 + Annex IV require 9
    technical-documentation sections. High-risk AI deadline: 2 August 2026
    standalone; 2 August 2027 for MDR/IVDR-regulated medical AI."""
    assert section in doc_text, (
        f"Missing EU AI Act Annex IV section: {section}. "
        f"Required by Article 11 for high-risk AI systems."
    )


# -----------------------------------------------------------------------------
# Required citations (DOI / PMID anchors)
# -----------------------------------------------------------------------------

REQUIRED_CITATIONS = [
    # Gebru Datasheets for Datasets
    "10.1145/3458723",
    # Mitchell Model Cards
    "10.1145/3287560.3287596",
    # FUTURE-AI BMJ 2025
    "10.1136/bmj-2024-081554",
    "39909534",  # FUTURE-AI PMID
    # NIA-AA 2018 Research Framework (Jack 2018)
    "29653606",  # PMID
    # Jack 2024 (AA-2024 source; documented as a gap)
    "10.1002/alz.13859",
    "38934362",  # Jack 2024 PMID
    # MIRIAD source publication
    "23274184",  # Malone 2013 PMID
]


@pytest.mark.parametrize("citation", REQUIRED_CITATIONS)
def test_required_citation_present(doc_text: str, citation: str):
    """Every framework cited in the datasheet must have its DOI or PMID
    anchor in the text — reviewers verify against the source publications."""
    assert citation in doc_text, (
        f"Missing required citation identifier in datasheet: {citation}"
    )


# -----------------------------------------------------------------------------
# Locked invariants from Section A — these are the AD validation's
# reproducibility certificate. They MUST appear verbatim in the doc.
# -----------------------------------------------------------------------------

LOCKED_INVARIANTS = [
    # ADNI
    "0.9946",
    "12,006",
    # OASIS-3
    "0.9942",
    "7,248",
    "1,377",
    # MIRIAD longitudinal
    "0.9854",
    "947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0",
    "aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da",
    # MIRIAD test-retest
    "804303993ff5c9134b5f4dfa8919fc6600d03a86081cedb02227ef5845784e85",
    "dcf8b7de3ff9019e9cda703064039e3a71193566d1f5082ce96646188fd52fc4",
    # Rulepack SHA prefix
    "f359148d1cbf6abe",
]


@pytest.mark.parametrize("invariant", LOCKED_INVARIANTS)
def test_locked_invariant_present(doc_text: str, invariant: str):
    """Every locked invariant from the three-cohort AD validation must
    appear verbatim in the datasheet's Section A. These are cryptographic
    anchors that reviewers verify against the test suite outputs."""
    assert invariant in doc_text, (
        f"Locked invariant missing from datasheet Section A: {invariant}. "
        f"This breaks the reproducibility certificate; do not edit the "
        f"locked invariants without re-running the audit and updating "
        f"the tests in tests/audit_core/test_real_*_audit.py."
    )


# -----------------------------------------------------------------------------
# Honest-gaps section — these MUST be acknowledged, not hidden
# -----------------------------------------------------------------------------

REQUIRED_GAPS = [
    "Jack 2024",  # primary AA-2024 staging text not yet transcribed
    "ADNI and OASIS-3 fairness pending",  # local demographic joins pending
    "race_ethnicity in MIRIAD",  # MIRIAD doesn't collect race
    "TPR",  # explicit acknowledgement that classifier metrics N/A
    "not yet a marketed medical device",  # regulatory honesty
]


@pytest.mark.parametrize("gap", REQUIRED_GAPS)
def test_honest_gap_acknowledged(doc_text: str, gap: str):
    """Each known limitation must be explicitly acknowledged in Section F.
    Hiding gaps to make the doc look stronger is exactly the partial-fix
    antipattern this AD-lock plan rules out."""
    # Restrict the search to the gaps section to ensure the phrase appears
    # in the right context (not just incidentally elsewhere).
    section_start = doc_text.find("## F — Honest gaps acknowledged")
    assert section_start >= 0, "Section F (honest gaps) missing entirely"
    section_end = doc_text.find("## G —", section_start)
    if section_end < 0:
        section_end = len(doc_text)
    gaps_block = doc_text[section_start:section_end]
    assert gap in gaps_block, (
        f"Honest-gap acknowledgement missing from Section F: '{gap}'. "
        f"The four-framework datasheet must surface known limitations "
        f"clearly so reviewers see them; do not silently drop them."
    )

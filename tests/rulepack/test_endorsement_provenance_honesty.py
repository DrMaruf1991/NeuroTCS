"""v1.64.0 -- honest endorsement provenance (external-audit Finding, 2026-06).

Co-author affiliations of a cited guideline's authors are NOT endorsements of
NeuroTCS. They must live in source_author_affiliations, never in
endorsing_bodies. These tests lock that separation across all production AD
rule packs and prove the AD-only scope (no Parkinson's / non-AD body is listed
as an endorser).
"""
from __future__ import annotations

import pytest

from neurotcs.rulepack.loader import load_rulepack

_PROD_PACKS = [
    "ad/aa_2024",
    "ad/aa_2024_trac",
    "ad/adni_clinical_stage",
    "ad/at_biological",
    "ad/atn_2018",
    "ad/niaaa_2018",
]

# Markers that indicate an entry is a mere author affiliation, not an endorser.
_AFFILIATION_MARKERS = ("co-author", "coauthor")
# Non-AD / clearly-not-an-AD-guideline-endorser bodies that must never appear in
# endorsing_bodies of an AD pack.
_NON_AD_BODIES = (
    "Michael J. Fox",
    "Parkinson",
    "Takeda",
    "Novartis",
)


@pytest.mark.parametrize("pid", _PROD_PACKS)
def test_endorsing_bodies_contain_no_pure_coauthor_affiliation(pid):
    """No endorsing_bodies entry may be framed as a co-author affiliation."""
    pack = load_rulepack(pid).rulepack
    for entry in pack.endorsing_bodies:
        low = entry.lower()
        assert not any(m in low for m in _AFFILIATION_MARKERS), (
            f"{pid}: endorsing_bodies entry frames a co-author affiliation as "
            f"an endorser: {entry!r}")


@pytest.mark.parametrize("pid", _PROD_PACKS)
def test_endorsing_bodies_contain_no_non_ad_body(pid):
    """No non-AD body (e.g. Michael J. Fox Foundation / Parkinson's) may be
    listed as an endorser of an AD rule pack."""
    pack = load_rulepack(pid).rulepack
    joined = " ".join(pack.endorsing_bodies)
    for body in _NON_AD_BODIES:
        assert body not in joined, (
            f"{pid}: non-AD body {body!r} must not be an endorsing_body.")


@pytest.mark.parametrize("pid", _PROD_PACKS)
def test_every_pack_keeps_five_genuine_endorsers(pid):
    """After the split, each production pack still has >=5 genuine endorsers
    (so the production gate passes honestly, not by padding)."""
    pack = load_rulepack(pid).rulepack
    assert len(set(pack.endorsing_bodies)) >= 5, (
        f"{pid}: only {len(set(pack.endorsing_bodies))} genuine endorsers.")


def test_moved_affiliations_recorded_in_source_field():
    """The co-author affiliations moved out of aa_2024 endorsing_bodies are
    preserved in source_author_affiliations (provenance not lost)."""
    pack = load_rulepack("ad/aa_2024").rulepack
    affils = getattr(pack, "source_author_affiliations", [])
    joined = " ".join(affils)
    # the Michael J. Fox Foundation entry was moved here, not deleted
    assert "Michael J. Fox" in joined
    assert "Takeda" in joined
    assert "Novartis" in joined


def test_source_author_affiliations_does_not_change_audit_id():
    """source_author_affiliations is metadata: mutating it must NOT change the
    canonical scientific SHA (audit_id input)."""
    from neurotcs.rulepack.loader import _canonical_serialize
    pack = load_rulepack("ad/aa_2024").rulepack
    before = _canonical_serialize(pack)
    mutated = pack.model_copy(update={
        "source_author_affiliations": [*pack.source_author_affiliations, "X"]})
    after = _canonical_serialize(mutated)
    assert before == after

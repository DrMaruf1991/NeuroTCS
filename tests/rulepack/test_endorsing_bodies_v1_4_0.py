"""
Tests for v1.4.0 schema feature: pack-level endorsing_bodies field.

Added in NeuroTCS v1.12.0 per gap-check Finding A 2026-05-26.

Two-stage validator:
  - HARD ERROR: production rulepacks must declare non-empty endorsing_bodies
  - WARNING: production rulepacks SHOULD have >=5 unique endorsing bodies
  - Skeleton + research_preview statuses are unaffected
"""

from __future__ import annotations

import warnings
from datetime import date

import pytest
from pydantic import ValidationError

from neurotcs.rulepack.schema import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    Citation,
    DiseaseDomain,
    RulePack,
    RulePackStatus,
    State,
    Transition,
)

# ============================================================
# Schema-level invariants
# ============================================================


def test_schema_version_bumped_to_1_4_0():
    """v1.12.0 ships schema 1.4.0."""
    assert SCHEMA_VERSION == "1.4.0"


def test_supported_schema_versions_includes_1_4_0():
    """1.4.0 is a supported loadable version."""
    assert "1.4.0" in SUPPORTED_SCHEMA_VERSIONS


def test_supported_schema_versions_includes_prior_versions():
    """Backward compat: 1.1.0, 1.2.0, 1.3.0 still loadable."""
    assert "1.1.0" in SUPPORTED_SCHEMA_VERSIONS
    assert "1.2.0" in SUPPORTED_SCHEMA_VERSIONS
    assert "1.3.0" in SUPPORTED_SCHEMA_VERSIONS


# ============================================================
# Helper fixtures
# ============================================================


def _minimal_kwargs(
    *,
    status: RulePackStatus,
    endorsing_bodies: list[str] | None = None,
    transitions: list[Transition] | None = None,
) -> dict:
    """Build a minimal-but-valid kwargs dict for RulePack construction."""
    cit = Citation(citation_pmid="12345", citation_text="ref")
    states = [
        State(name="A", description="state A", ordinal_rank=0),
        State(name="B", description="state B", ordinal_rank=1),
    ]
    if transitions is None:
        transitions = [
            Transition(
                from_state="A", to_state="B",
                citation=cit, guideline_section="X §1",
            )
        ]
    kw = dict(
        rulepack_id="test/endorsing_bodies_validator@1.0.0",
        ruleset_version="1.0.0",
        effective_date=date.today(),
        status=status,
        disease_domain=DiseaseDomain.CUSTOM,
        framework_name="Test framework",
        transcribed_by="Test MD",
        clinical_source_authority="Test authority",
        anchor_citation=cit,
        state_space=states,
        admissible_transitions=transitions,
    )
    if endorsing_bodies is not None:
        kw["endorsing_bodies"] = endorsing_bodies
    return kw


# ============================================================
# Hard-error tests: production rulepacks MUST have endorsing_bodies
# ============================================================


def test_production_without_endorsing_bodies_raises():
    """Production rulepack with no endorsing_bodies field -> hard error."""
    with pytest.raises(ValidationError) as exc_info:
        RulePack(**_minimal_kwargs(status=RulePackStatus.PRODUCTION))
    msg = str(exc_info.value)
    assert "endorsing_bodies" in msg
    assert "PRODUCTION" in msg


def test_production_with_empty_list_raises():
    """Production rulepack with empty endorsing_bodies list -> hard error."""
    with pytest.raises(ValidationError) as exc_info:
        RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=[],
        ))
    assert "endorsing_bodies" in str(exc_info.value)


def test_production_with_empty_string_entry_raises():
    """Production rulepack with empty-string entry -> hard error."""
    with pytest.raises(ValidationError) as exc_info:
        RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=["Body A", "", "Body C", "Body D", "Body E"],
        ))
    msg = str(exc_info.value)
    assert "empty" in msg.lower() or "whitespace" in msg.lower()


def test_production_with_whitespace_only_entry_raises():
    """Production rulepack with whitespace-only entry -> hard error."""
    with pytest.raises(ValidationError):
        RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=["Body A", "   ", "Body C", "Body D", "Body E"],
        ))


# ============================================================
# Warning tests: <5 unique endorsers emits warning but accepts
# ============================================================


def test_production_with_1_endorser_emits_warning():
    """Production with 1 endorser: accepts but warns."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        rp = RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=["Single Body"],
        ))
    assert rp.status == RulePackStatus.PRODUCTION
    assert len(w) >= 1
    assert any("only 1" in str(wi.message) for wi in w)


def test_production_with_4_endorsers_emits_warning():
    """Production with 4 endorsers (just under threshold): warns."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=["A", "B", "C", "D"],
        ))
    assert any("only 4" in str(wi.message) for wi in w)


def test_production_with_5_endorsers_accepts_silently():
    """Production with exactly 5 endorsers: no warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        rp = RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=["A", "B", "C", "D", "E"],
        ))
    # Filter for ONLY endorsing_bodies-related warnings; ignore others
    eb_warnings = [wi for wi in w
                   if "endorsing_bodies" in str(wi.message)]
    assert len(eb_warnings) == 0
    assert rp.status == RulePackStatus.PRODUCTION


def test_production_with_many_endorsers_accepts_silently():
    """Production with 14 endorsers (like real packs): no warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=[f"Body {i}" for i in range(14)],
        ))
    eb_warnings = [wi for wi in w
                   if "endorsing_bodies" in str(wi.message)]
    assert len(eb_warnings) == 0


def test_production_unique_count_used_not_total():
    """Duplicates in list don't satisfy >=5 unique threshold."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # 5 entries but only 3 unique
        RulePack(**_minimal_kwargs(
            status=RulePackStatus.PRODUCTION,
            endorsing_bodies=["A", "B", "C", "A", "B"],
        ))
    eb_warnings = [wi for wi in w
                   if "endorsing_bodies" in str(wi.message)]
    assert len(eb_warnings) >= 1
    assert any("only 3" in str(wi.message) for wi in eb_warnings)


# ============================================================
# Status-gating tests: only production is checked
# ============================================================


def test_skeleton_without_endorsing_bodies_accepts():
    """Skeleton rulepack does not require endorsing_bodies."""
    rp = RulePack(**_minimal_kwargs(
        status=RulePackStatus.SKELETON,
        transitions=[],  # skeleton may have empty transitions
    ))
    assert rp.status == RulePackStatus.SKELETON
    assert rp.endorsing_bodies == []


def test_skeleton_with_few_endorsers_no_warning():
    """Skeleton with <5 endorsers does NOT emit the endorsing-bodies warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        RulePack(**_minimal_kwargs(
            status=RulePackStatus.SKELETON,
            endorsing_bodies=["A"],
            transitions=[],
        ))
    eb_warnings = [wi for wi in w
                   if "endorsing_bodies" in str(wi.message)]
    assert len(eb_warnings) == 0


# ============================================================
# Shipped-pack assertions: real packs satisfy >=5 floor
# ============================================================


@pytest.mark.parametrize(
    "pack_name",
    ["ad/aa_2024", "ad/aa_2024_trac", "ad/niaaa_2018"],
)
def test_shipped_production_packs_have_5plus_endorsers(pack_name: str):
    """All 3 production AD rulepacks must have >=5 endorsing bodies."""
    from neurotcs.rulepack import load_rulepack
    pack = load_rulepack(pack_name)
    assert pack.rulepack.status == RulePackStatus.PRODUCTION
    unique = set(pack.rulepack.endorsing_bodies)
    assert len(unique) >= 5, (
        f"Pack {pack_name} has only {len(unique)} unique endorsing_bodies; "
        f">=5 required for production status (schema 1.4.0)."
    )


@pytest.mark.parametrize(
    "pack_name",
    ["ad/aa_2024", "ad/aa_2024_trac", "ad/niaaa_2018"],
)
def test_shipped_production_packs_declare_schema_1_4_0(pack_name: str):
    """All 3 production AD rulepacks declare schema_version 1.4.0."""
    from neurotcs.rulepack import load_rulepack
    pack = load_rulepack(pack_name)
    assert pack.rulepack.schema_version == "1.4.0", (
        f"Pack {pack_name} declares schema_version "
        f"'{pack.rulepack.schema_version}', expected '1.4.0' "
        f"(packs that use endorsing_bodies must declare 1.4.0)."
    )


@pytest.mark.parametrize(
    "pack_name",
    ["ad/aa_2024", "ad/aa_2024_trac", "ad/niaaa_2018"],
)
def test_shipped_production_packs_endorsers_are_non_empty_strings(
    pack_name: str,
):
    """No empty/whitespace entries in shipped endorsing_bodies."""
    from neurotcs.rulepack import load_rulepack
    pack = load_rulepack(pack_name)
    for entry in pack.rulepack.endorsing_bodies:
        assert isinstance(entry, str)
        assert entry.strip() != "", (
            f"Pack {pack_name} has empty/whitespace endorsing_bodies entry."
        )

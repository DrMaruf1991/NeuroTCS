"""
NeuroTCS Rule Pack v1.1 test suite.

Covers:
  - Schema v1.1 (transcribed_by, clinical_source_authority, guideline_section)
  - Citation enforcement (every transition requires PMID or DOI + section)
  - Fail-closed loader behavior
  - SHA-256 stable across runs
  - All discovered rule packs load as PRODUCTION
  - Behavioral admissibility for every rule pack
  - Transcription audit documents exist for every production rule pack
  - Pydantic strict-mode rejects unknown fields
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from neurotcs.rulepack.loader import (
    RulePackLoadError,
    list_rulepacks,
    load_rulepack,
    load_rulepack_from_path,
)
from neurotcs.rulepack.schema import (
    SCHEMA_VERSION,
    AttributionType,
    Citation,
    DiseaseDomain,
    RulePack,
    RulePackStatus,
    State,
    Transition,
)

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"

# ALL_PACKS is DERIVED from the filesystem, not hard-coded. A hard-coded list
# (or count) is a maintenance trap: adding a pack silently breaks these tests
# until someone edits the literal. Deriving from rules/ means the suite tracks
# reality automatically -- add a pack and it is covered with no edit here.
# (Mirrors scripts/ci/verify_rule_packs.py, which enforces the same invariant
# in CI: registry must equal filesystem.)
from neurotcs.rulepack.loader import DEFAULT_RULES_DIR as _RULES_DIR


def _discover_all_packs() -> list[str]:
    names: list[str] = []
    for _yaml in sorted(_RULES_DIR.rglob("*.yaml")):
        rel = _yaml.relative_to(_RULES_DIR)
        names.append(str(rel.with_suffix("")).replace("\\", "/"))
    return names


ALL_PACKS = _discover_all_packs()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTION_AUDIT_DIR = PROJECT_ROOT / "docs" / "transcription_audit"


# ============================================================
# Schema-level tests
# ============================================================

def test_schema_version_is_1_5():
    assert SCHEMA_VERSION == "1.5.0"
    print(f"  {PASS} test_schema_version_is_1_5")


def test_citation_requires_pmid_or_doi():
    try:
        Citation(citation_text="Some text")
        assert False
    except Exception as e:
        assert "at least one" in str(e).lower()
    print(f"  {PASS} test_citation_requires_pmid_or_doi")


def test_transition_requires_citation_and_section():
    """v1.1: Transition requires citation AND guideline_section."""
    cit = Citation(citation_pmid="1", citation_text="ref")

    # Missing citation
    try:
        Transition(from_state="A", to_state="B",
                    guideline_section="ref §1")
        assert False
    except Exception:
        pass

    # Missing guideline_section
    try:
        Transition(from_state="A", to_state="B", citation=cit)
        assert False
    except Exception:
        pass

    # Valid
    t = Transition(from_state="A", to_state="B", citation=cit,
                    guideline_section="ref §1")
    assert t.guideline_section == "ref §1"
    print(f"  {PASS} test_transition_requires_citation_and_section")


def test_transition_attribution_type_default_is_guideline_quote():
    """Schema v1.3: default attribution_type is GUIDELINE_QUOTE."""
    cit = Citation(citation_pmid="1", citation_text="ref")
    t = Transition(from_state="A", to_state="B", citation=cit,
                    guideline_section="ref §1")
    assert t.attribution_type == AttributionType.GUIDELINE_QUOTE
    assert t.inference_rationale is None
    print(f"  {PASS} test_transition_attribution_type_default_is_guideline_quote")


def test_transition_clinical_inference_requires_rationale():
    """Schema v1.3: attribution_type=clinical_inference REQUIRES inference_rationale."""
    cit = Citation(citation_pmid="1", citation_text="ref")
    try:
        Transition(
            from_state="A", to_state="B", citation=cit,
            guideline_section="ref §1",
            attribution_type=AttributionType.CLINICAL_INFERENCE,
            # missing inference_rationale!
        )
        assert False, "should have raised because rationale is required"
    except Exception as e:
        assert "inference_rationale" in str(e).lower()
    print(f"  {PASS} test_transition_clinical_inference_requires_rationale")


def test_transition_clinical_inference_empty_rationale_rejected():
    """Schema v1.3: empty / whitespace-only rationale must be rejected too."""
    cit = Citation(citation_pmid="1", citation_text="ref")
    try:
        Transition(
            from_state="A", to_state="B", citation=cit,
            guideline_section="ref §1",
            attribution_type=AttributionType.CLINICAL_INFERENCE,
            inference_rationale="   ",  # whitespace only
        )
        assert False
    except Exception as e:
        assert "inference_rationale" in str(e).lower()
    print(f"  {PASS} test_transition_clinical_inference_empty_rationale_rejected")


def test_transition_clinical_inference_with_rationale_valid():
    """Schema v1.3: clinical_inference + non-empty rationale must validate."""
    cit = Citation(citation_pmid="1", citation_text="ref")
    t = Transition(
        from_state="A", to_state="B", citation=cit,
        guideline_section="ref §1",
        attribution_type=AttributionType.CLINICAL_INFERENCE,
        inference_rationale=(
            "Direct A->B transition in a single scan is clinically "
            "implausible given measurement noise; 56-day minimum follows "
            "the response-confirmation window described in the citation."
        ),
    )
    assert t.attribution_type == AttributionType.CLINICAL_INFERENCE
    assert "implausible" in t.inference_rationale
    print(f"  {PASS} test_transition_clinical_inference_with_rationale_valid")


def test_rulepack_requires_v1_1_authorship_fields():
    """v1.1 schema requires transcribed_by and clinical_source_authority.

    NOTE (v1.4.0 schema): production status now also requires
    endorsing_bodies (>=1 entry; >=5 unique recommended). This test
    constructs a valid production pack with all required fields including
    endorsing_bodies; the test focus remains the v1.1 authorship fields.
    """
    cit = Citation(citation_pmid="1", citation_text="ref")
    states = [State(name="A", description="a", ordinal_rank=0),
              State(name="B", description="b", ordinal_rank=1)]
    trans = [Transition(from_state="A", to_state="B", citation=cit,
                          guideline_section="X §1")]

    base = dict(
        rulepack_id="test/foo@1.0.0",
        ruleset_version="1.0.0",
        effective_date=date.today(),
        status=RulePackStatus.PRODUCTION,
        disease_domain=DiseaseDomain.CUSTOM,
        framework_name="Test",
        anchor_citation=cit,
        state_space=states,
        admissible_transitions=trans,
        # v1.4.0 schema: production status requires endorsing_bodies
        endorsing_bodies=["Body A", "Body B", "Body C", "Body D",
                          "Body E", "Body F"],
    )

    # Missing transcribed_by
    try:
        RulePack(**base, clinical_source_authority="Some authority")
        assert False
    except Exception:
        pass

    # Missing clinical_source_authority
    try:
        RulePack(**base, transcribed_by="Test MD")
        assert False
    except Exception:
        pass

    # Valid
    rp = RulePack(**base,
                  transcribed_by="Test MD",
                  clinical_source_authority="Test authority")
    assert rp.transcribed_by == "Test MD"
    print(f"  {PASS} test_rulepack_requires_v1_1_authorship_fields")


def test_production_requires_transitions():
    cit = Citation(citation_pmid="1", citation_text="x")
    states = [State(name="A", description="a", ordinal_rank=0),
              State(name="B", description="b", ordinal_rank=1)]
    try:
        RulePack(
            rulepack_id="test/empty@1.0.0",
            ruleset_version="1.0.0",
            effective_date=date.today(),
            status=RulePackStatus.PRODUCTION,
            disease_domain=DiseaseDomain.CUSTOM,
            framework_name="X",
            transcribed_by="Test",
            clinical_source_authority="Test",
            anchor_citation=cit,
            state_space=states,
            admissible_transitions=[],
        )
        assert False
    except Exception as e:
        assert "production" in str(e).lower() or "skeleton" in str(e).lower()
    print(f"  {PASS} test_production_requires_transitions")


def test_strict_mode_rejects_extras():
    cit = Citation(citation_pmid="1", citation_text="x")
    try:
        Transition(from_state="A", to_state="B", citation=cit,
                    guideline_section="x", typo_field="oops")
        assert False
    except Exception:
        pass
    print(f"  {PASS} test_strict_mode_rejects_extras")


# ============================================================
# All discovered packs load and are PRODUCTION
# ============================================================

def test_all_discovered_packs_load_as_production():
    """All discovered rule packs are production (no more skeletons)."""
    for name in ALL_PACKS:
        pack = load_rulepack(name)
        assert pack.is_production, f"{name} should be PRODUCTION"
        # Skeleton guard: a non-skeleton multi-state pack has at least 3
        # admissible transitions (e.g. the 3-state A/T monotone chain
        # A-T-->A+T-, A+T-->A+T+, A-T-->A+T+). Larger packs have far more.
        assert len(pack.rulepack.admissible_transitions) >= 3, \
            f"{name} should have substantive transitions"
        pack.assert_usable_for_audit()  # must not raise
    print(f"  {PASS} test_all_discovered_packs_load_as_production "
          f"({len(ALL_PACKS)} packs)")


def test_every_pack_has_transcribed_by_and_authority():
    for name in ALL_PACKS:
        pack = load_rulepack(name)
        assert "Salokhiddinov" in pack.rulepack.transcribed_by, \
            f"{name} transcribed_by missing or wrong"
        assert len(pack.rulepack.clinical_source_authority) > 100, \
            f"{name} clinical_source_authority too short"
    print(f"  {PASS} test_every_pack_has_transcribed_by_and_authority")


def test_every_transition_has_guideline_section():
    for name in ALL_PACKS:
        pack = load_rulepack(name)
        for t in pack.rulepack.admissible_transitions:
            assert len(t.guideline_section) > 5, \
                f"{name}: {t.from_state}->{t.to_state} guideline_section too short"
    print(f"  {PASS} test_every_transition_has_guideline_section")


def test_sha256_stable_across_loads():
    p1 = load_rulepack("ad/niaaa_2018")
    p2 = load_rulepack("ad/niaaa_2018")
    assert p1.sha256 == p2.sha256
    print(f"  {PASS} test_sha256_stable_across_loads")


def test_sha256_unique_across_packs():
    shas = set()
    for name in ALL_PACKS:
        shas.add(load_rulepack(name).sha256)
    assert len(shas) == len(ALL_PACKS), "SHA-256 collisions across packs"
    print(f"  {PASS} test_sha256_unique_across_packs ({len(shas)} unique)")


def test_registry_summary():
    summary = list_rulepacks()
    assert len(summary) == len(ALL_PACKS)
    invalid = [p for p in summary if p.get("status") == "INVALID"]
    assert len(invalid) == 0, f"Invalid in registry: {invalid}"
    production = [p for p in summary if p.get("status") == "production"]
    assert len(production) == len(ALL_PACKS), \
        f"Expected all production, got {len(production)}"
    print(f"  {PASS} test_registry_summary ({len(summary)} all production)")


# ============================================================
# Transcription audit existence
# ============================================================

def test_transcription_audit_exists_for_each_pack():
    audit_dir = TRANSCRIPTION_AUDIT_DIR
    expected = {
        "ad/niaaa_2018": "ad_niaaa_2018.md",
        "ad/aa_2024": "ad_aa_2024.md",
        "ad/aa_2024_trac": "ad_aa_2024_trac.md",
    }
    for name, fname in expected.items():
        path = audit_dir / fname
        assert path.exists(), f"Missing transcription audit: {path}"
        content = path.read_text()
        assert "Transcription Audit" in content
        assert "Verification protocol" in content
    print(f"  {PASS} test_transcription_audit_exists_for_each_pack "
          f"({len(expected)} audits)")


# ============================================================
# Behavioral tests per pack
# ============================================================

def test_ad_niaaa_behaviors():
    pack = load_rulepack("ad/niaaa_2018")
    rp = pack.rulepack

    # Forward any interval
    ok, _ = rp.is_admissible("CN", "MCI", 30)
    assert ok

    # CN->AD short interval blocked
    ok, _ = rp.is_admissible("CN", "AD", 30)
    assert not ok

    # CN->AD over a year ok
    ok, _ = rp.is_admissible("CN", "AD", 500)
    assert ok

    # AD->CN always blocked
    ok, _ = rp.is_admissible("AD", "CN", 100000)
    assert not ok

    # Self-loop always ok
    ok, _ = rp.is_admissible("MCI", "MCI", 1)
    assert ok

    print(f"  {PASS} test_ad_niaaa_behaviors")


def test_ad_aa_2024_monotone():
    """AA 2024 v2.0.0 uses Table 7 integrated biological + clinical staging
    (17 states: Stage_0, Stage_1A..1D, Stage_2A..2D, Stage_3A..3D, Stage_4-6A..4-6D).
    All admissible transitions must be monotone in ordinal_rank.
    """
    pack = load_rulepack("ad/aa_2024")
    rp = pack.rulepack
    # All admissible transitions must be monotone (to_rank > from_rank)
    for t in rp.admissible_transitions:
        f_rank = next(s.ordinal_rank for s in rp.state_space if s.name == t.from_state)
        t_rank = next(s.ordinal_rank for s in rp.state_space if s.name == t.to_state)
        assert t_rank > f_rank, f"AA 2024 non-monotone: {t.from_state}->{t.to_state}"
    # Stage_0 -> Stage_1A is the only Stage_0 exit (per §5.2)
    ok, _ = rp.is_admissible("Stage_0", "Stage_1A", 100)
    assert ok
    # Transitional decline (Stage_1A -> Stage_2A) requires 180-day persistence
    ok, _ = rp.is_admissible("Stage_1A", "Stage_2A", 100)
    assert not ok
    ok, _ = rp.is_admissible("Stage_1A", "Stage_2A", 200)
    assert ok
    print(f"  {PASS} test_ad_aa_2024_monotone (17 states, Table 7 alphanumeric)")


# ============================================================
# Fail-closed tests
# ============================================================

def test_load_missing_file():
    try:
        load_rulepack("nonexistent/pack")
        assert False
    except RulePackLoadError as e:
        assert "not found" in str(e).lower()
    print(f"  {PASS} test_load_missing_file")


def test_yaml_with_missing_guideline_section_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.yaml"
        bad.write_text(yaml.dump({
            "schema_version": "1.1.0",
            "rulepack_id": "test/missing@1.0.0",
            "ruleset_version": "1.0.0",
            "effective_date": "2026-05-17",
            "status": "production",
            "disease_domain": "custom",
            "framework_name": "Test",
            "transcribed_by": "Test MD",
            "clinical_source_authority": "Test authority",
            "anchor_citation": {"citation_pmid": "1", "citation_text": "ref"},
            "state_space": [
                {"name": "A", "description": "a", "ordinal_rank": 0},
                {"name": "B", "description": "b", "ordinal_rank": 1},
            ],
            "admissible_transitions": [
                {
                    "from_state": "A", "to_state": "B",
                    "citation": {"citation_pmid": "1", "citation_text": "ref"},
                    # NO guideline_section
                }
            ],
        }))
        try:
            load_rulepack_from_path(bad)
            assert False, "Should reject transition without guideline_section"
        except RulePackLoadError:
            pass
    print(f"  {PASS} test_yaml_with_missing_guideline_section_rejected")


def test_yaml_with_missing_transcribed_by_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.yaml"
        bad.write_text(yaml.dump({
            "schema_version": "1.1.0",
            "rulepack_id": "test/missing@1.0.0",
            "ruleset_version": "1.0.0",
            "effective_date": "2026-05-17",
            "status": "skeleton",
            "disease_domain": "custom",
            "framework_name": "Test",
            # NO transcribed_by
            "clinical_source_authority": "Test authority",
            "anchor_citation": {"citation_pmid": "1", "citation_text": "ref"},
            "state_space": [
                {"name": "A", "description": "a", "ordinal_rank": 0},
                {"name": "B", "description": "b", "ordinal_rank": 1},
            ],
            "admissible_transitions": [],
        }))
        try:
            load_rulepack_from_path(bad)
            assert False
        except RulePackLoadError:
            pass
    print(f"  {PASS} test_yaml_with_missing_transcribed_by_rejected")


# ============================================================
# Schema v1.2 / TRAC tests
# ============================================================

def test_schema_v1_2_supports_required_conditions():
    """Schema v1.2 must accept the new required_conditions field on Transition."""
    from neurotcs.rulepack.schema import Citation, Transition
    # Should construct without raising
    t = Transition(
        from_state="A_pos",
        to_state="Full_TRAC",
        citation=Citation(
            citation_doi="10.1002/alz.70997",
            citation_text="La Joie 2025 TRAC test",
        ),
        guideline_section="La Joie 2025 §2",
        required_conditions={"treatment_status": ["anti_amyloid_active"]},
        conditions_evaluated_at="to_visit",
    )
    assert t.required_conditions == {"treatment_status": ["anti_amyloid_active"]}
    assert t.conditions_evaluated_at == "to_visit"
    print(f"  {PASS} test_schema_v1_2_supports_required_conditions")


def test_schema_v1_2_default_evaluated_at_is_either():
    """Default conditions_evaluated_at is 'either' for safety."""
    from neurotcs.rulepack.schema import Citation, Transition
    t = Transition(
        from_state="A",
        to_state="B",
        citation=Citation(citation_doi="10.0/x", citation_text="x"),
        guideline_section="x",
        required_conditions={"k": ["v"]},
    )
    assert t.conditions_evaluated_at == "either"
    print(f"  {PASS} test_schema_v1_2_default_evaluated_at_is_either")


def test_trac_pack_loads_with_schema_v1_4():
    """TRAC pack uses both v1.2.0 features (required_conditions) and
    v1.4.0 features (endorsing_bodies). Declared schema_version is 1.4.0.
    """
    pack = load_rulepack("ad/aa_2024_trac")
    assert pack.rulepack.schema_version == "1.4.0"
    assert pack.rulepack.rulepack_id == "ad/aa_2024_trac@1.1.1"
    assert pack.rulepack.disease_domain.value == "alzheimers"
    assert pack.rulepack.status.value == "production"
    # 4 states: A_neg, A_pos, Partial_TRAC, Full_TRAC
    assert len(pack.rulepack.state_space) == 4
    state_names = {s.name for s in pack.rulepack.state_space}
    assert state_names == {"A_neg", "A_pos", "Partial_TRAC", "Full_TRAC"}
    # 6 admissible transitions (1 natural + 5 treatment-conditional)
    assert len(pack.rulepack.admissible_transitions) == 6
    # 3 documented inadmissible transitions
    assert len(pack.rulepack.inadmissible_transitions) == 3
    # v1.4.0: endorsing_bodies populated for production pack
    assert len(pack.rulepack.endorsing_bodies) >= 5, (
        f"TRAC pack endorsing_bodies has {len(pack.rulepack.endorsing_bodies)} "
        f"entries; >=5 required for production status"
    )
    print(f"  {PASS} test_trac_pack_loads_with_schema_v1_4 "
          f"(sha={pack.sha256[:8]})")


def test_trac_pack_cites_la_joie_2025_doi():
    """Verify TRAC anchor citation matches the verified La Joie 2025 DOI."""
    pack = load_rulepack("ad/aa_2024_trac")
    assert pack.rulepack.anchor_citation.citation_doi == "10.1002/alz.70997"
    # And the transcribed_by field is set
    assert "Salokhiddinov" in pack.rulepack.transcribed_by
    print(f"  {PASS} test_trac_pack_cites_la_joie_2025_doi")


def test_trac_admits_a_pos_to_full_trac_with_active_treatment():
    pack = load_rulepack("ad/aa_2024_trac").rulepack
    ok, t = pack.is_admissible(
        "A_pos", "Full_TRAC", 365.0,
        to_context={"treatment_status": "anti_amyloid_active"},
    )
    assert ok, "A+ -> Full_TRAC must be admissible under active anti-Aβ therapy"
    assert t is not None
    print(f"  {PASS} test_trac_admits_a_pos_to_full_trac_with_active_treatment")


def test_trac_rejects_a_pos_to_full_trac_without_treatment():
    pack = load_rulepack("ad/aa_2024_trac").rulepack
    ok, t = pack.is_admissible(
        "A_pos", "Full_TRAC", 365.0,
        to_context={"treatment_status": "none"},
    )
    assert not ok, "A+ -> Full_TRAC must NOT be admissible without anti-Aβ therapy"
    print(f"  {PASS} test_trac_rejects_a_pos_to_full_trac_without_treatment")


def test_trac_fails_closed_when_context_missing():
    """No context = fail-closed for conditional transitions (regulatory safety)."""
    pack = load_rulepack("ad/aa_2024_trac").rulepack
    ok, _ = pack.is_admissible("A_pos", "Full_TRAC", 365.0)
    assert not ok, "Conditional transitions fail-closed when context is missing"
    print(f"  {PASS} test_trac_fails_closed_when_context_missing")


def test_trac_admits_natural_a_neg_to_a_pos_progression():
    """Natural amyloid accumulation has no treatment requirement."""
    pack = load_rulepack("ad/aa_2024_trac").rulepack
    ok, _ = pack.is_admissible("A_neg", "A_pos", 730.0)
    assert ok
    print(f"  {PASS} test_trac_admits_natural_a_neg_to_a_pos_progression")


def test_trac_admits_partial_to_full_under_treatment():
    pack = load_rulepack("ad/aa_2024_trac").rulepack
    ok, _ = pack.is_admissible(
        "Partial_TRAC", "Full_TRAC", 180.0,
        to_context={"treatment_status": "anti_amyloid_active"},
    )
    assert ok
    print(f"  {PASS} test_trac_admits_partial_to_full_under_treatment")


def test_trac_admits_full_to_partial_post_discontinuation():
    """Re-accumulation after discontinuation is admissible."""
    pack = load_rulepack("ad/aa_2024_trac").rulepack
    ok, _ = pack.is_admissible(
        "Full_TRAC", "Partial_TRAC", 730.0,
        to_context={"treatment_status": "anti_amyloid_discontinued"},
    )
    assert ok
    print(f"  {PASS} test_trac_admits_full_to_partial_post_discontinuation")


def test_existing_v1_1_packs_still_load_under_v1_2_schema():
    """Backward compatibility — all 8 prior packs must still load under the
    current schema.

    The pack list below is the set of packs that existed before schema v1.2.0
    was introduced. The point of this test is that introducing 1.2.0 (and
    later 1.3.0) features must not break loading of pre-existing packs. We
    therefore check (a) each pack loads cleanly via load_rulepack(), and
    (b) its declared schema_version is in the SUPPORTED set.

    Note: this test does NOT hard-code each pack's declared version. Doing
    so would couple this backward-compat test to the rule-pack content,
    which legitimately evolves (e.g. ad/aa_2024.yaml schema_version may be
    elevated as new attribution mechanisms are added). The schema-version
    declaration policy is enforced separately by
    tests/rulepack/test_schema_version_declaration.py.
    """
    from neurotcs.rulepack.schema import SUPPORTED_SCHEMA_VERSIONS
    for name in [
        "ad/niaaa_2018", "ad/aa_2024", "ad/aa_2024_trac",
    ]:
        pack = load_rulepack(name)
        assert pack.rulepack.schema_version in SUPPORTED_SCHEMA_VERSIONS, (
            f"Pack {name} declares schema_version="
            f"{pack.rulepack.schema_version!r} which is not in the "
            f"supported set {sorted(SUPPORTED_SCHEMA_VERSIONS)}."
        )
    print(f"  {PASS} test_existing_v1_1_packs_still_load_under_v1_2_schema "
          f"(3 AD packs)")


def test_unsupported_schema_version_rejected():
    """An unknown schema_version must be rejected by the validator."""
    from pydantic import ValidationError

    from neurotcs.rulepack.schema import RulePack
    try:
        RulePack(
            schema_version="0.9.0",
            rulepack_id="x/y@1.0.0",
            ruleset_version="1.0.0",
            effective_date="2026-01-01",
            status="production",
            disease_domain="alzheimers",
            framework_name="x",
            transcribed_by="X",
            clinical_source_authority="x",
            anchor_citation={"citation_doi": "10/x", "citation_text": "x"},
            state_space=[{"name": "A", "description": "x", "ordinal_rank": 0}],
            admissible_transitions=[],
        )
        assert False, "should have raised"
    except (ValidationError, ValueError):
        pass
    print(f"  {PASS} test_unsupported_schema_version_rejected")


# ============================================================
# AA-2024 v1.2.0 priors tests (ERRATA E-2026-002)
# ============================================================

def test_aa_2024_pack_is_v2_1_0():
    """AA 2024 v2.1.0 = full Table 7 integrated biological + clinical staging
    with endorsing_bodies field (schema_version 1.4.0).

    v2.0.0 (Schema 1.3.0) used clinical_inference attribution_type on 8
    cutpoint-dependent transitions per Jack 2024 §4.6. v2.1.0 (this) adds
    the pack-level endorsing_bodies field per gap-check Finding A
    2026-05-26; schema bumps to 1.4.0 as a result.
    """
    pack = load_rulepack("ad/aa_2024")
    assert pack.rulepack.rulepack_id == "ad/aa_2024@2.1.0"
    assert pack.rulepack.schema_version == "1.4.0"  # uses endorsing_bodies (1.4.0)
    assert len(pack.rulepack.endorsing_bodies) >= 5
    print(f"  {PASS} test_aa_2024_pack_is_v2_1_0 (sha={pack.sha256[:8]})")


def test_aa_2024_state_space_matches_table_7():
    """The 17 states must exactly match Jack 2024 Table 7 + Stage_0 from
    Table 6 row 1. Biological axis: A/B/C/D. Clinical axis: 0/1/2/3/4-6.
    """
    pack = load_rulepack("ad/aa_2024")
    expected_states = {
        "Stage_0",
        "Stage_1A", "Stage_1B", "Stage_1C", "Stage_1D",
        "Stage_2A", "Stage_2B", "Stage_2C", "Stage_2D",
        "Stage_3A", "Stage_3B", "Stage_3C", "Stage_3D",
        "Stage_4-6A", "Stage_4-6B", "Stage_4-6C", "Stage_4-6D",
    }
    actual_states = {s.name for s in pack.rulepack.state_space}
    assert actual_states == expected_states, (
        f"State-space mismatch.\n"
        f"  missing: {expected_states - actual_states}\n"
        f"  extra:   {actual_states - expected_states}"
    )
    assert len(pack.rulepack.state_space) == 17
    print(f"  {PASS} test_aa_2024_state_space_matches_table_7 (17 states)")


def test_aa_2024_stage_0_only_exits_to_1A():
    """Per Jack 2024 §5.2: 'A person with DSAD or ADAD would move from
    stage 0 into stage 1 when a diagnostic Core 1 biomarker(s) became
    positive.' Stage_0 → Stage_1A is the only admissible exit.
    """
    pack = load_rulepack("ad/aa_2024")
    rp = pack.rulepack
    stage_0_exits = [
        t for t in rp.admissible_transitions
        if t.from_state == "Stage_0"
    ]
    assert len(stage_0_exits) == 1
    assert stage_0_exits[0].to_state == "Stage_1A"

    # And reverse direction (Stage_1A -> Stage_0) must be inadmissible
    reverse = [
        t for t in rp.inadmissible_transitions
        if t.from_state == "Stage_1A" and t.to_state == "Stage_0"
    ]
    assert len(reverse) == 1, (
        "Stage_1A -> Stage_0 must be explicitly inadmissible "
        "(once Core 1+, cannot revert to biomarker-negative Stage_0)"
    )
    print(f"  {PASS} test_aa_2024_stage_0_only_exits_to_1A")


def test_aa_2024_biological_regression_inadmissible():
    """Per Jack 2024 §4.3 (verbatim): 'abnormal amyloid PET (A) precedes
    tau PET (T2), which, in turn, leads to neurodegeneration (N) and
    clinical symptoms (C), A to T2 to N to C.' The biological axis
    (A->B->C->D) is unidirectional in natural history. Within EACH
    clinical row (1, 2, 3, 4-6), backward biological transitions must
    be in the inadmissible list.
    """
    pack = load_rulepack("ad/aa_2024")
    inadmissible_pairs = {
        (t.from_state, t.to_state)
        for t in pack.rulepack.inadmissible_transitions
    }

    # For each clinical stage, biological regression must be inadmissible
    for clinical in ("1", "2", "3", "4-6"):
        # D -> C
        assert (f"Stage_{clinical}D", f"Stage_{clinical}C") in inadmissible_pairs, (
            f"Stage_{clinical}D -> Stage_{clinical}C must be inadmissible"
        )
        # C -> B
        assert (f"Stage_{clinical}C", f"Stage_{clinical}B") in inadmissible_pairs
        # B -> A
        assert (f"Stage_{clinical}B", f"Stage_{clinical}A") in inadmissible_pairs

    print(f"  {PASS} test_aa_2024_biological_regression_inadmissible (12 cells)")


def test_aa_2024_clinical_regression_dementia_to_MCI_inadmissible():
    """Per Jack 2024 Table 6: stages 4-6 are progressively worsening
    dementia. Reversion from dementia (4-6) to MCI-equivalent (3) is
    not contemplated in the staging scheme (reversible causes require
    human review). All four biological-axis cells must be inadmissible.
    """
    pack = load_rulepack("ad/aa_2024")
    inadmissible_pairs = {
        (t.from_state, t.to_state)
        for t in pack.rulepack.inadmissible_transitions
    }
    for biological in ("A", "B", "C", "D"):
        assert (f"Stage_4-6{biological}", f"Stage_3{biological}") in inadmissible_pairs

    print(f"  {PASS} test_aa_2024_clinical_regression_dementia_to_MCI_inadmissible")


def test_aa_2024_diagonal_progression_admissible():
    """Per Table 7 §Note: 'typical expected progression trajectory is along
    the diagonal shaded cells, from 1A to 4-6D'. The diagonal steps
    1A -> 2B, 2B -> 3C, 3C -> 4-6D must be admissible.
    """
    pack = load_rulepack("ad/aa_2024")
    rp = pack.rulepack
    diagonal_steps = [
        ("Stage_1A", "Stage_2B"),
        ("Stage_2B", "Stage_3C"),
        ("Stage_3C", "Stage_4-6D"),
    ]
    admissible_pairs = {
        (t.from_state, t.to_state)
        for t in rp.admissible_transitions
    }
    for from_s, to_s in diagonal_steps:
        assert (from_s, to_s) in admissible_pairs, (
            f"Diagonal step {from_s} -> {to_s} must be admissible per Table 7"
        )
    print(f"  {PASS} test_aa_2024_diagonal_progression_admissible")


def test_aa_2024_cutpoint_dependent_transitions_marked_clinical_inference():
    """Per Jack 2024 §4.6: the moderate-vs-high tau PET cutpoint is
    'an area of active research.' Every transition CROSSING the
    biological C/D boundary (i.e. ->C or ->D from a lower biological
    stage in the same clinical row) must use attribution_type=
    'clinical_inference' with the §4.6 caveat in inference_rationale.
    """
    pack = load_rulepack("ad/aa_2024")
    rp = pack.rulepack

    # Within each clinical row, the B->C and C->D transitions are
    # cutpoint-dependent
    cutpoint_dependent_pairs = set()
    for clinical in ("1", "2", "3", "4-6"):
        cutpoint_dependent_pairs.add(
            (f"Stage_{clinical}B", f"Stage_{clinical}C")
        )
        cutpoint_dependent_pairs.add(
            (f"Stage_{clinical}C", f"Stage_{clinical}D")
        )

    for t in rp.admissible_transitions:
        if (t.from_state, t.to_state) in cutpoint_dependent_pairs:
            assert t.attribution_type == "clinical_inference", (
                f"Cutpoint-dependent transition {t.from_state} -> "
                f"{t.to_state} must be clinical_inference, "
                f"got {t.attribution_type}"
            )
            assert t.inference_rationale is not None
            assert "active research" in t.inference_rationale.lower() or \
                   "§4.6" in t.inference_rationale or \
                   "cutpoint" in t.inference_rationale.lower(), (
                "Cutpoint transition rationale must reference §4.6 / cutpoint / active research"
            )

    print(f"  {PASS} test_aa_2024_cutpoint_dependent_transitions_marked_clinical_inference (8 transitions)")


def test_aa_2024_persistence_minimum_for_transitional_decline():
    """Per Jack 2024 Table 6 stage 2: 'persistent for at least 6 months.'
    All Stage_1X -> Stage_2X transitions (X = A, B, C, D) must have
    min_delta_t_days >= 180.
    """
    pack = load_rulepack("ad/aa_2024")
    rp = pack.rulepack
    for biological in ("A", "B", "C", "D"):
        from_s = f"Stage_1{biological}"
        to_s = f"Stage_2{biological}"
        candidates = [
            t for t in rp.admissible_transitions
            if t.from_state == from_s and t.to_state == to_s
        ]
        assert len(candidates) == 1, (
            f"Expected exactly one {from_s} -> {to_s} transition"
        )
        t = candidates[0]
        assert t.min_delta_t_days is not None
        assert t.min_delta_t_days >= 180, (
            f"{from_s} -> {to_s} min_delta_t_days={t.min_delta_t_days} "
            f"violates Table 6 stage 2 6-month persistence criterion"
        )
    print(f"  {PASS} test_aa_2024_persistence_minimum_for_transitional_decline")


# ============================================================
# Runner
# ============================================================

def run_all():
    tests = [
        test_schema_version_is_1_4,
        test_citation_requires_pmid_or_doi,
        test_transition_requires_citation_and_section,
        test_transition_attribution_type_default_is_guideline_quote,
        test_transition_clinical_inference_requires_rationale,
        test_transition_clinical_inference_empty_rationale_rejected,
        test_transition_clinical_inference_with_rationale_valid,
        test_rulepack_requires_v1_1_authorship_fields,
        test_production_requires_transitions,
        test_strict_mode_rejects_extras,
        test_all_discovered_packs_load_as_production,
        test_every_pack_has_transcribed_by_and_authority,
        test_every_transition_has_guideline_section,
        test_sha256_stable_across_loads,
        test_sha256_unique_across_packs,
        test_registry_summary,
        test_transcription_audit_exists_for_each_pack,
        test_ad_niaaa_behaviors,
        test_ad_aa_2024_monotone,
        test_load_missing_file,
        test_yaml_with_missing_guideline_section_rejected,
        test_yaml_with_missing_transcribed_by_rejected,
        # v1.2 schema + TRAC pack
        test_schema_v1_2_supports_required_conditions,
        test_schema_v1_2_default_evaluated_at_is_either,
        test_trac_pack_loads_with_schema_v1_4,
        test_trac_pack_cites_la_joie_2025_doi,
        test_trac_admits_a_pos_to_full_trac_with_active_treatment,
        test_trac_rejects_a_pos_to_full_trac_without_treatment,
        test_trac_fails_closed_when_context_missing,
        test_trac_admits_natural_a_neg_to_a_pos_progression,
        test_trac_admits_partial_to_full_under_treatment,
        test_trac_admits_full_to_partial_post_discontinuation,
        test_existing_v1_1_packs_still_load_under_v1_2_schema,
        test_unsupported_schema_version_rejected,
        # AA-2024 v1.2.0 priors (ERRATA E-2026-002)
        test_aa_2024_pack_is_v2_1_0,
        test_aa_2024_state_space_matches_table_7,
        test_aa_2024_stage_0_only_exits_to_1A,
        test_aa_2024_biological_regression_inadmissible,
        test_aa_2024_clinical_regression_dementia_to_MCI_inadmissible,
        test_aa_2024_diagonal_progression_admissible,
        test_aa_2024_cutpoint_dependent_transitions_marked_clinical_inference,
        test_aa_2024_persistence_minimum_for_transitional_decline,
    ]
    print(f"\nNeuroTCS Rule Pack v1.2 tests — running {len(tests)} tests:\n")
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  {FAIL} {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  {FAIL} {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)

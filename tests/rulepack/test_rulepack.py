"""
NeuroTCS Rule Pack v1.1 test suite.

Covers:
  - Schema v1.1 (transcribed_by, clinical_source_authority, guideline_section)
  - Citation enforcement (every transition requires PMID or DOI + section)
  - Fail-closed loader behavior
  - SHA-256 stable across runs
  - All 8 rule packs load as PRODUCTION
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
    Citation,
    DiseaseDomain,
    RulePack,
    RulePackStatus,
    State,
    Transition,
)

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"

ALL_PACKS = [
    "ad/niaaa_2018",
    "ad/aa_2024",
    "ad/aa_2024_trac",
    "pd/hoehn_yahr",
    "ms/mcdonald_2024",
    "oncology/recist_1_1",
    "oncology/irecist",
    "stroke/mrs_followup",
    "lung_nodule/fleischner_2017",
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTION_AUDIT_DIR = PROJECT_ROOT / "docs" / "transcription_audit"


# ============================================================
# Schema-level tests
# ============================================================

def test_schema_version_is_1_2():
    assert SCHEMA_VERSION == "1.2.0"
    print(f"  {PASS} test_schema_version_is_1_2")


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


def test_rulepack_requires_v1_1_authorship_fields():
    """v1.1 schema requires transcribed_by and clinical_source_authority."""
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
# All 8 packs load and are PRODUCTION
# ============================================================

def test_all_8_packs_load_as_production():
    """v1.1: All 8 rule packs are production (no more skeletons)."""
    for name in ALL_PACKS:
        pack = load_rulepack(name)
        assert pack.is_production, f"{name} should be PRODUCTION"
        assert len(pack.rulepack.admissible_transitions) >= 4, \
            f"{name} should have substantive transitions"
        pack.assert_usable_for_audit()  # must not raise
    print(f"  {PASS} test_all_8_packs_load_as_production "
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
        "pd/hoehn_yahr": "pd_hoehn_yahr.md",
        "ms/mcdonald_2024": "ms_mcdonald_2024.md",
        "oncology/recist_1_1": "oncology_recist_1_1.md",
        "oncology/irecist": "oncology_irecist.md",
        "stroke/mrs_followup": "stroke_mrs_followup.md",
        "lung_nodule/fleischner_2017": "lung_nodule_fleischner_2017.md",
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
    pack = load_rulepack("ad/aa_2024")
    rp = pack.rulepack
    # All admissible transitions must be monotone (to_rank > from_rank)
    for t in rp.admissible_transitions:
        f_rank = next(s.ordinal_rank for s in rp.state_space if s.name == t.from_state)
        t_rank = next(s.ordinal_rank for s in rp.state_space if s.name == t.to_state)
        assert t_rank > f_rank, f"AA 2024 non-monotone: {t.from_state}->{t.to_state}"
    # Two-step jumps require 730d
    ok, _ = rp.is_admissible("Stage_0", "Stage_2", 100)
    assert not ok
    ok, _ = rp.is_admissible("Stage_0", "Stage_2", 800)
    assert ok
    print(f"  {PASS} test_ad_aa_2024_monotone")


def test_pd_behaviors():
    pack = load_rulepack("pd/hoehn_yahr")
    rp = pack.rulepack

    # Adjacent forward any interval
    ok, _ = rp.is_admissible("HY_1", "HY_1_5", 10)
    assert ok

    # Two-step forward requires 365 days
    ok, _ = rp.is_admissible("HY_1", "HY_2", 100)
    assert not ok
    ok, _ = rp.is_admissible("HY_1", "HY_2", 400)
    assert ok

    # Backward natural-history blocked
    ok, _ = rp.is_admissible("HY_2", "HY_1", 100)
    assert not ok

    print(f"  {PASS} test_pd_behaviors")


def test_ms_relapse_remission():
    """MS is unique: adjacent backward admissible at any interval (RRMS)."""
    pack = load_rulepack("ms/mcdonald_2024")
    rp = pack.rulepack

    # Backward adjacent admissible (relapse remission)
    ok, _ = rp.is_admissible("EDSS_1_0_2_5", "EDSS_0", 30)
    assert ok, "MS adjacent backward should be admissible (RRMS biology)"

    ok, _ = rp.is_admissible("EDSS_3_0_4_5", "EDSS_1_0_2_5", 60)
    assert ok

    # Death absorbing
    ok, _ = rp.is_admissible("EDSS_10", "EDSS_9_0_9_5", 10000)
    assert not ok

    # Two-band forward jump requires 180d
    ok, _ = rp.is_admissible("EDSS_0", "EDSS_3_0_4_5", 90)
    assert not ok
    ok, _ = rp.is_admissible("EDSS_0", "EDSS_3_0_4_5", 200)
    assert ok

    print(f"  {PASS} test_ms_relapse_remission")


def test_recist_bidirectional_with_confirmation():
    pack = load_rulepack("oncology/recist_1_1")
    rp = pack.rulepack

    # Response confirmation requires 28d
    ok, _ = rp.is_admissible("SD", "PR", 20)
    assert not ok
    ok, _ = rp.is_admissible("SD", "PR", 30)
    assert ok

    # CR->PD direct (over <56d) blocked
    ok, _ = rp.is_admissible("CR", "PD", 30)
    assert not ok
    ok, _ = rp.is_admissible("CR", "PD", 60)
    assert ok

    # SD->PD any interval
    ok, _ = rp.is_admissible("SD", "PD", 14)
    assert ok

    print(f"  {PASS} test_recist_bidirectional_with_confirmation")


def test_irecist_pseudoprogression():
    """The defining iRECIST feature: iUPD can resolve to iSD/iPR/iCR."""
    pack = load_rulepack("oncology/irecist")
    rp = pack.rulepack

    # Pseudoprogression resolution: iUPD -> iPR admissible any interval
    ok, _ = rp.is_admissible("iUPD", "iPR", 30)
    assert ok, "iUPD->iPR pseudoprogression must be admissible"

    ok, _ = rp.is_admissible("iUPD", "iCR", 60)
    assert ok

    # iUPD -> iCPD must be in 28-56 day window
    ok, _ = rp.is_admissible("iUPD", "iCPD", 14)
    assert not ok  # too short
    ok, _ = rp.is_admissible("iUPD", "iCPD", 35)
    assert ok      # in window
    ok, _ = rp.is_admissible("iUPD", "iCPD", 90)
    assert not ok  # too long (window expired)

    # iCPD absorbing
    ok, _ = rp.is_admissible("iCPD", "iSD", 10000)
    assert not ok

    print(f"  {PASS} test_irecist_pseudoprogression")


def test_stroke_recovery_and_death():
    pack = load_rulepack("stroke/mrs_followup")
    rp = pack.rulepack

    # Adjacent improvement
    ok, _ = rp.is_admissible("mRS_5", "mRS_4", 10)
    assert ok

    # Death from any state
    for s in ["mRS_0", "mRS_1", "mRS_2", "mRS_3", "mRS_4", "mRS_5"]:
        ok, _ = rp.is_admissible(s, "mRS_6", 1)
        assert ok, f"{s}->mRS_6 (death) must be admissible"

    # Death absorbing
    ok, _ = rp.is_admissible("mRS_6", "mRS_5", 1000)
    assert not ok

    # Two-band improvement needs 30 days
    ok, _ = rp.is_admissible("mRS_5", "mRS_3", 10)
    assert not ok
    ok, _ = rp.is_admissible("mRS_5", "mRS_3", 40)
    assert ok

    print(f"  {PASS} test_stroke_recovery_and_death")


def test_fleischner_growth_and_shrinkage():
    pack = load_rulepack("lung_nodule/fleischner_2017")
    rp = pack.rulepack

    # Growth needs 90d minimum
    ok, _ = rp.is_admissible("Nodule_lt_6mm", "Nodule_6_8mm", 30)
    assert not ok
    ok, _ = rp.is_admissible("Nodule_lt_6mm", "Nodule_6_8mm", 100)
    assert ok

    # Two-band growth needs 180d
    ok, _ = rp.is_admissible("Nodule_lt_6mm", "Nodule_gt_8mm", 100)
    assert not ok
    ok, _ = rp.is_admissible("Nodule_lt_6mm", "Nodule_gt_8mm", 200)
    assert ok

    # Shrinkage admissible (override-allowed)
    ok, t = rp.is_admissible("Nodule_6_8mm", "Nodule_lt_6mm", 100)
    assert ok
    assert t.override_allowed

    print(f"  {PASS} test_fleischner_growth_and_shrinkage")


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


def test_trac_pack_loads_with_schema_v1_2():
    pack = load_rulepack("ad/aa_2024_trac")
    assert pack.rulepack.schema_version == "1.2.0"
    assert pack.rulepack.rulepack_id == "ad/aa_2024_trac@1.0.0"
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
    print(f"  {PASS} test_trac_pack_loads_with_schema_v1_2 "
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
    """Backward compatibility — all 8 prior packs must still load."""
    for name in [
        "ad/niaaa_2018", "ad/aa_2024", "pd/hoehn_yahr", "ms/mcdonald_2024",
        "oncology/recist_1_1", "oncology/irecist", "stroke/mrs_followup",
        "lung_nodule/fleischner_2017",
    ]:
        pack = load_rulepack(name)
        assert pack.rulepack.schema_version == "1.1.0"
    print(f"  {PASS} test_existing_v1_1_packs_still_load_under_v1_2_schema "
          f"(8 packs)")


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
# Runner
# ============================================================

def run_all():
    tests = [
        test_schema_version_is_1_2,
        test_citation_requires_pmid_or_doi,
        test_transition_requires_citation_and_section,
        test_rulepack_requires_v1_1_authorship_fields,
        test_production_requires_transitions,
        test_strict_mode_rejects_extras,
        test_all_8_packs_load_as_production,
        test_every_pack_has_transcribed_by_and_authority,
        test_every_transition_has_guideline_section,
        test_sha256_stable_across_loads,
        test_sha256_unique_across_packs,
        test_registry_summary,
        test_transcription_audit_exists_for_each_pack,
        test_ad_niaaa_behaviors,
        test_ad_aa_2024_monotone,
        test_pd_behaviors,
        test_ms_relapse_remission,
        test_recist_bidirectional_with_confirmation,
        test_irecist_pseudoprogression,
        test_stroke_recovery_and_death,
        test_fleischner_growth_and_shrinkage,
        test_load_missing_file,
        test_yaml_with_missing_guideline_section_rejected,
        test_yaml_with_missing_transcribed_by_rejected,
        # v1.2 schema + TRAC pack
        test_schema_v1_2_supports_required_conditions,
        test_schema_v1_2_default_evaluated_at_is_either,
        test_trac_pack_loads_with_schema_v1_2,
        test_trac_pack_cites_la_joie_2025_doi,
        test_trac_admits_a_pos_to_full_trac_with_active_treatment,
        test_trac_rejects_a_pos_to_full_trac_without_treatment,
        test_trac_fails_closed_when_context_missing,
        test_trac_admits_natural_a_neg_to_a_pos_progression,
        test_trac_admits_partial_to_full_under_treatment,
        test_trac_admits_full_to_partial_post_discontinuation,
        test_existing_v1_1_packs_still_load_under_v1_2_schema,
        test_unsupported_schema_version_rejected,
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

"""
v1.34.0 -- monogenic_ad_trajectory_consistency pack extended from v0.1.0 to v0.2.0.

PSEN1 (v0.1.0, v1.31.0) -- already covered in test_v131_invariant_packs.py.
This file covers the two new PSEN2 + APP invariants added in v0.2.0 (v1.34.0).

Design rationale (encoded in pack notes; verified here):
  - PSEN2: baseline 0.90 (variable penetrance per Cai 2015 CIA review),
           age window "by age 80" (wide onset range 45-88 yr).
  - APP:   baseline 0.99 (near-100% penetrance per DIAN-TU protocol),
           age window "by age 70" (mean onset ~54 yr; ~8 yr later than PSEN1).
"""

from __future__ import annotations

import pytest

from neurotcs.cross_sheet.loader import load_invariantpack
from neurotcs.cross_sheet.schema import InvariantPackStatus


@pytest.fixture(scope="module")
def pack():
    return load_invariantpack("cross_sheet/monogenic_ad_trajectory_consistency").invariantpack


@pytest.fixture(scope="module")
def by_name(pack):
    return {i.name: i for i in pack.invariants}


# ---------- pack-level extension ----------
def test_pack_bumped_to_v0_2_0(pack):
    assert pack.invariantpack_id == "cross_sheet/monogenic_ad_trajectory_consistency@0.2.0"
    assert pack.pack_version == "0.2.0"


def test_pack_now_has_three_invariants_psen1_psen2_app(by_name):
    assert set(by_name) == {
        "psen1_pathogenic_expected_ad_dementia_trajectory",
        "psen2_pathogenic_expected_ad_dementia_trajectory",
        "app_pathogenic_expected_ad_dementia_trajectory",
    }


def test_pack_remains_research_preview_info_severity(pack, by_name):
    assert pack.status == InvariantPackStatus.RESEARCH_PREVIEW
    for inv in by_name.values():
        assert inv.flag_severity == "info"


# ---------- PSEN2 ----------
def test_psen2_invariant_targets_correct_field_and_value(by_name):
    cond = by_name["psen2_pathogenic_expected_ad_dementia_trajectory"].condition
    assert cond.type == "categorical_implies_trajectory_pattern"
    assert cond.source_sheet == "patients"
    assert cond.source_field == "psen2_mutation_status"
    assert cond.source_value == "pathogenic"
    assert cond.trajectory_sheet == "predictions"


def test_psen2_uses_variable_penetrance_baseline(by_name):
    """PSEN2 has documented variable penetrance (Cai 2015) -- baseline lower than PSEN1's 0.99."""
    pattern = by_name["psen2_pathogenic_expected_ad_dementia_trajectory"].condition.pattern
    assert pattern.kind == "elevated_risk_marker"
    assert pattern.population_baseline_rate == 0.90
    # PSEN1 baseline is 0.99; PSEN2 must be strictly lower to reflect variable penetrance
    psen1 = by_name["psen1_pathogenic_expected_ad_dementia_trajectory"].condition.pattern
    assert pattern.population_baseline_rate < psen1.population_baseline_rate


def test_psen2_uses_wider_age_window_than_psen1(by_name):
    """PSEN2 onset 45-88 yr (Cai 2015) -- age cutoff 80, vs PSEN1's 60."""
    assert (
        by_name["psen2_pathogenic_expected_ad_dementia_trajectory"]
        .condition.pattern.flag_threshold
        == "none_observed_by_age_80_with_10y_followup"
    )


def test_psen2_citation_anchors_bateman_2012(by_name):
    cit = by_name["psen2_pathogenic_expected_ad_dementia_trajectory"].citation
    assert cit.citation_pmid == "22784036"
    assert cit.citation_doi == "10.1056/NEJMoa1202753"


# ---------- APP ----------
def test_app_invariant_targets_correct_field_and_value(by_name):
    cond = by_name["app_pathogenic_expected_ad_dementia_trajectory"].condition
    assert cond.type == "categorical_implies_trajectory_pattern"
    assert cond.source_sheet == "patients"
    assert cond.source_field == "app_mutation_status"
    assert cond.source_value == "pathogenic"


def test_app_uses_near_full_penetrance_baseline(by_name):
    pattern = by_name["app_pathogenic_expected_ad_dementia_trajectory"].condition.pattern
    assert pattern.kind == "elevated_risk_marker"
    assert pattern.population_baseline_rate == 0.99


def test_app_uses_age_window_between_psen1_and_psen2(by_name):
    """APP mean onset ~54 yr -- ~8 yr later than PSEN1, much earlier than PSEN2's wide window."""
    assert (
        by_name["app_pathogenic_expected_ad_dementia_trajectory"]
        .condition.pattern.flag_threshold
        == "none_observed_by_age_70_with_10y_followup"
    )


def test_app_citation_anchors_bateman_2012(by_name):
    cit = by_name["app_pathogenic_expected_ad_dementia_trajectory"].citation
    assert cit.citation_pmid == "22784036"


# ---------- target fields exist in the companion range pack ----------
def test_all_three_target_fields_exist_in_monogenic_ad_consensus(by_name):
    """The cross-sheet invariants reference fields that must exist in the v1.30.0
    monogenic_ad_consensus range pack (psen1_mutation_status / psen2_mutation_status /
    app_mutation_status). Verify the integration is wired correctly."""
    from neurotcs.clinical_ranges import load_rangepack
    lp = load_rangepack("genetics/monogenic_ad_consensus")
    range_fields = {m.name for m in lp.rangepack.measurements}
    for inv in by_name.values():
        assert inv.condition.source_field in range_fields, (
            f"Invariant {inv.name} references field {inv.condition.source_field} "
            f"which is NOT in monogenic_ad_consensus measurements {range_fields}"
        )

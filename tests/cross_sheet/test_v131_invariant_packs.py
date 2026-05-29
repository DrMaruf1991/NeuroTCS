"""
v1.31.0 Layer-3 invariant packs (3 research_preview).

- sample_type_namespace: CSF-vs-plasma Aβ42 namespace coherence (value_range_conditional)
- extended_clinical_coherence: CDR-SB threshold + CSF-p-tau217↔tau-PET discordance
- monogenic_ad_trajectory_consistency: PSEN1 expected ADAD trajectory pattern
"""

from __future__ import annotations

import pytest

from neurotcs.cross_sheet.loader import load_invariantpack
from neurotcs.cross_sheet.schema import InvariantPackStatus


# ---------- sample_type_namespace ----------
def test_sample_type_namespace_loads_research_preview():
    lp = load_invariantpack("cross_sheet/sample_type_namespace")
    assert lp.invariantpack.status == InvariantPackStatus.RESEARCH_PREVIEW
    assert len(lp.invariantpack.invariants) == 1


def test_sample_type_invariant_uses_value_range_conditional():
    lp = load_invariantpack("cross_sheet/sample_type_namespace")
    inv = lp.invariantpack.invariants[0]
    assert inv.condition.type == "value_range_conditional"
    # two cases: CSF and plasma
    case_values = {c.source_value for c in inv.condition.cases}
    assert case_values == {"CSF", "plasma"}


# ---------- extended_clinical_coherence ----------
def test_extended_coherence_loads_research_preview():
    lp = load_invariantpack("cross_sheet/extended_clinical_coherence")
    assert lp.invariantpack.status == InvariantPackStatus.RESEARCH_PREVIEW
    assert len(lp.invariantpack.invariants) == 2


def test_extended_coherence_invariant_names():
    lp = load_invariantpack("cross_sheet/extended_clinical_coherence")
    names = {i.name for i in lp.invariantpack.invariants}
    assert names == {
        "cn_state_requires_non_demented_cdr_sb",
        "elevated_csf_ptau217_with_negative_tau_pet_discordance",
    }


def test_extended_coherence_cdr_sb_threshold_is_4():
    lp = load_invariantpack("cross_sheet/extended_clinical_coherence")
    inv = next(i for i in lp.invariantpack.invariants if i.name == "cn_state_requires_non_demented_cdr_sb")
    case = inv.condition.cases[0]
    assert case.target_field == "cdr_sb_sum_boxes"
    assert case.target_range.hi == 4.0


# ---------- monogenic_ad_trajectory_consistency ----------
def test_monogenic_trajectory_loads_research_preview():
    lp = load_invariantpack("cross_sheet/monogenic_ad_trajectory_consistency")
    assert lp.invariantpack.status == InvariantPackStatus.RESEARCH_PREVIEW
    assert len(lp.invariantpack.invariants) == 1


def test_monogenic_trajectory_is_info_severity_advisory():
    lp = load_invariantpack("cross_sheet/monogenic_ad_trajectory_consistency")
    inv = lp.invariantpack.invariants[0]
    assert inv.flag_severity == "info"
    assert inv.condition.type == "categorical_implies_trajectory_pattern"
    assert inv.condition.source_field == "psen1_mutation_status"
    assert inv.condition.source_value == "pathogenic"
    assert inv.condition.pattern.kind == "elevated_risk_marker"


@pytest.mark.parametrize(
    "pack",
    [
        "cross_sheet/sample_type_namespace",
        "cross_sheet/extended_clinical_coherence",
        "cross_sheet/monogenic_ad_trajectory_consistency",
    ],
)
def test_canonical_sha256_reproducible(pack):
    lp = load_invariantpack(pack)
    assert lp.canonical_sha256 == load_invariantpack(pack).canonical_sha256

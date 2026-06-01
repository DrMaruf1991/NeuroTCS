"""Unit tests for vocabulary-match gating (Invariant B, v1.23.0)."""
from __future__ import annotations

import warnings

import pytest

from neurotcs.orchestration.vocabulary import (
    VocabularyMismatchError,
    assess_vocabulary,
    select_rulepack_or_refuse,
)

warnings.filterwarnings("ignore")


def test_clinical_vocab_covers_niaaa_pack():
    vm = assess_vocabulary(["CN", "MCI", "AD"], "ad/niaaa_2018")
    assert vm.coverage_fraction == 1.0
    assert vm.is_applicable is True
    assert vm.unmatched == ()


def test_contamination_is_reported_not_blocking():
    # core CN/MCI/AD present + contaminating tokens -> still applicable,
    # contamination reported.
    vm = assess_vocabulary(
        ["CN", "MCI", "AD", "SCD", "A+T+"], "ad/niaaa_2018")
    assert vm.coverage_fraction == 1.0
    assert vm.is_applicable is True
    assert set(vm.unmatched) == {"SCD", "A+T+"}


def test_at_tokens_do_not_cover_stage_pack():
    vm = assess_vocabulary(["A-T-", "A+T-", "A+T+"], "ad/aa_2024")
    assert vm.coverage_fraction == 0.0
    assert vm.is_applicable is False


def test_at_tokens_cover_at_pack():
    vm = assess_vocabulary(["A-T-", "A+T-", "A+T+"], "ad/at_biological")
    assert vm.coverage_fraction == 1.0
    assert vm.is_applicable is True


def test_select_refuses_when_no_pack_matches():
    with pytest.raises(VocabularyMismatchError):
        select_rulepack_or_refuse(
            ["FOO", "BAR"], candidate_packs=["ad/niaaa_2018", "ad/aa_2024"])


def test_select_picks_at_pack_for_at_tokens():
    name, vm = select_rulepack_or_refuse(
        ["A-T-", "A+T-", "A+T+"], disease_domain="alzheimers")
    assert name == "ad/at_biological"
    assert vm.coverage_fraction == 1.0


# ============================================================
# v1.41.0: additive applicability rule (b) -- full data recognition
# ============================================================

def test_v141_subset_data_against_superset_pack_is_applicable() -> None:
    """v1.41.0: a pack that is a deliberate superset of the data's
    vocabulary (contamination=0) is applicable even when coverage < 0.80.
    This handles the Jack 2018 AT(N) 8-state pack receiving typical
    5-state cohort data."""
    data = ["A+T+N+", "A+T+N-", "A+T-N+", "A+T-N-", "A-T-N-"]
    vm = assess_vocabulary(data, "ad/atn_2018")
    assert vm.coverage_fraction < 0.80     # below historical threshold
    assert vm.contamination_fraction == 0.0  # 100% data recognition
    assert vm.is_applicable                  # applicable via rule (b)


def test_v141_disjoint_vocabulary_still_refused() -> None:
    """v1.41.0 additive rule does NOT loosen disjoint-vocabulary refusal.
    Feeding A/T tokens to a Stage_* pack must still refuse (the original
    A/T-vs-Stage_* disaster guard)."""
    vm = assess_vocabulary(["A-T-", "A+T-", "A+T+"], "ad/aa_2024")
    assert vm.coverage_fraction == 0.0
    assert vm.contamination_fraction == 1.0
    assert not vm.is_applicable


def test_v141_select_prefers_zero_contamination_pack() -> None:
    """When multiple packs are applicable, prefer zero-contamination over
    high-coverage (more-specific pack wins)."""
    data = ["A+T+N+", "A+T+N-", "A+T-N+", "A+T-N-", "A-T-N-"]
    name, vm = select_rulepack_or_refuse(
        data, disease_domain="alzheimers")
    # atn_2018 has contamination=0 on this Jack 2018 data; at_biological
    # and aa_2024 would both have contamination>0 -> atn_2018 wins.
    assert name == "ad/atn_2018"
    assert vm.contamination_fraction == 0.0

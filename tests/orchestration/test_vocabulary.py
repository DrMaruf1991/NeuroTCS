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

"""Tests for mixed-dementia / differential-diagnosis cohort partitioning.

Locks the "work always" contract and the external-auditor design decisions:
  * A cohort containing recognized non-AD diagnoses (DLB/FTD/VaD/...) is NOT
    refused wholesale -- AD subjects are staged, non-AD subjects partitioned out
    and reported as out-of-AD-scope.
  * AD + comorbidity (CVD/WMH/CAA) -> staged on the AD axis with the comorbidity
    recorded as an annotation (Q2 decision).
  * Mixed-primary (AD trajectory + non-AD token) -> AD component staged,
    partial-frame; non-monotonic/reversion-type flags downgraded to REVIEW
    (informational) tier, NOT impossible (Q1 decision).
  * Contamination tokens that are NOT recognized non-AD diagnoses (a biomarker
    token in a clinical column, a typo) are STILL flagged, never hidden.
  * Pure non-AD cohort -> recognized, reported, not refused, no AD score.
"""
from __future__ import annotations

import pandas as pd

from neurotcs.orchestration.differential_registry import (
    classify_token,
    is_ad_comorbidity,
    is_non_ad_primary,
)
from neurotcs.orchestration.orchestrator import run_full_audit


def _clinical(seqs):
    rows = []
    for sid, seq in seqs.items():
        for i, (d, s) in enumerate(seq):
            rows.append({"subject_id": sid, "visit": i + 1,
                         "visit_date": d, "state": s})
    return pd.DataFrame(rows)


def _staging(res):
    for layer in res.layers:
        if layer.layer == "staging_clinical":
            return layer
    raise AssertionError("no staging_clinical layer")


class TestRegistry:

    def test_recognized_non_ad_primaries(self):
        for tok in ["DLB", "LBD", "FTD", "PPA", "vascular dementia", "PDD", "NPH"]:
            assert is_non_ad_primary(tok), tok

    def test_recognized_comorbidities(self):
        for tok in ["CVD", "WMH", "CAA", "cerebrovascular disease", "microbleeds"]:
            assert is_ad_comorbidity(tok), tok

    def test_ad_states_not_in_registry(self):
        # AD-trajectory states must NOT be claimed by the differential registry.
        for tok in ["CN", "MCI", "AD", "EMCI", "LMCI", "SMC"]:
            assert classify_token(tok) is None, tok

    def test_every_entry_has_a_citation(self):
        from neurotcs.orchestration.differential_registry import all_entries
        for e in all_entries():
            assert e.citation_pmid or e.citation_doi
            assert len(e.citation_text) > 40


class TestMixedCohortWorksAlways:

    def test_mixed_cohort_not_refused(self):
        df = _clinical({
            "AD01": [("2018-01-01", "CN"), ("2019-01-01", "MCI"), ("2020-06-01", "AD")],
            "DLB1": [("2018-01-01", "DLB"), ("2019-01-01", "DLB")],
            "FTD1": [("2018-01-01", "FTD")],
            "VAD1": [("2018-01-01", "vascular dementia")],
        })
        layer = _staging(run_full_audit({"clinical": df}, bootstrap_B=200))
        assert layer.ran is True
        assert layer.summary["staged_ad_subjects"] == 1
        oos = layer.summary["out_of_ad_scope"]
        assert oos["DLB1"] == ["DLB"]
        assert oos["FTD1"] == ["bvFTD"]
        assert oos["VAD1"] == ["VaD"]

    def test_ad_with_vascular_comorbidity_staged_and_annotated(self):
        df = _clinical({
            "CM01": [("2018-01-01", "CN"), ("2019-01-01", "MCI"), ("2019-06-01", "CVD")],
        })
        layer = _staging(run_full_audit({"clinical": df}, bootstrap_B=200))
        assert layer.ran is True
        assert layer.summary["staged_ad_subjects"] == 1
        assert layer.summary["comorbidity_annotated"]["CM01"] == ["CVD"]

    def test_mixed_primary_partial_frame_downgrades_to_review(self):
        # Same AD->CN transition is impossible for a pure-AD subject but only
        # review-tier for a mixed-primary (AD/DLB) subject.
        df = _clinical({
            "AD9": [("2018-01-01", "AD"), ("2019-06-01", "CN")],
            "MX9": [("2018-01-01", "AD"), ("2019-06-01", "CN"), ("2020-01-01", "DLB")],
        })
        layer = _staging(run_full_audit({"clinical": df}, bootstrap_B=200))
        tiers = {f["subject_id"]: f["tier"] for f in layer.flags}
        assert tiers["AD9"] == "impossible"
        assert tiers["MX9"] == "informational"
        assert layer.summary["mixed_primary_partial_frame"]["MX9"] == ["DLB"]

    def test_pure_non_ad_cohort_reported_not_refused(self):
        df = _clinical({
            "DLB1": [("2018-01-01", "DLB"), ("2019-01-01", "DLB")],
            "FTD1": [("2018-01-01", "FTD")],
        })
        layer = _staging(run_full_audit({"clinical": df}, bootstrap_B=200))
        assert layer.ran is True
        assert layer.summary["staged_ad_subjects"] == 0
        assert set(layer.summary["out_of_ad_scope"]) == {"DLB1", "FTD1"}


class TestContaminationStillFlagged:

    def test_biomarker_token_in_clinical_is_not_hidden(self):
        # 'A+T+N+' wrongly placed in a clinical column is contamination, NOT an
        # out-of-scope diagnosis -> the subject must remain staged and the bad
        # token reported as contamination (vm.unmatched), never partitioned out.
        df = _clinical({
            "AD1": [("2018-01-01", "CN"), ("2019-01-01", "MCI"), ("2020-06-01", "AD")],
            "BAD": [("2018-01-01", "CN"), ("2019-01-01", "A+T+N+")],
        })
        layer = _staging(run_full_audit({"clinical": df}, bootstrap_B=200))
        assert layer.ran is True
        # 'A+T+N+' is not a recognized non-AD diagnosis, so BAD is NOT in
        # out_of_ad_scope; it stays in the AD partition and the token is
        # surfaced as contamination.
        assert "BAD" not in layer.summary.get("out_of_ad_scope", {})
        assert "A+T+N+" in layer.summary.get("contamination_tokens", [])

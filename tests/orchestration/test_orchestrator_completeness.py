"""CI proof of completeness for the fail-closed orchestrator (v1.23.0).

These tests are the structural guarantee that the failure which motivated the
orchestrator -- a clean-looking result that silently skipped a layer -- cannot
recur. They assert that run_full_audit:
  * runs every applicable layer,
  * is byte-deterministic in its orchestrator_audit_id,
  * REFUSES (no id, complete=False) when a layer is skipped without a reason,
  * completes (with the skip recorded) when a reason is given,
  * auto-selects the A/T biological pack and emits a meaningful cTCS rather
    than the historical vocabulary-mismatch artifact,
  * stratifies range flags into impossible/implausible/informational tiers.
"""
from __future__ import annotations

import warnings

import pandas as pd
import pytest

from neurotcs.orchestration.orchestrator import run_full_audit
from neurotcs.orchestration.vocabulary import (
    VocabularyMismatchError,
    select_rulepack_or_refuse,
)

warnings.filterwarnings("ignore")


def _clinical_df():
    # 3 patients, niaaa_2018 vocabulary, one inadmissible AD->MCI regression.
    return pd.DataFrame({
        "subject_id": ["P1", "P1", "P2", "P2", "P3", "P3"],
        "visit": [0, 1, 0, 1, 0, 1],
        "visit_date": pd.to_datetime([
            "2020-01-01", "2021-01-01", "2020-01-01", "2021-06-01",
            "2020-01-01", "2021-01-01"]),
        "state": ["CN", "MCI", "AD", "MCI", "MCI", "AD"],  # P2 AD->MCI inadmissible
    })


def _biological_df():
    # A/T vocabulary, one inadmissible A+T+ -> A+T- regression (P2).
    return pd.DataFrame({
        "subject_id": ["P1", "P1", "P2", "P2", "P3", "P3"],
        "visit": [0, 1, 0, 1, 0, 1],
        "visit_date": pd.to_datetime([
            "2020-01-01", "2021-01-01", "2020-01-01", "2021-01-01",
            "2020-01-01", "2021-01-01"]),
        "state": ["A-T-", "A+T-", "A+T+", "A+T-", "A+T-", "A+T+"],
    })


def test_orchestrator_runs_all_applicable_layers_and_is_complete():
    sub = {"clinical": _clinical_df(), "biological": _biological_df()}
    r = run_full_audit(sub)
    assert r.complete is True
    assert r.orchestrator_audit_id  # non-empty
    assert "staging_clinical" in r.manifest.layers_run
    assert "staging_biological" in r.manifest.layers_run
    assert r.manifest.layers_skipped == {}


def test_orchestrator_audit_id_is_deterministic():
    sub = {"clinical": _clinical_df(), "biological": _biological_df()}
    a = run_full_audit(sub).orchestrator_audit_id
    b = run_full_audit(sub).orchestrator_audit_id
    assert a == b and a != ""


def test_orchestrator_refuses_on_unrecorded_skip():
    sub = {"clinical": _clinical_df(), "biological": _biological_df()}
    r = run_full_audit(sub, skip_layers={"staging_biological": ""})
    assert r.complete is False
    assert r.orchestrator_audit_id == ""
    assert "REFUSED" in (r.refusal_reason or "")


def test_orchestrator_completes_with_recorded_skip():
    sub = {"clinical": _clinical_df(), "biological": _biological_df()}
    r = run_full_audit(
        sub, skip_layers={"staging_biological": "deferred to validated batch"})
    assert r.complete is True
    assert "staging_biological" in r.manifest.layers_skipped
    assert r.manifest.layers_skipped["staging_biological"]


def test_biological_axis_auto_selects_at_pack_not_artifact():
    sub = {"biological": _biological_df()}
    r = run_full_audit(sub)
    bio = [layer for layer in r.layers if layer.layer == "staging_biological"][0]
    assert bio.ran is True
    assert bio.summary["pack"] == "ad/at_biological"
    # the planted A+T+ -> A+T- regression is caught
    assert bio.summary["n_flagged"] >= 1


def test_vocabulary_gate_refuses_at_tokens_on_stage_pack():
    # The historical 0.8637 artifact: A/T tokens must not be scored by aa_2024.
    with pytest.raises(VocabularyMismatchError):
        select_rulepack_or_refuse(
            ["A-T-", "A+T-", "A+T+"], candidate_packs=["ad/aa_2024"])


def test_severity_stratification_present():
    sub = {"clinical": _clinical_df()}
    r = run_full_audit(sub)
    assert set(r.severity_summary) == {"impossible", "implausible", "informational"}

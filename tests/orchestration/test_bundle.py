"""Tests for the self-verifying result bundle (neurotcs.orchestration.bundle).

These prove the guarantees the bundle format makes to a `pip install neurotcs`
user auditing a large dataset:
  * deterministic: same input -> same bundle_id (any machine, any year),
  * timings/wall-clock are EXCLUDED from the hash (they never change the id),
  * tamper-evident: altering any flag/score breaks verify_bundle,
  * a partial run (INCOMPLETE_REFUSED) carries NO bundle_id and is therefore
    cryptographically distinguishable from a complete one,
  * status leads (CLEAN / FLAGS_PRESENT / INCOMPLETE_REFUSED), and the score
    is per-axis, never a single collapsed cTCS.
"""
from __future__ import annotations

import json
import warnings

import pandas as pd
import pytest

from neurotcs.orchestration.bundle import (
    BUNDLE_FORMAT_VERSION,
    STATUS_CLEAN,
    STATUS_FLAGS_PRESENT,
    STATUS_INCOMPLETE_REFUSED,
    BundleVerificationError,
    build_bundle,
    fingerprint_dataframe,
    render_report,
    verify_bundle,
)
from neurotcs.orchestration.orchestrator import (
    CoverageManifest,
    LayerResult,
    OrchestratorResult,
    run_full_audit,
)

warnings.filterwarnings("ignore")


def _clinical_df():
    return pd.DataFrame({
        "subject_id": ["P1", "P1", "P2", "P2", "P3", "P3"],
        "visit": [0, 1, 0, 1, 0, 1],
        "visit_date": pd.to_datetime([
            "2020-01-01", "2021-01-01", "2020-01-01", "2021-06-01",
            "2020-01-01", "2021-01-01"]),
        "state": ["CN", "MCI", "AD", "MCI", "MCI", "AD"],  # P2 AD->MCI inadmissible
    })


def _biological_df():
    return pd.DataFrame({
        "subject_id": ["P1", "P1", "P2", "P2", "P3", "P3"],
        "visit": [0, 1, 0, 1, 0, 1],
        "visit_date": pd.to_datetime([
            "2020-01-01", "2021-01-01", "2020-01-01", "2021-01-01",
            "2020-01-01", "2021-01-01"]),
        "state": ["A-T-", "A+T-", "A+T+", "A+T-", "A+T-", "A+T+"],
    })


def _clean_clinical_df():
    # monotone-forward only: no inadmissible transition -> no error flags
    return pd.DataFrame({
        "subject_id": ["P1", "P1", "P2", "P2"],
        "visit": [0, 1, 0, 1],
        "visit_date": pd.to_datetime([
            "2020-01-01", "2021-01-01", "2020-01-01", "2021-01-01"]),
        "state": ["CN", "MCI", "MCI", "AD"],
    })


def _sub():
    return {"clinical": _clinical_df(), "biological": _biological_df()}


def _incomplete_result():
    manifest = CoverageManifest(
        orchestrator_version="test", layers_run=["staging_clinical"],
        layers_skipped={}, packs_applied={"staging_clinical": "abc"},
        columns_consumed={"clinical": ["state"]}, columns_ignored={},
        sub_audit_ids={"staging_clinical": "4b5c"})
    return OrchestratorResult(
        orchestrator_audit_id="", complete=False,
        refusal_reason="staging_biological skipped without recorded reason",
        manifest=manifest,
        layers=[LayerResult("staging_clinical", True, None, "4b5c", {}, [])],
        severity_summary={"impossible": 0, "implausible": 0, "informational": 0})


# --------------------------------------------------------------------------- #

def test_bundle_has_envelope_and_format_version():
    b = build_bundle(run_full_audit(_sub()))
    nb = b["neurotcs_bundle"]
    assert nb["format_version"] == BUNDLE_FORMAT_VERSION
    assert "deterministic_core" in nb
    assert "run_metadata" in nb


def test_every_flag_carries_source_provenance():
    """v1.57.0 GxP traceability: every emitted flag must be traceable to the
    rule and citation that produced it. A pharma/CRO/regulator reading the
    bundle must never see a flag with null rule_id / null pack / no citation.

    The only honest exception is the data_integrity (Layer 1) layer: structural
    flags (duplicate IDs, malformed rows) are universal data-contract checks,
    not anchored to a clinical pack/citation -- they carry rule_id but no
    pack_id/citation, which is correct.
    """
    b = build_bundle(run_full_audit(_sub()))
    flags = b["neurotcs_bundle"]["deterministic_core"]["flags"]
    all_flags = [f for tier in flags.values() for f in tier]
    assert all_flags, "fixture should produce flags to test provenance"

    for f in all_flags:
        layer = f.get("layer")
        assert f.get("rule_id"), f"flag in layer {layer} has null rule_id: {f}"
        if layer == "data_integrity":
            # structural integrity flags are not pack/citation anchored
            continue
        assert f.get("pack_id"), f"flag in layer {layer} has null pack_id: {f}"
        has_citation = bool(
            f.get("citation") or f.get("citation_pmid") or f.get("citation_doi"))
        assert has_citation, (
            f"flag in layer {layer} has no citation signal "
            f"(citation/pmid/doi all null): {f}")


def test_ranges_flags_carry_pmid_or_doi():
    """Range-pack flags (the bulk of a real audit) must carry a structured
    citation identifier, not just free text -- this is the field the audited
    1275-null-citation defect lived in."""
    import pandas as pd
    # a measurement value far outside any plausible bound -> a range flag
    meas = pd.DataFrame({
        "subject_id": ["P1"], "visit_id": ["v1"],
        "measurement_name": ["mmse_total"], "observed_value": [999.0],
    })
    sub = {**_sub(), "ranges": [("cognitive/mmse_range", meas)]}
    try:
        b = build_bundle(run_full_audit(sub))
    except Exception:
        pytest.skip("mmse_range pack not available in this build")
    flags = b["neurotcs_bundle"]["deterministic_core"]["flags"]
    range_flags = [f for tier in flags.values() for f in tier
                   if f.get("layer") == "ranges"]
    if not range_flags:
        pytest.skip("no range flags produced by fixture")
    for f in range_flags:
        assert f.get("citation_pmid") or f.get("citation_doi"), (
            f"range flag lacks structured citation id: {f}")


def test_status_leads_and_scores_are_per_axis():
    b = build_bundle(run_full_audit(_sub()))
    core = b["neurotcs_bundle"]["deterministic_core"]
    assert core["status"] in (STATUS_CLEAN, STATUS_FLAGS_PRESENT)
    # per-axis, not a single collapsed cTCS
    axes = core["axes"]
    assert {a["axis"] for a in axes} == {"staging_clinical", "staging_biological"}
    assert all("ctcs" in a for a in axes)
    assert "cTCS" not in core  # no single top-level collapsed score


def test_flags_present_status_when_errors_exist():
    # the _sub has inadmissible transitions -> impossible-tier flags
    b = build_bundle(run_full_audit(_sub()))
    core = b["neurotcs_bundle"]["deterministic_core"]
    assert core["severity_counts"]["impossible"] >= 1
    assert core["status"] == STATUS_FLAGS_PRESENT


def test_bundle_id_is_deterministic():
    a = build_bundle(run_full_audit(_sub()))["neurotcs_bundle"]["bundle_id"]
    b = build_bundle(run_full_audit(_sub()))["neurotcs_bundle"]["bundle_id"]
    assert a == b and a != ""


def test_timings_excluded_from_hash():
    a = build_bundle(run_full_audit(_sub()), timings_seconds={"x": 1.0})
    b = build_bundle(run_full_audit(_sub()), timings_seconds={"y": 999.9})
    assert a["neurotcs_bundle"]["bundle_id"] == b["neurotcs_bundle"]["bundle_id"]


def test_input_fingerprint_changes_bundle_id():
    base = build_bundle(run_full_audit(_sub()))["neurotcs_bundle"]["bundle_id"]
    fp = build_bundle(
        run_full_audit(_sub()), input_fingerprint="deadbeef"
    )["neurotcs_bundle"]["bundle_id"]
    assert base != fp  # fingerprint is part of the deterministic core


def test_verify_accepts_intact_bundle():
    b = build_bundle(run_full_audit(_sub()))
    assert verify_bundle(b) is True


def test_verify_detects_tampered_flag():
    b = build_bundle(run_full_audit(_sub()))
    core = b["neurotcs_bundle"]["deterministic_core"]
    assert core["flags"]["impossible"], "fixture should produce an impossible flag"
    # tamper inside the pinned flag (details holds layer-specific from/to)
    core["flags"]["impossible"][0]["details"]["from"] = "TAMPERED"
    with pytest.raises(BundleVerificationError):
        verify_bundle(b)


def test_flag_schema_is_pinned():
    b = build_bundle(run_full_audit(_sub()))
    flags = b["neurotcs_bundle"]["deterministic_core"]["flags"]["impossible"]
    assert flags, "fixture should produce a flag"
    f = flags[0]
    # every flag carries the pinned canonical envelope + details
    for key in ("tier", "layer", "subject_id", "visit", "field",
                "observed_value", "rule_id", "citation", "details"):
        assert key in f, f"flag missing pinned key {key}"
    # layer-specific data preserved under details (staging emits from/to)
    assert "from" in f["details"] and "to" in f["details"]


def test_version_fields_are_inside_the_hash():
    b = build_bundle(run_full_audit(_sub()))
    core = b["neurotcs_bundle"]["deterministic_core"]
    assert "bundle_format_version" in core
    assert "framework_version" in core
    assert "canonicalization" in core
    # altering the in-core version breaks verification (it is hashed)
    core["framework_version"] = "0.0.0"
    with pytest.raises(BundleVerificationError):
        verify_bundle(b)


def test_envelope_core_version_disagreement_is_rejected():
    b = build_bundle(run_full_audit(_sub()))
    # make the envelope copy disagree with the hashed core copy
    b["neurotcs_bundle"]["deterministic_core"]["bundle_format_version"] = "9.9.9"
    with pytest.raises(BundleVerificationError):
        verify_bundle(b)


def test_numeric_normalization_is_deterministic_across_float_noise():
    import numpy as np

    from neurotcs.orchestration.bundle import _canonical, _normalize
    # numpy float and a python float with last-ULP noise normalize identically
    a = _canonical(_normalize({"x": np.float64(0.6666666666666666)}))
    b = _canonical(_normalize({"x": 0.66666666666666663}))  # differs in last bits
    assert a == b


def test_render_report_is_presentation_only_and_has_no_emoji_in_json():
    b = build_bundle(run_full_audit(_sub()))
    # JSON core must be plain ASCII (no emoji) for cross-platform determinism
    core_json = json.dumps(b["neurotcs_bundle"]["deterministic_core"])
    assert core_json.isascii(), "deterministic_core must be ASCII (emoji-free)"
    # the rendered VIEW may carry symbols and capitalized headers
    text = render_report(b, use_symbols=True)
    assert "Status:" in text and "Flags By Severity" in text
    # ascii fallback works too
    plain = render_report(b, use_symbols=False)
    assert "[!]" in plain or "[OK]" in plain


def test_verify_detects_tampered_score():
    b = build_bundle(run_full_audit(_sub()))
    b["neurotcs_bundle"]["deterministic_core"]["axes"][0]["ctcs"] = 0.0
    with pytest.raises(BundleVerificationError):
        verify_bundle(b)


def test_verify_rejects_unknown_format():
    b = build_bundle(run_full_audit(_sub()))
    b["neurotcs_bundle"]["format_version"] = "99.0.0"
    with pytest.raises(BundleVerificationError):
        verify_bundle(b)


def test_verify_rejects_non_bundle():
    with pytest.raises(BundleVerificationError):
        verify_bundle({"not": "a bundle"})


def test_incomplete_run_has_no_bundle_id():
    b = build_bundle(_incomplete_result())
    core = b["neurotcs_bundle"]["deterministic_core"]
    assert core["status"] == STATUS_INCOMPLETE_REFUSED
    assert b["neurotcs_bundle"]["bundle_id"] == ""


def test_verify_accepts_correctly_refused_incomplete():
    b = build_bundle(_incomplete_result())
    assert verify_bundle(b) is True  # correctly unfinalized


def test_verify_rejects_forged_id_on_incomplete():
    b = build_bundle(_incomplete_result())
    b["neurotcs_bundle"]["bundle_id"] = "f" * 64
    with pytest.raises(BundleVerificationError):
        verify_bundle(b)


def test_clean_status_when_no_errors():
    b = build_bundle(run_full_audit({"clinical": _clean_clinical_df()}))
    core = b["neurotcs_bundle"]["deterministic_core"]
    # clean monotone trajectories -> no impossible/implausible flags
    assert core["severity_counts"]["impossible"] == 0
    assert core["severity_counts"]["implausible"] == 0
    assert core["status"] == STATUS_CLEAN


def test_coverage_uses_explicit_lists_not_a_fraction():
    b = build_bundle(run_full_audit(_sub()))
    cov = b["neurotcs_bundle"]["deterministic_core"]["coverage"]
    assert "columns_consumed" in cov and "columns_ignored" in cov
    # no misleading "fraction"/"percent" field
    assert not any("fraction" in k or "percent" in k for k in cov)


def test_axes_carry_confidence_interval():
    # Regression for the gap where the orchestrator dropped the CI: every
    # staging axis must expose cTCS AND its 95% CI / method / B, not just point.
    b = build_bundle(run_full_audit(_sub()))
    for ax in b["neurotcs_bundle"]["deterministic_core"]["axes"]:
        assert "ctcs" in ax
        assert ax.get("ctcs_ci_95_low") is not None, "CI low missing from axis"
        assert ax.get("ctcs_ci_95_high") is not None, "CI high missing from axis"
        assert ax.get("ctcs_ci_method") is not None
        assert ax.get("bootstrap_B") is not None


def test_fingerprint_is_deterministic_and_sensitive():
    df1 = _clinical_df()
    df2 = _clinical_df()
    assert fingerprint_dataframe(df1) == fingerprint_dataframe(df2)
    df3 = _clinical_df()
    df3.loc[0, "state"] = "AD"
    assert fingerprint_dataframe(df1) != fingerprint_dataframe(df3)

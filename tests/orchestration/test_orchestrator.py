

def test_unscoreable_cohort_degrades_without_keyerror():
    """A cohort where no patient yields a scored cTCS (e.g. trajectories too
    short / unscoreable) must complete the audit with ctcs=None, not raise
    KeyError('point'). Regression for the orchestrator summary builder."""
    import pandas as pd

    from neurotcs.orchestration.orchestrator import run_full_audit
    # Single-visit-per-subject: no transitions to score -> cTCS unavailable.
    clinical = pd.DataFrame({
        "subject_id": ["A", "B", "C"],
        "visit": [1, 1, 1],
        "visit_date": ["2018-01-01", "2018-01-01", "2018-01-01"],
        "state": ["CN", "MCI", "AD"],
    })
    res = run_full_audit({"clinical": clinical})
    layer = next((L for L in res.layers if L.layer == "staging_clinical"), None)
    assert layer is not None and layer.ran is True
    # ctcs is reported as None and flagged unavailable -- no crash.
    assert layer.summary.get("ctcs") is None
    assert layer.summary.get("ctcs_available") is False

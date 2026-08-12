"""VERIFICATION GATE -- the web MUST reproduce the locked CLI invariants.

For each cohort this drives the FastAPI backend (POST /api/audit/{cohort}) exactly
as the browser does, and asserts the returned result matches the locked invariant
to the SAME standard as tests/audit_core/test_real_*_audit.py:

    * cTCS within 0.0005 of the locked value, AND
    * transition count EXACTLY equal, AND
    * flagged count EXACTLY equal.

If any cohort's web result != its locked CLI result, the demo is NOT done.

Data-gated, exactly like the shipped real_* tests: a cohort whose DUA data path is
not configured on this machine is SKIPPED (not failed), because the raw data lives
only on the private server. Configure the same env vars the real_* tests use
(NEUROTCS_A4_CDR, NEUROTCS_NACC_CSV, NEUROTCS_OASIS3_CDR, NEUROTCS_ADNI_DXSUM_RDA,
NEUROTCS_MIRIAD_DIR) to enable a cohort here. On the deploy target (where all five
are configured) this gate runs green for all five.

Run:  pytest demo/test_web_parity.py -v
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from demo.app import app
from demo.config import COHORTS, CTCS_ABS_TOL, data_available


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("spec", COHORTS, ids=[c.cohort_id for c in COHORTS])
def test_web_matches_locked_invariant(client: TestClient, spec) -> None:
    """The web audit reproduces the locked cTCS/counts for ``spec`` cohort."""
    # Data-gated via the SAME canonical predicate the /api/cohorts `available`
    # field uses (config.data_available = configured AND present), so the gate and
    # the UI can never disagree. A path unset -- or set but absent on this host
    # (e.g. a .env carried over from another machine) -- is a skip, not a failure.
    if not data_available(spec):
        pytest.skip(
            f"{spec.cohort_id}: data not available on this host "
            f"(set one of {', '.join(spec.env_vars)} to an existing path). The DUA "
            f"data lives on the private server; enable there to run this gate."
        )

    resp = client.post(f"/api/audit/{spec.cohort_id}")
    assert resp.status_code == 200, (
        f"{spec.cohort_id}: audit endpoint returned {resp.status_code}: "
        f"{resp.text}"
    )
    body = resp.json()

    # --- server ran the SAME engine version whose invariants we lock against ---
    assert body["neurotcs_version"] == "1.86.0", (
        f"{spec.cohort_id}: neurotcs on server is {body['neurotcs_version']}, "
        f"but the locked invariants are for 1.86.0 -- pin the package."
    )

    ctcs = body["ctcs"]
    n_trans = body["n_transitions"]
    n_flagged = body["n_flagged"]

    assert ctcs is not None, f"{spec.cohort_id}: no cTCS returned"

    # cTCS: within framework tolerance of the locked value.
    assert abs(ctcs - spec.locked_ctcs) < CTCS_ABS_TOL, (
        f"{spec.cohort_id} cTCS drift: web returned {ctcs:.6f}, "
        f"expected {spec.locked_ctcs:.6f} (|delta| >= {CTCS_ABS_TOL})"
    )

    # transition / flagged counts: EXACT regression guard.
    assert n_trans == spec.locked_n_transitions, (
        f"{spec.cohort_id} transition count drift: web returned {n_trans}, "
        f"expected {spec.locked_n_transitions}"
    )
    assert n_flagged == spec.locked_n_flagged, (
        f"{spec.cohort_id} flagged count drift: web returned {n_flagged}, "
        f"expected {spec.locked_n_flagged}"
    )

    # the endpoint's own parity block must agree it holds.
    assert body["parity"]["parity_holds"] is True, (
        f"{spec.cohort_id}: endpoint reported parity_holds=False: {body['parity']}"
    )

    # de-identification contract: a reproducibility id must be present, and no
    # obviously subject-level field should have leaked into the payload.
    assert body["audit_id"], f"{spec.cohort_id}: missing audit_id (repro proof)"
    for leaky in ("subject_id", "patient_id", "bid", "records", "rows"):
        assert leaky not in body, (
            f"{spec.cohort_id}: payload unexpectedly contains '{leaky}' -- "
            f"the browser must receive results only, never subject-level data."
        )

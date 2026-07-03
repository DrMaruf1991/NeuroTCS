"""NeuroTCS live web demo -- FastAPI backend (NO LLM anywhere).

A thin HTTP layer over the shipped audit engine. Experts open the page, click
"Run audit", and the REAL engine audits the REAL DUA data on this private server,
returning ONLY de-identified results (cTCS, CIs, counts, cited rules, audit_id).

Endpoints:
    GET  /api/cohorts          -> the 5 cohorts + availability + locked invariants
    POST /api/audit/{cohort}   -> run the real audit, return de-identified JSON
    GET  /api/health           -> liveness + neurotcs version on this server
    GET  /                     -> single-page frontend (static/index.html)

Concurrency: audits are CPU-bound and some are long (NACC ~158k transitions), so
each audit runs in a worker thread (``run_in_threadpool``) -- one slow audit never
blocks the event loop or the rest of the UI. Per-cohort locks serialize repeat
requests for the same cohort (the engine result is deterministic; no need to run
the same audit twice concurrently).

DUA boundary: the browser receives RESULTS ONLY. Raw records and subject ids never
leave this process -- ``AuditOutcome`` carries aggregates, citations, and a hashed
audit_id, nothing subject-level.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

import neurotcs

from demo.config import (
    COHORTS,
    COHORTS_BY_ID,
    CTCS_ABS_TOL,
    resolve_data_path,
)
from demo.engine import (
    CohortDataUnavailable,
    CohortRecognitionError,
    StagingLayerMissing,
    run_cohort_audit,
)

logger = logging.getLogger("neurotcs.demo")

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="NeuroTCS Live Audit Demo",
    version=neurotcs.__version__,
    description="Reproducible, citation-locked auditor of AD cohort staging "
    "trajectories. Results only -- no raw data, no LLM.",
)

# One lock per cohort: serialize duplicate concurrent audits of the same cohort.
_locks: dict[str, asyncio.Lock] = {c.cohort_id: asyncio.Lock() for c in COHORTS}


def _cohort_public(spec) -> dict[str, object]:
    """Public, non-secret description of a cohort (path presence, not the path)."""
    data_path = resolve_data_path(spec)
    return {
        "cohort_id": spec.cohort_id,
        "display_name": spec.display_name,
        "input_hint": spec.input_hint,
        "note": spec.note,
        # availability only -- we expose WHETHER a path is configured, never the
        # path string itself (it can encode a private mount location).
        "available": bool(data_path),
        "locked": {
            "ctcs": spec.locked_ctcs,
            "n_transitions": spec.locked_n_transitions,
            "n_flagged": spec.locked_n_flagged,
            "ctcs_abs_tol": CTCS_ABS_TOL,
        },
    }


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Liveness + the neurotcs version running on this server (parity anchor)."""
    return {
        "status": "ok",
        "neurotcs_version": neurotcs.__version__,
        "cohorts": [c.cohort_id for c in COHORTS],
    }


@app.get("/api/cohorts")
async def list_cohorts() -> dict[str, object]:
    """List the 5 cohorts, their configured availability, and locked invariants."""
    return {
        "neurotcs_version": neurotcs.__version__,
        "cohorts": [_cohort_public(c) for c in COHORTS],
    }


@app.post("/api/audit/{cohort}")
async def audit_cohort(cohort: str) -> JSONResponse:
    """Run the real audit for one cohort and return de-identified results.

    Fail-closed: unknown cohort -> 404; unconfigured/missing data -> 503;
    signature mismatch -> 409. A successful audit returns the de-identified
    ``AuditOutcome`` plus a live parity check against the locked invariant.
    """
    spec = COHORTS_BY_ID.get(cohort)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"unknown cohort '{cohort}'")

    data_path = resolve_data_path(spec)
    if not data_path:
        raise HTTPException(
            status_code=503,
            detail=(
                f"cohort '{cohort}' has no data path configured on this server "
                f"(set one of {', '.join(spec.env_vars)}). The DUA data lives only "
                f"on the private server; this instance cannot audit it."
            ),
        )

    lock = _locks[cohort]
    async with lock:
        try:
            # CPU-bound + potentially long -> offload to a worker thread.
            outcome = await run_in_threadpool(run_cohort_audit, spec, data_path)
        except CohortDataUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except CohortRecognitionError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except StagingLayerMissing as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except Exception as e:  # noqa: BLE001 -- surface engine failure cleanly, no stack to client
            logger.exception("audit failed for cohort %s", cohort)
            raise HTTPException(
                status_code=500, detail=f"audit engine error: {e}"
            ) from e

    payload = outcome.to_dict()
    # Live parity check against the locked invariant -- the same standard as
    # test_web_parity.py, surfaced to the UI so an expert sees the proof inline.
    ctcs_ok = (
        outcome.ctcs is not None
        and abs(outcome.ctcs - spec.locked_ctcs) < CTCS_ABS_TOL
    )
    payload["parity"] = {
        "locked_ctcs": spec.locked_ctcs,
        "locked_n_transitions": spec.locked_n_transitions,
        "locked_n_flagged": spec.locked_n_flagged,
        "ctcs_abs_tol": CTCS_ABS_TOL,
        "ctcs_within_tol": ctcs_ok,
        "n_transitions_exact": outcome.n_transitions == spec.locked_n_transitions,
        "n_flagged_exact": outcome.n_flagged == spec.locked_n_flagged,
        "parity_holds": (
            ctcs_ok
            and outcome.n_transitions == spec.locked_n_transitions
            and outcome.n_flagged == spec.locked_n_flagged
        ),
    }
    return JSONResponse(payload)


# ---- Static single-page frontend (mounted last so /api/* wins) ----
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

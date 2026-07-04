"""Engine-reuse core for the NeuroTCS web demo -- parity by construction.

This module is a THIN wrapper. It does NOT compute cTCS, does NOT crosswalk
scales, does NOT touch the orchestrator internals. It calls the SAME shipped
functions the CLI's ``--cohort`` path calls, in the SAME order, so the web result
is identical to the CLI result by construction:

    read_tables(path)                       # neurotcs.io  -- same loader as CLI
      -> recognize_cohort(tables)           # neurotcs.cohorts -- signature match
      -> match.build_mapping(tables)        # cohort recognizer's own crosswalk
      -> tables_to_submission(tables, map)  # neurotcs.io -- same submission
      -> run_full_audit(submission,         # neurotcs.orchestration -- the engine
                        expected_layers=["staging_clinical"])
      -> result.layers[staging_clinical].summary   # ctcs, n_transitions, n_flagged

This is exactly the path proven in tests/audit_core/test_real_a4_audit.py (and the
sibling real_* invariant tests). No LLM, no measurement, no inference -- an audit
of pre-existing staging data against cited published criteria.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from demo.config import CohortSpec
from neurotcs import load_rulepack
from neurotcs.cohorts import recognize_cohort
from neurotcs.io import read_tables, tables_to_submission
from neurotcs.orchestration.orchestrator import run_full_audit

# The demo audits the clinical staging trajectory only (the invariant layer).
_EXPECTED_LAYERS = ["staging_clinical"]


class CohortDataUnavailable(RuntimeError):
    """The cohort's configured data path is missing or not set on this server."""


class CohortRecognitionError(RuntimeError):
    """The data at the configured path did not match the expected cohort signature."""


class StagingLayerMissing(RuntimeError):
    """The staging_clinical layer did not run (fail-closed: no score to report)."""


@dataclass(frozen=True)
class AuditOutcome:
    """De-identified audit result -- the ONLY thing that leaves the server.

    Every field is an aggregate or a citation/id. No raw records, no subject
    ids: ``audit_id`` is a deterministic hash (the reproducibility proof), and
    ``n_flagged`` is a count, not the flagged rows.
    """

    cohort: str
    ctcs: float | None
    ci_low: float | None
    ci_high: float | None
    ci_method: str | None
    n_transitions: int
    n_flagged: int
    flagged_rate: float
    status: str
    audit_id: str | None
    rulepack_id: str | None
    citation_pmid: str | None
    citation_doi: str | None
    neurotcs_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "cohort": self.cohort,
            "ctcs": self.ctcs,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "ci_method": self.ci_method,
            "n_transitions": self.n_transitions,
            "n_flagged": self.n_flagged,
            "flagged_rate": self.flagged_rate,
            "status": self.status,
            "audit_id": self.audit_id,
            "rulepack_id": self.rulepack_id,
            "citation_pmid": self.citation_pmid,
            "citation_doi": self.citation_doi,
            "neurotcs_version": self.neurotcs_version,
        }


def run_cohort_audit(spec: CohortSpec, data_path: str) -> AuditOutcome:
    """Audit one cohort via the shipped engine path and return de-identified results.

    Args:
        spec: the cohort registry entry (id, whether the input is a directory).
        data_path: the resolved on-disk path (a file, or a directory for MIRIAD).
            Comes from server config; never from the browser.

    Raises:
        CohortDataUnavailable: the path does not exist on this server.
        CohortRecognitionError: the data did not match ``spec.cohort_id``.
        StagingLayerMissing: the staging layer did not run.
    """
    import neurotcs

    p = Path(data_path)
    if not p.exists():
        raise CohortDataUnavailable(
            f"configured data path for '{spec.cohort_id}' does not exist: {data_path}"
        )

    # 1) SAME loader as the CLI (handles single file and MIRIAD directory alike).
    tables = read_tables(str(p), allow_pdf=False, skipped=[], decisions=[])

    # 2) Signature recognition -- confirm the data really is this cohort. This is
    #    the recognize-then-confirm contract: we only apply a cohort mapping when
    #    the caller has explicitly asked for that cohort AND the signature matches.
    match = recognize_cohort(tables)
    if match is None or match.cohort_id != spec.cohort_id:
        got = match.cohort_id if match is not None else "none"
        raise CohortRecognitionError(
            f"data at {data_path} does not match cohort '{spec.cohort_id}' "
            f"(recognizer matched: {got}). This is the same fail-closed guard the "
            f"CLI applies to --cohort."
        )

    # 3) The recognizer's OWN mapping builder (CDR/MMSE crosswalk, sentinel
    #    handling, MIRIAD 3-file join). We reuse it verbatim -- never re-implement.
    #    NOTE: for MIRIAD this mutates `tables` (consumes source sheets, adds the
    #    flattened staging sheet), exactly as the CLI relies on.
    mapping = match.build_mapping(tables)

    # 4) SAME submission the CLI builds.
    submission = tables_to_submission(tables, mapping, warnings=[])

    # 5) THE engine. Identical call to the locked-invariant tests.
    result = run_full_audit(submission, expected_layers=_EXPECTED_LAYERS)

    # 6) Read the staging layer summary (ctcs, counts) -- do not recompute.
    staging = next(
        (lyr for lyr in result.layers
         if lyr.layer == "staging_clinical" and lyr.ran),
        None,
    )
    if staging is None:
        raise StagingLayerMissing(
            f"staging_clinical layer did not run for '{spec.cohort_id}'"
        )

    summary = staging.summary
    ctcs = summary.get("ctcs")
    n_transitions = int(summary.get("n_transitions", 0))
    n_flagged = int(summary.get("n_flagged", 0))
    flagged_rate = (n_flagged / n_transitions) if n_transitions else 0.0

    # Citation + rulepack identity: reuse the loader, read the pack's anchor
    # citation (the same PMID/DOI the orchestrator attaches to every flag).
    pack_name = summary.get("pack")
    rulepack_id = citation_pmid = citation_doi = None
    if pack_name:
        try:
            lp = load_rulepack(pack_name)
            rulepack_id = lp.rulepack.rulepack_id
            citation_pmid = lp.rulepack.anchor_citation.citation_pmid
            citation_doi = lp.rulepack.anchor_citation.citation_doi
        except Exception:  # noqa: BLE001 -- citation is metadata; never fail the audit on it
            rulepack_id = pack_name

    # Overall audit status from the orchestrator (CLEAN vs flags present etc.).
    status = "FLAGS_PRESENT" if n_flagged else "CLEAN"
    if not getattr(result, "complete", True):
        status = "INCOMPLETE_REFUSED"

    return AuditOutcome(
        cohort=spec.cohort_id,
        ctcs=float(ctcs) if ctcs is not None else None,
        ci_low=summary.get("ctcs_ci_95_low"),
        ci_high=summary.get("ctcs_ci_95_high"),
        ci_method=summary.get("ctcs_ci_method"),
        n_transitions=n_transitions,
        n_flagged=n_flagged,
        flagged_rate=flagged_rate,
        status=status,
        # The per-layer audit_id IS the reproducibility proof: same input ->
        # same id, across library versions.
        audit_id=staging.audit_id,
        rulepack_id=rulepack_id,
        citation_pmid=citation_pmid,
        citation_doi=citation_doi,
        neurotcs_version=neurotcs.__version__,
    )

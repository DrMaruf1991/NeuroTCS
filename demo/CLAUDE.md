# NeuroTCS Live Web Demo — Build Brief (CLAUDE.md)

> Drop this in the repo (e.g. `demo/CLAUDE.md` or reference it from the root
> `CLAUDE.md`) so any Claude Code session has the full context persistently.

## What NeuroTCS is (get this right)

NeuroTCS is a **reproducible, citation-locked AUDITOR** of Alzheimer's-disease
cohort staging trajectories. It checks whether a cohort's disease-state
trajectories (CN -> MCI -> AD) obey published staging rules (NIA-AA 2018), and
emits a consistency score (**cTCS**) plus flagged transitions and a
byte-deterministic signed bundle.

**NeuroTCS NEVER measures, segments, or diagnoses.** It audits pre-existing
staging data against cited published criteria. Do not add measurement,
inference, or LLM logic anywhere. This demo has **no LLM layer**.

## The task

A **live web demo**: FastAPI backend + single-page HTML/JS frontend, deployed to
the existing **private, access-controlled Azure App Service**. Experts open it and
trigger real audits; the page shows the real cTCS, CIs, flags, and reproducibility
proof, computed live by the real engine on the real DUA data.

## HARD REQUIREMENT — invariant parity (non-negotiable)

The web MUST reproduce the EXACT cTCS already proven via the CLI on this machine's
real DUA data. These are locked invariants (see `tests/audit_core/test_real_*_audit.py`):

| cohort  | cTCS      | transitions | flagged | input                                   |
|---------|-----------|-------------|---------|-----------------------------------------|
| a4      | 0.996374  | 8892        | 34      | A4Learn/Raw Data/cdr.csv                |
| nacc    | 0.991502  | 158423      | 1217    | investigator_nacc73.csv                 |
| oasis3  | 0.9942    | 7248        | 30      | OASIS3_UDSb4_cdr.csv                     |
| adni    | 0.994575  | 12006       | 65      | ADNIMERGE2/data/DXSUM.rda               |
| miriad  | 0.985369  | 454         | 7       | MIRIAD dir (3 XNAT CSVs)                 |

Any web result differing from these is a BUG. The web is a thin layer over the
SAME engine and SAME data — parity must hold to tolerance 0.0005 on cTCS and
EXACTLY on the transition/flagged counts.

## Architecture — parity by construction (the world-class way)

The reason the CLI reproduces the locked loader invariants is that `--cohort`
reuses the exact engine path. The web MUST do the same — **reuse, never
reimplement**:

```
recognizer.build_mapping(tables)            # e.g. neurotcs.cohorts.<c>._build_<c>_mapping
  -> neurotcs.io.tables_to_submission(...)  # same submission the CLI builds
  -> neurotcs.orchestration.orchestrator.run_full_audit(submission, expected_layers=["staging_clinical"])
  -> read result.layers[staging_clinical].summary  # ctcs, n_transitions, n_flagged
```

For the single-table cohorts (a4/nacc/oasis3/adni): `read_tables(path)` ->
recognizer -> mapping -> submission -> `run_full_audit`.
For MIRIAD: point at the directory; the recognizer detects the 3 file roles by
header, calls `load_miriad_trajectories` WHOLE, flattens trajectories to a
submission, removes consumed source sheets (coverage-honesty), then `run_full_audit`.

Do NOT recompute cTCS by hand, do NOT copy crosswalk logic into the backend, do
NOT bypass the orchestrator. Reuse the shipped functions so parity is guaranteed,
then PROVE it with a test.

## Backend (FastAPI, no LLM)

- `GET  /api/cohorts` -> list the 5 cohorts + their configured data paths (paths
  from env/config, never hardcoded secrets).
- `POST /api/audit/{cohort}` -> run the real audit via the engine path above;
  return JSON: `{cohort, ctcs, ci_low, ci_high, n_transitions, n_flagged,
  status, audit_id, rulepack_id, citation_pmid, citation_doi}`.
- Data paths come from server config (the DUA files already live on this private
  server). NEVER send raw records to the browser — only the de-identified result
  fields above (hashed-ID flags at most).
- Long audits (NACC ~large): run async / stream progress; don't block the UI.

## Frontend (single-page HTML/CSS/JS)

- Cross-cohort cTCS chart with 95% CI whiskers (a4 highest ~0.9964, miriad lowest
  ~0.9854 — a real, explainable pattern: A4 is preclinical, MIRIAD is MMSE-staged).
- Per-cohort cards: cTCS, transitions, flagged count+rate, cited rulepack +
  PMID/DOI, audit_id (the reproducibility proof).
- "Run audit" buttons that call the backend live and update as results arrive.
- A short "why this is reproducible" panel: same input -> same audit_id, rules
  cite published criteria, IDs are hashed (de-identified).

## VERIFICATION GATE — ship only when this passes

Add `demo/test_web_parity.py`: for each cohort, call the backend endpoint and
assert the returned cTCS is within 0.0005 of the locked value AND the transition
and flagged counts match EXACTLY. Same standard as the `test_real_*_audit.py`
invariants. If any cohort's web result != CLI result, it's not done.

Also confirm against the CLI directly during dev:
`neurotcs audit <file> --cohort <c>` and the web endpoint must agree.

## DUA / compliance boundary (do not cross)

- Server is private + access-controlled -> DUA data may live on it for live audits.
- Browser receives RESULTS ONLY (cTCS, CIs, counts, hashed-ID flags, cited rules).
  Never raw cohort records, never real subject IDs.
- Commit ONLY app code + de-identified artifacts. GITIGNORE all data paths and any
  generated bundles that could contain subject-level detail. Never commit raw
  cohort files. Vet any committed bundle as de-identified first.

## Deploy

- Target: the existing private Azure App Service (NeuroTCS env). Keep access control on.
- FastAPI via the standard Azure App Service Python deploy (gunicorn/uvicorn).
- Install the `neurotcs` package (pinned to the version whose invariants you're
  matching — currently 1.86.0) in the App Service env so the engine is the exact
  shipped one. Confirm `neurotcs.__version__` on the server == the version whose
  locked cTCS you're reproducing.
- Provide the exact deploy commands and an app settings checklist (data paths,
  Python version, startup command).

## Definition of done

1. Backend reuses the shipped engine path (no reimplementation).
2. All 5 cohorts return cTCS/counts EXACTLY matching the locked invariants (proven
   by `test_web_parity.py`, green).
3. Frontend shows live results, CIs, citations, audit_ids.
4. Deployed to the private Azure App Service; `neurotcs` version on server matches.
5. No raw data in the repo or sent to the browser; data paths gitignored.
6. No LLM anywhere.

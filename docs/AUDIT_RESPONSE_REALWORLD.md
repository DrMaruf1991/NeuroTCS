# Response to the Real-World Readiness Audit (2026-06)

This document responds to the external "Exhaustive Real-World Readiness Audit"
(hostile-panel GO/NO-GO checklist) point by point. It does not dispute the
audit's NO-GO verdict *for its stated purpose* -- regulated clinical, hospital,
or pharma deployment. NeuroTCS is a **research instrument** (see
[`docs/SCOPE.md`](SCOPE.md) Regulatory status), and against a regulated-
deployment bar it is correctly NO-GO.

The purpose here is honesty about which findings are (1) already closed, (2)
correct-by-design and not defects, (3) genuinely out of scope for a research
instrument, or (4) real future work that cannot be faked. No item is dismissed;
none is fabricated. Where the audit ran against a stale `NeuroTCS.zip`, that is
noted with the current state on `main`.

## Audit-snapshot note

The audit ran against a zipped snapshot. Several of its blockers describe that
snapshot, not current `main`: it reported `pyproject 1.63.0`, `README badge
1.33.1`, and a `pyreadr` collection failure. Current `main` is later and the
test suite passes (1909 passed, 23 skipped). Items below are assessed against
current `main`.

## Classification key

- **CLOSED** -- fixed in the repository (version noted).
- **BY-DESIGN** -- correct behavior, not a defect; explained.
- **OUT-OF-SCOPE** -- a real artifact, but for regulated deployment, not for a
  research instrument; honestly declined rather than faked.
- **FUTURE-WORK** -- genuine work requiring data, clinicians, or a regulatory
  program; cannot be honestly shortcut and is not simulated.

## Item-by-item

| # | Audit blocker | Class | Disposition |
|---|---|---|---|
| 1 | No git history / tags in the zip | BY-DESIGN | A `.zip` never contains `.git`. Full history + signed tags exist in the GitHub repository. |
| 2 | Full suite fails at collection (`pyreadr`) | CLOSED (v1.67.0) | `pyreadr` made an optional `radni` extra + lazy-imported; modules and tests import without it. Suite: 1909 passed, 23 skipped. |
| 3 | No exact pass/fail/skip report | CLOSED (v1.67.0) | Suite runs clean; counts are deterministic and asserted. |
| 4 | No machine-verifiable citation ledger | FUTURE-WORK | Citation fields + guideline sections are present and structurally complete; a `rule_id -> PMID/DOI -> exact quote -> section` ledger with executed DOI/PMID resolution is a real, buildable next artifact (not yet shipped). |
| 5 | No full source-text verification per rule | FUTURE-WORK | Transcription-audit docs exist; a complete executed source-quote comparison for every rule is genuine work, partly dependent on licensed source-text access. |
| 6 | No independent KOL sign-off per pack | FUTURE-WORK | Requires recruiting independent AD/neuroimaging experts; cannot be self-certified. |
| 7 | No adjudicated sensitivity/specificity/PPV/NPV study | FUTURE-WORK | This is the deepest item. The study **design** is shipped ([`VALIDATION_PROTOCOL.md`](VALIDATION_PROTOCOL.md)) and the executable coverage harness ships (`neurotcs validate-coverage`). The adjudicated PPV result requires a cohort + blinded clinicians and is not simulated. |
| 8 | No locked pre-registered SAP | FUTURE-WORK | The SAP is specified in the protocol; an externally timestamped pre-registration (e.g. OSF) is a real next step accompanying the study. |
| 9 | Headline cTCS not reproducible from the zip | BY-DESIGN | Correct DUA governance: participant-level cohort data is gated and must not be redistributed. Reproduction path + invariants are documented in [`reproducibility/ad_neurotcs_reproducibility.md`](reproducibility/ad_neurotcs_reproducibility.md). |
| 10 | DUAs not included | BY-DESIGN | DUAs are between the data user and the data provider (ADNI/OASIS/NACC/MIRIAD); they cannot be redistributed in a tool repo. |
| 11 | Dataset dictionaries/provenance incomplete from zip | BY-DESIGN / FUTURE-WORK | Provenance for gated cohorts lives with the providers; a consolidated data dictionary for the audited fields is a reasonable future addition. |
| 12 | No intended-use / device-classification memo | OUT-OF-SCOPE | Regulatory positioning is stated in [`docs/SCOPE.md`](SCOPE.md) Regulatory status: research instrument, not a device. A device-classification memo belongs to a regulatory program, not a research tool. |
| 13 | No 21 CFR Part 11 / IQ-OQ-PQ package | OUT-OF-SCOPE | Explicitly not claimed. A fabricated compliance package would be worse than none; see SCOPE Regulatory status for what a pathway would require. |
| 14 | No HIPAA/GDPR/BAA deployment package | OUT-OF-SCOPE | NeuroTCS audits de-identified prediction outputs and does not retain PHI; a deployment-security dossier belongs to a deploying organization's environment, not the tool repo. |
| 15 | No on-prem data-flow / egress architecture | OUT-OF-SCOPE | Deployment architecture is the responsibility of the deploying site; the tool is a library/CLI, not a hosted service. |
| 16 | FHIR output is roadmap, not shipped | BY-DESIGN | Honestly labeled as roadmap in README; importing it raises ImportError by design. Not presented as shipped. |
| 17 | Validation harness is roadmap | CLOSED (v1.65.0) | The Arm B error-injection validation harness now ships (`neurotcs.validation`, `neurotcs validate-coverage`). |
| 18 | Layer 4 is design-only | BY-DESIGN | Labeled design-only in the design doc; not presented as implemented. |
| 19 | Versioning inconsistent across files | CLOSED (v1.67.0) | Single source of truth (`pyproject.toml`); README badge/prose/BibTeX, SECURITY.md, CITATION.cff unified; a drift-guard test (`tests/test_version_consistency.py`) prevents recurrence. |
| 20 | "strongest cross-cohort evidence to date" unproven | CLOSED (v1.67.0) | Reworded to an evidence-bounded within-tested-cohort statement, explicitly not a comparative claim. |
| 21 | Multi-disease/universal claims unsupported | CLOSED (v1.64.0/v1.66.0) | Repo is AD-only; all multi-disease roadmap language removed from code and docs; extracted packs are archival history only. |
| 22 | No liability/failure-mode governance | OUT-OF-SCOPE / FUTURE-WORK | A clinical-risk/user-responsibility model accompanies a deployment or regulatory program, not a research instrument; the research-use limitation is stated in SCOPE. |
| 23 | No ISO 14971 risk file | OUT-OF-SCOPE | A formal risk-management file is a regulated-device artifact; out of scope for research use, and not fabricated. |
| 24 | No vendor-neutrality / COI governance | FUTURE-WORK | A short COI/neutrality statement is a reasonable, honest next addition; the engine is model-agnostic by construction (it audits any tool's outputs against fixed rules). |

## Summary

Of the 24 items: **6 are CLOSED** in the repository (2, 3, 17, 19, 20, 21),
**6 are BY-DESIGN** and correct (1, 9, 10, 16, 18, and part of 11), **7 are
OUT-OF-SCOPE** for a research instrument and honestly declined rather than faked
(12, 13, 14, 15, 22, 23, and the deployment side of 11), and **the remainder are
genuine FUTURE-WORK** that cannot be honestly shortcut (4, 5, 6, 7, 8, 24).

The single most important real item is #7 -- the adjudicated detection-
performance study. Its design and executable apparatus are shipped; the
empirical result requires a cohort and independent clinicians and will not be
simulated. That is the honest boundary of what this repository can claim today.

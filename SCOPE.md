# NeuroTCS — Declared Audit Scope

**Version:** 1.23.0
**Last updated:** 2026-05-28

NeuroTCS is a reproducible, citation-locked auditor that verifies longitudinal
disease-state trajectories and their supporting biomarkers obey the rules of
published medical staging frameworks — and proves, cryptographically, exactly
what it checked. Its value is **not** "catches every error." Its value is
**completeness within the boundary stated here, with cryptographic proof of what
ran.** This document is that boundary, stated out loud.

## The four load-bearing properties

1. **Deterministic.** Same input → same audit_id, any machine, any year.
2. **Citation-locked.** Every flag traces to a published guideline (PMID/DOI/section).
3. **Fail-closed / complete-or-refuses.** `run_full_audit()` runs every
   applicable layer and refuses to finalize if any applicable layer was skipped
   without a recorded reason. A clean result means "checked and clean," never
   "never checked."
4. **Scope-honest.** It declares what it audits and what it does not, and reports
   per run which columns it consumed and which it ignored.

## What NeuroTCS audits (IN SCOPE)

| Layer | What it checks | Citation authority |
|---|---|---|
| Staging — clinical | Admissibility of CN/MCI/AD trajectory transitions, time-windows, reversions | NIA-AA 2018 (Jack, PMID 29653606); Salemme 2025 |
| Staging — biological | Admissibility of A/T trajectory transitions (A-T-, A+T-, A+T+), monotone-forward | AA 2024 (Jack, PMID 38934362); AT(N) PMID 27371494; cascade PMID 23332364 |
| Staging — integrated | AA 2024 17-state Stage_* integrated biological×clinical staging | AA 2024 (Jack, PMID 38934362, Table 7) |
| Ranges / biomarkers | Physiological plausibility of cognitive scales, volumetry, PET, CSF/plasma, genetics | Per-pack consensus citations |
| Cross-sheet coherence | Cross-modal concordance (amyloid status vs centiloid; p-tau217 vs PET), cognitive consistency, longitudinal monotonicity (hippocampal volume must not increase; amyloid must not spontaneously clear untreated) | `cross_sheet/ad_clinical_coherence` |
| Input contract | Structural integrity: duplicate visits, orphan records, future timestamps, **non-monotonic visit dates**, demographic plausibility bounds | Input-contract v1.2 |

The orchestrator selects the staging pack whose vocabulary matches the data and
**refuses** to emit a staging score on mismatched vocabulary (no fabricated cTCS).

## What NeuroTCS does NOT audit (OUT OF SCOPE — by design)

These are deliberately excluded because they are not temporal/staging coherence.
Absorbing them would dissolve the narrow thing NeuroTCS does well.

| Not covered | Why out of scope | Where it belongs |
|---|---|---|
| Cohort-context age plausibility (e.g. age 7 in an adult registry) | Generic data quality, not staging coherence. The input-contract bound is [0,122]; in-context eligibility is a study-specific rule. | Study eligibility / input-contract cohort-eligibility check (optional) |
| Sex / categorical-vocabulary validity (e.g. sex='X') | Pure categorical data quality. | CDISC / data-management QC, or an optional input-contract allowed-values check |
| Cognition vs **enrolled diagnosis group** coherence (e.g. perfect MMSE recorded for an EN dx_group=AD patient) | A real coherence rule, but the current cross-sheet cognitive invariant keys on `predicted_state`, not the EN `dx_group`. Recognized future rule. | Future cross-sheet invariant (NOT YET COVERED) |
| Treatment-related amyloid clearance (A+ → A- under anti-amyloid therapy) | Valid under treatment; not a natural-history error. | `ad/aa_2024_trac` (separate pack, treatment-conditional) |
| Generic epidemiology / CDISC conformance | Different tool class. | Dedicated CDISC/epi validators |
| Case-level clinical reasoning | There is no model in the audit path. That absence is the point. | Out of scope permanently |

## The defensible claim

NeuroTCS does not, and must never, claim "100% accurate on all possible errors."
The only claim that survives a regulatory review is:

> **100% completeness within this declared scope, with cryptographic proof of
> exactly what ran** — for every error class in scope there is a citation-locked
> rule and a test that proves it is caught; for everything out of scope, the
> boundary above states it plainly and names the alternative tool.

Per the project's external-audit discipline: never claim "100% true"; claim
"evidence-locked, fail-closed."

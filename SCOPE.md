# NeuroTCS — Declared Audit Scope

**Version:** 1.41.0
**Last updated:** 2026-05-29

> **One-sentence scope statement (leads every report):**
>
> NeuroTCS audits **temporal coherence** and **biomarker plausibility** against
> published, citation-locked staging rules. It runs **data-integrity** checks
> alongside, and explicitly reports any column it does **not** audit. For
> demographic validation, protocol-compliance checks, and data-dictionary
> conformance, use a complementary data-quality tool.

## The four layers any audit run touches

Every dataset audit a user runs traverses four genuine layers. NeuroTCS **owns**
two-and-a-half, **runs** the third alongside, and **acknowledges but does not
absorb** the fourth.

| # | Layer | NeuroTCS does what | Why |
|---|---|---|---|
| 1 | **Data integrity** — duplicate (subject,visit) records, orphan records (referential integrity), intra-subject temporal cadence breaks, broken visit ordering, APOE genotype validity (alleles ⊆ {e2,e3,e4}; diploid), categorical-domain validity (sex/handedness), hard patient-level bounds (education, age), anti-amyloid protocol eligibility | **Runs (v1.42.0)** under the `data_integrity` label as a universal, deterministic, fail-closed Layer-1 check over all raw sheets; biological constraints are citation-locked, pure integrity axioms cite the rule itself | Pre-condition for every downstream layer; these are hard, universally-true facts (an allele that does not exist; a non-existent sex code; a negative count), not domain opinions |
| 2 | **Value plausibility** — biomarker / cognitive-score range bounds; `bound_semantic` separates diagnostic-threshold bounds (informational) from physiological-envelope bounds (implausible) | **Owns**, citation-locked at `international_consensus` or stricter (physiological-envelope bounds may be honestly `derived`) | Adjacent to staging; safe only with verbatim cited thresholds |
| 3 | **Temporal coherence & staging admissibility** — trajectory admissibility, time-window constraints | **Owns**, citation-locked, **never expanded or diluted** | The regulator-defensible heart of NeuroTCS |
| 3b | **Cross-sheet coherence (v1.42.0 live in zero-config)** — cross-modal concordance, within-instrument consistency, longitudinal monotonicity | **Owns**, citation-locked; auto-wired by the universal role resolver; only production invariant packs run by default | Catches contradictions BETWEEN values that no single-value layer can see |
| 4 | **Genuinely out-of-scope domain concerns** — adverse-event-action logic, free-text/narrative columns, data-dictionary conformance beyond structural integrity, site-specific protocol logic | **Acknowledged by name in the report**; **never absorbed**; complementary-tool suggested | Absorbing open-ended domain logic dissolves the regulatory trust the tool is built on |

> **v1.42.0 scope note.** Layers 1 and 3b were present in the codebase but
> never reached in zero-config before v1.42.0 (a circular completeness hole:
> a layer was "applicable" only if its submission key was pre-populated, and
> nothing populated them). They now run universally, and a structural
> completeness guard (`expected_layers`) refuses on any silent wiring omission.
> Patient-level hard facts (sex domain, APOE validity, education/age bounds,
> anti-amyloid eligibility) moved from "out-of-scope domain concern" to the
> in-scope Layer-1 integrity check, because each is a single, citable,
> universally-true constraint — not open-ended domain logic.

## What the user sees per run

For every column in the input the report says exactly one of:
- **audited and clean** — wired into a pack, no flags
- **audited and flagged** — wired into a pack, flag(s) emitted (with tier + citation)
- **demoted to informational** — wired, but below `impossible`/`implausible` threshold
- **refused** — recognized but not wired, with the explicit reason
  (e.g. "assay/scale-calibrated biomarker; pass `--confirm-assays` to assert
  the data matches the pack's assay")
- **out of scope** — not in NeuroTCS's domain; complementary tool suggested

Nothing is silent. The user is never surprised later. That is what
"glad always" means in practice — completeness of communication, not
omniscience.

## What this position deliberately rejects

- **"Make it universal in scope."** The same trap as "claim 100% accuracy."
  Both promises collapse on contact with a serious user. A truly universal
  validator cannot be citation-locked because it would have to invent rules
  for territory no guideline covers.
- **Imitating a generic data-QC linter's flag taxonomy.** That flag list is not
  deterministic, not citation-locked, not reproducible — the very properties
  NeuroTCS exists to provide.
- **Silently absorbing out-of-scope columns** so the report "looks complete."
  This is a worse failure than refusing, because the user thinks they were
  audited and they weren't.

## Specific in-scope vs out-of-scope examples

**In scope** (NeuroTCS owns or runs):
- Range bounds on MMSE, MoCA, CDR, CDR-SB, ADAS-Cog, NPI-Q, Braak stage
  (safe ordinal / categorical scales — scale-invariant, no assay assertion needed)
- Range bounds on CSF Aβ42/40 ratio, plasma p-tau217, NfL, centiloid, FDG SUVR,
  cortical thickness, eTIV, WMH (assay-calibrated — `--confirm-assays`-gated)
- Clinical staging admissibility (CN ↔ MCI ↔ AD transitions per cited rule packs)
- **Biological staging admissibility — Jack 2024 integrated taxonomy** (Stage_0,
  Stage_1A through Stage_4-6D; covered by `ad/aa_2024@2.1.0`)
- **Biological staging admissibility — Jack 2018 AT(N) taxonomy** (8 states
  including all common AD-continuum profiles and the Jack 2024 §3 inadmissible
  A-T+ profiles; covered by `ad/atn_2018@1.0.0` as of v1.41.0). Closes the
  vocabulary_mismatch on ADNI-era and NACC-era staging exports. Jack 2024 §3
  inadmissibility of A-T+ profiles is **actively enforced at the staging-
  transition layer** (zero admissible transitions reference A-T+ states, so
  any trajectory entering or leaving them flags inadmissible_state with full
  citation context in the audit trail — not silently absorbed or refused).
- Cross-sheet concordance (amyloid status vs CSF ratio vs PET centiloid)
- Longitudinal monotonicity of biomarkers that have a published directional
  expectation
- Time-window admissibility of staging transitions (when real visit dates are
  available)

**Out of scope** (acknowledged in report; NeuroTCS does not audit):
- Demographic validity (sex vocabulary, age out-of-range for cohort, education
  years out-of-range) — use a data-dictionary validator
- Protocol-eligibility violations — use a trial-management QC tool
- Treatment-assignment validation — use a trial-management QC tool
- Adverse-event-action logic — use a pharmacovigilance/safety system
- Data-dictionary conformance (CDISC SDTM compliance, ADaM derivations) — use
  a clinical-data validator
- Free-text or operator-comment columns (no published rule to validate against)

---

## Original declared scope (preserved below for reference)

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

# NeuroTCS Criteria-Currency Review Policy

Document ID: NTCS-RM-003
Status: ACTIVE (process control)
Closes: HAZARD_ANALYSIS.md hazard H9 (clinical-criteria drift) / gap G4
Related: NTCS-RM-001 (hazard analysis), NTCS-RM-002 (IEC 62304 traceability)

## 1. Purpose

NeuroTCS audits longitudinal staging data against rule packs that each
transcribe a specific, dated edition of a published clinical-staging guideline.
Guidelines are revised over time (e.g. NIA-AA 2018 -> AA 2024). If a pack
continues to be used after the guideline edition it transcribes has been
superseded, the audit may produce systematically outdated flags against
criteria no longer reflecting current clinical knowledge (hazard H9; harm S3,
erroneous research conclusion).

The existing controls reduce but do not eliminate this risk: packs are
versioned, citation-locked to a named edition via `guideline_section`, multiple
editions coexist (2018 and 2024 packs ship side by side), and the citation
verifier resolves each cited source. The residual gap, recorded as G4, is that
**detecting that a guideline has been superseded is a manual process**. This
policy is the documented periodic criteria-review cadence the hazard analysis
recommends as the control for that gap.

## 2. Honest scope of what this policy can and cannot do

This policy establishes a *human* review process, assisted by an automated
*surfacing* aid. The distinction is deliberate and load-bearing:

- An automated check **cannot** determine whether a clinical guideline has been
  medically superseded. That judgement requires a qualified clinician reading
  the current literature and the relevant specialty-society publications. Any
  claim that the tool auto-detects superseded guidelines would overstate its
  capability.
- An automated check **can** surface which packs are due for review (by age of
  `effective_date` against a fixed interval), so no pack silently ages past its
  review window unnoticed.

Therefore: **automation surfaces; a qualified human judges.** The optional
`effective_date` age check (Section 6) flags packs as "due for review"; it never
asserts a pack is current or stale on clinical grounds.

## 3. Scope of packs covered

All production AD rule packs under `src/neurotcs/rulepack/rules/ad/`. Each pack
carries the two fields this policy tracks:

| Field | Role in this policy |
|-------|--------------------|
| `framework_name` | Names the guideline edition the pack transcribes; the object of the currency review. |
| `effective_date` | Date the pack edition was transcribed/last reviewed; drives the review-due interval. |
| `clinical_source_authority` | The dated primary source the reviewer re-checks for a newer edition. |
| `anchor_citation` (PMID/DOI) | The resolvable source the citation verifier confirms still resolves. |

As of this policy's adoption the covered packs and their transcribed frameworks
are (illustrative, not a frozen list -- the authoritative list is whatever ships
under `rules/ad/`):

- NIA-AA 2018 Research Framework (clinical staging CN/MCI/AD)
- AA 2024 Revised Criteria (integrated biological + clinical staging)
- AA 2024 TRAC (treatment-related amyloid clearance)
- AT(N) 2018 biomarker profile
- A/T biological staging (AA 2024)
- ADNI clinical-stage staging
- NIA-AA 2024 biological letter staging (A/B/C/D)
- NIA-AA 2024 numeric clinical staging (stages 0-6)

## 4. Review cadence

**Scheduled review: every 12 months** from each pack's `effective_date`.

Rationale for a 12-month interval: major neurodegenerative-staging guidelines
(NIA-AA, AA) are revised on multi-year cycles, not continuously; a 12-month
cadence reliably catches a revision within a year of publication without
imposing review churn disproportionate to the rate of real change. The interval
is a maximum, not a target -- event-triggered review (below) takes precedence.

**Event-triggered review (overrides the schedule):** a review is initiated
promptly, regardless of the 12-month clock, when any of the following occurs:

- A specialty society (Alzheimer's Association, NIA, IWG) or a regulatory body
  publishes a new edition or formal revision of a staging framework a pack
  transcribes.
- The citation verifier reports that a pack's anchor source no longer resolves,
  or resolves to a retracted/corrected record.
- A peer reviewer, user, or co-author raises a substantive question about a
  pack's currency.

## 5. Review procedure (per pack)

For each pack due for review:

1. **Identify the current edition.** Confirm, from the primary source named in
   `clinical_source_authority`, whether the transcribed edition
   (`framework_name`) is still the current one for that staging system.
2. **If still current:** update `effective_date` to the review date (recording
   that a review occurred and found no change), with a CHANGELOG note. No
   scientific content changes; the pack SHA and any cohort audit_ids are
   therefore unchanged (only `effective_date`, a metadata field excluded from
   the canonical SHA, moves -- see `loader.py` canonical-serialization scope).
3. **If superseded:** the pack is **not** silently edited to the new edition.
   Per the immutable-history policy (SCOPE.md), the existing pack is preserved
   as the transcription of its (now historical) edition, and a **new pack** for
   the current edition is added -- exactly as the 2018 and 2024 packs already
   coexist. The superseded pack is marked per Section 5a so users are not
   unknowingly auditing against an outdated edition.

### 5a. Superseded-disclosure mechanism

A pack whose transcribed edition has been superseded by a newer one is disclosed
as such, not removed (removal would break reproducibility of prior audits and
violate the immutable-history policy). Disclosure is by:

- A `superseded_by:` note in the pack naming the current-edition pack, and/or
- A deprecation entry in CHANGELOG/ERRATA and the pack registry,

so that an operator selecting the pack, and any audit bundle citing it, makes
the edition status visible. The auditor continues to run the pack on request
(prior audits remain reproducible) but the superseded status is surfaced.

## 6. Optional automated aid: review-due surfacing

A lightweight check MAY be run in CI or on demand that, for each pack, computes
the age of `effective_date` against the 12-month interval and lists any pack
whose review window has elapsed. Its sole output is "this pack is due for
review" -- a scheduling prompt for the human reviewer. It makes no clinical
judgement about currency and never blocks an audit. This keeps the surfacing
function honest: it guarantees no pack ages past its window unnoticed, without
ever claiming the tool can judge medical currency.

## 7. Responsibility

- The board-certified physician named in each pack's `transcribed_by` field is
  responsible for the clinical currency judgement in Section 5.
- A documented reviewer (which may be the same physician or an additive
  specialist per the `reviewers` field) records the review outcome.
- The review outcome (date, current/superseded finding, actions) is recorded in
  CHANGELOG so the review history is auditable.

## 8. Relationship to the residual risk

This policy reduces H9 from "no automated currency check; superseded-guideline
detection is unmanaged manual maintenance" to "scheduled + event-triggered human
review with automated review-due surfacing, and a disclosure mechanism for
superseded editions." It does not eliminate the residual risk -- a guideline
could be superseded between scheduled reviews and before an event trigger fires
-- and it does not, and cannot, claim automated clinical-currency judgement. The
residual risk remains ALARP, now managed by a documented process rather than
unmanaged manual maintenance.

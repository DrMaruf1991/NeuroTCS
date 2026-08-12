# Response to external expert review (2026-08)

**Review received:** 2026-08 (external neurology reviewer)
**Response version:** NeuroTCS v1.86.0 · ERRATA E-2026-011
**Format:** point-by-point — reviewer's point → what was found in the code →
action taken → evidence (file / test).

---

## Point 1 — "I'm not sure I would describe all of these transitions as clinically impossible. MCI to CN can definitely occur clinically."

**Finding.** Partially a misreading, but a diagnostic one. MCI→CN has been
an **admissible** transition in `ad/niaaa_2018` throughout (≥180-day
minimum interval, Salemme 2025 reversion priors 8.7% clinical / 28.2%
population; `src/neurotcs/rulepack/rules/ad/niaaa_2018.yaml`, MCI→CN
entry). It has never been flagged as an error. That a knowledgeable
reviewer assumed otherwise means the outputs did not communicate what a
flag means.

**Action.** Flag semantics now stated on every human-facing surface from a
single source of truth (`neurotcs.report.FLAG_SEMANTICS_STATEMENT`): CLI
summary, PDF report, SVG summary, demo landing page and guide. Machine
formats keep their stable severity tokens; the tier names
(`impossible`/`implausible`/`informational`) are documented as
machine-schema tokens, not clinical verdicts.

**Evidence.** `tests/report/test_flag_semantics.py` (reproduced failing on
all surfaces before the fix; passing after).

---

## Point 2 — "Even some apparent improvement from AD/dementia to MCI could reflect diagnostic reclassification rather than a true data-integrity problem."

**Finding.** Correct, and accepted in full. The AD→MCI inadmissible entry's
*reason* text was defensible, but the entry carried citation authority as
if Jack 2018 stated the prohibition. Root cause was structural:
`InadmissibleTransition` had no way to declare "clinical inference, not
verbatim transcription" (the fields existed only on admissible
`Transition`, schema v1.3.0).

**Action.**
1. Schema v1.5.0 adds `attribution_type` + `inference_rationale` to
   `InadmissibleTransition` with a fail-closed validator
   (`src/neurotcs/rulepack/schema.py`).
2. 22 inadmissible entries re-attributed as `clinical_inference` across
   `ad/niaaa_2018@1.4.0`, `ad/adni_clinical_stage@1.0.1`,
   `ad/niaaa_2024_clinical_numeric@1.0.1`. Every rationale names diagnostic
   reclassification, resolved delirium/depression, medication effects, and
   label-mapping artifacts as documented benign causes, and states that a
   flag requires adjudication.
3. Entries with verbatim structural source claims remain `guideline_quote`
   (`ad/aa_2024` §4.3 unidirectional sequence; `ad/aa_2024_trac` quoted La
   Joie 2025; `ad/at_biological` cascade monotonicity) — the full
   per-entry audit table is in ERRATA E-2026-011 §"What changed".
4. **Zero audit_id drift**: the new fields are provenance, excluded from
   the canonical scientific SHA; all three packs' SHAs verified
   byte-identical pre/post.

**Evidence.** `tests/rulepack/test_inadmissible_attribution.py` (6 tests
reproduced failing before the fix), `ERRATA.md` E-2026-011,
`docs/transcription_audit/ad_niaaa_2018.md`.

---

## Point 3 — "The 2018 NIA-AA framework by itself doesn't establish a one-way CN to MCI to AD state-transition model."

**Finding.** Correct. The rule pack never encoded a fully one-way model
(CN→MCI, MCI→AD, CN→AD, and MCI→CN are all admissible), but the two
AD-reversion prohibitions over-attributed their authority to Jack 2018.

**Action.** Same structural fix as Point 2; the `inference_rationale` on
both entries now states explicitly: "Jack 2018 describes the AD continuum
and syndromal staging but does NOT state a one-way CN->MCI->AD transition
model."

---

## Point 4 — "Take a representative sample of the flagged transitions from each dataset and manually review them… estimate how often a flag actually represents a real problem."

**Finding.** The study design already existed
(`docs/VALIDATION_PROTOCOL.md`: PPV against blinded expert gold standard;
false-positive decomposition into rare-biology vs encoding-limitation;
Wilson CIs; κ) but had no execution tooling and no results. It remains
honestly labeled **not executed**.

**Action.** Shipped the Arm A sampler:
`scripts/sample_flags_for_adjudication.py` — severity-stratified
(largest-remainder proportional allocation), seeded and byte-deterministic,
producing a **blinded** reviewer worksheet (no severity, no rule identity,
no flag status; flagged and unflagged interleaved; record ids assigned
after the shuffle) plus a separate coordinator-only unblinding key and a
reproducible manifest. Sample sizes come from the protocol §7 precision
table (e.g. n≈165 flagged for PPV 0.70 ± 0.07).

**Evidence.** `tests/scripts/test_sample_flags_for_adjudication.py`
(blinding, stratification, determinism, fail-closed behavior).

**What remains (data-holder + reviewers):** run the audit on each cohort
with `--csv`, run the sampler, recruit ≥3 blinded adjudicators per protocol
§5, and analyze per the SAP. The software gap is closed; the evidence gap
requires the human study.

---

## Point 5 — "Deliberately introduce known errors into otherwise valid longitudinal data and see how reliably the system detects them."

**Finding.** A fully synthetic benchmark existed
(`benchmark/generate_benchmark.py`) but nothing could corrupt *real* data
under its true noise structure.

**Action.** Shipped `scripts/inject_known_errors.py`: deterministic seeded
injection of dementia-reversion errors into any contract-conformant
longitudinal CSV, with a complete answer key (subject, row, column,
original, injected, error type) and a byte-reproducible manifest (input +
output SHA-256, no wall-clock values). Acceptance test proves the loop end
to end: a clean cohort audits clean, then 4/4 injected errors are detected
with **zero false positives** on untouched subjects.

**Evidence.** `tests/scripts/test_inject_known_errors.py`. Honest
limitation (per protocol §6): for error types that map directly onto an
encoded rule, detection approaches 1.0 by construction — the injector
measures *coverage*, never substitutes for Arm A's PPV.

---

## Point 6 — "Documenting the mapping for each dataset… may end up being a really important part of the work."

**Finding.** Agreed; mapping rationale was scattered across adapter code
and the datasheet.

**Action.** New `docs/mappings/` — one page per cohort (ADNI, NACC,
OASIS-3, MIRIAD) derived line-by-line from the shipped adapters: exact
source variables, mapping tables/thresholds, exclusions, visit ordering,
and a closing **"Mapping-artifact risks"** section listing the concrete
mechanisms an adjudicator must check before labeling a flag DATA_ERROR
(e.g. NACC consensus reclassification for AD→MCI flags; MMSE ±1-point
threshold crossings in MIRIAD; CDR 1→0.5 boundary reclassification in
OASIS-3; ADNI release-skew).

**Evidence.** `tests/docs/test_mapping_docs.py` pins each doc to the
adapter's real source variables so documentation cannot silently drift
from code.

---

## Point 7 — "Separate the deterministic/reproducibility piece from clinical validity."

**Finding.** Agreed; the separation existed in `VALIDATION_PROTOCOL.md` but
the README's hallmark framing did not carry it.

**Action.** New README "Validation status — what is established vs.
pending" section: reproducibility (established) ≠ rule correctness ≠ flag
precision (pending, protocol not yet executed). The `ad/niaaa_2018` pack
note no longer claims its 65 ADNI flags are "all clinically interpretable"
(unadjudicated).

---

## Point 8 — "Spend less time on the commercialization/regulatory/TAM side."

**Action.** Accepted. This release contains no commercialization material;
all effort went to attribution honesty, validation tooling, and mapping
documentation. No marketing claims were added anywhere in this release.

---

## Verification summary (v1.86.0)

- Every fix was reproduced as a failing test before the change and passes
  after (reproduce → root-cause → fix → verify discipline).
- Full suite green; all new tests listed above.
- Canonical scientific SHAs byte-identical for all three corrected packs →
  **every locked cohort audit_id remains valid without re-derivation**.
  Data-holders can confirm on their own machines:
  `pytest tests/audit_core/test_real_nacc_audit.py tests/audit_core/test_real_miriad_audit.py -q`
  (with `NEUROTCS_NACC_CSV` / `NEUROTCS_MIRIAD_DIR` set).

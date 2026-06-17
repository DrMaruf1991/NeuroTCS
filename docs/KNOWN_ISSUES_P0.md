# Known Issues -- P0 (production blockers, tracked)

This file records confirmed P0 defects with root cause traced from source, a
designed fix, and the honest blast radius -- so the fix is a scoped, ready task,
not a rediscovery. Nothing here is faked: where a fix needs governed data that
is not currently available, that dependency is stated rather than worked around.

---

## P0-1: autowired source columns are mislabeled as `columns_ignored`

**Status:** FIXED in v1.81.0. The fix is contained -- it corrects the CLI
coverage ledger only; the five locked invariants are UNAFFECTED (their
audit_id is scores-only, not coverage-derived), verified by all 7
real-cohort invariant tests passing unchanged post-fix. No re-lock was
needed. See CHANGELOG [1.81.0].

### Reproduction (v1.80.0)

A wide CSV with `clinical_stage`, `mmse_total`, `cdr_sb`, audited zero-config:

```
# auto-wired range packs (values audited; each decision shown):
  p0test -> cognitive_scales/cdr_mmse_moca_consensus: mmse_total=mmse_total, cdr_sb=cdr_sb_sum_boxes
```

The coverage ledger then reports:

```
columns_consumed : {'__autowired__p0test__...': ['measurement_name', 'visit_id'],
                    'p0test': ['clinical_stage', 'subject_id', 'visit', 'visit_date']}
columns_ignored  : {'p0test': ['cdr_sb', 'mmse_total']}    <-- DEFECT
```

`mmse_total` and `cdr_sb` were AUDITED via autowiring, yet appear under
`columns_ignored`. A reviewer reading the bundle would wrongly conclude the
clinically central columns (MMSE, CDR-SB, and by extension amyloid, p-tau217,
hippocampal volume, Fazekas in larger files) were not audited. This is a
production-trust defect: the audit is correct, but the coverage LABEL lies.

### Root cause (traced from source)

- `orchestration/orchestrator.py:683-684`:
  ```
  cols_consumed = submission.get("columns_consumed", {})
  cols_ignored  = {sheet: [c for c in cols if c not in cols_consumed.get(sheet, [])]
                   for sheet, cols in cols_present.items()}
  ```
  `cols_ignored = present - consumed`. But `consumed` (built by the CLI's
  `_columns_consumed_by_mapping`, cli.py:630) names only mapping-wired columns
  and the DERIVED `__autowired__` table columns (`measurement_name`, `visit_id`)
  -- NOT the SOURCE columns the autowire packs actually read (`mmse_total`,
  `cdr_sb`). The source columns therefore fall through to `ignored`.
- The source->pack decisions DO exist: `io/autowire.py` `autowire_ranges(...)`
  returns `decisions` (3rd element of its tuple) -- the per-column wiring
  strings the CLI prints. They are simply never folded into the coverage ledger.
- `_column_coverage_ledger` (cli.py:680) receives `autowired_sources` (the
  SHEET set) but not the per-column autowire decisions, so it cannot reclassify
  the source columns.

### Designed fix

1. Surface the autowire SOURCE columns from `decisions` (parse the wiring
   strings, as `_refused_columns` already parses refusal strings), or have
   `autowire_ranges` return a structured `{sheet: [source_cols]}` map.
2. Add a distinct coverage category **`columns_autowired`**: source columns
   consumed via autowiring. Keep `columns_consumed` for directly-mapped columns.
3. Remove autowired sources from the `ignored` derivation:
   `ignored = present - consumed - autowired - refused`.
4. Add a regression test (synthetic `mmse_total`/`cdr_sb` case): autowired
   sources appear in `columns_autowired`, NEVER in `columns_ignored`.
5. Add a release gate: CI fails if any audited/autowired column appears under
   `columns_ignored`.

### Blast radius (honest)

- The coverage ledger is inside the **hashed** `deterministic_core`
  (bundle.py:289 -> hashed by `_compute_bundle_id`). Changing its structure
  changes every `bundle_id`.
- Adding `columns_autowired` changes the coverage STRUCTURE -> requires
  `BUNDLE_FORMAT_VERSION` 1.4.0 -> 1.5.0 (bundle.py:87). That version is itself
  in the hashed core (bundle.py:274), so EVERY bundle_id drifts regardless.
- Therefore ALL FIVE locked cohort invariants must be re-locked:
  OASIS-3, ADNI, NACC, MIRIAD (longitudinal), MIRIAD (test-retest)
  -- new audit_id values in `tests/audit_core/test_real_*.py`.
- Downstream regen: `docs/reviewer_package/INVARIANTS_SUMMARY.md`, the reviewer
  notebook + prompt (audit_id values), framework version 1.80.0 -> 1.81.0,
  CHANGELOG, PyPI republish, and any in-suite tests asserting bundle_format 1.4.0.

### The hard dependency (why this is not fixed yet)

Re-locking four of the five invariants requires the DUA-governed datasets
(OASIS-3, NACC, MIRIAD) mounted locally. ADNI can be re-locked in any session
where `DXSUM.rda` is present; the other three cannot. A partial re-lock (ADNI
only, four stale) would ship a BROKEN reproducibility state -- unacceptable for
a tool whose core property is reproducibility. **The fix must be executed in a
single session with all four governed cohorts mounted, so the re-lock is whole.**

### Severity context

NeuroTCS is currently positioned as a research / reviewer-demo instrument
(see `docs/SCOPE.md`), not a regulated-deployment product. P0-1 mislabels
coverage; it does NOT produce wrong audit RESULTS (the values are audited
correctly). So it is a real production-readiness blocker but not an emergency:
the right fix is the complete one, done when the data is mounted -- not a rushed
partial re-lock or a human-report-only patch that leaves the JSON bundle wrong.

---

## P0-1 update: governed data LOCATED -- blocker lifted (ready to execute)

All four cohorts required to re-lock the five invariants are present locally,
under `G:\NeuroTCS data\NeuroTCS data\NeuroTCS\`:

| Cohort | File(s) | Path (under the base above) |
|---|---|---|
| ADNI | DXSUM.rda | `ADNI\ADNIMERGE2\data\DXSUM.rda` |
| OASIS-3 | OASIS3_UDSb4_cdr.csv | `OASIS3\OASIS3_UDSb4_cdr.csv` |
| NACC | investigator_nacc73.csv (~951 MB) | `NACC\investigator_nacc73.csv` |
| MIRIAD | three export CSVs (~18 KB / ~37 KB / ~1.7 KB) | `MIRIAD\DrMaruf_5_18_2026_*.csv` |

So the P0-1 fix is no longer data-blocked; it is a scoped, ready-to-execute
task. Recommended as a DEDICATED session (highest-stakes change in the codebase:
it deliberately rewrites every bundle_id and re-locks all five cryptographic
invariants -- a wrong locked value would silently corrupt reproducibility, so it
needs full fresh attention, not the tail of a long session).

### Execution order for the fix session (each step gated on verification)

1. BASELINE: re-run all five invariant tests on CURRENT code; confirm they pass
   (captures the pre-fix audit_ids, so post-fix drift is provable, not assumed).
2. CODE: thread autowire SOURCE columns into a new `columns_autowired` category;
   remove them from the `ignored` derivation (autowire.py -> cli.py ledger ->
   orchestrator.py manifest). Verify with the synthetic mmse_total/cdr_sb case.
3. FORMAT: bump BUNDLE_FORMAT_VERSION 1.4.0 -> 1.5.0.
4. RE-LOCK: re-run each of the five cohort audits on the real data; capture
   EXACTLY the audit_id each produces; lock THAT value (never transcribe/guess).
   Update tests/audit_core/test_real_*.py.
5. REGEN: INVARIANTS_SUMMARY.md + reviewer package notebook/prompt (new audit_ids).
6. VERSION: framework 1.80.0 -> 1.81.0 (all 6 bump locations + the guards).
7. TESTS: update any bundle_format==1.4.0 assertions; add the P0-1 regression
   test + a release gate (fail if an audited column appears under `ignored`).
8. VERIFY: full suite green + ruff clean LOCALLY before push.
9. SHIP: commit, push, confirm CI green, rebuild + republish to PyPI.

### Discipline reminder for the re-lock

Each re-locked invariant value MUST come from actually running NeuroTCS on the
real cohort data and capturing what it produces -- never a transcribed or
expected value. Same standard as every verified value this session.

---

## P0-2 disposition: reviewed, reproduced both directions -- CORRECT BY DESIGN (no change)

**Audit claim (P0-2):** a single sheet carrying both a clinical-stage axis and a
biological (A/T/N) axis audits ONLY the clinical axis, silently under-covering
the biological one.

**Reproduced from roots** (single sheet with clinical columns mmse_total/cdr_sb
plus a biological column `centiloid`):

Without `--confirm-assays`:
- The audit FAILS CLOSED with an explicit error naming the gap:
  "Column NOT wired: centiloid: resolves to centiloid_value
  (pet_amyloid/centiloid_consensus) but that is an assay/scale-calibrated
  biomarker -- NOT auto-wired ... Re-run with --confirm-assays ... or provide an
  explicit 'ranges' mapping."
- Coverage records it honestly in three places: REFUSED (with reason), IGNORED
  (listed), and the clinical axis CONSUMED. Nothing is dropped silently.

With `--confirm-assays` (operator asserts the calibration):
- BOTH packs wire on the same sheet: cognitive_scales/cdr_mmse_moca_consensus
  AND pet_amyloid/centiloid_consensus. Two autowired tables are created;
  centiloid moves into consumed; ignored is empty.

**Conclusion:** there is no same-sheet dual-axis under-coverage. The `by_pack`
grouping (autowire.py) wires EVERY pack a sheet's columns resolve to, not one.
The only gate on the biological axis is the assay-calibration refusal, which is
CORRECT fail-closed behavior: centiloid bounds are calibration-specific, and a
column name cannot certify which assay produced the value. Auto-wiring it would
fabricate an assay certification -- the exact hallucination the tool refuses to
make. The operator clears the gate by asserting the calibration (--confirm-assays
or an explicit mapping), at which point both axes audit.

The audit mistook a loud, reasoned, fail-closed refusal for silent
under-coverage; they are opposites. No code change. (Mirrors the P1
dispositions: do not "fix" correct behavior into a weaker contract.)

---

## P1-1 disposition: CONFIRMED REAL (bounded feature gap) -- long-format CDISC categorical state ingestion

**Audit claim (P1-1):** CDISC/SDTM data is not zero-config; it requires manual
mapping rather than being recognized automatically.

**Reproduced from roots. The claim is PARTIALLY correct -- a real, bounded gap:**

What WORKS (zero-config, verified):
- CDISC long-format MEASUREMENT recognition. `recognize_cdisc()` (io/cdisc.py)
  correctly detects SDTM/ADaM structure: for a QS long file it returns
  is_cdisc=True, subject_col=USUBJID, visit_col=VISITNUM, date_col=QSDTC,
  testcd_col=QSTESTCD, state_codes=('DX',), measurement_codes=('MMSE',).
- Numeric scales auto-wire and range-audit with no mapping (the autowire path
  pivots QSTESTCD->wide on the numeric result column QSSTRESN).

What does NOT work (the real gap):
- The CLINICAL STATE axis cannot be ingested from long format. In CDISC the
  categorical diagnosis (e.g. DX -> CN/MCI) lives in the CHARACTER result column
  (QSSTRESC), while numeric measurements live in QSSTRESN. The long->wide pivot
  `_pivot_long_to_wide` (io/autowire.py) HARD-COERCES the value column with
  `pd.to_numeric(..., errors='coerce')` -- by design, because range-auditing
  needs numbers. Pivoting the character column therefore yields an EMPTY frame
  (CN/MCI -> NaN). Verified empirically: char-pivot of QSSTRESC returns zero rows.
- The describe/emit-mapping scaffold (`_scaffold_mapping` / `_build_axis_spec` /
  `_sheet_has_recognizable_staging_field`, cli.py) detects state only by COLUMN
  NAME synonyms and never calls `recognize_cdisc`. A long-format sheet has no
  state COLUMN (state is a row value), so the gate rejects it and `state` is
  left as `<FILL:state>` -- even though recognize_cdisc would have found it.

**Why this is NOT a one-session patch (and why the obvious quick fix fails):**
Wiring `recognize_cdisc` into the describe scaffold to emit `state: "DX"` would
produce a mapping that DOES NOT AUDIT: the audit-time numeric pivot drops the DX
rows (categorical), so there is no DX state column at audit time. A scaffold that
emits a non-auditing mapping is a broken promise. The genuine fix requires a NEW
string-preserving categorical-state ingestion path for long-format CDISC,
coordinated with the numeric measurement pivot on the same sheet, wired into both
the audit path and the describe scaffold -- and it must never guess among
multiple state codes (preserve the CdiscMappingError ambiguous->fail-closed
contract). That is real ingestion-layer engineering with its own test surface.

**Shape of the genuine fix (for a focused session):**
1. Add a categorical long->wide pivot (preserve QSSTRESC/AVALC strings; do NOT
   to_numeric-coerce) used ONLY for the detected state code(s).
2. In the audit path: when recognize_cdisc reports state_codes on a long sheet,
   build the staging state column from the categorical pivot of the diagnosis
   code, alongside the existing numeric pivot for measurements.
3. In the describe scaffold: call recognize_cdisc when synonym detection finds no
   state column; if exactly ONE state_code, surface it as the candidate `state`
   (operator-confirmable); if MULTIPLE, leave <FILL:state> and LIST the candidate
   codes in _notes (never auto-pick); fill subject/visit/date from recognize_cdisc.
4. Round-trip test: describe --emit-mapping on a QS+DX long file must produce a
   mapping that AUDITS (stages the CN->MCI trajectory), not just a populated JSON.
5. Invariant-safe by construction (describe + ingestion of NEW long-format inputs;
   does not alter audit() scoring of existing wide submissions) -- but VERIFY by
   running the 7 real-cohort invariant tests post-change (must stay green).

**Severity:** usability/feature gap, NOT a trust/correctness defect. Long-format
CDISC data IS auditable today via an explicit wide `state` column or a separate
clinical sheet; only the zero-config path for categorical long-format state is
missing. Lower severity than P0-1 (which actively mislabeled coverage).

**Status:** confirmed real, root-caused, scoped. Deferred to a focused
implementation session (not appended to a long working session). No partial
scaffold shipped -- a scaffold that emits a non-auditing mapping would be worse
than the current honest fail-closed refusal.

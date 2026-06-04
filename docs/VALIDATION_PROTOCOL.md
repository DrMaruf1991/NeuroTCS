# NeuroTCS Flag-Validation Study Protocol

**Version 1.0 (design; no results)  -  2026-06-04**
**Sponsor/PI:** M. Salokhiddinov, MD PhD (KIUT, Uzbekistan)
**Statistical co-investigator:** *[to be appointed  -  biostatistician]*
**Status:** Pre-data study design. Contains NO empirical results. All numeric
targets below are design parameters, not findings.

---

## 0. Why this protocol exists

An external auditor issued a NO-GO with the following decisive objection
(paraphrased): NeuroTCS is a deterministic rule-matcher, so the "sensitivity"
of its flags *against its own encoded rules* is 1.0 by construction and
therefore scientifically meaningless. The unanswered, decision-relevant
question is: **of the records NeuroTCS flags, what fraction are genuine
data-quality errors, versus legitimate-but-rare biology, versus correct data
that an over-strict rule wrongly excludes?**

This protocol is the honest, rigorous answer. It specifies a study that
measures the **precision (positive predictive value) of NeuroTCS flags against
an independent expert gold standard**, plus the complementary coverage and
specificity questions. It deliberately does **not** report
sensitivity-against-rules as a headline metric, because that quantity is
tautological for a deterministic matcher.

This document is a *design*. It becomes a *result* only after execution on a
representative adjudicated cohort by blinded board-certified reviewers  -  work
that cannot be performed inside a chat session and is not simulated here.

---

## 1. Background and rationale

NeuroTCS audits the *outputs of other tools* (staging labels, biomarker values,
trajectories) against citation-locked published staging/coherence rules for
Alzheimer's disease. For each subject-record it emits a severity classification:
`impossible`, `implausible`, or `informational`.

Three failure modes are possible for any flag:

1. **True positive (true data error).** The flagged value reflects a real data
   problem (transcription error, unit error, mislabeled visit, impossible
   transition arising from a data-entry mistake).
2. **False positive  -  rare biology.** The flagged value is *correct* and
   reflects genuine but uncommon disease behavior the rule does not anticipate
   (e.g., a documented atypical trajectory).
3. **False positive  -  encoding limitation.** The flagged value is correct and
   *common enough that the rule should not have excluded it*; the flag reveals a
   defect in the rule encoding, not in the data.

A deterministic matcher cannot distinguish these three on its own. Only an
independent expert adjudication can. The clinical and regulatory value of
NeuroTCS rests entirely on the **proportion of flags that are type 1**  -  i.e.,
flag precision. That is this study's primary endpoint.

---

## 2. Objectives and endpoints

### 2.1 Primary objective
Estimate the **positive predictive value (PPV / precision) of NeuroTCS flags**
against a blinded expert gold standard, with a 95% confidence interval.

- **Primary endpoint:** PPV = (adjudicated true data errors among flagged
  records) / (all flagged records adjudicated), reported overall and stratified
  by severity tier (`impossible` vs `implausible`).

### 2.2 Secondary objectives
- **S1  -  Coverage / miss rate (1 - real-error sensitivity).** Among records
  NeuroTCS does **not** flag, estimate the proportion that nonetheless contain a
  true data error detectable by expert review. This is the honest analogue of
  sensitivity: sensitivity to *real errors in the wild*, not to encoded rules.
- **S2  -  Specificity on clean data.** On a subset adjudicated as error-free,
  estimate the false-flag rate.
- **S3  -  Misclassification decomposition.** Among false-positive flags,
  estimate the split between *rare biology* (type 2) and *encoding limitation*
  (type 3). Type-3 findings feed directly back into rule-pack revision.
- **S4  -  Inter-rater reliability.** Cohen's/Fleiss' kappa across adjudicators,
  reported with 95% CI, before disagreement resolution.

### 2.3 Exploratory
- Coverage of the encoded rule set against a realistic error taxonomy, via
  controlled error-injection (Section 6, the executable arm).
- Subgroup PPV by APOE genotype, cohort/site, and assay platform, to detect
  spectrum bias.

---

## 3. Study design

**Type:** Retrospective, reader-blinded diagnostic-accuracy study with an
independent expert reference standard, reported per STARD 2015 conventions
(adapted: the "index test" is the NeuroTCS flag; the "reference standard" is
blinded expert adjudication of data correctness, not a disease diagnosis).

**Two arms:**

- **Arm A  -  Natural-flag adjudication (primary).** Run NeuroTCS on a
  representative cohort. Draw the adjudication sample (Section 5) of flagged and
  unflagged records. Blinded experts adjudicate each record's data correctness.
  Yields PPV (primary), coverage/miss (S1), specificity (S2), decomposition (S3).
- **Arm B  -  Controlled error-injection (exploratory/supporting).** On a cohort
  adjudicated as clean, inject a pre-registered taxonomy of realistic data
  errors at known locations and rates; measure detection by error type. Yields
  rule-set coverage characterization independent of natural-error prevalence.
  Arm B is executable as soon as a clean cohort is available and is the basis of
  the software harness in Section 6.

---

## 4. Definitions (adjudication rubric)

Each adjudicated record is assigned exactly one label by each reviewer, blinded
to the NeuroTCS output:

- **DATA_ERROR**  -  the recorded value/label/sequence is incorrect as a matter of
  data integrity (verifiable against source documents or internally impossible).
- **CORRECT_RARE**  -  the value is correct and clinically legitimate but
  uncommon; no data problem.
- **CORRECT_COMMON**  -  the value is correct and unremarkable.
- **INDETERMINATE**  -  cannot be adjudicated from available information.

Mapping to flag outcomes:
- A flag is a **true positive** iff the consensus label is `DATA_ERROR`.
- A flag on `CORRECT_RARE` is a **type-2** false positive (rare biology).
- A flag on `CORRECT_COMMON` is a **type-3** false positive (encoding limitation).
- An *unflagged* record labeled `DATA_ERROR` is a **miss** (false negative).

`INDETERMINATE` records are reported separately and excluded from the primary
PPV denominator in the main analysis; a sensitivity analysis includes them as a
worst-case (counted as false positives) to bound the estimate.

---

## 5. Reference standard and blinding

- **Reviewers:** >=3 board-certified specialists (neurology / neuroradiology /
  geriatric medicine as appropriate to the cohort), independent of rule-pack
  authorship.
- **Blinding:** reviewers see the subject record and clinical context but **not**
  the NeuroTCS severity output, and not whether a record was flagged. Record
  order randomized; flagged and unflagged records interleaved.
- **Adjudication unit:** the subject-record (the same unit NeuroTCS scores).
- **Disagreement resolution:** primary analysis uses majority consensus; a
  fourth senior adjudicator resolves ties. Pre-resolution labels are retained
  for kappa (S4).
- **Source-of-truth:** where source documents (CRFs, original imaging reports)
  are available, `DATA_ERROR` adjudication must cite the discrepancy; where not,
  adjudication is on internal/clinical plausibility and flagged as such.

---

## 6. Error-injection harness (Arm B, executable now)

Arm B is implementable as dataset-agnostic software and can be self-verified on
synthetic data before any real cohort exists. Specification:

1. **Error taxonomy** (pre-registered): unit errors, decimal/transcription
   errors, swapped-visit dates, mislabeled stages, impossible
   transitions, out-of-physiological-range values, duplicated records,
   missing-as-zero. Each type carries a realistic injection rate drawn from the
   data-management literature, declared in advance.
2. **Injector:** given a clean cohort, inject errors at known
   (record, field, type) coordinates, emitting a ground-truth manifest.
3. **Runner:** execute the standard NeuroTCS audit on the corrupted cohort.
4. **Scorer:** compare flags to the injected manifest -> per-type detection rate,
   overall coverage, and specificity on un-injected records, with CIs.

**Honest limitation of Arm B:** for an error type that maps exactly onto an
encoded rule, detection is 1.0 by construction  -  so Arm B does **not** claim to
measure "accuracy." Its legitimate output is **coverage**: what fraction of a
*realistic* error distribution falls within the rule set's detectable scope.
That is a genuine, non-tautological, decision-relevant quantity. Arm B never
substitutes for Arm A's PPV.

---

## 7. Sample size and power

The primary endpoint is a single proportion (PPV). Sample size targets a 95% CI
half-width *w* on the estimate, using the Wald/Wilson interval; final analysis
uses the Wilson score interval (better small-sample coverage).

Required adjudicated **flagged** records `n_flag` ~ z^2p(1-p)/w^2 (z=1.96):

| Anticipated PPV (p) | Target half-width w | n_flag (approx) |
|---|---|---|
| 0.60 | 0.07 | 188 |
| 0.70 | 0.07 | 165 |
| 0.80 | 0.07 | 126 |
| 0.70 | 0.05 | 323 |

For the coverage/miss endpoint (S1), the unflagged-record sample is sized
separately for the same precision on the miss proportion; because true errors
among unflagged records are expected to be rare, S1 is reported with an exact
(Clopper-Pearson) interval and explicitly powered as a secondary, possibly
upper-bound, estimate.

The final numbers above are **design targets**; the statistical co-investigator
finalizes them against the realized flag prevalence in the chosen cohort.

---

## 8. Statistical analysis plan (SAP)

- **Primary:** PPV with 95% Wilson CI, overall and by severity tier. Pre-stated
  success threshold for "clinically useful flagging" is declared *before*
  unblinding (e.g., lower CI bound for `impossible`-tier PPV exceeding a
  pre-specified value agreed with the co-investigator); this protocol does not
  assert that threshold has been met.
- **Secondary:** S1 miss rate (Clopper-Pearson), S2 specificity (Wilson),
  S3 type-2/type-3 decomposition (proportions with CIs), S4 kappa with CI.
- **Subgroups (exploratory):** PPV by APOE, site, assay; reported with
  multiplicity caveat (no confirmatory claims).
- **Missing/indeterminate:** primary excludes `INDETERMINATE`; sensitivity
  analysis bounds the estimate by recoding `INDETERMINATE` as false positives.
- **Determinism check:** the NeuroTCS audit_id and severity counts are recorded
  and asserted byte-stable across the analysis runs (the tool's existing
  reproducibility invariant), so that the index test is fixed during adjudication.

---

## 9. Threats to validity and mitigations

- **Deterministic-matcher tautology.** Mitigated by making PPV (not
  rule-sensitivity) the primary endpoint and by labeling Arm B as coverage, not
  accuracy.
- **Imperfect gold standard.** Expert adjudication is itself fallible; mitigated
  by >=3 blinded reviewers, kappa reporting, source-document citation where
  available, and an `INDETERMINATE` category rather than forced labels.
- **Rare-biology confound.** The single most important threat: penalizing
  NeuroTCS for correctly flagging unusual-looking *correct* data. Mitigated by
  the explicit `CORRECT_RARE` label and the type-2/type-3 decomposition, so rare
  biology is measured rather than silently miscounted as error.
- **Spectrum/selection bias.** Mitigated by pre-specified cohort definition and
  subgroup reporting by site/assay.
- **Upstream-origin ambiguity.** NeuroTCS audits other tools' outputs; an error
  may originate upstream. Adjudication targets *data correctness at the audited
  record*, which is the appropriate unit regardless of origin; origin is
  recorded when knowable.
- **Reader blinding leakage.** Interleaving and randomization; audit of any
  records where blinding may have been compromised.

---

## 10. Data governance (ties to auditor Blocker 4)

Representative participant-level cohort data (ADNI, OASIS-3, A4, etc.) is
DUA-gated and **must not** be uploaded to general chat tools or this repository.
The study runs in the data holder's approved environment. The repository ships
the *apparatus* (Arm B harness, scoring code, SAP), the rule packs, and the
deterministic audit; it does not and will not ship the gated data. This is by
design and is the correct governance posture, not a limitation to be "fixed" by
embedding data.

---

## 11. Deliverables and honest status ledger

| Item | Status | Honest note |
|---|---|---|
| Study protocol (this document) | DRAFT v1.0, complete as a design | No results; needs biostatistician sign-off |
| Arm B injection/scoring harness | Buildable now; self-verifiable on synthetic data | Measures coverage, not accuracy |
| Arm A adjudication | NOT done | Requires cohort + blinded board-certified reviewers |
| Primary PPV result | NOT produced | Will not be simulated or estimated without Arm A |
| Statistical co-authorship | Open | This protocol is the recruiting artifact |

**Bottom line.** This protocol closes the *design* gap behind auditor Blocker 1.
It does not close the *evidence* gap  -  that requires executing Arm A on real
adjudicated data with qualified reviewers. Anyone reading this should understand
that distinction clearly: a rigorous plan to measure flag precision exists; the
measurement itself is future work that cannot be honestly shortcut.

# AD Fairness Audit (FUTURE-AI Panel B.4.4)

**Status**: pipeline shipped in v1.7.10 (AD-lock Step 2.2); locked invariants
to be captured by Maruf's first real-data run on the three cohorts.

**Framework citation**: Lekadir K, Frangi AF, Porras AR, Glocker B, Cintas C,
Langlotz CP, et al.; FUTURE-AI Consortium. FUTURE-AI: international consensus
guideline for trustworthy and deployable artificial intelligence in healthcare.
*BMJ* 2025;388:e081554. DOI [10.1136/bmj-2024-081554](https://doi.org/10.1136/bmj-2024-081554).
PMID [39909534](https://pubmed.ncbi.nlm.nih.gov/39909534/).

## What this document covers

This is the fairness-stratification audit of NeuroTCS's AD cTCS metric across
demographic subgroups. It is **distinct from** the robustness panel (B.4.5),
which stratifies on technical/operational variables (scanner vendor, field
strength, acquisition site). The two panels are intentionally disjoint per the
FUTURE-AI consensus.

## Scope and design decisions

### What we stratify on

The FUTURE-AI BMJ 2025 paper, Fairness 1 verbatim, lists "sex, gender, age,
ethnicity, socioeconomic status, geography, comorbidities, disabilities, skin
colour, breast density" plus application-specific factors. The NeuroTCS
canonical set (in `neurotcs.fairness.FUTURE_AI_FAIRNESS_ATTRIBUTES`) is:

| Attribute | Source field | Available in cohort |
|---|---|---|
| `sex` | MIRIAD: Subjects.csv `Gender`; ADNI: PTDEMOG `PTGENDER`; OASIS-3: demographics `gender` | MIRIAD ✓; ADNI / OASIS-3 require Maruf's local demographics-table join |
| `age_band` | Computed from minimum age-at-baseline per subject. 10-year bands: `<60`, `60-69`, `70-79`, `80-89`, `90+`. | MIRIAD ✓ from `Age` column; ADNI ✓ from PTAGE; OASIS-3 ✓ from CDR age |
| `race_ethnicity` | MIRIAD: not collected (single-site UCL DRC); ADNI: PTDEMOG `PTRACCAT`; OASIS-3: demographics `race` | MIRIAD = `unknown` (justifiable: single-site cohort); ADNI / OASIS-3 require join |
| `comorbidity` | Not extracted yet from any cohort | All `unknown` until adapters extract |
| `disease_stage` | Could be derived from baseline state (CN/MCI/AD) — not currently extracted | All `unknown` until populated |
| `treatment_status` | TRAC pack field — anti-amyloid yes/no | Default empty; relevant once AA-2024 + ALZ-NET data is wired |

### What is *not* a fairness variable here

Per the FUTURE-AI separation enforced by `neurotcs.fairness`:
- Scanner vendor, field strength, acquisition site → **Robustness panel (B.4.5)**
- The fairness panel will silently ignore these even if passed in, by design.

### What this audit measures

The fairness audit computes the **flag rate disparity** of the audit kernel
across demographic strata. For each stratum (e.g. sex=F), we report:

- `n_transitions`: number of audited transitions contributed by subjects in that stratum
- `n_flagged`: number of those transitions marked as inadmissible by the rule pack
- `flag_rate = n_flagged / n_transitions`
- `statistical_parity_vs_overall = flag_rate - overall_flag_rate`

The headline metric is `max_disparity` — the largest absolute deviation of any
stratum's flag rate from the cohort overall flag rate. A large disparity
suggests the audit kernel is treating subgroups differently and warrants
investigation.

### What this audit does NOT measure

- It is **not** an evaluation of a downstream predictive model (NeuroTCS is a
  rule-pack audit metric, not a classifier). TPR / Equalised Odds /
  Demographic Parity in the FUTURE-AI Fairness 3 recommendation are
  classifier-level metrics; they require ground-truth labels and a prediction
  score, which NeuroTCS does not produce. The `tpr` field on `StratumMetrics`
  is therefore reported as `None`.
- It is **not** a discrimination-bias test of the rule pack itself. The rule
  pack encodes published clinical guidelines (NIA-AA 2018, AA-2024, etc.).
  Any disparity observed reflects the input cohort's demographic distribution
  intersected with the rules' constraints, not a fairness-violating preference
  in the kernel.

What it DOES measure: whether some demographic groups have their natural-history
trajectories flagged at materially different rates by the audit. That is a
necessary precondition for any downstream conformance gate to be considered
fair under FUTURE-AI.

## Pipeline architecture

```
Subjects.csv (Gender, YOB, Education, Hand)
       │
       ▼
adapter_miriad.py
  ├── Maps Gender -> sex ∈ {M, F, unknown}
  ├── Computes age_band from min age-at-scan per subject
  ├── Extracts yob, education_years, handedness
  └── Attaches to Trajectory.metadata
       │
       ▼
audit(trajectories, pack, return_per_transition=True)
       │
       ▼  (additive, score-neutral; audit_id unchanged)
AuditResult.per_transition: PerTransitionFlags
  ├── flags: bool[n_transitions]
  ├── trajectory_metadata: dict[] per transition
  └── attribute_array(name) -> np.ndarray
       │
       ▼
cohort_fairness_audit(audit_result)
       │
       ▼
FairnessAuditResult
  ├── panel_id = "B.4.4_fairness"
  ├── strata: per-(attribute, value) flag rates
  ├── overall_flag_rate, max_disparity, max_disparity_stratum
```

## Key invariants

These are tested in CI and must hold across all v1.7.x releases going forward:

1. **`audit_id` and `audit_id_v2` are unchanged** when
   `return_per_transition=True` is passed. Per-transition data and demographic
   metadata are additive only. The locked invariants `947ab24e...`
   (MIRIAD longitudinal) and `80430399...` (MIRIAD test-retest) reproduce
   bit-exactly regardless of whether demographics are attached or fairness
   is requested.
   *Test*: `test_audit_id_unchanged_with_return_per_transition_true` and
   `test_miriad_adapter_demographic_extraction_does_not_break_audit_id`.

2. **The fairness panel and robustness panel use disjoint attribute sets**.
   `scanner_vendor` will NEVER appear in a fairness report.
   *Test*: `test_robustness_attributes_are_locked` and
   `test_fairness_audit_does_not_pick_up_scanner_vendor`.

3. **Missing demographics produce `unknown` strata, not crashes**. A cohort
   that lacks `race_ethnicity` data will show one stratum (`race_ethnicity:
   unknown`, n = total) with zero disparity — flagging this as a known
   limitation rather than fabricating values.
   *Test*: `test_miriad_adapter_demographics_unknown_without_subjects_csv`
   and `test_cohort_fairness_audit_handles_missing_attribute`.

4. **Per-transition iteration order is deterministic** (trajectories in input
   order, transitions within each trajectory in chronological order).
   Reproducibility guarantee for cross-machine audit verification.
   *Test*: `test_per_transition_iteration_order_is_trajectory_then_chronological`.

## How to run on a real cohort

For MIRIAD (the cohort with end-to-end demographic support today):

```powershell
$env:NEUROTCS_MIRIAD_DIR = "$env:USERPROFILE\Downloads"

python scripts/run_ad_fairness_audit.py `
    --cohort   miriad `
    --clinical "$env:USERPROFILE\Downloads\DrMaruf_5_18_2026_12_16_7.csv" `
    --sessions "$env:USERPROFILE\Downloads\DrMaruf_5_18_2026_12_16_24.csv" `
    --subjects "$env:USERPROFILE\Downloads\DrMaruf_5_18_2026_12_16_33.csv" `
    --rulepack ad/niaaa_2018 `
    --out      "$env:USERPROFILE\Downloads\MIRIAD_fairness_results"
```

This produces:
- `ad_fairness_report.json` — structured machine-readable report with
  `audit_id`, per-stratum flag rates, and FUTURE-AI framework metadata.
- `ad_fairness_summary.txt` — human-readable summary table.

For ADNI and OASIS-3, the corresponding cohort handlers are pending. They
require the production adapter (which lives in Maruf's workflow, not the
in-repo reference adapter) to populate `Trajectory.metadata` with the same
canonical attribute names: `sex`, `age_band`, `race_ethnicity` etc. Once
that is wired, the runner adds `--cohort adni` / `--cohort oasis3` paths
that follow the identical pattern.

## Locking the MIRIAD fairness invariant

After Maruf executes the runner on his real MIRIAD CSVs and pastes the
`ad_fairness_summary.txt` content back, we add a `tests/audit_core/
test_real_miriad_fairness_audit.py` that locks the per-stratum flag counts
exactly (paralleling `test_real_miriad_audit.py`'s locking of cTCS audit_ids).
That closes the loop for the MIRIAD cohort under NIA-AA 2018 framework.

## Honest gaps acknowledged

1. **ADNI and OASIS-3 fairness pending.** The in-repo reference adapters
   hardcode demographics as `"unknown"`. Maruf's production workflow already
   joins PTDEMOG and OASIS-3 demographics; the runner pattern lets him produce
   identical reports for those cohorts on his machine. We document this
   honestly rather than claiming fairness coverage we don't yet ship.
2. **No race_ethnicity in MIRIAD.** MIRIAD is single-site UCL DRC and does not
   collect race data. The fairness report shows `race_ethnicity: unknown` for
   all transitions — a true limitation of the cohort, not a deficit of the
   audit. ADNI and OASIS-3 do collect this; reports for those cohorts will
   show populated strata.
3. **No comorbidity, disease_stage, treatment_status data extracted yet.**
   These canonical FUTURE-AI attributes are recognised by the fairness panel
   but no adapter currently populates them. They show `unknown` in reports.
   Plumbing them is straightforward and a candidate for a future step (would
   require disease-stage column in adapters and TRAC-aware treatment flag
   extraction).
4. **`tpr` and other classifier-level metrics report `None`.** This is by
   design — NeuroTCS does not produce a classifier prediction, only a
   rule-pack audit verdict. The fairness panel's classifier-level metrics
   from FUTURE-AI Fairness 3 do not apply to the rule-audit context.

## What "world-class no-future-fix" looks like for this panel

After this step, the AD fairness pipeline:

- ✅ Has a documented policy (this doc)
- ✅ Has a citation-locked framework reference (FUTURE-AI BMJ 2025)
- ✅ Has a canonical attribute list (FUTURE_AI_FAIRNESS_ATTRIBUTES)
- ✅ Has end-to-end adapter → audit → fairness wiring for MIRIAD
- ✅ Has a runner script with both JSON and text reports linked to audit_id
- ✅ Has regression tests for the no-regression invariants (audit_id, panel
     separation, missing-attribute handling)
- ✅ Has explicit acknowledgement of honest gaps (ADNI / OASIS-3 pending
     local demographic joins)

After Maruf executes the runner on real MIRIAD data and locks the invariants,
this panel reaches the "no expert question" bar for MIRIAD. Bringing
ADNI / OASIS-3 to the same bar is local-workflow work (adapter extension
on his machine) that mirrors the MIRIAD pattern exactly.

## Version history

- **v1.7.10 (AD-lock Step 2.2)**: pipeline shipped. PerTransitionFlags
  machinery added to `audit()`, MIRIAD adapter extracts sex/age_band/yob/
  education_years/handedness, `cohort_fairness_audit()` helper added,
  runner script created, this document written. 15 new regression tests
  covering the demographic extraction + flag-detail + fairness-bridge layers.

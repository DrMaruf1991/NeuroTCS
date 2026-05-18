# Errata for NeuroTCS

This file documents corrections to published NeuroTCS results. All
corrections are made transparently and as soon as discovered.

---

## E-2026-001 · MCI→AD transition priors mis-encoded as cumulative when they should have been annual (fixed in v1.5.0)

**Discovered:** 2026-05-18
**Fixed in:** v1.5.0 (commit shipping with this errata)
**Affected versions:** v1.0.0 through v1.4.0
**Severity:** Affects pTCS values only. **cTCS and uTCS — including the headline Aim 1 ADNI and Aim 2 OASIS-3 replication findings — are unaffected.**

### What happened

The `ad/niaaa_2018@1.1.0` rule pack encoded MCI→AD annual transition priors of 0.415 (clinical) and 0.27 (population), citing Salemme et al. 2025 (*Alzheimer's & Dementia: DADM* 17(1):e70074, DOI 10.1002/dad2.70074). On re-reading the source paper, these figures are the **cumulative incidence of dementia over the meta-analysis's mean follow-up of 5.2 years**, NOT annual rates.

Salemme 2025 explicitly states: *"The cumulative incidence of dementia was 38%, with a 42% risk in clinical settings and 27% in population settings. The ACR [annual conversion rate] nearly doubled from 6% in population settings to 11% in clinical settings."*

The correct annual conversion rates from the same primary source are:
- MCI → dementia clinical: **0.11** [95% CI ~0.08, 0.14]
- MCI → dementia population: **0.06** [95% CI ~0.04, 0.08]

These are cross-validated by Mitchell & Shiri-Feshki 2009 (Acta Psychiatr Scand 119(4):252-265, doi:10.1111/j.1600-0447.2008.01326.x): specialist Mayo-MCI→AD ACR = 8.1%, community = 6.8%.

### What changed in v1.5.0

The `ad/niaaa_2018` rule pack has been bumped to `@1.2.0` with corrected priors derived directly from Salemme 2025's ACR values. The corrected priors block (in `src/neurotcs/rulepack/rules/ad/niaaa_2018.yaml`) carries full citation text explaining the correction and cross-validation sources for each rate.

### What is preserved

The published Aim 1 ADNI and Aim 2 OASIS-3 cTCS findings are **unchanged**:

- ADNI: n_transitions = 12,006, n_flagged = 65 (0.54 %), **cTCS = 0.9946**
- OASIS-3: n_transitions = 7,248, n_flagged = 30 (0.41 %), **cTCS = 0.9942**
- ΔcTCS = 0.0004 (independent cohort replication)

This is by construction: cTCS is the deterministic admissibility kernel (k_n / n) and does not depend on prior probabilities. The same logic applies to uTCS (the uncertainty-weighted admissibility average). Only pTCS uses the priors, and the corrected priors yield meaningful pTCS values where the previous ones were not interpretable.

### What changed

The locked Aim 1 ADNI pTCS value changed from -0.3319 to **-0.5802** (clinical priors). The locked audit_id changed from `d344ec1a00f428a8...e8fa693ac03` to **`0eb7a23911bd2111...297e98a5db`** because the priors are inputs to the audit hash.

The locked Aim 2 OASIS-3 pTCS value and audit_id will similarly change when the OASIS-3 data is re-audited locally — the test file `tests/audit_core/test_real_oasis3_audit.py` updates the expected `audit_id` and is structured to be re-derived rather than memorized.

### Methodology change

Starting v1.5.0, every numerical value in a NeuroTCS rule pack must be cross-validated against at least one additional primary source before commit. For ACR-type values specifically, the methodology requires reading the source paper's methods section to confirm whether the reported number is **annual** or **cumulative** (a common source of confusion in MCI prognosis literature). The verified evidence table for each rule pack is logged in `docs/transcription_audit/<pack>.md`.

### Acknowledgment

This error was identified by Dr. Marufjon Salokhiddinov during a v1.5.0 review session that asked whether the existing AA rule packs were sufficiently current. The question prompted re-reading of the Salemme 2025 source, which surfaced the cumulative-vs-annual confusion. The methodology fix is more important than the value fix.

---

## E-2026-002 · `ad/aa_2024@1.1.0` ships with empty `transition_priors` — pTCS unavailable (fixed in v1.6.0)

**Discovered:** 2026-05-18 (during v1.5.0 review session)
**Fixed in:** v1.6.0 (commit shipping with this errata entry)
**Affected versions:** v1.0.0 through v1.5.0
**Severity:** Restrictive — pTCS could not be computed when auditing trajectories with the AA-2024 rule pack. Did not affect cTCS or uTCS. Did not affect any published Aim 1 ADNI or Aim 2 OASIS-3 findings (which use `ad/niaaa_2018`).

### What happened

The `ad/aa_2024@1.1.0` rule pack was shipped with `transition_priors: []`. Without priors, the audit engine cannot build the continuous-time Markov generator matrix needed for pTCS, so pTCS would be reported as unavailable. This was a known gap in v1.1.0 — v1.4.0, documented in the README's "Known limitations and roadmap" section.

A deeper question raised in the v1.5.0 review: had the published literature actually progressed enough to populate these priors with rigorously-verified primary-source values? Initial search suggested only cross-sectional data existed for the AA-2024 4×4 matrix (Mendes 2025, Strandberg 2025). However, expanded literature review identified multiple longitudinal primary sources publishing explicit annual conversion rates (ACR) for every forward Stage_N → Stage_N+1 transition.

### What changed in v1.6.0

The `ad/aa_2024` rule pack is bumped to `@1.2.0` with 13 transition priors, all citation-locked to primary sources. Every ACR is verified against the source paper's methods section to confirm it is annual (not cumulative-misinterpreted-as-annual, per E-2026-001 methodology). Six single-step Stage_N → Stage_N+1 transitions are anchored to primary publications; five derived Stage_N → Stage_N+2 transitions are computed as products with √2 CI inflation and marked `prior_type: "derived"` to distinguish from primary rates.

Primary sources used:

| Transition | Source |
|---|---|
| Stage_0 → Stage_1 (population) | Roberts 2018 *JAMA Neurol*, MCSA, PMID 29710225 |
| Stage_0 → Stage_1 (clinical) | Jagust & Landau 2021 *Neurology*, ADNI, PMID 33408147 |
| Stage_1 → Stage_2 | Karagianni 2025 *Alz & Dem* Suppl, multicenter, PMC12724900 |
| Stage_2 → Stage_3 | Ossenkoppele 2022 *Nature Medicine*, 7-cohort, PMID 36357681 |
| Stage_3 → Stage_4 | Ossenkoppele 2022 *Nature Medicine*, 7-cohort, PMID 36357681 |
| Stage_4 → Stage_5 (clinical) | Tariot 2024 *Alz Res Ther*, NACC, PMID 38355706 |
| Stage_4 → Stage_5 (population) | Salemme 2025 *Alz Dem DADM* (already verified in v1.5.0) |
| Stage_5 → Stage_6 | Tariot 2024 *Alz Res Ther*, NACC, PMID 38355706 |

### What is preserved

The published Aim 1 ADNI and Aim 2 OASIS-3 cTCS findings are **unchanged**:

- ADNI: cTCS = 0.9946 (using `niaaa_2018@1.2.0`)
- OASIS-3: cTCS = 0.9942 (using `niaaa_2018@1.2.0`)
- ΔcTCS = 0.0004

The locked v1.5.0 ADNI invariant (audit_id `fa448b8f...`) is also unchanged because the ADNI audit does not use AA-2024.

### Methodology change (cumulative E-2026-001 + E-2026-002 lessons)

Starting v1.6.0, every numerical value in a NeuroTCS rule pack:

1. Must be verified against a peer-reviewed primary source via DOI or PMID
2. For ACR-type values, the source paper's methods section must explicitly state the rate is annual (not cumulative over follow-up)
3. Where multiple cohort settings exist (clinical vs population), both must be encoded as separate priors
4. Derived priors (products of two single-step rates) must be marked `prior_type: "derived"` and link to the underlying primary sources

The verified evidence table for each rule pack is logged in `docs/transcription_audit/<pack>.md` so any reviewer can spot-check.

### Acknowledgment

Same as E-2026-001: the gap was flagged by Dr. Salokhiddinov asking whether the AD rule packs were sufficiently current and pushing for "world-class no partial fix" verification.

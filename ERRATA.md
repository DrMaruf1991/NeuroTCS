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

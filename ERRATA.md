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

---

## E-2026-003 · Marras 2002 citation metadata wrong, "Table 2 stage-transition intervals" does not exist (fixed in v1.7.1)

**Discovered:** 2026-05-18 (external audit of the v1.7.0 release)
**Fixed in:** v1.7.1 (commit shipping with this errata entry)
**Affected versions:** v1.0.0 through v1.7.0
**Severity:** Restrictive — affects the structural integrity of citation locking; **does NOT change any audit value**. The cTCS, pTCS, uTCS, and locked invariants (ADNI cTCS=0.9946; OASIS-3 cTCS=0.9942) are unchanged because all of those audits run on AD rule packs, not PD.

### What happened

The `pd/hoehn_yahr` rule pack and its transcription audit cited the natural-history pace of Hoehn-Yahr progression as:

> Marras C et al. *Neurology* 2002;59:1724-1730. PMID 12473781. DOI 10.1212/01.WNL.0000036428.92845.27.

Every element of that citation is wrong:

| Field | Claimed | Verified (PubMed + Crossref) |
|---|---|---|
| Journal | Neurology | **Archives of Neurology** |
| Pages | 1724-1730 | **1724-1728** |
| PMID | 12473781 | **12433259** |
| DOI prefix | 10.1212/01.WNL.* (Neurology pattern) | **10.1001/archneur.59.11.1724** (Arch Neurol pattern) |

The PMID 12473781 actually points to an unrelated paper. The DOI `10.1212/01.WNL.0000036428.92845.27` is a Neurology-journal DOI pattern that cannot resolve to an Archives of Neurology paper.

Worse: the YAML's `guideline_section` field attributed multi-step Δt floors to **"Marras 2002, Table 2 (stage-transition intervals)"** — but the real paper is a *systematic review* of motor-decline predictors in PD literature (1966-2002), and it does **NOT publish a per-transition table of admissibility windows**. The min-Δt floors in the YAML are clinical inferences applied on top of the review's reported pace of ~1 H&Y stage per 2-3 years, not direct transcriptions of a table that does not exist.

### What changed in v1.7.1

1. **All 8 Marras citation blocks in `pd/hoehn_yahr.yaml` corrected** with verified metadata: PMID 12433259, DOI 10.1001/archneur.59.11.1724, journal Archives of Neurology, pages 1724-1728.
2. **All 7 multi-step Marras transitions reclassified** as `attribution_type: clinical_inference` (a new schema v1.3.0 field) with explicit `inference_rationale`. Reviewers reading the YAML can now see at a glance that the min-Δt floor is a clinical inference informed by the cited review, not a verbatim quote from a non-existent table.
3. **`pd_hoehn_yahr.md` transcription audit rewritten** with the corrected citation and a verification protocol section that walks reviewers through PubMed PMID 12433259 (NOT the prior 12473781) and confirms that Marras 2002 is a systematic review.
4. **Schema v1.3.0** adds the `AttributionType` enum (`guideline_quote` | `clinical_inference`) and the optional `inference_rationale` field. A validator REQUIRES the rationale when attribution_type is clinical_inference. Backward compatible: the default `guideline_quote` preserves prior behavior.
5. **`scripts/verify_citations.py` added** to call Crossref and PubMed EUtils on every `citation_pmid` and `citation_doi` in every rule pack and every transcription audit, on every commit. This is the mechanical defense that catches Marras-class defects (real paper, wrong metadata) at commit time. Wired into `.github/workflows/ci.yml` as a separate `citations` job.

### What is preserved

The Hoehn-Yahr rule pack's behavior is unchanged — the min-Δt floors (365 days for 2-step jumps, 730 days for 3-step jumps) and override_allowed=true flags are all preserved. Only the *attribution metadata* changed. No audit result, no cTCS value, no audit_id value depends on the citation text.

### Methodology change (cumulative E-2026-001/2/3 lessons)

Starting v1.7.1, every numerical value AND every citation in a NeuroTCS rule pack:

1. (E-2026-001) Must be verified against a peer-reviewed primary source via DOI or PMID.
2. (E-2026-001) For ACR-type values, the source paper's methods section must explicitly state the rate is annual.
3. (E-2026-002) Where multiple cohort settings exist, both must be encoded as separate priors.
4. (E-2026-002) Derived priors must be marked `prior_type: "derived"`.
5. **(E-2026-003, NEW) Citations must be verified against Crossref AND PubMed EUtils via `scripts/verify_citations.py` on every commit. A real paper at the wrong journal/pages/PMID/DOI no longer ships.**
6. **(E-2026-003, NEW) When a rule's structure is a clinical inference informed by — but not directly quoted from — the citation, the transition MUST set `attribution_type: clinical_inference` and provide a non-empty `inference_rationale`. The schema validator enforces this.**

### Acknowledgment

Flagged by an external auditor running citation cross-checks on the v1.7.0 release. The auditor's specific signal — "the DOI prefix 10.1212/01.WNL.* is a Neurology pattern that cannot resolve to an Arch Neurol paper" — is exactly the kind of structural mismatch that a mechanical resolver catches and a human eye fills in automatically. The methodology fix (per-commit Crossref + EUtils verification) is more important than the value fix.

---

## E-2026-004 · "Hayden 2017" attribution is incorrect; DOI 10.1016/j.jalz.2016.07.151 actually resolves to Chen Y et al. 2017 (fixed in v1.7.1)

**Discovered:** 2026-05-18 (external audit of the v1.7.0 release)
**Fixed in:** v1.7.1 (commit shipping with this errata entry)
**Affected versions:** v1.0.0 through v1.7.0
**Severity:** Restrictive — affects attribution accuracy of two priors in `ad/niaaa_2018`; **does NOT change any audit value**. The numerical ACR values (30% clinical, 5% population) match the resolved paper's abstract verbatim, so locked invariants (ADNI cTCS=0.9946 etc.) are unchanged.

### What happened

The `ad/niaaa_2018` rule pack cited two CN→MCI conversion priors as:

> Hayden et al. 2017 (Alz & Dem 13(5):573-582, PMC5451154) with DOI 10.1016/j.jalz.2016.07.151.

The DOI `10.1016/j.jalz.2016.07.151` actually resolves to a different paper:

> Chen Y, Denny KG, Harvey D, Farias ST, Mungas D, DeCarli C, Beckett L. "Progression from normal cognition to mild cognitive impairment in a diverse clinic-based and community-based elderly cohort." *Alzheimers Dement* 2017;**13(4):399-405** (NOT 13(5):573-582). PMID 27590706. PMCID PMC5451154.

There is no "Hayden" among the authors. The paper is from the UC Davis ADC cohort (same DeCarli/Beckett lab the YAML had partially identified correctly), but the lead author is Chen, not Hayden. The page numbers are also wrong (13(4):399-405, not 13(5):573-582).

### What is preserved (and why this is "metadata only")

The ACR values themselves are correct. The Chen 2017 paper's PubMed abstract states **verbatim**:

> "The clinic-based sample showed an annual conversion rate of **30% (95% CI 17%-54%) per person-year**, whereas the community-based sample showed a conversion rate of **5% (95% CI 3%-6%) per person-year**."

These match the YAML's `annual_probability: 0.30` (CI 0.17-0.54) and `annual_probability: 0.048` (CI 0.030-0.080) priors exactly. So the corrected citation strengthens the rule pack rather than changing its behavior — the locked AD cTCS/pTCS/uTCS values, audit_ids, and ADNI/OASIS-3 replication results all carry through unchanged.

### What changed in v1.7.1

1. Both CN→MCI priors in `ad/niaaa_2018.yaml` updated:
   - `citation_pmid` corrected from `null` to `27590706` (Chen 2017's PMID).
   - `citation_text` rewritten to cite Chen Y et al. 2017 with correct pages 13(4):399-405, and to quote the verbatim ACR sentence from the abstract.
   - Comment block above the priors explicitly notes the correction with cross-reference to this errata.
2. The new `scripts/verify_citations.py` would have caught this at commit time via its cross-resolver title check: Crossref's title for DOI 10.1016/j.jalz.2016.07.151 differs by more than the Jaccard threshold from any "Hayden" attribution; the verifier flags this as a `title` mismatch.

### Methodology change

Per the cumulative ERRATA E-2026-001/2/3/4 record, every citation in every rule pack and every transcription audit is now mechanically verified by `scripts/verify_citations.py` against Crossref + EUtils on every commit. The four cases that motivated this script — Marras (wrong everything), Chen-née-Hayden (wrong author, wrong pages), Karagianni (stray-period DOI typo), Therriault (phantom attribution) — would all have been caught at commit time had the verifier existed earlier.

### Acknowledgment

Same external audit that flagged Marras 2002. The auditor's specific signal — "the DOI resolves to a different paper" — is the strongest red flag in citation verification and is exactly what the Crossref/EUtils cross-resolver title check is designed to surface.

---

## E-2026-005 · ADNI canonical source switched from raw CSV DXSUM to R-format ADNIMERGE2/data/DXSUM.rda (fixed in v1.8.0)

**Discovered:** 2026-05-23 during v1.8 four-cohort triangulation lock.

### What was wrong

Pre-v1.8 documentation and a previous Claude session used the raw CSV
`All_Subjects_DXSUM_*.csv` as the ADNI longitudinal source. Cross-validation
on 28,352 matched (PTID, EXAMDATE) rows showed ~10–15% disagreement between
the raw CSV and the adjudicated R-format `ADNIMERGE2/data/DXSUM.rda`:

| CSV DIAGNOSIS | R = CN | R = MCI | R = Dementia |
|---|---:|---:|---:|
| 1 (CN-form) | 7,456 | 737 | 420 |
| 2 (MCI-form) | 702 | 6,902 | 240 |
| 3 (Dementia-form) | 420 | 252 | 3,123 |

The CSV contains raw clinical-form entries; the R file contains the adjudicated
final diagnosis after consensus review. For longitudinal cTCS audit, the
adjudicated final diagnosis is the clinically meaningful state.

### Numerical consequence

Using CSV DXSUM:
- n_trajectories = 3,685; n_transitions = 12,321; cTCS = 0.994970

Using canonical R-format DXSUM:
- n_trajectories = 3,762; n_transitions = 12,006; cTCS = 0.994575

The R-format reproduces the v1.7.13 published demo numbers
(`examples/adni_audit_demo.py`: 12,006 transitions, cTCS = 0.9946) exactly.

### What changed in v1.8.0

1. New canonical loader `adapter_adni_canonical.load_adni_trajectories` reads
   R-format DXSUM via pyreadr.
2. New regression test `test_real_adni_audit.py` locks audit_id
   `9e708f2ebd610e8ffe0abbc01d867ff34ff61fcd6aba14e2d6a293cd650e2b16`.
3. New documentation `docs/reproducibility/adni_source_decision.md`.
4. Datasheet Section A's stale ADNI audit_id `d344ec1a...` (from rule pack
   v1.1.0) replaced with v1.2.0 lock `9e708f2e...`.

### Acknowledgment

Internal verification caught this during the v1.8 pre-lock cross-tab review.

---

## E-2026-006 · NACC state mapping empirically validated, replacing earlier informal mappings (new in v1.8.0)

**Discovered:** 2026-05-23 during v1.8 NACC integration.

### What was wrong

An earlier prompt encoded the NACC state mapping as
`{1: CN, 3: CN, 4: MCI, 5: Dementia}`. This is wrong in two ways:

1. NACCUDSD=5 does not exist in the NACC UDS v73 data (highest valid code is 8).
2. NACCUDSD=3 modal CDRGLOB is 0.5 (87% of n=37,957 visits) → MCI, not CN.

The error was caught when applying the prompt's mapping produced
cTCS=0.976 — failing the four-cohort triangulation by ~0.015.

### Empirical validation

A NACCUDSD × CDRGLOB cross-tab on 214,976 visits established the correct
mapping:

| NACCUDSD | n | modal CDRGLOB | majority | State |
|---:|---:|---:|---:|---|
| 1 | 106,475 | 0.0 | 91.4% | CN |
| 2 | 9,575 | 0.5 | 65.9% | MCI |
| 3 | 37,957 | 0.5 | 86.7% | MCI |
| 4 | 60,945 | ≥1.0 (bucket) | 76.0% | AD |
| 8 | 24 | mixed | — | dropped |

NACCUDSD=4 is borderline under strict literal "single modal CDR with ≥50%
majority" (modal CDR=1.0 at 39.1%); under the clinically-meaningful "CDR
bucket ≥1.0" reading (76.0%, per Morris 1993 PMID 8232972), the 4 → AD
mapping is clearly justified.

### What changed in v1.8.0

1. New canonical adapter `adapter_nacc.load_nacc_trajectories` uses the
   empirical mapping with cross-tab evidence documented in the docstring.
2. New regression test `test_real_nacc_audit.py` locks audit_id
   `def60e6836a5a9feecc666dc558c5b115973f73dd65dd42ef13969819318754c`.
3. Datasheet Section G documents the empirical mapping + the NACCUDSD=4
   borderline finding.

### Acknowledgment

Internal verification during v1.8 NACC integration. The four-cohort
triangulation test (`test_four_cohort_triangulation.py`) would catch any
regression of this mapping at commit time.

## E-2026-007 · NACC slim-file recipe in `cohort_input_checksums.md` was not reproducible from documented columns (fixed in v1.8.1)

### Defect

Versions of `docs/reproducibility/cohort_input_checksums.md` up to and
including v1.8.0 listed `investigator_nacc73_slim.csv` with SHA-256
`7a349eb84920d366` as a canonical input, accompanied by a column whitelist
that explicitly included `NACCAPOE`.

The actual v1.8 NACC adapter's `DEFAULT_USECOLS` constant
(`src/neurotcs/input_contract/v1_1/adapters/adapter_nacc.py`) does NOT
include `NACCAPOE`. The slim file Maruf personally produced from the May
2026 freeze used a different (broader) column set than the one documented
in the manifest.

A reviewer following the documented recipe verbatim with
`pandas.read_csv(usecols=...)` and `to_csv(...)` would therefore produce a
file with a different SHA-256 than the manifest claimed.

### Detection

External audit reviewer flagged this on 2026-05-24 as Issue 2 of a 6-issue
audit. Independent reviewer reproduction of NACC against the full
`investigator_nacc73.csv` succeeded byte-exactly; the manifest discrepancy
did not affect the locked audit_id, which is computed from
adapter-emitted trajectories, not from the input file's SHA-256.

### Fix in v1.8.1

1. The slim file row is removed from `docs/reproducibility/cohort_input_checksums.md`.
2. The full file `investigator_nacc73.csv` (SHA-256 `a21a8537dc8ca679`) is
   the only canonical published input.
3. The manifest now points reviewers to derive the slim file themselves
   using the live `DEFAULT_USECOLS` constant, with code shown inline.
4. The audit invariant `def60e6836a5a9feecc666dc558c5b115973f73dd65dd42ef13969819318754c`
   continues to lock under v1.8.1 because it derives from the
   adapter-emitted trajectories, not from the input file checksum.

### Acknowledgment

External reviewer who ran the v1.8 reviewer-package protocol and identified
this in their FREE-RESPONSE diff section.

---

## E-2026-005 — Cohort audit_id supersession from v1.12.0 schema extension

**Date**: 2026-05-28
**Severity**: Process (not data, not science)
**Status**: Resolved in v1.19.0
**Related releases**: v1.7.13 (original lock), v1.12.0 (root-cause commit fbcfdfa), v1.19.0 (re-lock)

### Summary

The MIRIAD longitudinal, MIRIAD test-retest, MIRIAD fairness, and NACC
audit_ids (both v1 and v2 variants) locked in v1.7.13 / v1.8.1 drifted when
v1.12.0 (commit `fbcfdfa`) extended the Layer 1 rulepack schema to v1.4.0 by
adding `endorsing_bodies` to `ad/niaaa_2018.yaml` (Finding A from external
gap-check). The rulepack content SHA shifted from `1616F162...4B3F00` to
`F8FCD405...60E95AC`, propagating deterministically into every audit_id
that loads `ad/niaaa_2018`.

This was a documented, intentional, FDA-style regulatory metadata extension,
NOT a regression. The test constants for MIRIAD and NACC were not updated
at v1.12.0, and the drift went undetected through v1.13.0 → v1.18.0 because
the real-data locked-invariant tests skip when `NEUROTCS_MIRIAD_DIR` /
`NEUROTCS_NACC_CSV` env vars are unset (CI environment).

### Scientific invariants — unchanged

All scientific assertions (cTCS, n_subjects, n_transitions, n_flagged)
reproduce bit-exactly between v1.7.13/v1.8.1 and v1.19.0. This is verifiable
because the tests assert these quantities BEFORE the audit_id check; the
cTCS / n / flagged assertions did not fail.

- **MIRIAD longitudinal**: cTCS=0.9854 [BCa 95% CI 0.9715-0.9937], n=69 subjects, 454 transitions, 7 flagged (1.54%)
- **MIRIAD test-retest**: n=69 pairs, 0 flagged, cTCS=1.0000 (pipeline determinism)
- **NACC**: cTCS=0.991502 [BCa 95% CI 0.990833-0.992153], n=56,529 trajectories, 158,423 transitions, 1,217 flagged (0.768%)

### Supersession table (cryptographic continuity)

| Cohort | Pre-v1.12.0 audit_id (v1.7.13 lock) | Post-v1.12.0 audit_id (v1.19.0 lock) |
|---|---|---|
| MIRIAD longitudinal (v1) | `947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0` | `59ac763dfc4cd0098b33f13a2240171c888e5b4e99373d9b8f974d716647d96a` |
| MIRIAD longitudinal (v2) | `aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da` | `c34b37863dac549d2aec8298453b9bc1ef2b0a8f719384249786d55f6e10da08` |
| MIRIAD test-retest (v1) | `804303993ff5c9134b5f4dfa8919fc6600d03a86081cedb02227ef5845784e85` | `94126769ef6c468e7290ff15aaedaa8ba8874a58848545a08208c5f769730454` |
| MIRIAD test-retest (v2) | `dcf8b7de3ff9019e9cda703064039e3a71193566d1f5082ce96646188fd52fc4` | `2cd85d3b705fde826917dd72e3fec6997e5d3d25a06ae5c06ce6125c1805249e` |
| MIRIAD fairness (v1) | `947ab24ef83490e5ef74a0ef254f0553b512736259ab05b5ee917aa7fe3989e0` | `59ac763dfc4cd0098b33f13a2240171c888e5b4e99373d9b8f974d716647d96a` |
| MIRIAD fairness (v2) | `aa178e836e8a3824951ba3de2ee7e22e9dc496960c9999be242770730141f4da` | `c34b37863dac549d2aec8298453b9bc1ef2b0a8f719384249786d55f6e10da08` |
| NACC (v1) | `def60e6836a5a9feecc666dc558c5b115973f73dd65dd42ef13969819318754c` | `f233935d7a1c2d72702adc7627671d8785313ab446607fa309bb2f5a48129187` |
| NACC (v2) | `9c002cf653f8187c9c190293999b861e677f95ded8e1a4501fa47d928dac8648` | `8503a3107cc8a7f68490d33b51c07d8ef54be5fa6a835c700cbc0775055cc90c` |

OASIS-3 (`fa448b8f...` / cTCS=0.9942) is NOT affected because its test was
locked at v1.8.0 (post-v1.12.0 reasoning), and re-validated against
`ad/niaaa_2018@1.3.0`.

ADNI: real-data test status pending re-verification once
`NEUROTCS_ADNI_DXSUM_RDA` environment variable is set on the
verification host.

### Old audit_ids preserved as `*_V1_7_13` / `*_V1_8_1` constants

Per the precedent set by ERRATA E-2026-001 (OASIS-3 v1.5.0 re-lock, which
preserved `EXPECTED_AUDIT_ID_V1_3_0` for traceability), each affected test
file now carries both the old and new locked constants. This makes the
cryptographic continuity chain machine-readable and grep-able.

### Process improvement

v1.19.0 introduces a documented requirement: real-data locked-invariant
tests MUST pass on the developer's local machine before any release tag
is pushed when MIRIAD/NACC env vars are set. The skip-when-env-unset
behavior is preserved for CI, but a release-time gate is added to
Deploy-NeuroTCS-v1.X.0.ps1 (gate 11+) checking real-data invariants
when env vars are present. This prevents the same gap recurring.

### Verification

To verify this ERRATA on your own machine:

```powershell
$env:NEUROTCS_MIRIAD_DIR = "<path-to-MIRIAD>"
$env:NEUROTCS_NACC_CSV = "<path-to-investigator_nacc73.csv>"
pytest tests/audit_core/test_real_nacc_audit.py `
       tests/audit_core/test_real_miriad_audit.py `
       tests/audit_core/test_real_miriad_fairness_audit.py -v
```

Expected: 5 PASSED. The v1 audit_id, v2 audit_id, cTCS point estimate,
BCa CI, n_subjects, n_transitions, and n_flagged all reproduce bit-exactly.


### E-2026-005 CORRECTION (v1.19.1, 2026-05-28)

**The v1.19.0 statement that "OASIS-3 is NOT affected" was WRONG.**

Direct measurement in the v1.19.1 session proved OASIS-3 drifted by the
exact same mechanism as MIRIAD and NACC: the v1.12.0 endorsing_bodies
schema extension changed the canonical SHA of ad/niaaa_2018 (the rule pack
SHA is an input to audit_id per audit_core/audit.py line 10:
"audit_id: SHA-256 over (rule pack SHA, score vectors, B, seed)"), and
OASIS-3 loads the same rule pack.

The v1.19.0 claim was based on an UNVERIFIED assumption that OASIS-3 was
locked post-v1.12.0. It was not. The error was compounded by a latent
test defect (see below) that masked the drift.

**Why the drift was invisible until v1.19.1:**
The OASIS-3 locked-invariant test used a bare `return` (not `pytest.skip()`)
when the data file was absent from its default search path. pytest counts a
function that returns without asserting as PASSED. So whenever
NEUROTCS_OASIS3_CDR was unset, the test reported GREEN while asserting
nothing. The v1.18.0 deploy run and earlier CI showed OASIS-3 "passing"
because the file was never found at the hardcoded search path, so the
assertions never executed.

**OASIS-3 supersession (added to the E-2026-005 table):**

| Cohort | Pre-v1.12.0 (v1.8.0/v1.8.1 lock) | Post-v1.12.0 (v1.19.1 lock) |
|---|---|---|
| OASIS-3 (v1) | `766ffc5f26eae47fb95eddd21e33bbecb798989304ed17584db15aa0d4740f90` | `77f1945358e6b1db8c462e69e0d7f7d8d9dc1aba6d67909eddae34273785a11d` |
| OASIS-3 (v2) | `265d99ee07172a645d566491401632d295e1a782922866c7dda10334f46f19c5` | `b3e3f8f8c790509c86aaf719752f5fb364d2be717abbf03fb996bffb708c53e1` |

**OASIS-3 scientific invariants — unchanged (bit-exact):**
cTCS=0.994191 [BCa 95% CI 0.990264-0.996405], n_scored=1247,
1377 trajectories, 7248 transitions, 30 flagged (0.414%).

**Two fixes shipped in v1.19.1:**
1. OASIS-3 audit_id v1 + v2 re-locked (old preserved as
   EXPECTED_AUDIT_ID_V1_8_0 / EXPECTED_AUDIT_ID_V2_V1_8_1).
2. The silent `return` replaced with `pytest.skip()` so absent data yields
   an honest SKIP, never a false PASS. This was the more serious defect:
   a locked-invariant test that reports green while testing nothing.

**ADNI status:** still unverified (NEUROTCS_ADNI_DXSUM_RDA unset). By the
same mechanism, ADNI almost certainly also drifted and will need the same
re-lock once DXSUM.rda is available. Tracked as an open item.

**Lesson for the project:** the v1.19.0 ERRATA made a claim about OASIS-3
without measuring it. The correct discipline -- applied in v1.19.1 -- is to
measure every cohort's live audit_id against the current rule pack before
asserting which are or are not affected. All four available cohorts
(MIRIAD x3, NACC, OASIS-3) are now measured and re-locked; only ADNI
remains pending data.


---

## E-2026-006 — Structural fix: audit_id now hashes scientific content only (fixed in v1.20.0)

**Discovered:** 2026-05-28
**Fixed in:** v1.20.0
**Affected versions:** v1.12.0 through v1.19.1 (audit_id values only)
**Severity:** Reproducibility fingerprint only. **No scientific result changed** — cTCS, n, transitions, and flagged counts are byte-identical across all six cohorts before and after. Every cohort's audit_id changed once more, to a permanent metadata-independent value.

### Root cause (the disease behind E-2026-005)

E-2026-005 re-locked six cohort audit_ids after v1.12.0's `endorsing_bodies`
schema extension shifted the `ad/niaaa_2018` canonical SHA. That treated the
symptom. The underlying defect: `_canonical_serialize` (src/neurotcs/rulepack/loader.py)
hashed `rp.model_dump(mode="json")` — the ENTIRE RulePack object, including 14
metadata fields the scoring engine never reads (endorsing_bodies, effective_date,
schema_version, ruleset_version, rulepack_id, reviewers, anchor_citation,
framework_name, disease_domain, clinical_source_authority, transcribed_by,
status, notes, override_allowed_default). Any change to those — adding an
endorsement, refreshing a date, bumping a version — drifted every cohort
audit_id, even though the audit computation was untouched.

Proven by direct field diff (v1.11.0 pre-drift vs current): every scientific
field (state_space, admissible_transitions, inadmissible_transitions,
transition_priors) is byte-identical; only metadata differs.

### The fix

`_canonical_serialize` now hashes ONLY the four fields the scoring engine reads:
`state_space`, `admissible_transitions`, `inadmissible_transitions`,
`transition_priors`. Metadata is excluded from the audit_id by construction.
The rule-pack canonical SHA changed:

  aaac92fb901d13ea905e25d8dde5b31897cf425cb6600f6f87c72b63ed479081  (metadata-polluted, v1.12.0-v1.19.1)
  -> 97811e3f1a145e47393aa2568065303c594ffa20cc81a514ced027a23a81336b  (scientific content only, v1.20.0+)

From v1.20.0, metadata changes (endorsements, dates, versions, citations,
reviewers) can NEVER again drift a cohort audit_id.

### Two-directional proof (the executable guarantee)

tests/rulepack/test_canonical_serialization_partition.py proves the partition
in both directions:
- Mutating any of the 14 metadata fields does NOT change the canonical SHA.
- Mutating any of the 4 scientific fields DOES change it.
- A helper-vs-production check confirms the proof exercises the real serializer.
All four assertions pass. The if-and-only-if contract (same science <-> same
audit_id) is now machine-verified.

### Six-cohort supersession table (v1.19.x metadata-polluted -> v1.20.0 permanent)

All scientific invariants UNCHANGED; only audit_id values move.

NACC
  v1: f233935d7a1c2d72702adc7627671d8785313ab446607fa309bb2f5a48129187
   -> 58329c656e5ae14c8c6af496a6b526c2f93d317379ba3ffd145776e1cfcf07a9
  v2: 8503a3107cc8a7f68490d33b51c07d8ef54be5fa6a835c700cbc0775055cc90c
   -> 74aa4b64bcfc8004a10d1fe418ac72df98053e98ad8da68dfaa72a87ee2dc0ec

OASIS-3
  v1: 77f1945358e6b1db8c462e69e0d7f7d8d9dc1aba6d67909eddae34273785a11d
   -> 92df5429ed8439f84a9a65d18b1c489a2b50107facc08e3e59538948c9ad6478
  v2: b3e3f8f8c790509c86aaf719752f5fb364d2be717abbf03fb996bffb708c53e1
   -> fed6c9b880fee9c4e832978dc5224ec90994b5995b9530f18a377fe4ee4f5eab

ADNI (locked for the first time to a permanent value; no interim v1.19.2 lock)
  v1: 9e708f2ebd610e8ffe0abbc01d867ff34ff61fcd6aba14e2d6a293cd650e2b16
   -> 7a973f7b57a91f7cf0af796fd9f69552e14b57aa91f4241fabd5262436588f08
  v2: 7d08a227b6fe80b53adc0291fe9cda26bf4f1056b1a04cb47fd2afc63d0a7334
   -> dda642ff2e5c67b522f534d330d25eb59175eccc0f1c9d7e504b871dc03e0b9d

MIRIAD longitudinal
  v1: 59ac763dfc4cd0098b33f13a2240171c888e5b4e99373d9b8f974d716647d96a
   -> abda26cb4f77c4f5c7644b421b459b79dfa5caf58f32d60860736c6a2c9ee57f
  v2: c34b37863dac549d2aec8298453b9bc1ef2b0a8f719384249786d55f6e10da08
   -> 1aeb56ce5a88d9f74e7b6942ca4b3e2329fd918d96264b4df062744247cf1a80

MIRIAD test-retest
  v1: 94126769ef6c468e7290ff15aaedaa8ba8874a58848545a08208c5f769730454
   -> 4de7f7111aedea86636dae2f81a768a1013849e5949a21062e3bdbd99f499136
  v2: 2cd85d3b705fde826917dd72e3fec6997e5d3d25a06ae5c06ce6125c1805249e
   -> fa30cd364d9239a5fbc5774182a4d5093189605c10d5a1abe956653dd76afa1f

MIRIAD fairness (downstream of longitudinal; equals MIRIAD longitudinal)
  v1: -> abda26cb4f77c4f5c7644b421b459b79dfa5caf58f32d60860736c6a2c9ee57f
  v2: -> 1aeb56ce5a88d9f74e7b6942ca4b3e2329fd918d96264b4df062744247cf1a80

Scientific invariants (unchanged): NACC cTCS=0.991502, n=56529, 158423 trans,
1217 flagged; OASIS-3 cTCS=0.994191, n_scored=1247, 7248 trans, 30 flagged;
ADNI cTCS=0.994575, n_scored=2958, 12006 trans, 65 flagged; MIRIAD long
cTCS=0.985369, n=69, 454 trans, 7 flagged; MIRIAD test-retest 69 pairs,
0 flagged.

### Detection-gap closure (why this hid for six versions)

The drift survived v1.13-v1.19 because CI runs framework-only pytest with the
real-cohort locked-invariant tests SKIPPED — they need NEUROTCS_* env vars CI
never sets, so no locked fingerprint was ever checked in CI. v1.20.0 adds
tests/audit_core/test_synthetic_ci_invariant.py: a deterministic synthetic
cohort with a locked audit_id that runs on EVERY CI invocation, no env vars.
Any future fingerprint drift — serializer, scoring kernel, or RNG-affecting
dependency upgrade — now turns CI red on the next push.

### Honest scope statement

This fix makes audit_id permanently immune to METADATA drift. It does NOT claim
immunity to all change: a genuine scientific rule change SHOULD drift the
fingerprint (correct behavior), and engine/dependency drift remains possible but
is now caught loudly by the synthetic sentinel. The guarantee is not "never
drifts" but "never drifts silently, and never drifts for non-scientific reasons."

### Methodology change (cumulative E-2026-001 through E-2026-006 lessons)

7. (E-2026-006) The audit_id canonical serialization must hash scientific
   content only; metadata is reported as provenance but excluded from the
   fingerprint. Enforced by the two-directional partition test.
8. (E-2026-006) Every release must run at least one locked-fingerprint test in
   CI with no external-data dependency, so reproducibility drift is caught on
   every push rather than only in local real-data runs.

Same as prior errata: the structural root cause was found by Dr. Salokhiddinov
pushing for "world-class, no partial fix" — declining to accept the symptomatic
re-lock and demanding the underlying defect be traced and fixed permanently.

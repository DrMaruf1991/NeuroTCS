# Transcription Audit — `ad/aa_2024_trac@1.0.0`

**Pack:** `ad/aa_2024_trac@1.0.0`
**Anchor publication:** La Joie R, Cummings JL, Dage JL, et al. **Treatment-related amyloid clearance (TRAC): a framework to characterize patients in the era of anti-amyloid therapies.** *Alzheimer's & Dementia* 2025;21(11):e70997. **DOI: 10.1002/alz.70997**. **PMCID: PMC12657122**. Received 22 July 2025, accepted 18 November 2025, published online ~26 November 2025.

**Schema:** v1.2.0 (uses new `required_conditions` + `conditions_evaluated_at` fields).

**Transcribed by:** Salokhiddinov M, MD PhD, ESOR-BRACCO-ESNR Neuroimaging Fellow, KIUT, Uzbekistan.

**Methodology:** Every numerical threshold, every state definition, and every admissibility rule below was verified against the primary La Joie 2025 publication (and, where it cites other regulatory sources, against the FDA prescribing information for those drugs). No claim in this pack relies on language-model memory of FDA approval dates, DOIs, or quantitative thresholds.

---

## Verified evidence base

| Item | Source | Verified value |
|---|---|---|
| Lecanemab (Leqembi) accelerated approval | Eisai/Biogen press releases; FDA | **2023-01-06** |
| Lecanemab traditional/full approval | Eisai/Biogen press release; FDA | **2023-07-06** |
| Lecanemab maintenance-dosing approval | AJMC, Eisai press release | **2025-01-26** |
| Donanemab (Kisunla, donanemab-azbt) full approval | Eli Lilly press release; FDA; Drugs.com | **2024-07-02** |
| Donanemab modified-titration label update (TRAILBLAZER-ALZ 6) | Eli Lilly press release | **2025-07-09** |
| Jack 2024 AA Revised Criteria | PubMed | **PMID 38934362, PMCID PMC11350039, DOI 10.1002/alz.13859**, *Alz & Dem* **2024 Aug;20(8):5143-5169** (epub 2024-06-27) |
| La Joie 2025 TRAC | Alz-journals; PMC | **DOI 10.1002/alz.70997, PMCID PMC12657122**, *Alz & Dem* **2025;21(11):e70997** |
| Lecanemab Centiloid criteria | La Joie 2025, footnote on trial interruption rules | 1 scan <11 CL OR 2 consecutive <25 CL |
| Donanemab Centiloid criterion (fibrillar clearance) | La Joie 2025, footnote on TRAILBLAZER-ALZ criteria | <24.1 CL |

---

## State-space transcription

| YAML state | Source phrase (La Joie 2025) |
|---|---|
| `A_neg` | "amyloid PET below the positivity threshold" (baseline / never-treated) |
| `A_pos` | "pretreatment biomarker confirmation of cerebral Aβ deposition" |
| `Partial_TRAC` | "Partial TRAC means that PET levels dropped significantly but remain above the threshold" |
| `Full_TRAC` | "Full TRAC indicates that PET levels have dropped below a predetermined positivity threshold" |

---

## Admissible-transition transcription

For each admissible transition the YAML encodes, the table below shows the directly-corresponding statement from La Joie 2025 (or Jack 2024 for the one natural-progression transition) plus the exact section pointer.

### A1. `A_neg → A_pos` (natural amyloid accumulation, no treatment required)

- **Source:** Jack CR Jr et al. 2024 AA Revised Criteria, §3 "Integrated biological-clinical staging", Table 6 (Stage 0 → Stage 1 transition).
- **Quantitative anchor:** annual conversion rate ≈ 0.5–2% in clinic-attending cohorts (well-established in NIA-AA framework).
- **Time window:** `min_delta_t_days = 365.0` (measurement-noise floor; clinically meaningful amyloid accumulation observed across years).
- **Treatment dependency:** None.

### A2. `A_pos → Partial_TRAC`

- **Source:** La Joie 2025 §2 'TRAC framework definition': "applies to individuals with (1) pretreatment biomarker confirmation of cerebral Aβ deposition, (2) treatment with an Aβ-targeting therapy, and (3) a follow-up biomarker test indicative of partial or full clearance of Aβ deposits".
- **Section pointer:** La Joie 2025 §2 + Figure 1 right panel ([18F]Florbetaben trajectories).
- **Required conditions:** `treatment_status ∈ {anti_amyloid_active, anti_amyloid_discontinued}`.
- **`conditions_evaluated_at: to_visit`** — the follow-up scan proves the partial clearance, so treatment status is checked at the to-visit (the scan showing the drop).

### A3. `A_pos → Full_TRAC`

- **Source:** La Joie 2025: "Full TRAC indicates that PET levels have dropped below a predetermined positivity threshold"; drug-specific thresholds: lecanemab interruption criterion 1 scan <11 CL OR 2 consecutive <25 CL; donanemab fibrillar clearance criterion <24.1 CL.
- **Section pointer:** La Joie 2025 §2 + footnote on TRAILBLAZER-ALZ centiloid criteria.
- **Required conditions:** same as A2.
- **Quantitative threshold enforcement:** the Centiloid threshold is enforced upstream by the input-contract v1.1 biomarker pipeline (where the continuous Centiloid value is mapped to A+/A− and Partial/Full TRAC). The rule pack only encodes the admissibility *given* that the input pipeline has correctly labeled the state.

### A4. `Partial_TRAC → Full_TRAC`

- **Source:** La Joie 2025 §4 'Dose-response and treatment duration': "Within a given trial, higher doses and longer treatment duration were associated with higher rates of full TRAC".
- **Required conditions:** continued or recent anti-Aβ therapy.

### A5. `Full_TRAC → Partial_TRAC` (re-accumulation after discontinuation)

- **Source:** La Joie 2025 §5 "Post-treatment surveillance and label persistence" — re-accumulation after discontinuation is biologically expected; rate slower than untreated natural accumulation in some studies.
- **Required conditions:** `treatment_status = anti_amyloid_discontinued`.
- **Time window:** `min_delta_t_days = 365.0`.

### A6. `Partial_TRAC → A_pos` (full re-accumulation)

- **Source:** La Joie 2025 §5 — re-accumulation to pretreatment A+ levels may occur over years. Historical TRAC label persists (relevant for retreatment decisions and trial eligibility).
- **Required conditions:** `treatment_status = anti_amyloid_discontinued`.
- **Time window:** `min_delta_t_days = 365.0`.

---

## Inadmissible-transition transcription

### I1. `A_pos → A_neg` (spontaneous clearance, no anti-Aβ therapy)

- **Source:** La Joie 2025 §1–2: "TRAC designates biomarker-defined pharmacodynamic changes" that apply specifically to patients on "treatment with an Aβ-targeting therapy". Untreated clearance is not in TRAC's scope.
- **Reason:** Spontaneous amyloid clearance is biologically implausible. Such transitions reflect measurement error, mislabeling, or unreported anti-amyloid treatment. Should be flagged.

### I2. `A_neg → Partial_TRAC`

- **Reason:** Partial TRAC requires pretreatment A+ baseline per La Joie 2025 criterion (1) of the three required conditions. An A-negative baseline patient cannot enter Partial_TRAC.

### I3. `A_neg → Full_TRAC`

- **Reason:** Same as I2 — both partial and full TRAC require pretreatment A+ baseline.

---

## Priors

`transition_priors: []` — empty in v1.0.0. La Joie 2025 proposes the framework but does not publish per-state annual transition probabilities (real-world data from anti-Aβ therapy cohorts is still accumulating). Future versions will populate priors from:

1. CLARITY-AD final follow-up (lecanemab) — when RWD-quality transition rates are publishable.
2. TRAILBLAZER-ALZ 2 long-term extension (donanemab) — same.
3. ALZ-NET registry data — Alzheimer's Association real-world cohort.

Without priors, pTCS will report "unavailable" when this pack is used; cTCS and uTCS work fully.

---

## Verification protocol

A reviewer can verify this transcription end-to-end by:

1. Opening La Joie 2025 from DOI 10.1002/alz.70997 (open access via PMC12657122).
2. For each row above, reading the cited section and checking that the YAML encoding faithfully reflects the published rule.
3. Running `python tests/rulepack/test_rulepack.py` to confirm all conditional-admissibility behaviors fire correctly on synthetic data.

The pack's canonical SHA-256 is logged at load time so any drift between the published pack and a locally edited version is detected automatically.

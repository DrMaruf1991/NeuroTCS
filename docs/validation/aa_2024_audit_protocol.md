# AA-2024 Audit Protocol

**Document version:** 1.0 (locked v1.7.13)
**Companion rule pack:** `ad/aa_2024@2.0.0`, schema 1.3.0, SHA `1393ceb489d774c059cc30f500335e29622880e347a8081854f1c461f05c47e2`
**Source paper:** Jack CR Jr et al., *Alzheimer's & Dementia* 2024;20(8):5143-5169. DOI [10.1002/alz.13859](https://doi.org/10.1002/alz.13859). PMID [38934362](https://pubmed.ncbi.nlm.nih.gov/38934362/). PMC [PMC11350039](https://pmc.ncbi.nlm.nih.gov/articles/PMC11350039/) (open access CC BY-NC-ND 4.0).

This document specifies the end-to-end workflow for running the AA-2024 (Jack 2024 Table 7) staging audit on real cohort data, including the three external parameters that the audit caller must supply.

## 1. State space recap

The rule pack encodes Jack 2024 Table 7 verbatim:

| Biological stage \ Clinical stage | 0 | 1 | 2 | 3 | 4–6 |
| --- | --- | --- | --- | --- | --- |
| (no biology — ADAD/DSAD pre-A+) | `Stage_0` | — | — | — | — |
| **A** (initial: A+T2−) | — | `Stage_1A` | `Stage_2A` | `Stage_3A` | `Stage_4-6A` |
| **B** (early: A+T2MTL+) | — | `Stage_1B` | `Stage_2B` | `Stage_3B` | `Stage_4-6B` |
| **C** (intermediate: A+T2MOD+) | — | `Stage_1C` | `Stage_2C` | `Stage_3C` | `Stage_4-6C` |
| **D** (advanced: A+T2HIGH+) | — | `Stage_1D` | `Stage_2D` | `Stage_3D` | `Stage_4-6D` |

The diagonal `Stage_1A → Stage_2B → Stage_3C → Stage_4-6D` is the "typical expected progression trajectory" per Table 7 §Note. Off-diagonal cells are biologically plausible per Figures 1B (copathology left-shift) and 1C (cognitive reserve right-shift).

## 2. External parameters (caller-supplied)

Per Jack 2024 §4.6 (verbatim): *"the distinction between moderate (stage C) and high (stage D) neocortical tau uptake could be operationalized in different ways. Methods for quantification of tau PET is an area of active research, and selecting the best cutpoint to distinguish moderate versus high uptake will be informed by upcoming research findings."*

The paper deliberately declines to commit to a single cutpoint methodology. Encoding a fabricated cutpoint in the rule pack would violate the no-hallucination rule. The cutpoints are therefore caller-supplied at audit time, declared in the audit report's metadata. **Fail-closed policy:** if a required parameter is not supplied, the affected transitions cannot be evaluated and the audit emits a warning.

### 2.1 `tau_pet_mod_vs_high_cutpoint` (required, fail-closed)

The SUVR threshold distinguishing moderate (stage C) from high (stage D) neocortical tau PET uptake. Units: SUVR.

**Acceptable sources:**

| Source | Reference | Notes |
| --- | --- | --- |
| La Joie 2019 | Alzheimer's & Dementia 15:205-216. DOI [10.1016/j.jalz.2018.09.001](https://doi.org/10.1016/j.jalz.2018.09.001). PMID [30347188](https://pubmed.ncbi.nlm.nih.gov/30347188/). | Centiloid + PIB-PET tau cutpoints validated against autopsy. |
| CenTauR scale (Villemagne 2023) | *Alzheimer's Research & Therapy*. | Tau-PET cross-tracer harmonization analogous to Centiloid for amyloid. |
| Ossenkoppele 2022 | *Nature Medicine* 28:2381-2387. DOI [10.1038/s41591-022-02049-x](https://doi.org/10.1038/s41591-022-02049-x). PMID [36357681](https://pubmed.ncbi.nlm.nih.gov/36357681/). | Meta-analysis using moderate/high neocortical stratification. HR 1.5 / 5.6 / 39.9 across A+T2−/A+T2MTL+/A+T2NEO+. |
| Local site methodology | Institutional radiopharmacology paper or guideline | Acceptable provided the methodology is peer-reviewed and cited in the audit report's `external_parameter_sources` field. |

### 2.2 `neocortical_meta_roi_definition` (required, NOT fail-closed)

The anatomical definition of the neocortical meta-ROI used for tau PET quantification. Jack 2024 §4.6 explicitly does not prescribe an inflexible ROI list, but specifies that "sampling of at least some of these areas should be included in a neocortical tau PET meta-ROI": inferior + lateral temporal + inferior + medial parietal lobes.

**Acceptable choices:**

- Inferior + lateral temporal + inferior + medial parietal (Jack 2024 §4.6 listed regions).
- Braak-region-based composite (citations 107, 110, 116, 127, 129, 142 in the paper).
- Local site methodology with peer-reviewed reference.

### 2.3 `amyloid_pet_positivity_threshold` (required, fail-closed)

The threshold defining amyloid PET positivity (A+ vs A−). Jack 2024 §3.1 references Centiloid ≥ 25 for the Mayo Clinic cohort, but does not prescribe a single cutoff. Per §4.6: *"the approach to determining A+ versus A− may need special consideration in ADAD and DSAD"* (florid striatal uptake patterns differ in genetic AD).

**Acceptable sources:**

- Centiloid ≥ 20–25 for sporadic AD (Klunk 2015; Jack 2024 §3.1 cites Centiloid ≥ 25).
- Tracer-specific SUVR cutoff (florbetapir, florbetaben, flutemetamol) per FDA package insert.
- Visual read positive (FDA-approved reading method for amyloid PET ligands).
- ADAD/DSAD-specific cutoff per local methodology.

## 3. Cohort filter (amyloid-positive only)

Per Jack 2024 §4 (verbatim): *"Staging of AD applies only to individuals in whom the disease has been diagnosed by means of Core 1 biomarkers and does not apply to individuals who are not in the AD pathway."*

The AA-2024 rule pack must be run only on subjects who are amyloid-positive (Core 1+). Filter your ADNI cohort to retain only subjects whose amyloid PET (or biofluid Core 1 surrogate) crosses the `amyloid_pet_positivity_threshold` you supplied. Amyloid-negative subjects are not in the AD pathway and AA-2024 staging does not apply.

## 4. Per-visit state derivation (production ADNI adapter)

For each (subject, visit) pair, derive the integrated alphanumeric state as follows:

**Step 1 — biological axis (A/B/C/D)**

| Amyloid PET | Tau PET medial temporal | Tau PET moderate neocortical | Tau PET high neocortical | Biological stage |
| --- | --- | --- | --- | --- |
| − | (any) | (any) | (any) | (NOT in AD pathway — exclude) |
| + | − | − | − | A (`A+T2-`) |
| + | + | − | − | B (`A+T2MTL+`) |
| + | + | + | − | C (`A+T2MOD+`) |
| + | + | + | + | D (`A+T2HIGH+`) |

This is Jack 2024 Table 4 verbatim. The "moderate" and "high" thresholds come from `tau_pet_mod_vs_high_cutpoint`; the "amyloid positive" threshold comes from `amyloid_pet_positivity_threshold`.

**Step 2 — clinical axis (0/1/2/3/4-6)**

| Subject status | Clinical stage |
| --- | --- |
| Asymptomatic, deterministic gene carrier (ADAD or DSAD), biomarker-negative | 0 |
| Asymptomatic, biomarker-positive | 1 |
| Transitional decline (subtle, persistent ≥ 6 months; Table 6 stage 2) | 2 |
| Cognitive impairment with early functional impact (MCI-equivalent; Table 6 stage 3) | 3 |
| Dementia (mild → moderate → severe; Table 6 stages 4/5/6 collapsed) | 4-6 |

Map ADNI's DXSUM/CDR data to this scheme:
- ADNI DX = `CN` and amyloid-positive → clinical stage 1.
- ADNI DX = `CN` and amyloid-positive with subjective decline that meets Table 6 stage 2 → clinical stage 2 (persistence verified ≥ 180 days from baseline).
- ADNI DX = `MCI` and amyloid-positive → clinical stage 3.
- ADNI DX = `Dementia` and amyloid-positive → clinical stage 4-6.

**Step 3 — combine into Table 7 cell**

The state name is `Stage_{clinical}{biological}` (e.g., `Stage_2B`, `Stage_4-6D`). Stage 0 is named `Stage_0` (no biological sub-stage by definition).

## 5. Running the audit

Once trajectories are built with the alphanumeric states above:

```python
from neurotcs import audit, load_rulepack

pack = load_rulepack("ad/aa_2024")
result = audit(
    trajectories=adni_amyloid_positive_trajectories,
    pack=pack,
    bootstrap_B=10_000,
    seed=42,
    ci_method="bca",
    return_per_transition=True,
    external_parameter_sources={
        "tau_pet_mod_vs_high_cutpoint": {
            "value": 2.30,                          # caller's chosen SUVR threshold
            "citation_doi": "10.1038/s41591-022-02049-x",
            "citation_pmid": "36357681",
            "rationale": "Ossenkoppele 2022 Nature Medicine moderate/high cutpoints",
        },
        "neocortical_meta_roi_definition": {
            "value": "inferior+lateral temporal + inferior+medial parietal",
            "rationale": "Jack 2024 §4.6 listed regions",
        },
        "amyloid_pet_positivity_threshold": {
            "value": 25.0,
            "units": "Centiloid",
            "citation_doi": "10.1002/alz.13859",
            "rationale": "Jack 2024 §3.1 (Mayo Clinic cohort cutoff)",
        },
    },
)
```

(Note: at v1.7.13 the `external_parameter_sources` argument is informational metadata appearing in the audit report; the rule pack engine does not yet enforce a fail-closed runtime check on it. Adding strict runtime enforcement is tracked for v1.7.14.)

## 6. Expected outputs

- **cTCS**: citation-locked admissibility audit on the full 17-state space. This is fully functional in v1.7.13.
- **pTCS**: unavailable in v1.7.13 because the rule pack's `transition_priors` is empty. Multi-axis (biological + clinical) longitudinal cohort priors are not yet published in the form needed for the synthesizer. For pTCS audits, use the NIA-AA 2018 pack (`ad/niaaa_2018@1.2.0`) which has Salemme 2025 priors over the single-axis CN/MCI/AD state space.
- **per-stratum fairness**: routed through `cohort_fairness_audit(result)` exactly as for the NIA-AA 2018 pack; the FUTURE-AI Panel B.4.4 mechanism is state-space-agnostic.

## 7. TRAC-treated subjects

Subjects on anti-amyloid immunotherapy who experience treatment-related amyloid clearance (TRAC) move out of the natural-history A→B→C→D unidirectional sequence. They are handled by the companion pack `ad/aa_2024_trac@1.0.0` (schema 1.2.0), not by this main pack.

Per Jack 2024 §9 (verbatim): *"The underlying AD pathophysiologic process is therefore still active in an individual who has had fibrillar amyloid removed to below PET detection levels."* TRAC subjects do not return to Stage 0 even if amyloid PET reverts to subdetection.

## 8. Verification checklist

Before publishing AA-2024 audit results, verify:

- [ ] The cohort is filtered to amyloid-positive subjects only (§3 of this protocol).
- [ ] `tau_pet_mod_vs_high_cutpoint` is documented with a peer-reviewed citation.
- [ ] `neocortical_meta_roi_definition` is documented.
- [ ] `amyloid_pet_positivity_threshold` is documented with FDA-label or peer-reviewed citation.
- [ ] TRAC-treated subjects (if any) are routed through `ad/aa_2024_trac`, not `ad/aa_2024`.
- [ ] The audit report's metadata contains the three external parameters and their sources.
- [ ] The reported cTCS is paired with the rulepack SHA-256 `1393ceb489d774c0...` for reproducibility.

## 9. Provenance

- Source: Jack 2024 PMC11350039 fetched 2026-05-18 via NeuroTCS v1.7.13 build.
- Transcription attested by Salokhiddinov M, MD PhD, ESOR-BRACCO-ESNR Neuroimaging Fellow, KIUT Tashkent.
- License of source: CC BY-NC-ND 4.0 (open access).
- No fabricated cutpoints, no inferred thresholds: every numerical parameter is caller-supplied with citation.

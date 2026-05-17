# NeuroTCS

**Citation-locked, fail-closed longitudinal medical AI audit framework.**

[![CI](https://github.com/DrMaruf1991/NeuroTCS/actions/workflows/ci.yml/badge.svg)](https://github.com/DrMaruf1991/NeuroTCS/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version 1.4.0](https://img.shields.io/badge/version-1.4.0-success.svg)](CHANGELOG.md)
[![Tests 136/136](https://img.shields.io/badge/tests-136%2F136-success.svg)](tests/)
[![Spec v1.6 FINAL](https://img.shields.io/badge/spec-v1.6_FINAL-success.svg)](docs/spec/temporalmetric_v1.6_FINAL.md)

NeuroTCS audits the temporal coherence of longitudinal medical AI predictions against internationally endorsed published clinical guidelines. It answers the question regulators, hospitals, and trialists ask first: *does this AI model's visit-to-visit prediction trajectory obey the clinical biology it claims to predict?*

The framework is anchored on Dr. Marufjon Salokhiddinov's ASNR 2026 presentation (Austin, May 2026) and the temporalmetric v1.6 FINAL technical specification.

**External replication achieved (v1.3.0, Aim 2).** The AD instantiation has been validated on **two independent cohorts**:

| Cohort | Subjects | Transitions | Flagged | cTCS | audit_id |
|---|---|---|---|---|---|
| ADNI (Aim 1) | 2,958 | 12,006 | 65 (0.54 %) | **0.9946** | `d344ec1a...` |
| OASIS-3 (Aim 2) | 1,247 | 7,248 | 30 (0.41 %) | **0.9942** | `96d942e4...` |

ΔcTCS between cohorts = **0.0004**. Confidence intervals (BCa 95 %) overlap almost completely. The cTCS metric generalizes across cohorts collected by different institutions, in different decades, with different recruitment criteria. Full validation report at [`docs/validation/aim2_oasis3_external_replication.md`](docs/validation/aim2_oasis3_external_replication.md).

---

## What's in this repo

NeuroTCS is the umbrella for seven engineering pieces. Pieces 1–3 are shipped in v1.1.0; pieces 4–7 are planned per the spec roadmap.

| Piece | Subpackage | Status | Description |
|---|---|---|---|
| 1 | `neurotcs.input_contract.v1_0` | ✅ shipped | Categorical input contract (8-step validation, fail-closed) |
| 2 | `neurotcs.input_contract.v1_1` | ✅ shipped | Continuous-biomarker contract with UCUM unit enforcement |
| 3 | `neurotcs.rulepack` | ✅ shipped | 8 production rule packs across 6 disease domains |
| 4 | `neurotcs.audit_core` | ✅ shipped | cTCS / pTCS / uTCS engine + cluster bootstrap + BCa + Huber |
| 5 | `neurotcs.output_schema` | ⏳ planned | FHIR Observation emitter for EHR interoperability |
| 6 | `neurotcs.adapters` | 🟡 partial | ADNI + OASIS-3 shipped; PPMI / RIDER / MIRIAD planned |
| 7 | `neurotcs.validation_harness` | ⏳ planned | Synthetic-trajectory self-tests per rule pack |

## Rule packs shipped

| Pack | Disease | Anchor publication | Transitions |
|---|---|---|---|
| `ad/niaaa_2018@1.1.0` | Alzheimer's | Jack 2018 NIA-AA Framework (PMID 29653606) | 4 + 2 inadmissible |
| `ad/aa_2024@1.1.0` | Alzheimer's | Jack 2024 AA Revised Criteria (PMID 38934362) | 11 monotone |
| `ad/aa_2024_trac@1.0.0` | Alzheimer's (anti-Aβ therapy) | **La Joie 2025 TRAC framework** (DOI 10.1002/alz.70997, PMCID PMC12657122) | 6 admissible + 3 inadmissible (5 require `treatment_status`) |
| `pd/hoehn_yahr@1.0.0` | Parkinson's | Goetz 2008 MDS-UPDRS (DOI 10.1002/mds.22340) | 13 |
| `ms/mcdonald_2024@1.0.0` | Multiple sclerosis | Montalban 2025 + Lublin 2014 | 13 (bidirectional RRMS) |
| `oncology/recist_1_1@1.0.0` | Oncology (solid tumor) | Eisenhauer 2009 RECIST 1.1 (PMID 19097774) | 11 |
| `oncology/irecist@1.0.0` | Oncology (immunotherapy) | Seymour 2017 iRECIST (PMID 28271869) | 13 (pseudoprogression) |
| `stroke/mrs_followup@1.0.0` | Stroke | Banks 2007 + Winstein 2016 | 19 |
| `lung_nodule/fleischner_2017@1.0.0` | Pulmonology | MacMahon 2017 Fleischner 2017 | 8 |

Each rule pack is:
- **Citation-locked** — every transition requires `citation_pmid` or `citation_doi` AND `guideline_section` (exact section/table/figure pointer).
- **Version-stamped** — canonical JSON SHA-256 hash computed at load time.
- **Fail-closed** — Pydantic v2 strict mode rejects unknown fields, missing citations, inconsistent state spaces.

**Schema v1.2.0 (v1.4.0)** adds backward-compatible support for **context-conditional admissibility**: a transition may declare `required_conditions: {treatment_status: [...]}`, in which case the audit core checks the trajectory's per-visit context before scoring it as admissible. The TRAC pack uses this to encode that A+ → A− amyloid clearance is admissible *only* under anti-Aβ therapy (lecanemab, donanemab). All 8 prior v1.1.0 packs load unchanged under v1.2.0.

## Authority model

NeuroTCS rule packs do NOT require disease-specialist co-authorship to be authoritative. They require provenance to internationally endorsed published guidelines. The schema makes this explicit:

- `clinical_source_authority` — names the peer-reviewed publication + endorsing professional society where clinical authority resides (NIA-AA, MDS, ECTRIMS, EORTC RECIST Working Group, AHA/ASA, Fleischner Society).
- `transcribed_by` — names the board-certified physician who attests the YAML faithfully encodes the cited guideline.
- `guideline_section` per transition — exact pointer so any reviewer can verify the transcription.
- `reviewers` — additive specialist sign-off (non-blocking).

This is exactly how FHIR / SNOMED / LOINC terminology encodings work. Authority lives in the cited publication, not in a co-author's signature.

See [`docs/transcription_audit/`](docs/transcription_audit/) for side-by-side YAML ↔ source-paragraph audits.

## Quick start

```bash
git clone https://github.com/DrMaruf1991/NeuroTCS.git
cd NeuroTCS
pip install -e ".[dev]"
python tests/audit_core/test_audit_core.py    # 35/35 should pass
```

### Rule pack only

```python
from neurotcs import load_rulepack

pack = load_rulepack("ad/niaaa_2018")
ok, rule = pack.rulepack.is_admissible("CN", "AD", delta_t_days=200)
print(ok)  # False — CN->AD requires >=365 days (Jack 2018)
```

### Full audit pipeline (the v1.2.0 addition)

```python
from neurotcs import audit, load_rulepack, trajectories_from_dataframe
import pandas as pd

# Long-format DataFrame: one row per (patient, visit)
df = pd.DataFrame({
    "RID":       [1, 1, 1, 2, 2, 2],
    "EXAMDATE":  ["2020-01-01", "2021-01-01", "2022-01-01",
                  "2020-06-01", "2021-06-01", "2022-06-01"],
    "DIAGNOSIS": ["CN", "MCI", "AD", "CN", "MCI", "MCI"],
})

trajectories = trajectories_from_dataframe(
    df, patient_id_col="RID", visit_date_col="EXAMDATE",
    state_col="DIAGNOSIS",
)
pack = load_rulepack("ad/niaaa_2018")
result = audit(trajectories, pack, bootstrap_B=10_000, seed=42)

print(result.summary())
# cTCS  1.0000  (BCA 95% CI: 1.0000..1.0000; Huber: 1.0000; B=10000, N=2)
# pTCS  -0.2741 (BCA 95% CI: -0.31..-0.24; ...)  (priors: clinical)
# uTCS  1.0000  (BCA 95% CI: 1.0000..1.0000; ...)

print(result.audit_id)         # stable SHA-256 over the full audit
result.to_json("report.json")  # JSON for FDA Q-Sub / Nature Medicine supplement
```

### CLI

```bash
neurotcs-audit audit \
  --predictions predictions.csv \
  --rulepack ad/niaaa_2018 \
  --output report.json \
  --bootstrap 10000 --seed 42 \
  --patient-col RID --date-col EXAMDATE --state-col DIAGNOSIS \
  --state-label-map Dementia=AD
```

## Real-world validation

```
$ python examples/adni_audit_demo.py
Rule pack:   ad/niaaa_2018@1.1.0
SHA-256:     372cc128832bf693...
Schema:      v1.1.0

Transitions audited: 12,006
Flagged:             65 (0.54%)
Flag types:          MCI→CN below 180-day minimum, AD→MCI (inadmissible)
```

All 65 flags are clinically interpretable — none are false positives from spec mis-encoding.

## Specification

The canonical spec is [`docs/spec/temporalmetric_v1.6_FINAL.md`](docs/spec/temporalmetric_v1.6_FINAL.md) (9,859 words). Read this to understand:

- §A.2 — Coherence Temporal Consistency Score (cTCS) definition
- §A.3 — Probabilistic TCS with matrix exponential M(Δτ) = exp(Q · Δτ / 365)
- §A.4 — Unified TCS (weighted ensemble)
- §A.5 — Cluster bootstrap (B = 10,000) + Huber M-estimation (c = 1.345)
- §B.1 — Aims 1–6 validation plan
- §B.2 — Required datasets (ADNI, OASIS-3, MIRIAD, PPMI, RIDER, ALZ-NET)
- §B.6 — Rule pack registry and engineering discipline
- §C — Library architecture (input contract, rule pack, audit core, output schema)

## Roadmap to v0.2 / v1.0 / Q-Sub

- **v0.2 (Q3 2026)** — Pieces 4 (audit core) + 5 (FHIR output) + first adapter additions (MIRIAD, RIDER).
- **W22 (~Sept 2026)** — Nature Medicine submission with AD validation across ADNI + OASIS-3 + MIRIAD.
- **Oct 2026** — ASFNR Newport Beach workshop demo.
- **Q1 2027** — FDA Q-Submission with v1.0.0 release.

## Citation

```bibtex
@software{salokhiddinov2026neurotcs,
  author    = {Salokhiddinov, Marufjon},
  title     = {NeuroTCS: Citation-locked, fail-closed longitudinal medical AI audit framework},
  version   = {1.1.0},
  year      = {2026},
  url       = {https://github.com/DrMaruf1991/NeuroTCS},
  note      = {temporalmetric v1.6 FINAL specification, 8 production rule packs}
}
```

See [`CITATION.cff`](CITATION.cff) for GitHub's citation widget.

## Known limitations and roadmap

NeuroTCS publicly documents gaps so reviewers can assess fitness for purpose.

### v1.4.0 closed
- ✅ **TRAC framework** (La Joie 2025, DOI 10.1002/alz.70997, PMCID PMC12657122) — shipped as `ad/aa_2024_trac@1.0.0`. Anti-amyloid therapy patients (lecanemab approved 2023-07-06, donanemab approved 2024-07-02) are no longer falsely flagged for biological reversal of amyloid biomarkers.
- ✅ **Schema v1.2** with conditional admissibility (`required_conditions`) — generalizes beyond AD to any rule pack needing context-dependent rules.
- ✅ **Evidence-base verification methodology** — every FDA date and DOI in v1.4.0 documentation was verified at a primary source (Eisai/Biogen, Eli Lilly, FDA, PubMed/PMC) before commit. No claim relies on language-model memory.

### Open gaps (planned for v1.5.0)
- ⚠️ **AA 2024 transition priors empty.** The `ad/aa_2024@1.1.0` rule pack has `transition_priors: []`. As a result, **pTCS is unavailable when auditing with AA 2024** (only cTCS and uTCS report). Source for priors: Mendes AJ et al., *Neurology* May 13 2025 (DOI 10.1212/WNL.0000000000213675, PMCID PMC12079574) — ADNI validation of the AA-2024 4×4 biological/clinical staging matrix — and similar emerging cohort studies.
- ⚠️ **Plasma biomarker reference range bindings.** The 2024 AA criteria put plasma p-tau217 and Aβ42/40 as Core 1 biomarkers sufficient for diagnostic confirmation of AD. Input contract v1.1 supports them via UCUM units, but specific reference range thresholds (e.g. p-tau217 "intermediate range" 0.186–0.324 pg/mL per La Joie 2025) are not yet bound. pTCS scoring works on the categorical state, not the raw biomarker value, so this gap does NOT affect current audit results — but downstream interoperability is incomplete.
- ⚠️ **Tau PET tracers in clinical use.** Eli Lilly's Tauvid (flortaucipir F-18, AV-1451, FDA approved May 2020) is the currently-marketed tau tracer and is implicitly supported via the existing T2 biomarker states. **MK-6240 / florquinitau F-18** (Lantheus; NDA accepted 2025-10-28, PDUFA target **2026-08-13**) will be added on FDA approval if it succeeds.
- ⚠️ **Aim 3 (MIRIAD test-retest)** — DUA email sent 2026-05-17, awaiting response.
- ⚠️ **Aim 5 (PD + Oncology external replication)** — PPMI + RIDER DUAs not yet filed.

### Planned for v1.6.0 / 2.0.0
- Piece 5: FHIR Observation emitter (output schema)
- Piece 7: validation harness (synthetic-trajectory self-tests per rule pack)
- Cohort-specific transition priors (clinical-ADNI, clinical-OASIS3, community)

## License

Apache 2.0 — see [`LICENSE`](LICENSE). The cited published guidelines (Jack 2018, Eisenhauer 2009, MacMahon 2017, etc.) remain © their respective publishers; this package transcribes them into machine-readable form for academic / regulatory audit purposes under fair-use interpretation. NeuroTCS does NOT redistribute the publications themselves.

## Contact

**Dr. Marufjon Salokhiddinov, MD PhD**
ESOR-BRACCO-ESNR Neuroimaging Fellow
Kimyo International University in Tashkent (KIUT), Uzbekistan

Issues and contributions via GitHub (currently private; co-authors and invited reviewers only until v1.0.0).

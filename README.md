# NeuroTCS

**Citation-locked, fail-closed longitudinal medical AI audit framework.**

[![CI](https://github.com/DrMaruf1991/NeuroTCS/actions/workflows/ci.yml/badge.svg)](https://github.com/DrMaruf1991/NeuroTCS/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Schema v1.1](https://img.shields.io/badge/schema-v1.1.0-success.svg)](src/neurotcs/rulepack/schema.py)
[![Spec v1.6 FINAL](https://img.shields.io/badge/spec-v1.6_FINAL-success.svg)](docs/spec/temporalmetric_v1.6_FINAL.md)

NeuroTCS audits the temporal coherence of longitudinal medical AI predictions against internationally endorsed published clinical guidelines. It answers the question regulators, hospitals, and trialists ask first: *does this AI model's visit-to-visit prediction trajectory obey the clinical biology it claims to predict?*

The framework is anchored on Dr. Marufjon Salokhiddinov's ASNR 2026 presentation (Austin, May 2026) and the temporalmetric v1.6 FINAL technical specification. The AD instantiation has been validated on 12,006 real ADNI clinical-label transitions: 65 flagged (0.54%), all clinically interpretable.

---

## What's in this repo

NeuroTCS is the umbrella for seven engineering pieces. Pieces 1–3 are shipped in v1.1.0; pieces 4–7 are planned per the spec roadmap.

| Piece | Subpackage | Status | Description |
|---|---|---|---|
| 1 | `neurotcs.input_contract.v1_0` | ✅ shipped | Categorical input contract (8-step validation, fail-closed) |
| 2 | `neurotcs.input_contract.v1_1` | ✅ shipped | Continuous-biomarker contract with UCUM unit enforcement |
| 3 | `neurotcs.rulepack` | ✅ shipped | 8 production rule packs across 6 disease domains |
| 4 | `neurotcs.audit_core` | ⏳ planned | cTCS / pTCS / uTCS engine with cluster bootstrap + Huber |
| 5 | `neurotcs.output_schema` | ⏳ planned | FHIR Observation emitter for EHR interoperability |
| 6 | `neurotcs.adapters` | 🟡 partial | ADNI shipped; OASIS-3 / PPMI / RIDER / MIRIAD planned |
| 7 | `neurotcs.validation_harness` | ⏳ planned | Synthetic-trajectory self-tests per rule pack |

## Rule packs shipped

| Pack | Disease | Anchor publication | Transitions |
|---|---|---|---|
| `ad/niaaa_2018@1.1.0` | Alzheimer's | Jack 2018 NIA-AA Framework (PMID 29653606) | 4 + 2 inadmissible |
| `ad/aa_2024@1.1.0` | Alzheimer's | Jack 2024 AA Revised Criteria (PMID 38934362) | 11 monotone |
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
python tests/rulepack/test_rulepack.py    # 24/24 should pass
```

```python
from neurotcs import load_rulepack

pack = load_rulepack("ad/niaaa_2018")
pack.assert_usable_for_audit()
print(pack.sha256[:16])

# Check admissibility
ok, rule = pack.rulepack.is_admissible("CN", "AD", delta_t_days=200)
print(ok)  # False — CN->AD requires >=365 days (Jack 2018)

ok, rule = pack.rulepack.is_admissible("CN", "AD", delta_t_days=500)
print(ok)  # True

# iRECIST pseudoprogression resolution
ire = load_rulepack("oncology/irecist")
ok, _ = ire.rulepack.is_admissible("iUPD", "iPR", 30)
print(ok)  # True — pseudoprogression resolved to partial response
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

## License

Apache 2.0 — see [`LICENSE`](LICENSE). The cited published guidelines (Jack 2018, Eisenhauer 2009, MacMahon 2017, etc.) remain © their respective publishers; this package transcribes them into machine-readable form for academic / regulatory audit purposes under fair-use interpretation. NeuroTCS does NOT redistribute the publications themselves.

## Contact

**Dr. Marufjon Salokhiddinov, MD PhD**
ESOR-BRACCO-ESNR Neuroimaging Fellow
Kimyo International University in Tashkent (KIUT), Uzbekistan

Issues and contributions via GitHub (currently private; co-authors and invited reviewers only until v1.0.0).

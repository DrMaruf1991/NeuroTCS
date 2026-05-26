# NeuroTCS World-Class Gate (production-pack invariant)

**Status:** Architectural canon, established in v1.15.1.
**Authority:** This document describes what makes a Layer 2 production pack
production-grade. Every future pack proposal must clear this gate before being
added to `EXPECTED_PRODUCTION_PACKS` in `tests/clinical_ranges/test_loader.py`.

---

## TL;DR

A Layer 2 rangepack is world-class iff every bound clears three invariants
**simultaneously**:

1. **Endorser floor:** `len(citation.endorsing_bodies) >= 5`
2. **Citation strength form:** `citation_strength` ∈ {`international_consensus`,
   `verbatim`, `derived`}
3. **Derived bounds only:** `citation_text` references multi-cohort or
   multi-source evidence (not a single paper's number)

If all three hold across all bounds, the pack qualifies for `status: production`
and is added to `EXPECTED_PRODUCTION_PACKS`. Otherwise it ships as
`research_preview`.

---

## Background — why this gate exists

NeuroTCS Layer 2 ranges are intended for **clinical-grade audit logic**.
A bound like `plasma_ptau181_pgml_elecsys.plausible_max = 0.722` is going to
appear in downstream flagging logic that influences clinical decisions, trial
eligibility, or regulatory submissions. Such bounds must rest on evidence
strong enough to defend in front of an FDA reviewer, an EMA assessor, a peer
reviewer at *Lancet Neurology*, or a courtroom.

This is what "world-class" means operationally: the bound has been endorsed
by enough independent international bodies that no individual paper, author,
or platform can override it.

---

## The three invariants in detail

### Invariant 1 — Endorser floor (>=5 bodies)

**Definition:** `len(citation.endorsing_bodies) >= 5`, with endorsing bodies
being international specialty societies (SNMMI, EANM, AA, AAN), regulatory
authorities (FDA, EMA, PMDA, ARTG), named research consortia (ADNI, A4,
OASIS-3, HABS, BioFINDER, BACS, EMIF-AD, Meta VCI Map, AMYPAD, GAAIN),
manufacturer-developers when paired with regulatory action (Roche, Eli Lilly,
Fujirebio, Avid, Quanterix, C2N), or recent foundational peer-reviewed
studies (Karikari 2020, Schöll 2016, Maass 2017, Pascoal 2021, Villemagne 2023,
Palmqvist 2025, Jack 2024).

**Why >=5:** Any cutoff is debatable; this one is the load-bearing invariant
of the entire world-class architecture. With 5 endorsers, no single body
can drive the bound. With fewer, the pack effectively depends on one source.

**Why this is the load-bearing invariant:** Invariant 2 (the citation_strength
label) is a form-of-evidence descriptor. Invariant 3 (multi-source evidence
text) is a quality check on derived bounds specifically. Only invariant 1
captures the multi-body-agreement that makes a bound regulatorily defensible.

### Invariant 2 — Citation strength form

**Definition:** `citation_strength` must be one of three world-class forms.

- **`international_consensus`** — multiple specialty bodies have published
  agreeing numeric criteria. Example: pet_amyloid/centiloid_consensus
  (Klunk 2015 + AMYPAD 2024 + SNMMI + EANM + AA + GAAIN + FDA).
- **`verbatim`** — the cited source contains the EXACT numeric bound in a
  table, figure caption, or explicit statement; `citation_text` quotes
  the source directly. Example: Fazekas 1987 AJR scale 0-3 (the founding
  paper). FDA Tauvid PI §2.4 verbatim 1.65x cerebellar threshold.
- **`derived`** — the cited source contains data (e.g., cohort distribution,
  population statistics) from which the bound is derived (e.g., 99th percentile,
  upper envelope); `citation_text` explains the derivation. Example: Meta
  VCI Map Consortium 99th-percentile WMH volume cutoffs (n=14,876 across
  15 cohorts).

**Why all three are valid:** The strict v1.10.x-v1.15.0 gate required EVERY
bound to carry the literal string `international_consensus`. This was
historically dishonest: Fazekas 1987 verbatim ceiling at 3 IS international
consensus (39-year-old founding paper, ratified by STRIVE-2 2023 and the
Wahlund 2001 visual scale), but its citation FORM is verbatim. Meta VCI
Map 99th-percentile cutoffs derived from n=14,876 across 15 cohorts are
STRONGER evidence than a single guideline endorsement, but the schema
labels it derived. The reconciled gate accepts any of the three forms
because the LOAD-BEARING invariant is the endorser floor (Invariant 1),
not the form label.

### Invariant 3 — Multi-source evidence for derived bounds

**Definition:** If `citation_strength == derived`, the `citation_text` must
contain evidence that the bound rests on multi-cohort or multi-source data,
not a single paper's number.

**Heuristic markers (case-sensitive substring match in citation_text):**
`cohort`, `multi-`, `Meta VCI`, `consortium`, `Consortium`, `percentile`,
`across`, `n=`, `ADNI`, `BioFINDER`, `OASIS`, `OASIS-3`, `A4 Study`, `HABS`,
`EMIF-AD`, `INSIGHT-preAD`, `Karikari`, `Maass`, `Schöll`, `Pascoal`,
`Mattsson`, `Therriault`, `GAAIN`, `AMYPAD`, `TRAILBLAZER`.

**Why this is necessary:** A "derived" bound from a single small study is
not world-class. A "derived" bound that says "Meta VCI Map Consortium
(n=14,876, 15 cohorts) 99th percentile = 100 mL" is. The marker list is
the canonical set of named cohorts and population-statistical phrasings
that distinguish multi-source derivation from single-paper extrapolation.

---

## How this gate is enforced

Three tests in `tests/clinical_ranges/test_loader.py::TestProductionPackWorldClassGate`
enforce the invariants across every pack in `EXPECTED_PRODUCTION_PACKS`:

1. `test_every_bound_meets_world_class_evidence_bar` — checks invariants 1 + 2 atomically
2. `test_derived_bounds_show_multi_source_evidence` — checks invariant 3
3. `test_every_bound_has_5plus_endorsing_bodies` — back-compat name for invariant 1

Plus per-pack invariants in each pack's own test file (e.g.,
`test_every_bound_meets_world_class_evidence_bar` in
`test_wmh_fazekas_consensus_pack.py`).

---

## Path-to-production for a new pack

To add a new Layer 2 pack at `status: production`:

1. Build the YAML with `status: production` and an `anchor_citation` carrying
   PMID or DOI plus public_url
2. Every bound must carry `citation_strength` in {`international_consensus`,
   `verbatim`, `derived`}
3. Every bound must have `endorsing_bodies` list with >=5 named bodies
4. Every bound must have `public_url`
5. For every `derived` bound, the `citation_text` must include at least one
   multi-source marker (named cohort or population-statistical phrasing)
6. Add the pack to `EXPECTED_PRODUCTION_PACKS` in `test_loader.py`
7. Add the pack's golden yaml_sha256 to `PRODUCTION_YAML_SHA256_GOLDEN` in
   `test_yaml_sha256_cross_platform.py`
8. Write a pack-specific test file mirroring the central gate plus pack-content
   tests
9. Update roster counts in `test_deprecation_semantics.py::TestRosterCounts`
10. Run full pytest + ruff; verify byte-exact invariance against the prior release

If any step fails or any bound can't clear the gate, ship the pack at
`status: research_preview` instead. Research_preview packs cannot be used
in `audit_clinical_ranges()` by design (only production packs audit).

---

## Versioning of this gate

- **v1.10.x-v1.15.0:** Strict gate required every bound to carry the literal
  string `international_consensus` as citation_strength. This was the
  silent-skip era for wmh_fazekas_consensus (v1.13.0, v1.14.0, v1.15.0
  CHANGELOGs documented the gap but did not fix it).
- **v1.15.1 (this release):** Reconciled gate. wmh_fazekas_consensus joined
  EXPECTED_PRODUCTION_PACKS. World-class invariant is endorser-floor-based
  not label-based. All 8 current production packs pass the reconciled gate.

---

## Standing mandate

This gate exists to honor the user's standing mandate:

> world class no partial fix, end-to-end, root-to-root, no hallucinations,
> double-test always, no step back in future.

Every future pack-addition PR should be reviewed against this document.
If the path-to-production above cannot be completed without skipping a step,
the pack ships at research_preview, not production. No silent gaps.

# NeuroTCS -- Software Lifecycle Traceability (IEC 62304-structured)

**Document ID:** NTCS-RM-002
**Standard structure:** IEC 62304 (Medical device software -- software life cycle
processes), linked to the risk controls in NTCS-RM-001 (ISO 14971 hazard
analysis).
**Status:** REGULATORY-GAP DRAFT -- not a compliance declaration.

---

## 0. Status banner -- read first

This document applies the *structure* of IEC 62304 to NeuroTCS: it classifies the
software, decomposes it into software items, and traces each hazard-control from
NTCS-RM-001 through requirement -> design -> implementation -> verification -> CI
gate. It is **not** a completed, compliant software lifecycle record. IEC 62304
compliance requires a quality management system (ISO 13485), a software
development plan established *before* development, configuration-controlled
records, and qualified human owners. This is a **reconstructed, after-the-fact
traceability map** prepared as an engineering-grade starting point. Where a
process area is not yet formalized, it is listed as a gap (Section 9), not
papered over.

NeuroTCS remains **research use only**; clinical use is gated on the Arm A
validation study (NTCS-RM-001 Section 7).

---

## 1. Software safety classification (IEC 62304 clause 4.3)

**Method.** IEC 62304 classifies software by the worst-case harm a hazardous
situation the software can contribute to could cause: Class A (no injury
possible), Class B (non-serious injury possible), Class C (death or serious
injury possible). Classification is assigned conservatively and may use external
risk controls and segregation to justify a lower class.

**Reasoning from the hazard analysis (NTCS-RM-001):**

- In the **intended research scope**, the software contributes only to
  research-integrity harm (a wrong audit -> a wrong research conclusion). No
  direct patient injury occurs; harm caps at S3. Considered alone, this is
  Class A territory.
- However, foreseeable misuse M6 (clinical deployment without validation) could
  let output contribute to a reversible clinical decision (S4). The
  research-use-only status is a **labeling** control, not a software partition,
  so it cannot by itself justify Class A.

**Provisional classification: Class B (for the intended research scope).**
This reflects "non-serious injury possible" if output influenced a reversible
decision, while the RUO control and the mediated (human-in-the-loop) harm pathway
keep it below Class C in intended use.

**Mandatory caveats:**

1. This classification must be reviewed and owned by a qualified team under a
   QMS; it is a documented engineering judgment, not an assigned regulatory
   class.
2. **Any clinical deployment forces re-classification to Class C** and the full
   Class C lifecycle rigor (detailed design records, unit-level verification of
   every item, etc.), and is gated on Arm A regardless.

---

## 2. Software item decomposition (IEC 62304 clause 5.3)

NeuroTCS decomposed into software items (top-level), each a traceability anchor:

| Item | Path (representative) | Responsibility |
|------|----------------------|----------------|
| SI-ORCH | src/neurotcs/orchestration/ | Fail-closed orchestration; layer scheduling; refusal logic; coverage manifest |
| SI-VOCAB | src/neurotcs/orchestration/vocabulary.py | Vocabulary coverage / pack applicability |
| SI-IO | src/neurotcs/io/readers.py | Input reading; format dispatch; archive-bomb guardrails |
| SI-INTEG | src/neurotcs/io/data_integrity.py | Date validity; temporal ordering; structural integrity |
| SI-WIRE | src/neurotcs/io/autowire.py, io/cdisc.py | Range autowiring; CDISC handling |
| SI-TRAJ | src/neurotcs/audit_core/ | Trajectory audit; deterministic audit_id |
| SI-RANGE | src/neurotcs/clinical_ranges/ | Numeric range audit |
| SI-XSHEET | src/neurotcs/cross_sheet/ | Cross-sheet invariant audit |
| SI-RULE | src/neurotcs/rulepack/ | Rule-pack loading; schema validation; SHA-256 integrity |
| SI-PACKS | src/neurotcs/rulepack/rules/ad/*.yaml | Citation-locked clinical rule packs |
| SI-CONTRACT | src/neurotcs/input_contract/, reference_adapters/ | Input contracts and dataset adapters |
| SI-VALID | src/neurotcs/validation/ | Validation harness; error taxonomy |
| SI-CITE | scripts/verify_citations.py | Networked citation verifier |
| SI-SBOM | scripts/ci/generate_sbom.py | CycloneDX SBOM generation |

---

## 3. Traceability matrix (risk control -> requirement -> item -> verification -> CI gate)

Each row traces a risk control from NTCS-RM-001 through the full chain. "Test
ref" cites a confirmed test module/class where known, or the responsible test
area otherwise (exact function names not asserted where unverified). "CI gate"
names the workflow enforcing it.

### RC-1 (mitigates H2) -- Fail-closed orchestration

- **Requirement (derived):** When a substantive audit layer cannot run, the
  system shall refuse (exit INCOMPLETE_REFUSED) rather than report "clean".
- **Design/item:** SI-ORCH (orchestrator forced-skip / scored-layer logic).
- **Implementation:** orchestrator forced_skips/scored_layers refusal
  (release v1.74.0, E-2026-047).
- **Verification:** orchestration test area; reproduction case vocab_test
  (CLEAN/0 -> exit 3).
- **CI gate:** ci.yml (Test); ci-matrix.yml.
- **Status:** Verified.

### RC-2 (mitigates H2, H5) -- Malformed-date fail-closed

- **Requirement:** Present-but-unparseable dates shall be flagged
  (malformed_visit_date, impossible tier), never silently coerced.
- **Design/item:** SI-INTEG (data_integrity malformed-date check).
- **Implementation:** v1.74.0 (E-2026-047).
- **Verification:** data-integrity test area; reproduction case malformed_test
  (CLEAN/0 -> FLAGS_PRESENT/1).
- **CI gate:** ci.yml; ci-matrix.yml.
- **Status:** Verified.

### RC-3 (mitigates H2, H4) -- Vocabulary-mismatch fail-closed

- **Requirement:** Staging shall not score on vocabulary below the coverage
  threshold; it shall fail closed.
- **Design/item:** SI-VOCAB.
- **Implementation:** vocabulary coverage gate; synonym ontology
  (v1.59.0/1.60.0; v1.74.0 refusal).
- **Verification:** tests/orchestration (vocabulary area).
- **CI gate:** ci.yml; ci-matrix.yml.
- **Status:** Verified.

### RC-4 (mitigates H3) -- Citation cross-resolver gate

- **Requirement:** Every PMID and DOI shall resolve, and for a citation carrying
  both, the PubMed and Crossref records shall agree (title/journal/first-author);
  a mismatch shall fail the build.
- **Design/item:** SI-CITE.
- **Implementation:** cross-resolver comparator (v1.77.0); exit-1-on-mismatch and
  exit-2-on-outage (v1.76.0); normalization fixes (v1.77.1).
- **Verification:** tests/scripts/test_verify_citations_exit_codes.py
  (8+ tests: mismatch->1, clean->0, outage->2, offline->0; precision tests).
- **CI gate:** supply-chain.yml (citation verifier: offline hard gate + networked
  best-effort).
- **Status:** Verified. Last networked run: 183/183 resolved, 0 mismatches.

### RC-5 (mitigates H5) -- Archive-bomb guardrails

- **Requirement:** Compressed inputs shall fail closed (ArchiveLimitError) on
  size/ratio/member-count limits before exhausting memory.
- **Design/item:** SI-IO.
- **Implementation:** readers.py limits + bounded reads (v1.75.0, E-2026-048).
- **Verification:** tests/io/test_readers.py::TestArchiveBombGuardrails
  (6 tests: ratio/member/size/gzip bombs blocked; normal archives read).
- **CI gate:** ci.yml; ci-matrix.yml.
- **Status:** Verified.

### RC-6 (mitigates H7) -- Deterministic audit and reproducibility

- **Requirement:** The audit shall produce a deterministic audit_id and identical
  flags across supported platforms and Python versions.
- **Design/item:** SI-TRAJ (audit_id); SI-RULE (SHA-256 pack integrity).
- **Implementation:** deterministic audit_id; canonical pinned closure
  (requirements.lock); locked invariants.
- **Verification:** tests/docs/test_reproducibility_structure.py (lockfile pin
  contract); validation + threshold-derivation suites (invariant evidence).
- **CI gate:** reproducibility.yml (Ubuntu/macOS/Windows x Python 3.11/3.12 ->
  green; audit_id-invariant job).
- **Status:** Verified with multi-OS CI evidence.

### RC-7 (mitigates H8) -- Supply-chain assurance

- **Requirement:** The dependency closure shall be pinned, CVE-scanned, and
  enumerated in an SBOM.
- **Design/item:** SI-SBOM; requirements.lock; rule-pack SHA-256 gates (SI-RULE).
- **Implementation:** lockfile (v1.75.0); generate_sbom.py (v1.75.0).
- **Verification:** tests/scripts/test_generate_sbom.py (3 tests: valid
  CycloneDX 1.6, deterministic, fail-closed on missing lock).
- **CI gate:** supply-chain.yml (pip-audit on push + weekly -> "No known
  vulnerabilities found"; SBOM artifact upload).
- **Status:** Verified.

### RC-8 (mitigates H9) -- Citation-locked, versioned rule packs

- **Requirement:** Each clinical rule shall be bound to a dated, resolvable
  source with a guideline_section; multiple guideline editions shall coexist.
- **Design/item:** SI-PACKS; SI-RULE (schema).
- **Implementation:** NIA-AA 2018, AA 2024 (clinical numeric + biological
  letter), AT(N), TRAC packs, each citation-locked.
- **Verification:** rulepack test area; citation verifier (RC-4).
- **CI gate:** supply-chain.yml (citation verifier); ci.yml.
- **Status:** Verified for identifier integrity. GAP: semantic attribution
  (does the source support the exact threshold) is spot-checked, not exhaustively
  adjudicated (G2).

### RC-9 (mitigates H1, H10) -- Severity-typed, citation-bearing flags

- **Requirement:** Flags shall be typed by severity (impossible / implausible /
  informational); implausible/informational are advisory, not assertions of
  error; every flag shall carry an inspectable citation.
- **Design/item:** SI-TRAJ, SI-RANGE, SI-XSHEET (flag provenance).
- **Implementation:** flag provenance (v1.57.0); coverage ledger (v1.58.0).
- **Verification:** audit-core / clinical-ranges / cross-sheet test areas.
- **CI gate:** ci.yml; ci-matrix.yml.
- **Status:** Verified (mechanism). GAP: flag PPV/sensitivity unmeasured (G1,
  Arm A).

### RC-10 (mitigates H4, H10) -- Explicit AD-only scope and refusal

- **Requirement:** Out-of-scope (non-AD) domains shall be refused; scope shall be
  documented.
- **Design/item:** SI-ORCH, SI-VOCAB.
- **Implementation:** AD-only scope and endorsement honesty (v1.64.0).
- **Verification:** scope/orchestration test area.
- **CI gate:** ci.yml.
- **Status:** Verified.

---

## 4. Verification and validation summary (IEC 62304 clauses 5.5-5.7)

- **Unit / integration / system verification:** automated test suite of
  approximately 1982 tests, green on the canonical interpreter and across the
  multi-OS reproducibility matrix.
- **Regression guard:** the v3 cohort invariant (impossible 69 / implausible 65 /
  informational 1236) is held constant across releases as a system-level
  regression anchor.
- **CI gates (enforcing verification on every change):**
  - ci.yml -- lint (ruff) + full test suite + citation resolver.
  - ci-matrix.yml -- cross-platform x Python (3.11-3.13).
  - reproducibility.yml -- multi-OS reproducibility + audit_id invariant.
  - supply-chain.yml -- pip-audit (CVE) + SBOM + citation verifier.
- **Validation (clinical correctness):** NOT YET PERFORMED. Gated on Arm A
  (NTCS-RM-001 Section 7; docs/VALIDATION_PROTOCOL.md). This is the dominant
  open item and the reason for RUO status.

---

## 5. SOUP -- Software of Unknown Provenance (IEC 62304 clause 8.1.2, 5.3.3-5.3.4)

NeuroTCS's third-party runtime components are the **locked dependency closure**
in requirements.lock (the canonical reproducibility set). IEC 62304 requires each
SOUP item to be identified by version and evaluated for anomalies.

- **SOUP inventory:** the 31-component closure enumerated in requirements.lock
  and the generated CycloneDX SBOM (scripts/ci/generate_sbom.py output).
- **Version control:** each component pinned to an exact version; the canonical
  set (e.g. pandas 3.0.2, numpy 2.4.4, scipy 1.17.1) is the set that produces the
  locked audit_id invariants.
- **Anomaly / vulnerability evaluation:** pip-audit runs on every push and weekly
  in supply-chain.yml against the advisory database; current result "No known
  vulnerabilities found."
- **Functional adequacy:** verified transitively -- a clean install of exactly
  the locked set passes the full suite (proven in the v1.75.0 lockfile
  verification).
- **GAP:** the lockfile does not yet carry per-artifact cryptographic hashes; the
  regeneration path (pip-compile --generate-hashes) is documented (G5).

---

## 6. Configuration management (IEC 62304 clause 8)

- **Version control:** git (github.com/DrMaruf1991/NeuroTCS), tagged releases
  (v1.68.0 ... v1.77.1).
- **Release identification:** single-version-of-truth enforced by
  tests/test_version_consistency.py (pyproject, __init__, CITATION.cff, README
  badge/prose, SECURITY.md, CHANGELOG must agree).
- **Change records:** CHANGELOG.md with engineering-change IDs (E-2026-045
  through E-2026-051) describing each release's intent and verification.
- **Release process:** changes delivered as self-verified patches applied to a
  clean baseline tree, install + full suite + invariant re-run before commit and
  tag.
- **Reproducible builds:** Dockerfile (containerized) + reproducibility.yml
  (multi-OS) establish build/runtime reproducibility.
- **GAP:** no cryptographic signing/attestation of release artifacts yet (G5).

---

## 7. Problem resolution (IEC 62304 clause 9)

The project demonstrates a working defect lifecycle (identify -> reproduce ->
fix at root -> add regression test -> verify -> release). Representative real
defects resolved under this process:

- **Citation-verifier fail-open** (gate could never return non-zero on a
  mismatch) -- found, fixed to honor the exit-code contract, locked with
  regression tests (v1.76.0, E-2026-049).
- **TRAC wrong-PMID citation defect** (Jack 2024 PMID welded to La Joie 2025 DOI
  on six transitions) -- the citation gate's first real run surfaced it; corrected
  to the verified PMID and confirmed by a clean networked re-run (v1.77.0,
  E-2026-050).
- **Comparator false positives** (multi-word surnames, journal abbreviations) --
  diagnosed to root and fixed, with precision regression tests (v1.77.1,
  E-2026-051).

Each fix added a regression test so the defect cannot silently recur -- the core
of an effective problem-resolution process.

- **GAP:** problem resolution is currently developer-driven via git/issues; no
  formal post-market complaint-handling system tied to a QMS (part of G7).

---

## 8. Maintenance (IEC 62304 clause 6)

- Clinical-criteria currency (H9) requires periodic review as guidelines evolve;
  packs are versioned and citation-locked to support coexistence of editions.
- Dependency currency is monitored by the weekly pip-audit schedule.
- **GAP:** a formal maintenance plan with a defined criteria-review cadence is
  not yet established (G4).

---

## 9. Consolidated process gaps (IEC 62304 readiness)

| ID | Gap | Clause | Owner action |
|----|-----|--------|--------------|
| P1 | No QMS (ISO 13485) / software development plan established a priori | 4.1, 5.1 | Stand up QMS; adopt a plan |
| P2 | Safety classification not formally owned/assigned | 4.3 | Qualified-team classification review |
| P3 | Detailed-design records not maintained as formal artifacts | 5.4 | Formalize if pursuing Class C |
| P4 | No release signing / hashed lockfile (= NTCS-RM-001 G5) | 8 | Sign releases; --generate-hashes |
| P5 | No formal complaint-handling / post-market system | 9 | Establish under QMS |
| P6 | Maintenance plan / criteria-review cadence informal (= G4) | 6 | Define cadence |
| P7 | Semantic citation attribution not exhaustively adjudicated (= G2) | 5.7 | Rule-by-rule source adjudication |
| P8 | Clinical validation not performed (= G1) | 5.7 | Run Arm A |

(Gn IDs cross-reference the NTCS-RM-001 hazard-analysis gap register.)

---

## 10. Conclusion

NeuroTCS has a **strong, evidenced verification chain**: every hazard control in
NTCS-RM-001 traces to an implementing software item, a verification, and a CI
gate that enforces it on every change, across multiple operating systems and
Python versions, with supply-chain scanning and citation integrity proven on
real networked data. By the substance of IEC 62304's verification expectations,
the software is well-instrumented.

What is **not** yet in place is the surrounding **lifecycle process formalism**
(QMS, a priori development plan, owned classification, formal design and
complaint-handling records) and, above all, **clinical validation** (Arm A).
These are listed honestly as gaps P1-P8 rather than claimed.

This document is therefore an accurate map of where NeuroTCS stands on the
IEC 62304 path: verification substantially in place and traceable; lifecycle
formalism and validation pending; clinical use deferred and research-use-only
status retained.

---

*Prepared as an engineering-grade gap-analysis draft. Requires review and
ownership by a qualified software lifecycle / regulatory process owner before any
reliance. Not a compliance claim. Cross-references NTCS-RM-001.*

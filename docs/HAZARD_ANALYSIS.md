# NeuroTCS -- Hazard Analysis (ISO 14971-structured)

**Document ID:** NTCS-RM-001
**Standard structure:** ISO 14971:2019 (Application of risk management to medical
devices), with software hazard guidance per ISO/TR 24971 and forward reference to
IEC 62304.
**Status:** REGULATORY-GAP DRAFT -- not a compliance declaration.

---

## 0. Status banner -- read first

This document applies the *structure* of ISO 14971 to NeuroTCS so that the
project has an honest, systematic hazard foundation. It is **not**:

- a declaration that NeuroTCS is safe for clinical use;
- a completed, compliant Risk Management File (ISO 14971 requires a competent
  risk-management team, top-management commitment, a quality management system,
  and signed review records -- none of which a drafted document can substitute);
- a regulatory clearance, CE mark, or 510(k) artifact.

It is a **starting point for a qualified human risk-management process owner**.
Every risk estimate below is a documented engineering judgment, not field-
validated data; probabilities in particular are estimates pending post-market
information that does not yet exist. The single most important conclusion is
stated up front in Section 7: the dominant residual risk (clinical correctness
of the flags) is **not reducible by software** and requires the Arm A clinical-
validation study. Until Arm A is complete, NeuroTCS is **research use only**.

---

## 1. Intended use and intended purpose

**Intended purpose.** NeuroTCS is a reproducible, citation-locked **auditor** of
longitudinal Alzheimer's disease (AD) cohort data. Given staging values,
biomarker statuses, and trajectories that *other tools or processes have already
produced*, NeuroTCS checks them for internal coherence against published staging
and progression criteria (e.g. NIA-AA 2018, AA 2024, AT(N)) and emits flags
(impossible / implausible / informational), each bound to a verifiable citation.

**What NeuroTCS does NOT do (scope exclusions -- safety-critical):**

- It does **not** measure, segment, quantify, or derive any biomarker or image.
- It does **not** diagnose, stage a patient, or generate a clinical impression.
- It does **not** recommend treatment or management.
- It does **not** assert that flagged data is wrong or that unflagged data is
  correct -- it asserts only *consistency (or not) with the cited rule*.

**Intended users.** Researchers, data managers, and methodologists working with
AD cohort datasets (ADNI, OASIS-3, NACC, and similar); secondarily, clinical-
research staff performing data quality control. Users are expected to be
competent in AD staging concepts and to treat output as decision-support QC, not
as ground truth.

**Intended environment.** Offline or networked research computing environments.
Not an embedded clinical system; not real-time; no direct device or patient
interface.

**Operating principle (the safety promise).** "Evidence-locked, fail-closed,
sourced, universal." The promise is explicitly **not** "100% true." NeuroTCS is
designed to *refuse rather than guess*, and to make the basis of every flag
inspectable via citation.

---

## 2. Reasonably foreseeable misuse

Per ISO 14971, misuse must be analyzed, not only correct use:

- **M1 -- Treating a flag as a diagnosis or measurement.** A user reads
  "impossible transition" as "the patient does not have AD" or as a biomarker
  value. (Automation bias / scope confusion.)
- **M2 -- Treating "clean" as "data is correct/complete."** A user assumes an
  unflagged dataset has been fully validated.
- **M3 -- Auditing non-AD data** against AD rule packs and trusting the output.
- **M4 -- Using a stale rule pack** after the underlying clinical criteria have
  been superseded.
- **M5 -- Feeding identifiable patient data (PHI)** into a tool intended for
  de-identified research values.
- **M6 -- Using NeuroTCS output directly in clinical patient management** without
  the clinical validation that would justify that use.

Each is mapped to a hazard and control in Section 5.

---

## 3. Characteristics related to safety (ISO/TR 24971 Annex A, answered)

- **Does the software make decisions affecting patients?** Indirectly only --
  it informs a human who may make research or (if misused) clinical decisions.
- **Is output relied upon as authoritative?** It is designed to be inspectable
  (citations), but automation bias is a foreseeable risk (M1, M2).
- **Is the software deterministic?** Yes -- by design (deterministic `audit_id`,
  locked invariants); non-determinism would itself be a hazard (H7).
- **Does it handle untrusted input?** Yes -- arbitrary cohort files, including
  potentially malformed or malicious archives (H5).
- **Does it process sensitive data?** It may receive PHI if misused (H6);
  intended input is de-identified.
- **Does it depend on third-party components?** Yes -- a pinned dependency
  closure (supply-chain hazard H8).
- **Does the clinical knowledge it encodes change over time?** Yes -- staging
  criteria evolve (H9).

---

## 4. Risk acceptability criteria

### 4.1 Severity (S) -- harm mediated through a research/clinical decision

| Level | Name | Description (decision-corruption framing) |
|------|------|-------------------------------------------|
| S1 | Negligible | Transient inconvenience; no decision impact (e.g. a cosmetic informational flag misread, immediately self-correcting). |
| S2 | Minor | Reversible research inefficiency; good data briefly questioned but caught on routine review. |
| S3 | Serious | An erroneous *research* conclusion is reached or published; recoverable but with real scientific cost. |
| S4 | Critical | Output contributes to an erroneous *clinical* decision affecting patient management (only reachable via misuse M6 in current scope). |
| S5 | Catastrophic | Output directly contributes to serious patient harm or death. |

> In the intended (research) scope, realistic harm caps at **S3**. S4/S5 are
> reachable only through misuse M6 (clinical deployment without validation),
> which is itself controlled by scope labeling and the RUO status.

### 4.2 Probability (P) -- ESTIMATES (no field data yet)

| Level | Name | Qualitative meaning |
|------|------|---------------------|
| P1 | Improbable | Not expected in the lifetime of typical use. |
| P2 | Remote | Conceivable but unlikely. |
| P3 | Occasional | Likely to occur sometime across the user base. |
| P4 | Probable | Likely to occur for a given user within normal use. |
| P5 | Frequent | Expected routinely. |

> Probabilities are documented engineering judgments. They cannot be empirically
> grounded until post-market / Arm A data exist; this is itself a documented
> limitation (Section 8).

### 4.3 Risk acceptability matrix (S x P)

```
            P1        P2        P3        P4        P5
   S5      ALARP     UNACC     UNACC     UNACC     UNACC
   S4      ALARP     ALARP     UNACC     UNACC     UNACC
   S3      ACC       ALARP     ALARP     UNACC     UNACC
   S2      ACC       ACC       ALARP     ALARP     UNACC
   S1      ACC       ACC       ACC       ACC       ALARP
```

ACC = acceptable; ALARP = acceptable only if reduced as low as reasonably
practicable, with justification; UNACC = unacceptable, must be controlled.

---

## 5. Hazard identification and risk analysis (per-hazard worksheets)

Each worksheet: hazard -> foreseeable sequence of events -> hazardous situation
-> harm; initial risk (S/P); existing control(s) with verification reference;
residual risk; gap.

### H1 -- False-positive flag (valid data flagged impossible/implausible)

- **Sequence:** Audit rule or comparator over-fires -> a clinically valid
  trajectory is labeled impossible/implausible -> user discards or "corrects"
  good data -> biased dataset.
- **Hazardous situation:** A correct value is presented as an error.
- **Harm:** Erroneous research conclusion (S3).
- **Initial risk:** S3 / P3 -> ALARP.
- **Existing controls:**
  - Flags are typed by severity; "implausible/informational" are explicitly
    non-authoritative advisories, not assertions of error (design;
    flag-provenance, v1.57.0).
  - Every flag carries an inspectable citation so the user can adjudicate
    (citation-locked design).
  - Rule packs encode admissible *and* inadmissible transitions from primary
    sources, reducing spurious "impossible" calls (rulepack design).
- **Residual risk:** S3 / P2 -> ALARP. **The true false-positive RATE is
  unmeasured.**
- **Gap:** Flag positive predictive value (PPV) is unknown until **Arm A**.

### H2 -- False-negative / fail-open (wrong data passes "clean")

- **Sequence:** A genuinely impossible value is not flagged (rule gap, silent
  skip, or comparator miss) -> dataset reported clean -> bad data enters a study.
- **Hazardous situation:** Erroneous data is falsely reassured as validated.
- **Harm:** Erroneous research conclusion (S3); S4 under misuse M6.
- **Initial risk:** S3 / P3 -> ALARP (S4 / P2 under misuse -> ALARP).
- **Existing controls:**
  - **Fail-closed orchestrator**: refuses rather than guesses (design).
  - `INCOMPLETE_REFUSED` (exit 3) when no substantive layer scored, so a
    skipped audit cannot masquerade as clean (v1.74.0; tests).
  - Malformed-date detection fails closed instead of silently coercing
    (v1.74.0; reproduction test malformed_test).
  - Coverage manifest reports what was and was not audited (v1.58.0).
  - Vocabulary-mismatch forced-skip refusal (v1.74.0).
- **Residual risk:** S3 / P2 -> ALARP. **Sensitivity is unmeasured.**
- **Gap:** Flag sensitivity / false-negative rate unknown until **Arm A**.

### H3 -- False authority (wrong or fabricated citation)

- **Sequence:** A rule is bound to a wrong PMID/DOI or an unsupported source ->
  the rule appears authoritative -> user trusts an unsupported clinical
  threshold.
- **Hazardous situation:** An unsupported claim is presented as guideline-backed.
- **Harm:** Erroneous research or clinical decision (S3; S4 under M6).
- **Initial risk:** S4 / P2 -> ALARP (high concern: this is the Hayden/Marras
  defect class).
- **Existing controls:**
  - **Networked citation verifier** cross-resolves every PMID (PubMed) and DOI
    (Crossref) and requires the two authoritative records to agree on
    title/journal/first-author (v1.77.0); this caught and fixed a real
    wrong-PMID defect.
  - Verifier **cannot fail open**: a mismatch returns exit 1; total outage
    returns exit 2 ("could not verify" != clean) (v1.76.0; exit-code tests).
  - Offline structural well-formedness scan as a hard CI gate
    (supply-chain workflow).
  - Last networked run: **183/183 resolved, 0 mismatches** (verified).
- **Residual risk:** S4 / P1 -> ALARP. Strongly controlled.
- **Gap:** Verifier confirms identifier->paper integrity, not that the cited
  paper's content fully supports the exact encoded threshold (semantic
  attribution); spot-checked, not exhaustively adjudicated.

### H4 -- Wrong rule pack / vocabulary mismatch (audited against wrong criteria)

- **Sequence:** Data labels do not match the selected rule pack's vocabulary ->
  audit runs against inapplicable criteria -> systematically wrong flags.
- **Hazardous situation:** Data audited against criteria that do not apply to it.
- **Harm:** Erroneous research conclusion (S3).
- **Initial risk:** S3 / P3 -> ALARP.
- **Existing controls:**
  - Vocabulary-coverage threshold; on mismatch the staging layer fails closed
    rather than scoring on non-matching vocabulary (v1.74.0).
  - AD-only scope is explicit; out-of-scope domains are refused (v1.64.0).
  - Label synonym ontology reduces spurious mismatch (v1.59.0/1.60.0).
- **Residual risk:** S3 / P2 -> ALARP.
- **Gap:** Correct pack *selection* still depends on the user; no automated
  domain detector beyond vocabulary coverage.

### H5 -- Malformed / malicious input (crash, hang, or partial result)

- **Sequence:** A malformed or adversarial input (decompression bomb, malformed
  dates, corrupt table) -> crash/OOM/hang, or a partial result mistaken for
  complete.
- **Hazardous situation:** Audit denied, or an incomplete audit presented as
  complete.
- **Harm:** Research inefficiency (S2); false reassurance (S3 if partial-as-
  complete).
- **Initial risk:** S3 / P2 -> ALARP.
- **Existing controls:**
  - **Archive-bomb guardrails**: per-member, ratio, total-size, and member-count
    caps; checked against zip metadata before materializing bytes and re-checked
    on read (v1.75.0; bomb tests).
  - Malformed-date fail-closed (v1.74.0).
  - Ambiguous-input refusal rather than guessing (readers design).
- **Residual risk:** S2 / P2 -> ACC.
- **Gap:** Fuzzing is not exhaustive; novel malformed-input classes possible.

### H6 -- PHI exposure

- **Sequence:** User feeds identifiable data -> NeuroTCS processes/persists/logs
  it -> identifiers exposed in outputs, caches, or logs.
- **Hazardous situation:** Patient identifiers exposed.
- **Harm:** Privacy harm (severity context-dependent; treated as S3 for a
  confidentiality breach).
- **Initial risk:** S3 / P2 -> ALARP.
- **Existing controls:**
  - Intended input is de-identified research values/statuses, not identifiers
    (intended use; documentation).
  - The auditor operates on values/trajectories, not on identity fields, and
    does not require names/MRNs.
- **Residual risk:** S3 / P2 -> ALARP.
- **Control added (v1.80.0):** an **optional direct-identifier (PHI) input
  gate** (src/neurotcs/io/phi_gate.py, docs/PHI_INPUT_GATE.md). It scans
  input column names and sampled values for high-confidence direct
  identifiers and **warns by default** (audit still runs); `--refuse-phi`
  makes it **fail-closed** (EXIT_INPUT, no bundle written). It allowlists the
  de-identified study vocabulary so cohort data (ADNI/OASIS/NACC) does not
  false-positive.
- **Residual gap:** the gate is **best-effort, not a de-identification
  guarantee** -- free-text names, contextual identifiers, and unusual formats
  are not caught. PHI handling is no longer purely by convention, but the
  user remains responsible for de-identification.

### H7 -- Non-reproducible result

- **Sequence:** Dependency drift or platform variance -> different
  flags/`audit_id` on different machines -> an audit cannot be reproduced or
  trusted.
- **Hazardous situation:** The audit result is environment-dependent.
- **Harm:** Scientific/regulatory integrity failure (S3).
- **Initial risk:** S3 / P3 -> ALARP.
- **Existing controls:**
  - Deterministic `audit_id`; locked invariants enforced by tests.
  - Canonical pinned dependency closure (`requirements.lock`) tied to the
    versions that produce the locked invariants; enforced by
    test_reproducibility_structure.
  - **Multi-OS / multi-Python reproducibility CI** (Ubuntu/macOS/Windows x
    3.11/3.12) -- green.
  - Containerized reproducible environment (Dockerfile).
- **Residual risk:** S3 / P1 -> ACC. Strongly controlled with CI evidence.
- **Gap:** Byte-level container reproducibility requires the base image digest
  to be pinned (documented in Dockerfile).

### H8 -- Supply-chain compromise

- **Sequence:** A dependency CVE or tampered package -> altered audit behavior
  or exfiltration.
- **Hazardous situation:** Trusted component behaves maliciously/incorrectly.
- **Harm:** Wrong results (S3) or security breach.
- **Initial risk:** S3 / P2 -> ALARP.
- **Existing controls:**
  - Pinned closure + **pip-audit CVE scan** in CI (push + weekly schedule) --
    currently "No known vulnerabilities found."
  - **CycloneDX SBOM** generated in CI and published as an artifact (v1.75.0).
  - SHA-256 integrity gates on rule packs.
- **Residual risk:** S3 / P1 -> ACC.
- **Gap:** No cryptographic signing/attestation of releases yet; lockfile lacks
  per-artifact hashes (regeneration path with `--generate-hashes` documented).

### H9 -- Clinical-criteria drift (stale rule pack)

- **Sequence:** Staging criteria are revised (e.g. NIA-AA 2018 -> AA 2024) -> an
  old rule pack audits against superseded criteria -> systematically outdated
  flags.
- **Hazardous situation:** Data audited against superseded clinical knowledge.
- **Harm:** Erroneous research conclusion (S3).
- **Initial risk:** S3 / P3 -> ALARP.
- **Existing controls:**
  - Rule packs are versioned and citation-locked to a specific guideline edition
    with `guideline_section`; multiple editions coexist (2018, 2024 numeric and
    biological).
  - The citation verifier ties each pack to a resolvable, dated source.
- **Residual risk:** S3 / P2 -> ALARP.
- **Gap:** Detecting that a guideline has been superseded is a **manual
  maintenance** process; no automated currency check. RECOMMENDED control: a
  documented periodic criteria-review cadence.

### H10 -- Automation bias / scope confusion (misuse M1, M2, M6)

- **Sequence:** User over-trusts output -> treats a flag as diagnosis/measurement
  (M1), or "clean" as fully validated (M2), or deploys in clinical care without
  validation (M6).
- **Hazardous situation:** Output used beyond its evidentiary basis.
- **Harm:** S3 (research) up to S4 (clinical misuse).
- **Initial risk:** S4 / P2 -> ALARP.
- **Existing controls:**
  - Explicit scope and "not 100% true" framing in documentation.
  - Severity-typed flags (informational/implausible are advisory).
  - Coverage manifest communicates what was not audited.
  - RUO status; VALIDATION_PROTOCOL documents what clinical use would require.
- **Residual risk:** S4 / P2 -> ALARP. **Labeling-dependent.**
- **Gap:** Labeling/training is the only control against M6; no technical
  enforcement prevents clinical misuse. This is intrinsic to a research tool and
  is the principal reason for the RUO conclusion.

---

## 6. Risk control completeness and risks introduced by controls

- The fail-closed controls (H2, H4, H5) trade availability for safety: NeuroTCS
  may **refuse** to audit borderline inputs. This is an intentional, documented
  trade-off (refusing is safer than a wrong "clean"); the introduced risk is
  reduced throughput, not patient harm. Accepted.
- The citation verifier's networked dependency (H3) could itself fail (outage);
  this is controlled by the exit-2 "could not verify" semantics and the offline
  structural hard gate, so an outage cannot produce a false "clean."
- No control introduces a new hazard of higher severity than the one it
  mitigates.

---

## 7. Overall residual risk evaluation (the central conclusion)

Most hazards are reduced to ACC or well-justified ALARP by **real, verified
engineering controls** (fail-closed design, citation cross-resolver gate,
reproducibility CI, supply-chain scanning). These address the *verification*
question -- does the tool do what it claims, reproducibly, with honest sources --
and the evidence for that is strong and current.

**However, hazards H1 and H2 carry an irreducible residual:** the true clinical
**correctness** of the flags -- their positive predictive value and sensitivity
on real, adjudicated patient trajectories -- is **unmeasured**. No software
control can establish it; only the Arm A clinical-validation study
(`docs/VALIDATION_PROTOCOL.md`: blinded board-certified adjudicators,
biostatistician co-author, flag-PPV with Wilson CIs by severity tier, OSF
pre-registration) can.

**Therefore the overall residual risk cannot be declared acceptable for clinical
use.** It is assessed as:

- **Acceptable for RESEARCH USE** as a citation-locked, fail-closed,
  reproducible data-quality auditor whose every flag is inspectable and whose
  limitations are documented; and
- **NOT established for CLINICAL USE**, which is gated on completion of Arm A and
  a formal risk-management process owned by a qualified team under a QMS.

This is the honest end state: verification substantially complete; validation
pending; clinical use deferred.

---

## 8. Production and post-market / post-deployment surveillance

Because probabilities here are estimates, post-deployment information is required
to close the loop:

- **Collect** user-reported false positives/negatives (issue template tied to
  the flag's `audit_id` and citation).
- **Re-run** the networked citation verifier on a schedule (already in CI) to
  catch source drift or retraction.
- **Re-run** pip-audit weekly (already in CI) for newly disclosed CVEs.
- **Review** clinical criteria currency on a defined cadence (RECOMMENDED, not
  yet formalized -- see H9 gap).
- **Feed** Arm A results back to replace the estimated P-values for H1/H2 with
  measured rates, and re-evaluate overall residual risk.

---

## 9. Traceability and next documents

- **IEC 62304 (software lifecycle):** a traceability matrix linking each control
  above to its implementing module, test, and CI gate is the recommended next
  artifact (NTCS-RM-002, not yet drafted).
- **Verification evidence** for the controls cited above lives in the test suite
  (~1982 tests), the reproducibility/supply-chain CI workflows, and the release
  CHANGELOG (E-2026-045 through E-2026-051).
- **Validation evidence** does not yet exist and is gated on Arm A.

---

## 10. Open gaps consolidated (action register)

| ID | Gap | Type | Owner action |
|----|-----|------|--------------|
| G1 | Flag PPV / sensitivity unmeasured (H1, H2) | Clinical validation | Run Arm A |
| G2 | Semantic citation attribution not exhaustively adjudicated (H3) | Content review | Rule-by-rule source adjudication |
| G3 | PHI handling by convention (H6) | Software control | DONE v1.80.0: optional warn/refuse PHI input gate (best-effort) |
| G4 | Criteria-currency check is manual (H9) | Process | Define periodic review cadence |
| G5 | No release signing; lockfile lacks hashes (H8) | Supply chain | Sign releases; `--generate-hashes` |
| G6 | ~15 mypy advisory findings | Code quality | Focused typing pass |
| G7 | No formal QMS / IEC 62304 records | Regulatory | Stand up QMS; draft NTCS-RM-002 |

---

*Prepared as an engineering-grade gap-analysis draft. Requires review and
ownership by a qualified risk-management process owner before any reliance.
Not a compliance claim. NeuroTCS is research-use-only pending Arm A.*

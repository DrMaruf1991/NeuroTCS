# NeuroTCS v1.8.0 Reviewer Package

**Audience:** independent technical reviewers — FDA CDRH technical staff, pharma diligence teams, academic peer reviewers, hospital AI governance committees, ESNR-BRACCO independent validators.

This directory contains the third-party verification artifacts for NeuroTCS v1.8.0. Pick your surface based on what you have access to and how much time you have.

---

## Three surfaces, one underlying protocol

| Surface | File | Time | Verdict possible | Needs cohort data? |
|---|---|---|---|---|
| **Local — manual** | `reviewer_verification_prompt.md` (v2 protocol) | 90 min | FULL_REPRODUCED | Yes (your DUA) |
| **Local — AI-assisted** | `cursor_verification_prompt.md` | 25–40 min | FULL_REPRODUCED | Yes (your DUA) |
| **Browser — zero install** | `NeuroTCS_v1.8.0_Reviewer_Verification.ipynb` (Colab) | 5–10 min | FRAMEWORK_INSTALL_VERIFIED only | No |

The three surfaces share the **same underlying canonical protocol** (v2). They differ in how the reviewer executes it and what verdict is achievable from each surface.

## What the verdict labels mean

- **FULL_REPRODUCED** — All accessed cohorts: input SHA-256s match manifest AND audit_ids match locked values AND cold-rerun determinism observed across ≥3 reruns. Strongest possible third-party attestation for v1.8.0.
- **METHOD_CONSISTENT_DIFFERENT_FREEZE** — Input SHA-256s differ from manifest (reviewer's DUA freeze ≠ sponsor's freeze), but cTCS values fall in [0.95, 1.00] and cold-rerun determinism observed.
- **FRAMEWORK_INSTALL_VERIFIED** — Framework cloned at locked commit, installed cleanly, 401 framework-only tests passed, synthetic-data audit ran end-to-end with deterministic output. Cohort verification not attempted.
- **PARTIAL** — Some cohorts verified, others not accessed. Specify which.
- **REFUTED** — A locked invariant did not reproduce on matching inputs. Most informative if obtained.

## What each verdict supports

| Verdict | FDA Q-Sub Volume I | Pharma diligence | Peer review | Hospital governance |
|---|---|---|---|---|
| FULL_REPRODUCED | Strong supporting evidence | Sufficient for pilot greenlight | Strong reproducibility citation | Sufficient input for ARCH-AI review |
| METHOD_CONSISTENT_DIFFERENT_FREEZE | Useful supporting evidence | Sufficient for pilot greenlight (with freeze note) | Acceptable reproducibility citation | Acceptable input for ARCH-AI review |
| FRAMEWORK_INSTALL_VERIFIED | Useful but insufficient | Useful preview | Acceptable for "code available" statement | Insufficient |
| PARTIAL | Depends on which cohorts | Depends on which cohorts | Depends on which cohorts | Depends on which cohorts |
| REFUTED | Critical — sponsor must respond | Critical — diligence halts | Critical — submission affected | Critical — review halts |

No verdict, on its own, constitutes FDA clearance, clinical validation, or deployment authorization. Reproducibility evidence is one input to a multi-part evidence package; per-aim study evidence (Aims 1–5 of the project proposal) remains the substantive clinical validation pathway.

---

## How the sponsor uses these in practice

### FDA Q-Submission (Q1 2027 per project timeline §E.1)

In Volume I — Performance Testing section:

> "Independent third-party reproducibility of v1.8.0 has been verified by [N] non-sponsor reviewers across [M] institutions. Attestations are appended as Attachment Q-Sub-7 in YAML format per the protocol at [protocol URL]. Verdict distribution: [N₁] FULL_REPRODUCED, [N₂] METHOD_CONSISTENT_DIFFERENT_FREEZE, [N₃] FRAMEWORK_INSTALL_VERIFIED. Attestations support, but do not substitute for, the per-aim study evidence in Volume II."

### Pharma BD outreach

In response to "how do we know NeuroTCS does what you claim?":

> "Choose your verification surface. Colab takes 10 minutes and gives you a sense of the framework. Cursor on your secure machine with your internal cohort takes 30 minutes and gives you a FULL_REPRODUCED attestation if your data hashes match the manifest. We do not see your data; the verification runs entirely on your infrastructure."

### Peer review code-and-data-availability statement

> "Code is publicly available at github.com/DrMaruf1991/NeuroTCS @ v1.8.0 under Apache-2.0. Three reviewer-verification surfaces are provided: a manual protocol, a Cursor IDE prompt, and a Colab notebook. As of submission, [N] non-sponsor reviewers have produced [verdicts] per [URL]. Reviewers of this manuscript are invited to execute any of the three surfaces during peer review."

---

## Why three surfaces and not one

We are deliberately lowering the friction-to-engage curve. A reviewer who would not invest 90 minutes manually might invest 30 minutes with Cursor or 10 minutes with Colab. Three surfaces, each with explicit and honest scope, maximize the number of independent attestations the sponsor can collect — which is the actual measure of reproducibility.

## Files in this directory

```
reviewer_package/
├── README.md                                       (this file)
├── reviewer_verification_prompt.md                 (v2 canonical protocol — 90-min manual path)
├── cursor_verification_prompt.md                   (Cursor IDE one-paste assistant — 30-min AI-assisted)
└── NeuroTCS_v1.8.0_Reviewer_Verification.ipynb     (Colab notebook — 10-min zero-install preview)
```

## Honest scope statement

These three artifacts collectively enable independent verification of the v1.8.0 audit pipeline's reproducibility. They do not constitute, are not intended to constitute, and must not be represented as constituting:

- FDA clearance, classification, or approval of any kind
- Clinical validation for any specific clinical decision
- Authorization for use on any individual patient
- Substitution for the per-aim study evidence in the project proposal
- Substitution for institutional review board (IRB) review

Reviewers using these artifacts should consult the open limitations disclosure in `docs/datasheet/ad_neurotcs_datasheet.md` of the v1.8.0 release before signing any attestation.

---

*Apache-2.0 license matches the underlying framework. Sponsor: Dr. Marufjon Salokhiddinov (DrMaruf1991), KIUT Tashkent.*

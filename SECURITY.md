# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.1.x   | ✅        |
| 1.0.x   | ⚠️ legacy, embedded in 1.1 |
| < 1.0   | ❌        |

## Reporting a vulnerability

NeuroTCS does not process patient data directly — vendor predictions are audited against rule packs without retaining PHI — but the framework is intended to be used in clinical-research and regulatory-submission settings where any vulnerability has downstream consequences.

If you discover a security issue, **do not file a public GitHub issue**. Instead email:

**drmaruf1991@gmail.com**

Please include:
- A description of the issue and a minimal reproducer (or screenshots).
- The affected version and platform.
- Any suggested mitigation.

You will receive an acknowledgement within 5 business days. Critical issues will be patched within 14 days; non-critical within 60 days. CVE assignment will be requested for any vulnerability with patient-safety implications.

## What counts as a security issue

- **Critical:** A rule pack loads despite missing required citations (would allow uncertified clinical claims to pass audit).
- **Critical:** SHA-256 stamping produces non-deterministic output (would break reproducibility audit trail).
- **Critical:** Override mechanism bypassed without explicit citation in audit log.
- **High:** Schema validator accepts disallowed extra fields (Pydantic strict-mode regression).
- **High:** YAML loader fails to fail-closed on malformed input.
- **Medium:** Input contract validator passes a submission containing PHI.
- **Medium:** Performance regression causing audit DoS on large cohorts.

## Out of scope

- Dependency vulnerabilities in transitive deps (file upstream).
- Cosmetic issues in documentation.
- Issues in `output_schema` and `validation_harness` while these
  subpackages are marked `__status__ = "planned"`. (Note: `audit_core`
  is `__status__ = "production"` and `adapters` is `__status__ =
  "partial"` — both ARE in scope as of v1.7.1, per the v1.7.1 SECURITY
  fix to the prior over-broad clause.)

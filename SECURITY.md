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
- Roadmap items not yet shipped: `neurotcs.output_schema` (Piece 5, FHIR
  Observation emitter) and `neurotcs.validation_harness` (Piece 7,
  synthetic-trajectory self-tests) — both planned for v1.9.x. As of
  v1.8.1, importing these raises `ImportError` with a roadmap pointer
  (see the `_PlannedModuleFinder` hook in `src/neurotcs/__init__.py`);
  there are no shipped stub directories that could harbor a vulnerability.
  Other subpackages (`audit_core`, `input_contract`, `rulepack`, the v1.7.0
  methodological modules, `reference_adapters`, the v1.1 trajectory adapters)
  are all in production scope.

# Contributing to NeuroTCS

Thank you for your interest in NeuroTCS. This document explains how to set up a development environment, how the codebase is organized, and what changes are appropriate at this stage of the project.

## Repository status

NeuroTCS is currently a **private repository** under active development by Dr. Marufjon Salokhiddinov (MD PhD, ESOR-BRACCO-ESNR Neuroimaging Fellow, KIUT Tashkent). Pieces 1, 2, and 3 of the temporalmetric v1.6 FINAL spec are shipped; pieces 4–7 are in active development. External contributions are welcome once the repo is made public after first Nature Medicine submission and FDA Q-Sub response (~Q1 2027).

Until then, contributions from co-authors and invited reviewers should follow the workflow below.

## Development setup

```bash
git clone https://github.com/DrMaruf1991/NeuroTCS.git
cd NeuroTCS
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python tests/rulepack/test_rulepack.py    # 24/24 should pass
```

## Repository layout

```
NeuroTCS/
├── src/neurotcs/                    importable package
│   ├── input_contract/{v1_0,v1_1}/  pieces 1-2 (SHIPPED)
│   ├── rulepack/                    piece 3 (SHIPPED)
│   ├── audit_core/                  piece 4 (PLANNED)
│   ├── output_schema/               piece 5 (PLANNED)
│   ├── adapters/                    piece 6 (PARTIAL)
│   └── validation_harness/          piece 7 (PLANNED)
├── tests/                           all tests (mirrors src/ structure)
├── docs/spec/                       temporalmetric v1.6 FINAL spec
├── docs/transcription_audit/        per-rule-pack YAML <-> source verification
└── examples/                        end-to-end usage scripts
```

Use `src/` layout means: you **must** install the package (`pip install -e .`) before running tests, or rely on the repo-root `conftest.py` which puts `src/` on `sys.path`.

## Coding standards

- **Python 3.10+**.
- **Pydantic v2 strict mode** for all data classes (extra="forbid").
- **Fail-closed by default.** No best-effort modes, no implicit defaults that change behavior.
- **Citations required.** Every clinical rule must reference `citation_pmid` or `citation_doi` AND `guideline_section`. Loading fails if missing.
- **Type hints everywhere.**
- **Ruff** for linting (`ruff check src/ tests/`).
- **mypy** for type-checking (`mypy src/neurotcs` — non-blocking for now).

## Adding a new rule pack

Until pieces 4–7 ship, the most common contribution is a new rule pack. The process:

1. Create `src/neurotcs/rulepack/rules/<domain>/<framework>.yaml` populated with `schema_version: "1.1.0"`, full `state_space`, every `admissible_transition` carrying a citation AND `guideline_section`.
2. Create `docs/transcription_audit/<domain>_<framework>.md` with the side-by-side YAML ↔ source-paragraph audit.
3. Add behavioral tests in `tests/rulepack/test_rulepack.py` (one or more `test_<domain>_behaviors` functions).
4. Ensure `python tests/rulepack/test_rulepack.py` shows the new pack loading as production and behaving as expected.

## Adding new clinical rules to an existing pack

1. Bump the pack's `ruleset_version` (semver: patch for clarifications, minor for additive rules, major for breaking changes).
2. Add the new transition(s) with full citation + guideline_section.
3. Document the change in the pack's `notes` and in CHANGELOG.md.
4. Update the relevant transcription_audit MD file.
5. Add behavioral tests covering the new rule.

## Validation against real datasets

For changes affecting the AD rule packs, run the real ADNI validation:

```bash
python examples/adni_audit_demo.py
```

Expected: ~12,006 transitions audited, ~65 flagged (~0.54%). Any large deviation from this baseline requires investigation.

## Reporting issues

For bugs, errata in clinical rule transcription, or proposed enhancements, file a GitHub issue with:

- For **transcription errata**: the exact YAML transition, the cited section, and a quote from the source paper showing the discrepancy.
- For **bugs**: a minimal reproducer and the Python + neurotcs versions.

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

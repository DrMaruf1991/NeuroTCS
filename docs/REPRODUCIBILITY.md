# Reproducibility

NeuroTCS is built to be reproducible: the same inputs and the same locked
dependency set produce the same audit results (the same `audit_id` /
coherence-score invariants) on any machine. This page documents the three
independent ways that claim is verified.

## 1. Locked dependency closure

`requirements.lock` pins NeuroTCS's complete dependency closure to the
**canonical reproducibility set** -- the exact versions that produce the locked
`audit_id` invariants (e.g. `pandas==3.0.2`, `numpy==2.4.4`, `scipy==1.17.1`,
`ruff==0.15.13`, `pytest==9.0.3`). These pins are enforced by
`tests/docs/test_reproducibility_structure.py`, so the lockfile and the test
suite can never silently disagree.

The lockfile is intentionally **scoped to NeuroTCS only** -- it is not a freeze
of a shared development environment. A clean install pulls exactly this set and
nothing else:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
pytest -q
```

To regenerate the lockfile with cryptographic hashes (recommended for a release
artifact):

```bash
pip install pip-tools
pip-compile --generate-hashes --extra dev -o requirements.lock pyproject.toml
```

## 2. Containerized reproducibility (`Dockerfile`)

The `Dockerfile` builds NeuroTCS in a clean, pinned container so an auditor on
any host gets a byte-identical dependency set. Running the container *is* the
reproducibility check -- it runs the full suite and exits non-zero on any drift.

```bash
docker build -t neurotcs:local .
docker run --rm neurotcs:local            # full suite; non-zero on any failure
```

For a fully reproducible image, pin the base to a digest (see the note at the
top of the `Dockerfile`).

## 3. Multi-OS / multi-Python CI (`.github/workflows/reproducibility.yml`)

On every push and pull request, GitHub Actions runs the full suite across a
matrix of operating systems (Ubuntu, macOS, Windows) and Python versions
(3.10-3.12), each installing from the lockfile. A dedicated job publishes the
`audit_id` invariant evidence (the validation, threshold-derivation, and
reproducibility-structure tests) on the canonical interpreter.

## Supply-chain assurance (`.github/workflows/supply-chain.yml`)

Adjacent to reproducibility, the supply-chain workflow:

- runs **`pip-audit`** against the locked closure on every push/PR and weekly on
  a schedule, so a CVE disclosed after merge is still surfaced against the
  shipped lockfile;
- regenerates the **CycloneDX SBOM** (`scripts/ci/generate_sbom.py`) and uploads
  it as a build artifact;
- runs the **citation verifier** -- the offline structural scan as a hard gate,
  and live PubMed/Crossref resolution as a best-effort (non-blocking) check so a
  registry outage never blocks a PR while a genuine mismatch still surfaces.

## What reproducibility does and does not establish

Reproducibility establishes that NeuroTCS computes the **same audit result every
time, everywhere** -- it is part of *verification* (the tool does what it
claims). It does **not** establish *validation* (that the flags are clinically
correct on real patients); that requires the Arm A clinical-validation study
described in `docs/VALIDATION_PROTOCOL.md`.

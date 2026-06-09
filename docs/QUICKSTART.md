# NeuroTCS Quickstart

> **Scope (read first).** NeuroTCS is a **research instrument** for auditing the
> reproducibility and internal consistency of longitudinal Alzheimer's-disease
> cohort/trial data against citation-locked staging rules. It is **not** an
> FDA-cleared or CE-marked medical device, **not for clinical use**, and it does
> not diagnose, treat, or make per-patient determinations. It audits values that
> other tools produced; it never measures biomarkers itself. See
> [`docs/SCOPE.md`](SCOPE.md) for the full scope and regulatory status.

This guide gets a new user from install to a first audit in a few minutes.

## 1. Install

NeuroTCS is distributed as a versioned wheel attached to each GitHub Release
(the repository is private; there is no public PyPI package).

```bash
# from a downloaded release wheel
pip install neurotcs-<version>-py3-none-any.whl

# OR directly from a release tag (requires repo access)
pip install "git+https://github.com/DrMaruf1991/NeuroTCS.git@v<version>"
```

Optional extras:

```bash
pip install "neurotcs[radni]"   # adds pyreadr, only needed for the optional
                                # ADNI .rda reference-adapter CLIs
pip install "neurotcs[pdf]"     # PDF report rendering
```

Verify the install:

```bash
python -c "import neurotcs; print(neurotcs.__version__)"
neurotcs --help
```

## 2. Understand your data first (optional but recommended)

`describe` inspects a dataset and scaffolds a column mapping without auditing:

```bash
neurotcs describe path/to/your_cohort.xlsx
```

NeuroTCS accepts a single file (`.csv/.tsv/.xlsx/.xls/.parquet/.json/.sas7bdat/
.dta/.sav/.rds`), a folder of such files, a glob, or a `.zip/.gz` archive.

## 3. Run your first audit

For a conventionally structured cohort, no mapping is needed (zero-config):

```bash
neurotcs audit path/to/your_cohort.xlsx -o ./audit_out
```

This writes a signed bundle (`*.bundle.json`) and a human-readable report
(`*.report.txt`) into `./audit_out`. The bundle's `deterministic_core` carries:

- `severity_counts` -- counts of `impossible`, `implausible`, `informational`
  flags;
- `flags` -- per-record flags keyed by `(subject_id, field, visit)` with a
  `tier` and the `rule_id` that fired;
- `audit_id` -- a deterministic hash; the same input + rules always produce the
  same `audit_id` (this is the reproducibility guarantee).

Useful flags:

```bash
neurotcs audit cohort.xlsx -o out --csv --svg     # also emit flags CSV + summary SVG
neurotcs audit cohort.xlsx -o out --allow-no-dates  # cohort has no date column; use visit order
neurotcs audit cohort.xlsx -o out --confirm-assays  # acknowledge assay-unit assumptions
```

## 4. Re-verify a bundle

Any bundle can be independently re-verified (determinism / integrity check):

```bash
neurotcs verify ./audit_out
```

## 5. Interpreting flags (important, honest)

A flag means a record violated an encoded staging/coherence rule. A flag is
**not** automatically a data error: it may be (a) a true data-quality problem,
(b) legitimate but rare biology the rule did not anticipate, or (c) an
over-strict rule. Distinguishing these requires expert adjudication.

If you intend to **report flag counts scientifically** (e.g. in a paper), first
establish what the flags mean in your cohort using the validation apparatus:

```bash
# measure rule-set detection COVERAGE on a CLEAN cohort (injects a realistic
# error taxonomy and scores detection); this is coverage, NOT accuracy.
neurotcs validate-coverage path/to/clean_cohort.xlsx --seed 0 -o coverage.json
```

The full flag-precision (PPV) study design -- which requires blinded expert
adjudication on a representative cohort -- is specified in
[`VALIDATION_PROTOCOL.md`](VALIDATION_PROTOCOL.md). NeuroTCS ships the design
and the coverage apparatus; the adjudicated precision result is study work, not
a property of the software alone.

## 6. Data governance

NeuroTCS runs where your data already lives. Participant-level cohort data
(ADNI/OASIS-3/NACC/MIRIAD/etc.) is governed by Data Use Agreements and must not
be uploaded to third-party services; the tool comes to the data, never the
reverse. See [`reproducibility/ad_neurotcs_reproducibility.md`](reproducibility/ad_neurotcs_reproducibility.md).

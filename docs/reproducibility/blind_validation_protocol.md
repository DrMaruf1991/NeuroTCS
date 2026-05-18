# AD NeuroTCS — Blind-Validation Protocol

**Status**: AD-lock Step 2.5 deliverable. Shipped in NeuroTCS v1.7.12.
**Audience**: external collaborators with their own AD longitudinal
cohort who want an independent, gaming-resistant validation of cTCS on
that cohort.

This protocol lets you (the external collaborator) run the NeuroTCS AD
audit on a cohort I (the maintainer) have not seen and cannot see — and
report results back in a form that protects both sides:

- **You retain control of your data.** No PHI ever leaves your
  institution. The protocol asks only for de-identified summary
  statistics + cryptographic hashes.
- **I cannot tune the rule pack to your data.** Rule packs are
  citation-locked, hash-verified, and version-tagged before you
  audit. Any post-hoc modification by me would break the SHA
  verification you perform.
- **Neither side can misrepresent the result.** The audit_id is a
  SHA-256 fingerprint of (rule pack, per-patient scores, bootstrap
  parameters). Reproducing it requires the same inputs end-to-end.

The protocol is also the canonical pattern for any future independent
validation submitted as evidence to FDA, EMA, EU AI Act notified bodies,
or peer-reviewed publications.

---

## 1. What you need before starting

### 1.1 — Cohort data requirements

Your cohort must be a longitudinal AD diagnostic-trajectory dataset:

| Required | Description |
|---|---|
| ≥ 2 visits per subject | Subjects with one visit contribute no transitions. |
| Categorical diagnostic state | NIA-AA 2018 conventions: `CN` (cognitively normal), `MCI`, `AD-dementia`. |
| Per-visit timestamps | Day precision is sufficient. UTC preferred. |
| ≥ 50 unique subjects | Below this, the bootstrap CI is wide enough to be uninformative. There is no upper limit. |

### 1.2 — Demographic data (for fairness panel)

Optional but strongly recommended:

| Attribute | Purpose |
|---|---|
| Sex (`M` / `F` / `unknown`) | FUTURE-AI Panel B.4.4 stratification |
| Age at baseline | Computed into 10-year band (`60-69`, `70-79`, etc.) |
| Race / ethnicity | FUTURE-AI Panel B.4.4 stratification |
| APOE4 status | (optional) carrier / non-carrier / homozygote |

### 1.3 — Compute environment

- Python 3.12.x
- `pip install -r requirements.lock` (canonical pinned versions)
- Approximately 10 minutes wall-clock for a 1,000-subject cohort with
  the default bootstrap (B=10,000).

---

## 2. Protocol overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                    BLIND VALIDATION PROTOCOL                          │
│                                                                       │
│  Phase A: PRE-REGISTRATION                                            │
│    1. You declare intent. You name the cohort source and approximate │
│       n. I respond with the locked NeuroTCS tag (e.g., v1.7.12) and  │
│       the three AD rule-pack SHAs you must verify.                    │
│                                                                       │
│  Phase B: VERIFICATION                                                │
│    2. You verify the rule packs. You clone the tag, run the SHA      │
│       commands, confirm the three rule-pack SHAs match. You run      │
│       `pytest tests/ -q` and confirm 331 passed + 2 skipped.         │
│                                                                       │
│  Phase C: AUDIT                                                       │
│    3. You transform your cohort into a NeuroTCS Input Contract       │
│       v1.1 submission (use one of the adapter patterns as template). │
│    4. You compute CSV SHA-256 checksums (these become PUBLIC; the    │
│       CSVs themselves remain on your machine).                       │
│    5. You run the audit pipeline. You record audit_id, audit_id_v2, │
│       cTCS point + 95% BCa CI, n_transitions, n_flagged.             │
│    6. You run the fairness panel B.4.4 if you have demographics.     │
│       You record per-stratum flag rates and max disparity.           │
│                                                                       │
│  Phase D: REPORTING                                                   │
│    7. You send back ONLY:                                            │
│       - The audit summary (the JSON / text output of the runner).    │
│       - The CSV SHA-256 checksums.                                   │
│       - Your cohort's high-level demographic distribution            │
│         (counts per stratum; no individual rows).                    │
│       - Any anomalies or warnings the audit pipeline emitted.        │
│                                                                       │
│  Phase E: PUBLICATION                                                 │
│    8. The reported audit_id + cTCS becomes a published locked        │
│       invariant. Any subsequent NeuroTCS release that affects the    │
│       AD pipeline must reproduce your audit_id bit-exactly on the    │
│       same inputs, or be flagged as a behavioural change.            │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase A — Pre-registration

### 3.1 — What you tell the maintainer (no PHI)

Open a GitHub Issue at `DrMaruf1991/NeuroTCS/issues` with the title
"Blind-validation pre-registration" and the following template:

```yaml
collaborator:
  name: <your name>
  institution: <your institution>
  contact: <email>
  ORCID: <if available>

cohort:
  source: <e.g., "single-site academic cohort", "consortium X registry">
  irb_approval: <IRB protocol number; no patient-level details>
  approximate_n_subjects: <integer>
  approximate_n_visits: <integer>
  date_range_years: <e.g., "2018-2024">
  state_labels_used: <e.g., "CN / MCI / AD-dementia per NIA-AA 2018">

intent:
  rule_pack: <one of: "ad/niaaa_2018", "ad/aa_2024", "ad/aa_2024_trac">
  fairness_attributes_available: <list, e.g., ["sex", "age_band"]>
  expected_completion: <YYYY-MM-DD>
```

### 3.2 — What the maintainer commits to (no rule-pack changes mid-flight)

The maintainer responds with:

- The canonical NeuroTCS tag for this validation (e.g., `v1.7.12`).
- The three AD rule-pack SHA-256 hashes from Section 1.1 of
  `docs/reproducibility/ad_neurotcs_reproducibility.md`.
- A commitment NOT to modify any AD rule pack until the validation is
  complete. Any pre-completion rule-pack change would be a protocol
  violation; the validation switches to a frozen branch tag if any
  upstream change is unavoidable.

This commitment is publicly verifiable: the rule-pack SHA is a function
of the YAML content; if the maintainer changed it post-registration, the
collaborator's SHA verification would fail.

---

## 4. Phase B — Verification

### 4.1 — Verify the code is what was promised

Run the canonical Section 3.1–3.3 commands from
`docs/reproducibility/ad_neurotcs_reproducibility.md`. Three rule-pack
SHAs must match. Test suite must report 331 passed + 2 skipped.

### 4.2 — Verify your environment is reproducible

Confirm your Python is 3.12.x and your package versions match
`requirements.lock`:

```bash
python --version
# Python 3.12.x

pip list --format=freeze | grep -E "pydantic|numpy|scipy|pandas|PyYAML|pyarrow|jsonschema|pyreadr|pytest|ruff"
# Should match requirements.lock pins.
```

If any version differs, your audit_id may diverge from the cohort-level
audit_ids in Section 1.2 of the reproducibility report. This is a
warning, not a failure — your local audit_id is still a valid
cryptographic fingerprint of YOUR run. It just won't match the
maintainer's MIRIAD audit_ids (which you wouldn't be reproducing anyway,
since you're running on your own cohort).

---

## 5. Phase C — Audit execution

### 5.1 — Step 1: Transform your cohort into the Input Contract

Write an adapter that produces a list of `Trajectory` objects with
metadata for each patient. Templates available in the repo:

- `src/neurotcs/input_contract/v1_1/adapters/adapter_miriad.py` —
  reference XNAT-export pattern (recommended for the cleanest example
  including demographic extraction).
- `src/neurotcs/input_contract/v1_1/adapters/adapter_oasis3.py` —
  reference for a longitudinal CDR-based cohort.
- `src/neurotcs/input_contract/v1_1/adapters/adapter_adni.py` —
  reference for an ADNI-style DXSUM extraction.

Your adapter must:

- Produce `Trajectory` objects with `patient_id` (hashed if PHI),
  `states` (using `CN` / `MCI` / `AD-dementia` labels), `dates` (date
  objects, ascending per patient).
- Populate `Trajectory.metadata` with the canonical FUTURE-AI fairness
  attribute names: `sex`, `age_band`, `race_ethnicity`, `comorbidity`,
  `disease_stage`, `treatment_status` (any subset; unknown attributes
  produce an `unknown` stratum which is correct behaviour).
- Hash patient IDs with a cohort-specific salt before any output
  (SHA-256 + salt is the canonical pattern; see `hash_patient_id` in
  the reference adapters).

### 5.2 — Step 2: Compute CSV checksums (PUBLIC component)

Before running the audit, compute SHA-256 checksums of every input CSV
the adapter reads. These checksums become part of the published
validation result; the CSVs themselves never leave your machine.

```bash
python scripts/compute_input_checksums.py --json /path/to/your/csvs/*.csv \
    > my_cohort_checksums.json
```

Save `my_cohort_checksums.json` — you will commit this to the Phase D
report.

### 5.3 — Step 3: Run the audit

```python
# my_blind_validation.py
import json
from neurotcs import audit, load_rulepack
from neurotcs.fairness import cohort_fairness_audit
from my_adapter import load_my_cohort  # YOUR adapter, written in Step 1

trajectories = load_my_cohort(...)
pack = load_rulepack("ad/niaaa_2018")    # or whichever pack you registered

result = audit(
    trajectories, pack,
    bootstrap_B=10_000,
    seed=42,
    ci_method="bca",
    return_per_transition=True,           # required for fairness panel
)

# Audit summary (the PUBLIC report)
summary = {
    "neurotcs_version": "v1.7.12",
    "rulepack_id": result.rulepack_id,
    "rulepack_sha256": result.rulepack_sha256,
    "audit_id": result.audit_id,
    "audit_id_v2": result.audit_id_v2,
    "n_patients": result.n_patients,
    "n_patients_scored": result.n_patients_scored,
    "n_transitions": result.n_transitions,
    "n_flagged": result.n_flagged,
    "flagged_rate": result.flagged_rate,
    "ctcs": {
        "point": result.ctcs.ci.point,
        "ci_95_low": result.ctcs.ci.ci_low,
        "ci_95_high": result.ctcs.ci.ci_high,
        "ci_method": result.ctcs.ci.ci_method,
        "B": result.ctcs.ci.B,
        "seed": result.ctcs.ci.seed,
    },
}
with open("audit_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# Fairness panel (optional, requires demographics in metadata)
fairness = cohort_fairness_audit(result)
fairness_summary = {
    "panel_id": fairness.panel_id,
    "framework_doi": fairness.framework_doi,
    "framework_pmid": fairness.framework_pmid,
    "overall_flag_rate": fairness.overall_flag_rate,
    "max_disparity": fairness.max_disparity,
    "max_disparity_stratum": fairness.max_disparity_stratum,
    "strata": [
        {"attribute": s.stratum_name, "value": s.stratum_value,
         "n": s.n, "n_flagged": s.n_flagged,
         "flag_rate": s.flag_rate,
         "statistical_parity": s.statistical_parity}
        for s in fairness.strata
    ],
}
with open("fairness_summary.json", "w") as f:
    json.dump(fairness_summary, f, indent=2)
```

### 5.4 — Step 4: Demographic distribution summary (PUBLIC component)

Produce a per-stratum count table — no individual rows, just aggregates:

```python
# demographics.py
from collections import Counter

# After loading your trajectories
sex_counts = Counter(t.metadata.get("sex", "unknown") for t in trajectories)
age_counts = Counter(t.metadata.get("age_band", "unknown") for t in trajectories)

with open("demographic_distribution.json", "w") as f:
    json.dump({
        "n_subjects": len(trajectories),
        "sex": dict(sex_counts),
        "age_band": dict(age_counts),
    }, f, indent=2)
```

---

## 6. Phase D — Reporting back

### 6.1 — What to commit to the validation issue

Reply to your Phase A pre-registration issue with these four artifacts
(all small, all PHI-free):

| Artifact | Content |
|---|---|
| `audit_summary.json` | Audit identifiers + cTCS + flag counts |
| `fairness_summary.json` (optional) | Per-stratum flag rates |
| `demographic_distribution.json` | Cohort demographics (counts only, no rows) |
| `my_cohort_checksums.json` | CSV SHA-256 hashes from Phase C Step 2 |

### 6.2 — Verification by the maintainer

The maintainer verifies:

- The `rulepack_sha256` in `audit_summary.json` matches the
  pre-registered SHA. (If not, the wrong rule pack was used.)
- The audit pipeline parameters (`B=10000, seed=42, ci_method="bca"`)
  match the canonical values. (If not, a non-canonical run was made.)
- The `neurotcs_version` matches the pre-registered tag.

If all three checks pass, the validation is **independent and binding**.
The maintainer can publish the `audit_id` + `cTCS CI` + cohort
demographics as an additional locked invariant alongside the
ADNI/OASIS-3/MIRIAD primary results.

### 6.3 — What the maintainer publishes

A single new entry in `docs/validation/external_validations.md`
(created lazily on first validation):

```markdown
## External validation #N: <institution code>

- Date: <YYYY-MM-DD>
- NeuroTCS version: v1.7.12
- Rule pack: ad/niaaa_2018@1.2.0 (SHA-256 f359148d1cbf6abe...)
- Cohort: <high-level description, n_subjects, n_transitions>
- audit_id: <SHA-256 from collaborator>
- cTCS: <point> (95% CI <low>, <high>)
- Fairness: <max disparity + stratum, if available>
- CSV checksums: <commit hash linking to the published checksums>
```

---

## 7. Anti-gaming guarantees

### 7.1 — Why the maintainer cannot tune the rule pack to your data

Each AD rule pack has a SHA-256 hash that is a function of its YAML
content. The hash for `ad/niaaa_2018@1.2.0` is
`f359148d1cbf6abed3d4f1d36de6b3bf315c10e8997d5e73beb1a0d7bdf9e374` for
v1.7.12; you verified this in Phase B Step 1. If the maintainer modified
the rule pack between pre-registration and your audit, your local SHA
would no longer match.

### 7.2 — Why you cannot misrepresent the result

The `audit_id` is a function of the rule-pack SHA, per-patient cTCS
scores, bootstrap parameters, and seed. If you reported a different
cTCS than the audit_id implies, the maintainer could regenerate the
audit_id from your reported cTCS and detect the inconsistency.

For stronger guarantees, the maintainer can run a "spot check": you
share a small subset of your trajectory STATES (not patient IDs, not
dates beyond month-precision, not demographics), and the maintainer
re-runs the audit on the subset and confirms the resulting partial
audit_id is consistent with the per-patient cTCS arrays you reported.

### 7.3 — Why neither side can post-hoc reroll

Once an audit_id is published in Phase E, both sides have committed.
A subsequent NeuroTCS release that affects the AD pipeline must
reproduce the published audit_id bit-exactly on the same inputs, OR it
must explicitly document the behavioural change in CHANGELOG.md and
re-validate.

---

## 8. Honest gaps in the protocol

- **No formal IRB-level coordination.** The protocol assumes each
  collaborator has their own IRB approval for their own cohort. There
  is no central IRB; cross-institutional data-sharing is NOT part of
  the protocol (no PHI flows between sides).
- **No automated CI hook for external validations.** The maintainer
  verifies the four artifacts manually before publishing the
  validation. A future enhancement could add a CI workflow that
  ingests `audit_summary.json` and verifies its consistency
  automatically, but this is not yet implemented.
- **No formal blind-validation timeline SLA.** Validations are
  best-effort; the maintainer commits to responding within 14 days to
  pre-registration issues but does not guarantee verification time
  for the artifacts in Phase D.
- **The protocol is one-way.** The collaborator audits AGAINST our
  rule pack. There is no symmetric step where the maintainer audits
  the collaborator's audit logic — only the cryptographic identity of
  the rule pack and audit pipeline. This is intentional: the rule
  pack is what's being validated, not the collaborator's adapter.

---

## 9. Reference contact

Open issues at: `https://github.com/DrMaruf1991/NeuroTCS/issues`.
For DUA-required communications, contact the maintainer via the
institutional address on the project README.

---

## 10. Citation

When citing a blind validation result, cite both:

- Salokhiddinov M. NeuroTCS v1.7.12. 2026. (Software.)
- The specific validation entry in
  `docs/validation/external_validations.md` (lists external collaborator
  institution + audit_id).

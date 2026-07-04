# NeuroTCS Live Web Demo

A thin FastAPI + single-page frontend over the **shipped NeuroTCS audit engine**.
Experts open the page on the private Azure App Service and trigger **real audits**
of five public AD cohorts; the page shows the real cTCS, 95% CIs, flagged
transitions, cited rule packs (PMID/DOI), and the reproducibility `audit_id` —
computed live by the real engine on the real DUA data.

> NeuroTCS is an **auditor, not a measurement tool**. It checks whether a cohort's
> `CN → MCI → AD` trajectories obey published staging criteria (NIA-AA 2018). It
> never measures, segments, diagnoses, or infers. **There is no LLM anywhere.**

## Parity by construction

The web reuses the **exact** functions the CLI's `--cohort` path uses — it never
recomputes cTCS or re-implements a crosswalk:

```
read_tables(path)                              # neurotcs.io          (same loader)
  → recognize_cohort(tables)                   # neurotcs.cohorts     (signature match)
  → match.build_mapping(tables)                # cohort recognizer    (CDR/MMSE crosswalk)
  → tables_to_submission(tables, mapping)      # neurotcs.io          (same submission)
  → run_full_audit(submission,                 # neurotcs.orchestration (THE engine)
                   expected_layers=["staging_clinical"])
  → result.layers["staging_clinical"].summary  # ctcs, n_transitions, n_flagged
```

This is the identical path proven in `tests/audit_core/test_real_a4_audit.py` and
its siblings. See [`engine.py`](engine.py) — the whole reuse layer is ~30 lines of
orchestration and zero clinical logic.

## Locked invariants (the web must reproduce these EXACTLY)

| cohort  | cTCS      | transitions | flagged | input                              |
|---------|-----------|-------------|---------|------------------------------------|
| a4      | 0.996374  | 8892        | 34      | `A4Learn/Raw Data/cdr.csv`         |
| nacc    | 0.991502  | 158423      | 1217    | `investigator_nacc73.csv`          |
| oasis3  | 0.9942    | 7248        | 30      | `OASIS3_UDSb4_cdr.csv`             |
| adni    | 0.994575  | 12006       | 65      | `ADNIMERGE2/data/DXSUM.rda`        |
| miriad  | 0.985369  | 454         | 7       | MIRIAD dir (3 XNAT CSVs)           |

Tolerance: **0.0005** on cTCS, **exact** on the transition/flagged counts.

## API

| method | path                    | returns                                                        |
|--------|-------------------------|---------------------------------------------------------------|
| GET    | `/api/health`           | liveness + `neurotcs` version on the server                   |
| GET    | `/api/cohorts`          | the 5 cohorts, availability (path configured?), locked values |
| POST   | `/api/audit/{cohort}`   | de-identified result + live parity check                      |
| POST   | `/api/upload/describe`  | read an uploaded `.xlsx/.csv`, suggest a column mapping        |
| POST   | `/api/audit/upload`     | audit an uploaded file with a confirmed mapping               |
| GET    | `/`                     | the single-page frontend                                      |

### Upload audit (bring-your-own file)

The "Audit your own file" panel lets an expert drop an `.xlsx`/`.csv` staging
table and audit it through the **same engine path** the cohorts use:

```
_read_bytes_as_table(data)              # neurotcs.io.readers — in-memory (BytesIO)
  → describe_tables → _scaffold_mapping # the `neurotcs describe` auto-mapping
  → (user confirms subject_id/state/visit_date in the UI)
  → tables_to_submission → run_full_audit → build_bundle
```

`POST /api/upload/describe` returns the sheet/column inventory + an auto-suggested
mapping; `POST /api/audit/upload` takes the file plus the confirmed mapping (JSON:
`{sheet, subject_id, state, visit_date?, visit?}`) and an optional `normalize`
flag, and returns cTCS, CI, counts, flags (of the caller's own file), citations,
`audit_id`, and the bundle.

**Label normalization** (`normalize`, default on): reuses the shipped
citation-anchored ontology (`normalize_labels`) to map common text labels
("Normal"→CN, "Alzheimer's disease"→AD, "early MCI"→EMCI, …) to the canonical
staging vocabulary. Every substitution is reported in the response
(`label_normalization`) — never silent. Numeric scale scores (CDR-global,
NACCUDSD) are **not** converted; those need cohort-specific crosswalks.

**De-identification**: subject ids are **hashed before the audit runs**, so the
cTCS, flags, `audit_id`, and the bundle are all computed over hashes — no raw id
enters the engine or any returned artifact (the bundle stays self-verifying, and
cTCS is unchanged since hashing is a bijection on the id).

A user-facing guide lives at [`demo/DATASET_REQUIREMENTS.md`](DATASET_REQUIREMENTS.md)
and is served in-app at `/DATASET_REQUIREMENTS.md` (linked from the upload panel's
"What file do I need?" help).

**Accepted formats & disk policy** (50 MB cap; the caller's own file, not a DUA
cohort — discarded when the request returns):

- **Tabular** — `.csv .tsv .txt .xlsx .xls .parquet .json .jsonl .ndjson`: parsed
  entirely in memory via `BytesIO`, **nothing written to disk**
  (`read_mode="in_memory"`).
- **Statistical & archive** — `.rds .rdata .rda .sav .dta .sas7bdat .zsav .zip`:
  their readers (pyreadr/pyreadstat, zip) require a filesystem path, so the bytes
  are written to a **secure temp directory** (`mkdtemp`, 0700) under the file's
  original name, read via the shipped `read_tables`, and the directory is removed
  immediately in a `finally` block — even on error
  (`read_mode="transient_temp_file"`). The response reports which path was used so
  the UI can state it plainly.

`POST /api/audit/{cohort}` returns **results only** — no raw records, no subject
ids:

```json
{
  "cohort": "a4", "ctcs": 0.996374, "ci_low": 0.9957, "ci_high": 0.9971,
  "n_transitions": 8892, "n_flagged": 34, "flagged_rate": 0.0038,
  "status": "FLAGS_PRESENT",
  "audit_id": "…sha256…", "rulepack_id": "ad/niaaa_2018@1.3.0",
  "citation_pmid": "29653606", "citation_doi": "10.1016/j.jalz.2018.02.018",
  "neurotcs_version": "1.85.1",
  "parity": { "parity_holds": true, "…": "…" }
}
```

Fail-closed status codes: `404` unknown cohort, `503` data path not configured /
missing, `409` data did not match the cohort signature, `500` engine error.

## Verification gate — ship only when this is green

```bash
# On the server (or any host with the DUA data + env vars configured):
pytest demo/test_web_parity.py -v
```

For each cohort it drives `POST /api/audit/{cohort}` and asserts the web result is
within 0.0005 of the locked cTCS **and** the counts match exactly — the same
standard as the `test_real_*_audit.py` invariants. A cohort whose data path is not
configured is **skipped** (identical data-gating to the shipped tests), so on a
machine without the DUA data the suite reports `skipped`, not `failed`. On the
deploy target, where all five paths are set, it runs green for all five.

## Run locally (dev)

```bash
pip install .                        # the shipped engine (from this repo)
pip install -r demo/requirements.txt # web layer
cp demo/.env.example demo/.env       # point env vars at your DUA files
set -a; source demo/.env; set +a
uvicorn demo.app:app --reload --port 8000
# open http://127.0.0.1:8000
```

Cohorts with no configured path render as **"no data"** and their Run button is
disabled — the demo still shows the locked invariants for context.

## Deploy — private Azure App Service (Linux, Python 3.11)

Keep the existing **access control on** (the App Service is private; the DUA data
lives on it precisely because it is access-controlled). These are the exact steps.

### 1. App settings (Configuration → Application settings)

| setting                            | value                                             | why |
|------------------------------------|---------------------------------------------------|-----|
| `NEUROTCS_A4_CDR`                  | server path to `A4Learn/Raw Data/cdr.csv`         | data path (never in repo) |
| `NEUROTCS_NACC_CSV`                | server path to `investigator_nacc73.csv`          | data path |
| `NEUROTCS_OASIS3_CDR`              | server path to `OASIS3_UDSb4_cdr.csv`             | data path |
| `NEUROTCS_ADNI_DXSUM_RDA`          | server path to `ADNIMERGE2/data/DXSUM.rda`        | data path |
| `NEUROTCS_MIRIAD_DIR`              | server directory holding the 3 MIRIAD XNAT CSVs   | data path |
| `SCM_DO_BUILD_DURING_DEPLOYMENT`   | `true`                                            | run Oryx pip build on deploy |
| `WEBSITES_PORT`                    | `8000`                                            | matches gunicorn `--bind` |
| `WEB_TIMEOUT`                      | `600`                                             | headroom for the large NACC audit |

Python version: **3.11** (App Service "Python 3.11" runtime — the version the
engine is tested on).

### 2. Startup command (Configuration → General settings → Startup Command)

```
bash demo/startup.sh
```

`startup.sh` installs the engine **from this repo** (`pip install .` → the exact
shipped 1.85.1), installs the web deps, then **refuses to start** unless
`neurotcs.__version__ == 1.85.1` — so the server can never serve a result under a
different engine than the one the cTCS is locked to. It then runs gunicorn with a
uvicorn worker.

### 3. Deploy the code

Using the Azure CLI, zip-deploy the repo (Oryx builds it server-side):

```bash
az webapp up \
  --name <APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --runtime "PYTHON:3.11"

# or, for an existing app, a zip deploy:
zip -r app.zip . -x '.git/*' 'tests/*' '*.pyc'
az webapp deploy \
  --name <APP_NAME> --resource-group <RESOURCE_GROUP> \
  --type zip --src-path app.zip
```

### 4. Confirm on the server

```bash
# engine version must match the locked-invariant version
curl -s https://<APP_NAME>.azurewebsites.net/api/health
# -> {"status":"ok","neurotcs_version":"1.85.1", ...}

# run the parity gate against the LIVE deployment (all five must pass)
NEUROTCS_A4_CDR=... NEUROTCS_NACC_CSV=... NEUROTCS_OASIS3_CDR=... \
NEUROTCS_ADNI_DXSUM_RDA=... NEUROTCS_MIRIAD_DIR=... \
  pytest demo/test_web_parity.py -v
```

## DUA / compliance boundary (do not cross)

- The server is private + access-controlled → the DUA data may live on it for
  live audits. Data paths come **only** from App Settings (env vars); no path is
  hardcoded and no path string is ever returned to the browser (only *whether* a
  cohort is available).
- The browser receives **results only**: cTCS, CIs, counts, cited rules, a hashed
  `audit_id`. Never raw cohort records, never real subject ids.
- The repo contains **app code + this README only**. All data extensions
  (`*.csv`, `*.rda`, `*.xlsx`, `data/`, `demo/.env`, `demo/**/*.bundle.json`) are
  gitignored. Never commit raw cohort files or generated bundles.

# Preparing Your Dataset for NeuroTCS (Upload)

A quick guide to what your file must contain so the **"Audit your own file"** upload
runs cleanly and gives a valid consistency score (cTCS). Following this avoids the
common errors.

> This guide is specifically for the **web upload path**. The five built-in public
> cohorts (A4, NACC, OASIS-3, ADNI, MIRIAD) use dedicated loaders with extra
> crosswalks that the generic upload does **not** apply — see *State column* below.

---

## What NeuroTCS does (so the requirements make sense)

NeuroTCS audits **longitudinal disease-state trajectories** — it follows each
subject across their visits and checks whether the sequence of clinical stages
(CN → MCI → AD) is consistent with published staging rules (NIA-AA 2018). It does
**not** measure, diagnose, or segment anything; it audits staging data you already
have.

Because it audits *trajectories over time*, your data must be **longitudinal**:
multiple visits per subject, in a known time order.

---

## The three columns NeuroTCS must find

Your file needs, at minimum, these three pieces of information (column names can
differ — you map them in the UI after upload):

| Role | What it is | Example values |
|------|-----------|----------------|
| **subject_id** | A stable identifier for each person | `S001`, `PT-4471`, a coded ID |
| **visit_date** *or* **visit** | When each assessment happened, or its order | `2019-03-14`, or `1, 2, 3...` |
| **state** | The clinical stage at that visit | `CN`, `MCI`, `AD` |

- **subject_id** must be the SAME value across a person's visits (that's how visits
  are grouped into one trajectory).
- **visit_date** orders the visits within each subject. If you have no dates but a
  visit number/order, that works too. If you have **neither**, order is derived from
  row order (you'll see a warning) — provide dates or a visit index for a clean order.
- **state** must resolve to **CN**, **MCI**, or **AD** (see next section).

---

## The `state` column: what the upload accepts

**✅ Already-labelled states (simplest — always works):**
`CN` (cognitively normal), `MCI` (mild cognitive impairment), `AD` (dementia).
The canonical sub-stages `SMC`, `EMCI`, `LMCI` are also accepted.

**✅ Common text synonyms (auto-normalized when "Normalize stage labels" is ON —
it is by default):**
The upload reuses NeuroTCS's citation-anchored label ontology, so these map
automatically:

| Your label | Becomes |
|------------|---------|
| `Normal`, `Cognitively Normal`, `NC`, `CU` | `CN` |
| `early MCI` | `EMCI` |
| `Alzheimer's disease`, `Alzheimer's dementia` | `AD` |

Every substitution is shown in the result ("Normalized stage labels: …") — nothing
is changed silently. If your labels aren't recognized, the audit fails clearly and
you can rename them to CN/MCI/AD.

**❌ Numeric scale scores are NOT converted on the upload path:**
`CDR-global` (0 / 0.5 / 1 …), `NACCUDSD` codes (1 / 2 / 3 / 4), MMSE, etc. are
**not** crosswalked here — those conversions are specific to each public cohort's
loader. If your `state` column is a numeric score, **convert it to CN/MCI/AD before
uploading**, for example CDR-global `0 → CN`, `0.5 → MCI`, `≥1 → AD`. (Or, for a
recognized public cohort, use the CLI: `neurotcs audit <file> --cohort <id>`.)

---

## Requirements checklist (avoid the common errors)

Before uploading, confirm:

- [ ] **Longitudinal**: at least some subjects have **2+ visits**. A file with one
      row per subject (cross-sectional) has no trajectory to audit → no cTCS.
- [ ] **Consistent IDs**: a subject's ID is identical across their visits (watch for
      trailing spaces, case differences, `S1` vs `s1`).
- [ ] **Orderable visits**: a date or a visit number per visit (or accept the
      derived-from-row-order warning).
- [ ] **Mappable states**: every state is CN/MCI/AD (or a recognized text synonym,
      with normalization on). Numeric scores must be pre-converted. Unmappable values
      (blank, `Unknown`, `8`, `-99`) are dropped, not guessed — if too many drop, the
      audit thins out.
- [ ] **One staging table**: a single sheet/file with these columns. (A `.zip` may
      contain several files, but multi-file joins like MIRIAD are handled by the
      cohort loaders, not the generic upload.)
- [ ] **Supported format** (see below).

---

## Supported formats

| Group | Extensions | How it's read |
|-------|-----------|---------------|
| Tabular | `.csv` `.tsv` `.txt` `.xlsx` `.xls` `.parquet` `.json` `.jsonl` `.ndjson` | **In memory** (nothing written to disk) |
| Statistical / archive | `.rds` `.rdata` `.rda` `.sav` `.dta` `.sas7bdat` `.zip` | Read via a **secure temp file, deleted immediately** after parsing (their readers need a path) |

Size limit: **50 MB**. The result shows which read path was used.

---

## Minimal valid example

The simplest file that audits cleanly — three columns, several subjects, multiple
visits each:

| subject_id | visit_date | state |
|-----------|-----------|-------|
| S001 | 2018-01-10 | CN  |
| S001 | 2019-01-15 | CN  |
| S001 | 2020-01-20 | MCI |
| S002 | 2018-03-01 | MCI |
| S002 | 2019-03-05 | AD  |
| S003 | 2018-06-01 | CN  |
| S003 | 2019-06-01 | CN  |

3 subjects, 2–3 visits each, orderable by date, states all CN/MCI/AD → a valid cTCS.

---

## What each message means (and the fix)

- **"mapping incomplete: 'sheet', 'subject_id' and 'state' are required"** → pick a
  subject id and a state column in the mapping dropdowns before running.
- **"the staging layer did not run — check that 'state' points at a recognized
  staging column"** → your state values didn't resolve to CN/MCI/AD. Turn on
  "Normalize stage labels", or (for numeric scores) pre-convert to CN/MCI/AD.
- **"mapping does not match the data"** → a chosen column isn't in the sheet (e.g.
  wrong sheet selected). Re-check the dropdowns.
- **"has no visit column; visit index was DERIVED from … order"** *(warning, not an
  error)* → some/all visits had no date; order came from row order. Provide dates or
  a visit index for a guaranteed-correct order.
- **cTCS = 1.0 with very few transitions** → your data has almost no state changes
  (subjects stay in one stage). Technically valid, but not an interesting audit —
  confirm the data really is longitudinal with some progression.
- **Very high "flagged" rate** → many transitions violate the staging rules. That's
  a *real finding* (the audit doing its job), not an error — inspect the flagged
  transitions to see what's inconsistent.

---

## Privacy

- The upload is the **caller's own file**, processed transiently and **discarded when
  the audit returns** — nothing is stored server-side.
- **Subject ids are hashed** before the audit runs, so the results, the flagged-
  transitions table, and the downloadable bundle carry only stable, non-reversible
  hashes — never your raw ids.
- Still, upload **de-identified** data only — no names, no MRNs, no dates of birth.
  Coded subject ids are fine (and are hashed in the output).

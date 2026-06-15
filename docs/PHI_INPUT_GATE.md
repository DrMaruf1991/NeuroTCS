# PHI Input Gate

Document ID: NTCS-DOC-PHI
Related: hazard H6 / gap G3 (docs/HAZARD_ANALYSIS.md), src/neurotcs/io/phi_gate.py

## What it is

NeuroTCS audits **de-identified** research values. It operates on
values/trajectories, not identity fields, and subject_id values flow into the
output bundle's flags. If a user misuses the tool by feeding identifiable
patient data (PHI) -- e.g. a column that is really a patient name or MRN --
those identifiers can propagate into the bundle (hazard H6).

The PHI input gate is an **optional, best-effort** check that runs at the start
of `neurotcs audit`. It scans input column names and a sample of values for
**high-confidence direct identifiers** and, by default, **warns**. It never
blocks a normal audit unless you opt in.

## Behaviour

- **Default (warn):** if a probable identifier is detected, a `NOTE:` is
  printed to stderr and **the audit still runs**. A false positive is a
  dismissable note, not a broken audit.
- **`--refuse-phi` (opt-in, fail-closed):** the same detection instead
  **refuses** the run with exit code 4 (EXIT_INPUT) and writes no bundle.
  Use this where an institution mandates a hard gate.

## What it detects

- **Direct-identifier column names** (separator-insensitive): patient_name,
  first/last/full name, ssn, mrn / medical_record_number, dob /
  date_of_birth, address / street / zip, phone / fax, email, national_id,
  passport, insurance/policy/account number, and similar.
- **Strict value patterns**, requiring a clear majority of sampled values to
  match: US SSN (`NNN-NN-NNNN`), email address, US phone number.

## What it deliberately does NOT flag (false-positive avoidance)

The gate allowlists the **de-identified study vocabulary** the tool already
understands, so cohort data (ADNI / OASIS / NACC) never trips it:

- Study IDs: subject_id, patient_id, rid, ptid, usubjid, participant_id, id
- Visit / timepoint: visit, viscode, visitnum, event_id, timepoint, wave
- Visit/exam/scan/assessment **dates** (these are not dates-of-birth)
- De-identified demographics/values: age, sex, education, apoe, state,
  diagnosis, and the measurement-code / value columns.

Note that `patient_id` is a **study-ID synonym** in NeuroTCS (a de-identified
label), not a direct identifier -- it is allowlisted and does not warn.

## Honest limits -- this is NOT a de-identification guarantee

This is a best-effort warning for **common** direct-identifier patterns. It
does **not** and **cannot** catch all PHI: free-text names inside a notes
field, contextual identifiers, unusual formats, or quasi-identifiers in
combination are out of scope. **You remain responsible for de-identification.**
NeuroTCS is not a de-identification tool and makes no PHI-detection
completeness claim. The gate reduces the chance of an accidental PHI-bearing
audit; it does not certify that input is PHI-free.

## Why warn-by-default (not refuse-by-default)

The tool's entire validated use is de-identified cohort data that
superficially resembles identifiers (subject IDs, visit dates, ages). A
refuse-by-default gate would risk breaking that primary use on a false
positive. Warning-by-default keeps the tool usable on legitimate data while
still surfacing a probable-PHI signal; `--refuse-phi` is available for those
who want the hard gate.

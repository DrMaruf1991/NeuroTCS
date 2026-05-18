# How to apply this bundle and push to GitHub

You are in:
```
C:\Users\Dell\Downloads\NeuroTCS_extracted\NeuroTCS>
```

This is your local repo. The zip contains 12 files at the **exact same paths**
relative to the repo root. So you can just extract over the top.

## Step 1 — Extract the zip OVER your existing repo

In PowerShell:

```powershell
# cd into your repo (you're already here)
cd C:\Users\Dell\Downloads\NeuroTCS_extracted\NeuroTCS

# Extract the zip on top of the repo (overwrites the 12 changed files)
Expand-Archive -Path "$HOME\Downloads\neurotcs_v1.7.2_ci_patch.zip" -DestinationPath . -Force
```

Adjust `$HOME\Downloads\neurotcs_v1.7.2_ci_patch.zip` if you saved the zip somewhere else.

## Step 2 — Sanity-check locally before pushing

```powershell
# Run the same checks GitHub Actions runs
python -m pytest tests/ -q
ruff check src/ tests/
python scripts/verify_citations.py --offline
```

You should see:
- `202 passed`
- `All checks passed!`
- `All structural checks passed (offline mode).`

If you don't have `ruff` installed locally:
```powershell
pip install ruff
```

## Step 3 — Commit and push

```powershell
git status                                # see the 12 changed files
git add -A
git commit -m "v1.7.2: green CI — ruff lint clean + resolver false-positive fix

- Fix 12 ruff errors introduced by v1.7.1 modules (I001, UP035, UP034, B905, F841)
- Citation resolver: skip first_author check on annotated subsidiary
  references (Correction / Erratum / Scoping review / Cross-reference)
- Add Nature Health <-> Nat Health journal alias; broaden _normalize_journal
  to strip & and 'and' so Alzheimer's & Dementia matches Alzheimers Dement
- Hayden-class detection on primary citations preserved (regression-tested)
- Bump README badge tests-199/199 -> tests-202/202"

git push origin main
```

## Step 4 — Tag the release (optional but recommended)

```powershell
git tag -a v1.7.2 -m "v1.7.2 — CI hygiene patch on top of v1.7.1"
git push origin v1.7.2
```

## What you should see on GitHub after push

Both checks green:
- ✅ CI / Test (push)
- ✅ CI / Citation resolver (Crossref + PubMed EUtils) (push)

If the citation resolver job still has a red X after the push, look at the log.
There may be additional false positives in lines above what your screenshot
captured. If so, send me the new log tail and I'll patch the resolver again.

## Why not a PR?

You can absolutely do a PR if you want a clean audit trail:

```powershell
git checkout -b ci-fix-v1.7.2
git add -A
git commit -m "v1.7.2: green CI"
git push -u origin ci-fix-v1.7.2
# then open the PR on github.com
```

Direct push to main is fine since you're the only committer and the change
is mechanical / lint-clean. PR is better discipline once you have co-authors.

## What's in the zip — file checklist

```
README.md                                          (badge fix)
scripts/verify_citations.py                        (resolver smarts)
src/neurotcs/__init__.py                           (ruff I001)
src/neurotcs/sample_size/__init__.py               (ruff B905 + I001 if any)
src/neurotcs/fairness/__init__.py                  (ruff UP035)
src/neurotcs/scanner_factorial/__init__.py         (ruff UP035)
tests/audit_core/test_audit_core.py                (ruff I001)
tests/fairness/test_fairness.py                    (ruff I001)
tests/sample_size/test_sample_size.py              (ruff I001)
tests/scanner_factorial/test_scanner_factorial.py  (ruff F841 + UP034)
tests/silent_deployment/test_silent_deployment.py  (ruff I001)
tests/threshold_derivation/test_threshold_derivation.py (ruff I001)
```

That's it — 12 files, one zip, three PowerShell commands.
